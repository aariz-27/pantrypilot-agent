"""Module F 4.2: POST /api/recommend rejects oversized bodies before
they ever reach the orchestrator (LLM/provider processing)."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.api.recommend import get_orchestrator
from app.config import get_settings
from app.main import app


class _OrchestratorSpy:
    """Fails the test if the oversized request ever reaches this far."""

    async def run(self, request):
        raise AssertionError("orchestrator.run() must never be called for an oversized request")


def test_oversized_recommend_request_is_rejected_before_reaching_the_orchestrator():
    app.dependency_overrides[get_orchestrator] = lambda: _OrchestratorSpy()
    try:
        client = TestClient(app)
        oversized_body = json.dumps(
            {"ingredients": ["a" * 80] * 250, "servings": 4, "max_total_time_minutes": 30}
        ).encode("utf-8")
        assert len(oversized_body) > get_settings().max_request_body_bytes

        response = client.post(
            "/api/recommend", content=oversized_body, headers={"content-type": "application/json"}
        )

        assert response.status_code == 413
        envelope = response.json()
        assert envelope["error"]["code"] == "REQUEST_TOO_LARGE"
        assert envelope["error"]["retryable"] is False
    finally:
        app.dependency_overrides.clear()
