"""User, session, and preference models."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from zen.db.base import Base, TimestampMixin, new_uuid, utcnow


class Role(str, enum.Enum):
    ADMIN = "admin"
    USER = "user"
    READONLY = "readonly"


class AuthSource(str, enum.Enum):
    LOCAL = "local"
    OIDC = "oidc"
    LDAP = "ldap"


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str] = mapped_column(String(128), default="")
    role: Mapped[str] = mapped_column(String(16), default=Role.USER.value, index=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    auth_source: Mapped[str] = mapped_column(String(16), default=AuthSource.LOCAL.value)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    last_login_at: Mapped[datetime | None] = mapped_column(nullable=True)

    preferences: Mapped[UserPreferences | None] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    sessions: Mapped[list[UserSession]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def is_admin(self) -> bool:
        return self.role == Role.ADMIN.value

    @property
    def can_write(self) -> bool:
        return self.role in (Role.ADMIN.value, Role.USER.value)


class UserSession(Base):
    __tablename__ = "user_sessions"
    __table_args__ = (Index("ix_user_sessions_user_expires", "user_id", "expires_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    user_agent: Mapped[str] = mapped_column(Text, default="")
    ip_address: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(nullable=True)

    user: Mapped[User] = relationship(back_populates="sessions")


class UserPreferences(Base):
    __tablename__ = "user_preferences"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    theme: Mapped[str] = mapped_column(String(16), default="system")
    accent: Mapped[str] = mapped_column(String(32), default="zen")
    default_mode: Mapped[str] = mapped_column(String(16), default="normal")
    default_profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("search_profiles.id", ondelete="SET NULL"), nullable=True
    )
    open_links_new_tab: Mapped[bool] = mapped_column(default=True)
    keyboard_shortcuts: Mapped[dict] = mapped_column(default=dict)
    dashboard_layout: Mapped[dict] = mapped_column(default=dict)
    extra: Mapped[dict] = mapped_column(default=dict)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="preferences")
