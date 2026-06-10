"""Search profile service (admin-managed presets users select from)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zen.core.exceptions import ConflictError, NotFoundError, ValidationFailed
from zen.db.models import SearchProfile
from zen.search.providers import all_providers
from zen.services.collections import slugify


class ProfileService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_active(self) -> list[SearchProfile]:
        rows = (
            await self.db.execute(
                select(SearchProfile)
                .where(SearchProfile.is_active.is_(True))
                .order_by(SearchProfile.position, SearchProfile.name)
            )
        ).scalars().all()
        return list(rows)

    async def list_all(self) -> list[SearchProfile]:
        rows = (
            await self.db.execute(
                select(SearchProfile).order_by(SearchProfile.position, SearchProfile.name)
            )
        ).scalars().all()
        return list(rows)

    async def get(self, profile_id: str) -> SearchProfile:
        profile = await self.db.get(SearchProfile, profile_id)
        if profile is None:
            raise NotFoundError("Search profile not found.")
        return profile

    async def get_by_slug(self, slug: str) -> SearchProfile:
        profile = (
            await self.db.execute(select(SearchProfile).where(SearchProfile.slug == slug))
        ).scalar_one_or_none()
        if profile is None:
            raise NotFoundError("Search profile not found.")
        return profile

    async def create(self, fields: dict) -> SearchProfile:
        name = (fields.get("name") or "").strip()
        if not name:
            raise ValidationFailed("Profile name is required.")
        slug = fields.get("slug") or slugify(name)
        existing = (
            await self.db.execute(select(SearchProfile).where(SearchProfile.slug == slug))
        ).scalar_one_or_none()
        if existing is not None:
            raise ConflictError(f"A profile with slug '{slug}' already exists.")
        self._validate_providers(fields.get("providers") or [])
        profile = SearchProfile(
            slug=slug,
            name=name,
            description=fields.get("description", ""),
            icon=fields.get("icon", "search"),
            providers=fields.get("providers") or [],
            ranking=fields.get("ranking") or {},
            filters=fields.get("filters") or {},
            ai=fields.get("ai") or {},
            workspace=fields.get("workspace") or {},
            ui=fields.get("ui") or {},
            is_default=bool(fields.get("is_default", False)),
            is_active=bool(fields.get("is_active", True)),
            position=int(fields.get("position", 0)),
        )
        if profile.is_default:
            await self._clear_default()
        self.db.add(profile)
        await self.db.commit()
        await self.db.refresh(profile)
        return profile

    async def update(self, profile_id: str, fields: dict) -> SearchProfile:
        profile = await self.get(profile_id)
        if "providers" in fields and fields["providers"] is not None:
            self._validate_providers(fields["providers"])
            profile.providers = fields["providers"]
        for key in ("name", "description", "icon", "ranking", "filters", "ai", "workspace", "ui"):
            if key in fields and fields[key] is not None:
                setattr(profile, key, fields[key])
        if "position" in fields and fields["position"] is not None:
            profile.position = int(fields["position"])
        if "is_active" in fields and fields["is_active"] is not None:
            profile.is_active = bool(fields["is_active"])
        if fields.get("is_default"):
            await self._clear_default()
            profile.is_default = True
        elif "is_default" in fields and fields["is_default"] is False:
            profile.is_default = False
        await self.db.commit()
        await self.db.refresh(profile)
        return profile

    async def delete(self, profile_id: str) -> None:
        profile = await self.get(profile_id)
        if profile.is_default:
            raise ConflictError("The default profile cannot be deleted. Set another default first.")
        await self.db.delete(profile)
        await self.db.commit()

    async def _clear_default(self) -> None:
        rows = (
            await self.db.execute(
                select(SearchProfile).where(SearchProfile.is_default.is_(True))
            )
        ).scalars().all()
        for row in rows:
            row.is_default = False

    @staticmethod
    def _validate_providers(providers: list) -> None:
        if not isinstance(providers, list):
            raise ValidationFailed("providers must be a list of provider slugs.")
        known = set(all_providers().keys())
        unknown = [p for p in providers if p not in known]
        if unknown:
            raise ValidationFailed(f"Unknown providers: {', '.join(unknown)}")
