"""Real Postgres (pgvector image) via testcontainers, migrated with Alembic, roles as in prod.

The container starts once per test session. Tests that need it are marked ``integration``
and are skipped automatically when Docker is not available.
"""

import asyncio
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import asyncpg
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

API_ROOT = Path(__file__).resolve().parents[2]
TENANT_A = UUID("3f6c1c2e-8a4b-4f0e-9d51-2b7a6c1e0a01")
TENANT_B = UUID("9b2d7e4a-1c3f-4a8b-b6e2-5d4f3a2c1b02")


@dataclass(frozen=True)
class DbUrls:
    owner: str
    app: str
    owner_raw: str  # plain postgresql:// for asyncpg


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if "integration" in item.path.parts:
            item.add_marker(pytest.mark.integration)


def _docker_available() -> bool:
    try:
        import docker

        docker.from_env().ping()
    except Exception:
        return False
    return True


async def _bootstrap(raw_owner_url: str) -> None:
    conn = await asyncpg.connect(raw_owner_url)
    try:
        await conn.execute((API_ROOT / "scripts" / "db_roles.sql").read_text())
    finally:
        await conn.close()


async def _seed_tenants(raw_owner_url: str) -> None:
    conn = await asyncpg.connect(raw_owner_url)
    try:
        await conn.executemany(
            "INSERT INTO tenants (id, slug, name) VALUES ($1, $2, $3)",
            [(TENANT_A, "acme", "Acme Financial"), (TENANT_B, "globex", "Globex Retail")],
        )
    finally:
        await conn.close()


@pytest.fixture(scope="session")
def db_urls() -> Iterator[DbUrls]:
    if not _docker_available():
        pytest.skip("Docker is not available; start Docker to run integration tests")

    from testcontainers.postgres import PostgresContainer

    with PostgresContainer(
        "pgvector/pgvector:pg16", username="atlas", password="atlas", dbname="atlas"
    ) as pg:
        host, port = pg.get_container_host_ip(), pg.get_exposed_port(5432)
        urls = DbUrls(
            owner=f"postgresql+asyncpg://atlas:atlas@{host}:{port}/atlas",
            app=f"postgresql+asyncpg://atlas_app:atlas_app@{host}:{port}/atlas",
            owner_raw=f"postgresql://atlas:atlas@{host}:{port}/atlas",
        )
        asyncio.run(_bootstrap(urls.owner_raw))

        cfg = Config(str(API_ROOT / "alembic.ini"))
        cfg.attributes["database_url"] = urls.owner
        cfg.attributes["configure_logger"] = False
        command.upgrade(cfg, "head")

        asyncio.run(_seed_tenants(urls.owner_raw))
        yield urls


@pytest.fixture
async def app_engine(db_urls: DbUrls) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(db_urls.app, pool_size=1, max_overflow=0)
    yield engine
    await engine.dispose()


@pytest.fixture
async def owner_conn(db_urls: DbUrls) -> AsyncIterator[asyncpg.Connection]:
    conn = await asyncpg.connect(db_urls.owner_raw)
    yield conn
    await conn.close()
