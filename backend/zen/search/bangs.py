"""Search bangs: ``!gh fastapi`` jumps straight to GitHub search.

Administrators can define custom bangs through instance settings
(``search.custom_bangs``: ``{"name": "https://...{q}..."}``); custom bangs
shadow built-ins.
"""

from __future__ import annotations

import re
import urllib.parse

#: Built-in bang → URL template. ``{q}`` is the URL-encoded query remainder.
BUILTIN_BANGS: dict[str, str] = {
    "g": "https://www.google.com/search?q={q}",
    "ddg": "https://duckduckgo.com/?q={q}",
    "b": "https://www.bing.com/search?q={q}",
    "brave": "https://search.brave.com/search?q={q}",
    "gh": "https://github.com/search?q={q}",
    "reddit": "https://www.reddit.com/search/?q={q}",
    "r": "https://www.reddit.com/search/?q={q}",
    "yt": "https://www.youtube.com/results?search_query={q}",
    "wiki": "https://en.wikipedia.org/wiki/Special:Search?search={q}",
    "w": "https://en.wikipedia.org/wiki/Special:Search?search={q}",
    "so": "https://stackoverflow.com/search?q={q}",
    "docs": "https://devdocs.io/#q={q}",
    "mdn": "https://developer.mozilla.org/en-US/search?q={q}",
    "npm": "https://www.npmjs.com/search?q={q}",
    "pypi": "https://pypi.org/search/?q={q}",
    "crates": "https://crates.io/search?q={q}",
    "hn": "https://hn.algolia.com/?q={q}",
    "aw": "https://wiki.archlinux.org/index.php?search={q}",
    "dh": "https://hub.docker.com/search?q={q}",
    "maps": "https://www.openstreetmap.org/search?query={q}",
    "imdb": "https://www.imdb.com/find/?q={q}",
    "az": "https://www.amazon.com/s?k={q}",
}

_BANG_PATTERN = re.compile(r"(?:^|\s)!([a-z0-9_-]{1,32})(?:\s|$)", re.IGNORECASE)


def parse_bang(text: str) -> tuple[str, str] | None:
    """Extract ``(bang, remaining_query)`` or None if no bang present."""
    match = _BANG_PATTERN.search(text)
    if not match:
        return None
    bang = match.group(1).lower()
    rest = (text[: match.start()] + " " + text[match.end() :]).strip()
    return bang, rest


def resolve_bang(text: str, custom_bangs: dict[str, str] | None = None) -> str | None:
    """Return a redirect URL when the query contains a known bang."""
    parsed = parse_bang(text)
    if parsed is None:
        return None
    bang, rest = parsed
    table = {**BUILTIN_BANGS, **{k.lower(): v for k, v in (custom_bangs or {}).items()}}
    template = table.get(bang)
    if template is None:
        return None
    encoded = urllib.parse.quote_plus(rest)
    return template.replace("{q}", encoded)


def all_bangs(custom_bangs: dict[str, str] | None = None) -> dict[str, str]:
    return {**BUILTIN_BANGS, **{k.lower(): v for k, v in (custom_bangs or {}).items()}}
