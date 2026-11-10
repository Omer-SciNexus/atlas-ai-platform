"""Database engine and tenant-scoped sessions.

Tenant isolation is enforced by PostgreSQL row-level security. Each request runs in one
transaction that first calls ``set_config('app.tenant_id', <id>, true)``; the ``true`` makes it
transaction-local (``SET LOCAL``), so the value can never leak to the next request that reuses
the pooled connection. Policies read it through the ``app_current_tenant()`` SQL function.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings


def create_engine(settings: Settings, *, url: str | None = None) -> AsyncEngine:
    return create_async_engine(
        url or settings.database_url.get_secret_value(),
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,
        connect_args={
            "server_settings": {
                "application_name": settings.service_name,
                "statement_timeout": str(settings.db_statement_timeout_ms),
            }
        },
    )


def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def set_tenant(session: AsyncSession, tenant_id: UUID) -> None:
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )


@asynccontextmanager
async def tenant_session(
    sessionmaker: async_sessionmaker[AsyncSession], tenant_id: UUID
) -> AsyncIterator[AsyncSession]:
    """One transaction bound to one tenant. Commits on success, rolls back on error."""
    async with sessionmaker() as session, session.begin():
        await set_tenant(session, tenant_id)
        yield session
