"""Plugin lifecycle manager: install, update, remove, rollback, dependencies."""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import zipfile

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zen.core.exceptions import ConflictError, NotFoundError, PluginError
from zen.db.base import utcnow
from zen.db.models import Plugin, PluginStatus
from zen.observability import metrics
from zen.plugins.loader import (
    load_plugin,
    plugin_root,
    set_active_version,
    unload_plugin,
)
from zen.plugins.manifest import MANIFEST_FILENAME, PluginManifest, parse_manifest
from zen.plugins.repository import RepositoryService

log = structlog.get_logger(__name__)

MAX_DEPENDENCY_DEPTH = 10


class PluginManager:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repositories = RepositoryService(db)

    async def list_installed(self) -> list[Plugin]:
        rows = (await self.db.execute(select(Plugin).order_by(Plugin.name))).scalars().all()
        return list(rows)

    async def get(self, slug: str) -> Plugin:
        plugin = (
            await self.db.execute(select(Plugin).where(Plugin.slug == slug))
        ).scalar_one_or_none()
        if plugin is None:
            raise NotFoundError(f"Plugin '{slug}' is not installed.")
        return plugin

    # ------------------------------------------------------------------
    # Install / update
    # ------------------------------------------------------------------

    async def install_from_repository(
        self, plugin_id: str, version: str | None = None, *, _depth: int = 0
    ) -> Plugin:
        if _depth > MAX_DEPENDENCY_DEPTH:
            raise PluginError("Dependency chain too deep (possible cycle).")
        repo, entry = await self.repositories.find_plugin(plugin_id, version)
        manifest = parse_manifest(entry.get("manifest") or {})
        if manifest.id != plugin_id:
            raise PluginError("Repository entry id does not match its manifest id.")

        # Resolve dependencies first (depth-first; already-installed are skipped).
        for dependency in manifest.requires:
            if dependency == plugin_id:
                raise PluginError(f"Plugin '{plugin_id}' cannot depend on itself.")
            existing = (
                await self.db.execute(select(Plugin).where(Plugin.slug == dependency))
            ).scalar_one_or_none()
            if existing is None:
                log.info("plugin.installing_dependency", plugin=plugin_id, dependency=dependency)
                await self.install_from_repository(dependency, _depth=_depth + 1)

        blob = await self.repositories.download_artifact(entry)
        return await self._install_artifact(
            blob,
            manifest=manifest,
            source_repo=repo.name,
            checksum=entry["sha256"].lower(),
        )

    async def install_from_bytes(self, blob: bytes, *, source: str = "upload") -> Plugin:
        """Install from an uploaded zip (private/sideloaded plugins)."""
        manifest = self._read_manifest_from_zip(blob)
        checksum = hashlib.sha256(blob).hexdigest()
        return await self._install_artifact(
            blob, manifest=manifest, source_repo=source, checksum=checksum
        )

    async def _install_artifact(
        self, blob: bytes, *, manifest: PluginManifest, source_repo: str, checksum: str
    ) -> Plugin:
        zip_manifest = self._read_manifest_from_zip(blob)
        if zip_manifest.id != manifest.id or zip_manifest.version != manifest.version:
            raise PluginError(
                "Artifact manifest does not match the catalog manifest "
                f"({zip_manifest.id}@{zip_manifest.version} vs {manifest.id}@{manifest.version})."
            )
        existing = (
            await self.db.execute(select(Plugin).where(Plugin.slug == manifest.id))
        ).scalar_one_or_none()
        previous_version = existing.version if existing is not None else None
        if existing is not None and existing.version == manifest.version:
            raise ConflictError(
                f"Plugin '{manifest.id}' version {manifest.version} is already installed."
            )

        target = plugin_root(manifest.id) / manifest.version
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True, exist_ok=True)
        self._safe_extract(blob, target)

        # Switch the active pointer, reload, persist.
        if existing is not None:
            unload_plugin(manifest.id)
        set_active_version(manifest.id, manifest.version)
        try:
            load_plugin(manifest.id)
            status, error = PluginStatus.ENABLED.value, ""
        except PluginError as exc:
            status, error = PluginStatus.ERROR.value, str(exc)
            log.error("plugin.post_install_load_failed", plugin=manifest.id, error=str(exc))

        if existing is None:
            plugin = Plugin(
                slug=manifest.id,
                name=manifest.name,
                version=manifest.version,
                description=manifest.description,
                author=manifest.author,
                license=manifest.license,
                homepage=manifest.homepage,
                types=manifest.types,
                manifest=manifest.to_dict(),
                source_repo=source_repo,
                checksum=checksum,
                status=status,
                error=error,
            )
            self.db.add(plugin)
        else:
            plugin = existing
            plugin.name = manifest.name
            plugin.version = manifest.version
            plugin.description = manifest.description
            plugin.author = manifest.author
            plugin.license = manifest.license
            plugin.homepage = manifest.homepage
            plugin.types = manifest.types
            plugin.manifest = manifest.to_dict()
            plugin.source_repo = source_repo
            plugin.checksum = checksum
            plugin.status = status
            plugin.error = error
            plugin.previous_version = previous_version
            plugin.updated_at = utcnow()
        await self.db.commit()
        await self.db.refresh(plugin)
        await self._refresh_metrics()
        log.info(
            "plugin.installed",
            plugin=manifest.id,
            version=manifest.version,
            previous=previous_version,
            source=source_repo,
        )
        return plugin

    # ------------------------------------------------------------------
    # Enable / disable / remove / rollback
    # ------------------------------------------------------------------

    async def set_enabled(self, slug: str, enabled: bool) -> Plugin:
        plugin = await self.get(slug)
        if enabled:
            try:
                load_plugin(slug)
                plugin.status = PluginStatus.ENABLED.value
                plugin.error = ""
            except PluginError as exc:
                plugin.status = PluginStatus.ERROR.value
                plugin.error = str(exc)
        else:
            unload_plugin(slug)
            plugin.status = PluginStatus.DISABLED.value
        await self.db.commit()
        await self._refresh_metrics()
        return plugin

    async def remove(self, slug: str) -> None:
        plugin = await self.get(slug)
        dependents = await self._dependents_of(slug)
        if dependents:
            raise ConflictError(
                f"Cannot remove '{slug}': required by {', '.join(sorted(dependents))}."
            )
        unload_plugin(slug)
        root = plugin_root(slug)
        if root.exists():
            shutil.rmtree(root, ignore_errors=True)
        await self.db.delete(plugin)
        await self.db.commit()
        await self._refresh_metrics()
        log.info("plugin.removed", plugin=slug)

    async def rollback(self, slug: str) -> Plugin:
        plugin = await self.get(slug)
        if not plugin.previous_version:
            raise ConflictError(f"Plugin '{slug}' has no previous version to roll back to.")
        previous_dir = plugin_root(slug) / plugin.previous_version
        manifest_path = previous_dir / MANIFEST_FILENAME
        if not manifest_path.is_file():
            raise PluginError(
                f"Previous version {plugin.previous_version} is no longer on disk."
            )
        manifest = parse_manifest(json.loads(manifest_path.read_text(encoding="utf-8")))
        unload_plugin(slug)
        rolled_back_from = plugin.version
        set_active_version(slug, plugin.previous_version)
        try:
            load_plugin(slug)
            plugin.status = PluginStatus.ENABLED.value
            plugin.error = ""
        except PluginError as exc:
            plugin.status = PluginStatus.ERROR.value
            plugin.error = str(exc)
        plugin.version = manifest.version
        plugin.manifest = manifest.to_dict()
        plugin.previous_version = None
        await self.db.commit()
        await self.db.refresh(plugin)
        await self._refresh_metrics()
        log.info("plugin.rolled_back", plugin=slug, from_version=rolled_back_from, to=manifest.version)
        return plugin

    async def check_updates(self) -> list[dict]:
        """Compare installed versions against enabled repository catalogs."""
        from packaging.version import InvalidVersion, Version

        updates = []
        for plugin in await self.list_installed():
            try:
                _, entry = await self.repositories.find_plugin(plugin.slug)
            except NotFoundError:
                continue
            try:
                if Version(entry["version"]) > Version(plugin.version):
                    updates.append(
                        {
                            "slug": plugin.slug,
                            "installed": plugin.version,
                            "available": entry["version"],
                        }
                    )
            except InvalidVersion:
                continue
        return updates

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _dependents_of(self, slug: str) -> list[str]:
        dependents = []
        for plugin in await self.list_installed():
            if slug in (plugin.manifest or {}).get("requires", []):
                dependents.append(plugin.slug)
        return dependents

    @staticmethod
    def _read_manifest_from_zip(blob: bytes) -> PluginManifest:
        try:
            with zipfile.ZipFile(io.BytesIO(blob)) as zf:
                names = zf.namelist()
                if MANIFEST_FILENAME not in names:
                    raise PluginError(f"Plugin zip does not contain {MANIFEST_FILENAME} at its root.")
                manifest_data = json.loads(zf.read(MANIFEST_FILENAME).decode("utf-8"))
        except zipfile.BadZipFile as exc:
            raise PluginError("Artifact is not a valid zip file.") from exc
        except ValueError as exc:
            raise PluginError(f"Plugin manifest is not valid JSON: {exc}") from exc
        return parse_manifest(manifest_data)

    @staticmethod
    def _safe_extract(blob: bytes, target) -> None:
        """Extract with zip-slip protection."""
        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            for member in zf.infolist():
                name = member.filename
                if name.startswith(("/", "\\")) or ".." in name.replace("\\", "/").split("/"):
                    raise PluginError(f"Plugin zip contains an unsafe path: {name}")
            zf.extractall(target)

    async def _refresh_metrics(self) -> None:
        from sqlalchemy import func

        rows = (
            await self.db.execute(
                select(Plugin.status, func.count()).group_by(Plugin.status)
            )
        ).all()
        for status in (s.value for s in PluginStatus):
            metrics.PLUGIN_GAUGE.labels(status=status).set(0)
        for status, count in rows:
            metrics.PLUGIN_GAUGE.labels(status=status).set(count)
