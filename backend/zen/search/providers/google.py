"""Google web search via HTML scraping.

No official API exists for organic results at reasonable cost. Markup changes
are expected and handled by the circuit breaker + health probes (ADR-0009).
Parsing is selector-redundant: it tries several known result containers.
"""

from __future__ import annotations

import urllib.parse

import httpx
from selectolax.parser import HTMLParser

from zen.search.http import resilient_get
from zen.search.models import ProviderCategory, RawResult, SearchQuery
from zen.search.providers.base import SearchProvider


class GoogleProvider(SearchProvider):
    slug = "google"
    name = "Google"
    category = ProviderCategory.GENERAL
    default_weight = 1.3
    description = "Google web results (scraped). High quality, may be rate-limited upstream."

    BASE = "https://www.google.com/search"

    #: Sending an accepted-consent cookie avoids the EU/interstitial consent
    #: wall that returns HTTP 200 with a JS-only page (and therefore no
    #: parseable results) for datacenter IPs.
    CONSENT_COOKIES = {"CONSENT": "YES+cb", "SOCS": "CAI"}

    async def search(self, query: SearchQuery, client: httpx.AsyncClient) -> list[RawResult]:
        params = {
            "q": query.text,
            "num": "20",
            "hl": query.locale or "en",
            "start": str((query.page - 1) * 10),
            # udm=14 selects the plain "Web" results view, which returns clean
            # server-rendered HTML instead of the JavaScript-heavy default page.
            "udm": "14",
        }
        if query.safe_search:
            params["safe"] = "active"
        response = await resilient_get(
            client, self.BASE, params=params, cookies=self.CONSENT_COOKIES
        )
        return self.parse(response.text)

    def parse(self, html: str) -> list[RawResult]:
        tree = HTMLParser(html)
        results: list[RawResult] = []
        seen: set[str] = set()
        # Strategy: every h3 inside an anchor is an organic result title.
        for h3 in tree.css("a h3"):
            anchor = h3.parent
            while anchor is not None and anchor.tag != "a":
                anchor = anchor.parent
            if anchor is None:
                continue
            href = anchor.attributes.get("href", "") or ""
            url = self._clean_url(href)
            if not url or url in seen:
                continue
            title = h3.text(strip=True)
            if not title:
                continue
            snippet = self._find_snippet(anchor)
            seen.add(url)
            results.append(
                RawResult(title=title, url=url, snippet=snippet, position=len(results) + 1)
            )
        if not results:
            # Fallback: some layouts wrap the title text directly in the anchor
            # rather than an <h3>. Recover organic links heuristically.
            results = self._parse_fallback(tree, seen)
        return results

    def _parse_fallback(self, tree: HTMLParser, seen: set[str]) -> list[RawResult]:
        results: list[RawResult] = []
        for anchor in tree.css("a[href^='/url?'], a[href^='https://']"):
            href = anchor.attributes.get("href", "") or ""
            url = self._clean_url(href)
            if not url or url in seen:
                continue
            title = anchor.text(strip=True)
            if not title or len(title) < 12:
                continue
            seen.add(url)
            snippet = self._find_snippet(anchor)
            results.append(
                RawResult(title=title, url=url, snippet=snippet, position=len(results) + 1)
            )
            if len(results) >= 20:
                break
        return results

    @staticmethod
    def _clean_url(href: str) -> str:
        if href.startswith("/url?"):
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
            candidates = qs.get("q") or qs.get("url") or []
            href = candidates[0] if candidates else ""
        if href.startswith("http://") or href.startswith("https://"):
            if "google." in urllib.parse.urlparse(href).netloc:
                return ""
            return href
        return ""

    @staticmethod
    def _find_snippet(anchor) -> str:
        # Walk up a few levels and look for the descriptive text block.
        node = anchor
        for _ in range(5):
            node = node.parent
            if node is None:
                return ""
            for candidate in node.css("div[data-sncf], div[style*='-webkit-line-clamp'], div.VwiC3b"):
                text = candidate.text(strip=True)
                if text and len(text) > 40:
                    return text
        return ""
