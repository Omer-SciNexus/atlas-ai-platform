"""Row-level security, tested as the runtime role the API really uses.

These are the tests that prove one tenant can never read or write another tenant's rows,
even if application code forgets a WHERE clause.
"""

import uuid

import asyncpg
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db import create_sessionmaker, tenant_session
from tests.integration.conftest import TENANT_A, TENANT_B


async def _insert_user(conn: asyncpg.Connection, tenant: uuid.UUID) -> str:
    sub = f"sub-{uuid.uuid4().hex[:8]}"
    await conn.execute(
        "INSERT INTO users (tenant_id, oidc_sub, role) VALUES ($1, $2, 'viewer')", tenant, sub
    )
    return sub


async def test_session_sees_only_its_own_tenant(
    app_engine: AsyncEngine, owner_conn: asyncpg.Connection
) -> None:
    sub_a = await _insert_user(owner_conn, TENANT_A)
    sub_b = await _insert_user(owner_conn, TENANT_B)

    async with tenant_session(create_sessionmaker(app_engine), TENANT_A) as session:
        subs = set((await session.scalars(text("SELECT oidc_sub FROM users"))).all())
        tenants = (await session.execute(text("SELECT slug FROM tenants"))).scalars().all()

    assert sub_a in subs
    assert sub_b not in subs
    assert tenants == ["acme"]


async def test_no_tenant_bound_means_no_rows(app_engine: AsyncEngine) -> None:
    async with app_engine.connect() as conn:
        assert (await conn.execute(text("SELECT count(*) FROM tenants"))).scalar_one() == 0
        assert (await conn.execute(text("SELECT count(*) FROM users"))).scalar_one() == 0


async def test_tenant_setting_does_not_leak_to_next_transaction(app_engine: AsyncEngine) -> None:
    # pool_size=1: both transactions reuse the same physical connection.
    async with tenant_session(create_sessionmaker(app_engine), TENANT_A) as session:
        assert (await session.execute(text("SELECT count(*) FROM tenants"))).scalar_one() == 1

    async with app_engine.connect() as conn:
        assert (await conn.execute(text("SELECT count(*) FROM tenants"))).scalar_one() == 0


async def test_cannot_insert_rows_for_another_tenant(app_engine: AsyncEngine) -> None:
    with pytest.raises(DBAPIError, match="row-level security"):
        async with tenant_session(create_sessionmaker(app_engine), TENANT_A) as session:
            await session.execute(
                text("INSERT INTO users (tenant_id, oidc_sub, role) VALUES (:t, 'x', 'viewer')"),
                {"t": TENANT_B},
            )


async def test_cannot_move_a_row_to_another_tenant(
    app_engine: AsyncEngine, owner_conn: asyncpg.Connection
) -> None:
    sub = await _insert_user(owner_conn, TENANT_A)
    with pytest.raises(DBAPIError, match="row-level security"):
        async with tenant_session(create_sessionmaker(app_engine), TENANT_A) as session:
            await session.execute(
                text("UPDATE users SET tenant_id = :b WHERE oidc_sub = :s"),
                {"b": TENANT_B, "s": sub},
            )


async def test_audit_log_is_append_only(app_engine: AsyncEngine) -> None:
    async with tenant_session(create_sessionmaker(app_engine), TENANT_A) as session:
        await session.execute(
            text("INSERT INTO audit_events (tenant_id, action) VALUES (:t, 'test.event')"),
            {"t": TENANT_A},
        )

    for statement in ("UPDATE audit_events SET action = 'tampered'", "DELETE FROM audit_events"):
        with pytest.raises(DBAPIError, match="permission denied"):
            async with tenant_session(create_sessionmaker(app_engine), TENANT_A) as session:
                await session.execute(text(statement))


async def test_app_role_cannot_create_or_rename_tenants(app_engine: AsyncEngine) -> None:
    with pytest.raises(DBAPIError, match="permission denied"):
        async with tenant_session(create_sessionmaker(app_engine), TENANT_A) as session:
            await session.execute(text("UPDATE tenants SET name = 'pwned'"))


async def test_app_role_cannot_delete_users(
    app_engine: AsyncEngine, owner_conn: asyncpg.Connection
) -> None:
    sub = await _insert_user(owner_conn, TENANT_A)
    with pytest.raises(DBAPIError, match="permission denied"):
        async with tenant_session(create_sessionmaker(app_engine), TENANT_A) as session:
            await session.execute(text("DELETE FROM users WHERE oidc_sub = :s"), {"s": sub})
