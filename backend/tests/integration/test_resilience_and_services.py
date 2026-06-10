"""Integration tests: circuit breaker, settings layering, scheduler, AI service."""

import httpx
import pytest
import respx

from zen.search import health as provider_health


async def test_circuit_breaker_opens_and_recovers(app):
    slug = "cb-test-provider"
    await provider_health.reset_health(slug)

    ok, _ = await provider_health.is_available(slug)
    assert ok

    for i in range(provider_health.FAILURE_THRESHOLD):
        await provider_health.record_failure(slug, f"error {i}")

    health = await provider_health.get_health(slug)
    assert health.state == "open"
    ok, reason = await provider_health.is_available(slug)
    assert not ok
    assert reason == "circuit_open"

    # Success closes the circuit.
    await provider_health.record_success(slug, 120)
    health = await provider_health.get_health(slug)
    assert health.state == "closed"
    ok, _ = await provider_health.is_available(slug)
    assert ok


async def test_health_tracks_rolling_stats(app):
    slug = "stats-provider"
    await provider_health.reset_health(slug)
    for _ in range(8):
        await provider_health.record_success(slug, 100)
    for _ in range(2):
        await provider_health.record_failure(slug, "x")
    health = await provider_health.get_health(slug)
    assert health.total_ok == 8
    assert health.total_fail == 2
    assert health.success_rate == pytest.approx(0.8)


async def test_settings_layering_and_invalidation(app, db_session):
    from zen.services.settings import SettingsService

    service = SettingsService(db_session)
    # Default
    assert await service.get("instance.name") == "Zen"
    # Override
    await service.set("instance.name", "Lab Zen")
    SettingsService.invalidate_local()
    assert await service.get("instance.name") == "Lab Zen"
    # Reset returns to default
    await service.reset("instance.name")
    SettingsService.invalidate_local()
    assert await service.get("instance.name") == "Zen"


async def test_settings_secret_encryption(app, db_session):
    from sqlalchemy import select

    from zen.db.models import InstanceSetting
    from zen.services.settings import SettingsService

    service = SettingsService(db_session)
    await service.set("ai.api_key", "sk-test-secret")
    row = (
        await db_session.execute(
            select(InstanceSetting).where(InstanceSetting.key == "ai.api_key")
        )
    ).scalar_one()
    assert "sk-test-secret" not in str(row.value)
    SettingsService.invalidate_local()
    assert await service.get("ai.api_key") == "sk-test-secret"


async def test_scheduler_runs_tasks_and_isolates_failures(app):
    import asyncio
    import time

    from zen.workers.scheduler import Scheduler

    runs = {"good": 0, "bad": 0}

    async def good_task():
        runs["good"] += 1

    async def bad_task():
        runs["bad"] += 1
        raise RuntimeError("intentional")

    scheduler = Scheduler()
    scheduler.register("good", good_task, interval_seconds=0.05, jitter_seconds=0.01, run_at_start=True)
    scheduler.register("bad", bad_task, interval_seconds=0.05, jitter_seconds=0.01, run_at_start=True)
    await scheduler.start()
    try:
        # Poll instead of a fixed sleep: CI runners are slow and exception
        # logging is expensive, so a wall-clock window flakes. The deadline is
        # generous; the happy path exits in well under a second.
        deadline = time.monotonic() + 15.0
        while time.monotonic() < deadline and not (runs["good"] >= 2 and runs["bad"] >= 2):
            await asyncio.sleep(0.05)
    finally:
        await scheduler.stop()

    assert runs["good"] >= 2, "good task should run repeatedly"
    assert runs["bad"] >= 2, "failing task must not kill its loop"


async def test_history_retention(app, db_session):
    from datetime import timedelta

    from zen.db.base import utcnow
    from zen.db.models import SearchHistory
    from zen.services.auth import AuthService
    from zen.services.history import HistoryService
    from zen.services.settings import SettingsService

    user = await AuthService(db_session).create_user(
        username="retention", password="long-enough-pw-123", role="user"
    )
    old = SearchHistory(user_id=user.id, query="old", created_at=utcnow() - timedelta(days=400))
    new = SearchHistory(user_id=user.id, query="new")
    db_session.add_all([old, new])
    await db_session.commit()

    await SettingsService(db_session).set("privacy.search_history_retention_days", 90)
    SettingsService.invalidate_local()
    removed = await HistoryService(db_session).enforce_retention()
    assert removed == 1

    from sqlalchemy import select

    remaining = (
        (await db_session.execute(select(SearchHistory))).scalars().all()
    )
    assert [h.query for h in remaining] == ["new"]


@respx.mock
async def test_ai_service_with_mocked_ollama(app, db_session):
    from zen.services.settings import SettingsService

    service = SettingsService(db_session)
    await service.set_many(
        {
            "ai.enabled": True,
            "ai.backend": "ollama",
            "ai.base_url": "http://ollama.test:11434",
            "ai.model": "llama3.2",
        }
    )
    SettingsService.invalidate_local()

    respx.post("http://ollama.test:11434/api/chat").mock(
        return_value=httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": '["kubernetes networking basics", "k8s CNI comparison"]',
                }
            },
        )
    )

    from zen.ai.service import AIService

    suggestions = await AIService(db_session).expand_query("kubernetes networking")
    assert "kubernetes networking basics" in suggestions


async def test_ai_disabled_raises_cleanly(app, db_session):
    from zen.ai.service import AIService
    from zen.core.exceptions import AIUnavailableError

    with pytest.raises(AIUnavailableError):
        await AIService(db_session).expand_query("anything")


@respx.mock
async def test_ai_openai_compatible_backend(app):
    from zen.ai.base import ChatMessage, ChatOptions, build_backend

    respx.post("http://lmstudio.test:1234/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": "pong"}}]},
        )
    )
    backend = build_backend("lmstudio", base_url="http://lmstudio.test:1234/v1")
    reply = await backend.chat(
        [ChatMessage(role="user", content="ping")],
        ChatOptions(model="local-model"),
    )
    assert reply == "pong"


@respx.mock
async def test_repository_checksum_verification(app, db_session):
    import hashlib

    from zen.core.exceptions import PluginError
    from zen.plugins.repository import RepositoryService

    blob = b"fake plugin zip bytes"
    good_entry = {
        "id": "x",
        "version": "1.0.0",
        "download_url": "https://repo.test/x.zip",
        "sha256": hashlib.sha256(blob).hexdigest(),
    }
    bad_entry = {**good_entry, "sha256": "0" * 64}

    respx.get("https://repo.test/x.zip").mock(return_value=httpx.Response(200, content=blob))

    service = RepositoryService(db_session)
    downloaded = await service.download_artifact(good_entry)
    assert downloaded == blob

    with pytest.raises(PluginError, match="Checksum mismatch"):
        await service.download_artifact(bad_entry)
