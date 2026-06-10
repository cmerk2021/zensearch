# ADR-0002: Technology stack

**Status:** Accepted

## Decision

| Layer | Choice | Rationale |
|---|---|---|
| Backend | Python 3.11+ / FastAPI | Async-native, mature ecosystem for HTTP scraping/parsing, typed with Pydantic v2, easiest contribution surface for the homelab community. |
| ORM | SQLAlchemy 2.0 (async) + Alembic | Portable across PostgreSQL and SQLite; first-class async; migrations. |
| Frontend | Next.js (App Router) + TypeScript + TailwindCSS | Server-rendered first paint under 1s on LAN, standalone output for slim Docker images, shadcn-style component system. |
| Database | PostgreSQL 16 (SQLite supported) | See [ADR-0005](0005-sqlite-and-optional-redis.md). |
| Cache | Redis 7 (optional) | See [ADR-0005](0005-sqlite-and-optional-redis.md). |
| HTTP client | httpx | Async, HTTP/2, per-request timeouts, mockable via respx. |
| HTML parsing | selectolax | 10–30x faster than BeautifulSoup; matters on Pi-class hardware. |
| Background work | In-process asyncio scheduler | See [ADR-0004](0004-in-process-scheduler.md). |
| Passwords | argon2id | Current OWASP recommendation. |
| Metrics | prometheus-client | Homelab standard (Prometheus/Grafana). |

## Deviation from the brief

The brief suggested Celery. We deviate ([ADR-0004](0004-in-process-scheduler.md))
because Celery requires a separate worker container + broker, which conflicts
with the Pi-class footprint requirement. The task interface is abstracted so an
external queue can be reintroduced without touching call sites.
