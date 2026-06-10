"""Note service: markdown notes with revisions, links, and search."""

from __future__ import annotations

import re

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from zen.core.exceptions import NotFoundError, PermissionDeniedError, ValidationFailed
from zen.core.pagination import Page, PageParams
from zen.db.models import Bookmark, Note, NoteLink, NoteRevision, Tag, User

MAX_REVISIONS_PER_NOTE = 50

_MD_SYNTAX = re.compile(r"(```.*?```|`[^`]*`|\[(.*?)\]\([^)]*\)|[#>*_~\-|!])", re.DOTALL)


def strip_markdown(content: str) -> str:
    """Plain-text projection used for searching note content."""

    def _replace(match: re.Match) -> str:
        if match.group(2) is not None:
            return match.group(2)
        token = match.group(1)
        if token.startswith("```") or token.startswith("`"):
            return " "
        return " "

    text = _MD_SYNTAX.sub(_replace, content)
    return re.sub(r"\s+", " ", text).strip()


class NoteService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_owned(self, note_id: str, user: User) -> Note:
        note = (
            await self.db.execute(
                select(Note)
                .options(selectinload(Note.tags), selectinload(Note.links))
                .where(Note.id == note_id)
            )
        ).scalar_one_or_none()
        if note is None:
            raise NotFoundError("Note not found.")
        if note.owner_id != user.id and not user.is_admin:
            raise PermissionDeniedError("You do not have access to this note.")
        return note

    async def create(
        self,
        user: User,
        *,
        title: str = "",
        content: str = "",
        workspace_id: str | None = None,
        tag_ids: list[str] | None = None,
    ) -> Note:
        note = Note(
            owner_id=user.id,
            workspace_id=workspace_id,
            title=title.strip() or "Untitled note",
            content=content,
            content_text=strip_markdown(content),
        )
        if tag_ids:
            note.tags = await self._resolve_tags(user, tag_ids)
        self.db.add(note)
        await self.db.commit()
        return await self.get_owned(note.id, user)

    async def update(self, note_id: str, user: User, fields: dict) -> Note:
        note = await self.get_owned(note_id, user)
        content_changed = "content" in fields and fields["content"] is not None
        title_changed = "title" in fields and fields["title"] is not None
        if content_changed or title_changed:
            # Snapshot the current state before mutating.
            self.db.add(
                NoteRevision(
                    note_id=note.id,
                    title=note.title,
                    content=note.content,
                    created_by=user.id,
                )
            )
            await self._prune_revisions(note.id)
        if title_changed:
            note.title = fields["title"].strip() or "Untitled note"
        if content_changed:
            note.content = fields["content"]
            note.content_text = strip_markdown(fields["content"])
        if "workspace_id" in fields:
            note.workspace_id = fields["workspace_id"]
        if "is_pinned" in fields and fields["is_pinned"] is not None:
            note.is_pinned = bool(fields["is_pinned"])
        if "tag_ids" in fields and fields["tag_ids"] is not None:
            note.tags = await self._resolve_tags(user, fields["tag_ids"])
        await self.db.commit()
        return await self.get_owned(note.id, user)

    async def delete(self, note_id: str, user: User) -> None:
        note = await self.get_owned(note_id, user)
        await self.db.delete(note)
        await self.db.commit()

    async def list_for_user(
        self,
        user: User,
        page_params: PageParams,
        *,
        query: str | None = None,
        workspace_id: str | None = None,
        tag_id: str | None = None,
    ) -> Page[Note]:
        stmt = (
            select(Note)
            .options(selectinload(Note.tags))
            .where(Note.owner_id == user.id)
        )
        if workspace_id:
            stmt = stmt.where(Note.workspace_id == workspace_id)
        if tag_id:
            stmt = stmt.where(Note.tags.any(Tag.id == tag_id))
        if query:
            like = f"%{query.strip()}%"
            stmt = stmt.where(or_(Note.title.ilike(like), Note.content_text.ilike(like)))
        total = (
            await self.db.execute(select(func.count()).select_from(stmt.subquery()))
        ).scalar_one()
        rows = (
            await self.db.execute(
                stmt.order_by(Note.is_pinned.desc(), Note.updated_at.desc())
                .offset(page_params.offset)
                .limit(page_params.size)
            )
        ).scalars().all()
        return Page(items=list(rows), total=total, page=page_params.page, size=page_params.size)

    # ------------------------------------------------------------------
    # Revisions
    # ------------------------------------------------------------------

    async def revisions(self, note_id: str, user: User) -> list[NoteRevision]:
        await self.get_owned(note_id, user)
        rows = (
            await self.db.execute(
                select(NoteRevision)
                .where(NoteRevision.note_id == note_id)
                .order_by(NoteRevision.created_at.desc())
            )
        ).scalars().all()
        return list(rows)

    async def restore_revision(self, note_id: str, revision_id: str, user: User) -> Note:
        note = await self.get_owned(note_id, user)
        revision = await self.db.get(NoteRevision, revision_id)
        if revision is None or revision.note_id != note.id:
            raise NotFoundError("Revision not found.")
        self.db.add(
            NoteRevision(
                note_id=note.id, title=note.title, content=note.content, created_by=user.id
            )
        )
        note.title = revision.title
        note.content = revision.content
        note.content_text = strip_markdown(revision.content)
        await self.db.commit()
        return await self.get_owned(note.id, user)

    async def _prune_revisions(self, note_id: str) -> None:
        ids = (
            await self.db.execute(
                select(NoteRevision.id)
                .where(NoteRevision.note_id == note_id)
                .order_by(NoteRevision.created_at.desc())
                .offset(MAX_REVISIONS_PER_NOTE - 1)
            )
        ).scalars().all()
        if ids:
            from sqlalchemy import delete

            await self.db.execute(delete(NoteRevision).where(NoteRevision.id.in_(ids)))

    # ------------------------------------------------------------------
    # Links (note ↔ note / bookmark)
    # ------------------------------------------------------------------

    async def add_link(self, note_id: str, user: User, *, target_type: str, target_id: str) -> NoteLink:
        note = await self.get_owned(note_id, user)
        if target_type not in ("note", "bookmark"):
            raise ValidationFailed("target_type must be 'note' or 'bookmark'.")
        if target_type == "note":
            target = await self.db.get(Note, target_id)
            if target is None or target.owner_id != user.id:
                raise NotFoundError("Target note not found.")
            if target.id == note.id:
                raise ValidationFailed("A note cannot link to itself.")
        else:
            target = await self.db.get(Bookmark, target_id)
            if target is None or target.owner_id != user.id:
                raise NotFoundError("Target bookmark not found.")
        existing = (
            await self.db.execute(
                select(NoteLink).where(
                    NoteLink.note_id == note.id,
                    NoteLink.target_type == target_type,
                    NoteLink.target_id == target_id,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        link = NoteLink(note_id=note.id, target_type=target_type, target_id=target_id)
        self.db.add(link)
        await self.db.commit()
        await self.db.refresh(link)
        return link

    async def remove_link(self, note_id: str, link_id: str, user: User) -> None:
        await self.get_owned(note_id, user)
        link = await self.db.get(NoteLink, link_id)
        if link is not None and link.note_id == note_id:
            await self.db.delete(link)
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
