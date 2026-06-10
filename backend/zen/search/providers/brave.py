"""Brave Search — official API when a key is configured, HTML fallback otherwise."""

from __future__ import annotations

import httpx
from selectolax.parser import HTMLParser

from zen.search.http import resilient_get
from zen.search.models import ProviderCategory, RawResult, SearchQuery
from zen.search.providers.base import SearchProvider


class BraveProvider(SearchProvider):
    slug = "brave"
    name = "Brave Search"
    category = ProviderCategory.GENERAL
    default_weight = 1.1
    description = (
        "Brave independent index. Configure an API key (free tier available) for "
        "reliable access; without one a best-effort scrape is used."
    )

    API = "https://api.search.brave.com/res/v1/web/search"
    HTML = "https://search.brave.com/search"

    async def search(self, query: SearchQuery, client: httpx.AsyncClient) -> list[RawResult]:
        if self.api_key:
            return await self._search_api(query, client)
        return await self._search_html(query, client)

    async def _search_api(self, query: SearchQuery, client: httpx.AsyncClient) -> list[RawResult]:
        response = await resilient_get(
            client,
            self.API,
            params={
                "q": query.text,
                "count": "20",
                "offset": str(query.page - 1),
                "safesearch": "strict" if query.safe_search else "off",
            },
            headers={"X-Subscription-Token": self.api_key, "Accept": "application/json"},
        )
        payload = response.json()
        results: list[RawResult] = []
        for item in (payload.get("web") or {}).get("results", []):
            url = item.get("url", "")
            title = item.get("title", "")
            if not url or not title:
                continue
            results.append(
                RawResult(
                    title=title,
                    url=url,
                    snippet=item.get("description", "") or "",
                    position=len(results) + 1,
                    published_at=item.get("age"),
                    thumbnail=(item.get("thumbnail") or {}).get("src"),
                )
            )
        return results

    async def _search_html(self, query: SearchQuery, client: httpx.AsyncClient) -> list[RawResult]:
        response = await resilient_get(
            client, self.HTML, params={"q": query.text, "source": "web"}
        )
        return self.parse(response.text)

    def parse(self, html: str) -> list[RawResult]:
        tree = HTMLParser(html)
        results: list[RawResult] = []
        for block in tree.css("div.snippet[data-type='web'], div#results > div.snippet"):
            link = block.css_first("a")
            if link is None:
                continue
            url = link.attributes.get("href", "") or ""
            if not url.startswith(("http://", "https://")):
                continue
            title_node = block.css_first(".title, .snippet-title, .url")
            title = title_node.text(strip=True) if title_node else link.text(strip=True)
            if not title:
                continue
            snippet_node = block.css_first(".snippet-description, .snippet-content")
            snippet = snippet_node.text(strip=True) if snippet_node else ""
            results.append(
                RawResult(title=title, url=url, snippet=snippet, position=len(results) + 1)
            )
        return results
