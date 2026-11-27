# 0006. One embedding size (1024), Voyage in production, a keyless embedder for development

Status: accepted (2026-11-27)

## Context

Claude has no embedding model, so embeddings come from another provider. The project must
also run and be tested on a laptop with no API keys. An HNSW index needs a fixed vector size.

## Decision

- `document_chunks.embedding` is `vector(1024)`. All embedders return 1024 numbers.
- Production uses Voyage AI (`voyage-3.5`, set by `ATLAS_EMBEDDING_MODEL`), called with
  `input_type` `document` for chunks and `query` for questions.
- Local development and tests use `HashEmbedder`: feature hashing over words and word pairs.
  It needs no key and no network, and is deterministic. It matches shared words, not meaning,
  so the service refuses to start with it in staging or production.
- The text that is embedded is the document title, the section heading and the chunk. The
  stored chunk content stays the exact source text. A chunk such as "It rose 12% over the
  prior year." means little alone; with its title and heading, its vector lands near the
  right questions.
- Each chunk row records the model that embedded it.

## Consequences

- Vectors from different models cannot be compared. Changing the model means re-ingesting
  every document; a different size also needs a migration. The recorded model name makes
  stale chunks easy to find.
- Search quality numbers measured with the hash embedder say nothing about production.
  Evaluation (Phase 2) must run with the real model.
- Chunk sizes are counted in characters (1600, with 200 overlap), not tokens. This is exact,
  needs no tokenizer, and stays far below the model's input limit.
