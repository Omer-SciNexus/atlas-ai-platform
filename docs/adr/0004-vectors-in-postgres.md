# 0004. Vectors live in Postgres (pgvector) behind a `VectorStore` interface

Status: accepted (2026-11-27)

## Context

Retrieval needs nearest-neighbour search over chunk embeddings. The choice is between a
dedicated vector database (Qdrant, Pinecone) and pgvector inside the Postgres we already run.

## Decision

Chunks and their embeddings are a normal table, `document_chunks`, with an HNSW index
(cosine distance). Code talks to it through the `VectorStore` protocol in
`app/modules/retrieval/store.py`.

Reasons:

- Tenant isolation is the same row-level security policy as every other table (0002). In a
  separate vector database, isolation would be a second mechanism to build, test and trust.
- A document's status and its chunks change in one transaction. There is no moment where
  search returns chunks of a deleted document, and no sync job between two stores.
- One system to run, back up and monitor.

One known problem is handled explicitly. The HNSW index returns the nearest vectors across
all tenants; row-level security then removes the rows of other tenants. A small tenant
could get fewer results than asked for, or none. Search therefore sets
`hnsw.iterative_scan = strict_order` (pgvector 0.8+), which makes the index keep scanning
until enough visible rows are found.

## Consequences

- Good up to millions of chunks. Past that, or if filtered search gets slow for small
  tenants, the options are per-tenant partitions or a dedicated store behind the same
  interface.
- The vector size is fixed by the column type; see 0006.
- Hybrid search (keywords plus vectors) can use Postgres full-text search in the same query.
  That is Phase 2.
