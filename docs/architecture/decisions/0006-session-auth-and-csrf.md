# ADR-0006: Cookie sessions + CSRF double-submit

**Status:** Accepted

## Context

Authentication options considered: stateless JWT in localStorage, JWT in
cookies, opaque server-side sessions.

## Decision

Opaque session tokens stored **hashed** (SHA-256) in the `user_sessions` table,
delivered via an `httpOnly`, `SameSite=Lax`, `Secure` (configurable for plain
HTTP LAN deployments) cookie. A companion non-httpOnly `zen_csrf` cookie holds
a per-session CSRF token; unsafe methods require the `X-CSRF-Token` header to
match the session's stored token (double-submit + server-side comparison).

## Rationale

- localStorage tokens are XSS-exfiltratable; httpOnly cookies are not.
- Opaque server sessions allow instant revocation ("log out everywhere"),
  session listing in user settings, and sliding expiry — all product features.
- Self-hosted instances are frequently served over plain HTTP on LANs;
  `ZEN_COOKIE_SECURE` therefore defaults to auto-detection with explicit
  override, and the docs push HTTPS via reverse proxy.

## Consequences

- Every authenticated request does a session lookup → mitigated with a
  short-TTL cache keyed by token hash.
- OIDC/LDAP logins converge into the same session mechanism after identity
  assertion; only the verification step differs.
