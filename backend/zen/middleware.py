"""ASGI middleware: security headers, request IDs, metrics."""

from __future__ import annotations

import time
import uuid

import structlog

from zen.observability import metrics


class SecurityHeadersMiddleware:
    """Defense-in-depth headers on every response."""

    CSP = (
        "default-src 'self'; "
        "img-src 'self' data: https:; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )

    def __init__(self, app, *, hsts: bool = False) -> None:
        self.app = app
        self.hsts = hsts

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message) -> None:
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                extra = [
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"referrer-policy", b"strict-origin-when-cross-origin"),
                    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
                    (b"content-security-policy", self.CSP.encode()),
                    (b"x-robots-tag", b"noindex, nofollow"),
                ]
                if self.hsts:
                    extra.append(
                        (b"strict-transport-security", b"max-age=31536000; includeSubDomains")
                    )
                existing = {h[0].lower() for h in headers}
                headers.extend(h for h in extra if h[0] not in existing)
            await send(message)

        await self.app(scope, receive, send_with_headers)


class RequestIDMiddleware:
    """Attach a request ID to logs and responses."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = uuid.uuid4().hex[:16]
        structlog.contextvars.bind_contextvars(request_id=request_id)

        async def send_with_id(message) -> None:
            if message["type"] == "http.response.start":
                message.setdefault("headers", []).append(
                    (b"x-request-id", request_id.encode())
                )
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            structlog.contextvars.unbind_contextvars("request_id")


class MetricsMiddleware:
    """Prometheus HTTP metrics with bounded label cardinality."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        method = scope.get("method", "GET")
        started = time.perf_counter()
        status_holder = {"status": 500}

        async def send_with_capture(message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_with_capture)
        finally:
            route = scope.get("route")
            template = getattr(route, "path", None)
            if template:  # Only record matched routes → bounded cardinality.
                elapsed = time.perf_counter() - started
                status_class = f"{status_holder['status'] // 100}xx"
                metrics.HTTP_REQUESTS.labels(
                    method=method, route=template, status=status_class
                ).inc()
                metrics.HTTP_DURATION.labels(method=method, route=template).observe(elapsed)
