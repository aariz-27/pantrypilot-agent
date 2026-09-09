"""Manual, one-off live validation for the PR #15 "final blocker" fix
(2026-09-09): an invalid, non-pantry-grounded search anchor (e.g. "lamb"
when the user's pantry only has "minced_lamb") must be rejected by the
deterministic grounding guard and recovered from gracefully -- never
surface as an unhandled exception / HTTP 500.

Exercises the REAL, connected pipeline through the REAL FastAPI app
object (app.main.app, via TestClient -- same ASGI app, same dependency
injection, same global PantryPilotError handler a real deployment
uses): AgentOrchestrator -> AnthropicLLMProvider (real Anthropic API,
Claude Sonnet 5, DEC-010) -> RecipeAPIIOAdapter (real RecipeAPI.io) ->
the deterministic Module A-C pipeline (normalization, pantry matching,
PriceRepository against the real local reference DB, cost engine,
constraint evaluator, ranker).

A real, well-instructed Claude Sonnet 5 now correctly avoids proposing
a broader anchor like "lamb" for a specific pantry item like
"minced_lamb" (SYSTEM_POLICY explicitly forbids exactly this -- see
app.agent.policy, and the "lamb-family provider audit" fix on this
branch) -- so it will not organically reproduce the original defect's
precondition any more. To still exercise the real deterministic guard,
the real corrective-feedback path, and a real Claude Sonnet 5 response
to that feedback, this script wraps AnthropicLLMProvider so ONLY the
very first decision of the run is forced to the exact invalid action
from the ticket's live bug report ("lamb"); every subsequent decision
(the corrective response and everything after it) is answered by the
real, live model.

Like scripts/live_smoke_full_pipeline.py, this is NOT part of the
automated test suite: it is not under tests/ (pytest's testpaths),
never imported by any test module, and refuses to run under pytest or
with an unconfigured environment. Manual invocation only:

    cd backend
    python scripts/live_smoke_grounding_recovery.py

It never prints API keys, the system prompt, or raw provider payloads
-- only the safe, high-level diagnostics TECHNICAL_SPEC.md's
observability section allows.
"""

from __future__ import annotations

import os
import sys

if "PYTEST_CURRENT_TEST" in os.environ:
    raise RuntimeError("live_smoke_grounding_recovery.py must never run under pytest")


def _fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


class _ForcedFirstActionThenRealLLM:
    """Forces the ticket's exact reproduction precondition (an invalid,
    broader-than-pantry "lamb" anchor) on the first decision only, then
    delegates every subsequent decision to the real, live LLMProvider --
    so the corrective response and everything after it is genuine
    Claude Sonnet 5 behavior, not scripted."""

    def __init__(self, real_provider) -> None:
        self._real = real_provider
        self.provider_name = real_provider.provider_name
        self.call_count = 0
        self.requests: list = []

    async def decide(self, request):
        from app.integrations.llm_provider import LLMDecisionResponse

        self.call_count += 1
        self.requests.append(request)
        if self.call_count == 1:
            forced_action = {
                "action_type": "search",
                "search": {
                    "route": "recipeapi_io",
                    "anchor_ingredients": ["lamb"],
                    "cuisine": None,
                    "enrich_free_text": False,
                    "broaden_provider_search": False,
                    "rationale_category": None,
                },
            }
            return LLMDecisionResponse(raw_action=forced_action, model_name="forced-repro (not a real model call)")
        return await self._real.decide(request)


def _run() -> None:
    from fastapi.testclient import TestClient

    from app.agent.orchestrator import AgentOrchestrator
    from app.api.recommend import get_orchestrator
    from app.config import get_settings
    from app.integrations.llm_provider import AnthropicLLMProvider, LLMProviderError
    from app.integrations.recipeapi_io import RecipeAPIIOAdapter
    from app.main import app
    from app.repositories.price_repository import PriceRepository

    settings = get_settings()
    if not settings.llm_configured:
        _fail("ANTHROPIC_API_KEY / PANTRYPILOT_LLM_MODEL not configured")
    if not settings.recipeapi_io_configured:
        _fail("RECIPEAPI_IO_API_KEY not configured")
    if not os.path.exists(settings.price_db_path):
        _fail(f"reference price DB not found at {settings.price_db_path!r}")

    try:
        real_llm = AnthropicLLMProvider(settings)
        llm = _ForcedFirstActionThenRealLLM(real_llm)
        recipeapi = RecipeAPIIOAdapter(settings)
    except LLMProviderError as exc:
        _fail(f"could not construct a provider ({exc.code})")
        return

    price_repository = PriceRepository(settings.price_db_path)
    orchestrator = AgentOrchestrator(llm, {"recipeapi_io": recipeapi}, price_repository)

    pantry = ["minced lamb", "garlic", "onion", "cumin", "salt", "pepper"]
    payload = {
        "ingredients": pantry,
        "servings": 4,
        "max_total_time_minutes": 60,
    }

    app.dependency_overrides[get_orchestrator] = lambda: orchestrator
    try:
        with TestClient(app) as client:
            response = client.post("/api/recommend", json=payload)
    finally:
        app.dependency_overrides.clear()
        # Best-effort only: the httpx.AsyncClient underneath
        # RecipeAPIIOAdapter was created/used inside TestClient's own
        # portal event loop, which is already torn down once the `with`
        # block above exits -- a fresh asyncio.run() here cannot safely
        # close a transport bound to a different, closed loop. This is a
        # one-off diagnostic script (not a production code path); the
        # OS reclaims the socket on process exit either way, so a
        # cleanup failure here must never hide the actual validation
        # report below.
        try:
            import asyncio

            asyncio.run(recipeapi.aclose())
        except RuntimeError:
            pass

    body = response.json()

    print("=== Live grounding-recovery validation (PR #15 final blocker) ===")
    print(f"  model_used: {settings.pantrypilot_llm_model}")
    print(f"  pantry: {pantry}")
    print("  initial_action (forced repro precondition): search anchor_ingredients=['lamb']")
    print("  expected_guard_rejection: 'lamb' is not present in the user's resolved pantry canonical ids")
    print(f"  llm_decision_calls: {llm.call_count} (1 forced + {llm.call_count - 1} real Claude Sonnet 5 call(s))")
    if len(llm.requests) >= 2:
        corrective_feedback = llm.requests[1].previous_action_error
        print(f"  corrective_observation_sent_to_claude: {corrective_feedback!r}")
    else:
        corrective_feedback = None
        print("  corrective_observation_sent_to_claude: <none -- unexpected, see below>")
    print(f"  progress_events: {body.get('progress_events')}")
    print(f"  final_http_status: {response.status_code}")
    print(f"  status: {body.get('status')}")
    print(f"  recommendations: {[r['recipe_id'] for r in body.get('recommendations', [])]}")
    print(f"  additional_options: {[r['recipe_id'] for r in body.get('additional_options', [])]}")
    print(f"  closest_alternatives: {[r['recipe_id'] for r in body.get('closest_alternatives', [])]}")

    if response.status_code == 500:
        _fail("final HTTP response was 500 -- the defect this ticket fixes is still present")
    if corrective_feedback is None or "lamb" not in corrective_feedback:
        _fail("no structured corrective observation naming the rejected anchor was sent to Claude")
    if "unsupported action rejected" not in " ".join(body.get("progress_events", [])):
        _fail("progress events do not show the expected corrective-rejection event")

    print("PASS: invalid non-grounded anchor was rejected, Claude received structured corrective")
    print("      feedback, and the run completed without an HTTP 500.")


if __name__ == "__main__":
    _run()
