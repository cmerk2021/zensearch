"""Outbound HTTP for providers: client construction and resilient fetch.

Implements the resilience envelope of ADR-0009 (timeouts + a single jittered
retry on transient failure). Circuit breaking lives in ``zen.search.health``.
"""

from __future__ import annotations

import asyncio
import random

import httpx
import structlog

from zen.core.config import get_settings

log = structlog.get_logger(__name__)

ACCEPT_LANGUAGE = "en-US,en;q=0.8"

_TRANSIENT_STATUS = {429, 500, 502, 503, 504}


def build_search_client(timeout: float | None = None) -> httpx.AsyncClient:
    """A shared client for one search execution (connection pooling across providers)."""
    settings = get_settings()
    return httpx.AsyncClient(
        timeout=httpx.Timeout(timeout or settings.outbound_timeout_seconds),
        headers={
            "User-Agent": settings.outbound_user_agent,
            "Accept-Language": ACCEPT_LANGUAGE,
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        },
        proxy=settings.outbound_proxy or None,
        follow_redirects=True,
        limits=httpx.Limits(max_connections=32, max_keepalive_connections=16),
    )


class TransientProviderFailure(Exception):
    """Connection/timeout/5xx failure that may succeed on retry."""


async def resilient_get(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    retries: int = 1,
) -> httpx.Response:
    return await _resilient_request(
        client, "GET", url, params=params, headers=headers, retries=retries
    )


async def resilient_post(
    client: httpx.AsyncClient,
    url: str,
    *,
    data: dict | None = None,
    headers: dict | None = None,
    retries: int = 1,
) -> httpx.Response:
    return await _resilient_request(
        client, "POST", url, data=data, headers=headers, retries=retries
    )


async def _resilient_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    params: dict | None = None,
    data: dict | None = None,
    headers: dict | None = None,
    retries: int = 1,
) -> httpx.Response:
    attempt = 0
    while True:
        try:
            response = await client.request(
                method, url, params=params, data=data, headers=headers
            )
            if response.status_code in _TRANSIENT_STATUS:
                raise TransientProviderFailure(f"upstream status {response.status_code}")
            response.raise_for_status()
            return response
        except (
            TransientProviderFailure,
            httpx.ConnectError,
            httpx.ReadTimeout,
            httpx.ConnectTimeout,
            httpx.RemoteProtocolError,
            httpx.PoolTimeout,
        ) as exc:
            attempt += 1
            if attempt > retries:
                raise TransientProviderFailure(str(exc)) from exc
            await asyncio.sleep(0.15 + random.random() * 0.35)
        except httpx.HTTPStatusError:
            # Non-transient HTTP error (4xx): no retry, bubble up.
            raise
