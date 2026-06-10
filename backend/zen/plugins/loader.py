"""Plugin loader: imports installed plugins and runs their setup hooks."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zen.core.config import get_settings
from zen.core.exceptions import PluginError
from zen.db.models import Plugin, PluginStatus
from zen.plugins.manifest import MANIFEST_FILENAME, parse_manifest
from zen.plugins.sdk import PluginContext, unload_context

log = structlog.get_logger(__name__)

#: slug → live context for currently loaded plugins.
_loaded: dict[str, PluginContext] = {}

CURRENT_POINTER = "current.txt"


def plugin_root(slug: str) -> Path:
    return Path(get_settings().plugins_dir) / slug


def active_version_dir(slug: str) -> Path | None:
    root = plugin_root(slug)
    pointer = root / CURRENT_POINTER
    if not pointer.is_file():
        return None
    version = pointer.read_text(encoding="utf-8").strip()
    candidate = root / version
    return candidate if candidate.is_dir() else None


def set_active_version(slug: str, version: str) -> None:
    root = plugin_root(slug)
    root.mkdir(parents=True, exist_ok=True)
    (root / CURRENT_POINTER).write_text(version, encoding="utf-8")


def loaded_plugins() -> dict[str, PluginContext]:
    return dict(_loaded)


def load_plugin(slug: str, config: dict | None = None) -> PluginContext:
    """Import and initialize one installed plugin from its active version dir."""
    if slug in _loaded:
        return _loaded[slug]
    directory = active_version_dir(slug)
    if directory is None:
        raise PluginError(f"Plugin '{slug}' has no active installed version.")
    manifest_path = directory / MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise PluginError(f"Plugin '{slug}' is missing {MANIFEST_FILENAME}.")
    try:
        manifest = parse_manifest(json.loads(manifest_path.read_text(encoding="utf-8")))
    except (ValueError, OSError) as exc:
        raise PluginError(f"Plugin '{slug}' manifest unreadable: {exc}") from exc

    directory_str = str(directory)
    if directory_str not in sys.path:
        sys.path.insert(0, directory_str)
    try:
        # Force a fresh import if a previous version was loaded in-process.
        if manifest.entry in sys.modules:
            module = importlib.reload(sys.modules[manifest.entry])
        else:
            module = importlib.import_module(manifest.entry)
        setup = getattr(module, "setup", None)
        if not callable(setup):
            raise PluginError(
                f"Plugin '{slug}' entry module '{manifest.entry}' has no setup(ctx) function."
            )
        ctx = PluginContext(
            slug=slug, permissions=frozenset(manifest.permissions), config=config or {}
        )
        setup(ctx)
    except PluginError:
        raise
    except Exception as exc:
        raise PluginError(f"Plugin '{slug}' failed during setup: {exc}") from exc
    _loaded[slug] = ctx
    log.info("plugin.loaded", plugin=slug, version=manifest.version)
    return ctx


def unload_plugin(slug: str) -> None:
    ctx = _loaded.pop(slug, None)
    if ctx is not None:
        unload_context(ctx)
        log.info("plugin.unloaded", plugin=slug)


async def load_enabled_plugins(db: AsyncSession) -> None:
    """Startup hook: load every enabled plugin; isolate individual failures."""
    rows = (
        await db.execute(select(Plugin).where(Plugin.status == PluginStatus.ENABLED.value))
    ).scalars().all()
    for plugin in rows:
        try:
            load_plugin(plugin.slug, config=plugin.manifest.get("config", {}))
        except PluginError as exc:
            plugin.status = PluginStatus.ERROR.value
            plugin.error = str(exc)
            log.error("plugin.load_failed", plugin=plugin.slug, error=str(exc))
    await db.commit()
