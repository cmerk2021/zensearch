"""Provider health tracking and circuit breaking (ADR-0009).

State is stored in the cache backend so it is shared across workers (Redis)
and survives within a process otherwise. The admin dashboard reads this state
via the providers health endpoint.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field

from zen.core.cache import get_cache

FAILURE_THRESHOLD = 5
OPEN_SECONDS = 300
HALF_OPEN_PROBE_INTERVAL = 60
STATE_TTL = 7 * 24 * 3600


@dataclass(slots=True)
class ProviderHealth:
    slug: str
    consecutive_failures: int = 0
    open_until: float = 0.0
    last_probe_at: float = 0.0
    total_ok: int = 0
    total_fail: int = 0
    latency_ms_avg: float = 0.0
    last_error: str = ""
    last_ok_at: float = 0.0
    recent: list = field(default_factory=list)
    """Sliding window of the last 50 outcomes (1=ok, 0=fail)."""

    @property
    def state(self) -> str:
        now = time.time()
        if self.open_until > now:
            return "open"
        if self.consecutive_failures >= FAILURE_THRESHOLD:
            return "half-open"
        return "closed"

    @property
    def success_rate(self) -> float:
        if not self.recent:
            return 1.0
        return sum(self.recent) / len(self.recent)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["state"] = self.state
        data["success_rate"] = round(self.success_rate, 4)
        return data


def _key(slug: str) -> str:
    return f"provider:health:{slug}"


async def get_health(slug: str) -> ProviderHealth:
    raw = await get_cache().get(_key(slug))
    if raw:
        try:
            data = json.loads(raw)
            data.pop("state", None)
            data.pop("success_rate", None)
            return ProviderHealth(**data)
        except (ValueError, TypeError):
            pass
    return ProviderHealth(slug=slug)


async def _save(health: ProviderHealth) -> None:
    await get_cache().set(_key(health.slug), json.dumps(asdict(health)), ttl=STATE_TTL)


async def is_available(slug: str) -> tuple[bool, str | None]:
    """Whether the circuit allows a call. Returns (allowed, reason_if_not)."""
    health = await get_health(slug)
    now = time.time()
    if health.open_until > now:
        return False, "circuit_open"
    if health.consecutive_failures >= FAILURE_THRESHOLD:
        # Half-open: allow one probe per interval.
        if now - health.last_probe_at < HALF_OPEN_PROBE_INTERVAL:
            return False, "circuit_half_open"
        health.last_probe_at = now
        await _save(health)
    return True, None


async def record_success(slug: str, latency_ms: int) -> None:
    health = await get_health(slug)
    health.consecutive_failures = 0
    health.open_until = 0.0
    health.total_ok += 1
    health.last_ok_at = time.time()
    health.last_error = ""
    n = min(health.total_ok, 100)
    health.latency_ms_avg = health.latency_ms_avg + (latency_ms - health.latency_ms_avg) / n
    health.recent = ([*health.recent, 1])[-50:]
    await _save(health)


async def record_failure(slug: str, error: str) -> None:
    health = await get_health(slug)
    health.consecutive_failures += 1
    health.total_fail += 1
    health.last_error = error[:300]
    health.recent = ([*health.recent, 0])[-50:]
    if health.consecutive_failures >= FAILURE_THRESHOLD:
        health.open_until = time.time() + OPEN_SECONDS
    await _save(health)


async def reset_health(slug: str) -> None:
    await get_cache().delete(_key(slug))


async def all_health(slugs: list[str]) -> dict[str, dict]:
    return {slug: (await get_health(slug)).to_dict() for slug in slugs}
