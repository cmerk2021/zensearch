"""Async engine/session management and declarative base."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import JSON, DateTime, event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    type_annotation_map = {
        dict: JSON,
        list: JSON,
        datetime: DateTime(timezone=True),
    }


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _configure_sqlite(engine: AsyncEngine) -> None:
    @event.listens_for(engine.sync_engine, "connect")
    def _on_connect(dbapi_conn, _record) -> None:  # pragma: no cover - driver glue
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


def build_engine(database_url: str, *, pool_size: int = 10, max_overflow: int = 5) -> AsyncEngine:
    if database_url.startswith("sqlite"):
        # Ensure parent directory exists for file-backed SQLite.
        path_part = database_url.split("///")[-1]
        if path_part and ":memory:" not in path_part:
            Path(path_part).parent.mkdir(parents=True, exist_ok=True)
        engine = create_async_engine(database_url, echo=False)
        _configure_sqlite(engine)
        return engine
    return create_async_engine(
        database_url,
        echo=False,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,
    )


def init_db(database_url: str | None = None) -> AsyncEngine:
    """Initialise the global engine and session factory."""
    global _engine, _session_factory
    if database_url is None:
        from zen.core.config import get_settings

        settings = get_settings()
        database_url = settings.database_url
        _engine = build_engine(
            database_url,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_pool_max_overflow,
        )
    else:
        _engine = build_engine(database_url)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_engine() -> AsyncEngine:
    if _engine is None:
        init_db()
    assert _engine is not None
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        init_db()
    assert _session_factory is not None
    return _session_factory


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a transactional session."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def dispose_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


async def create_all() -> None:
    """Create the full schema directly (dev/test/SQLite path).

    Production PostgreSQL deployments use Alembic migrations; this exists so
    a zero-dependency evaluation install works out of the box.
    """
    from zen.db import models  # noqa: F401  (ensure model registration)

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
