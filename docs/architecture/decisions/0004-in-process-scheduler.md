# ADR-0004: In-process scheduler instead of Celery

**Status:** Accepted

## Context

Background needs: provider health probes, plugin repository sync, session/cache
cleanup, smart-collection refresh, retention enforcement. The brief suggests
"Celery or equivalent". Celery adds a broker dependency, a worker container,
and ~150MB+ of RSS — hostile to the Raspberry Pi deployment target.

## Decision

Ship a supervised in-process asyncio scheduler (`zen.workers.scheduler`)
running inside the API process lifespan. Tasks are plain async callables
registered with an interval and jitter; failures are isolated, logged, and
counted in metrics.

## Consequences

- Single-container deployment remains possible; RAM floor stays low.
- Horizontal scaling of the API tier would duplicate scheduled work; the
  scheduler therefore takes a cache-based leader lock so only one instance runs
  periodic tasks at a time.
- If future workloads need durable queues (e.g. large crawl jobs), the
  `TaskRunner` protocol allows an external-queue implementation without
  changing task code. This is the documented escalation path.
