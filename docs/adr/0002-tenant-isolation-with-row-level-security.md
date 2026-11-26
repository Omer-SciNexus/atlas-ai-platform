# 0002. Tenant isolation is enforced by Postgres row-level security

Status: accepted (2026-11-10)

## Context

Every tenant's data is in the same database. The usual approach, a `WHERE tenant_id = ...` in
every query, fails the first time one query forgets it. With retrieval and agents, queries
are also built in more places and some are generated, which makes a forgotten filter more
likely and its effect worse: one tenant's documents in another tenant's answer.

## Decision

- Every tenant-scoped table has a `tenant_id` column, `ENABLE` and `FORCE ROW LEVEL SECURITY`,
  and one policy: `tenant_id = app_current_tenant()`.
- Each request runs in one transaction that first calls
  `set_config('app.tenant_id', <id>, true)`. The `true` makes the value transaction-local, so
  it cannot leak to the next request that reuses the pooled connection.
- The API connects as `atlas_app`: not the table owner, `NOBYPASSRLS`. Migrations use the
  owner role `atlas`. The tenant id comes only from the verified token.
- Application code writes no tenant filters. A query without a bound tenant returns no rows.

## Consequences

- A missing filter cannot leak data; the database refuses. This is tested as the runtime role
  in `services/api/tests/integration/test_rls.py`.
- Every new table needs the policy and explicit grants in its migration, and a test.
- Work that spans tenants (the ingestion queue) needs a deliberate exception; see 0005.
- Vector search needs care, because the index does not know about tenants; see 0004.
- Queries pay a small cost for the policy check. Tables are indexed by `tenant_id`.
