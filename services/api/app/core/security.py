"""OIDC access-token verification.

Tokens are verified locally against the identity provider's JWKS (no network call per
request). Keys are cached; an unknown ``kid`` triggers one refresh, rate-limited so a flood
of forged tokens cannot hammer the IdP. Only the configured asymmetric algorithms are
accepted, which rules out ``alg: none`` and HS256 key-confusion attacks.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import httpx
import jwt
import structlog
from jwt import PyJWK

from app.core.config import Settings
from app.core.rbac import Role, highest_role

log = structlog.get_logger(__name__)

JwksFetcher = Callable[[], Awaitable[dict[str, Any]]]


class AuthError(Exception):
    """Raised for any invalid token. The message is safe to return to the client."""


@dataclass(frozen=True, slots=True)
class Principal:
    subject: str
    tenant_id: UUID
    role: Role
    email: str | None = None
    name: str | None = None


def http_jwks_fetcher(url: str, client: httpx.AsyncClient) -> JwksFetcher:
    async def fetch() -> dict[str, Any]:
        resp = await client.get(url, timeout=5.0)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        return data

    return fetch


class JwksCache:
    def __init__(self, fetcher: JwksFetcher, ttl_seconds: int, min_refresh_seconds: float = 10.0):
        self._fetch = fetcher
        self._ttl = ttl_seconds
        self._min_refresh = min_refresh_seconds
        self._keys: dict[str, PyJWK] = {}
        self._loaded_at: float | None = None
        self._lock = asyncio.Lock()

    async def _refresh(self, *, force: bool) -> None:
        async with self._lock:
            if self._loaded_at is not None:
                age = time.monotonic() - self._loaded_at
                if age < (self._min_refresh if force else self._ttl):
                    return
            try:
                jwks = await self._fetch()
            except httpx.HTTPError as exc:
                # Keep serving the keys we have; an IdP blip must not log everyone out.
                log.warning("jwks.fetch_failed", error=type(exc).__name__, cached=len(self._keys))
                if not self._keys:
                    raise AuthError("Signing keys unavailable") from None
                self._loaded_at = time.monotonic()
                return
            keys: dict[str, PyJWK] = {}
            for jwk in jwks.get("keys", []):
                if jwk.get("use", "sig") != "sig" or "kid" not in jwk:
                    continue
                try:
                    keys[jwk["kid"]] = PyJWK.from_dict(jwk)
                except jwt.PyJWTError:
                    log.warning("jwks.skip_unsupported_key", kid=jwk.get("kid"))
            self._keys = keys
            self._loaded_at = time.monotonic()
            log.info("jwks.refreshed", key_count=len(keys))

    async def get(self, kid: str) -> PyJWK:
        await self._refresh(force=False)
        if kid not in self._keys:
            await self._refresh(force=True)
        try:
            return self._keys[kid]
        except KeyError:
            raise AuthError("Unknown signing key") from None


class TokenVerifier:
    def __init__(self, settings: Settings, jwks: JwksCache):
        self._settings = settings
        self._jwks = jwks

    async def verify(self, token: str) -> Principal:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError:
            raise AuthError("Malformed token") from None

        alg = header.get("alg")
        if alg not in self._settings.oidc_algorithms:
            raise AuthError("Unsupported token algorithm")
        kid = header.get("kid")
        if not isinstance(kid, str):
            raise AuthError("Token has no key id")

        key = await self._jwks.get(kid)
        try:
            claims: dict[str, Any] = jwt.decode(
                token,
                key=key,
                algorithms=self._settings.oidc_algorithms,
                audience=self._settings.oidc_audience,
                issuer=self._settings.oidc_issuer,
                options={"require": ["exp", "iat", "sub", "iss", "aud"]},
                leeway=30,
            )
        except jwt.ExpiredSignatureError:
            raise AuthError("Token expired") from None
        except jwt.PyJWTError:
            raise AuthError("Invalid token") from None

        return self._principal_from_claims(claims)

    def _principal_from_claims(self, claims: dict[str, Any]) -> Principal:
        raw_tenant = claims.get(self._settings.oidc_tenant_claim)
        try:
            tenant_id = UUID(str(raw_tenant))
        except (ValueError, TypeError):
            raise AuthError("Token has no valid tenant") from None

        # Keycloak puts realm roles under realm_access.roles; other IdPs use a flat "roles".
        realm_roles = (claims.get("realm_access") or {}).get("roles") or []
        roles = [*realm_roles, *(claims.get("roles") or [])]

        return Principal(
            subject=str(claims["sub"]),
            tenant_id=tenant_id,
            role=highest_role([str(r) for r in roles]),
            email=claims.get("email"),
            name=claims.get("name") or claims.get("preferred_username"),
        )
