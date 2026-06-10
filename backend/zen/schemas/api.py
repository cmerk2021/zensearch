"""Search, knowledge and admin schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from zen.schemas.common import ORMModel

# --- Search -----------------------------------------------------------------


class SearchRequest(BaseModel):
    q: str = Field(min_length=1, max_length=512)
    mode: str = Field(default="normal", pattern="^(normal|privacy|focus|research)$")
    profile: str | None = Field(default=None, max_length=64)
    page: int = Field(default=1, ge=1, le=10)
    providers: list[str] | None = None
    workspace_id: str | None = None


class ResultOut(BaseModel):
    title: str
    url: str
    snippet: str
    domain: str
    favicon_url: str
    providers: list[str]
    positions: dict[str, int]
    score: float
    result_type: str
    published_at: str | None
    thumbnail: str | None
    pinned: bool


class ProviderStatusOut(BaseModel):
    slug: str
    name: str
    ok: bool
    result_count: int
    duration_ms: int
    error: str | None
    skipped: bool
    skip_reason: str | None


class SearchResponseOut(BaseModel):
    query: str
    mode: str
    page: int
    results: list[ResultOut]
    providers: list[ProviderStatusOut]
    duration_ms: int
    cached: bool
    redirect: str | None
    profile_slug: str | None
    workspace_id: str | None


class ClickRequest(BaseModel):
    url: str = Field(max_length=4096)
    query: str | None = Field(default=None, max_length=512)
    provider: str | None = Field(default=None, max_length=64)


class HistoryEntryOut(ORMModel):
    id: str
    query: str
    mode: str
    workspace_id: str | None
    profile_id: str | None
    providers: list
    result_count: int
    duration_ms: int
    created_at: datetime


# --- Workspaces ---------------------------------------------------------------


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=4000)
    icon: str = Field(default="folder", max_length=64)
    color: str = Field(default="", max_length=16)


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    icon: str | None = Field(default=None, max_length=64)
    color: str | None = Field(default=None, max_length=16)
    status: str | None = Field(default=None, pattern="^(active|archived)$")
    settings: dict | None = None


class WorkspaceOut(ORMModel):
    id: str
    name: str
    description: str
    icon: str
    color: str
    status: str
    settings: dict
    created_at: datetime
    updated_at: datetime


# --- Bookmarks ----------------------------------------------------------------


class TagOut(ORMModel):
    id: str
    name: str
    slug: str
    parent_id: str | None
    color: str


class BookmarkCreate(BaseModel):
    url: str = Field(min_length=1, max_length=4096)
    title: str = Field(default="", max_length=2000)
    description: str = Field(default="", max_length=4000)
    snippet: str = Field(default="", max_length=4000)
    workspace_id: str | None = None
    source_provider: str | None = Field(default=None, max_length=64)
    source_query: str | None = Field(default=None, max_length=512)
    tag_ids: list[str] | None = None


class BookmarkUpdate(BaseModel):
    url: str | None = Field(default=None, max_length=4096)
    title: str | None = Field(default=None, max_length=2000)
    description: str | None = Field(default=None, max_length=4000)
    snippet: str | None = Field(default=None, max_length=4000)
    workspace_id: str | None = None
    is_favorite: bool | None = None
    is_archived: bool | None = None
    tag_ids: list[str] | None = None


class BookmarkOut(ORMModel):
    id: str
    url: str
    domain: str
    title: str
    description: str
    snippet: str
    favicon_url: str
    workspace_id: str | None
    source_provider: str | None
    source_query: str | None
    is_favorite: bool
    is_archived: bool
    tags: list[TagOut]
    created_at: datetime
    updated_at: datetime


# --- Collections ----------------------------------------------------------------


class CollectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=4000)
    icon: str = Field(default="bookmark", max_length=64)
    color: str = Field(default="", max_length=16)
    is_smart: bool = False
    rules: dict | None = None


class CollectionUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    icon: str | None = Field(default=None, max_length=64)
    color: str | None = Field(default=None, max_length=16)
    rules: dict | None = None
    position: int | None = None


class CollectionOut(ORMModel):
    id: str
    name: str
    slug: str
    description: str
    icon: str
    color: str
    is_smart: bool
    rules: dict
    position: int
    created_at: datetime


# --- Tags -----------------------------------------------------------------------


class TagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    parent_id: str | None = None
    color: str = Field(default="", max_length=16)


class TagUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    parent_id: str | None = None
    color: str | None = Field(default=None, max_length=16)


class TagWithCounts(BaseModel):
    tag: TagOut
    bookmark_count: int
    note_count: int


# --- Notes ----------------------------------------------------------------------


class NoteCreate(BaseModel):
    title: str = Field(default="", max_length=500)
    content: str = Field(default="", max_length=500_000)
    workspace_id: str | None = None
    tag_ids: list[str] | None = None


class NoteUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    content: str | None = Field(default=None, max_length=500_000)
    workspace_id: str | None = None
    is_pinned: bool | None = None
    tag_ids: list[str] | None = None


class NoteLinkOut(ORMModel):
    id: str
    target_type: str
    target_id: str


class NoteOut(ORMModel):
    id: str
    title: str
    content: str
    workspace_id: str | None
    is_pinned: bool
    tags: list[TagOut]
    links: list[NoteLinkOut] = []
    created_at: datetime
    updated_at: datetime


class NoteListItem(ORMModel):
    id: str
    title: str
    workspace_id: str | None
    is_pinned: bool
    tags: list[TagOut]
    created_at: datetime
    updated_at: datetime


class NoteRevisionOut(ORMModel):
    id: str
    title: str
    created_at: datetime


class NoteLinkCreate(BaseModel):
    target_type: str = Field(pattern="^(note|bookmark)$")
    target_id: str


# --- Profiles ---------------------------------------------------------------------


class ProfileOut(ORMModel):
    id: str
    slug: str
    name: str
    description: str
    icon: str
    providers: list
    ranking: dict
    filters: dict
    ai: dict
    workspace: dict
    ui: dict
    is_default: bool
    is_active: bool
    position: int


class ProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str | None = Field(default=None, max_length=64)
    description: str = Field(default="", max_length=2000)
    icon: str = Field(default="search", max_length=64)
    providers: list[str] = []
    ranking: dict = {}
    filters: dict = {}
    ai: dict = {}
    workspace: dict = {}
    ui: dict = {}
    is_default: bool = False
    is_active: bool = True
    position: int = 0


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    icon: str | None = Field(default=None, max_length=64)
    providers: list[str] | None = None
    ranking: dict | None = None
    filters: dict | None = None
    ai: dict | None = None
    workspace: dict | None = None
    ui: dict | None = None
    is_default: bool | None = None
    is_active: bool | None = None
    position: int | None = None


# --- AI -------------------------------------------------------------------------


class ExpandQueryRequest(BaseModel):
    q: str = Field(min_length=1, max_length=512)


class SummarizeRequest(BaseModel):
    q: str = Field(min_length=1, max_length=512)
    results: list[ResultOut] = Field(max_length=20)


class AITextOut(BaseModel):
    text: str


class KnowledgeMapOut(BaseModel):
    nodes: list[dict]
    edges: list[dict]


# --- Admin ----------------------------------------------------------------------


class ProviderConfigOut(BaseModel):
    slug: str
    name: str
    description: str
    category: str
    requires_api_key: bool
    enabled: bool
    weight: float
    timeout_seconds: float | None
    has_api_key: bool
    supports_paging: bool
    builtin: bool


class ProviderConfigUpdate(BaseModel):
    enabled: bool | None = None
    weight: float | None = Field(default=None, ge=0.0, le=10.0)
    timeout_seconds: float | None = Field(default=None, ge=1.0, le=60.0)
    api_key: str | None = Field(default=None, max_length=512)
    config: dict | None = None


class DomainRuleCreate(BaseModel):
    domain: str = Field(min_length=1, max_length=255)
    action: str = Field(pattern="^(boost|lower|pin|block)$")
    weight: float = Field(default=1.0, ge=0.0, le=10.0)
    scope: str = Field(default="instance", pattern="^(instance|profile|user)$")
    profile_id: str | None = None


class DomainRuleOut(ORMModel):
    id: str
    domain: str
    action: str
    weight: float
    scope: str
    profile_id: str | None
    user_id: str | None
    created_at: datetime


class InstanceSettingsUpdate(BaseModel):
    values: dict[str, Any]


class AdminUserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=10, max_length=256)
    email: str | None = Field(default=None, max_length=255)
    role: str = Field(default="user", pattern="^(admin|user|readonly)$")


class AdminUserUpdate(BaseModel):
    role: str | None = Field(default=None, pattern="^(admin|user|readonly)$")
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=10, max_length=256)


class RepositoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    url: str = Field(min_length=1, max_length=2000)
    kind: str = Field(default="community", pattern="^(official|community|private)$")


class RepositoryOut(ORMModel):
    id: str
    name: str
    url: str
    kind: str
    enabled: bool
    last_synced_at: datetime | None
    added_at: datetime


class PluginOut(ORMModel):
    id: str
    slug: str
    name: str
    version: str
    description: str
    author: str
    license: str
    homepage: str
    types: list
    source_repo: str | None
    status: str
    error: str
    previous_version: str | None
    installed_at: datetime
    updated_at: datetime


class PluginInstallRequest(BaseModel):
    plugin_id: str = Field(min_length=1, max_length=128)
    version: str | None = Field(default=None, max_length=32)


class AuditEntryOut(ORMModel):
    id: str
    actor_id: str | None
    action: str
    target_type: str
    target_id: str
    data: dict
    ip_address: str
    created_at: datetime
