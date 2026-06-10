# ADR-0009: Provider resilience model

**Status:** Accepted

## Context

Upstream engines block scrapers, change markup, rate-limit, and degrade —
constantly. SearXNG's experience shows silent engine breakage is the #1
operational pain. Provider failure must be a designed-for state.

## Decision

Every provider call goes through a resilience envelope:

1. **Timeout** — per-provider, configurable, default 8s.
2. **Retry** — one retry on transient failure (connect/5xx) with jittered
   backoff, only if budget remains.
3. **Circuit breaker** — consecutive-failure threshold opens the circuit for a
   cooldown; half-open probes restore it. State lives in the cache backend so
   it survives restarts (Redis) and is visible to all workers.
4. **Health tracking** — rolling success rate + latency stored per provider,
   surfaced on the admin dashboard and `/api/v1/admin/providers/health`.
5. **Graceful degradation** — `asyncio.gather` semantics: a search succeeds
   with whatever subset responded inside the deadline; failed providers are
   reported in the response's `providers` block so the UI can show partial
   coverage honestly.

## Consequences

- A dead Google scraper degrades Zen to the remaining providers instead of
  breaking search.
- The scheduler runs lightweight synthetic probes so admins learn about
  breakage before users do.
