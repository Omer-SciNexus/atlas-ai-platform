# 0001. One API service with feature modules, plus a separate ingestion worker

Status: accepted (2026-11-10)

## Context

Atlas will have many features: identity, documents, retrieval, an LLM gateway, agents,
NL-to-SQL. One developer builds it. Two kinds of work have very different shapes: API requests
must answer in milliseconds to seconds, while ingesting a 300-page PDF takes minutes of CPU and
many embedding calls.

## Decision

- One FastAPI service. Each feature is a module under `app/modules/<name>` with its own models,
  service and router. Modules call each other through service functions, not through HTTP.
- One separate process, the ingestion worker (`python -m app.worker`), built from the same
  code and image. It shares the database and the blob store with the API.

## Consequences

- One deploy unit, one database transaction across features, and no network calls between
  features. Refactoring across modules is a normal code change.
- Heavy ingestion cannot slow down chat requests, and the worker scales on its own.
- A module can be moved into its own service later, because the boundary (its service
  functions) is already there. Until a real need shows up, that cost is not paid.
- Discipline is needed to keep modules from reading each other's tables directly.
