"""Knowledge domain: workspaces, bookmarks, collections, tags, notes."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Column, ForeignKey, Index, String, Table, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from zen.db.base import Base, TimestampMixin, new_uuid, utcnow


class WorkspaceStatus(str, enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


bookmark_tags = Table(
    "bookmark_tags",
    Base.metadata,
    Column("bookmark_id", ForeignKey("bookmarks.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)

note_tags = Table(
    "note_tags",
    Base.metadata,
    Column("note_id", ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Workspace(TimestampMixin, Base):
    __tablename__ = "workspaces"
    __table_args__ = (Index("ix_workspaces_owner_status", "owner_id", "status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    icon: Mapped[str] = mapped_column(String(64), default="folder")
    color: Mapped[str] = mapped_column(String(16), default="")
    status: Mapped[str] = mapped_column(String(16), default=WorkspaceStatus.ACTIVE.value)
    settings: Mapped[dict] = mapped_column(default=dict)

    bookmarks: Mapped[list[Bookmark]] = relationship(back_populates="workspace")
    notes: Mapped[list[Note]] = relationship(back_populates="workspace")


class Bookmark(TimestampMixin, Base):
    """Unified knowledge object (ADR-0008): manual bookmark or saved result."""

    __tablename__ = "bookmarks"
    __table_args__ = (
        Index("ix_bookmarks_owner_created", "owner_id", "created_at"),
        Index("ix_bookmarks_owner_urlhash", "owner_id", "url_hash"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    workspace_id: Mapped[str | None] = mapped_column(
        ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True, index=True
    )
    url: Mapped[str] = mapped_column(Text)
    url_hash: Mapped[str] = mapped_column(String(64))
    domain: Mapped[str] = mapped_column(String(255), default="", index=True)
    title: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    snippet: Mapped[str] = mapped_column(Text, default="")
    favicon_url: Mapped[str] = mapped_column(Text, default="")
    source_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_favorite: Mapped[bool] = mapped_column(default=False)
    is_archived: Mapped[bool] = mapped_column(default=False)
    meta: Mapped[dict] = mapped_column(default=dict)

    workspace: Mapped[Workspace | None] = relationship(back_populates="bookmarks")
    tags: Mapped[list[Tag]] = relationship(secondary=bookmark_tags, back_populates="bookmarks")
    collection_items: Mapped[list[CollectionItem]] = relationship(
        back_populates="bookmark", cascade="all, delete-orphan"
    )


class Collection(TimestampMixin, Base):
    __tablename__ = "collections"
    __table_args__ = (UniqueConstraint("owner_id", "slug", name="uq_collections_owner_slug"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    icon: Mapped[str] = mapped_column(String(64), default="bookmark")
    color: Mapped[str] = mapped_column(String(16), default="")
    is_smart: Mapped[bool] = mapped_column(default=False)
    rules: Mapped[dict] = mapped_column(default=dict)
    position: Mapped[int] = mapped_column(default=0)

    items: Mapped[list[CollectionItem]] = relationship(
        back_populates="collection", cascade="all, delete-orphan"
    )


class CollectionItem(Base):
    __tablename__ = "collection_items"

    collection_id: Mapped[str] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True
    )
    bookmark_id: Mapped[str] = mapped_column(
        ForeignKey("bookmarks.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(default=0)
    added_at: Mapped[datetime] = mapped_column(default=utcnow)

    collection: Mapped[Collection] = relationship(back_populates="items")
    bookmark: Mapped[Bookmark] = relationship(back_populates="collection_items")


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("owner_id", "slug", name="uq_tags_owner_slug"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(120))
    parent_id: Mapped[str | None] = mapped_column(
        ForeignKey("tags.id", ondelete="CASCADE"), nullable=True
    )
    color: Mapped[str] = mapped_column(String(16), default="")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    parent: Mapped[Tag | None] = relationship(remote_side=[id], backref="children")
    bookmarks: Mapped[list[Bookmark]] = relationship(
        secondary=bookmark_tags, back_populates="tags"
    )
    notes: Mapped[list[Note]] = relationship(secondary=note_tags, back_populates="tags")


class Note(TimestampMixin, Base):
    __tablename__ = "notes"
    __table_args__ = (Index("ix_notes_owner_updated", "owner_id", "updated_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    workspace_id: Mapped[str | None] = mapped_column(
        ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(Text, default="")
    content: Mapped[str] = mapped_column(Text, default="")
    content_text: Mapped[str] = mapped_column(Text, default="")
    is_pinned: Mapped[bool] = mapped_column(default=False)

    workspace: Mapped[Workspace | None] = relationship(back_populates="notes")
    revisions: Mapped[list[NoteRevision]] = relationship(
        back_populates="note", cascade="all, delete-orphan", order_by="NoteRevision.created_at"
    )
    links: Mapped[list[NoteLink]] = relationship(
        back_populates="note", cascade="all, delete-orphan"
    )
    tags: Mapped[list[Tag]] = relationship(secondary=note_tags, back_populates="notes")


class NoteRevision(Base):
    __tablename__ = "note_revisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    note_id: Mapped[str] = mapped_column(ForeignKey("notes.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(Text, default="")
    content: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    created_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    note: Mapped[Note] = relationship(back_populates="revisions")


class NoteLink(Base):
    __tablename__ = "note_links"
    __table_args__ = (
        UniqueConstraint("note_id", "target_type", "target_id", name="uq_note_links_target"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    note_id: Mapped[str] = mapped_column(ForeignKey("notes.id", ondelete="CASCADE"))
    target_type: Mapped[str] = mapped_column(String(16))  # "note" | "bookmark"
    target_id: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    note: Mapped[Note] = relationship(back_populates="links")
