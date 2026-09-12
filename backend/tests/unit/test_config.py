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


# -- admin dashboard config (feature/admin-ingredient-dashboard) -----------
#
# Regression coverage for a real bug caught during live-server
# acceptance testing (2026-09-13): the admin_* fields must be
# populated from the ticket-mandated PANTRYPILOT_ADMIN_* env var names
# specifically -- not the bare field name (there is no global
# env_prefix on Settings) -- while ALSO remaining constructible by
# plain Python kwarg (every admin test fixture and FastAPI
# dependency-override in this repo does exactly that). Both paths must
# keep working; a regression in either one previously passed unit
# tests that only exercised the other.


def test_admin_not_configured_by_default():
    settings = Settings(_env_file=None)
    assert settings.admin_configured is False


def test_admin_configured_via_direct_kwargs():
    settings = Settings(
        _env_file=None, admin_username="founder", admin_password_hash="scrypt$hash", admin_session_secret="secret"
    )
    assert settings.admin_username == "founder"
    assert settings.admin_configured is True


def test_admin_configured_via_pantrypilot_prefixed_env_vars(monkeypatch):
    monkeypatch.setenv("PANTRYPILOT_ADMIN_USERNAME", "founder")
    monkeypatch.setenv("PANTRYPILOT_ADMIN_PASSWORD_HASH", "scrypt$hash")
    monkeypatch.setenv("PANTRYPILOT_ADMIN_SESSION_SECRET", "secret")
    settings = Settings(_env_file=None)
    assert settings.admin_username == "founder"
    assert settings.admin_password_hash.get_secret_value() == "scrypt$hash"
    assert settings.admin_configured is True


def test_admin_partial_configuration_is_not_configured():
    settings = Settings(_env_file=None, admin_username="founder")
    assert settings.admin_configured is False
