"""Typed configuration foundation.

Environment variable names follow TECHNICAL_SPEC.md section 19.
Secrets use SecretStr so they never appear in logs, reprs, or error output.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        # Required so the three aliased admin_* fields below can still
        # be populated by their plain Python field name too (tests and
        # FastAPI dependency-override fixtures construct
        # Settings(admin_username=..., ...) directly) as well as by
        # their PANTRYPILOT_ADMIN_* env var alias.
        populate_by_name=True,
    )

    environment: str = "development"

    anthropic_api_key: SecretStr | None = None
    pantrypilot_llm_model: str | None = None
    recipeapi_io_api_key: SecretStr | None = None

    # Comma-separated list of allowed frontend origins. Empty by default:
    # CORS must be explicitly configured, never wildcarded, before any
    # origin is trusted.
    allowed_origins: list[str] = []

    # PP-003 addition (backward-compatible, additive): path to the
    # packaged grocery reference-price SQLite database (M10). Read-only
    # at runtime; never written by the live recommendation path.
    price_db_path: str = "data/pantrypilot.db"

    # Module F 4.2: deterministic max request-body size, enforced
    # before Pydantic validation or any agent/provider call (see
    # app.middleware.request_size_limit). 16 KiB comfortably covers the
    # largest structurally valid RecommendRequest (30 ingredients + 20
    # exclusions at 80 chars each, plus the remaining scalar fields and
    # JSON overhead is well under 8 KiB) while still bounding payload
    # size against abuse.
    max_request_body_bytes: int = 16384

    # Module F 4.3: in-memory, per-client-IP rate limits (see
    # app.rate_limit). Deliberately conservative but not so tight that
    # normal interactive use (typing a search, retrying once) gets
    # throttled. /recommend is stricter because each call can spend LLM
    # + RecipeAPI.io quota; /ingredients/suggest is typed interactively
    # so it gets a much higher ceiling.
    rate_limit_recommend: str = "10/minute"
    rate_limit_ingredients_suggest: str = "60/minute"

    # Admin dashboard (feature/admin-ingredient-dashboard). One
    # controlled administrative account, configured entirely via
    # environment -- never hardcoded, never committed. The password
    # itself is never stored; only its hash (app.admin.security).
    #
    # Explicit validation_alias is required here: unlike
    # pantrypilot_llm_model (whose field name already spells out its
    # own env var), Settings has no global env_prefix, so a plain field
    # name would map to ADMIN_USERNAME, not the ticket-mandated
    # PANTRYPILOT_ADMIN_USERNAME. Caught live (2026-09-13): a real
    # uvicorn process with PANTRYPILOT_ADMIN_* exported still reported
    # admin_configured=False, because TestClient-based tests construct
    # Settings(...) directly in Python and never exercise real env-var
    # parsing at all -- only a live server boot surfaces this class of
    # bug.
    admin_username: str | None = Field(default=None, validation_alias="PANTRYPILOT_ADMIN_USERNAME")
    admin_password_hash: SecretStr | None = Field(default=None, validation_alias="PANTRYPILOT_ADMIN_PASSWORD_HASH")
    admin_session_secret: SecretStr | None = Field(default=None, validation_alias="PANTRYPILOT_ADMIN_SESSION_SECRET")
    admin_session_ttl_minutes: int = 60
    rate_limit_admin_login: str = "5/minute"

    # Quota-aware recommendation depth (2026-09-13 trial-quota ticket).
    # Deliberately NOT hardcoded to the free-plan defaults still baked
    # into app.recipe.provider.MAX_PAGE_SIZE (10) / app.agent.state's
    # old fixed reserve-depth target -- both are now overridable per
    # deployment so a future plan downgrade (trial expiry) needs only an
    # env change, never a code change. Bounds are a safety ceiling
    # against a misconfigured value causing a malformed provider
    # request or unbounded search effort, not a claim about what any
    # specific plan actually supports.
    #
    # recipeapi_page_size default of 25 is evidence-based, not guessed:
    # confirmed live against the active RecipeAPI.io trial (2026-09-13,
    # one bounded GET /recipes call) that per_page=25 is accepted and
    # actually returns 25 items (meta.per_page echoed back as 25, not
    # silently capped). Reduce to 10 (the confirmed free-plan ceiling)
    # after the trial expires -- see docs/admin/ADMIN_DASHBOARD.md's
    # sibling recommendation-depth doc for the exact rollback steps.
    recipeapi_page_size: int = Field(
        default=25, ge=1, le=100, validation_alias="PANTRYPILOT_RECIPEAPI_PAGE_SIZE"
    )
    # How many strong, same-anchor, grounded feasible candidates the
    # agent should make a reasonable effort to find before treating the
    # pool as "enough" (app.agent.observations.build_decision_payload's
    # sufficient_feasible_found). Advisory only -- DEC-005 keeps stop/
    # continue authority with the LLM; provider inventory exhaustion or
    # constraint scarcity can still legitimately yield fewer. Previously
    # a fixed 3 (app.agent.state.MAX_FINAL_RECOMMENDATIONS doubled as
    # both "how many are top-tier recommendations" and "when is it okay
    # to stop") -- now decoupled: MAX_FINAL_RECOMMENDATIONS still
    # governs the recommendations/additional_options split (unchanged,
    # 3), while this governs only the stop-policy signal.
    target_feasible_results: int = Field(
        default=6, ge=1, le=20, validation_alias="PANTRYPILOT_TARGET_FEASIBLE_RESULTS"
    )

    @property
    def admin_configured(self) -> bool:
        return (
            self.admin_username is not None
            and self.admin_password_hash is not None
            and self.admin_session_secret is not None
        )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _parse_allowed_origins(cls, value: object) -> list[str]:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            parsed = [origin.strip() for origin in value.split(",") if origin.strip()]
        else:
            parsed = list(value)  # type: ignore[arg-type]
        # Module F 4.4: reject a wildcard origin outright rather than
        # silently accepting it. CORSMiddleware is configured with
        # allow_credentials=True (app.main), and browsers already
        # refuse "*" combined with credentialed requests -- so an
        # ALLOWED_ORIGINS=* misconfiguration would silently break CORS
        # for every real client rather than doing anything useful.
        # Failing fast at startup is safer than a broken production CORS.
        if "*" in parsed:
            raise ValueError(
                "ALLOWED_ORIGINS must not include '*' -- list explicit origins "
                "(wildcard origins are never permitted, and are incompatible "
                "with allow_credentials=True regardless)"
            )
        return parsed

    @property
    def llm_configured(self) -> bool:
        return self.anthropic_api_key is not None and bool(self.pantrypilot_llm_model)

    @property
    def recipeapi_io_configured(self) -> bool:
        return self.recipeapi_io_api_key is not None


@lru_cache
def get_settings() -> Settings:
    return Settings()
