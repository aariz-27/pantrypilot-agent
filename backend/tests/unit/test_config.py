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


# -- ALLOWED_ORIGINS real environment-variable parsing (2026-09-13) --------
#
# Regression coverage for a real, production-relevant bug: pydantic-
# settings' default behavior for ANY list-typed field is to JSON-decode
# the raw environment string BEFORE Settings._parse_allowed_origins
# (the field_validator above) ever runs. A real ALLOWED_ORIGINS
# environment variable in its own documented comma-separated form, a
# single bare URL, or even an EMPTY value (exactly what .env.example
# ships) is not valid JSON and crashed the entire application at
# startup with a raw pydantic_settings.SettingsError -- never caught by
# the tests above because every one of them constructs
# Settings(allowed_origins=...) directly in Python (an "InitSettingsSource"
# kwarg), which never goes through the environment-variable JSON
# pre-decode at all. These tests use monkeypatch.setenv, exercising the
# REAL EnvSettingsSource/DotEnvSettingsSource path that only a live
# server boot previously exercised. Fixed via Annotated[list[str],
# NoDecode] (app.config), which hands the raw string straight to the
# validator unconditionally, regardless of source.


def test_allowed_origins_json_list_single_origin_via_real_env_var(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", '["https://130.162.185.187"]')
    settings = Settings(_env_file=None)
    assert settings.allowed_origins == ["https://130.162.185.187"]


def test_allowed_origins_json_list_multiple_origins_via_real_env_var(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", '["https://a.example","https://b.example"]')
    settings = Settings(_env_file=None)
    assert settings.allowed_origins == ["https://a.example", "https://b.example"]


def test_allowed_origins_production_style_ip_origin_via_real_env_var(monkeypatch):
    # The exact production value named in the ticket.
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://130.162.185.187")
    settings = Settings(_env_file=None)
    assert settings.allowed_origins == ["https://130.162.185.187"]


def test_allowed_origins_comma_separated_via_real_env_var(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://a.example,https://b.example")
    settings = Settings(_env_file=None)
    assert settings.allowed_origins == ["https://a.example", "https://b.example"]


def test_allowed_origins_empty_string_via_real_env_var_does_not_crash(monkeypatch):
    # The single most likely real-world value: exactly what
    # backend/.env.example ships before an operator configures a real
    # value. Previously crashed the entire application at import time.
    monkeypatch.setenv("ALLOWED_ORIGINS", "")
    settings = Settings(_env_file=None)
    assert settings.allowed_origins == []


def test_allowed_origins_unset_via_real_env_does_not_crash(monkeypatch):
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    settings = Settings(_env_file=None)
    assert settings.allowed_origins == []


def test_allowed_origins_malformed_json_rejected_safely_via_real_env_var(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "[this is not valid json")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_allowed_origins_garbage_string_rejected_safely_via_real_env_var(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "not a url and not json {{{")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_allowed_origins_wildcard_rejected_via_real_env_var(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "*")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_allowed_origins_wildcard_in_json_list_rejected_via_real_env_var(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", '["https://a.example","*"]')
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_allowed_origins_rejects_non_http_scheme_via_real_env_var(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "ftp://a.example")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_allowed_origins_rejects_origin_with_a_path_via_real_env_var(monkeypatch):
    # A CORS Origin is scheme://host[:port] only -- an origin with a
    # path would silently never match any real browser Origin header,
    # which is a worse failure mode than refusing it at startup.
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://a.example/some/path")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_allowed_origins_still_works_via_dotenv_file(tmp_path, monkeypatch):
    # The same JSON pre-decode bug applies identically to .env-file-
    # sourced values (DotEnvSettingsSource shares EnvSettingsSource's
    # decode path) -- verified against a real file, not just os.environ.
    env_file = tmp_path / ".env"
    env_file.write_text('ALLOWED_ORIGINS=["https://130.162.185.187"]\n')
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    settings = Settings(_env_file=str(env_file))
    assert settings.allowed_origins == ["https://130.162.185.187"]


def test_allowed_origins_empty_via_dotenv_file_does_not_crash(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("ALLOWED_ORIGINS=\n")
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    settings = Settings(_env_file=str(env_file))
    assert settings.allowed_origins == []
