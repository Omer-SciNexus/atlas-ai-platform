from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, literal_column, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal
from app.modules.audit import service as audit
from app.modules.tenants.models import Tenant, User


@dataclass(frozen=True, slots=True)
class CurrentUser:
    user: User
    tenant: Tenant


async def get_current_tenant(session: AsyncSession) -> Tenant:
    # RLS limits `tenants` to the row whose id matches the session's tenant, and the
    # TenantSession dependency has already checked that the row exists and is active.
    return (await session.scalars(select(Tenant))).one()


async def sync_current_user(session: AsyncSession, principal: Principal) -> CurrentUser:
    """Upsert the caller's user row (just-in-time provisioning) and return it with its tenant.

    The IdP stays the source of truth for identity and role; the row exists so other tables
    can reference users and so admins can see who has used the tenant.
    """
    tenant = await get_current_tenant(session)

    stmt: Any = (
        insert(User)
        .values(
            tenant_id=principal.tenant_id,
            oidc_sub=principal.subject,
            email=principal.email,
            display_name=principal.name,
            role=principal.role.value,
        )
        .on_conflict_do_update(
            index_elements=[User.tenant_id, User.oidc_sub],
            set_={
                "email": principal.email,
                "display_name": principal.name,
                "role": principal.role.value,
                "last_seen_at": func.now(),
            },
        )
        # xmax = 0 only for a freshly inserted row: tells us whether this was a first login.
        .returning(User, literal_column("(xmax = 0)").label("inserted"))
    )
    row = (await session.execute(stmt)).one()
    user: User = row[0]
    if row.inserted:
        await audit.record(
            session,
            principal,
            "user.provisioned",
            actor_user_id=user.id,
            resource_type="user",
            resource_id=str(user.id),
            details={"role": principal.role.value},
        )
    return CurrentUser(user=user, tenant=tenant)
