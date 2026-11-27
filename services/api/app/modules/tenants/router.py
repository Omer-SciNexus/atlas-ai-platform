from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.deps import CurrentPrincipal, TenantSession
from app.core.rbac import ROLE_PERMISSIONS, Role
from app.modules.tenants.service import sync_current_user

router = APIRouter(prefix="/v1", tags=["identity"])


class TenantOut(BaseModel):
    id: UUID
    slug: str
    name: str


class MeOut(BaseModel):
    user_id: UUID
    email: str | None
    display_name: str | None
    role: Role
    permissions: list[str]
    tenant: TenantOut


@router.get("/me", response_model=MeOut)
async def me(principal: CurrentPrincipal, session: TenantSession) -> MeOut:
    current = await sync_current_user(session, principal)

    return MeOut(
        user_id=current.user.id,
        email=current.user.email,
        display_name=current.user.display_name,
        role=principal.role,
        permissions=sorted(p.value for p in ROLE_PERMISSIONS[principal.role]),
        tenant=TenantOut(id=current.tenant.id, slug=current.tenant.slug, name=current.tenant.name),
    )
