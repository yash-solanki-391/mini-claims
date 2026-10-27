# ADR 003: Signed Demo JWT for Local/Test Authentication

## Status
Accepted (learning project only)

## Context
The first demo adapter read tenant, user and permissions from `X-Demo-*` headers. Any caller could
assert any identity or permission, so permission checks proved nothing beyond wiring.

The AtlasIQ standard (`docs/atlasiq_python_standards (1).md`, Security) says:
"only the shared auth library (Entra ID staff, email OTP external). No custom token handling."
Entra ID / OTP are explicit non-goals of this project (CLAUDE.md, Scope), and the shared library is not available here.

## Decision
Replace the header adapter with a signed demo token, accepted only when `APP_ENV` is `local` or `test`:

- `Authorization: Bearer <JWT>`, HS256, key from `DEMO_JWT_SECRET` (env / `.env`, never committed, min 32 chars).
- Verified: signature, `exp`, `iss` (`mini-claims-demo-issuer`), `aud` (`mini-claims-api`); `exp`, `iat`, `iss`, `aud`, `sub`
  required; algorithm pinned so `alg: none` and algorithm switching are rejected.
- Identity from signed claims only: `tid` -> tenant, `sub` -> user (safe charset, max 64).
- Token carries **roles**; the server maps roles to permissions (`ROLE_PERMISSIONS` in `app/core/demo_auth.py`).
  Unknown roles and any `permissions` claim grant nothing.
- Every failure returns the same 403; the reason is logged as an exception type only, never the token.
- Tokens are minted by a local CLI (`python -m services.claims.app.core.demo_auth`), not an endpoint; it also refuses outside local/test.
- New dependency: `pyjwt`.

This is a **deliberate, documented deviation** from "no custom token handling", allowed only because this is a
synthetic-data learning project. It is NOT production authentication.

## Consequences
- Permission and tenant checks are now exercised with identities the caller cannot forge without the key.
- `RequestContext` and `require_permission(...)` are unchanged; moving to the shared auth library replaces only
  `get_request_context` and `app/core/demo_auth.py`.
- Anyone holding `DEMO_JWT_SECRET` can mint any identity; acceptable for local/test, never for shared environments.
- No key rotation, revocation or refresh; tokens expire (default 60 min).
- In the real AtlasIQ repo, delete this module and use the shared auth library.
