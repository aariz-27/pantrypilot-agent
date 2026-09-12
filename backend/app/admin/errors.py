"""Typed admin errors, following the same PantryPilotError contract the
public API already uses (app.domain.errors) so app.main's existing
exception handler and error-envelope shape need no admin-specific
branching.
"""

from __future__ import annotations

from app.domain.errors import PantryPilotError


class AdminAuthError(PantryPilotError):
    """Missing, invalid, expired, or revoked session. Also used for bad
    login credentials -- the message is always the same generic string
    regardless of whether the username or the password was wrong, so a
    caller can never distinguish "unknown user" from "wrong password"
    (ticket section 8: never expose username existence)."""

    code = "ADMIN_UNAUTHORIZED"
    retryable = False


class AdminCsrfError(PantryPilotError):
    code = "ADMIN_CSRF_INVALID"
    retryable = False


class AdminNotFoundError(PantryPilotError):
    code = "ADMIN_NOT_FOUND"
    retryable = False


class AdminConflictError(PantryPilotError):
    """A create/mutate request would violate a uniqueness or identity
    invariant the admin UI must never silently paper over -- e.g. a
    duplicate canonical_id, a duplicate active alias, or an alias
    already mapped to a different canonical ingredient."""

    code = "ADMIN_CONFLICT"
    retryable = False


class AdminValidationError(PantryPilotError):
    """Reserved for domain-level validation Pydantic's field types
    cannot express (e.g. cross-field checks, unsupported unit values).
    Pydantic schema validation itself still produces a plain 422
    without going through this type."""

    code = "ADMIN_VALIDATION_ERROR"
    retryable = False


class AdminNotConfiguredError(PantryPilotError):
    """The three PANTRYPILOT_ADMIN_* environment variables are not all
    set. Distinct from AdminAuthError so an operator misconfiguration
    is never confused with an actual bad login attempt in logs/metrics."""

    code = "ADMIN_NOT_CONFIGURED"
    retryable = False
