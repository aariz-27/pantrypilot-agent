from app.domain.errors import PantryPilotError
from app.domain.provider_errors import (
    RecipeNotFoundError,
    RecipeProviderConfigurationError,
    RecipeProviderMalformedResponseError,
    RecipeProviderRateLimitedError,
    RecipeProviderTimeoutError,
    RecipeProviderUnavailableError,
)


def test_all_provider_errors_are_pantrypilot_errors():
    for error_cls in (
        RecipeProviderTimeoutError,
        RecipeProviderUnavailableError,
        RecipeProviderRateLimitedError,
        RecipeProviderMalformedResponseError,
        RecipeProviderConfigurationError,
        RecipeNotFoundError,
    ):
        instance = error_cls("test message")
        assert isinstance(instance, PantryPilotError)
        assert instance.code
        assert instance.message == "test message"


def test_retryable_flags_match_retry_classification_policy():
    # Per docs/API_INTEGRATION_STANDARDS.md section 22: timeouts and
    # transient unavailability are potentially retryable; rate limits,
    # malformed responses, config/auth failures, and not-found are not.
    assert RecipeProviderTimeoutError("x").retryable is True
    assert RecipeProviderUnavailableError("x").retryable is True
    assert RecipeProviderRateLimitedError("x").retryable is False
    assert RecipeProviderMalformedResponseError("x").retryable is False
    assert RecipeProviderConfigurationError("x").retryable is False
    assert RecipeNotFoundError("x").retryable is False


def test_error_envelope_never_includes_extra_internals():
    error = RecipeProviderConfigurationError("RECIPEAPI_IO_API_KEY is not configured")
    envelope = error.to_error_envelope(request_id="req_1")
    assert set(envelope["error"].keys()) == {"code", "message", "retryable"}
