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

## How a document becomes an answer

```
POST /v1/documents     store the file, create the document row and an ingestion job
                       (one transaction), return 201 with status "pending"
  -> worker            claim the job (FOR UPDATE SKIP LOCKED)
       parse           .txt / .md / .html / .pdf -> text blocks with heading and page
       chunk           about 1600 characters, cut at sentence ends, 200 overlap, new chunk per heading
       embed           title + heading + chunk -> 1024-dimension vector
       store           replace the document's chunks in pgvector, status "ready"

POST /v1/ask           embed the question -> nearest chunks (cosine, HNSW, filtered by RLS)
  -> Claude            each chunk is a citable document; the model answers only from them
  -> response          answer segments, each with the quotes that support it
```

- **The worker is a separate process** (`uv run python -m app.worker`), so parsing a large
  PDF never slows down a request. Jobs are retried with a growing delay; a job left by a dead
  worker is taken over after a timeout. A file that cannot be parsed fails at once with a
  message on the document.
- **Citations come from the model API**, not from markers in the text: each cited statement
  carries the exact quote and its position in the source document.
- **No sources, no model call.** If retrieval finds nothing, the answer says so.
- **Every external part has an interface** with a keyless stand-in for tests: `Embedder`
  (Voyage / hash), `AnswerGenerator` (Claude / scripted), `BlobStore` (local disk, S3 later),
  `VectorStore` (pgvector).

The reasons behind these choices are in [docs/adr](../../docs/adr/README.md).

## Layout

```
app/core/        config, db, auth (security, deps, rbac), errors, logging, middleware
app/modules/     feature modules:
  tenants/       users and tenants (/v1/me)
  audit/         append-only audit log
  documents/     upload, list, delete; blob storage; document, chunk and job tables
  ingestion/     parsers, chunker, the job pipeline
  retrieval/     vector store (pgvector)
  llm/           embedding and answer providers
  rag/           search and ask endpoints
  health/        liveness and readiness
app/worker.py    ingestion worker entry point
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
| GET | `/v1/audit-events` | `audit:read` | Audit events for the caller's tenant, newest first (`before` pages back) |
| POST | `/v1/documents` | `documents:write` | Upload a file (multipart `file`, optional `title`); 200 if the same file exists |
| GET | `/v1/documents` | `documents:read` | List documents, newest first (`limit`, `cursor`) |
| GET | `/v1/documents/{id}` | `documents:read` | One document with its ingestion status |
| DELETE | `/v1/documents/{id}` | `documents:write` | Delete a document, its chunks and its file |
| POST | `/v1/search` | `documents:read` | The passages most similar to a query (no model call) |
| POST | `/v1/ask` | `documents:read` | An answer with citations; server-sent events, or JSON with `"stream": false` |

`/v1/ask` events: `sources` (retrieved passages), `delta` (answer text for a segment),
`citation` (a quote supporting a segment), `done` (model and token usage), and `error` if the
model fails after the stream has started.

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
the service refuses to start with default database credentials, non-JSON logs, symmetric JWT
algorithms, or the keyless hash embedder.

| Setting | Default | Meaning |
|---|---|---|
| `ATLAS_EMBEDDING_PROVIDER` | `hash` | `hash` (keyless, word matching, local only) or `voyage` |
| `ATLAS_VOYAGE_API_KEY` | none | Required for `voyage` |
| `ATLAS_ANTHROPIC_API_KEY` | none | Without it, `/v1/ask` returns 503 |
| `ATLAS_CHAT_MODEL` | `claude-opus-5-5` | Model that writes answers |
| `ATLAS_RETRIEVAL_TOP_K` | `8` | Passages given to the model |
| `ATLAS_BLOB_DIR` | `data/blobs` | Uploaded files; the API and the worker must share it |

Changing the embedding provider or model means ingesting every document again.

## Container image

```bash
docker build -t atlas-api services/api
docker run --env-file .env atlas-api alembic upgrade head   # migrations, as the owner role
docker run --env-file .env -p 8000:8000 -v atlas-blobs:/data/blobs atlas-api
docker run --env-file .env -v atlas-blobs:/data/blobs atlas-api python -m app.worker
```

The API and the worker are the same image with a different command. They share the blob
volume until the S3 blob store exists.
