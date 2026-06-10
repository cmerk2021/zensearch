# Backups, updates, and operations

## What to back up

| Data | Where | Criticality |
|---|---|---|
| PostgreSQL database | `postgres-data` volume | **Everything lives here** |
| SQLite database | `zen-data` volume (`/data/zen.db`) | Same, minimal installs |
| Installed plugins | `zen-data` volume (`/data/plugins`) | Reinstallable, but back up private plugins |
| `.env` / secrets | Compose directory | **`ZEN_SECRET_KEY` is required to decrypt stored API keys** |

> Losing `ZEN_SECRET_KEY` does not lose your data, but all encrypted secrets
> (provider/AI API keys, OIDC client secret) become undecryptable and must be
> re-entered.

## PostgreSQL backup

```bash
# Hot backup
docker compose exec postgres pg_dump -U zen -Fc zen > zen-$(date +%F).dump

# Restore into a fresh instance
docker compose exec -T postgres pg_restore -U zen -d zen --clean < zen-2026-01-01.dump
```

Schedule it with cron/systemd timers; keep at least 7 daily copies off-host.

## SQLite backup

```bash
docker compose exec zen-server sh -c \
  "python -c \"import sqlite3; sqlite3.connect('/data/zen.db').execute('VACUUM INTO \\'/data/backup.db\\'')\""
docker compose cp zen-server:/data/backup.db ./zen-$(date +%F).db
```

(`VACUUM INTO` gives a consistent snapshot while the app runs.)

## Updates

```bash
docker compose pull && docker compose up -d
```

- Migrations are applied by the `zen-migrate` one-shot service before the API
  accepts traffic.
- Patch/minor versions are always forward-migratable. Major versions may
  contain breaking changes — read the release notes.
- Roll back by pinning the previous image tag *and* restoring the DB backup
  taken before the upgrade (migrations are not auto-reversed in production).

## Monitoring

- **Liveness:** `GET /api/v1/health` → `{"status":"ok"}`
- **Readiness:** `GET /api/v1/health/ready` → checks DB + cache, 503 when degraded
- **Metrics:** `GET /metrics` (Prometheus format). Admin-gated by default;
  set `ZEN_METRICS_REQUIRE_ADMIN=false` to expose to an internal scraper.

Useful series: `zen_searches_total`, `zen_search_duration_seconds`,
`zen_provider_requests_total`, `zen_provider_latency_seconds`,
`zen_http_request_duration_seconds`, `zen_scheduler_task_runs_total`,
`zen_active_sessions`, `zen_plugins_installed`.

Structured JSON logs go to stdout — point Loki/Vector/fluentd at the
container output.

## Scaling notes

A single instance comfortably serves a household or small team on Pi-class
hardware. If you need more:

1. Move to PostgreSQL and Redis (required for any multi-replica setup —
   the in-memory cache and rate limiter are per-process).
2. Scale `zen-server` replicas; the scheduler elects a single leader through
   a Redis lock, so periodic tasks don't duplicate.
3. `zen-web` is stateless; scale freely behind your proxy.
