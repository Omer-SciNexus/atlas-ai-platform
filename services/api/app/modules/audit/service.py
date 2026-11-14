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
    request_id = structlog.contextvars.get_contextvars().get("request_id")
    session.add(
        AuditEvent(
            tenant_id=principal.tenant_id,
            actor_user_id=actor_user_id,
            actor_subject=principal.subject,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            request_id=request_id,
            details=details or {},
        )
    )
    await session.flush()


async def list_recent(session: AsyncSession, limit: int) -> list[AuditEvent]:
    # No tenant filter here on purpose: row-level security restricts rows to the session's tenant.
    stmt = select(AuditEvent).order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
    return list((await session.scalars(stmt.limit(limit))).all())
