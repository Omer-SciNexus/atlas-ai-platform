"""Application settings, loaded from environment variables prefixed with ``ATLAS_``.

Every value has a safe local default so the service runs against ``docker compose``
without extra setup. Secrets are ``SecretStr`` so they never appear in logs or reprs.
"""

from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def project_roots(config_file: Path) -> tuple[Path, Path]:
    """Return (api_root, repo_root) for this file's location.

    Uses ``.parent`` rather than ``.parents[n]`` so a shallow layout (the Docker image puts the
    API at ``/app``, making the "repo root" ``/``) still works instead of raising IndexError.
    """
    api_root = config_file.resolve().parent.parent.parent
    return api_root, api_root.parent.parent


# Resolved from this file, not the working directory, so `.env` is found no matter where the
# process starts (repo root, services/api, an IDE, a container).
API_ROOT, REPO_ROOT = project_roots(Path(__file__))


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

    # ---- Documents and ingestion ----
    # Uploaded files, keyed by tenant and document id. Local disk now; S3 in the AWS phase.
    blob_dir: Path = REPO_ROOT / "data" / "blobs"
    max_upload_bytes: int = 25 * 1024 * 1024
    chunk_size_chars: int = 1600
    chunk_overlap_chars: int = 200
    worker_concurrency: int = 2
    worker_poll_seconds: float = 1.0
    ingestion_max_attempts: int = 3
    # A job still "running" after this long is assumed to belong to a dead worker.
    ingestion_lock_timeout_seconds: int = 600

    # ---- Embeddings ----
    # "hash" is a keyless lexical embedder for local development and tests. It finds
    # passages that share words with the question, not passages that share meaning.
    embedding_provider: Literal["hash", "voyage"] = "hash"
    embedding_model: str = "voyage-3.5"
    voyage_api_key: SecretStr | None = None

    # ---- Retrieval and answers ----
    retrieval_top_k: int = 8
    # Chunks scoring below this cosine similarity are not shown to the model.
    retrieval_min_score: float = 0.0
    anthropic_api_key: SecretStr | None = None
    chat_model: str = "claude-opus-5-5"
    chat_effort: Literal["low", "medium", "high", "xhigh", "max"] = "medium"
    chat_max_tokens: int = 16_000

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
            if self.embedding_provider == "hash":
                raise ValueError("The hash embedder is for local/test only; use a real model")
        if self.embedding_provider == "voyage" and self.voyage_api_key is None:
            raise ValueError("ATLAS_VOYAGE_API_KEY is required when the provider is voyage")
        if not 0 <= self.chunk_overlap_chars < self.chunk_size_chars:
            raise ValueError("Chunk overlap must be smaller than the chunk size")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
