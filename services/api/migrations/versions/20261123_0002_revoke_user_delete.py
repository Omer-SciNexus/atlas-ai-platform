"""Revoke DELETE on users from the runtime role.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-23

Migration 0001 grants the app role SELECT, INSERT, UPDATE on ``users``, but the default
privileges in scripts/db_roles.sql also hand it DELETE on every new table. Users are
deprovisioned in the IdP, and audit events reference them, so the API must not delete rows.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'atlas_app') THEN
                REVOKE DELETE, TRUNCATE ON users FROM atlas_app;
            END IF;
        END
        $$
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'atlas_app') THEN
                GRANT DELETE ON users TO atlas_app;
            END IF;
        END
        $$
        """
    )
