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


async def _insert_document_with_chunk(conn: asyncpg.Connection, tenant: uuid.UUID) -> uuid.UUID:
    document_id: uuid.UUID = await conn.fetchval(
        "INSERT INTO documents (tenant_id, title, filename, mime_type, sha256, size_bytes, status) "
        "VALUES ($1, 'T', 'f.txt', 'text/plain', $2, 1, 'ready') RETURNING id",
        tenant,
        uuid.uuid4().hex + uuid.uuid4().hex,
    )
    vector = "[" + ",".join(["0.03125"] * 1024) + "]"
    await conn.execute(
        "INSERT INTO document_chunks (tenant_id, document_id, ordinal, content, char_start, "
        "char_end, embedding, embedding_model) VALUES ($1, $2, 0, 'secret', 0, 6, $3::vector, 'm')",
        tenant,
        document_id,
        vector,
    )
    return document_id


async def test_documents_and_chunks_are_isolated(
    app_engine: AsyncEngine, owner_conn: asyncpg.Connection
) -> None:
    doc_a = await _insert_document_with_chunk(owner_conn, TENANT_A)
    doc_b = await _insert_document_with_chunk(owner_conn, TENANT_B)

    async with tenant_session(create_sessionmaker(app_engine), TENANT_A) as session:
        documents = set((await session.scalars(text("SELECT id FROM documents"))).all())
        chunk_docs = set(
            (await session.scalars(text("SELECT document_id FROM document_chunks"))).all()
        )
        # A direct write to the other tenant's rows changes nothing: they are not visible.
        updated = await session.execute(
            text("UPDATE documents SET title = 'pwned' WHERE id = :d"), {"d": doc_b}
        )
        deleted = await session.execute(
            text("DELETE FROM document_chunks WHERE document_id = :d"), {"d": doc_b}
        )

    assert doc_a in documents
    assert doc_b not in documents
    assert doc_a in chunk_docs
    assert doc_b not in chunk_docs
    assert (updated.rowcount, deleted.rowcount) == (0, 0)  # type: ignore[attr-defined]
    assert await owner_conn.fetchval("SELECT title FROM documents WHERE id = $1", doc_b) == "T"


async def test_cannot_attach_a_chunk_to_another_tenant(
    app_engine: AsyncEngine, owner_conn: asyncpg.Connection
) -> None:
    doc_a = await _insert_document_with_chunk(owner_conn, TENANT_A)
    vector = "[" + ",".join(["0.03125"] * 1024) + "]"
    with pytest.raises(DBAPIError, match="row-level security"):
        async with tenant_session(create_sessionmaker(app_engine), TENANT_A) as session:
            await session.execute(
                text(
                    "INSERT INTO document_chunks (tenant_id, document_id, ordinal, content, "
                    "char_start, char_end, embedding, embedding_model) "
                    "VALUES (:t, :d, 1, 'x', 0, 1, CAST(:v AS vector), 'm')"
                ),
                {"t": TENANT_B, "d": doc_a, "v": vector},
            )


async def test_chunks_cannot_be_edited_and_jobs_cannot_be_deleted(
    app_engine: AsyncEngine, owner_conn: asyncpg.Connection
) -> None:
    await _insert_document_with_chunk(owner_conn, TENANT_A)
    for statement in (
        "UPDATE document_chunks SET content = 'tampered'",
        "DELETE FROM ingestion_jobs",
    ):
        with pytest.raises(DBAPIError, match="permission denied"):
            async with tenant_session(create_sessionmaker(app_engine), TENANT_A) as session:
                await session.execute(text(statement))
