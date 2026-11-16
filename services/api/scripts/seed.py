"""Provision the demo tenants used by local development and the Keycloak dev realm.

Run with the owner role:  uv run python scripts/seed.py
Idempotent: safe to run repeatedly.
"""

import asyncio
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings

# These ids must match the `tenant_id` user attributes in infra/compose/keycloak/atlas-realm.json.
DEMO_TENANTS: list[tuple[UUID, str, str]] = [
    (UUID("3f6c1c2e-8a4b-4f0e-9d51-2b7a6c1e0a01"), "acme", "Acme Financial"),
    (UUID("9b2d7e4a-1c3f-4a8b-b6e2-5d4f3a2c1b02"), "globex", "Globex Retail"),
]


async def seed(database_url: str) -> None:
    engine = create_async_engine(database_url)
    async with engine.begin() as conn:
        for tenant_id, slug, name in DEMO_TENANTS:
            # Binding the tenant first lets this work under FORCE ROW LEVEL SECURITY even when
            # the owner role is not a superuser (as on managed Postgres).
            await conn.execute(
                text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_id)}
            )
            await conn.execute(
                text(
                    "INSERT INTO tenants (id, slug, name) VALUES (:id, :slug, :name) "
                    "ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name"
                ),
                {"id": tenant_id, "slug": slug, "name": name},
            )
    await engine.dispose()
    print(f"Seeded {len(DEMO_TENANTS)} tenants: {', '.join(s for _, s, _ in DEMO_TENANTS)}")


if __name__ == "__main__":
    asyncio.run(seed(get_settings().migration_database_url.get_secret_value()))
