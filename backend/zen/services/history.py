"""Search history service: listing, clearing, retention enforcement."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from zen.core.pagination import Page, PageParams
from zen.db.base import utcnow
from zen.db.models import ClickEvent, SearchHistory, User
from zen.services.settings import SettingsService


class HistoryService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_for_user(
        self,
        user: User,
        page_params: PageParams,
        *,
        query: str | None = None,
        workspace_id: str | None = None,
    ) -> Page[SearchHistory]:
        stmt = select(SearchHistory).where(SearchHistory.user_id == user.id)
        if workspace_id:
            stmt = stmt.where(SearchHistory.workspace_id == workspace_id)
        if query:
            stmt = stmt.where(SearchHistory.query.ilike(f"%{query.strip()}%"))
        total = (
            await self.db.execute(select(func.count()).select_from(stmt.subquery()))
        ).scalar_one()
        rows = (
            await self.db.execute(
                stmt.order_by(SearchHistory.created_at.desc())
                .offset(page_params.offset)
                .limit(page_params.size)
            )
        ).scalars().all()
        return Page(items=list(rows), total=total, page=page_params.page, size=page_params.size)

    async def clear_for_user(self, user: User) -> int:
        result = await self.db.execute(
            delete(SearchHistory).where(SearchHistory.user_id == user.id)
        )
        await self.db.execute(delete(ClickEvent).where(ClickEvent.user_id == user.id))
        await self.db.commit()
        return result.rowcount or 0

    async def delete_entry(self, entry_id: str, user: User) -> None:
        await self.db.execute(
            delete(SearchHistory).where(
                SearchHistory.id == entry_id, SearchHistory.user_id == user.id
            )
        )
        await self.db.commit()

    async def enforce_retention(self) -> int:
        """Scheduled task: delete history older than the configured retention."""
        days = int(
            await SettingsService(self.db).get("privacy.search_history_retention_days", 90)
        )
        if days <= 0:
            return 0
        cutoff = utcnow() - timedelta(days=days)
        result = await self.db.execute(
            delete(SearchHistory).where(SearchHistory.created_at < cutoff)
        )
        await self.db.execute(delete(ClickEvent).where(ClickEvent.created_at < cutoff))
        await self.db.commit()
        return result.rowcount or 0
