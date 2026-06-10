"""Search modes (Normal / Privacy / Focus / Research).

A mode is a behavior bundle applied by the engine:

* ``normal``   — default behavior.
* ``privacy``  — no history, no personalization signals, no result caching.
* ``focus``    — distraction categories removed (news/social/shopping/
                 entertainment) at both provider and domain level.
* ``research`` — activity is associated with a workspace; capture tools are
                 surfaced in the UI.
"""

from __future__ import annotations

from dataclasses import dataclass

from zen.search.models import ProviderCategory, SearchResult

#: Provider categories excluded by Focus mode.
FOCUS_EXCLUDED_CATEGORIES: frozenset[ProviderCategory] = frozenset(
    {
        ProviderCategory.NEWS,
        ProviderCategory.SOCIAL,
        ProviderCategory.SHOPPING,
        ProviderCategory.ENTERTAINMENT,
        ProviderCategory.VIDEO,
    }
)

#: Built-in domain lists backing the Focus mode result filter. Administrators
#: can extend these via instance setting ``search.focus_blocked_domains``.
FOCUS_BLOCKED_DOMAINS: frozenset[str] = frozenset(
    {
        # social
        "facebook.com", "instagram.com", "twitter.com", "x.com", "tiktok.com",
        "threads.net", "snapchat.com", "pinterest.com", "linkedin.com",
        "reddit.com",
        # entertainment / video
        "youtube.com", "netflix.com", "hulu.com", "twitch.tv", "dailymotion.com",
        "9gag.com", "buzzfeed.com",
        # shopping
        "amazon.com", "ebay.com", "aliexpress.com", "walmart.com", "etsy.com",
        "temu.com", "wish.com", "target.com",
        # mainstream news (excluded unless explicitly requested)
        "cnn.com", "foxnews.com", "dailymail.co.uk", "nypost.com",
        "buzzfeednews.com", "tmz.com",
    }
)


@dataclass(frozen=True, slots=True)
class ModeBehavior:
    slug: str
    record_history: bool
    use_personalization: bool
    use_cache: bool
    filter_focus_categories: bool
    associate_workspace: bool


MODES: dict[str, ModeBehavior] = {
    "normal": ModeBehavior(
        slug="normal",
        record_history=True,
        use_personalization=True,
        use_cache=True,
        filter_focus_categories=False,
        associate_workspace=False,
    ),
    "privacy": ModeBehavior(
        slug="privacy",
        record_history=False,
        use_personalization=False,
        use_cache=False,
        filter_focus_categories=False,
        associate_workspace=False,
    ),
    "focus": ModeBehavior(
        slug="focus",
        record_history=True,
        use_personalization=True,
        use_cache=True,
        filter_focus_categories=True,
        associate_workspace=False,
    ),
    "research": ModeBehavior(
        slug="research",
        record_history=True,
        use_personalization=True,
        use_cache=True,
        filter_focus_categories=False,
        associate_workspace=True,
    ),
}


def get_mode(slug: str) -> ModeBehavior:
    return MODES.get(slug, MODES["normal"])


def _domain_blocked(domain: str, blocked: frozenset[str] | set[str]) -> bool:
    return any(domain == b or domain.endswith("." + b) for b in blocked)


def apply_focus_filter(
    results: list[SearchResult], extra_blocked: set[str] | None = None
) -> list[SearchResult]:
    blocked: set[str] = set(FOCUS_BLOCKED_DOMAINS)
    if extra_blocked:
        blocked |= extra_blocked
    return [r for r in results if not _domain_blocked(r.domain, blocked)]
