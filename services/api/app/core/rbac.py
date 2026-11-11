"""Role-based access control.

Roles are ordered (owner > admin > editor > viewer) and each role inherits the permissions of
the roles below it. Endpoints depend on a *permission*, never on a role name, so the role
matrix can change in one place.
"""

from enum import StrEnum


class Role(StrEnum):
    VIEWER = "viewer"
    EDITOR = "editor"
    ADMIN = "admin"
    OWNER = "owner"


ROLE_RANK: dict[Role, int] = {Role.VIEWER: 0, Role.EDITOR: 1, Role.ADMIN: 2, Role.OWNER: 3}


class Permission(StrEnum):
    DOCUMENTS_READ = "documents:read"
    DOCUMENTS_WRITE = "documents:write"
    AGENTS_RUN = "agents:run"
    AGENTS_APPROVE = "agents:approve"
    ANALYTICS_QUERY = "analytics:query"
    USERS_MANAGE = "users:manage"
    AUDIT_READ = "audit:read"
    TENANT_MANAGE = "tenant:manage"


_VIEWER = frozenset({Permission.DOCUMENTS_READ, Permission.ANALYTICS_QUERY})
_EDITOR = _VIEWER | {Permission.DOCUMENTS_WRITE, Permission.AGENTS_RUN}
_ADMIN = _EDITOR | {Permission.AGENTS_APPROVE, Permission.USERS_MANAGE, Permission.AUDIT_READ}
_OWNER = _ADMIN | {Permission.TENANT_MANAGE}

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.VIEWER: _VIEWER,
    Role.EDITOR: _EDITOR,
    Role.ADMIN: _ADMIN,
    Role.OWNER: _OWNER,
}


def has_permission(role: Role, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS[role]


def highest_role(names: list[str] | tuple[str, ...]) -> Role:
    """Pick the strongest Atlas role among IdP role names; unknown names are ignored.

    A user with no Atlas role gets ``viewer`` (read-only), the least-privileged role.
    """
    roles = [Role(n) for n in names if n in Role._value2member_map_]
    return max(roles, key=ROLE_RANK.__getitem__, default=Role.VIEWER)
