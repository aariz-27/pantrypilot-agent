"""Unified ingredient resolution pipeline (2026-09-13 ticket).

Implements the preferred resolution order (ticket section 9), amended
2026-09-13 (hotfix: generic-provider-direct-fallback) with an explicit
safe direct-term fallback (new step 4a) so an ordinary, correctly
spelled, broad term ("chicken", "rice") is never escalated to the LLM
or declared UNRESOLVED just because no SINGLE catalogue entry is
safely exact/singular-plural-equal to it:

    1. local canonical / alias match
    2. known cached provider mapping
    3. direct natural-language provider term
    4. RecipeAPI /ingredients lookup if needed
    4a. if the catalogue returned candidates but none safely matched,
        that non-empty result is itself evidence the term is real
        vocabulary -- preserve the term directly (PROVIDER_DIRECT)
        instead of escalating to the LLM
    5. controlled LLM intent interpretation, reached only when the
       catalogue returned NO candidates at all (genuine suspicion of a
       typo, e.g. "chiken")
    6. ground the LLM candidate against local/provider vocabulary
    7. if a safe match exists, proceed
    8. if ambiguous, return a structured unresolved/ambiguous state

Two distinct entry points, matching the two distinct problems this
ticket fixes (never conflated -- ticket section 1):

- `resolve_pantry_ingredient`: is a user's typed pantry phrase eligible
  to enter the search pipeline AT ALL (as a canonical id, or as a
  grounded free-text search anchor)? Used once per pantry item, at
  request-normalization time.
- `resolve_provider_search_term`: given an identity already accepted
  into the pipeline (a canonical id OR a free-text anchor), what exact
  text should reach RecipeAPI.io's `ingredients` filter? Used whenever
  the orchestrator is about to build a SearchStrategy.

Neither function ever sets a `RecipeIngredient.canonical_id` or touches
pricing -- that remains exclusively
app.domain.ingredient_normalizer.normalize_ingredient_name against the
local/admin taxonomy, called independently by
app.agent.tools.normalize_recipe_ingredients. See
app.domain.ingredient_resolution's module docstring for the full A-E
identity separation this ticket is built around.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.ingredient_normalizer import normalize_ingredient_name, normalize_raw_text_identity
from app.domain.ingredient_resolution import (
    IngredientResolutionState,
    ProviderIngredient,
    humanize_for_provider,
    select_safe_provider_match,
    singular_plural_query_variants,
)
from app.domain.models import NormalizationStatus
from app.domain.provider_errors import RecipeProviderError
from app.integrations.llm_provider import IngredientCorrectionRequest, LLMProvider, LLMProviderError
from app.integrations.provider_ingredient_cache import get_cached_match, set_cached_match


@dataclass(frozen=True)
class ResolvedProviderTerm:
    """What to actually send to RecipeAPI.io's `ingredients` search
    filter for one already-accepted anchor identity, plus why."""

    provider_term: str
    state: IngredientResolutionState
    matched_provider_id: str | None = None
    # 2026-09-13 hotfix (generic-provider-direct-fallback): whether the
    # catalogue query returned ANY candidates at all, even when `state`
    # is UNRESOLVED (none of them cleared a safe-match tier). This is
    # the deterministic signal resolve_pantry_ingredient uses to tell
    # an ordinary broad real word ("chicken") apart from a genuine typo
    # ("chiken") without an LLM call: a real word's catalogue query
    # returns plenty of related candidates even with no single exact
    # match; a typo's query returns nothing at all.
    had_candidates: bool = False


@dataclass(frozen=True)
class PantryTermResolution:
    """Whether/how one raw pantry phrase may enter the search pipeline.

    `canonical_id` is set only when local/admin taxonomy resolution
    succeeded (LOCAL_EXACT/LOCAL_ALIAS) -- this is the ONLY field
    pricing/pantry-matching may ever read; it is untouched by anything
    in this module (normalize_recipe_ingredients computes it
    independently for RECIPE ingredients, this module only mirrors the
    same lookup for PANTRY input).

    `search_anchor_identity` is the value safe to use as a grounded
    search anchor -- either the canonical_id (when resolved locally) or
    a free-text pseudo-identity (the cleaned raw/corrected phrase) when
    no canonical id exists but the term was still safely grounded.
    None when the term is not usable as an anchor at all (fully
    unresolved or ambiguous)."""

    raw_text: str
    canonical_id: str | None
    search_anchor_identity: str | None
    state: IngredientResolutionState


async def resolve_provider_search_term(
    term: str, catalogue_lookup, *, use_cache: bool = True
) -> ResolvedProviderTerm:
    """`catalogue_lookup` is an async callable(query: str) ->
    list[ProviderIngredient] (typically a RecipeAPIIOAdapter's
    search_ingredients bound method), or None when unavailable (no
    RecipeAPI.io configured, or a non-catalogue provider route)."""

    humanized = humanize_for_provider(term)
    cache_key = humanized.strip().lower()

    if use_cache:
        cached = get_cached_match(cache_key)
        if cached is not None:
            if cached.match is not None:
                return ResolvedProviderTerm(
                    cached.match.name, IngredientResolutionState.PROVIDER_CATALOG_RESOLVED, cached.match.provider_id
                )
            return ResolvedProviderTerm(
                humanized, IngredientResolutionState.UNRESOLVED, had_candidates=cached.had_candidates
            )

    if catalogue_lookup is None:
        return ResolvedProviderTerm(humanized, IngredientResolutionState.PROVIDER_DIRECT)

    match: ProviderIngredient | None = None
    state = IngredientResolutionState.UNRESOLVED
    had_candidates = False
    # Try the direct spelling first, and -- only if that returns no
    # safe match -- a bounded number of deterministic singular/plural
    # QUERY variants (confirmed live gap, 2026-09-13: RecipeAPI.io does
    # not stem plurals server-side, so "lamb chops" alone never returns
    # the provider's singular "Lamb chop" candidate to match against;
    # see singular_plural_query_variants). Matching is always evaluated
    # against the ORIGINAL humanized identity, regardless of which
    # query variant fetched the candidate list, so the safe-match tiers
    # (never "Lamb liver", never "Chicken broth") are unaffected.
    for query in (humanized, *singular_plural_query_variants(humanized)):
        try:
            candidates: list[ProviderIngredient] = await catalogue_lookup(query)
        except RecipeProviderError:
            # A catalogue-lookup failure is never fatal to the recipe
            # search itself (ticket section 24) -- fall back to the
            # best-effort humanized text and let the actual /recipes
            # search proceed.
            return ResolvedProviderTerm(humanized, IngredientResolutionState.PROVIDER_DIRECT)
        had_candidates = had_candidates or bool(candidates)
        match, state = select_safe_provider_match(humanized, candidates)
        if match is not None or state == IngredientResolutionState.AMBIGUOUS:
            break

    if use_cache:
        set_cached_match(cache_key, match, had_candidates=had_candidates)
    if match is not None:
        return ResolvedProviderTerm(match.name, state, match.provider_id)
    # UNRESOLVED or AMBIGUOUS at the catalogue level still returns a
    # usable term (ticket section 11's own alternative: "preserve the
    # raw user term if provider search can safely use it") -- this
    # function never blocks a search, it only tries to IMPROVE the term.
    return ResolvedProviderTerm(humanized, state, had_candidates=had_candidates)


async def resolve_pantry_ingredient(
    raw_text: str,
    canonical_vocabulary: frozenset[str],
    aliases: dict[str, str],
    *,
    catalogue_lookup=None,
    llm_provider: LLMProvider | None = None,
) -> PantryTermResolution:
    """Full 8-step pipeline (ticket section 9) for ONE raw pantry
    phrase. Never raises -- any provider/LLM failure degrades to the
    next step or, at worst, UNRESOLVED, exactly like today's behavior
    for input nothing can ground."""

    # Steps 1: local canonical / alias match (existing Module A/B logic,
    # completely unmodified -- this module only calls it).
    local = normalize_ingredient_name(raw_text, canonical_vocabulary, aliases)
    if local.canonical_id is not None:
        state = (
            IngredientResolutionState.LOCAL_EXACT
            if local.status == NormalizationStatus.EXACT
            else IngredientResolutionState.LOCAL_ALIAS
        )
        return PantryTermResolution(raw_text, local.canonical_id, local.canonical_id, state)

    cleaned = normalize_raw_text_identity(raw_text)
    if not cleaned:
        return PantryTermResolution(raw_text, None, None, IngredientResolutionState.UNRESOLVED)

    # Steps 2-4: cached provider mapping / direct term / catalogue
    # lookup -- resolve_provider_search_term already implements this
    # exact escalation order.
    provider_resolved = await resolve_provider_search_term(cleaned, catalogue_lookup)
    if provider_resolved.state == IngredientResolutionState.PROVIDER_CATALOG_RESOLVED:
        return PantryTermResolution(
            raw_text, None, provider_resolved.provider_term, IngredientResolutionState.PROVIDER_CATALOG_RESOLVED
        )
    if provider_resolved.state == IngredientResolutionState.AMBIGUOUS:
        # Ticket section 11: do not silently narrow -- an ambiguous
        # catalogue result is not, by itself, usable as a search anchor.
        return PantryTermResolution(raw_text, None, None, IngredientResolutionState.AMBIGUOUS)
    # Note: PROVIDER_DIRECT here (catalogue unavailable, or its lookup
    # failed entirely) deliberately falls through to the LLM step
    # below, exactly like before this hotfix -- an absent/failed
    # catalogue is NOT evidence the term is valid vocabulary (unlike
    # the had_candidates branch just below, which reflects an actual
    # successful catalogue query), so it must not skip typo correction.
    # A real typo ("chiken brest") with no catalogue configured must
    # still reach the LLM here, not be sent to the provider unchanged.
    if provider_resolved.state == IngredientResolutionState.UNRESOLVED and provider_resolved.had_candidates:
        # 2026-09-13 hotfix (generic-provider-direct-fallback): the
        # confirmed production root cause. A broad, ordinary, correctly
        # spelled term ("chicken", "rice") legitimately has no single
        # catalogue entry that is safely EXACT/singular-plural-equal to
        # it -- the catalogue instead returns many narrower entries
        # ("Chicken Breast", "Chicken Broth", ...). That non-empty
        # candidate list is itself strong deterministic evidence the
        # term is real vocabulary, not a typo -- so it must not be
        # escalated to the LLM (an ordinary word needs no "correction",
        # and per ticket section 3/12 of the prior tickets, PantryPilot
        # must never silently narrow "chicken" into one of those
        # candidates either). Preserve the user's own broad term as a
        # direct, ungrounded-but-safe search anchor instead of
        # declaring it fully UNRESOLVED and silently skipping recipe
        # search altogether (the exact previous production bug: /api/
        # recommend still returned 200 with no /recipes call ever made).
        return PantryTermResolution(
            raw_text, None, provider_resolved.provider_term, IngredientResolutionState.PROVIDER_DIRECT
        )

    # Steps 5-7: controlled LLM intent interpretation, reached only when
    # local resolution AND catalogue grounding both failed AND the
    # catalogue gave no evidence the term is real vocabulary (zero
    # candidates at all) -- an optional enhancement (ticket section 24)
    # for actual suspicious/unresolved spellings, never required for an
    # ordinary correctly-spelled ingredient (those are now handled
    # above without ever reaching the LLM).
    if llm_provider is not None:
        try:
            correction = await llm_provider.propose_ingredient_correction(IngredientCorrectionRequest(cleaned))
        except LLMProviderError:
            correction = None

        if correction is not None and correction.proposed_name:
            proposed = correction.proposed_name.strip()
            # The proposal is NEVER trusted directly -- re-run it through
            # the exact same deterministic local-then-catalogue grounding
            # steps 1-4 above (ticket section 10: "PantryPilot must
            # ground those proposals"; section 35: "if grounding fails,
            # do not accept the fabricated correction").
            reground_local = normalize_ingredient_name(proposed, canonical_vocabulary, aliases)
            if reground_local.canonical_id is not None:
                return PantryTermResolution(
                    raw_text,
                    reground_local.canonical_id,
                    reground_local.canonical_id,
                    IngredientResolutionState.LLM_CORRECTED_AND_GROUNDED,
                )
            reground_provider = await resolve_provider_search_term(proposed, catalogue_lookup)
            if reground_provider.state == IngredientResolutionState.PROVIDER_CATALOG_RESOLVED:
                return PantryTermResolution(
                    raw_text,
                    None,
                    reground_provider.provider_term,
                    IngredientResolutionState.LLM_CORRECTED_AND_GROUNDED,
                )
            # LLM proposal did not ground against anything real -- never
            # accepted (falls through to UNRESOLVED below), never used
            # even as free text (an ungrounded LLM guess is exactly the
            # "fabricated correction" ticket section 35 forbids).

    # Step 8: nothing grounded it -- structured unresolved state,
    # identical to today's behavior for input nothing can explain.
    return PantryTermResolution(raw_text, None, None, IngredientResolutionState.UNRESOLVED)
