"""Module F 4.3: rate limiting on /api/recommend and
/api/ingredients/suggest.

The suite-wide autouse fixture in tests/conftest.py resets the
in-memory limiter before every test, so each test here starts from a
clean count and exercises the REAL configured default limits
(app.config.Settings.rate_limit_recommend / rate_limit_ingredients_suggest)
rather than monkeypatching them.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.recommend import get_orchestrator
from app.config import get_settings
from app.main import app

from .test_recommend_endpoint import VALID_REQUEST, FakeOrchestrator, _happy_path_result


def _limit_count(limit_string: str) -> int:
    # e.g. "10/minute" -> 10
    return int(limit_string.split("/", 1)[0])


class _CountingOrchestrator(FakeOrchestrator):
    def __init__(self, result) -> None:
        super().__init__(result)
        self.call_count = 0

    async def run(self, request):
        self.call_count += 1
        return await super().run(request)


def test_recommend_returns_429_once_the_limit_is_exceeded_and_stops_calling_the_orchestrator():
    limit = _limit_count(get_settings().rate_limit_recommend)
    orchestrator = _CountingOrchestrator(_happy_path_result())
    app.dependency_overrides[get_orchestrator] = lambda: orchestrator
    try:
        client = TestClient(app)
        for _ in range(limit):
            response = client.post("/api/recommend", json=VALID_REQUEST)
            assert response.status_code == 200
        assert orchestrator.call_count == limit

        # One more request over the limit must be rejected with 429
        # and must NOT reach the orchestrator (no LLM/provider call).
        response = client.post("/api/recommend", json=VALID_REQUEST)
        assert response.status_code == 429
        envelope = response.json()
        assert envelope["error"]["code"] == "RATE_LIMITED"
        assert envelope["error"]["retryable"] is True
        assert orchestrator.call_count == limit  # unchanged
    finally:
        app.dependency_overrides.clear()


def test_ingredients_suggest_returns_429_once_its_higher_limit_is_exceeded():
    limit = _limit_count(get_settings().rate_limit_ingredients_suggest)
    client = TestClient(app)
    for _ in range(limit):
        response = client.get("/api/ingredients/suggest", params={"q": "chick"})
        assert response.status_code == 200

    response = client.get("/api/ingredients/suggest", params={"q": "chick"})
    assert response.status_code == 429
    envelope = response.json()
    assert envelope["error"]["code"] == "RATE_LIMITED"
    assert envelope["error"]["retryable"] is True


def test_recommend_and_suggest_limits_are_tracked_independently():
    # A client exhausting the (stricter) recommend limit must still be
    # able to use autocomplete normally.
    orchestrator = _CountingOrchestrator(_happy_path_result())
    app.dependency_overrides[get_orchestrator] = lambda: orchestrator
    try:
        limit = _limit_count(get_settings().rate_limit_recommend)
        client = TestClient(app)
        for _ in range(limit + 1):
            client.post("/api/recommend", json=VALID_REQUEST)

        response = client.get("/api/ingredients/suggest", params={"q": "chick"})
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()
