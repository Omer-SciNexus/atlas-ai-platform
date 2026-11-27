from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import redis.asyncio as redis
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings, get_settings
from app.core.db import create_engine, create_sessionmaker
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.core.security import JwksCache, TokenVerifier, http_jwks_fetcher
from app.modules.audit.router import router as audit_router
from app.modules.documents.blobs import LocalBlobStore
from app.modules.documents.router import router as documents_router
from app.modules.health.router import router as health_router
from app.modules.llm.answers import create_answer_generator
from app.modules.llm.embeddings import create_embedder
from app.modules.rag.router import router as rag_router
from app.modules.retrieval.store import PgVectorStore
from app.modules.tenants.router import router as identity_router

VERSION = "0.1.0"
log = structlog.get_logger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(settings)
        http = httpx.AsyncClient()
        app.state.settings = settings
        app.state.engine = engine
        app.state.sessionmaker = create_sessionmaker(engine)
        app.state.redis = redis.from_url(settings.redis_url.get_secret_value())
        app.state.http = http
        app.state.vector_store = PgVectorStore()
        # Tests may install their own parts (a local key set, a scripted model, a temporary
        # blob directory) before startup; anything already set is kept.
        if not hasattr(app.state, "token_verifier"):
            jwks = JwksCache(
                http_jwks_fetcher(settings.jwks_url, http), settings.oidc_jwks_cache_seconds
            )
            app.state.token_verifier = TokenVerifier(settings, jwks)
        if not hasattr(app.state, "blob_store"):
            app.state.blob_store = LocalBlobStore(settings.blob_dir)
        if not hasattr(app.state, "embedder"):
            app.state.embedder = create_embedder(settings, http)
        if not hasattr(app.state, "answer_generator"):
            app.state.answer_generator = create_answer_generator(settings)
        log.info(
            "startup",
            env=settings.env.value,
            version=VERSION,
            embedding_model=app.state.embedder.model,
            answers_enabled=app.state.answer_generator is not None,
        )
        try:
            yield
        finally:
            await http.aclose()
            await app.state.redis.aclose()
            await engine.dispose()
            log.info("shutdown")

    app = FastAPI(
        title="Atlas API",
        version=VERSION,
        lifespan=lifespan,
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    # Added last so it is the outermost middleware and sees every request.
    app.add_middleware(RequestContextMiddleware)
    register_error_handlers(app)

    app.include_router(health_router)
    app.include_router(identity_router)
    app.include_router(audit_router)
    app.include_router(documents_router)
    app.include_router(rag_router)
    return app


app = create_app()
