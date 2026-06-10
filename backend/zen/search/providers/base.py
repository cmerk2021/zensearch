"""Provider abstraction. Plugins register additional providers via the SDK."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

import httpx

from zen.search.models import ProviderCategory, RawResult, SearchQuery


class SearchProvider(ABC):
    """Base class for all search providers.

    Implementations must be stateless across calls; per-instance state is the
    admin-supplied ``config`` dict and decrypted ``api_key``. Never log query
    text at INFO level or above (privacy requirement).
    """

    #: Stable identifier. Lowercase, [a-z0-9-]. Used in configs and metrics.
    slug: ClassVar[str]
    #: Human-readable name shown in the UI.
    name: ClassVar[str]
    #: Category used by Focus mode and the admin UI.
    category: ClassVar[ProviderCategory] = ProviderCategory.GENERAL
    #: Whether the provider cannot work without an API key.
    requires_api_key: ClassVar[bool] = False
    #: Relative confidence used by the ranking engine (admin-overridable).
    default_weight: ClassVar[float] = 1.0
    #: Per-call timeout in seconds (admin-overridable).
    default_timeout: ClassVar[float] = 8.0
    #: Whether ``SearchQuery.page`` > 1 is meaningful for this provider.
    supports_paging: ClassVar[bool] = True
    #: Short description for the admin dashboard.
    description: ClassVar[str] = ""

    def __init__(self, config: dict | None = None, api_key: str = "") -> None:
        self.config = config or {}
        self.api_key = api_key

    @abstractmethod
    async def search(self, query: SearchQuery, client: httpx.AsyncClient) -> list[RawResult]:
        """Execute the query and return raw results (empty list permitted)."""

    def probe_query(self) -> SearchQuery:
        """Cheap query used by scheduled health probes."""
        return SearchQuery(text="zen", page=1)

    @classmethod
    def info(cls) -> dict:
        return {
            "slug": cls.slug,
            "name": cls.name,
            "category": cls.category.value,
            "requires_api_key": cls.requires_api_key,
            "default_weight": cls.default_weight,
            "default_timeout": cls.default_timeout,
            "supports_paging": cls.supports_paging,
            "description": cls.description,
        }
