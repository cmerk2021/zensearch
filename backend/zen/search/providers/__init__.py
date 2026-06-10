"""Provider registry. Built-ins plus plugin-registered providers."""

from __future__ import annotations

import structlog

from zen.search.providers.base import SearchProvider
from zen.search.providers.bing import BingProvider
from zen.search.providers.brave import BraveProvider
from zen.search.providers.duckduckgo import DuckDuckGoProvider
from zen.search.providers.github import GitHubProvider
from zen.search.providers.google import GoogleProvider
from zen.search.providers.kagi import KagiProvider
from zen.search.providers.mojeek import MojeekProvider
from zen.search.providers.reddit import RedditProvider
from zen.search.providers.stackoverflow import StackOverflowProvider
from zen.search.providers.startpage import StartpageProvider
from zen.search.providers.wikipedia import WikipediaProvider
from zen.search.providers.youtube import YouTubeProvider

log = structlog.get_logger(__name__)

BUILTIN_PROVIDERS: dict[str, type[SearchProvider]] = {
    cls.slug: cls
    for cls in (
        GoogleProvider,
        BingProvider,
        DuckDuckGoProvider,
        BraveProvider,
        StartpageProvider,
        KagiProvider,
        MojeekProvider,
        WikipediaProvider,
        GitHubProvider,
        RedditProvider,
        StackOverflowProvider,
        YouTubeProvider,
    )
}

_plugin_providers: dict[str, type[SearchProvider]] = {}


def register_provider(cls: type[SearchProvider], *, source: str = "plugin") -> None:
    """Register an additional provider (used by the plugin SDK)."""
    slug = getattr(cls, "slug", "")
    if not slug or not isinstance(slug, str):
        raise ValueError("Provider class must define a non-empty 'slug'.")
    if slug in BUILTIN_PROVIDERS:
        raise ValueError(f"Provider slug '{slug}' conflicts with a built-in provider.")
    _plugin_providers[slug] = cls
    log.info("provider.registered", slug=slug, source=source)


def unregister_provider(slug: str) -> None:
    _plugin_providers.pop(slug, None)


def all_providers() -> dict[str, type[SearchProvider]]:
    return {**BUILTIN_PROVIDERS, **_plugin_providers}


def get_provider_class(slug: str) -> type[SearchProvider] | None:
    return all_providers().get(slug)


__all__ = [
    "BUILTIN_PROVIDERS",
    "SearchProvider",
    "all_providers",
    "get_provider_class",
    "register_provider",
    "unregister_provider",
]
