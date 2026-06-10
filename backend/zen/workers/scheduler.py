"""Supervised in-process asyncio scheduler (ADR-0004).

Single-leader semantics across replicas via a cache lock; failures are
isolated per task and surfaced through metrics and logs.
"""

from __future__ import annotations

import asyncio
import random
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import structlog

from zen.core.cache import get_cache
from zen.observability import metrics

log = structlog.get_logger(__name__)

LEADER_KEY = "scheduler:leader"
LEADER_TTL = 60


@dataclass(slots=True)
class ScheduledTask:
    name: str
    func: Callable[[], Awaitable[None]]
    interval_seconds: float
    jitter_seconds: float = 5.0
    run_at_start: bool = False


class Scheduler:
    def __init__(self) -> None:
        self.tasks: list[ScheduledTask] = []
        self._runners: list[asyncio.Task] = []
        self._leader_task: asyncio.Task | None = None
        self._holder = uuid.uuid4().hex
        self._is_leader = asyncio.Event()
        self._stopping = False

    def register(
        self,
        name: str,
        func: Callable[[], Awaitable[None]],
        *,
        interval_seconds: float,
        jitter_seconds: float = 5.0,
        run_at_start: bool = False,
    ) -> None:
        self.tasks.append(
            ScheduledTask(
                name=name,
                func=func,
                interval_seconds=interval_seconds,
                jitter_seconds=jitter_seconds,
                run_at_start=run_at_start,
            )
        )

    async def start(self) -> None:
        self._stopping = False
        self._leader_task = asyncio.create_task(self._leadership_loop(), name="zen-leader")
        for task in self.tasks:
            self._runners.append(
                asyncio.create_task(self._run_loop(task), name=f"zen-task-{task.name}")
            )
        log.info("scheduler.started", tasks=[t.name for t in self.tasks])

    async def stop(self) -> None:
        import contextlib

        self._stopping = True
        for runner in [*self._runners, self._leader_task]:
            if runner is not None:
                runner.cancel()
        for runner in [*self._runners, self._leader_task]:
            if runner is not None:
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await runner
        self._runners.clear()
        self._leader_task = None
        if self._is_leader.is_set():
            await get_cache().release_lock(LEADER_KEY, self._holder)
            self._is_leader.clear()
        log.info("scheduler.stopped")

    async def _leadership_loop(self) -> None:
        while not self._stopping:
            try:
                acquired = await get_cache().acquire_lock(LEADER_KEY, self._holder, LEADER_TTL)
                if acquired:
                    if not self._is_leader.is_set():
                        log.info("scheduler.leader_acquired")
                    self._is_leader.set()
                else:
                    if self._is_leader.is_set():
                        log.info("scheduler.leader_lost")
                    self._is_leader.clear()
            except Exception:
                log.exception("scheduler.leadership_error")
                self._is_leader.clear()
            await asyncio.sleep(LEADER_TTL / 3)

    async def _run_loop(self, task: ScheduledTask) -> None:
        if not task.run_at_start:
            await asyncio.sleep(
                random.uniform(2.0, max(task.jitter_seconds, 2.0))
            )
        while not self._stopping:
            if self._is_leader.is_set():
                try:
                    await task.func()
                    metrics.SCHEDULER_RUNS.labels(task=task.name, outcome="ok").inc()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    metrics.SCHEDULER_RUNS.labels(task=task.name, outcome="error").inc()
                    log.exception("scheduler.task_failed", task=task.name)
            sleep_for = task.interval_seconds + random.uniform(0, task.jitter_seconds)
            await asyncio.sleep(sleep_for)
