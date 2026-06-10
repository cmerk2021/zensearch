"""DuckDuckGo search via the HTML (non-JS) endpoint."""

from __future__ import annotations

import urllib.parse

import httpx
from selectolax.parser import HTMLParser

from zen.search.http import resilient_post
from zen.search.models import ProviderCategory, RawResult, SearchQuery
from zen.search.providers.base import SearchProvider


class DuckDuckGoProvider(SearchProvider):
    slug = "duckduckgo"
    name = "DuckDuckGo"
    category = ProviderCategory.GENERAL
    default_weight = 1.0
    supports_paging = False
    description = "DuckDuckGo HTML endpoint. Privacy-friendly upstream, no paging."

    BASE = "https://html.duckduckgo.com/html/"

    async def search(self, query: SearchQuery, client: httpx.AsyncClient) -> list[RawResult]:
        data = {"q": query.text, "kl": "us-en" if query.locale.startswith("en") else "wt-wt"}
        if query.safe_search:
            data["kp"] = "1"
        response = await resilient_post(client, self.BASE, data=data)
        return self.parse(response.text)

    def parse(self, html: str) -> list[RawResult]:
        tree = HTMLParser(html)
        results: list[RawResult] = []
        seen: set[str] = set()
        for block in tree.css("div.result, div.web-result"):
            if "result--ad" in (block.attributes.get("class") or ""):
                continue
            link = block.css_first("a.result__a")
            if link is None:
                continue
            url = self._unwrap(link.attributes.get("href", "") or "")
            title = link.text(strip=True)
            if not url or not title or url in seen:
                continue
            seen.add(url)
            snippet_node = block.css_first("a.result__snippet, div.result__snippet")
            snippet = snippet_node.text(strip=True) if snippet_node else ""
            results.append(
                RawResult(title=title, url=url, snippet=snippet, position=len(results) + 1)
            )
        return results

    @staticmethod
    def _unwrap(href: str) -> str:
        """DDG html endpoint links via //duckduckgo.com/l/?uddg=<encoded>."""
        if not href:
            return ""
        if href.startswith("//"):
            href = "https:" + href
        parsed = urllib.parse.urlparse(href)
        if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
            qs = urllib.parse.parse_qs(parsed.query)
            target = (qs.get("uddg") or [""])[0]
            return target if target.startswith(("http://", "https://")) else ""
        if href.startswith(("http://", "https://")):
            return href
        return ""
