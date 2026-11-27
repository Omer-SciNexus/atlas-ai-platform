"""The tenant transaction must finish before the response is sent."""

import uuid
from collections.abc import Iterator
from types import TracebackType
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.deps import TenantSession
from app.main import create_app
from tests.support import FakeIdP, make_settings


class _Result:
    def first(self) -> tuple[str]:
        return ("active",)


class _FailingCommit:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if exc_type is None:
            raise RuntimeError("commit failed")


class _FakeSession:
    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    def begin(self) -> _FailingCommit:
        return _FailingCommit()

    async def execute(self, *args: Any, **kwargs: Any) -> _Result:
        return _Result()


@pytest.fixture
def idp() -> FakeIdP:
    return FakeIdP()


@pytest.fixture
def client(idp: FakeIdP) -> Iterator[TestClient]:
    settings = make_settings()
    app = create_app(settings)
    app.state.token_verifier = idp.verifier(settings)

    @app.post("/probe-write")
    async def probe_write(session: TenantSession) -> dict[str, bool]:
        return {"written": True}

    with TestClient(app, raise_server_exceptions=False) as c:
        app.state.sessionmaker = _FakeSession
        yield c


def test_failed_commit_is_not_reported_as_success(client: TestClient, idp: FakeIdP) -> None:
    token = idp.token(tenant_id=uuid.uuid4(), roles=["editor"])
    resp = client.post("/probe-write", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 500
