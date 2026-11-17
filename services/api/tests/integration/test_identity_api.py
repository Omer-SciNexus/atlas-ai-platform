"""End-to-end API tests: real app, real Postgres, tokens from a fake IdP."""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.integration.conftest import TENANT_A, TENANT_B, DbUrls
from tests.support import FakeIdP, make_settings


@pytest.fixture
def idp() -> FakeIdP:
    return FakeIdP()


@pytest.fixture
def client(db_urls: DbUrls, idp: FakeIdP) -> Iterator[TestClient]:
    settings = make_settings(database_url=db_urls.app)
    app = create_app(settings)
    app.state.token_verifier = idp.verifier(settings)
    with TestClient(app) as c:
        yield c


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_first_request_provisions_user_once(client: TestClient, idp: FakeIdP) -> None:
    sub = f"alice-{uuid.uuid4().hex[:6]}"
    token = idp.token(sub=sub, tenant_id=TENANT_A, roles=["admin"], email="alice@acme.test")

    first = client.get("/v1/me", headers=_auth(token))
    second = client.get("/v1/me", headers=_auth(token))

    assert first.status_code == 200, first.text
    body = first.json()
    assert body["tenant"]["slug"] == "acme"
    assert body["role"] == "admin"
    assert "audit:read" in body["permissions"]
    assert second.json()["user_id"] == body["user_id"]

    events = client.get("/v1/audit-events", headers=_auth(token)).json()
    provisioned = [
        e for e in events if e["action"] == "user.provisioned" and e["actor_subject"] == sub
    ]
    assert len(provisioned) == 1
    assert provisioned[0]["request_id"]


def test_audit_log_is_isolated_between_tenants(client: TestClient, idp: FakeIdP) -> None:
    alice = idp.token(sub=f"alice-{uuid.uuid4().hex[:6]}", tenant_id=TENANT_A, roles=["admin"])
    carol_sub = f"carol-{uuid.uuid4().hex[:6]}"
    carol = idp.token(sub=carol_sub, tenant_id=TENANT_B, roles=["admin"])
    client.get("/v1/me", headers=_auth(alice))
    client.get("/v1/me", headers=_auth(carol))

    acme_events = client.get("/v1/audit-events", headers=_auth(alice)).json()
    assert all(e["actor_subject"] != carol_sub for e in acme_events)

    globex_events = client.get("/v1/audit-events", headers=_auth(carol)).json()
    assert any(e["actor_subject"] == carol_sub for e in globex_events)


def test_unknown_tenant_is_forbidden(client: TestClient, idp: FakeIdP) -> None:
    token = idp.token(tenant_id=uuid.uuid4(), roles=["owner"])
    resp = client.get("/v1/me", headers=_auth(token))
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Tenant is not provisioned"


def test_validation_error_is_problem_json(client: TestClient, idp: FakeIdP) -> None:
    token = idp.token(tenant_id=TENANT_A, roles=["admin"])
    resp = client.get("/v1/audit-events?limit=0", headers=_auth(token))
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/problem+json")
    assert resp.json()["errors"][0]["loc"] == ["query", "limit"]


def test_readiness_reports_database(client: TestClient) -> None:
    resp = client.get("/readyz")
    assert resp.json()["checks"]["database"] == "ok"
