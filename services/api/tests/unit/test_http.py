"""HTTP behavior that needs no database: request ids, error shape, authn and authz gates."""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.support import FakeIdP, make_settings

TENANT = uuid.uuid4()


@pytest.fixture
def idp() -> FakeIdP:
    return FakeIdP()


@pytest.fixture
def client(idp: FakeIdP) -> Iterator[TestClient]:
    settings = make_settings()
    app = create_app(settings)
    app.state.token_verifier = idp.verifier(settings)
    with TestClient(app) as c:
        yield c


def test_healthz_generates_request_id(client: TestClient) -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert len(resp.headers["x-request-id"]) == 32


def test_safe_request_id_is_echoed(client: TestClient) -> None:
    resp = client.get("/healthz", headers={"X-Request-ID": "trace-abc.123"})
    assert resp.headers["x-request-id"] == "trace-abc.123"


def test_unsafe_request_id_is_replaced(client: TestClient) -> None:
    resp = client.get("/healthz", headers={"X-Request-ID": "bad id\r\ninjected: 1"})
    assert resp.headers["x-request-id"] != "bad id\r\ninjected: 1"
    assert len(resp.headers["x-request-id"]) == 32


def test_missing_token_is_problem_json_401(client: TestClient) -> None:
    resp = client.get("/v1/me", headers={"X-Request-ID": "req-1"})
    assert resp.status_code == 401
    assert resp.headers["content-type"].startswith("application/problem+json")
    assert resp.headers["www-authenticate"] == "Bearer"
    body = resp.json()
    assert body["status"] == 401
    assert body["request_id"] == "req-1"


def test_invalid_token_is_401(client: TestClient) -> None:
    resp = client.get("/v1/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Malformed token"


def test_viewer_cannot_read_audit_log(client: TestClient, idp: FakeIdP) -> None:
    token = idp.token(tenant_id=TENANT, roles=["viewer"])
    resp = client.get("/v1/audit-events", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Missing permission: audit:read"
