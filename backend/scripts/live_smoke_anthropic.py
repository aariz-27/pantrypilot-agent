"""DEFERRED live Anthropic smoke test for Module D (ticket section 19).

Status: DEFERRED -- API key pending. The Founder has not yet supplied
ANTHROPIC_API_KEY, so this script has never been executed against the
live API. It is not part of the automated test suite: it is not under
tests/ (pytest's testpaths), it is never imported by any test module,
and it refuses to run at all under pytest or in CI (see the guards
below).

Manual invocation only, once a real key is available:

    cd backend
    ANTHROPIC_API_KEY=sk-ant-... PANTRYPILOT_LLM_MODEL=claude-sonnet-5 \
        python scripts/live_smoke_anthropic.py

Exercises exactly one permitted structured decision (a STOP action is
the only thing a real model can validly return with zero search
history) through the real AnthropicLLMProvider, to prove the
tool-calling wiring itself works end-to-end. It never prints the API
key and never dumps the full raw model response -- only a bounded
pass/fail summary.
"""

from __future__ import annotations

import asyncio
import os
import sys

if "PYTEST_CURRENT_TEST" in os.environ:
    raise RuntimeError("live_smoke_anthropic.py must never run under pytest")


def _fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


async def _run() -> None:
    from app.agent.actions import AgentAction
    from app.agent.policy import SYSTEM_POLICY
    from app.config import get_settings
    from app.integrations.llm_provider import AnthropicLLMProvider, LLMDecisionRequest, LLMProviderError

    settings = get_settings()
    if not settings.llm_configured:
        _fail("ANTHROPIC_API_KEY / PANTRYPILOT_LLM_MODEL not configured in the environment")

    try:
        provider = AnthropicLLMProvider(settings)
    except LLMProviderError as exc:
        _fail(f"could not construct AnthropicLLMProvider ({exc.code})")

    request = LLMDecisionRequest(
        system_policy=SYSTEM_POLICY,
        action_schema=AgentAction.model_json_schema(),
        observation={
            "state_summary": {
                "search_attempts_used": 3,
                "search_attempts_remaining": 0,
                "candidates_evaluated_total": 0,
                "candidate_cap_remaining": 20,
                "current_best_feasible_count": 0,
                "cuisine_preference": None,
                "cuisine_strict": False,
                "budget_set": False,
                "max_total_time_set": False,
                "provider_status": {},
            },
            "latest_search_observation": None,
        },
    )

    try:
        response = await provider.decide(request)
    except LLMProviderError as exc:
        _fail(f"live decide() call failed ({exc.code})")
        return

    try:
        action = AgentAction.model_validate(response.raw_action)
    except Exception:
        _fail("model response did not validate as a well-formed AgentAction")
        return

    print(f"PASS: received a well-formed AgentAction (action_type={action.action_type.value}) from model={response.model_name}")


if __name__ == "__main__":
    asyncio.run(_run())
