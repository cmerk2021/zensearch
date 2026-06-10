"""Startpage search via HTML scraping (Google results, privacy frontend)."""

from __future__ import annotations

import httpx
from selectolax.parser import HTMLParser

from zen.search.http import resilient_post
from zen.search.models import ProviderCategory, RawResult, SearchQuery
from zen.search.providers.base import SearchProvider


class StartpageProvider(SearchProvider):
    slug = "startpage"
    name = "Startpage"
    category = ProviderCategory.GENERAL
    default_weight = 1.0
    description = "Startpage (Google-sourced, privacy frontend; scraped)."

    BASE = "https://www.startpage.com/sp/search"

    async def search(self, query: SearchQuery, client: httpx.AsyncClient) -> list[RawResult]:
        data = {
            "query": query.text,
            "page": str(query.page),
            "cat": "web",
        }
        response = await resilient_post(client, self.BASE, data=data)
        return self.parse(response.text)

    def parse(self, html: str) -> list[RawResult]:
        tree = HTMLParser(html)
        results: list[RawResult] = []
        for block in tree.css("div.result, section.result, div.w-gl__result"):
            link = block.css_first("a.result-title, a.w-gl__result-title, a[data-testid='gl-title-link']")
            if link is None:
                link = block.css_first("h2 a, h3 a")
            if link is None:
                continue
            url = link.attributes.get("href", "") or ""
            if not url.startswith(("http://", "https://")):
                continue
            title = link.text(strip=True)
            if not title:
                continue
            snippet_node = block.css_first(
                "p.description, p.w-gl__description, span.description, p"
            )
            snippet = snippet_node.text(strip=True) if snippet_node else ""
            results.append(
                RawResult(title=title, url=url, snippet=snippet, position=len(results) + 1)
            )
        return results
