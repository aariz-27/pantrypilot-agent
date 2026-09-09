"""RecipeAPI.io adapter (M05): the primary live recipe provider.

Confirmed live contract (fetched from https://recipeapi.io/docs/ and
https://recipeapi.io/docs/api-reference/ on 2026-09-05, private repo
session -- not re-verified beyond that fetch until the live smoke test
in this same ticket):

- Base URL: https://recipeapi.io/api/v1
- Auth: `Authorization: Bearer <key>` header
- GET /recipes       -- search/list. Query params: page (default 1),
  per_page (default 10, free-plan max 10), search (free text),
  ingredients (comma-separated names, relevance-ranked -- NOT strict
  AND), lang (en/fr/es).
- GET /recipes/{id}  -- recipe detail.
- List envelope:   {"data": [...], "links": {...}, "meta": {
  "current_page", "last_page", "per_page", "total", ...}}
- Detail envelope: {"data": {...}, "meta": {"language": ...}}
- Error envelope:  {"error": {"code": "...", "message": "..."}}
- Documented status codes: 401 UNAUTHENTICATED, 402
  PLAN_FEATURE_UNAVAILABLE, 404 NOT_FOUND, 422 UNSUPPORTED_LANGUAGE,
  429 RATE_LIMIT / USAGE_LIMIT_EXCEEDED.
- Documented recipe object fields: id, name, description, difficulty,
  meal_type, cuisine, dietary_tags, servings, prep_time (minutes),
  cook_time (minutes), calories_per_serving, protein, instructions
  (array of strings), ingredients (array of {id, name, category,
  quantity, unit, optional}). image_url/source_url are NOT documented
  as existing fields -- this adapter never fabricates them and only
  uses them if actually present in a response.
- Module E live verification (2026-09-08, 2 bounded live calls -- 1
  search, 1 detail): `difficulty` IS present with real lowercase string
  values ("medium", "hard" observed; "easy" also a documented/expected
  value) -- mapped via app.domain.models.Difficulty.from_raw(), which
  falls back to UNKNOWN for anything unrecognized or absent, never
  guessed. `image_url`/`source_url` were `null` on every real response
  observed, confirming the frontend's "no image available"/omit-
  source-link fallback paths are load-bearing, not theoretical.

UNCONFIRMED pending the live smoke test in this ticket: the exact query
parameter name for cuisine filtering (the provider's own "Query
Builder" documentation confirms a cuisine filter exists, but the
parameter reference page returned 404 when fetched). This adapter sends
a `cuisine` query parameter, consistent with the provider's documented
`cuisine` recipe-object field and TECHNICAL_SPEC.md's already-recorded
August finding that "a supported specific cuisine filter ... can
materially improve relevance". See the PR report for the smoke-test
verification of this parameter.

TECHNICAL_SPEC.md's already-established facts this adapter preserves:
multi-ingredient search is relevance-ranked, not strict AND; provider
`max_prep_time` constrains prep time only (never substituted for
PantryPilot's local prep+cook total-time rule, which lives unchanged in
app.domain.constraint_evaluator from PP-001).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from itertools import zip_longest

import httpx

from app.config import Settings
from app.domain.errors import InvalidInputError
from app.domain.models import Difficulty, NormalizationStatus, Recipe, RecipeIngredient
from app.domain.provider_errors import (
    RecipeNotFoundError,
    RecipeProviderConfigurationError,
    RecipeProviderError,
    RecipeProviderMalformedResponseError,
    RecipeProviderRateLimitedError,
    RecipeProviderTimeoutError,
    RecipeProviderUnavailableError,
)
from app.recipe.mapping import build_recipe_id, require_usable_identity
from app.recipe.provider import (
    MAX_PAGE_SIZE,
    PROVIDER_SEARCH_TERM_OVERRIDES,
    SearchResult,
    SearchResultItem,
    SearchStrategy,
    dedupe_search_results,
)

logger = logging.getLogger(__name__)

_RETRY_BACKOFF_SECONDS = 0.5


class RecipeAPIIOAdapter:
    """Primary live RecipeProvider. Implements the RecipeProvider
    Protocol structurally (see app.recipe.provider.RecipeProvider)."""

    provider_name = "recipeapi_io"

    BASE_URL = "https://recipeapi.io/api/v1"
    DEFAULT_TIMEOUT_SECONDS = 5.0
    DEFAULT_MAX_RETRIES = 1  # bounded: at most one retry, only for timeout/network/5xx

    # Reliability invariants (PP-002 review finding): these are enforced
    # by the adapter itself, not merely by the defaults above, so a
    # caller cannot construct an adapter that bypasses bounded retry,
    # deterministic termination, or the approved timeout ceiling.
    MAX_TIMEOUT_SECONDS = 5.0
    ALLOWED_MAX_RETRIES = (0, 1)


    def __init__(
        self,
        settings: Settings,
        *,
        http_client: httpx.AsyncClient | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        if max_retries not in self.ALLOWED_MAX_RETRIES:
            raise InvalidInputError(
                f"max_retries must be one of {self.ALLOWED_MAX_RETRIES} (got {max_retries!r}); "
                "PP-002 requires a bounded, deterministic retry policy"
            )
        if not (0 < timeout_seconds <= self.MAX_TIMEOUT_SECONDS):
            raise InvalidInputError(
                f"timeout_seconds must be positive and must not exceed "
                f"{self.MAX_TIMEOUT_SECONDS} seconds (got {timeout_seconds!r})"
            )

        if not settings.recipeapi_io_configured or settings.recipeapi_io_api_key is None:
            raise RecipeProviderConfigurationError("RECIPEAPI_IO_API_KEY is not configured")

        self._api_key = settings.recipeapi_io_api_key.get_secret_value()
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(base_url=self.BASE_URL, timeout=timeout_seconds)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> "RecipeAPIIOAdapter":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    async def _request(self, method: str, path: str, params: dict[str, object] | None = None) -> dict:
        for attempt in range(self._max_retries + 1):
            start = asyncio.get_event_loop().time()
            try:
                response = await self._client.request(
                    method, path, params=params, headers=self._headers(), timeout=self._timeout_seconds
                )
            except httpx.TimeoutException as exc:
                logger.warning(
                    "recipeapi_io request timeout provider=%s path=%s attempt=%d",
                    self.provider_name, path, attempt + 1,
                )
                if attempt < self._max_retries:
                    await asyncio.sleep(_RETRY_BACKOFF_SECONDS)
                    continue
                raise RecipeProviderTimeoutError(
                    f"RecipeAPI.io request to {path} timed out after {attempt + 1} attempt(s)"
                ) from exc
            except httpx.TransportError as exc:
                logger.warning(
                    "recipeapi_io transport error provider=%s path=%s attempt=%d",
                    self.provider_name, path, attempt + 1,
                )
                if attempt < self._max_retries:
                    await asyncio.sleep(_RETRY_BACKOFF_SECONDS)
                    continue
                raise RecipeProviderUnavailableError(
                    f"RecipeAPI.io request to {path} failed after {attempt + 1} attempt(s)"
                ) from exc

            duration_ms = (asyncio.get_event_loop().time() - start) * 1000
            logger.info(
                "recipeapi_io request provider=%s path=%s status=%d duration_ms=%.1f attempt=%d",
                self.provider_name, path, response.status_code, duration_ms, attempt + 1,
            )

            if response.status_code >= 500:
                if attempt < self._max_retries:
                    await asyncio.sleep(_RETRY_BACKOFF_SECONDS)
                    continue
                raise RecipeProviderUnavailableError(
                    f"RecipeAPI.io returned {response.status_code} for {path}"
                )

            return self._parse_response(response, path)

        raise RecipeProviderUnavailableError(f"RecipeAPI.io request to {path} failed after retries")

    def _parse_response(self, response: httpx.Response, path: str) -> dict:
        if response.status_code == 200:
            try:
                return response.json()
            except ValueError as exc:
                raise RecipeProviderMalformedResponseError(
                    f"RecipeAPI.io returned a non-JSON success response for {path}"
                ) from exc
        if response.status_code == 401:
            raise RecipeProviderConfigurationError(
                "RecipeAPI.io rejected the configured API key (401 UNAUTHENTICATED)"
            )
        if response.status_code == 402:
            raise RecipeProviderConfigurationError(
                "RecipeAPI.io plan does not include this feature (402 PLAN_FEATURE_UNAVAILABLE)"
            )
        if response.status_code == 404:
            raise RecipeNotFoundError(f"RecipeAPI.io returned 404 NOT_FOUND for {path}")
        if response.status_code == 422:
            raise InvalidInputError(f"RecipeAPI.io rejected the request to {path} as invalid (422)")
        if response.status_code == 429:
            raise RecipeProviderRateLimitedError("RecipeAPI.io rate limit exceeded (429)")
        raise RecipeProviderUnavailableError(
            f"RecipeAPI.io returned unexpected status {response.status_code} for {path}"
        )

    def _provider_search_term(self, canonical_id: str, *, broaden: bool) -> str:
        """Resolves ONE anchor's canonical id to the text actually sent
        to RecipeAPI.io. A no-op (returns canonical_id unchanged) unless
        broadening was explicitly requested AND a reviewed override
        exists for this exact id -- see PROVIDER_SEARCH_TERM_OVERRIDES."""

        if broaden and canonical_id in PROVIDER_SEARCH_TERM_OVERRIDES:
            return PROVIDER_SEARCH_TERM_OVERRIDES[canonical_id]
        return canonical_id

    def _build_search_params(self, strategy: SearchStrategy) -> dict[str, object]:
        params: dict[str, object] = {
            "page": strategy.page,
            "per_page": min(strategy.page_size, MAX_PAGE_SIZE),
            "lang": "en",
        }
        if strategy.query_ingredients:
            terms = [
                self._provider_search_term(cid, broaden=strategy.broaden_provider_search)
                for cid in strategy.query_ingredients
            ]
            params["ingredients"] = ",".join(terms)
        if strategy.cuisine:
            # Live smoke test (2026-09-05) found the provider's cuisine
            # enum values are lowercase (observed "french", "american" in
            # real responses); a capitalized filter value ("Italian")
            # matched zero results. Lowercasing here is a RecipeAPI.io
            # wire-format detail localized to this adapter -- callers may
            # still pass a display-cased cuisine name.
            params["cuisine"] = strategy.cuisine.strip().lower()
        if strategy.max_prep_time_minutes is not None:
            params["max_prep_time"] = strategy.max_prep_time_minutes
        return params

    async def search(self, strategy: SearchStrategy) -> SearchResult:
        params = self._build_search_params(strategy)
        payload = await self._request("GET", "/recipes", params=params)
        result = self._map_search_response(payload, strategy)

        # Priority-1 efficiency fix (PR #15 correction pass, 2026-09-08):
        # the free-text enrichment pass below used to run unconditionally
        # whenever query_ingredients was non-empty, doubling RecipeAPI.io
        # request volume on every search regardless of whether the
        # primary query already worked. It is now strictly opt-in via
        # strategy.enrich_free_text, set by the agent orchestrator only
        # when a prior attempt's deterministic evidence indicated the
        # `ingredients` filter under-represented the pantry (see
        # app.agent.policy.SYSTEM_POLICY and AgentOrchestrator._run_attempt).
        if not strategy.query_ingredients or not strategy.enrich_free_text:
            return result
        return await self.enrich_with_free_text_search(strategy, result)

    async def enrich_with_free_text_search(
        self, strategy: SearchStrategy, primary_result: SearchResult
    ) -> SearchResult:
        """Retrieval-quality fix (PR #15 browser review, 2026-09-08).

        Live investigation (real RecipeAPI.io calls, not assumed) found
        that the documented `ingredients` filter can silently contribute
        ZERO relevance signal for a real, well-represented canonical
        ingredient term -- confirmed for "chicken_wings": querying
        `ingredients=chicken_wings,garlic` returns a result set BYTE-
        IDENTICAL to `ingredients=garlic` alone, even though RecipeAPI.io's
        own `search` (free-text) field finds many directly relevant
        "Chicken Wings ..." recipes for the same pantry intent. This is
        a provider-side `ingredients`-matching gap, not specific to any
        one ingredient -- confirmed generally by combining `ingredients`
        (unchanged) with `search` set to the primary (first) anchor,
        which reliably surfaced the missing recipes without narrowing
        other already-working queries to zero (joining ALL anchors into
        one `search` phrase was also tried live and reliably returned
        zero -- the field appears to require a short, phrase-like query,
        not a bag of unrelated words -- so only the single primary
        anchor is ever used here).

        Public (not merged into `search()` unconditionally, PR #15
        correction pass): the orchestrator calls this explicitly, only
        when the agent requests it, exactly once per attempt. MERGES the
        free-text results into the primary result set (deduped by
        provider identity, primary result first) rather than replacing
        it -- this can only ever add candidates the primary query
        missed, never remove or bias away from what already worked.
        Bounded exactly like the primary call (same page_size cap,
        same per-request timeout/retry policy).
        """

        # PR #15 fourth correction pass (2026-09-08, Blocker 2): the
        # free-text phrase uses the same broadened term as the primary
        # `ingredients` filter when broadening was requested and a
        # reviewed override exists (e.g. "rice" instead of "basmati
        # rice") -- consistent broadening across both retrieval paths,
        # still zero extra requests (this is still exactly one
        # additional call, unchanged from before this pass).
        primary_anchor = self._provider_search_term(
            strategy.query_ingredients[0], broaden=strategy.broaden_provider_search
        ).replace("_", " ").strip()
        if not primary_anchor:
            return primary_result

        enriched_params = self._build_search_params(strategy)
        enriched_params["search"] = primary_anchor
        try:
            enriched_payload = await self._request("GET", "/recipes", params=enriched_params)
        except RecipeProviderError:
            # The enrichment pass is a bonus signal, not the source of
            # truth -- a failure here must never fail (or even taint)
            # the already-successful primary search.
            return primary_result
        enriched_result = self._map_search_response(enriched_payload, strategy)

        # Bug found during implementation (2026-09-08): concatenating
        # primary-then-enriched before truncating to page_size silently
        # discarded every enriched item whenever the primary query
        # already filled a full page (the common case -- RecipeAPI.io
        # typically returns exactly page_size items), completely
        # defeating the fix it was meant to be. Interleaving instead
        # guarantees both sources get a fair share of the page_size
        # slots regardless of which one happens to be "full".
        interleaved: list = []
        for pair in zip_longest(primary_result.items, enriched_result.items):
            interleaved.extend(item for item in pair if item is not None)
        merged_items = dedupe_search_results(interleaved)

        return SearchResult(
            items=merged_items[: strategy.page_size],
            page=strategy.page,
            page_size=strategy.page_size,
            has_more=primary_result.has_more or enriched_result.has_more,
        )

    async def get_details(self, provider_recipe_id: str) -> Recipe:
        payload = await self._request("GET", f"/recipes/{provider_recipe_id}")
        raw = payload.get("data")
        if not isinstance(raw, dict):
            raise RecipeProviderMalformedResponseError(
                "RecipeAPI.io detail response is missing a 'data' object"
            )
        return self._map_recipe(raw)

    def _map_search_response(self, payload: dict, strategy: SearchStrategy) -> SearchResult:
        raw_items = payload.get("data")
        if not isinstance(raw_items, list):
            raise RecipeProviderMalformedResponseError(
                "RecipeAPI.io search response is missing a 'data' list"
            )

        items: list[SearchResultItem] = []
        for raw in raw_items:
            item = self._map_search_item(raw)
            if item is not None:
                items.append(item)
        items = dedupe_search_results(items)

        meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
        current_page = meta.get("current_page", strategy.page)
        last_page = meta.get("last_page", current_page)
        has_more = (
            isinstance(current_page, int) and isinstance(last_page, int) and current_page < last_page
        )

        return SearchResult(
            items=items, page=strategy.page, page_size=strategy.page_size, has_more=has_more
        )

    def _map_search_item(self, raw: object) -> SearchResultItem | None:
        if not isinstance(raw, dict):
            return None
        provider_recipe_id = raw.get("id")
        name = raw.get("name")
        if provider_recipe_id is None or not isinstance(name, str) or not name.strip():
            # Skip an individual malformed search-result item rather than
            # failing the whole page -- this is a listing, not a grounded
            # recipe that will be shown; get_details() is stricter.
            return None
        cleaned_id = str(provider_recipe_id)
        return SearchResultItem(
            id=build_recipe_id(self.provider_name, cleaned_id),
            provider=self.provider_name,
            provider_recipe_id=cleaned_id,
            name=name.strip(),
            image_url=raw.get("image_url") if isinstance(raw.get("image_url"), str) else None,
            cuisine=raw.get("cuisine") if isinstance(raw.get("cuisine"), str) else None,
            full_recipe=self._try_map_full_recipe_from_list_item(raw),
        )

    def _try_map_full_recipe_from_list_item(self, raw: dict) -> Recipe | None:
        """Priority-1 efficiency fix (PR #15 correction pass, 2026-09-08).

        Live investigation (real RecipeAPI.io calls, not assumed) found
        that /recipes (search/list) items are NOT lightweight stubs --
        confirmed live to already carry the exact same ingredients/
        instructions/difficulty/servings/timing fields as a /recipes/{id}
        detail response. Reusing _map_recipe here (the same mapping
        already proven for detail responses) means a candidate whose
        list item already has real ingredients+instructions needs no
        separate get_details() round trip at all.

        Conservative by construction, never inferring unsupported data:
        only attempted when the raw item actually has a non-empty
        ingredients array AND non-empty instructions; any mapping
        failure (or a genuinely thin list item, some other provider
        version, a future RecipeAPI.io response shape) silently leaves
        this None so app.agent.tools.fetch_recipe_details falls back to
        the real get_details() call for that one candidate, unchanged.
        """

        raw_ingredients = raw.get("ingredients")
        raw_instructions = raw.get("instructions")
        has_ingredients = isinstance(raw_ingredients, list) and len(raw_ingredients) > 0
        has_instructions = (isinstance(raw_instructions, list) and len(raw_instructions) > 0) or (
            isinstance(raw_instructions, str) and bool(raw_instructions.strip())
        )
        if not (has_ingredients and has_instructions):
            return None
        try:
            return self._map_recipe(raw)
        except RecipeProviderError:
            return None

    def _map_recipe(self, raw: dict) -> Recipe:
        recipe_recipe_id, name = require_usable_identity(
            provider=self.provider_name,
            provider_recipe_id=raw.get("id"),
            name=raw.get("name"),
            source_description="RecipeAPI.io recipe detail",
        )

        ingredients: list[RecipeIngredient] = []
        raw_ingredients = raw.get("ingredients")
        if isinstance(raw_ingredients, list):
            for raw_ing in raw_ingredients:
                mapped = self._map_ingredient(raw_ing)
                if mapped is not None:
                    ingredients.append(mapped)

        raw_instructions = raw.get("instructions")
        if isinstance(raw_instructions, list):
            instructions = "\n".join(str(step) for step in raw_instructions if isinstance(step, str))
        elif isinstance(raw_instructions, str):
            instructions = raw_instructions
        else:
            instructions = None

        return Recipe(
            id=build_recipe_id(self.provider_name, recipe_recipe_id),
            provider=self.provider_name,
            provider_recipe_id=recipe_recipe_id,
            name=name,
            cuisine=raw.get("cuisine") if isinstance(raw.get("cuisine"), str) else None,
            category=raw.get("meal_type") if isinstance(raw.get("meal_type"), str) else None,
            image_url=raw.get("image_url") if isinstance(raw.get("image_url"), str) else None,
            ingredients=ingredients,
            instructions=instructions,
            source_url=raw.get("source_url") if isinstance(raw.get("source_url"), str) else None,
            servings=raw.get("servings") if isinstance(raw.get("servings"), int) else None,
            prep_time_minutes=raw.get("prep_time") if isinstance(raw.get("prep_time"), int) else None,
            cook_time_minutes=raw.get("cook_time") if isinstance(raw.get("cook_time"), int) else None,
            fetched_at=datetime.now(timezone.utc),
            difficulty=Difficulty.from_raw(raw.get("difficulty")),
        )

    def _map_ingredient(self, raw: object) -> RecipeIngredient | None:
        if not isinstance(raw, dict):
            return None
        raw_name = raw.get("name")
        if not isinstance(raw_name, str) or not raw_name.strip():
            return None

        quantity = raw.get("quantity")
        quantity_value = float(quantity) if isinstance(quantity, (int, float)) else None
        unit = raw.get("unit") if isinstance(raw.get("unit"), str) else None

        if quantity_value is not None and unit:
            raw_measure = f"{quantity} {unit}".strip()
        elif unit:
            raw_measure = unit
        else:
            raw_measure = None

        return RecipeIngredient(
            raw_name=raw_name.strip(),
            canonical_id=None,  # canonical resolution is M08's job, applied later -- not this ticket
            raw_measure=raw_measure,
            quantity=quantity_value,
            normalized_unit=None,  # unit normalization is M11's job (Cost Engine), not this ticket
            optional=bool(raw.get("optional", False)),
            normalization_status=NormalizationStatus.UNKNOWN,
        )
