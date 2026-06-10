# Troubleshooting

## Startup

**`ZEN_SECRET_KEY is required in production`**
Set it in `.env`. Generate: `python -c "import secrets; print(secrets.token_urlsafe(48))"`.

**Container restarts repeatedly / unhealthy**
`docker compose logs zen-server` — common causes: wrong `ZEN_DATABASE_URL`,
PostgreSQL not ready (the full compose file gates on health checks; custom
setups should too), or a volume permission issue (`/data` must be writable by
uid 1000).

**Setup page never appears**
The setup page only shows while no admin exists. Create one manually:
`docker compose exec zen-server zen users create-admin`.

## Search

**A provider always fails**
Admin → Providers → *Test* shows the exact error.

- `circuit_open` in results: the breaker tripped after repeated failures;
  reset it in Admin → Providers after fixing the cause.
- Google/Bing/Startpage are scraped — upstream blocks (CAPTCHA, 429) appear
  as transient failures. Consider keys for Brave (free) for stable API
  access, and rely on multiple providers — that's the design.
- Kagi requires an API key; GitHub/Stack Overflow work without keys but at
  low rate limits.

**Searches are slow**
Check Admin → Overview latency figures. Slowest provider bounds total time —
lower per-provider `timeout_seconds` (e.g. 5s) so stragglers stop holding up
the response; results from finished providers are still merged.

**No suggestions appear**
Suggestions come from *your own* search history; they're disabled in privacy
mode and for anonymous users.

## Authentication

**OIDC redirect mismatch**
`ZEN_BASE_URL` must exactly match the public origin, and the IdP redirect URI
must be `<base>/api/v1/auth/oidc/callback`.

**OIDC state validation failed**
Clock skew or a stale login page (state cookie expires after 10 minutes).
Retry from a fresh page; verify the host clock.

**Locked out (lost admin password)**
`docker compose exec zen-server zen users set-password <username>`.

**429 Too Many Requests on login**
Auth is rate-limited (10 attempts / 5 min per IP). Wait, or adjust
`security.rate_limits` via CLI if you're behind CGNAT with many users.

## Behind a reverse proxy

**Login works on LAN but not through the proxy**
Cookies are `Secure` when `ZEN_BASE_URL` is https — the proxy must terminate
TLS and forward `X-Forwarded-Proto: https`. Also set `ZEN_TRUSTED_PROXIES`
to the proxy IP so client IPs (rate limiting, audit) are correct.

**Plugin upload fails with 413**
Raise the proxy body limit (64 MB examples are in `deploy/reverse-proxy/`).

## AI

**"AI backend unreachable" with Docker + host Ollama**
Use `http://host.docker.internal:11434`; on Linux add
`extra_hosts: ["host.docker.internal:host-gateway"]` to `zen-server`.

**Empty/garbled summaries**
Small models struggle with the structured prompts; try ≥7B models for
summaries and digests.

## Data

**Migrating SQLite → PostgreSQL**
1. Take a takeout export per user (Settings → Your data) as a safety net.
2. Stand up the full compose stack, run `zen db upgrade`.
3. Use `pgloader` (`pgloader sqlite:///data/zen.db postgresql://…`) or
   re-import the takeouts.

**Diagnostics one-liner**
`docker compose exec zen-server zen doctor`

Still stuck? Open a discussion with `zen doctor` output and relevant
`docker compose logs --tail 100 zen-server`.
