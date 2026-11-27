from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal
from app.modules.audit.models import AuditEvent


async def record(
    session: AsyncSession,
    principal: Principal,
    action: str,
    *,
    actor_user_id: UUID | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Write an audit event in the caller's transaction, so it commits or rolls back with it."""
    await _add(
        session,
        tenant_id=principal.tenant_id,
        actor_user_id=actor_user_id,
        actor_subject=principal.subject,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
    )


async def record_system(
    session: AsyncSession,
    tenant_id: UUID,
    actor: str,
    action: str,
    *,
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Audit something a background process did. ``actor`` is recorded as ``system:<actor>``."""
    await _add(
        session,
        tenant_id=tenant_id,
        actor_user_id=None,
        actor_subject=f"system:{actor}",
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
    )


async def _add(session: AsyncSession, *, details: dict[str, Any] | None, **fields: Any) -> None:
    request_id = structlog.contextvars.get_contextvars().get("request_id")
    session.add(AuditEvent(request_id=request_id, details=details or {}, **fields))
    await session.flush()


async def list_recent(
    session: AsyncSession, limit: int, before_id: int | None = None
) -> list[AuditEvent]:
    # No tenant filter here on purpose: row-level security restricts rows to the session's tenant.
    # Ids only grow, so "id < before_id" pages backwards without skipping or repeating rows.
    stmt = select(AuditEvent).order_by(AuditEvent.id.desc())
    if before_id is not None:
        stmt = stmt.where(AuditEvent.id < before_id)
    return list((await session.scalars(stmt.limit(limit))).all())
