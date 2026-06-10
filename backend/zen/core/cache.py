"""Cache abstraction: Redis when configured, in-memory LRU+TTL otherwise.

All transient state — search caches, rate-limit counters, circuit breaker
state, scheduler leadership, session lookups — goes through this interface so
single-container deployments need no Redis (ADR-0005).
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import OrderedDict
from typing import Any, Protocol

import structlog

log = structlog.get_logger(__name__)


class CacheBackend(Protocol):
    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, ttl: int | None = None) -> None: ...
    async def delete(self, *keys: str) -> None: ...
    async def incr(self, key: str, amount: int = 1, ttl: int | None = None) -> int: ...
    async def expire(self, key: str, ttl: int) -> None: ...
    async def acquire_lock(self, key: str, holder: str, ttl: int) -> bool: ...
    async def release_lock(self, key: str, holder: str) -> None: ...
    async def ping(self) -> bool: ...
    async def close(self) -> None: ...


class MemoryCache:
    """Process-local cache. Single-replica deployments only (documented)."""

    def __init__(self, max_entries: int = 8192) -> None:
        self._data: OrderedDict[str, tuple[str, float | None]] = OrderedDict()
        self._max = max_entries
        self._lock = asyncio.Lock()

    def _purge_expired(self) -> None:
        now = time.monotonic()
        dead = [k for k, (_, exp) in self._data.items() if exp is not None and exp <= now]
        for k in dead:
            self._data.pop(k, None)

    async def get(self, key: str) -> str | None:
        async with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            value, expires = entry
            if expires is not None and expires <= time.monotonic():
                self._data.pop(key, None)
                return None
            self._data.move_to_end(key)
            return value

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        async with self._lock:
            self._purge_expired()
            expires = time.monotonic() + ttl if ttl else None
            self._data[key] = (value, expires)
            self._data.move_to_end(key)
            while len(self._data) > self._max:
                self._data.popitem(last=False)

    async def delete(self, *keys: str) -> None:
        async with self._lock:
            for key in keys:
                self._data.pop(key, None)

    async def incr(self, key: str, amount: int = 1, ttl: int | None = None) -> int:
        async with self._lock:
            entry = self._data.get(key)
            now = time.monotonic()
            current = 0
            expires: float | None = None
            if entry is not None:
                value, expires = entry
                if expires is not None and expires <= now:
                    current, expires = 0, None
                else:
                    try:
                        current = int(value)
                    except ValueError:
                        current = 0
            current += amount
            if expires is None and ttl:
                expires = now + ttl
            self._data[key] = (str(current), expires)
            return current

    async def expire(self, key: str, ttl: int) -> None:
        async with self._lock:
            entry = self._data.get(key)
            if entry is not None:
                self._data[key] = (entry[0], time.monotonic() + ttl)

    async def acquire_lock(self, key: str, holder: str, ttl: int) -> bool:
        async with self._lock:
            entry = self._data.get(key)
            now = time.monotonic()
            if entry is not None:
                value, expires = entry
                if (expires is None or expires > now) and value != holder:
                    return False
            self._data[key] = (holder, now + ttl)
            return True

    async def release_lock(self, key: str, holder: str) -> None:
        async with self._lock:
            entry = self._data.get(key)
            if entry is not None and entry[0] == holder:
                self._data.pop(key, None)

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        self._data.clear()


class RedisCache:
    """Redis-backed cache for multi-replica and durable deployments."""

    def __init__(self, url: str) -> None:
        import redis.asyncio as aioredis

        self._redis = aioredis.from_url(url, decode_responses=True)

    async def get(self, key: str) -> str | None:
        return await self._redis.get(key)

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        await self._redis.set(key, value, ex=ttl)

    async def delete(self, *keys: str) -> None:
        if keys:
            await self._redis.delete(*keys)

    async def incr(self, key: str, amount: int = 1, ttl: int | None = None) -> int:
        value = await self._redis.incrby(key, amount)
        if ttl and value == amount:
            await self._redis.expire(key, ttl)
        return value

    async def expire(self, key: str, ttl: int) -> None:
        await self._redis.expire(key, ttl)

    async def acquire_lock(self, key: str, holder: str, ttl: int) -> bool:
        ok = await self._redis.set(key, holder, nx=True, ex=ttl)
        if ok:
            return True
        return (await self._redis.get(key)) == holder

    async def release_lock(self, key: str, holder: str) -> None:
        # Compare-and-delete; benign race acceptable for scheduler leadership.
        if (await self._redis.get(key)) == holder:
            await self._redis.delete(key)

    async def ping(self) -> bool:
        try:
            return bool(await self._redis.ping())
        except Exception:
            return False

    async def close(self) -> None:
        await self._redis.aclose()


_cache: CacheBackend | None = None


def build_cache(redis_url: str = "") -> CacheBackend:
    if redis_url:
        log.info("cache.backend", backend="redis")
        return RedisCache(redis_url)
    log.info("cache.backend", backend="memory")
    return MemoryCache()


def get_cache() -> CacheBackend:
    global _cache
    if _cache is None:
        from zen.core.config import get_settings

        _cache = build_cache(get_settings().redis_url)
    return _cache


def set_cache(cache: CacheBackend | None) -> None:
    """Install a specific cache backend (app startup / tests)."""
    global _cache
    _cache = cache


# --- JSON convenience --------------------------------------------------------


async def cache_get_json(key: str) -> Any | None:
    raw = await get_cache().get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


async def cache_set_json(key: str, value: Any, ttl: int | None = None) -> None:
    await get_cache().set(key, json.dumps(value, separators=(",", ":")), ttl)
