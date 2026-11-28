# 0008. The web app signs in from the browser and calls the API directly

Status: accepted (2026-11-28)

## Context

The web app needs an access token for the API (ADR 0003). There are two usual designs.
In the first, the browser runs the sign-in itself and holds the tokens. In the second, a
server in front of the API (a backend-for-frontend) runs the sign-in, keeps the tokens, and
gives the browser a session cookie.

Answers are streamed, uploads can be 25 MB, and every request is already authorized and
tenant-scoped by the API.

## Decision

- The web app is a public OpenID Connect client. It uses the authorization code flow with
  PKCE and has no client secret.
- Tokens are kept in `sessionStorage`: they survive a reload and are gone when the tab closes.
  The access token lives 15 minutes and is renewed with the refresh token.
- The browser calls the API directly with the access token. The API allows the app's origin
  through CORS. The Next.js server never sees a token and holds no session.
- After sign-in the app returns only to a path inside itself.
- The app shows or hides controls from the permissions `/v1/me` returns. This is for
  convenience; the API enforces every permission.

## Consequences

- One hop from browser to API: streaming and uploads need no proxy, and the web app can be
  served as static files.
- A script injected into the page could read the tokens. The exposure is limited by the short
  token lifetime and by the app rendering all document and model text as plain text, never as
  HTML. A content security policy is part of Phase 6.
- If that risk is not acceptable for a deployment, the replacement is a backend-for-frontend
  with an `HttpOnly` cookie. Sign-in is behind `src/lib/auth` and API calls behind
  `src/lib/api/client.ts`, so the change stays in those two places.
- Signing out ends the identity provider session, but an access token already issued stays
  valid until it expires.
