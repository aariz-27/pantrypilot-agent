"""Shared Module D test doubles and fixtures.

FakeLLMProvider and FakeRecipeProvider are scripted test doubles, not
production code -- Module D's own tests must run with zero live
Anthropic/RecipeAPI.io calls (ticket section 17).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.agent.actions import AgentAction
from app.db.connection import connection_scope
from app.db.schema import create_schema
from app.domain.models import Recipe
from app.domain.provider_errors import RecipeProviderError
from app.integrations.llm_provider import LLMDecisionRequest, LLMDecisionResponse
from app.recipe.provider import SearchResult, SearchStrategy


class FakeLLMProvider:
    """Returns pre-scripted decisions in order. Each scripted item may be
    an AgentAction (happy path, converted to its wire dict) or a raw
    dict (to simulate malformed/unsupported output)."""

    provider_name = "fake"

    def __init__(self, decisions: list[AgentAction | dict]) -> None:
        self._decisions = list(decisions)
        self.requests: list[LLMDecisionRequest] = []

    async def decide(self, request: LLMDecisionRequest) -> LLMDecisionResponse:
        self.requests.append(request)
        if not self._decisions:
            raise AssertionError("FakeLLMProvider ran out of scripted decisions")
        next_decision = self._decisions.pop(0)
        raw = next_decision.model_dump(mode="json") if isinstance(next_decision, AgentAction) else next_decision
        return LLMDecisionResponse(raw_action=raw, model_name="fake-model")

    @property
    def call_count(self) -> int:
        return len(self.requests)


@dataclass
class ScriptedSearch:
    result: SearchResult | None = None
    error: type[RecipeProviderError] | None = None


class FakeRecipeProvider:
    """A RecipeProvider test double with a scripted queue of search
    outcomes (consumed in call order) and a fixed id->Recipe/error
    lookup table for get_details."""

    def __init__(
        self,
        provider_name: str,
        searches: list[ScriptedSearch],
        details_by_id: dict[str, Recipe | type[RecipeProviderError]] | None = None,
    ) -> None:
        self.provider_name = provider_name
        self._searches = list(searches)
        self._details_by_id = details_by_id or {}
        self.search_calls: list[SearchStrategy] = []
        self.detail_calls: list[str] = []

    async def search(self, strategy: SearchStrategy) -> SearchResult:
        self.search_calls.append(strategy)
        if not self._searches:
            raise AssertionError("FakeRecipeProvider ran out of scripted search outcomes")
        scripted = self._searches.pop(0)
        if scripted.error is not None:
            raise scripted.error("scripted provider failure")
        assert scripted.result is not None
        return scripted.result

    async def get_details(self, provider_recipe_id: str) -> Recipe:
        self.detail_calls.append(provider_recipe_id)
        entry = self._details_by_id.get(provider_recipe_id)
        if entry is None:
            raise AssertionError(f"FakeRecipeProvider has no scripted detail for {provider_recipe_id!r}")
        if isinstance(entry, type) and issubclass(entry, RecipeProviderError):
            raise entry("scripted detail failure")
        return entry


@pytest.fixture()
def price_db(tmp_path):
    path = str(tmp_path / "agent_test.db")
    with connection_scope(path, read_only=False) as connection:
        create_schema(connection)
        rows = [
            ("tomato", "g", "tomato", 0.005, 1000, "g", 5.0, 1000, 2, "median_even",
             "lulu_uae", "Tomato 1 kg", "https://example.test/tomato", "2026-09-06"),
            ("onion", "g", "onion", 0.005, 1000, "g", 5.0, 1000, 2, "median_even",
             "lulu_uae", "Onion 1 kg", "https://example.test/onion", "2026-09-06"),
            ("basmati_rice", "g", "basmati_rice", 0.008, 1000, "g", 8.0, 1000, 1, "median_single",
             "lulu_uae", "Basmati Rice 1 kg", "https://example.test/rice", "2026-09-06"),
        ]
        connection.executemany(
            """
            INSERT INTO ingredient_prices (
                canonical_id, normalized_unit, display_name, normalized_price_per_unit,
                package_quantity, package_unit, package_price_aed, normalized_package_quantity,
                contributor_count, aggregation_basis, source_name, source_product_name,
                source_url, collected_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        connection.commit()
    return path


def make_recipe(**overrides) -> Recipe:
    defaults = dict(
        id="recipeapi_io:1",
        provider="recipeapi_io",
        provider_recipe_id="1",
        name="Tomato Onion Curry",
        cuisine="Asian",
        ingredients=[],
        instructions="Cook everything together until done.",
    )
    defaults.update(overrides)
    return Recipe(**defaults)
