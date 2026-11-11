import itertools

import pytest

from app.core.rbac import (
    ROLE_PERMISSIONS,
    ROLE_RANK,
    Permission,
    Role,
    has_permission,
    highest_role,
)


def test_each_role_includes_every_permission_of_lower_roles() -> None:
    ordered = sorted(Role, key=ROLE_RANK.__getitem__)
    for lower, higher in itertools.pairwise(ordered):
        assert ROLE_PERMISSIONS[lower] < ROLE_PERMISSIONS[higher]


def test_owner_has_every_permission() -> None:
    assert ROLE_PERMISSIONS[Role.OWNER] == frozenset(Permission)


@pytest.mark.parametrize(
    ("role", "permission", "allowed"),
    [
        (Role.VIEWER, Permission.DOCUMENTS_READ, True),
        (Role.VIEWER, Permission.DOCUMENTS_WRITE, False),
        (Role.EDITOR, Permission.AGENTS_RUN, True),
        (Role.EDITOR, Permission.AGENTS_APPROVE, False),
        (Role.ADMIN, Permission.AUDIT_READ, True),
        (Role.ADMIN, Permission.TENANT_MANAGE, False),
    ],
)
def test_permission_matrix(role: Role, permission: Permission, allowed: bool) -> None:
    assert has_permission(role, permission) is allowed


@pytest.mark.parametrize(
    ("names", "expected"),
    [
        (["viewer", "admin", "editor"], Role.ADMIN),
        (["offline_access", "uma_authorization", "editor"], Role.EDITOR),
        ([], Role.VIEWER),
        (["superuser"], Role.VIEWER),
    ],
)
def test_highest_role_ignores_unknown_names(names: list[str], expected: Role) -> None:
    assert highest_role(names) is expected
