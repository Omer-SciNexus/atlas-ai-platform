from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict

from app.core.deps import TenantSession, require
from app.core.rbac import Permission
from app.modules.audit import service

router = APIRouter(prefix="/v1/audit-events", tags=["audit"])


class AuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_user_id: UUID | None
    actor_subject: str | None
    action: str
    resource_type: str | None
    resource_id: str | None
    request_id: str | None
    details: dict[str, Any]
    occurred_at: datetime


@router.get(
    "",
    response_model=list[AuditEventOut],
    dependencies=[Depends(require(Permission.AUDIT_READ))],
)
async def list_audit_events(
    session: TenantSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[AuditEventOut]:
    events = await service.list_recent(session, limit)
    return [AuditEventOut.model_validate(e) for e in events]
