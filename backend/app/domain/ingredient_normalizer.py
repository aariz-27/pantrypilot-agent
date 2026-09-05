"""Ingredient normalization (M08 foundation).

Pipeline per TECHNICAL_SPEC.md section 11:
unicode normalize -> lowercase -> trim -> safe punctuation cleanup ->
safe plural normalization -> exact canonical check -> alias lookup ->
UNKNOWN.

The constrained-LLM resolution step described in the spec is explicitly
out of scope for this ticket (no LLM runtime is implemented here).
Names that cannot be resolved deterministically return UNKNOWN, which
is the spec-mandated safe outcome ("UNKNOWN is preferable to unsafe
over-generalization" -- docs/DATA_INTEGRITY_POLICY.md).

This module never raises on malformed/malicious input; it always
degrades to UNKNOWN so callers (pantry input, recipe ingredient
parsing) remain safe under arbitrary user or provider text.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from app.domain.canonical_ingredients import CANONICAL_INGREDIENTS, INGREDIENT_ALIASES
from app.domain.models import NormalizationStatus

_PUNCTUATION_PATTERN = re.compile(r"[^a-z0-9\s-]")
_WHITESPACE_PATTERN = re.compile(r"\s+")


@dataclass(frozen=True)
class IngredientNormalizationResult:
    raw_name: str
    canonical_id: str | None
    status: NormalizationStatus


def _clean(raw_name: str) -> str:
    text = unicodedata.normalize("NFKC", raw_name)
    text = text.lower().strip()
    text = _PUNCTUATION_PATTERN.sub(" ", text)
    text = text.replace("-", " ")
    text = _WHITESPACE_PATTERN.sub(" ", text).strip()
    return text


def _to_snake(cleaned: str) -> str:
    return cleaned.replace(" ", "_")


def _singular_candidates(cleaned: str) -> list[str]:
    candidates: list[str] = []
    if cleaned.endswith("es") and len(cleaned) > 3:
        candidates.append(cleaned[:-2])
    if cleaned.endswith("s") and len(cleaned) > 2:
        candidates.append(cleaned[:-1])
    return candidates


def normalize_ingredient_name(
    raw_name: str,
    canonical_vocabulary: frozenset[str] = CANONICAL_INGREDIENTS,
    aliases: dict[str, str] = INGREDIENT_ALIASES,
) -> IngredientNormalizationResult:
    if not isinstance(raw_name, str):
        return IngredientNormalizationResult(str(raw_name), None, NormalizationStatus.UNKNOWN)

    cleaned = _clean(raw_name)
    if not cleaned:
        return IngredientNormalizationResult(raw_name, None, NormalizationStatus.UNKNOWN)

    snake = _to_snake(cleaned)
    if snake in canonical_vocabulary:
        return IngredientNormalizationResult(raw_name, snake, NormalizationStatus.EXACT)

    if cleaned in aliases:
        return IngredientNormalizationResult(raw_name, aliases[cleaned], NormalizationStatus.ALIAS)

    for singular in _singular_candidates(cleaned):
        singular_snake = _to_snake(singular)
        if singular_snake in canonical_vocabulary:
            return IngredientNormalizationResult(raw_name, singular_snake, NormalizationStatus.EXACT)
        if singular in aliases:
            return IngredientNormalizationResult(raw_name, aliases[singular], NormalizationStatus.ALIAS)

    return IngredientNormalizationResult(raw_name, None, NormalizationStatus.UNKNOWN)


@dataclass(frozen=True)
class PantryNormalizationResult:
    canonical_ids: frozenset[str]
    unresolved: tuple[str, ...] = field(default_factory=tuple)
    results: tuple[IngredientNormalizationResult, ...] = field(default_factory=tuple)


def normalize_pantry(
    raw_names: list[str],
    canonical_vocabulary: frozenset[str] = CANONICAL_INGREDIENTS,
    aliases: dict[str, str] = INGREDIENT_ALIASES,
) -> PantryNormalizationResult:
    """Normalize a raw pantry ingredient list into a duplicate-safe
    canonical set plus the list of raw names that could not be
    resolved. Duplicate raw entries resolving to the same canonical
    ingredient collapse to a single set member."""

    results = tuple(
        normalize_ingredient_name(raw, canonical_vocabulary, aliases) for raw in raw_names
    )
    canonical_ids = frozenset(r.canonical_id for r in results if r.canonical_id is not None)
    unresolved = tuple(r.raw_name for r in results if r.canonical_id is None)
    return PantryNormalizationResult(canonical_ids=canonical_ids, unresolved=unresolved, results=results)
