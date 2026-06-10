"""Tag service: hierarchical tags shared by bookmarks and notes."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from zen.core.exceptions import NotFoundError, PermissionDeniedError, ValidationFailed
from zen.db.models import Tag, User, bookmark_tags, note_tags
from zen.services.collections import slugify

MAX_TAG_DEPTH = 5


class TagService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_for_user(self, user: User) -> list[dict]:
        tags = (
            await self.db.execute(
                select(Tag).where(Tag.owner_id == user.id).order_by(Tag.name)
            )
        ).scalars().all()
        bookmark_counts = dict(
            (
                await self.db.execute(
                    select(bookmark_tags.c.tag_id, func.count())
                    .group_by(bookmark_tags.c.tag_id)
                )
            ).all()
        )
        note_counts = dict(
            (
                await self.db.execute(
                    select(note_tags.c.tag_id, func.count()).group_by(note_tags.c.tag_id)
                )
            ).all()
        )
        return [
            {
                "tag": tag,
                "bookmark_count": bookmark_counts.get(tag.id, 0),
                "note_count": note_counts.get(tag.id, 0),
            }
            for tag in tags
        ]

    async def get_owned(self, tag_id: str, user: User) -> Tag:
        tag = await self.db.get(Tag, tag_id)
        if tag is None:
            raise NotFoundError("Tag not found.")
        if tag.owner_id != user.id and not user.is_admin:
            raise PermissionDeniedError("You do not have access to this tag.")
        return tag

    async def create(
        self, user: User, *, name: str, parent_id: str | None = None, color: str = ""
    ) -> Tag:
        name = name.strip()
        if not name:
            raise ValidationFailed("Tag name is required.")
        if parent_id:
            parent = await self.get_owned(parent_id, user)
            depth = 1
            cursor = parent
            while cursor.parent_id is not None and depth <= MAX_TAG_DEPTH:
                cursor = await self.db.get(Tag, cursor.parent_id)
                depth += 1
            if depth >= MAX_TAG_DEPTH:
                raise ValidationFailed(f"Maximum tag depth is {MAX_TAG_DEPTH}.")
        slug = await self._unique_slug(user, slugify(name))
        tag = Tag(owner_id=user.id, name=name, slug=slug, parent_id=parent_id, color=color)
        self.db.add(tag)
        await self.db.commit()
        await self.db.refresh(tag)
        return tag

    async def update(self, tag_id: str, user: User, fields: dict) -> Tag:
        tag = await self.get_owned(tag_id, user)
        if fields.get("name"):
            tag.name = fields["name"].strip()
        if "color" in fields and fields["color"] is not None:
            tag.color = fields["color"]
        if "parent_id" in fields:
            parent_id = fields["parent_id"]
            if parent_id:
                if parent_id == tag.id:
                    raise ValidationFailed("A tag cannot be its own parent.")
                parent = await self.get_owned(parent_id, user)
                # Reject cycles.
                cursor = parent
                while cursor is not None:
                    if cursor.id == tag.id:
                        raise ValidationFailed("Tag hierarchy cannot contain cycles.")
                    cursor = (
                        await self.db.get(Tag, cursor.parent_id) if cursor.parent_id else None
                    )
            tag.parent_id = parent_id
        await self.db.commit()
        await self.db.refresh(tag)
        return tag

    async def delete(self, tag_id: str, user: User) -> None:
        tag = await self.get_owned(tag_id, user)
        await self.db.delete(tag)
        await self.db.commit()

    async def _unique_slug(self, user: User, base: str) -> str:
        candidate = base
        suffix = 1
        while True:
            existing = (
                await self.db.execute(
                    select(Tag).where(Tag.owner_id == user.id, Tag.slug == candidate)
                )
            ).scalar_one_or_none()
            if existing is None:
                return candidate
            suffix += 1
            candidate = f"{base}-{suffix}"
