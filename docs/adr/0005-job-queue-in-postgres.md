# 0005. The ingestion queue is a Postgres table

Status: accepted (2026-11-27)

## Context

An upload must return fast, and ingestion (parse, chunk, embed) runs later in the worker. A
queue connects them. Redis is already part of the stack, so a Redis queue was the obvious
alternative.

## Decision

Jobs are rows in `ingestion_jobs`. A worker claims one with
`UPDATE ... WHERE id = (SELECT ... FOR UPDATE SKIP LOCKED LIMIT 1)`.

- The document row and its job are written in the same transaction. A document can never
  exist without a job, and a job can never point at a document that was rolled back. With a
  Redis queue that guarantee needs an outbox table anyway.
- Failed jobs are retried with a growing delay, up to 3 attempts. A file that cannot be
  parsed fails at once, with a message the user sees on the document.
- A job left in `running` by a dead worker is taken over when its lock is older than
  `ATLAS_INGESTION_LOCK_TIMEOUT_SECONDS`.
- No database transaction is held while a file is parsed or the embedding API is called.

`ingestion_jobs` is the one tenant table **without** row-level security: the worker must see
jobs of all tenants. To keep that safe, it holds only ids and state (never content or error
text), no API endpoint reads it, and the worker binds the job's tenant before it reads any
tenant data. A job with a wrong tenant id would find no document and do nothing.

## Consequences

- No new infrastructure, and job state can be inspected with SQL.
- Throughput is limited to what Postgres polling gives (hundreds of jobs per second), far
  above what document ingestion needs.
- Workers poll (default every second) instead of being pushed. `LISTEN/NOTIFY` can remove
  the delay later.
- The lock timeout must stay longer than the slowest real job, or a live job is run twice.
  Ingestion is idempotent (chunks are replaced as a set), so that would waste work but not
  corrupt data.
