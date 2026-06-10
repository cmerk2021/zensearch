"""Sliding-window rate limiting on top of the cache abstraction."""

from __future__ import annotations

from dataclasses import dataclass

from zen.core.cache import get_cache
from zen.core.exceptions import RateLimitedError


@dataclass(frozen=True, slots=True)
class RateLimit:
    """``limit`` requests per ``window`` seconds."""

    limit: int
    window: int

    @classmethod
    def parse(cls, spec: str) -> RateLimit:
        """Parse ``"30/60"`` → 30 requests per 60 seconds."""
        limit_s, _, window_s = spec.partition("/")
        return cls(limit=int(limit_s), window=int(window_s or "60"))


# Defaults; instance settings may override (security.rate_limits).
DEFAULT_LIMITS: dict[str, RateLimit] = {
    "auth": RateLimit(10, 300),
    "search": RateLimit(60, 60),
    "api": RateLimit(600, 60),
    "ai": RateLimit(30, 300),
}


async def check_rate_limit(bucket: str, identity: str, limit: RateLimit) -> None:
    """Raise :class:`RateLimitedError` when ``identity`` exceeds ``limit``.

    Fixed-window counting with per-window keys: cheap (one INCR), accurate
    enough for abuse protection, and identical semantics on Redis and memory.
    """
    import time

    window_id = int(time.time()) // limit.window
    key = f"rl:{bucket}:{identity}:{window_id}"
    count = await get_cache().incr(key, ttl=limit.window * 2)
    if count > limit.limit:
        retry_after = limit.window - (int(time.time()) % limit.window)
        raise RateLimitedError(
            f"Rate limit exceeded for {bucket}.", retry_after=max(retry_after, 1)
        )
