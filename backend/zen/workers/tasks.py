"""Periodic maintenance tasks executed by the scheduler."""

from __future__ import annotations

import structlog
from sqlalchemy import func, select

from zen.db.base import get_session_factory
from zen.observability import metrics

log = structlog.get_logger(__name__)


async def purge_expired_sessions() -> None:
    from zen.services.auth import AuthService

    factory = get_session_factory()
    async with factory() as db:
        removed = await AuthService(db).purge_expired_sessions()
        if removed:
            log.info("task.sessions_purged", removed=removed)


async def enforce_history_retention() -> None:
    from zen.services.history import HistoryService

    factory = get_session_factory()
    async with factory() as db:
        removed = await HistoryService(db).enforce_retention()
        if removed:
            log.info("task.history_retention_enforced", removed=removed)


async def probe_provider_health() -> None:
    """Synthetic probes so admins learn about provider breakage early.

    Probes only providers that are enabled and currently degraded or stale —
    healthy providers are validated by organic traffic.
    """
    import time

    from zen.core.config import get_settings
    from zen.core.security import decrypt_secret
    from zen.db.models import ProviderConfig
    from zen.search import health as provider_health
    from zen.search.http import build_search_client
    from zen.search.providers import all_providers

    factory = get_session_factory()
    async with factory() as db:
        configs = {
            row.slug: row
            for row in (await db.execute(select(ProviderConfig))).scalars().all()
        }
    secret_key = get_settings().secret_key
    registry = all_providers()
    to_probe: list[str] = []
    now = time.time()
    for slug, cls in registry.items():
        config = configs.get(slug)
        if config is not None and not config.enabled:
            continue
        if cls.requires_api_key and not (config and config.api_key_encrypted):
            continue
        health = await provider_health.get_health(slug)
        stale = (now - health.last_ok_at) > 6 * 3600
        degraded = health.consecutive_failures > 0
        if stale or degraded:
            to_probe.append(slug)
    if not to_probe:
        return
    async with build_search_client() as client:
        for slug in to_probe[:4]:  # bounded per cycle to stay polite upstream
            cls = registry[slug]
            config = configs.get(slug)
            api_key = ""
            if config and config.api_key_encrypted:
                try:
                    api_key = decrypt_secret(config.api_key_encrypted, secret_key)
                except ValueError:
                    continue
            provider = cls(config=config.config if config else {}, api_key=api_key)
            started = time.perf_counter()
            try:
                await provider.search(provider.probe_query(), client)
                await provider_health.record_success(
                    slug, int((time.perf_counter() - started) * 1000)
                )
            except Exception as exc:
                await provider_health.record_failure(slug, f"probe: {exc}")
    log.info("task.providers_probed", providers=to_probe[:4])


async def sync_plugin_repositories() -> None:
    from zen.plugins.repository import RepositoryService

    factory = get_session_factory()
    async with factory() as db:
        synced = await RepositoryService(db).sync_all_enabled()
        if synced:
            log.info("task.repositories_synced", count=synced)


async def refresh_session_metrics() -> None:
    from zen.db.base import utcnow
    from zen.db.models import UserSession

    factory = get_session_factory()
    async with factory() as db:
        count = (
            await db.execute(
                select(func.count())
                .select_from(UserSession)
                .where(
                    UserSession.revoked_at.is_(None),
                    UserSession.expires_at > utcnow(),
                )
            )
        ).scalar_one()
        metrics.ACTIVE_SESSIONS.set(count)


def register_default_tasks(scheduler) -> None:
    scheduler.register(
        "purge_sessions", purge_expired_sessions, interval_seconds=3600, jitter_seconds=60
    )
    scheduler.register(
        "history_retention",
        enforce_history_retention,
        interval_seconds=6 * 3600,
        jitter_seconds=300,
    )
    scheduler.register(
        "provider_probes", probe_provider_health, interval_seconds=900, jitter_seconds=120
    )
    scheduler.register(
        "repo_sync", sync_plugin_repositories, interval_seconds=12 * 3600, jitter_seconds=600
    )
    scheduler.register(
        "session_metrics", refresh_session_metrics, interval_seconds=300, jitter_seconds=30
    )
