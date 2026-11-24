"""Test helpers: a local signing key that stands in for the identity provider."""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from app.core.config import Environment, Settings
from app.core.security import JwksCache, TokenVerifier

ISSUER = "https://idp.test/realms/atlas"
AUDIENCE = "atlas-api"


def make_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "env": Environment.TEST,
        "oidc_issuer": ISSUER,
        "oidc_audience": AUDIENCE,
        "redis_url": "redis://127.0.0.1:1/0",  # nothing listens here; readiness reports it
        "log_level": "WARNING",
    }
    values.update(overrides)
    return Settings(**values)


@dataclass
class SigningKey:
    kid: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    private_key: rsa.RSAPrivateKey = field(
        default_factory=lambda: rsa.generate_private_key(public_exponent=65537, key_size=2048)
    )

    def public_jwk(self) -> dict[str, Any]:
        jwk: dict[str, Any] = RSAAlgorithm.to_jwk(self.private_key.public_key(), as_dict=True)
        jwk.update({"kid": self.kid, "use": "sig", "alg": "RS256"})
        return jwk


@dataclass
class FakeIdP:
    keys: list[SigningKey] = field(default_factory=lambda: [SigningKey()])
    fetch_count: int = 0

    async def fetch_jwks(self) -> dict[str, Any]:
        self.fetch_count += 1
        return {"keys": [k.public_jwk() for k in self.keys]}

    def verifier(self, settings: Settings, *, min_refresh_seconds: float = 10.0) -> TokenVerifier:
        cache = JwksCache(self.fetch_jwks, ttl_seconds=600, min_refresh_seconds=min_refresh_seconds)
        return TokenVerifier(settings, cache)

    def token(
        self,
        *,
        sub: str | None = None,
        tenant_id: uuid.UUID | str | None = None,
        roles: list[str] | None = None,
        email: str | None = None,
        expires_in: int = 300,
        key: SigningKey | None = None,
        **claims: Any,
    ) -> str:
        now = int(time.time())
        payload: dict[str, Any] = {
            "iss": ISSUER,
            "aud": AUDIENCE,
            "sub": sub or f"user-{uuid.uuid4().hex[:8]}",
            "iat": now,
            "exp": now + expires_in,
            "realm_access": {"roles": roles if roles is not None else ["viewer"]},
            "email": email,
        }
        if tenant_id is not None:
            payload["tenant_id"] = str(tenant_id)
        payload.update(claims)
        signer = key or self.keys[0]
        return jwt.encode(
            payload, signer.private_key, algorithm="RS256", headers={"kid": signer.kid}
        )


def minimal_pdf(pages: list[str]) -> bytes:
    """Build a small, valid PDF with one line of text per page (ASCII only)."""
    objects: list[bytes] = []
    page_ids = [4 + 2 * i for i in range(len(pages))]
    kids = " ".join(f"{i} 0 R" for i in page_ids)
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode())
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for index, text in enumerate(pages):
        escaped = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode()
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> "
            f"/Contents {page_ids[index] + 1} 0 R >>".encode()
        )
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream")

    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(out)
