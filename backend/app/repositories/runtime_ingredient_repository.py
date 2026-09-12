"""Merged built-in + admin-managed canonical ingredient/alias resolution
(runtime integration, 2026-09-13 -- closes the gap documented in
app.db.admin_schema and docs/admin/ADMIN_DASHBOARD.md section 1).

ONE coherent resolution model (ticket section 5): the built-in
app.domain.grocery_taxonomy vocabulary/aliases remain the frozen,
heavily-tested foundation Module A/B was built and reviewed against;
admin-managed DB records (`canonical_ingredients` + `ingredient_aliases`,
both introduced by the admin dashboard ticket) are an ADDITIVE overlay
on top, never a second, independently-authoritative resolver.

Precedence rules (ticket section 7), documented explicitly here so the
merge logic below is a direct implementation of stated policy, not an
implicit accident of dict-merge ordering:

1. A built-in canonical id's identity is never redefined by a DB row --
   canonical_ingredients rows only ever ADD ids the built-in taxonomy
   doesn't already have. (There is nothing to "override" for an id the
   built-in taxonomy already defines: the built-in id already fully
   defines the resolver's notion of that ingredient's identity: the
   admin dashboard's own display_name/default_unit for such an id is
   administrative metadata about that ingredient, never consulted by
   this resolver.)
2. An alias already resolving (via the built-in taxonomy OR an existing
   active DB row) to canonical id A can never be silently repointed to
   a different canonical id B by a later admin write. This is enforced
   at WRITE TIME (ticket section 7: "prefer preventing conflicts during
   admin writes") -- see app.repositories.admin_ingredient_repository.
   AdminIngredientRepository.create_alias, which now also consults this
   module's built-in vocabulary before accepting a new alias, and
   app.api.admin_ingredients's dependency wiring. Belt-and-braces: even
   if a conflicting row somehow existed, the merge below still resolves
   deterministically by construction (built-in aliases are merged in
   LAST, so they always win a raw key collision) rather than raising or
   guessing.
3. If the DB is unreachable, unmigrated (no admin schema applied), or
   the admin subsystem was never configured for this deployment, every
   function here falls back silently to the exact built-in-only result
   -- the public app must never fail, degrade unpredictably, or even
   log a warning merely because the admin subsystem isn't set up
   (ticket section 6). Verified by test for: missing database file,
   missing `canonical_ingredients` table (schema.py ran, admin_schema.py
   never did), missing `active` column (pre-migration ingredient_aliases
   shape), and db_path=None (admin subsystem not wired to a path at all).

Caching (ticket section 12): a short, fixed TTL, invalidated
immediately by every admin ingredient/alias mutation (see
app.api.admin_ingredients / app.api.admin_prices is NOT involved --
pricing has no such gap, see docs/admin/ADMIN_DASHBOARD.md section 1).
This is the "simplest robust design" the ticket explicitly permits
choosing: no cross-process pub/sub, no version numbers -- an admin edit
is visible in the SAME process within one cache lookup (explicit
invalidation) and in every process within _CACHE_TTL_SECONDS at the
outside (competition deployment is a single Oracle Cloud VM, consistent
with app.rate_limit's own documented single-process assumption).
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass

from app.db.connection import connection_scope
from app.domain.grocery_taxonomy import CANONICAL_GROCERY_INGREDIENTS, RECIPE_INGREDIENT_ALIASES

_CACHE_TTL_SECONDS = 30.0


@dataclass(frozen=True)
class MergedIngredientVocabulary:
    canonical_ids: frozenset[str]
    # alias text (already normalized: trimmed, lowercased, whitespace-
    # collapsed, matching app.repositories.admin_ingredient_repository.
    # normalize_alias_text) -> canonical_id.
    aliases: dict[str, str]


_cache: dict[str, tuple[float, MergedIngredientVocabulary]] = {}


def invalidate_runtime_ingredient_cache(db_path: str | None = None) -> None:
    """Call this immediately after any admin ingredient/alias mutation
    (create/update/reassign/deactivate) so the edit is visible on this
    process's very next lookup rather than waiting out the TTL.
    db_path=None clears every cached entry (used by tests and safe as a
    blanket call); a specific path clears only that deployment's entry.
    """
    if db_path is None:
        _cache.clear()
    else:
        _cache.pop(db_path, None)


def _load_db_overlay(db_path: str) -> tuple[frozenset[str], dict[str, str]]:
    """Best-effort DB read. Never raises -- any failure (missing file,
    missing table, missing column, corrupt database, locked file) is
    treated identically to "no admin data exists yet", per ticket
    section 6. Returns (extra_canonical_ids, extra_aliases)."""

    try:
        with connection_scope(db_path, read_only=True) as connection:
            ingredient_rows = connection.execute(
                "SELECT canonical_id FROM canonical_ingredients WHERE status = 'active'"
            ).fetchall()
            alias_rows = connection.execute(
                "SELECT alias, canonical_id FROM ingredient_aliases WHERE active = 1"
            ).fetchall()
    except (sqlite3.Error, FileNotFoundError, OSError):
        return frozenset(), {}

    extra_ids = frozenset(row["canonical_id"] for row in ingredient_rows)
    extra_aliases = {row["alias"]: row["canonical_id"] for row in alias_rows}
    return extra_ids, extra_aliases


def get_merged_vocabulary(db_path: str | None) -> MergedIngredientVocabulary:
    """The one coherent canonical resolution surface every live call
    site (autocomplete, pantry normalization, anchor grounding, recipe-
    ingredient normalization) now reads through. db_path=None (admin
    subsystem has no database path configured at all) never attempts
    any I/O and returns the built-in vocabulary completely unchanged --
    byte-identical to calling the built-in constants directly, which is
    exactly what every one of these call sites did before this change.
    """

    if db_path is None:
        return MergedIngredientVocabulary(CANONICAL_GROCERY_INGREDIENTS, RECIPE_INGREDIENT_ALIASES)

    now = time.monotonic()
    cached = _cache.get(db_path)
    if cached is not None and (now - cached[0]) < _CACHE_TTL_SECONDS:
        return cached[1]

    extra_ids, extra_aliases = _load_db_overlay(db_path)

    # Precedence rule 1 & 3 above: built-in ids/aliases are authoritative
    # over any (should-be-impossible, write-time-prevented) DB
    # collision -- RECIPE_INGREDIENT_ALIASES is merged in LAST so its
    # values always win a raw key collision.
    merged_ids = CANONICAL_GROCERY_INGREDIENTS | extra_ids
    merged_aliases = {**extra_aliases, **RECIPE_INGREDIENT_ALIASES}

    result = MergedIngredientVocabulary(canonical_ids=merged_ids, aliases=merged_aliases)
    _cache[db_path] = (now, result)
    return result


def alias_conflicts_with_builtin(alias_text: str, canonical_id: str, db_path: str | None) -> str | None:
    """Used at ADMIN WRITE TIME (ticket section 7: "prefer preventing
    conflicts during admin writes") -- returns the built-in canonical id
    the alias/id already resolves to if creating this alias would
    silently remap a built-in identity, or None if the write is safe.

    Two distinct conflict shapes are checked:
    - the alias text IS ITSELF a canonical id the built-in taxonomy
      already defines (e.g. admin tries to alias "onion" to
      "green_chili" -- "onion" is already its own canonical identity);
    - the alias text already resolves, via the built-in
      RECIPE_INGREDIENT_ALIASES table, to a DIFFERENT canonical id than
      the one being requested.
    """

    vocab = get_merged_vocabulary(db_path)
    if alias_text in CANONICAL_GROCERY_INGREDIENTS and alias_text != canonical_id:
        return alias_text
    built_in_target = RECIPE_INGREDIENT_ALIASES.get(alias_text)
    if built_in_target is not None and built_in_target != canonical_id:
        return built_in_target
    return None
