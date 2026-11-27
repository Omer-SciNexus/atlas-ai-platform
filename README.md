![Atlas](docs/assets/readme/atlas-hero-banner.png)

# Atlas

A multi-tenant enterprise AI knowledge and agent platform.

**Status:** the tenancy foundation and the document question-answering backend are built:
upload a document, and ask questions that are answered from it with citations. There is no
web app yet (`apps/web` holds only image assets), and the later phases below are not built.

## What works today

- **Tenant isolation in the database.** Postgres row-level security filters every query to
  the caller's tenant, including vector search. Application code has no tenant filters to
  forget.
- **Document ingestion.** Upload `.txt`, `.md`, `.html` or `.pdf`. A separate worker parses
  the file, splits it into overlapping chunks at sentence and heading boundaries, embeds
  them, and stores them in pgvector. Failures are retried; the status is visible per document.
- **Answers with citations.** `/v1/ask` retrieves the most relevant passages and has Claude
  answer only from them. Each statement comes back with the exact quote that supports it and
  its position in the source document. Answers stream as server-sent events.
- **Audit log.** Uploads, deletions, ingestion results and questions are recorded in an
  append-only table.

The design decisions are written down in [docs/adr](docs/adr/README.md).

## Roadmap

| Phase | Scope | State |
|---|---|---|
| 0 | Tenancy foundation: OIDC auth, RBAC, Postgres row-level security, audit log | Done |
| 1 | Basic RAG with citations: ingestion, vector search, grounded answers | Backend done; conversations and web app next |
| 2 | Advanced RAG (hybrid search, reranking) and evals | Planned |
| 3 | LLM gateway | Planned |
| 4 | Agents and MCP with human approval | Planned |
| 5 | NL-to-SQL | Planned |
| 6 | Security hardening | Planned |
| 7 | AWS deploy | Planned |

## Repository layout

```
services/api/     FastAPI service and ingestion worker (Python 3.13, uv): see services/api/README.md
infra/compose/    Local Postgres (pgvector), Redis and Keycloak
apps/web/         Web app (Next.js, not started; image assets only)
docs/adr/         Architecture decision records
docs/assets/      Images
```

## Quickstart

Requires Docker, [uv](https://docs.astral.sh/uv/) and pnpm.

```bash
pnpm dev:infra     # Postgres, Redis, Keycloak; waits until healthy
pnpm db:migrate    # apply migrations (owner role)
pnpm db:seed       # create the demo tenants
pnpm api:dev       # API on http://localhost:8000 (OpenAPI docs at /docs)
pnpm worker:dev    # ingestion worker, in a second terminal
```

No `.env` is needed to start. With no keys set:

- Search uses a simple word-matching embedder, good enough to try the flow.
- `/v1/ask` returns 503 until `ATLAS_ANTHROPIC_API_KEY` is set.

Copy `.env.example` to `.env` to set keys (`ATLAS_ANTHROPIC_API_KEY`, and
`ATLAS_EMBEDDING_PROVIDER=voyage` with `ATLAS_VOYAGE_API_KEY` for real embeddings).

Get a token for a demo user, upload a document and ask a question:

```bash
TOKEN=$(curl -s -X POST http://localhost:8080/realms/atlas/protocol/openid-connect/token \
  -d grant_type=password -d client_id=atlas-web -d username=alice -d password=alice \
  | python3 -c 'import sys, json; print(json.load(sys.stdin)["access_token"])')

curl -s http://localhost:8000/v1/me -H "Authorization: Bearer $TOKEN"

# Upload. The response has the document id and status "pending".
curl -s http://localhost:8000/v1/documents -H "Authorization: Bearer $TOKEN" -F file=@report.pdf

# List documents; wait until the status is "ready".
curl -s http://localhost:8000/v1/documents -H "Authorization: Bearer $TOKEN"

# The passages retrieval finds (no model call).
curl -s http://localhost:8000/v1/search -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"query": "net interest income"}'

# An answer with citations, streamed.
curl -N http://localhost:8000/v1/ask -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"question": "How did net interest income change?"}'
```

| User | Password | Tenant | Role |
|---|---|---|---|
| alice | alice | Acme Financial | admin |
| bob | bob | Acme Financial | viewer |
| carol | carol | Globex Retail | owner |

Carol cannot see or search Alice's documents: they are in different tenants.

The Keycloak admin console is at http://localhost:8080 (admin / admin). All of these credentials
are local-only; the API refuses default credentials in staging and production.

Other commands: `pnpm api:test`, `pnpm api:lint`, `pnpm dev:infra:down`.
