"""Plugin repository client: catalog sync and artifact download.

Catalog format (``index.json`` at the repository URL)::

    {
      "name": "Official Zen Repository",
      "plugins": [
        {
          "id": "example-provider",
          "name": "Example Provider",
          "version": "1.2.0",
          "description": "...",
          "download_url": "https://.../example-provider-1.2.0.zip",
          "sha256": "<hex digest of the zip>",
          "manifest": { ...zen-plugin.json contents... }
        }
      ]
    }
"""

from __future__ import annotations

import hashlib

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zen.core.exceptions import NotFoundError, PluginError, ValidationFailed
from zen.db.base import utcnow
from zen.db.models import PluginRepository, RepositoryKind

log = structlog.get_logger(__name__)

MAX_PLUGIN_SIZE = 50 * 1024 * 1024  # 50 MB
CATALOG_TIMEOUT = 20.0
DOWNLOAD_TIMEOUT = 120.0


class RepositoryService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_repositories(self) -> list[PluginRepository]:
        rows = (
            await self.db.execute(select(PluginRepository).order_by(PluginRepository.added_at))
        ).scalars().all()
        return list(rows)

    async def add(self, *, name: str, url: str, kind: str) -> PluginRepository:
        if kind not in (k.value for k in RepositoryKind):
            raise ValidationFailed(f"Unknown repository kind: {kind}")
        if not url.startswith("https://") and not url.startswith("http://localhost"):
            raise ValidationFailed("Repository URLs must use HTTPS (or localhost for testing).")
        existing = (
            await self.db.execute(select(PluginRepository).where(PluginRepository.url == url))
        ).scalar_one_or_none()
        if existing is not None:
            raise ValidationFailed("This repository is already configured.")
        repo = PluginRepository(name=name.strip() or url, url=url, kind=kind)
        self.db.add(repo)
        await self.db.commit()
        await self.db.refresh(repo)
        return repo

    async def remove(self, repo_id: str) -> None:
        repo = await self.db.get(PluginRepository, repo_id)
        if repo is None:
            raise NotFoundError("Repository not found.")
        await self.db.delete(repo)
        await self.db.commit()

    async def set_enabled(self, repo_id: str, enabled: bool) -> PluginRepository:
        repo = await self.db.get(PluginRepository, repo_id)
        if repo is None:
            raise NotFoundError("Repository not found.")
        repo.enabled = enabled
        await self.db.commit()
        return repo

    async def sync(self, repo_id: str) -> PluginRepository:
        repo = await self.db.get(PluginRepository, repo_id)
        if repo is None:
            raise NotFoundError("Repository not found.")
        try:
            async with httpx.AsyncClient(timeout=CATALOG_TIMEOUT, follow_redirects=True) as client:
                response = await client.get(repo.url, headers={"Accept": "application/json"})
                response.raise_for_status()
                catalog = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise PluginError(f"Failed to fetch repository catalog: {exc}") from exc
        if not isinstance(catalog, dict) or not isinstance(catalog.get("plugins"), list):
            raise PluginError("Repository catalog is malformed (expected {'plugins': [...]}).")
        cleaned = []
        for entry in catalog["plugins"]:
            if not isinstance(entry, dict):
                continue
            if not all(isinstance(entry.get(k), str) and entry.get(k) for k in ("id", "version", "download_url", "sha256")):
                log.warning("repository.entry_skipped", repo=repo.name, entry=str(entry)[:120])
                continue
            cleaned.append(entry)
        repo.catalog = {"name": catalog.get("name", repo.name), "plugins": cleaned}
        repo.last_synced_at = utcnow()
        await self.db.commit()
        await self.db.refresh(repo)
        log.info("repository.synced", repo=repo.name, plugins=len(cleaned))
        return repo

    async def sync_all_enabled(self) -> int:
        repos = await self.list_repositories()
        synced = 0
        for repo in repos:
            if not repo.enabled:
                continue
            try:
                await self.sync(repo.id)
                synced += 1
            except PluginError as exc:
                log.warning("repository.sync_failed", repo=repo.name, error=str(exc))
        return synced

    async def find_plugin(
        self, plugin_id: str, version: str | None = None
    ) -> tuple[PluginRepository, dict]:
        """Locate a plugin entry across enabled repositories (priority: official first)."""
        repos = await self.list_repositories()
        order = {RepositoryKind.OFFICIAL.value: 0, RepositoryKind.PRIVATE.value: 1,
                 RepositoryKind.COMMUNITY.value: 2}
        repos.sort(key=lambda r: order.get(r.kind, 3))
        for repo in repos:
            if not repo.enabled or not repo.catalog:
                continue
            for entry in repo.catalog.get("plugins", []):
                if entry.get("id") != plugin_id:
                    continue
                if version and entry.get("version") != version:
                    continue
                return repo, entry
        raise NotFoundError(
            f"Plugin '{plugin_id}'{f' version {version}' if version else ''} "
            "was not found in any enabled repository. Try syncing repositories."
        )

    @staticmethod
    async def download_artifact(entry: dict) -> bytes:
        url = entry["download_url"]
        if not url.startswith("https://") and not url.startswith("http://localhost"):
            raise PluginError("Plugin downloads must use HTTPS.")
        try:
            async with httpx.AsyncClient(
                timeout=DOWNLOAD_TIMEOUT, follow_redirects=True
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                blob = response.content
        except httpx.HTTPError as exc:
            raise PluginError(f"Plugin download failed: {exc}") from exc
        if len(blob) > MAX_PLUGIN_SIZE:
            raise PluginError("Plugin artifact exceeds the 50 MB limit.")
        digest = hashlib.sha256(blob).hexdigest()
        if digest != entry["sha256"].lower():
            raise PluginError(
                "Checksum mismatch: the downloaded artifact does not match the "
                "repository catalog. Refusing to install."
            )
        return blob
