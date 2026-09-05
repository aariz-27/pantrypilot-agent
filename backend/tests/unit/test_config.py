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
