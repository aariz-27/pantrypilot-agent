"""Typed Module D (agent orchestrator) errors.

Extends app.domain.errors.PantryPilotError. Every failure the
orchestrator itself detects -- malformed/invalid LLM output that
survives one corrective retry, or a request to exceed bounded autonomy
-- must fail through one of these typed errors rather than raising a
bare exception or silently coercing to a default action. The LLM is
never trusted to enforce its own limits (TECHNICAL_SPEC.md section 2,
"Bounded autonomy"); Python enforces them independently.
"""

from __future__ import annotations

from app.domain.errors import PantryPilotError


class AgentError(PantryPilotError):
    code = "AGENT_ERROR"
    retryable = False


class AgentMalformedActionError(AgentError):
    """The LLM's action output could not be parsed into a valid
    AgentAction after the one permitted corrective retry."""

    code = "AGENT_MALFORMED_ACTION"
    retryable = False


class AgentUnsupportedActionError(AgentError):
    """The requested action is schema-valid but violates a bounded
    orchestration policy the schema cannot express alone -- e.g. an
    identical search strategy repeated without a transient failure, a
    local-curated route requested for a non-approved regional intent,
    or pagination/retry requested with no prior matching attempt."""

    code = "AGENT_UNSUPPORTED_ACTION"
    retryable = False
