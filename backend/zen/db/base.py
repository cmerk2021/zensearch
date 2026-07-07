"""Async engine/session management and declarative base."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import structlog
from sqlalchemy import JSON, Column, DateTime, event, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

log = structlog.get_logger(__name__)


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
    a zero-dependency evaluation install works out of the box. After creating
    any missing tables it reconciles additive columns so in-place upgrades
    (which SQLAlchemy's ``create_all`` alone does not handle) pick up newly
    introduced model columns.
    """
    from zen.db import models  # noqa: F401  (ensure model registration)

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_reconcile_additive_columns)


def _reconcile_additive_columns(sync_conn: Connection) -> None:
    """Add columns introduced after a table was first created (in-place upgrades).

    ``metadata.create_all`` only creates missing *tables*; it never alters an
    existing table. SQLite / homelab installs upgrade in place, so a model
    column added in a new release would otherwise be missing until the database
    is recreated (surfacing as ``no such column`` errors). This performs
    additive, idempotent ``ALTER TABLE ... ADD COLUMN`` for any missing column.

    Column removals and renames are intentionally not handled — those require
    Alembic (which PostgreSQL production deployments use).
    """
    inspector = sa_inspect(sync_conn)
    dialect = sync_conn.dialect
    existing_tables = set(inspector.get_table_names())
    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue  # freshly created by create_all — already complete
        present = {col["name"] for col in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in present:
                continue
            sync_conn.execute(text(_add_column_ddl(dialect, table.name, column)))
            log.info("db.column_added", table=table.name, column=column.name)


def _add_column_ddl(dialect, table_name: str, column: Column) -> str:
    coltype = column.type.compile(dialect=dialect)
    ddl = f'ALTER TABLE "{table_name}" ADD COLUMN "{column.name}" {coltype}'
    default_sql = _column_default_sql(column)
    if default_sql is not None:
        ddl += f" DEFAULT {default_sql}"
    if not column.nullable:
        ddl += " NOT NULL"
    return ddl


def _column_default_sql(column: Column) -> str | None:
    """A constant DEFAULT expression for an added column.

    Databases (notably SQLite) reject adding a NOT NULL column without a
    default, so a safe zero-value is derived from the column type when no
    explicit ``server_default`` is set.
    """
    server_default = column.server_default
    if server_default is not None and hasattr(server_default, "arg"):
        arg = server_default.arg
        return str(getattr(arg, "text", arg))
    if column.nullable:
        return None
    try:
        py_type = column.type.python_type
    except (NotImplementedError, AttributeError):
        py_type = None
    if py_type is bool or py_type in (int, float):
        return "0"
    return "''"
