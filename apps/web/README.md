# Atlas web

The web app for Atlas. Next.js (App Router), React, TypeScript and Tailwind CSS.
To run it with the API and its dependencies, see the quickstart in the [root README](../../README.md).

## Pages

| Path | Needs | Purpose |
|---|---|---|
| `/ask` | `documents:read` | Ask a question; the answer streams in with a numbered citation after each statement. Selecting a citation opens the passage with the quote highlighted. |
| `/documents` | `documents:read` | The organization's documents and their ingestion status. Upload and delete need `documents:write`. |
| `/search` | `documents:read` | The passages retrieval finds for a query, with no model call. |
| `/audit` | `audit:read` | The audit log, newest first. |
| `/auth/callback` | none | Finishes sign-in. |

The app hides what a role cannot do (a viewer sees no upload area and no audit link). That is
for convenience only: the API checks the permission on every request.

## How it works

- **Sign-in runs in the browser.** The app is a public OpenID Connect client: authorization
  code flow with PKCE, no client secret. Tokens are kept in `sessionStorage` and sent straight
  to the API; the Next.js server never sees them. The reasons are in
  [ADR 0008](../../docs/adr/0008-web-app-signs-in-from-the-browser.md).
- **Answers are read from a `fetch` stream.** `/v1/ask` is a POST with an Authorization header,
  which the browser's `EventSource` cannot send, so `src/lib/api/sse.ts` parses the
  server-sent events itself.
- **An answer is a list of segments,** each with the quotes that support it. The page renders
  the citation numbers from that structure; it never parses markers out of the answer text.
- **The thread lives in memory.** The API does not store conversations yet, so the thread is
  kept above the pages (it survives moving between pages, and an answer keeps streaming) and
  is gone after a reload. Each question is answered on its own.
- **Server data goes through TanStack Query.** The document list polls every two seconds while
  a document is being ingested, and stops when all are ready or failed.
- **Light and dark themes** come from CSS variables switched by a class on `<html>`.

## Layout

```
src/app/              routes: (app)/ needs sign-in; auth/callback finishes it
src/components/       shell, sign-in screen, shared UI
src/features/ask/     thread state (thread.ts), composer, answer, sources panel
src/features/documents/  upload area, document list
src/features/search/  passage search
src/features/audit/   audit log
src/lib/api/          API client, types, SSE parser, query hooks
src/lib/auth/         OpenID Connect sign-in
public/images/        illustrations
```

## Development

```bash
pnpm install          # from the repository root
pnpm web:dev          # http://localhost:3000
pnpm web:test         # unit tests (Vitest)
pnpm web:lint         # ESLint and the TypeScript check
pnpm web:build        # production build
```

## Configuration

All settings are public (they are compiled into the browser bundle) and have local defaults.
Copy `.env.example` to `.env.local` to change them.

| Setting | Default | Meaning |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | The Atlas API |
| `NEXT_PUBLIC_OIDC_AUTHORITY` | `http://localhost:8080/realms/atlas` | The identity provider's issuer URL |
| `NEXT_PUBLIC_OIDC_CLIENT_ID` | `atlas-web` | The public client registered for this app |

The API must list this app's origin in `ATLAS_CORS_ORIGINS`, and the identity provider must
allow `<origin>/auth/callback` as a redirect URI.
