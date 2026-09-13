"""app.agent.ingredient_resolution -- the wired-together pipeline
(local -> cache -> catalogue -> LLM -> reground). Ticket sections 9-11,
20, 22-24, 35.
"""

from __future__ import annotations

import pytest

from app.agent.ingredient_resolution import resolve_pantry_ingredient, resolve_provider_search_term
from app.domain.grocery_taxonomy import CANONICAL_GROCERY_INGREDIENTS, RECIPE_INGREDIENT_ALIASES
from app.domain.ingredient_resolution import IngredientResolutionState, ProviderIngredient
from app.domain.provider_errors import RecipeProviderUnavailableError
from app.integrations.llm_provider import IngredientCorrectionRequest, IngredientCorrectionResponse
from app.integrations.provider_ingredient_cache import clear_provider_ingredient_cache


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_provider_ingredient_cache()
    yield
    clear_provider_ingredient_cache()


class _FakeCatalogue:
    """Callable(query) -> list[ProviderIngredient], recording calls."""

    def __init__(self, responses: dict[str, list[ProviderIngredient]]):
        self._responses = responses
        self.calls: list[str] = []

    async def __call__(self, query: str) -> list[ProviderIngredient]:
        self.calls.append(query)
        return self._responses.get(query.strip().lower(), [])


class _FailingCatalogue:
    async def __call__(self, query: str) -> list[ProviderIngredient]:
        raise RecipeProviderUnavailableError("scripted failure")


class _FakeLLM:
    def __init__(self, corrections: dict[str, str | None]):
        self._corrections = corrections
        self.requests: list[IngredientCorrectionRequest] = []

    async def propose_ingredient_correction(self, request: IngredientCorrectionRequest) -> IngredientCorrectionResponse:
        self.requests.append(request)
        return IngredientCorrectionResponse(proposed_name=self._corrections.get(request.raw_text), model_name="fake")


# -- resolve_provider_search_term -------------------------------------------


async def test_provider_direct_when_no_catalogue_available():
    resolved = await resolve_provider_search_term("lamb_chops", None)
    assert resolved.provider_term == "lamb chops"
    assert resolved.state == IngredientResolutionState.PROVIDER_DIRECT


async def test_provider_catalog_resolved_uses_safe_match():
    catalogue = _FakeCatalogue({"lamb chops": [ProviderIngredient("1139", "Lamb chop", "meat")]})
    resolved = await resolve_provider_search_term("lamb_chops", catalogue)
    assert resolved.provider_term == "Lamb chop"
    assert resolved.state == IngredientResolutionState.PROVIDER_CATALOG_RESOLVED
    assert resolved.matched_provider_id == "1139"


async def test_provider_catalog_resolved_via_singular_query_variant_when_plural_query_returns_nothing():
    # Confirmed live, 2026-09-13: RecipeAPI.io's GET /ingredients search
    # does not stem plurals server-side -- querying "lamb chops" (the
    # naive humanization of canonical id lamb_chops) returns ZERO
    # candidates, even though the provider's own catalogue lists the
    # singular "Lamb chop". select_safe_provider_match's candidate-level
    # singular/plural comparison can only help once a query actually
    # RETURNS that candidate -- this is the real production root cause,
    # at the query level, not only at the candidate-matching level.
    catalogue = _FakeCatalogue({"lamb chop": [ProviderIngredient("1139", "Lamb chop", "meat")]})
    resolved = await resolve_provider_search_term("lamb_chops", catalogue)
    assert resolved.provider_term == "Lamb chop"
    assert resolved.state == IngredientResolutionState.PROVIDER_CATALOG_RESOLVED
    assert catalogue.calls == ["lamb chops", "lamb chop"]


async def test_catalogue_failure_falls_back_to_humanized_text_never_blocks():
    resolved = await resolve_provider_search_term("lamb_chops", _FailingCatalogue())
    assert resolved.provider_term == "lamb chops"
    assert resolved.state == IngredientResolutionState.PROVIDER_DIRECT


async def test_cache_prevents_a_repeated_catalogue_lookup():
    catalogue = _FakeCatalogue({"chicken": [ProviderIngredient("125", "Chicken", "poultry")]})
    first = await resolve_provider_search_term("chicken", catalogue)
    second = await resolve_provider_search_term("chicken", catalogue)
    assert first.provider_term == second.provider_term == "Chicken"
    assert len(catalogue.calls) == 1


async def test_cache_also_remembers_a_no_match_result():
    catalogue = _FakeCatalogue({})
    await resolve_provider_search_term("nonexistent thing", catalogue)
    await resolve_provider_search_term("nonexistent thing", catalogue)
    # The first resolution tries the direct spelling plus its one
    # deterministic plural-variant escalation (both come back empty);
    # the second resolution is served entirely from cache, adding zero
    # further calls.
    assert len(catalogue.calls) == 2


# -- resolve_pantry_ingredient (full pipeline) -------------------------------


async def test_local_exact_never_touches_catalogue_or_llm():
    catalogue = _FakeCatalogue({})
    resolution = await resolve_pantry_ingredient(
        "onion", CANONICAL_GROCERY_INGREDIENTS, RECIPE_INGREDIENT_ALIASES, catalogue_lookup=catalogue
    )
    assert resolution.canonical_id == "onion"
    assert resolution.state == IngredientResolutionState.LOCAL_EXACT
    assert catalogue.calls == []


async def test_local_alias_resolves_via_existing_taxonomy():
    resolution = await resolve_pantry_ingredient(
        "capsicum", CANONICAL_GROCERY_INGREDIENTS, RECIPE_INGREDIENT_ALIASES
    )
    assert resolution.canonical_id == "bell_pepper"
    assert resolution.state == IngredientResolutionState.LOCAL_ALIAS


async def test_generic_chicken_grounds_via_catalogue_without_local_canonical_id():
    # Ticket's own confirmed production bug: "chicken" has no generic
    # PantryPilot canonical id, but RecipeAPI.io's catalogue has one.
    catalogue = _FakeCatalogue({"chicken": [ProviderIngredient("125", "Chicken", "poultry")]})
    resolution = await resolve_pantry_ingredient(
        "chicken", CANONICAL_GROCERY_INGREDIENTS, RECIPE_INGREDIENT_ALIASES, catalogue_lookup=catalogue
    )
    assert resolution.canonical_id is None  # never fabricated -- pricing stays unknown
    assert resolution.search_anchor_identity == "Chicken"
    assert resolution.state == IngredientResolutionState.PROVIDER_CATALOG_RESOLVED


# -- 2026-09-13 hotfix (generic-provider-direct-fallback) --------------------
# Confirmed production root cause: "chicken"'s catalogue query returns
# many candidates (Chicken Breast, Chicken Broth, ...) but none is
# safely EXACT/singular-plural-equal to "chicken" itself -- previously
# this fell straight to the LLM, which correctly declined to "correct"
# an already-valid word, leaving the term fully UNRESOLVED and
# skipping recipe search entirely (HTTP 200, zero /recipes calls).


async def test_broad_term_with_only_narrower_catalogue_candidates_falls_back_to_direct_term():
    catalogue = _FakeCatalogue(
        {
            "chicken": [
                ProviderIngredient("1", "Chicken Breast", "poultry"),
                ProviderIngredient("2", "Chicken Broth", "poultry"),
                ProviderIngredient("3", "Chicken Drumsticks", "poultry"),
            ]
        }
    )
    resolution = await resolve_pantry_ingredient(
        "chicken", CANONICAL_GROCERY_INGREDIENTS, RECIPE_INGREDIENT_ALIASES, catalogue_lookup=catalogue
    )
    assert resolution.canonical_id is None  # never fabricated -- pricing stays unknown
    assert resolution.search_anchor_identity == "chicken"  # the user's own term, never narrowed
    assert resolution.state == IngredientResolutionState.PROVIDER_DIRECT


async def test_broad_term_fallback_never_calls_the_llm():
    llm = _FakeLLM({})
    catalogue = _FakeCatalogue(
        {"rice": [ProviderIngredient("1", "Arborio rice", "grain"), ProviderIngredient("2", "Basmati rice", "grain")]}
    )
    resolution = await resolve_pantry_ingredient(
        "rice", CANONICAL_GROCERY_INGREDIENTS, RECIPE_INGREDIENT_ALIASES, catalogue_lookup=catalogue, llm_provider=llm
    )
    assert resolution.search_anchor_identity == "rice"
    assert resolution.state == IngredientResolutionState.PROVIDER_DIRECT
    assert llm.requests == []  # ordinary valid term never needs LLM escalation


async def test_broad_term_never_narrowed_to_one_of_the_catalogue_candidates():
    # Ticket section 3/12: "chicken" must never silently become
    # "Chicken Breast" merely because that is one of the candidates
    # returned -- the fallback must preserve the ORIGINAL user term.
    catalogue = _FakeCatalogue({"chicken": [ProviderIngredient("1", "Chicken Breast", "poultry")]})
    resolution = await resolve_pantry_ingredient(
        "chicken", CANONICAL_GROCERY_INGREDIENTS, RECIPE_INGREDIENT_ALIASES, catalogue_lookup=catalogue
    )
    assert resolution.search_anchor_identity == "chicken"
    assert resolution.search_anchor_identity != "Chicken Breast"


async def test_catalogue_unavailable_still_escalates_to_llm_unlike_a_confirmed_real_word():
    # A missing/failed catalogue gives NO evidence either way about the
    # term -- unlike the had_candidates branch above, which reflects an
    # actual successful catalogue query returning real vocabulary. So a
    # typo with no catalogue configured must still reach the LLM,
    # exactly like before this hotfix (otherwise "chiken brest" with no
    # catalogue configured would be sent to the provider unchanged).
    llm = _FakeLLM({"chiken": "chicken"})
    resolution = await resolve_pantry_ingredient(
        "chiken", CANONICAL_GROCERY_INGREDIENTS, RECIPE_INGREDIENT_ALIASES, catalogue_lookup=None, llm_provider=llm
    )
    assert llm.requests != []


async def test_zero_candidate_typo_still_escalates_to_llm_unlike_a_broad_real_word():
    # The distinguishing signal is candidate presence, not merely "no
    # exact match": a genuine typo's catalogue query returns nothing at
    # all, which is exactly when LLM correction remains warranted.
    llm = _FakeLLM({"chiken": "chicken"})
    catalogue = _FakeCatalogue({"chicken": [ProviderIngredient("125", "Chicken", "poultry")]})
    resolution = await resolve_pantry_ingredient(
        "chiken", CANONICAL_GROCERY_INGREDIENTS, RECIPE_INGREDIENT_ALIASES,
        catalogue_lookup=catalogue, llm_provider=llm,
    )
    assert llm.requests != []
    assert resolution.search_anchor_identity == "Chicken"
    assert resolution.state == IngredientResolutionState.LLM_CORRECTED_AND_GROUNDED


async def test_ambiguous_catalogue_result_never_silently_narrowed():
    catalogue = _FakeCatalogue(
        {"chik": [ProviderIngredient("1", "chik", "poultry"), ProviderIngredient("2", "Chik", "poultry")]}
    )
    resolution = await resolve_pantry_ingredient(
        "chik", CANONICAL_GROCERY_INGREDIENTS, RECIPE_INGREDIENT_ALIASES, catalogue_lookup=catalogue
    )
    assert resolution.canonical_id is None
    assert resolution.search_anchor_identity is None
    assert resolution.state == IngredientResolutionState.AMBIGUOUS


# -- 2026-09-13 hotfix: "generic free-text must always reach recipe search" -


async def test_focused_1_empty_catalogue_chicken_falls_back_to_provider_direct():
    # Production evidence: GET /ingredients?search=chicken -> 200 (with
    # zero candidates this time), Anthropic -> 200, POST /recommend ->
    # 200, but NO /recipes call. Catalogue queried and genuinely empty
    # (had_candidates=False) must still preserve "chicken" as a usable
    # search term, not declare it UNRESOLVED.
    resolution = await resolve_pantry_ingredient(
        "chicken", CANONICAL_GROCERY_INGREDIENTS, RECIPE_INGREDIENT_ALIASES, catalogue_lookup=_FakeCatalogue({})
    )
    assert resolution.canonical_id is None
    assert resolution.search_anchor_identity == "chicken"
    assert resolution.state == IngredientResolutionState.PROVIDER_DIRECT


async def test_focused_2_llm_declines_to_correct_original_term_still_returned_as_provider_direct():
    # The LLM is available and IS asked (catalogue was empty), but
    # correctly declines to "fix" an already-valid word (no confident
    # correction) -- the ORIGINAL term must still reach the provider.
    llm = _FakeLLM({})  # no correction for any input
    resolution = await resolve_pantry_ingredient(
        "chicken", CANONICAL_GROCERY_INGREDIENTS, RECIPE_INGREDIENT_ALIASES,
        catalogue_lookup=_FakeCatalogue({}), llm_provider=llm,
    )
    assert llm.requests != []  # confirms the LLM really was consulted first
    assert resolution.canonical_id is None
    assert resolution.search_anchor_identity == "chicken"
    assert resolution.state == IngredientResolutionState.PROVIDER_DIRECT


async def test_unresolvable_text_still_falls_back_to_provider_direct_without_llm():
    # 2026-09-13 hotfix ("generic free-text must always reach recipe
    # search"): nothing grounds this term better, but it is still
    # non-empty user-typed text -- preserved as PROVIDER_DIRECT rather
    # than declared UNRESOLVED, so recipe search is never silently
    # skipped. Never fabricated into a canonical id or a candidate name.
    resolution = await resolve_pantry_ingredient(
        "zzznotarealthing", CANONICAL_GROCERY_INGREDIENTS, RECIPE_INGREDIENT_ALIASES, catalogue_lookup=_FakeCatalogue({})
    )
    assert resolution.canonical_id is None
    assert resolution.search_anchor_identity == "zzznotarealthing"
    assert resolution.state == IngredientResolutionState.PROVIDER_DIRECT


async def test_typo_correction_grounds_to_local_canonical_id():
    llm = _FakeLLM({"chiken brest": "chicken breast"})
    resolution = await resolve_pantry_ingredient(
        "chiken brest", CANONICAL_GROCERY_INGREDIENTS, RECIPE_INGREDIENT_ALIASES,
        catalogue_lookup=_FakeCatalogue({}), llm_provider=llm,
    )
    assert resolution.canonical_id == "chicken_breast"
    assert resolution.state == IngredientResolutionState.LLM_CORRECTED_AND_GROUNDED
    assert llm.requests[0].raw_text == "chiken brest"


async def test_typo_correction_grounds_via_catalogue_when_no_local_id():
    llm = _FakeLLM({"muton": "mutton"})
    catalogue = _FakeCatalogue({"mutton": [ProviderIngredient("3944", "Mutton", "meat")]})
    resolution = await resolve_pantry_ingredient(
        "muton", CANONICAL_GROCERY_INGREDIENTS, RECIPE_INGREDIENT_ALIASES,
        catalogue_lookup=catalogue, llm_provider=llm,
    )
    assert resolution.canonical_id is None
    assert resolution.search_anchor_identity == "Mutton"
    assert resolution.state == IngredientResolutionState.LLM_CORRECTED_AND_GROUNDED


async def test_ungrounded_llm_proposal_is_never_accepted():
    # Ticket section 35: if grounding fails, do not accept the LLM's
    # fabricated correction ("madeupingredient" must never appear
    # anywhere in the result). Falls back to the user's own ORIGINAL
    # text as PROVIDER_DIRECT instead (2026-09-13 hotfix) -- a
    # different thing entirely from trusting the LLM's guess.
    llm = _FakeLLM({"asdkjhasd": "madeupingredient"})
    resolution = await resolve_pantry_ingredient(
        "asdkjhasd", CANONICAL_GROCERY_INGREDIENTS, RECIPE_INGREDIENT_ALIASES,
        catalogue_lookup=_FakeCatalogue({}), llm_provider=llm,
    )
    assert resolution.canonical_id is None
    assert resolution.search_anchor_identity == "asdkjhasd"
    assert resolution.search_anchor_identity != "madeupingredient"
    assert resolution.state == IngredientResolutionState.PROVIDER_DIRECT


async def test_llm_not_called_when_catalogue_already_grounded_it():
    # Ticket section 25: only escalate when needed.
    llm = _FakeLLM({})
    catalogue = _FakeCatalogue({"chicken": [ProviderIngredient("125", "Chicken", "poultry")]})
    await resolve_pantry_ingredient(
        "chicken", CANONICAL_GROCERY_INGREDIENTS, RECIPE_INGREDIENT_ALIASES,
        catalogue_lookup=catalogue, llm_provider=llm,
    )
    assert llm.requests == []


async def test_no_llm_provider_still_resolves_via_local_and_catalogue():
    # Ticket section 24: fallback without LLM.
    catalogue = _FakeCatalogue({"chicken": [ProviderIngredient("125", "Chicken", "poultry")]})
    resolution = await resolve_pantry_ingredient(
        "chicken", CANONICAL_GROCERY_INGREDIENTS, RECIPE_INGREDIENT_ALIASES, catalogue_lookup=catalogue, llm_provider=None
    )
    assert resolution.search_anchor_identity == "Chicken"


async def test_no_llm_provider_still_falls_back_to_provider_direct_for_a_true_typo():
    # Without an LLM available to correct it, "chiken brest" is still
    # preserved as PROVIDER_DIRECT (verbatim, uncorrected) rather than
    # UNRESOLVED -- ticket section 24's fallback-without-LLM guarantee,
    # extended by the 2026-09-13 hotfix so the pipeline never dead-ends.
    resolution = await resolve_pantry_ingredient(
        "chiken brest", CANONICAL_GROCERY_INGREDIENTS, RECIPE_INGREDIENT_ALIASES,
        catalogue_lookup=_FakeCatalogue({}), llm_provider=None,
    )
    assert resolution.canonical_id is None
    assert resolution.search_anchor_identity == "chiken brest"
    assert resolution.state == IngredientResolutionState.PROVIDER_DIRECT
