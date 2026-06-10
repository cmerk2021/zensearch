"""Zen command-line interface."""

from __future__ import annotations

import asyncio
import json

import typer

from zen.version import __version__

app = typer.Typer(name="zen", help="Zen — self-hosted research platform.", no_args_is_help=True)
users_app = typer.Typer(help="User management.", no_args_is_help=True)
db_app = typer.Typer(help="Database management.", no_args_is_help=True)
settings_app = typer.Typer(help="Instance settings.", no_args_is_help=True)
plugins_app = typer.Typer(help="Plugin management.", no_args_is_help=True)
app.add_typer(users_app, name="users")
app.add_typer(db_app, name="db")
app.add_typer(settings_app, name="settings")
app.add_typer(plugins_app, name="plugins")


def _run(coro):
    return asyncio.run(coro)


@app.command()
def version() -> None:
    """Print the Zen server version."""
    typer.echo(f"Zen {__version__}")


@app.command()
def serve(
    host: str = typer.Option(None, help="Bind host (default: ZEN_HOST)."),
    port: int = typer.Option(None, help="Bind port (default: ZEN_PORT)."),
    reload: bool = typer.Option(False, help="Auto-reload (development only)."),
) -> None:
    """Run the Zen server."""
    import uvicorn

    from zen.core.config import get_settings

    settings = get_settings()
    uvicorn.run(
        "zen.main:app",
        host=host or settings.host,
        port=port or settings.port,
        reload=reload,
        log_config=None,
    )


@app.command()
def doctor() -> None:
    """Diagnose configuration, database and cache connectivity."""

    async def _doctor() -> None:
        from sqlalchemy import text

        from zen.core.cache import build_cache
        from zen.core.config import get_settings
        from zen.db.base import get_session_factory, init_db

        settings = get_settings()
        typer.echo(f"Zen {__version__}")
        typer.echo(f"  env:       {settings.env}")
        typer.echo(f"  database:  {'sqlite' if settings.is_sqlite else 'postgresql'}")
        typer.echo(f"  cache:     {'redis' if settings.redis_url else 'memory'}")
        init_db()
        try:
            factory = get_session_factory()
            async with factory() as db:
                await db.execute(text("SELECT 1"))
            typer.secho("  database:  OK", fg=typer.colors.GREEN)
        except Exception as exc:
            typer.secho(f"  database:  FAILED — {exc}", fg=typer.colors.RED)
        cache = build_cache(settings.redis_url)
        if await cache.ping():
            typer.secho("  cache:     OK", fg=typer.colors.GREEN)
        else:
            typer.secho("  cache:     FAILED", fg=typer.colors.RED)
        await cache.close()

    _run(_doctor())


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------


@db_app.command("upgrade")
def db_upgrade(revision: str = typer.Argument("head")) -> None:
    """Apply Alembic migrations up to the given revision."""
    from pathlib import Path

    from alembic.config import Config

    from alembic import command

    config_path = Path(__file__).resolve().parent.parent / "alembic.ini"
    config = Config(str(config_path))
    command.upgrade(config, revision)
    typer.secho(f"Database upgraded to {revision}.", fg=typer.colors.GREEN)


@db_app.command("create-all")
def db_create_all() -> None:
    """Create the schema directly (SQLite / evaluation installs)."""

    async def _create() -> None:
        from zen.db.base import create_all, init_db

        init_db()
        await create_all()

    _run(_create())
    typer.secho("Schema created.", fg=typer.colors.GREEN)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


@users_app.command("create-admin")
def create_admin(
    username: str = typer.Option(..., prompt=True),
    password: str = typer.Option(..., prompt=True, hide_input=True, confirmation_prompt=True),
    email: str = typer.Option("", help="Optional email address."),
) -> None:
    """Create an administrator account."""

    async def _create() -> None:
        from zen.db.base import create_all, get_session_factory, init_db
        from zen.db.models import Role
        from zen.services.auth import AuthService

        init_db()
        await create_all()
        factory = get_session_factory()
        async with factory() as db:
            user = await AuthService(db).create_user(
                username=username, password=password, email=email or None, role=Role.ADMIN.value
            )
            typer.secho(f"Administrator '{user.username}' created.", fg=typer.colors.GREEN)

    _run(_create())


@users_app.command("list")
def list_users() -> None:
    """List all users."""

    async def _list() -> None:
        from sqlalchemy import select

        from zen.db.base import get_session_factory, init_db
        from zen.db.models import User

        init_db()
        factory = get_session_factory()
        async with factory() as db:
            users = (await db.execute(select(User).order_by(User.username))).scalars().all()
            for user in users:
                status = "active" if user.is_active else "disabled"
                typer.echo(f"{user.username:<24} {user.role:<10} {status:<9} {user.auth_source}")

    _run(_list())


@users_app.command("set-password")
def set_password(
    username: str = typer.Argument(...),
    password: str = typer.Option(..., prompt=True, hide_input=True, confirmation_prompt=True),
) -> None:
    """Reset a user's password."""

    async def _set() -> None:
        from sqlalchemy import select

        from zen.core.security import hash_password
        from zen.db.base import get_session_factory, init_db
        from zen.db.models import User

        init_db()
        factory = get_session_factory()
        async with factory() as db:
            user = (
                await db.execute(select(User).where(User.username == username.lower()))
            ).scalar_one_or_none()
            if user is None:
                typer.secho(f"User '{username}' not found.", fg=typer.colors.RED)
                raise typer.Exit(1)
            user.password_hash = hash_password(password)
            await db.commit()
            typer.secho("Password updated.", fg=typer.colors.GREEN)

    _run(_set())


@users_app.command("set-role")
def set_role(
    username: str = typer.Argument(...),
    role: str = typer.Argument(..., help="admin | user | readonly"),
) -> None:
    """Change a user's role."""

    async def _set() -> None:
        from sqlalchemy import select

        from zen.db.base import get_session_factory, init_db
        from zen.db.models import Role, User

        if role not in (Role.ADMIN.value, Role.USER.value, Role.READONLY.value):
            typer.secho(f"Unknown role: {role}", fg=typer.colors.RED)
            raise typer.Exit(1)
        init_db()
        factory = get_session_factory()
        async with factory() as db:
            user = (
                await db.execute(select(User).where(User.username == username.lower()))
            ).scalar_one_or_none()
            if user is None:
                typer.secho(f"User '{username}' not found.", fg=typer.colors.RED)
                raise typer.Exit(1)
            user.role = role
            await db.commit()
            typer.secho(f"'{username}' is now {role}.", fg=typer.colors.GREEN)

    _run(_set())


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


@settings_app.command("list")
def settings_list() -> None:
    """Show all instance settings (secrets redacted)."""

    async def _list() -> None:
        from zen.db.base import get_session_factory, init_db
        from zen.services.settings import SettingsService

        init_db()
        factory = get_session_factory()
        async with factory() as db:
            data = await SettingsService(db).get_all(redact_secrets=True)
            typer.echo(json.dumps(data, indent=2, sort_keys=True))

    _run(_list())


@settings_app.command("set")
def settings_set(key: str = typer.Argument(...), value: str = typer.Argument(...)) -> None:
    """Set an instance setting. VALUE is parsed as JSON, falling back to string."""

    async def _set() -> None:
        from zen.db.base import get_session_factory, init_db
        from zen.services.settings import SettingsService

        init_db()
        try:
            parsed = json.loads(value)
        except ValueError:
            parsed = value
        factory = get_session_factory()
        async with factory() as db:
            await SettingsService(db).set(key, parsed)
            typer.secho(f"{key} updated.", fg=typer.colors.GREEN)

    _run(_set())


# ---------------------------------------------------------------------------
# Plugins
# ---------------------------------------------------------------------------


@plugins_app.command("list")
def plugins_list() -> None:
    """List installed plugins."""

    async def _list() -> None:
        from zen.db.base import get_session_factory, init_db
        from zen.plugins.manager import PluginManager

        init_db()
        factory = get_session_factory()
        async with factory() as db:
            plugins = await PluginManager(db).list_installed()
            if not plugins:
                typer.echo("No plugins installed.")
                return
            for plugin in plugins:
                typer.echo(f"{plugin.slug:<32} {plugin.version:<12} {plugin.status}")

    _run(_list())


@plugins_app.command("install")
def plugins_install(
    plugin_id: str = typer.Argument(...),
    version: str = typer.Option(None, help="Specific version (default: latest in catalog)."),
) -> None:
    """Install a plugin from configured repositories."""

    async def _install() -> None:
        from zen.db.base import get_session_factory, init_db
        from zen.plugins.manager import PluginManager

        init_db()
        factory = get_session_factory()
        async with factory() as db:
            plugin = await PluginManager(db).install_from_repository(plugin_id, version)
            typer.secho(
                f"Installed {plugin.slug} {plugin.version} ({plugin.status}).",
                fg=typer.colors.GREEN,
            )

    _run(_install())


@plugins_app.command("remove")
def plugins_remove(plugin_id: str = typer.Argument(...)) -> None:
    """Remove an installed plugin."""

    async def _remove() -> None:
        from zen.db.base import get_session_factory, init_db
        from zen.plugins.manager import PluginManager

        init_db()
        factory = get_session_factory()
        async with factory() as db:
            await PluginManager(db).remove(plugin_id)
            typer.secho(f"Removed {plugin_id}.", fg=typer.colors.GREEN)

    _run(_remove())


if __name__ == "__main__":
    app()
