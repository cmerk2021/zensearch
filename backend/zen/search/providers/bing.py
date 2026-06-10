"""Bing web search via HTML scraping."""

from __future__ import annotations

import base64
import urllib.parse

import httpx
from selectolax.parser import HTMLParser

from zen.search.http import resilient_get
from zen.search.models import ProviderCategory, RawResult, SearchQuery
from zen.search.providers.base import SearchProvider


class BingProvider(SearchProvider):
    slug = "bing"
    name = "Bing"
    category = ProviderCategory.GENERAL
    default_weight = 1.0
    description = "Microsoft Bing web results (scraped)."

    BASE = "https://www.bing.com/search"

    async def search(self, query: SearchQuery, client: httpx.AsyncClient) -> list[RawResult]:
        params = {
            "q": query.text,
            "count": "20",
            "first": str((query.page - 1) * 10 + 1),
            "setlang": query.locale or "en",
        }
        if query.safe_search:
            params["adlt"] = "strict"
        response = await resilient_get(client, self.BASE, params=params)
        return self.parse(response.text)

    def parse(self, html: str) -> list[RawResult]:
        tree = HTMLParser(html)
        results: list[RawResult] = []
        for li in tree.css("li.b_algo"):
            link = li.css_first("h2 a")
            if link is None:
                continue
            url = self._decode_url(link.attributes.get("href", "") or "")
            title = link.text(strip=True)
            if not url or not title:
                continue
            snippet_node = li.css_first("div.b_caption p, p")
            snippet = snippet_node.text(strip=True) if snippet_node else ""
            results.append(
                RawResult(title=title, url=url, snippet=snippet, position=len(results) + 1)
            )
        return results

    @staticmethod
    def _decode_url(href: str) -> str:
        """Bing wraps results in /ck/a redirects with a base64 ``u`` param."""
        if not href:
            return ""
        if href.startswith("https://www.bing.com/ck/") or href.startswith("/ck/"):
            try:
                qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                u = (qs.get("u") or [""])[0]
                if u.startswith("a1"):
                    u = u[2:]
                padded = u + "=" * (-len(u) % 4)
                decoded = base64.urlsafe_b64decode(padded).decode("utf-8", "replace")
                if decoded.startswith(("http://", "https://")):
                    return decoded
            except (ValueError, UnicodeDecodeError):
                return ""
            return ""
        if href.startswith(("http://", "https://")):
            return href
        return ""
