"""Bookmark service — the unified knowledge object (ADR-0008)."""

from __future__ import annotations

import hashlib

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from zen.core.exceptions import NotFoundError, PermissionDeniedError, ValidationFailed
from zen.core.pagination import Page, PageParams
from zen.db.models import Bookmark, ClickEvent, Tag, User
from zen.search.pipeline import canonicalize_url, extract_domain, favicon_url_for


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


class BookmarkService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_owned(self, bookmark_id: str, user: User) -> Bookmark:
        bookmark = (
            await self.db.execute(
                select(Bookmark)
                .options(selectinload(Bookmark.tags))
                .where(Bookmark.id == bookmark_id)
            )
        ).scalar_one_or_none()
        if bookmark is None:
            raise NotFoundError("Bookmark not found.")
        if bookmark.owner_id != user.id and not user.is_admin:
            raise PermissionDeniedError("You do not have access to this bookmark.")
        return bookmark

    async def create(
        self,
        user: User,
        *,
        url: str,
        title: str = "",
        description: str = "",
        snippet: str = "",
        workspace_id: str | None = None,
        source_provider: str | None = None,
        source_query: str | None = None,
        tag_ids: list[str] | None = None,
    ) -> Bookmark:
        canonical = canonicalize_url(url)
        if not canonical:
            raise ValidationFailed("A valid http(s) URL is required.")
        url_hash = _url_hash(canonical)
        existing = (
            await self.db.execute(
                select(Bookmark)
                .options(selectinload(Bookmark.tags))
                .where(Bookmark.owner_id == user.id, Bookmark.url_hash == url_hash)
            )
        ).scalar_one_or_none()
        if existing is not None:
            # Idempotent save: update provenance/workspace instead of duplicating.
            if workspace_id and not existing.workspace_id:
                existing.workspace_id = workspace_id
            if source_provider and not existing.source_provider:
                existing.source_provider = source_provider
                existing.source_query = source_query
            if title and not existing.title:
                existing.title = title
            if snippet and not existing.snippet:
                existing.snippet = snippet
            await self.db.commit()
            await self.db.refresh(existing)
            return existing
        domain = extract_domain(canonical)
        bookmark = Bookmark(
            owner_id=user.id,
            workspace_id=workspace_id,
            url=canonical,
            url_hash=url_hash,
            domain=domain,
            title=title.strip() or canonical,
            description=description,
            snippet=snippet,
            favicon_url=favicon_url_for(domain),
            source_provider=source_provider,
            source_query=source_query,
        )
        if tag_ids:
            bookmark.tags = await self._resolve_tags(user, tag_ids)
        self.db.add(bookmark)
        await self.db.commit()
        return await self.get_owned(bookmark.id, user)

    async def update(self, bookmark_id: str, user: User, fields: dict) -> Bookmark:
        bookmark = await self.get_owned(bookmark_id, user)
        simple = {"title", "description", "snippet", "is_favorite", "is_archived", "workspace_id"}
        for key, value in fields.items():
            if key in simple and value is not None:
                setattr(bookmark, key, value)
        if fields.get("url"):
            canonical = canonicalize_url(fields["url"])
            if not canonical:
                raise ValidationFailed("A valid http(s) URL is required.")
            bookmark.url = canonical
            bookmark.url_hash = _url_hash(canonical)
            bookmark.domain = extract_domain(canonical)
            bookmark.favicon_url = favicon_url_for(bookmark.domain)
        if "tag_ids" in fields and fields["tag_ids"] is not None:
            bookmark.tags = await self._resolve_tags(user, fields["tag_ids"])
        await self.db.commit()
        return await self.get_owned(bookmark.id, user)

    async def delete(self, bookmark_id: str, user: User) -> None:
        bookmark = await self.get_owned(bookmark_id, user)
        await self.db.delete(bookmark)
        await self.db.commit()

    async def list_for_user(
        self,
        user: User,
        page_params: PageParams,
        *,
        query: str | None = None,
        workspace_id: str | None = None,
        tag_id: str | None = None,
        domain: str | None = None,
        favorites_only: bool = False,
        include_archived: bool = False,
    ) -> Page[Bookmark]:
        stmt = (
            select(Bookmark)
            .options(selectinload(Bookmark.tags))
            .where(Bookmark.owner_id == user.id)
        )
        if not include_archived:
            stmt = stmt.where(Bookmark.is_archived.is_(False))
        if workspace_id:
            stmt = stmt.where(Bookmark.workspace_id == workspace_id)
        if domain:
            stmt = stmt.where(Bookmark.domain == domain.lower())
        if favorites_only:
            stmt = stmt.where(Bookmark.is_favorite.is_(True))
        if tag_id:
            stmt = stmt.where(Bookmark.tags.any(Tag.id == tag_id))
        if query:
            like = f"%{query.strip()}%"
            stmt = stmt.where(
                or_(
                    Bookmark.title.ilike(like),
                    Bookmark.description.ilike(like),
                    Bookmark.snippet.ilike(like),
                    Bookmark.url.ilike(like),
                )
            )
        total = (
            await self.db.execute(select(func.count()).select_from(stmt.subquery()))
        ).scalar_one()
        rows = (
            await self.db.execute(
                stmt.order_by(Bookmark.created_at.desc())
                .offset(page_params.offset)
                .limit(page_params.size)
            )
        ).scalars().all()
        return Page(items=list(rows), total=total, page=page_params.page, size=page_params.size)

    async def record_click(
        self, user: User | None, *, url: str, query: str | None, provider: str | None
    ) -> None:
        """Record a result click as a ranking signal (honors privacy settings)."""
        from zen.services.settings import SettingsService

        if user is None:
            return
        if not await SettingsService(self.db).get("privacy.click_tracking_enabled", True):
            return
        canonical = canonicalize_url(url)
        if not canonical:
            return
        self.db.add(
            ClickEvent(
                user_id=user.id,
                query=query,
                url=canonical,
                domain=extract_domain(canonical),
                provider=provider,
            )
        )
        await self.db.commit()

    async def _resolve_tags(self, user: User, tag_ids: list[str]) -> list[Tag]:
        if not tag_ids:
            return []
        tags = (
            await self.db.execute(
                select(Tag).where(Tag.id.in_(tag_ids), Tag.owner_id == user.id)
            )
        ).scalars().all()
        return list(tags)
