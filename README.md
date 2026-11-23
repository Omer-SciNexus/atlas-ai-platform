![Atlas](docs/assets/readme/atlas-hero-banner.png)

# Atlas

A multi-tenant enterprise AI knowledge and agent platform.

**Status:** the foundation is in place: tenancy, identity, authorization and audit logging. The AI
features on the roadmap below are not built yet, and `apps/web` currently holds only image assets.

## Roadmap

| Phase | Scope | State |
|---|---|---|
| 0 | Tenancy foundation: OIDC auth, RBAC, Postgres row-level security, audit log | Done |
| 1 | Basic RAG with citations | Planned |
| 2 | Advanced RAG and evals | Planned |
| 3 | LLM gateway | Planned |
| 4 | Agents and MCP with human approval | Planned |
| 5 | NL-to-SQL | Planned |
| 6 | Security hardening | Planned |
| 7 | AWS deploy | Planned |

## Repository layout

```
services/api/     FastAPI service (Python 3.13, uv): see services/api/README.md
infra/compose/    Local Postgres (pgvector), Redis and Keycloak
apps/web/         Web app (Next.js, not started; image assets only)
docs/             Image prompt guide and generated images
```

## Quickstart

Requires Docker, [uv](https://docs.astral.sh/uv/) and pnpm.

```bash
pnpm dev:infra     # Postgres, Redis, Keycloak; waits until healthy
pnpm db:migrate    # apply migrations (owner role)
pnpm db:seed       # create the demo tenants
pnpm api:dev       # API on http://localhost:8000 (OpenAPI docs at /docs)
```

No `.env` is needed for local development. Copy `.env.example` to `.env` only to override defaults.

Get a token for a demo user and call the API:

```bash
TOKEN=$(curl -s -X POST http://localhost:8080/realms/atlas/protocol/openid-connect/token \
  -d grant_type=password -d client_id=atlas-web -d username=alice -d password=alice \
  | python3 -c 'import sys, json; print(json.load(sys.stdin)["access_token"])')

curl -s http://localhost:8000/v1/me -H "Authorization: Bearer $TOKEN"
```

| User | Password | Tenant | Role |
|---|---|---|---|
| alice | alice | Acme Financial | admin |
| bob | bob | Acme Financial | viewer |
| carol | carol | Globex Retail | owner |

The Keycloak admin console is at http://localhost:8080 (admin / admin). All of these credentials
are local-only; the API refuses default credentials in staging and production.

Other commands: `pnpm api:test`, `pnpm api:lint`, `pnpm dev:infra:down`.
