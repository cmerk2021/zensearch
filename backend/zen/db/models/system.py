"""System domain: instance settings, profiles, plugins, audit log."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from zen.db.base import Base, TimestampMixin, new_uuid, utcnow


class InstanceSetting(Base):
    """Layer-2 key/value store. Values are JSON documents (ADR-0003)."""

    __tablename__ = "instance_settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[dict] = mapped_column(default=dict)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)
    updated_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class SearchProfile(TimestampMixin, Base):
    """Admin-managed search behavior preset users can select."""

    __tablename__ = "search_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    icon: Mapped[str] = mapped_column(String(64), default="search")
    providers: Mapped[list] = mapped_column(default=list)
    """Provider slugs enabled for this profile. Empty list = all enabled providers."""
    ranking: Mapped[dict] = mapped_column(default=dict)
    """{"factor_weights": {...}, "domain_weights": {"domain": multiplier}}"""
    filters: Mapped[dict] = mapped_column(default=dict)
    """{"blocked_domains": [...], "focus_categories": [...], "safe_search": bool}"""
    ai: Mapped[dict] = mapped_column(default=dict)
    """{"enabled": bool, "auto_summarize": bool, "query_expansion": bool}"""
    workspace: Mapped[dict] = mapped_column(default=dict)
    """{"auto_associate": bool, "default_workspace_id": str | None}"""
    ui: Mapped[dict] = mapped_column(default=dict)
    """{"default_mode": str, "results_density": "comfortable"|"compact"}"""
    is_default: Mapped[bool] = mapped_column(default=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    position: Mapped[int] = mapped_column(default=0)


class PluginStatus(str, enum.Enum):
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"


class Plugin(Base):
    __tablename__ = "plugins"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    slug: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    version: Mapped[str] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(Text, default="")
    author: Mapped[str] = mapped_column(String(160), default="")
    license: Mapped[str] = mapped_column(String(64), default="")
    homepage: Mapped[str] = mapped_column(Text, default="")
    types: Mapped[list] = mapped_column(default=list)
    manifest: Mapped[dict] = mapped_column(default=dict)
    source_repo: Mapped[str | None] = mapped_column(String(160), nullable=True)
    checksum: Mapped[str] = mapped_column(String(128), default="")
    status: Mapped[str] = mapped_column(String(16), default=PluginStatus.ENABLED.value)
    error: Mapped[str] = mapped_column(Text, default="")
    previous_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    installed_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class RepositoryKind(str, enum.Enum):
    OFFICIAL = "official"
    COMMUNITY = "community"
    PRIVATE = "private"


class PluginRepository(Base):
    __tablename__ = "plugin_repositories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(120))
    url: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(16), default=RepositoryKind.COMMUNITY.value)
    enabled: Mapped[bool] = mapped_column(default=True)
    catalog: Mapped[dict] = mapped_column(default=dict)
    last_synced_at: Mapped[datetime | None] = mapped_column(nullable=True)
    added_at: Mapped[datetime] = mapped_column(default=utcnow)


class AuditLogEntry(Base):
    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_log_action_created", "action", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    actor_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(96), index=True)
    target_type: Mapped[str] = mapped_column(String(64), default="")
    target_id: Mapped[str] = mapped_column(String(64), default="")
    data: Mapped[dict] = mapped_column(default=dict)
    ip_address: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)
