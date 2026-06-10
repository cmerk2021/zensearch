"""Search domain: history, click signals, ranking rules, provider config."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from zen.db.base import Base, new_uuid, utcnow


class SearchMode(str, enum.Enum):
    NORMAL = "normal"
    PRIVACY = "privacy"
    FOCUS = "focus"
    RESEARCH = "research"


class SearchHistory(Base):
    __tablename__ = "search_history"
    __table_args__ = (Index("ix_search_history_user_created", "user_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    workspace_id: Mapped[str | None] = mapped_column(
        ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True, index=True
    )
    query: Mapped[str] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(String(16), default=SearchMode.NORMAL.value)
    profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("search_profiles.id", ondelete="SET NULL"), nullable=True
    )
    providers: Mapped[list] = mapped_column(default=list)
    result_count: Mapped[int] = mapped_column(default=0)
    duration_ms: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)


class ClickEvent(Base):
    """Result-click signal used by the personal ranking factor."""

    __tablename__ = "click_events"
    __table_args__ = (Index("ix_click_events_user_domain", "user_id", "domain"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    query: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(Text)
    domain: Mapped[str] = mapped_column(String(255), default="", index=True)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)


class RuleAction(str, enum.Enum):
    BOOST = "boost"
    LOWER = "lower"
    PIN = "pin"
    BLOCK = "block"


class RuleScope(str, enum.Enum):
    INSTANCE = "instance"
    PROFILE = "profile"
    USER = "user"


class DomainRule(Base):
    """Kagi-style domain ranking control at instance/profile/user scope."""

    __tablename__ = "domain_rules"
    __table_args__ = (Index("ix_domain_rules_scope", "scope", "profile_id", "user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    domain: Mapped[str] = mapped_column(String(255), index=True)
    action: Mapped[str] = mapped_column(String(16))
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    scope: Mapped[str] = mapped_column(String(16), default=RuleScope.INSTANCE.value)
    profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("search_profiles.id", ondelete="CASCADE"), nullable=True
    )
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    created_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class ProviderConfig(Base):
    """Admin-managed per-provider settings (Layer 2)."""

    __tablename__ = "provider_configs"

    slug: Mapped[str] = mapped_column(String(64), primary_key=True)
    enabled: Mapped[bool] = mapped_column(default=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    timeout_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    api_key_encrypted: Mapped[str] = mapped_column(Text, default="")
    config: Mapped[dict] = mapped_column(default=dict)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)
