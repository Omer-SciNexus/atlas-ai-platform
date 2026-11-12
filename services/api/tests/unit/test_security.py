import uuid

import httpx
import jwt
import pytest

from app.core.rbac import Role
from app.core.security import AuthError, JwksCache, TokenVerifier
from tests.support import FakeIdP, SigningKey, make_settings

TENANT = uuid.UUID("3f6c1c2e-8a4b-4f0e-9d51-2b7a6c1e0a01")


@pytest.fixture
def idp() -> FakeIdP:
    return FakeIdP()


@pytest.fixture
def verifier(idp: FakeIdP) -> TokenVerifier:
    return idp.verifier(make_settings())


async def test_valid_token_becomes_principal(idp: FakeIdP, verifier: TokenVerifier) -> None:
    token = idp.token(sub="alice", tenant_id=TENANT, roles=["editor", "admin"], email="a@x.test")
    principal = await verifier.verify(token)
    assert principal.subject == "alice"
    assert principal.tenant_id == TENANT
    assert principal.role is Role.ADMIN
    assert principal.email == "a@x.test"


@pytest.mark.parametrize(
    ("claims", "message"),
    [
        ({"expires_in": -120}, "Token expired"),
        ({"aud": "some-other-api"}, "Invalid token"),
        ({"iss": "https://evil.test/realms/atlas"}, "Invalid token"),
    ],
)
async def test_rejects_bad_claims(
    idp: FakeIdP, verifier: TokenVerifier, claims: dict[str, object], message: str
) -> None:
    token = idp.token(tenant_id=TENANT, **claims)  # type: ignore[arg-type]
    with pytest.raises(AuthError, match=message):
        await verifier.verify(token)


async def test_rejects_token_without_tenant(idp: FakeIdP, verifier: TokenVerifier) -> None:
    with pytest.raises(AuthError, match="no valid tenant"):
        await verifier.verify(idp.token(tenant_id=None))


async def test_rejects_token_signed_by_unknown_key(idp: FakeIdP, verifier: TokenVerifier) -> None:
    forged = idp.token(tenant_id=TENANT, key=SigningKey())
    with pytest.raises(AuthError, match="Unknown signing key"):
        await verifier.verify(forged)


async def test_rejects_hs256_key_confusion(idp: FakeIdP, verifier: TokenVerifier) -> None:
    # Classic attack: sign with HMAC using the *public* key as the secret.
    token = jwt.encode(
        {"sub": "x", "tenant_id": str(TENANT)},
        "public-key-material-used-as-an-hmac-secret!",
        algorithm="HS256",
        headers={"kid": idp.keys[0].kid},
    )
    with pytest.raises(AuthError, match="Unsupported token algorithm"):
        await verifier.verify(token)


async def test_rejects_alg_none(verifier: TokenVerifier) -> None:
    token = jwt.encode({"sub": "x"}, key=None, algorithm="none")
    with pytest.raises(AuthError, match="Unsupported token algorithm"):
        await verifier.verify(token)


async def test_picks_up_rotated_key_with_one_refresh(idp: FakeIdP) -> None:
    verifier = idp.verifier(make_settings(), min_refresh_seconds=0)
    await verifier.verify(idp.token(tenant_id=TENANT))
    assert idp.fetch_count == 1

    new_key = SigningKey()
    idp.keys.append(new_key)
    await verifier.verify(idp.token(tenant_id=TENANT, key=new_key))
    assert idp.fetch_count == 2


async def test_unknown_kid_refresh_is_rate_limited(idp: FakeIdP, verifier: TokenVerifier) -> None:
    await verifier.verify(idp.token(tenant_id=TENANT))
    for _ in range(5):
        with pytest.raises(AuthError):
            await verifier.verify(idp.token(tenant_id=TENANT, key=SigningKey()))
    assert idp.fetch_count == 1


async def test_keeps_cached_keys_when_idp_is_down(idp: FakeIdP) -> None:
    calls = 0

    async def flaky_fetch() -> dict[str, object]:
        nonlocal calls
        calls += 1
        if calls > 1:
            raise httpx.ConnectError("idp down")
        return await idp.fetch_jwks()

    cache = JwksCache(flaky_fetch, ttl_seconds=0, min_refresh_seconds=0)  # type: ignore[arg-type]
    verifier = TokenVerifier(make_settings(), cache)
    await verifier.verify(idp.token(tenant_id=TENANT))
    # TTL expired and the IdP is down, but the cached key still verifies.
    principal = await verifier.verify(idp.token(tenant_id=TENANT))
    assert principal.tenant_id == TENANT
