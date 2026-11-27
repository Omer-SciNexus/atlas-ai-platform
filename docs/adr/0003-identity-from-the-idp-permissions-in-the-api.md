# 0003. Identity and roles come from the identity provider; the API checks permissions

Status: accepted (2026-11-10)

## Context

Enterprise customers bring their own identity provider and expect single sign-on. Storing
passwords or issuing tokens in Atlas would add risk and work with no benefit.

## Decision

- Atlas accepts OIDC access tokens (Keycloak locally) and verifies them itself against the
  provider's cached signing keys: signature, issuer, audience, expiry. Only asymmetric
  algorithms are accepted.
- The token carries the tenant (`tenant_id` claim) and the role (`viewer` < `editor` <
  `admin` < `owner`). A user row is created on first use so other tables can reference it.
- Endpoints depend on a permission (`documents:write`), never on a role name. The mapping from
  roles to permissions is one table in `app/core/rbac.py`.
- If the signing keys cannot be loaded at all, the API answers 503, not 401: the caller's
  token may be valid, and clients should retry instead of logging the user out.

## Consequences

- No passwords or sessions in Atlas. Removing a user in the provider removes their access when
  their token expires (minutes).
- A role change takes effect on the next token, not instantly.
- The role matrix can change without touching any endpoint.
