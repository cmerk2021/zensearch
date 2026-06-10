"""Prometheus metrics. Exposed at /metrics (admin-gated by default).

Cardinality discipline: labels are bounded sets (provider slugs, modes,
HTTP methods, route templates) — never raw paths, queries, or user IDs.
"""

from __future__ import annotations

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

REGISTRY = CollectorRegistry()

HTTP_REQUESTS = Counter(
    "zen_http_requests_total",
    "HTTP requests by method, route template and status class.",
    ["method", "route", "status"],
    registry=REGISTRY,
)
HTTP_DURATION = Histogram(
    "zen_http_request_duration_seconds",
    "HTTP request duration by route template.",
    ["method", "route"],
    buckets=(0.005, 0.025, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=REGISTRY,
)

SEARCHES_TOTAL = Counter(
    "zen_searches_total",
    "Search executions by mode and cache outcome.",
    ["mode", "cached"],
    registry=REGISTRY,
)
SEARCH_DURATION = Histogram(
    "zen_search_duration_seconds",
    "End-to-end search execution duration.",
    buckets=(0.1, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 15.0),
    registry=REGISTRY,
)

PROVIDER_REQUESTS = Counter(
    "zen_provider_requests_total",
    "Provider calls by outcome.",
    ["provider", "outcome"],
    registry=REGISTRY,
)
PROVIDER_LATENCY = Histogram(
    "zen_provider_latency_seconds",
    "Provider call latency.",
    ["provider"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0),
    registry=REGISTRY,
)

CACHE_OPERATIONS = Counter(
    "zen_cache_operations_total",
    "Cache operations by kind and outcome (hit/miss/set).",
    ["kind", "outcome"],
    registry=REGISTRY,
)

AI_REQUESTS = Counter(
    "zen_ai_requests_total",
    "AI backend calls by capability and outcome.",
    ["capability", "outcome"],
    registry=REGISTRY,
)
AI_LATENCY = Histogram(
    "zen_ai_latency_seconds",
    "AI backend call latency.",
    ["capability"],
    buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
    registry=REGISTRY,
)

PLUGIN_GAUGE = Gauge(
    "zen_plugins_installed",
    "Installed plugins by status.",
    ["status"],
    registry=REGISTRY,
)
SCHEDULER_RUNS = Counter(
    "zen_scheduler_task_runs_total",
    "Scheduler task executions by task and outcome.",
    ["task", "outcome"],
    registry=REGISTRY,
)
ACTIVE_SESSIONS = Gauge(
    "zen_active_sessions",
    "Currently valid user sessions (refreshed periodically).",
    registry=REGISTRY,
)
BUILD_INFO = Gauge(
    "zen_build_info",
    "Build metadata.",
    ["version"],
    registry=REGISTRY,
)


def init_build_info(version: str) -> None:
    BUILD_INFO.labels(version=version).set(1)


def render() -> tuple[bytes, str]:
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
