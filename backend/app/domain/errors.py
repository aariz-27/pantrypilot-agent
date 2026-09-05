"""Typed expected application errors.

Per docs/API_INTEGRATION_STANDARDS.md section 9, every expected failure
maps to a stable {code, message, retryable} shape. This ticket only
implements the subset of the taxonomy that the deterministic core and
health foundation can actually raise; provider/agent error codes
(e.g. RECIPE_PROVIDER_TIMEOUT) belong to later tickets that own those
integrations.

Note: TECHNICAL_SPEC.md section 15's example error envelope uses the
code "INVALID_INPUT" for request validation, while the taxonomy in
docs/API_INTEGRATION_STANDARDS.md section 10 lists "INVALID_REQUEST" as
the equivalent category name. This is a pre-existing naming
inconsistency between the two governance documents (not introduced by
this ticket). INVALID_INPUT is used here because it is the literal code
shown in TECHNICAL_SPEC.md's canonical error example.
"""

from __future__ import annotations


class PantryPilotError(Exception):
    """Base type for all expected application errors."""

    code: str = "INTERNAL_ERROR"
    retryable: bool = False

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def to_error_envelope(self, request_id: str | None = None) -> dict:
        return {
            "request_id": request_id,
            "error": {
                "code": self.code,
                "message": self.message,
                "retryable": self.retryable,
            },
        }


class InvalidInputError(PantryPilotError):
    """Raised when supplied domain input fails a required invariant.

    Reserved for defensive validation inside deterministic domain
    functions (e.g. a negative budget reaching the constraint evaluator
    directly). Pydantic request-schema validation handles the public
    HTTP boundary separately and is not routed through this exception.
    """

    code = "INVALID_INPUT"
    retryable = False
