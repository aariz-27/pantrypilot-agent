"""Typed recipe-provider-layer errors.

Extends app.domain.errors.PantryPilotError with the provider failure
categories from docs/API_INTEGRATION_STANDARDS.md section 27 ("Provider
Failure Taxonomy") and the RECIPE_PROVIDER_* / RECIPE_NOT_FOUND codes
already named in TECHNICAL_SPEC.md section 15's error taxonomy.

RECIPE_PROVIDER_CONFIGURATION_ERROR is a ticket-scoped addition (not
explicitly named in either document) for the "authentication/config
failure" category docs/API_INTEGRATION_STANDARDS.md section 27 calls
PERMANENT_CONFIGURATION_ERROR/AUTH_FAILURE; it follows the existing
RECIPE_PROVIDER_* naming convention.

Retryability follows docs/API_INTEGRATION_STANDARDS.md section 22
(Retry Classification): timeouts/transient unavailability are
potentially retryable; rate limits, auth/config failures, and malformed
responses are explicitly NOT retried automatically.
"""

from __future__ import annotations

from app.domain.errors import PantryPilotError


class RecipeProviderError(PantryPilotError):
    """Base class for all recipe-provider-layer errors."""

    code = "RECIPE_PROVIDER_ERROR"
    retryable = False


class RecipeProviderTimeoutError(RecipeProviderError):
    code = "RECIPE_PROVIDER_TIMEOUT"
    retryable = True


class RecipeProviderUnavailableError(RecipeProviderError):
    """Transient network failure or provider 5xx response."""

    code = "RECIPE_PROVIDER_UNAVAILABLE"
    retryable = True


class RecipeProviderRateLimitedError(RecipeProviderError):
    """HTTP 429. Per the Retry Classification policy this is NOT
    immediately retried by the adapter -- the caller (future Recipe
    Service/agent) decides whether to use a cache or another strategy."""

    code = "RECIPE_PROVIDER_RATE_LIMITED"
    retryable = False


class RecipeProviderMalformedResponseError(RecipeProviderError):
    """The provider responded but the payload could not be safely
    parsed/mapped into the internal Recipe DTO."""

    code = "RECIPE_PROVIDER_MALFORMED_RESPONSE"
    retryable = False


class RecipeProviderConfigurationError(RecipeProviderError):
    """Missing/invalid API key, or a plan/feature the current API key
    is not entitled to use. Never includes the key value itself."""

    code = "RECIPE_PROVIDER_CONFIGURATION_ERROR"
    retryable = False


class RecipeNotFoundError(RecipeProviderError):
    code = "RECIPE_NOT_FOUND"
    retryable = False
