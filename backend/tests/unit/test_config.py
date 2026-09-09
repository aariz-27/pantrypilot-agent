import pytest
from pydantic import ValidationError

from app.config import Settings


def test_defaults_are_safe_and_unconfigured():
    settings = Settings(_env_file=None)
    assert settings.allowed_origins == []
    assert settings.llm_configured is False
    assert settings.recipeapi_io_configured is False


def test_allowed_origins_parses_comma_separated_string():
    settings = Settings(_env_file=None, allowed_origins="https://a.example,https://b.example")
    assert settings.allowed_origins == ["https://a.example", "https://b.example"]


def test_secret_values_never_appear_in_repr():
    settings = Settings(_env_file=None, anthropic_api_key="sk-super-secret", recipeapi_io_api_key="rk-super-secret")
    rendered = repr(settings)
    assert "sk-super-secret" not in rendered
    assert "rk-super-secret" not in rendered
    assert settings.llm_configured is False  # model still unset
    assert settings.recipeapi_io_configured is True


def test_llm_configured_requires_both_key_and_model():
    settings = Settings(_env_file=None, anthropic_api_key="sk-x", pantrypilot_llm_model="claude-sonnet-5")
    assert settings.llm_configured is True


def test_allowed_origins_tolerates_whitespace_and_stray_commas():
    settings = Settings(
        _env_file=None,
        allowed_origins="  https://a.example , , https://b.example ,",
    )
    assert settings.allowed_origins == ["https://a.example", "https://b.example"]


def test_allowed_origins_rejects_wildcard():
    # Module F 4.4: "*" is incompatible with allow_credentials=True
    # (app.main) and must fail fast at startup rather than silently
    # producing a broken/insecure CORS configuration.
    with pytest.raises(ValidationError):
        Settings(_env_file=None, allowed_origins="*")


def test_allowed_origins_rejects_wildcard_mixed_with_real_origins():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, allowed_origins="https://a.example,*")
