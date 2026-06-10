"""Zen application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from zen.core.cache import build_cache, get_cache, set_cache
from zen.core.config import get_settings
from zen.core.exceptions import RateLimitedError, ZenError
from zen.db.base import dispose_engine, get_session_factory, init_db
from zen.middleware import MetricsMiddleware, RequestIDMiddleware, SecurityHeadersMiddleware
from zen.observability import metrics
from zen.observability.logging import configure_logging
from zen.version import __version__
from zen.workers.scheduler import Scheduler
from zen.workers.tasks import register_default_tasks

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    metrics.init_build_info(__version__)
    set_cache(build_cache(settings.redis_url))
    init_db()

    # Schema: SQLite/dev installs self-create; PostgreSQL production uses Alembic.
    if settings.is_sqlite or settings.env != "production":
        from zen.db.base import create_all

        await create_all()

    factory = get_session_factory()
    async with factory() as db:
        from zen.services.bootstrap import bootstrap_instance

        await bootstrap_instance(db)
        from zen.plugins.loader import load_enabled_plugins

        await load_enabled_plugins(db)

    scheduler = Scheduler()
    register_default_tasks(scheduler)
    await scheduler.start()
    app.state.scheduler = scheduler
    log.info("zen.started", version=__version__, env=settings.env)

    yield

    await scheduler.stop()
    await get_cache().close()
    await dispose_engine()
    log.info("zen.stopped")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Zen",
        version=__version__,
        description="Self-hosted research and knowledge discovery platform.",
        lifespan=lifespan,
        docs_url="/api/docs" if settings.env != "production" else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.env != "production" else None,
    )

    # --- Middleware (outermost first) -----------------------------------
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        SecurityHeadersMiddleware, hsts=settings.cookie_secure_effective
    )
    if settings.cors_origin_list:
        from fastapi.middleware.cors import CORSMiddleware

        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*", "X-CSRF-Token"],
        )

    # --- Exception handlers ------------------------------------------------
    @app.exception_handler(ZenError)
    async def zen_error_handler(request: Request, exc: ZenError) -> JSONResponse:
        headers = {}
        if isinstance(exc, RateLimitedError):
            headers["Retry-After"] = str(exc.retry_after)
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message, "details": exc.details},
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "code": "validation_failed",
                "message": "Request validation failed.",
                "details": exc.errors(),
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_error", path=request.url.path)
        return JSONResponse(
            status_code=500,
            content={"code": "internal_error", "message": "An internal error occurred."},
        )

    # --- Routes -------------------------------------------------------------
    from zen.api.routes.admin import router as admin_router
    from zen.api.routes.auth import router as auth_router
    from zen.api.routes.knowledge import router as knowledge_router
    from zen.api.routes.search import router as search_router
    from zen.api.routes.user import ai_router, meta_router
    from zen.api.routes.user import router as user_router

    api_prefix = "/api/v1"
    app.include_router(auth_router, prefix=api_prefix)
    app.include_router(search_router, prefix=api_prefix)
    app.include_router(knowledge_router, prefix=api_prefix)
    app.include_router(user_router, prefix=api_prefix)
    app.include_router(ai_router, prefix=api_prefix)
    app.include_router(meta_router, prefix=api_prefix)
    app.include_router(admin_router, prefix=api_prefix)

    # --- Health & metrics ------------------------------------------------------
    @app.get("/api/v1/health", tags=["meta"])
    async def health() -> dict:
        return {"status": "ok", "version": __version__}

    @app.get("/api/v1/health/ready", tags=["meta"])
    async def ready() -> Response:
        from sqlalchemy import text

        checks: dict[str, bool] = {}
        try:
            factory = get_session_factory()
            async with factory() as db:
                await db.execute(text("SELECT 1"))
            checks["database"] = True
        except Exception:
            checks["database"] = False
        checks["cache"] = await get_cache().ping()
        ok = all(checks.values())
        return JSONResponse(
            status_code=200 if ok else 503,
            content={"status": "ok" if ok else "degraded", "checks": checks},
        )

    @app.get("/metrics", include_in_schema=False)
    async def metrics_endpoint(request: Request) -> Response:
        if not settings.metrics_enabled:
            return Response(status_code=404)
        if settings.metrics_require_admin:
            from zen.api.deps import get_current_user_optional
            from zen.db.base import get_db_session

            async for db in get_db_session():
                user = await get_current_user_optional(request, db)
                if user is None or not user.is_admin:
                    return JSONResponse(
                        status_code=403,
                        content={
                            "code": "permission_denied",
                            "message": "Metrics require administrator access "
                            "(set ZEN_METRICS_REQUIRE_ADMIN=false to expose internally).",
                        },
                    )
        payload, content_type = metrics.render()
        return Response(content=payload, media_type=content_type)

    return app


app = create_app()
