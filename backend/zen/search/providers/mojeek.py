"""Mojeek — independent UK index, via HTML scraping."""

from __future__ import annotations

import httpx
from selectolax.parser import HTMLParser

from zen.search.http import resilient_get
from zen.search.models import ProviderCategory, RawResult, SearchQuery
from zen.search.providers.base import SearchProvider


class MojeekProvider(SearchProvider):
    slug = "mojeek"
    name = "Mojeek"
    category = ProviderCategory.GENERAL
    default_weight = 0.8
    description = "Mojeek independent index (scraped). True index diversity."

    BASE = "https://www.mojeek.com/search"

    async def search(self, query: SearchQuery, client: httpx.AsyncClient) -> list[RawResult]:
        params = {"q": query.text}
        if query.page > 1:
            params["s"] = str((query.page - 1) * 10 + 1)
        if query.safe_search:
            params["safe"] = "1"
        response = await resilient_get(client, self.BASE, params=params)
        return self.parse(response.text)

    def parse(self, html: str) -> list[RawResult]:
        tree = HTMLParser(html)
        results: list[RawResult] = []
        for li in tree.css("ul.results-standard li, ul.results li"):
            link = li.css_first("h2 a, a.title")
            if link is None:
                continue
            url = link.attributes.get("href", "") or ""
            if not url.startswith(("http://", "https://")):
                continue
            title = link.text(strip=True)
            if not title:
                continue
            snippet_node = li.css_first("p.s, p.i, p")
            snippet = snippet_node.text(strip=True) if snippet_node else ""
            results.append(
                RawResult(title=title, url=url, snippet=snippet, position=len(results) + 1)
            )
        return results
