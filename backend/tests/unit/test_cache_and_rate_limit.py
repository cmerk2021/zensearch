"""Unit tests for the cache abstraction and rate limiter."""

import asyncio

import pytest

from zen.core.cache import MemoryCache, set_cache
from zen.core.exceptions import RateLimitedError
from zen.core.rate_limit import RateLimit, check_rate_limit


@pytest.fixture
def memory_cache():
    cache = MemoryCache(max_entries=100)
    set_cache(cache)
    yield cache
    set_cache(None)


async def test_get_set_delete(memory_cache):
    await memory_cache.set("k", "v")
    assert await memory_cache.get("k") == "v"
    await memory_cache.delete("k")
    assert await memory_cache.get("k") is None


async def test_ttl_expiry(memory_cache, monkeypatch):
    await memory_cache.set("k", "v", ttl=1)
    assert await memory_cache.get("k") == "v"
    # Fake the clock instead of sleeping.
    import time

    real = time.monotonic
    monkeypatch.setattr(time, "monotonic", lambda: real() + 2)
    assert await memory_cache.get("k") is None


async def test_lru_eviction():
    cache = MemoryCache(max_entries=3)
    for i in range(5):
        await cache.set(f"k{i}", str(i))
    assert await cache.get("k0") is None
    assert await cache.get("k4") == "4"


async def test_incr(memory_cache):
    assert await memory_cache.incr("counter") == 1
    assert await memory_cache.incr("counter") == 2
    assert await memory_cache.incr("counter", amount=5) == 7


async def test_locks(memory_cache):
    assert await memory_cache.acquire_lock("lock", "holder-a", ttl=30)
    assert not await memory_cache.acquire_lock("lock", "holder-b", ttl=30)
    # Re-entrant for the same holder.
    assert await memory_cache.acquire_lock("lock", "holder-a", ttl=30)
    await memory_cache.release_lock("lock", "holder-b")  # not the owner → no-op
    assert not await memory_cache.acquire_lock("lock", "holder-b", ttl=30)
    await memory_cache.release_lock("lock", "holder-a")
    assert await memory_cache.acquire_lock("lock", "holder-b", ttl=30)


async def test_concurrent_incr(memory_cache):
    await asyncio.gather(*(memory_cache.incr("n") for _ in range(50)))
    assert await memory_cache.get("n") == "50"


def test_rate_limit_parse():
    limit = RateLimit.parse("30/60")
    assert limit.limit == 30 and limit.window == 60
    assert RateLimit.parse("10").window == 60


async def test_rate_limit_enforcement(memory_cache):
    limit = RateLimit(limit=3, window=60)
    for _ in range(3):
        await check_rate_limit("test", "1.2.3.4", limit)
    with pytest.raises(RateLimitedError) as exc_info:
        await check_rate_limit("test", "1.2.3.4", limit)
    assert exc_info.value.retry_after >= 1
    # Different identity unaffected.
    await check_rate_limit("test", "5.6.7.8", limit)
