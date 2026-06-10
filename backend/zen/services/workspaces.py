"""Workspace service: research workspaces and their contents."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from zen.core.exceptions import NotFoundError, PermissionDeniedError, ValidationFailed
from zen.db.models import (
    Bookmark,
    Note,
    SearchHistory,
    User,
    Workspace,
    WorkspaceStatus,
)
from zen.services.settings import SettingsService


class WorkspaceService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_for_user(self, user: User, *, include_archived: bool = False) -> list[Workspace]:
        query = select(Workspace).where(Workspace.owner_id == user.id)
        if not include_archived:
            query = query.where(Workspace.status == WorkspaceStatus.ACTIVE.value)
        query = query.order_by(Workspace.updated_at.desc())
        return list((await self.db.execute(query)).scalars().all())

    async def get_owned(self, workspace_id: str, user: User) -> Workspace:
        workspace = await self.db.get(Workspace, workspace_id)
        if workspace is None:
            raise NotFoundError("Workspace not found.")
        if workspace.owner_id != user.id and not user.is_admin:
            raise PermissionDeniedError("You do not have access to this workspace.")
        return workspace

    async def create(
        self,
        user: User,
        *,
        name: str,
        description: str = "",
        icon: str = "folder",
        color: str = "",
    ) -> Workspace:
        name = name.strip()
        if not name:
            raise ValidationFailed("Workspace name is required.")
        max_per_user = int(await SettingsService(self.db).get("workspaces.max_per_user", 0))
        if max_per_user:
            count = (
                await self.db.execute(
                    select(func.count())
                    .select_from(Workspace)
                    .where(Workspace.owner_id == user.id)
                )
            ).scalar_one()
            if count >= max_per_user:
                raise ValidationFailed(
                    f"Workspace limit reached ({max_per_user} per user on this instance)."
                )
        workspace = Workspace(
            owner_id=user.id, name=name, description=description, icon=icon, color=color
        )
        self.db.add(workspace)
        await self.db.commit()
        await self.db.refresh(workspace)
        return workspace

    async def update(self, workspace_id: str, user: User, fields: dict) -> Workspace:
        workspace = await self.get_owned(workspace_id, user)
        allowed = {"name", "description", "icon", "color", "status", "settings"}
        for key, value in fields.items():
            if key not in allowed or value is None:
                continue
            if key == "name":
                value = str(value).strip()
                if not value:
                    raise ValidationFailed("Workspace name cannot be empty.")
            if key == "status" and value not in (
                WorkspaceStatus.ACTIVE.value,
                WorkspaceStatus.ARCHIVED.value,
            ):
                raise ValidationFailed("Invalid workspace status.")
            setattr(workspace, key, value)
        await self.db.commit()
        await self.db.refresh(workspace)
        return workspace

    async def delete(self, workspace_id: str, user: User) -> None:
        workspace = await self.get_owned(workspace_id, user)
        # Detach contents (SET NULL semantics preserved explicitly for clarity).
        for bookmark in (
            await self.db.execute(select(Bookmark).where(Bookmark.workspace_id == workspace.id))
        ).scalars():
            bookmark.workspace_id = None
        for note in (
            await self.db.execute(select(Note).where(Note.workspace_id == workspace.id))
        ).scalars():
            note.workspace_id = None
        await self.db.delete(workspace)
        await self.db.commit()

    async def overview(self, workspace_id: str, user: User) -> dict:
        workspace = await self.get_owned(workspace_id, user)
        bookmark_count = (
            await self.db.execute(
                select(func.count())
                .select_from(Bookmark)
                .where(Bookmark.workspace_id == workspace.id)
            )
        ).scalar_one()
        note_count = (
            await self.db.execute(
                select(func.count()).select_from(Note).where(Note.workspace_id == workspace.id)
            )
        ).scalar_one()
        search_count = (
            await self.db.execute(
                select(func.count())
                .select_from(SearchHistory)
                .where(SearchHistory.workspace_id == workspace.id)
            )
        ).scalar_one()
        recent_searches = (
            await self.db.execute(
                select(SearchHistory)
                .where(SearchHistory.workspace_id == workspace.id)
                .order_by(SearchHistory.created_at.desc())
                .limit(10)
            )
        ).scalars().all()
        return {
            "workspace": workspace,
            "bookmark_count": bookmark_count,
            "note_count": note_count,
            "search_count": search_count,
            "recent_searches": list(recent_searches),
        }
