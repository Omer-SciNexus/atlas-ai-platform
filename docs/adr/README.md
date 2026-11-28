# Architecture decision records

Each record states one decision: the situation, what was chosen, and what it costs.
A record is not edited after it is accepted; a later record replaces it.

| # | Decision | Status |
|---|---|---|
| [0001](0001-modular-monolith-and-worker.md) | One API service with feature modules, plus a separate ingestion worker | Accepted |
| [0002](0002-tenant-isolation-with-row-level-security.md) | Tenant isolation is enforced by Postgres row-level security | Accepted |
| [0003](0003-identity-from-the-idp-permissions-in-the-api.md) | Identity and roles come from the identity provider; the API checks permissions | Accepted |
| [0004](0004-vectors-in-postgres.md) | Vectors live in Postgres (pgvector) behind a `VectorStore` interface | Accepted |
| [0005](0005-job-queue-in-postgres.md) | The ingestion queue is a Postgres table | Accepted |
| [0006](0006-embedding-model-and-fixed-dimensions.md) | One embedding size (1024), Voyage in production, a keyless embedder for development | Accepted |
| [0007](0007-citations-from-the-model-api.md) | Citations come from the Claude citations feature, not from parsing the answer | Accepted |
| [0008](0008-web-app-signs-in-from-the-browser.md) | The web app signs in from the browser (PKCE) and calls the API directly | Accepted |
