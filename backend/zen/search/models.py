"""Value objects flowing through the search subsystem."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field


class ResultType(str, enum.Enum):
    WEB = "web"
    IMAGE = "image"
    VIDEO = "video"
    NEWS = "news"
    CODE = "code"
    QA = "qa"
    SOCIAL = "social"
    REFERENCE = "reference"


class ProviderCategory(str, enum.Enum):
    """Coarse category used by Focus mode filtering."""

    GENERAL = "general"
    REFERENCE = "reference"
    CODE = "code"
    QA = "qa"
    SOCIAL = "social"
    NEWS = "news"
    VIDEO = "video"
    SHOPPING = "shopping"
    ENTERTAINMENT = "entertainment"


@dataclass(slots=True)
class SearchQuery:
    """Provider-facing query (already stripped of bangs/operators)."""

    text: str
    page: int = 1
    locale: str = "en"
    safe_search: bool = True


@dataclass(slots=True)
class RawResult:
    """What a provider emits before normalization."""

    title: str
    url: str
    snippet: str = ""
    position: int = 0
    result_type: ResultType = ResultType.WEB
    published_at: str | None = None
    thumbnail: str | None = None
    extra: dict = field(default_factory=dict)


@dataclass(slots=True)
class SearchResult:
    """Merged, ranked result returned to clients."""

    title: str
    url: str
    snippet: str
    domain: str
    favicon_url: str = ""
    providers: list[str] = field(default_factory=list)
    positions: dict[str, int] = field(default_factory=dict)
    score: float = 0.0
    result_type: ResultType = ResultType.WEB
    published_at: str | None = None
    thumbnail: str | None = None
    pinned: bool = False

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "domain": self.domain,
            "favicon_url": self.favicon_url,
            "providers": self.providers,
            "positions": self.positions,
            "score": round(self.score, 6),
            "result_type": self.result_type.value,
            "published_at": self.published_at,
            "thumbnail": self.thumbnail,
            "pinned": self.pinned,
        }

    @classmethod
    def from_dict(cls, data: dict) -> SearchResult:
        data = dict(data)
        data["result_type"] = ResultType(data.get("result_type", "web"))
        return cls(**data)


@dataclass(slots=True)
class ProviderStatus:
    slug: str
    name: str
    ok: bool
    result_count: int = 0
    duration_ms: int = 0
    error: str | None = None
    skipped: bool = False
    skip_reason: str | None = None

    def to_dict(self) -> dict:
        return {
            "slug": self.slug,
            "name": self.name,
            "ok": self.ok,
            "result_count": self.result_count,
            "duration_ms": self.duration_ms,
            "error": self.error,
            "skipped": self.skipped,
            "skip_reason": self.skip_reason,
        }


@dataclass(slots=True)
class SearchResponse:
    query: str
    mode: str
    page: int
    results: list[SearchResult] = field(default_factory=list)
    providers: list[ProviderStatus] = field(default_factory=list)
    duration_ms: int = 0
    cached: bool = False
    redirect: str | None = None
    profile_slug: str | None = None
    workspace_id: str | None = None
