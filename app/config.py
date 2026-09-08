"""Application configuration.

Every value comes from the environment (I5: no secrets in any client, and none
hardcoded here either). pydantic-settings validates at import time, so a
missing or malformed secret fails the process at boot rather than at the first
request that needs it.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "development"
    debug: bool = False
    log_level: str = "INFO"

    public_base_url: str = "http://localhost:8000"

    postgres_user: str = "vora"
    postgres_password: SecretStr
    postgres_db: str = "vora"
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    redis_url: str = "redis://redis:6379/0"

    osrm_base_url: str = "http://osrm:5000"
    osrm_timeout_s: float = 2.0
    # Off until Phase 2 prepares the routing extract. /health then reports osrm
    # as not_configured rather than as a failure.
    osrm_enabled: bool = False

    # No defaults. A missing secret must stop the process at boot, not fall
    # back to a value that is in a public repository. Distinct key per purpose,
    # so compromise of one does not grant the others.
    #
    # SecretStr keeps these out of logs and tracebacks: repr() renders as
    # '**********', so an exception that carries the settings object cannot
    # print the signing key into stdout.
    jwt_secret: SecretStr
    quote_hmac_secret: SecretStr
    share_token_secret: SecretStr
    kyc_encryption_key: SecretStr

    access_token_ttl_s: int = 900
    refresh_token_ttl_s: int = 2592000

    allowed_country_codes: str = "237"
    # SMS delivery through an Android handset running HTTPSMS. Both must be
    # set for the real sender to be selected; either missing falls back to the
    # console sender, which is the honest default rather than a silent no-op.
    httpsms_api_key: SecretStr | None = None
    httpsms_from_number: str | None = None

    allow_test_numbers: bool = False
    test_number_prefix: str = "+23760000000"

    cors_origins: str = ""

    max_body_bytes: int = 1_048_576
    request_timeout_s: int = 15

    service_area_bbox: str = "9.55,3.60,11.75,4.20"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password.get_secret_value()}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def allowed_country_code_list(self) -> list[str]:
        return [c.strip() for c in self.allowed_country_codes.split(",") if c.strip()]

    @property
    def service_area_bounds(self) -> tuple[float, float, float, float]:
        parts = [float(p) for p in self.service_area_bbox.split(",")]
        if len(parts) != 4:
            raise ValueError("SERVICE_AREA_BBOX must be min_lng,min_lat,max_lng,max_lat")
        return parts[0], parts[1], parts[2], parts[3]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"production", "prod"}

    @field_validator("cors_origins")
    @classmethod
    def _reject_wildcard_cors(cls, v: str) -> str:
        # I6-adjacent: a wildcard allow-list with credentials is the standard
        # CORS foot-gun. Fail at boot, not in review.
        if "*" in v:
            raise ValueError("CORS_ORIGINS must be an explicit allow-list, never '*'")
        return v

    @field_validator(
        "jwt_secret", "quote_hmac_secret", "share_token_secret", "kyc_encryption_key"
    )
    @classmethod
    def _reject_weak_secret(cls, v: SecretStr) -> SecretStr:
        # 32 hex characters is 128 bits, the floor for an HMAC key here.
        # The placeholder check catches the case where someone copies
        # .env.example to .env and forgets to run the generator.
        raw = v.get_secret_value()
        if len(raw) < 32:
            raise ValueError("secret must be at least 32 characters (openssl rand -hex 32)")
        if raw.startswith("replace_with") or "change_me" in raw:
            raise ValueError("secret is still the .env.example placeholder")
        return v

    @model_validator(mode="after")
    def _reject_duplicate_secrets(self) -> Settings:
        # Reusing one key for JWTs and quote signing means a leaked JWT key
        # also lets an attacker mint their own fares.
        secrets = [
            self.jwt_secret.get_secret_value(),
            self.quote_hmac_secret.get_secret_value(),
            self.share_token_secret.get_secret_value(),
            self.kyc_encryption_key.get_secret_value(),
        ]
        if len(set(secrets)) != len(secrets):
            raise ValueError("each secret must be distinct; generate them separately")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
