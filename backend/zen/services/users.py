"""User administration and preferences."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from zen.core.exceptions import ConflictError, NotFoundError, ValidationFailed
from zen.core.pagination import Page, PageParams
from zen.core.security import hash_password, validate_password_strength
from zen.db.models import Role, User, UserPreferences


class UserService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, user_id: str) -> User:
        user = (
            await self.db.execute(
                select(User).options(selectinload(User.preferences)).where(User.id == user_id)
            )
        ).scalar_one_or_none()
        if user is None:
            raise NotFoundError("User not found.")
        return user

    async def list_users(self, page_params: PageParams, *, query: str | None = None) -> Page[User]:
        stmt = select(User)
        if query:
            like = f"%{query.strip()}%"
            stmt = stmt.where(
                User.username.ilike(like)
                | User.display_name.ilike(like)
                | User.email.ilike(like)
            )
        total = (
            await self.db.execute(select(func.count()).select_from(stmt.subquery()))
        ).scalar_one()
        rows = (
            await self.db.execute(
                stmt.order_by(User.created_at.desc())
                .offset(page_params.offset)
                .limit(page_params.size)
            )
        ).scalars().all()
        return Page(items=list(rows), total=total, page=page_params.page, size=page_params.size)

    async def set_role(self, user_id: str, role: str, *, acting_admin: User) -> User:
        if role not in (Role.ADMIN.value, Role.USER.value, Role.READONLY.value):
            raise ValidationFailed(f"Unknown role: {role}")
        user = await self.get(user_id)
        if user.id == acting_admin.id and role != Role.ADMIN.value:
            await self._ensure_other_admin_exists(user.id)
        user.role = role
        await self.db.commit()
        return user

    async def set_active(self, user_id: str, active: bool, *, acting_admin: User) -> User:
        user = await self.get(user_id)
        if user.id == acting_admin.id and not active:
            raise ConflictError("You cannot disable your own account.")
        if not active and user.is_admin:
            await self._ensure_other_admin_exists(user.id)
        user.is_active = active
        await self.db.commit()
        return user

    async def admin_set_password(self, user_id: str, password: str) -> User:
        user = await self.get(user_id)
        problems = validate_password_strength(password)
        if problems:
            raise ValidationFailed(" ".join(problems))
        user.password_hash = hash_password(password)
        await self.db.commit()
        return user

    async def delete(self, user_id: str, *, acting_admin: User) -> None:
        user = await self.get(user_id)
        if user.id == acting_admin.id:
            raise ConflictError("You cannot delete your own account.")
        if user.is_admin:
            await self._ensure_other_admin_exists(user.id)
        await self.db.delete(user)
        await self.db.commit()

    async def _ensure_other_admin_exists(self, excluding_user_id: str) -> None:
        count = (
            await self.db.execute(
                select(func.count())
                .select_from(User)
                .where(
                    User.role == Role.ADMIN.value,
                    User.is_active.is_(True),
                    User.id != excluding_user_id,
                )
            )
        ).scalar_one()
        if count == 0:
            raise ConflictError("The instance must retain at least one active administrator.")

    # ------------------------------------------------------------------
    # Preferences (Layer 3)
    # ------------------------------------------------------------------

    async def get_preferences(self, user: User) -> UserPreferences:
        prefs = await self.db.get(UserPreferences, user.id)
        if prefs is None:
            prefs = UserPreferences(user_id=user.id)
            self.db.add(prefs)
            await self.db.commit()
            await self.db.refresh(prefs)
        return prefs

    async def update_preferences(self, user: User, fields: dict) -> UserPreferences:
        prefs = await self.get_preferences(user)
        if "theme" in fields and fields["theme"] is not None:
            if fields["theme"] not in ("system", "light", "dark", "amoled"):
                raise ValidationFailed("Invalid theme.")
            prefs.theme = fields["theme"]
        if "accent" in fields and fields["accent"] is not None:
            prefs.accent = str(fields["accent"])[:32]
        if "default_mode" in fields and fields["default_mode"] is not None:
            if fields["default_mode"] not in ("normal", "privacy", "focus", "research"):
                raise ValidationFailed("Invalid default mode.")
            prefs.default_mode = fields["default_mode"]
        if "default_profile_id" in fields:
            prefs.default_profile_id = fields["default_profile_id"]
        if "open_links_new_tab" in fields and fields["open_links_new_tab"] is not None:
            prefs.open_links_new_tab = bool(fields["open_links_new_tab"])
        for json_field in ("keyboard_shortcuts", "dashboard_layout", "extra"):
            if json_field in fields and fields[json_field] is not None:
                if not isinstance(fields[json_field], dict):
                    raise ValidationFailed(f"{json_field} must be an object.")
                setattr(prefs, json_field, fields[json_field])
        await self.db.commit()
        await self.db.refresh(prefs)
        return prefs

    async def update_profile(self, user: User, fields: dict) -> User:
        if "display_name" in fields and fields["display_name"] is not None:
            user.display_name = str(fields["display_name"]).strip()[:128]
        if "email" in fields:
            email = (fields["email"] or "").strip().lower() or None
            if email and "@" not in email:
                raise ValidationFailed("Invalid email address.")
            user.email = email
        await self.db.commit()
        return user
