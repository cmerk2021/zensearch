# ADR-0005: SQLite support and optional Redis

**Status:** Accepted

## Context

Primary deployment target is homelab hardware, including Raspberry Pi. Every
hard service dependency raises the entry barrier and the RAM floor.

## Decision

1. **PostgreSQL is the recommended production database**; **SQLite
   (aiosqlite) is fully supported** for evaluation, dev, tests, and small
   single-user instances. The schema uses portable column types (`JSON`, not
   `JSONB`; string UUIDs; timezone-aware timestamps).
2. **Redis is optional.** `zen.core.cache` defines a `CacheBackend` protocol
   with `RedisCache` and `MemoryCache` (LRU + TTL) implementations selected by
   `ZEN_REDIS_URL` presence. Rate limiting, search caching, health tracking and
   the scheduler leader lock all go through this abstraction.

## Consequences

- `docker compose up` with the minimal file starts one app container + SQLite
  volume; the full file adds Postgres + Redis.
- MemoryCache is per-process: multi-replica deployments MUST configure Redis
  (documented in the scaling guide).
- No JSONB-specific queries; JSON filtering happens in Python where volume
  permits, with indexed scalar columns for hot paths.
