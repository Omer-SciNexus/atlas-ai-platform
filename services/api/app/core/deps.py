"""FastAPI dependencies shared by every module.

``CurrentPrincipal`` authenticates the caller; ``require(permission)`` authorizes them;
``TenantSession`` gives a database session already bound to the caller's tenant, so a
handler cannot forget the tenant filter: row-level security applies it in Postgres. It also
refuses tenants that are not provisioned or are suspended, so every tenant-scoped endpoint
gets that check, not only ``/v1/me``.
"""

from collections.abc import AsyncIterator, Callable, Coroutine
from typing import Annotated, Any

import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import tenant_session
from app.core.rbac import Permission, has_permission
from app.core.security import AuthError, Principal, TokenVerifier

_bearer = HTTPBearer(auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_principal(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Principal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized("Missing bearer token")
    verifier: TokenVerifier = request.app.state.token_verifier
    try:
        principal = await verifier.verify(credentials.credentials)
    except AuthError as exc:
        raise _unauthorized(str(exc)) from None

    structlog.contextvars.bind_contextvars(
        tenant_id=str(principal.tenant_id), user=principal.subject, role=principal.role.value
    )
    return principal


CurrentPrincipal = Annotated[Principal, Depends(get_principal)]


def require(permission: Permission) -> Callable[..., Coroutine[Any, Any, Principal]]:
    async def check(principal: CurrentPrincipal) -> Principal:
        if not has_permission(principal.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permission: {permission.value}",
            )
        return principal

    return check


async def get_tenant_session(
    request: Request, principal: CurrentPrincipal
) -> AsyncIterator[AsyncSession]:
    async with tenant_session(request.app.state.sessionmaker, principal.tenant_id) as session:
        # RLS limits `tenants` to the caller's own row, so no WHERE clause is needed.
        row = (await session.execute(text("SELECT status FROM tenants"))).first()
        if row is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Tenant is not provisioned")
        if row[0] != "active":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Tenant is suspended")
        yield session


# scope="function" commits (or rolls back) when the handler returns, *before* the response is
# sent. With the default "request" scope the commit runs after the client already got a 2xx,
# so a failed commit would silently lose the write.
TenantSession = Annotated[AsyncSession, Depends(get_tenant_session, scope="function")]
