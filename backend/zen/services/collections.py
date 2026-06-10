"""Collection service: manual collections and rule-based smart collections."""

from __future__ import annotations

import re
import unicodedata

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from zen.core.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationFailed,
)
from zen.db.models import Bookmark, Collection, CollectionItem, Tag, User


def slugify(name: str) -> str:
    value = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value or "collection"


#: Smart-collection rule fields → SQLAlchemy filters. Conditions are ANDed.
#: Rules document shape:
#: {"match": "all"|"any", "conditions": [{"field": ..., "operator": ..., "value": ...}]}
SMART_FIELDS = {"domain", "title", "url", "source_provider", "source_query", "is_favorite", "tag"}
SMART_OPERATORS = {"equals", "contains", "starts_with", "ends_with", "is_true", "is_false"}


def validate_rules(rules: dict) -> None:
    if not isinstance(rules, dict):
        raise ValidationFailed("Rules must be an object.")
    match = rules.get("match", "all")
    if match not in ("all", "any"):
        raise ValidationFailed("rules.match must be 'all' or 'any'.")
    conditions = rules.get("conditions", [])
    if not isinstance(conditions, list) or not conditions:
        raise ValidationFailed("rules.conditions must be a non-empty list.")
    for condition in conditions:
        field = condition.get("field")
        operator = condition.get("operator")
        if field not in SMART_FIELDS:
            raise ValidationFailed(f"Unknown rule field: {field}")
        if operator not in SMART_OPERATORS:
            raise ValidationFailed(f"Unknown rule operator: {operator}")
        if operator not in ("is_true", "is_false") and not isinstance(
            condition.get("value"), str
        ):
            raise ValidationFailed(f"Rule on '{field}' requires a string value.")


class CollectionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_for_user(self, user: User) -> list[Collection]:
        rows = (
            await self.db.execute(
                select(Collection)
                .where(Collection.owner_id == user.id)
                .order_by(Collection.position, Collection.name)
            )
        ).scalars().all()
        return list(rows)

    async def get_owned(self, collection_id: str, user: User) -> Collection:
        collection = await self.db.get(Collection, collection_id)
        if collection is None:
            raise NotFoundError("Collection not found.")
        if collection.owner_id != user.id and not user.is_admin:
            raise PermissionDeniedError("You do not have access to this collection.")
        return collection

    async def create(
        self,
        user: User,
        *,
        name: str,
        description: str = "",
        icon: str = "bookmark",
        color: str = "",
        is_smart: bool = False,
        rules: dict | None = None,
    ) -> Collection:
        name = name.strip()
        if not name:
            raise ValidationFailed("Collection name is required.")
        if is_smart:
            validate_rules(rules or {})
        slug = await self._unique_slug(user, slugify(name))
        collection = Collection(
            owner_id=user.id,
            name=name,
            slug=slug,
            description=description,
            icon=icon,
            color=color,
            is_smart=is_smart,
            rules=rules or {},
        )
        self.db.add(collection)
        await self.db.commit()
        await self.db.refresh(collection)
        return collection

    async def update(self, collection_id: str, user: User, fields: dict) -> Collection:
        collection = await self.get_owned(collection_id, user)
        if "rules" in fields and fields["rules"] is not None:
            if collection.is_smart:
                validate_rules(fields["rules"])
            collection.rules = fields["rules"]
        for key in ("name", "description", "icon", "color", "position"):
            if key in fields and fields[key] is not None:
                setattr(collection, key, fields[key])
        await self.db.commit()
        await self.db.refresh(collection)
        return collection

    async def delete(self, collection_id: str, user: User) -> None:
        collection = await self.get_owned(collection_id, user)
        await self.db.delete(collection)
        await self.db.commit()

    # ------------------------------------------------------------------
    # Membership
    # ------------------------------------------------------------------

    async def add_bookmark(self, collection_id: str, bookmark_id: str, user: User) -> None:
        collection = await self.get_owned(collection_id, user)
        if collection.is_smart:
            raise ConflictError("Smart collections populate automatically.")
        bookmark = await self.db.get(Bookmark, bookmark_id)
        if bookmark is None or bookmark.owner_id != user.id:
            raise NotFoundError("Bookmark not found.")
        existing = await self.db.get(CollectionItem, (collection_id, bookmark_id))
        if existing is not None:
            return
        max_position = (
            await self.db.execute(
                select(func.coalesce(func.max(CollectionItem.position), 0)).where(
                    CollectionItem.collection_id == collection_id
                )
            )
        ).scalar_one()
        self.db.add(
            CollectionItem(
                collection_id=collection_id, bookmark_id=bookmark_id, position=max_position + 1
            )
        )
        await self.db.commit()

    async def remove_bookmark(self, collection_id: str, bookmark_id: str, user: User) -> None:
        collection = await self.get_owned(collection_id, user)
        if collection.is_smart:
            raise ConflictError("Smart collections populate automatically.")
        item = await self.db.get(CollectionItem, (collection_id, bookmark_id))
        if item is not None:
            await self.db.delete(item)
            await self.db.commit()

    async def bookmarks_in(self, collection_id: str, user: User) -> list[Bookmark]:
        collection = await self.get_owned(collection_id, user)
        if collection.is_smart:
            return await self._evaluate_smart(collection, user)
        rows = (
            await self.db.execute(
                select(Bookmark)
                .options(selectinload(Bookmark.tags))
                .join(CollectionItem, CollectionItem.bookmark_id == Bookmark.id)
                .where(CollectionItem.collection_id == collection_id)
                .order_by(CollectionItem.position)
            )
        ).scalars().all()
        return list(rows)

    async def _evaluate_smart(self, collection: Collection, user: User) -> list[Bookmark]:
        rules = collection.rules or {}
        conditions = rules.get("conditions", [])
        clauses = []
        for condition in conditions:
            field = condition.get("field")
            operator = condition.get("operator")
            value = condition.get("value", "")
            if field == "tag":
                tag_clause = Bookmark.tags.any(
                    (Tag.slug == value) if operator == "equals" else Tag.slug.ilike(f"%{value}%")
                )
                clauses.append(tag_clause)
                continue
            if field == "is_favorite":
                clauses.append(
                    Bookmark.is_favorite.is_(operator != "is_false")
                )
                continue
            column = getattr(Bookmark, field, None)
            if column is None:
                continue
            if operator == "equals":
                clauses.append(func.lower(column) == value.lower())
            elif operator == "contains":
                clauses.append(column.ilike(f"%{value}%"))
            elif operator == "starts_with":
                clauses.append(column.ilike(f"{value}%"))
            elif operator == "ends_with":
                clauses.append(column.ilike(f"%{value}"))
        from sqlalchemy import and_

        stmt = (
            select(Bookmark)
            .options(selectinload(Bookmark.tags))
            .where(Bookmark.owner_id == user.id, Bookmark.is_archived.is_(False))
        )
        if clauses:
            combined = or_(*clauses) if rules.get("match") == "any" else and_(*clauses)
            stmt = stmt.where(combined)
        rows = (
            await self.db.execute(stmt.order_by(Bookmark.created_at.desc()).limit(500))
        ).scalars().all()
        return list(rows)

    async def _unique_slug(self, user: User, base: str) -> str:
        candidate = base
        suffix = 1
        while True:
            existing = (
                await self.db.execute(
                    select(Collection).where(
                        Collection.owner_id == user.id, Collection.slug == candidate
                    )
                )
            ).scalar_one_or_none()
            if existing is None:
                return candidate
            suffix += 1
            candidate = f"{base}-{suffix}"
