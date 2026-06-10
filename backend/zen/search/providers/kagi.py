"""Kagi search via the official API (requires a Kagi API key)."""

from __future__ import annotations

import httpx

from zen.search.http import resilient_get
from zen.search.models import ProviderCategory, RawResult, SearchQuery
from zen.search.providers.base import SearchProvider


class KagiProvider(SearchProvider):
    slug = "kagi"
    name = "Kagi"
    category = ProviderCategory.GENERAL
    requires_api_key = True
    default_weight = 1.3
    description = "Kagi premium results via the official API. Requires an API key (paid)."

    API = "https://kagi.com/api/v0/search"

    async def search(self, query: SearchQuery, client: httpx.AsyncClient) -> list[RawResult]:
        if not self.api_key:
            return []
        response = await resilient_get(
            client,
            self.API,
            params={"q": query.text, "limit": "20"},
            headers={"Authorization": f"Bot {self.api_key}", "Accept": "application/json"},
        )
        payload = response.json()
        results: list[RawResult] = []
        for item in payload.get("data", []):
            # t == 0 → search result; t == 1 → related searches block.
            if item.get("t") != 0:
                continue
            url = item.get("url", "")
            title = item.get("title", "")
            if not url or not title:
                continue
            results.append(
                RawResult(
                    title=title,
                    url=url,
                    snippet=item.get("snippet", "") or "",
                    position=len(results) + 1,
                    published_at=item.get("published"),
                    thumbnail=(item.get("thumbnail") or {}).get("url"),
                )
            )
        return results
