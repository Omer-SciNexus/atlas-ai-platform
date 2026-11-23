# Atlas API

FastAPI service for Atlas. Python 3.13, managed with [uv](https://docs.astral.sh/uv/).
To run it locally with its dependencies, see the quickstart in the [root README](../../README.md).

## How a request is handled

```
RequestContextMiddleware   request id (X-Request-ID), access log, problem+json 500s
  → CurrentPrincipal       verify the OIDC access token locally against cached JWKS
  → require(permission)    RBAC: endpoints depend on permissions, never on role names
  → TenantSession          one transaction with SET LOCAL app.tenant_id; refuses
                           unprovisioned or suspended tenants
  → Postgres RLS           every query is filtered to the caller's tenant
```

- **Tenant isolation is enforced by Postgres**, not by `WHERE` clauses in application code.
  Every tenant-scoped table has `FORCE ROW LEVEL SECURITY` and a `tenant_isolation` policy.
  The API connects as `atlas_app`, which neither owns the tables nor can bypass RLS.
  Migrations and seeding use the owner role `atlas`.
- **The tenant comes from the token** (`tenant_id` claim), and the role comes from the IdP's
  realm roles (`viewer` < `editor` < `admin` < `owner`). Users are created just-in-time on
  their first request to `/v1/me`.
- **The audit log is append-only**: the runtime role has no UPDATE, DELETE or TRUNCATE grant.
  Audit events are written in the same transaction as the change they describe.
- **Errors** are RFC 9457 `application/problem+json` and always include the request id.

## Layout

```
app/core/        config, db, auth (security, deps, rbac), errors, logging, middleware
app/modules/     feature modules (models, service, router): tenants, audit, health
migrations/      Alembic migrations (RLS policies and grants live here)
scripts/         db_roles.sql (database roles), seed.py (demo tenants)
tests/unit/      no external services
tests/integration/  real Postgres via testcontainers (skipped without Docker)
```

## Endpoints

| Method | Path | Permission | Purpose |
|---|---|---|---|
| GET | `/healthz` | none | Liveness: the process is up |
| GET | `/readyz` | none | Readiness: database and Redis reachable |
| GET | `/v1/me` | authenticated | Current user, role, permissions and tenant |
| GET | `/v1/audit-events` | `audit:read` | Recent audit events for the caller's tenant |

## Development

```bash
uv sync                          # install dependencies
uv run pytest                    # all tests (integration tests need Docker)
uv run ruff check . && uv run ruff format --check .
uv run mypy app tests scripts    # strict mode
uv run alembic revision -m "..." # new migration (write RLS policy + grants for new tables)
```

Every new tenant-scoped table needs, in its migration: a `tenant_id` column, `ENABLE` and
`FORCE ROW LEVEL SECURITY`, a `tenant_isolation` policy, and explicit grants for `atlas_app`.
Add a test in `tests/integration/test_rls.py` that proves another tenant cannot read or write it.

## Configuration

All settings are environment variables prefixed with `ATLAS_` (see `app/core/config.py` and
`.env.example` at the repository root). Every setting has a local default. Outside `local`/`test`,
the service refuses to start with default database credentials, non-JSON logs, or symmetric JWT
algorithms.

## Container image

```bash
docker build -t atlas-api services/api
docker run --env-file .env atlas-api alembic upgrade head   # migrations, as the owner role
docker run --env-file .env -p 8000:8000 atlas-api
```
