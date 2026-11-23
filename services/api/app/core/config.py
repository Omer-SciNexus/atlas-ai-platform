"""Application settings, loaded from environment variables prefixed with ``ATLAS_``.

Every value has a safe local default so the service runs against ``docker compose``
without extra setup. Secrets are ``SecretStr`` so they never appear in logs or reprs.
"""

from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolved from this file, not the working directory, so `.env` is found no matter where the
# process starts (repo root, services/api, an IDE, a container).
API_ROOT = Path(__file__).resolve().parents[2]  # services/api
REPO_ROOT = API_ROOT.parents[1]


class Environment(StrEnum):
    LOCAL = "local"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ATLAS_",
        # Later files win: the repo-root .env (documented in .env.example) overrides
        # services/api/.env.
        env_file=(API_ROOT / ".env", REPO_ROOT / ".env"),
        extra="ignore",
    )

    env: Environment = Environment.LOCAL
    service_name: str = "atlas-api"
    log_level: str = "INFO"
    log_json: bool = False

    # Runtime role (no BYPASSRLS, not the table owner) so row-level security applies.
    database_url: SecretStr = SecretStr(
        "postgresql+asyncpg://atlas_app:atlas_app@localhost:5432/atlas"
    )
    # Owner role, used only by migrations and provisioning scripts.
    migration_database_url: SecretStr = SecretStr(
        "postgresql+asyncpg://atlas:atlas@localhost:5432/atlas"
    )
    db_pool_size: int = 10
    db_max_overflow: int = 10
    db_statement_timeout_ms: int = 15_000

    redis_url: SecretStr = SecretStr("redis://localhost:6379/0")

    oidc_issuer: str = "http://localhost:8080/realms/atlas"
    oidc_audience: str = "atlas-api"
    oidc_jwks_url: str | None = None
    oidc_algorithms: list[str] = ["RS256"]
    oidc_jwks_cache_seconds: int = 600
    oidc_tenant_claim: str = "tenant_id"

    cors_origins: list[str] = ["http://localhost:3000"]

    @property
    def is_production(self) -> bool:
        return self.env in {Environment.STAGING, Environment.PRODUCTION}

    @property
    def jwks_url(self) -> str:
        # Keycloak's JWKS path. Other IdPs set ATLAS_OIDC_JWKS_URL explicitly.
        return self.oidc_jwks_url or f"{self.oidc_issuer.rstrip('/')}/protocol/openid-connect/certs"

    @model_validator(mode="after")
    def _check_production_safety(self) -> "Settings":
        if self.is_production:
            if "atlas_app:atlas_app@" in self.database_url.get_secret_value():
                raise ValueError("Default database credentials are not allowed outside local/test")
            if "atlas:atlas@" in self.migration_database_url.get_secret_value():
                raise ValueError(
                    "Default migration database credentials are not allowed outside local/test"
                )
            if not self.log_json:
                raise ValueError("ATLAS_LOG_JSON must be true outside local/test")
            if any(
                alg.upper().startswith("HS") or alg.lower() == "none"
                for alg in self.oidc_algorithms
            ):
                raise ValueError("Only asymmetric JWT algorithms are allowed in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
