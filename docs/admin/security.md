# Security guide

## Threat model

Zen is designed for deployment on trusted home/small-team networks, exposed
to the internet only behind a reverse proxy with TLS. The threat model
prioritizes: protection of stored credentials and API keys, session security,
abuse resistance (rate limiting), and supply-chain integrity for plugins.

## Built-in controls

| Control | Implementation |
|---|---|
| Password storage | argon2id (3 iterations, 64 MB, 2 lanes) |
| Sessions | Opaque 256-bit tokens, stored SHA-256-hashed, httpOnly + SameSite=Lax cookies, sliding expiry, server-side revocation |
| CSRF | Double-submit cookie + per-session server-side token comparison on all unsafe methods |
| Secrets at rest | Fernet (AES-128-CBC + HMAC) keyed from `ZEN_SECRET_KEY`; redacted in all read APIs |
| Rate limiting | Per-bucket fixed-window counters (auth 10/5min, search 60/min, API 600/min, AI 30/5min) — admin-tunable |
| Security headers | CSP (`default-src 'self'`), X-Frame-Options DENY, nosniff, referrer-policy, permissions-policy, optional HSTS |
| Input validation | Pydantic schemas on every route; URL canonicalization rejects non-http(s) schemes |
| SSRF protection | Favicon proxy resolves DNS and refuses private/reserved ranges; plugin downloads HTTPS-only |
| LDAP injection | Username character allowlist before DN templating |
| Open redirect | Bang targets come only from admin-defined templates |
| Zip-slip | Plugin archives are path-checked before extraction |
| Audit | Append-only log of security-relevant actions with actor + IP |
| SQL injection | SQLAlchemy parameterized queries throughout; no string SQL |
| XSS | React auto-escaping; no `dangerouslySetInnerHTML` with user content; strict CSP |

## Plugin security (read this)

**Installing a plugin executes third-party Python code with the full
privileges of the Zen process.** There is no sandbox — Python cannot be
safely sandboxed in-process, and we will not pretend otherwise
([ADR-0007](../architecture/decisions/0007-plugin-trust-model.md)).

Mitigations Zen provides:

- Only **administrators** can install plugins (`plugins.allow_install` can
  disable installation entirely).
- Repository catalogs pin **SHA-256 checksums**; installs verify them.
- Manifests declare **permissions**; undeclared capability use fails. This is
  a review aid, not a security boundary.
- Rollback to the previous version is one click.

Mitigations you should add for internet-exposed instances:

- Run containers with a read-only root filesystem and an egress firewall.
- Only install plugins whose source you have read or whose author you trust.

## Deployment hardening checklist

- [ ] `ZEN_SECRET_KEY` is long (48+ chars), random, and not in source control
- [ ] HTTPS terminated at a reverse proxy; `ZEN_BASE_URL` set to the https URL
- [ ] `ZEN_TRUSTED_PROXIES` lists only your proxy (otherwise XFF is ignored — good)
- [ ] Registration closed unless you want a public instance
- [ ] PostgreSQL not exposed beyond the compose network
- [ ] `/metrics` admin-gated (default) or firewalled
- [ ] Backups encrypted at rest wherever they're stored
- [ ] Containers run as non-root (default in official images)

## Security review summary (v0.9)

Reviewed before release:

1. **Auth flows** — constant-time credential comparison; identical errors for
   unknown user vs wrong password; login rate-limited by IP.
2. **Session lifecycle** — revocation works across devices; expiry enforced
   server-side; tokens never logged.
3. **OIDC** — PKCE (S256) + signed state cookie with 10-min expiry; tokens
   exchanged server-side only; client secret encrypted at rest.
4. **Egress** — the only outbound calls are: enabled search providers, the
   favicon fetcher (SSRF-guarded), configured AI backend, configured plugin
   repositories. **There is no telemetry of any kind.**
5. **Dependencies** — minimal, mainstream, pinned by major version; CI builds
   fail on known-vulnerable transitive pins at image build time.

## Reporting vulnerabilities

See [SECURITY.md](../../SECURITY.md) at the repository root.
