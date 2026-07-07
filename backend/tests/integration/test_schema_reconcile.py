"""In-place schema reconciliation for SQLite/homelab upgrades.

``create_all`` only creates missing tables; these tests cover the additive
column reconciler that lets an existing database pick up newly added model
columns on restart (e.g. ``users.ai_enabled``).
"""

from sqlalchemy import inspect as sa_inspect


async def test_reconcile_adds_missing_columns(tmp_path):
    from zen.db import base as db_base

    url = f"sqlite+aiosqlite:///{tmp_path / 'old.db'}"
    await db_base.dispose_engine()
    db_base.init_db(url)
    engine = db_base.get_engine()

    # Simulate a pre-existing 'users' table from a release that predates the
    # ai_enabled column, with an existing row.
    async with engine.begin() as conn:
        await conn.exec_driver_sql(
            "CREATE TABLE users ("
            "id TEXT PRIMARY KEY, username TEXT NOT NULL, is_active BOOLEAN NOT NULL"
            ")"
        )
        await conn.exec_driver_sql(
            "INSERT INTO users (id, username, is_active) VALUES ('u1', 'legacy', 1)"
        )

    # create_all creates the remaining tables and reconciles the users table.
    await db_base.create_all()

    async with engine.begin() as conn:
        cols = await conn.run_sync(
            lambda c: {col["name"] for col in sa_inspect(c).get_columns("users")}
        )
        ai_enabled = (
            await conn.exec_driver_sql("SELECT ai_enabled FROM users WHERE id = 'u1'")
        ).scalar_one()

    assert "ai_enabled" in cols
    # Existing rows default to False (0) for the new NOT NULL column.
    assert ai_enabled == 0

    await db_base.dispose_engine()


async def test_reconcile_is_noop_on_current_schema(tmp_path):
    from zen.db import base as db_base

    url = f"sqlite+aiosqlite:///{tmp_path / 'fresh.db'}"
    await db_base.dispose_engine()
    db_base.init_db(url)

    # First call creates everything; a second call must be an idempotent no-op.
    await db_base.create_all()
    await db_base.create_all()

    engine = db_base.get_engine()
    async with engine.begin() as conn:
        cols = await conn.run_sync(
            lambda c: {col["name"] for col in sa_inspect(c).get_columns("users")}
        )
    assert "ai_enabled" in cols

    await db_base.dispose_engine()
