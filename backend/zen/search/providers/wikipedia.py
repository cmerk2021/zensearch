"""Wikipedia search via the official MediaWiki API (stable JSON)."""

from __future__ import annotations

import httpx

from zen.search.http import resilient_get
from zen.search.models import ProviderCategory, RawResult, ResultType, SearchQuery
from zen.search.providers.base import SearchProvider


class WikipediaProvider(SearchProvider):
    slug = "wikipedia"
    name = "Wikipedia"
    category = ProviderCategory.REFERENCE
    default_weight = 1.0
    description = "Wikipedia articles via the official MediaWiki API."

    async def search(self, query: SearchQuery, client: httpx.AsyncClient) -> list[RawResult]:
        lang = (query.locale or "en").split("-")[0] or "en"
        base = f"https://{lang}.wikipedia.org/w/api.php"
        response = await resilient_get(
            client,
            base,
            params={
                "action": "query",
                "list": "search",
                "srsearch": query.text,
                "srlimit": "10",
                "sroffset": str((query.page - 1) * 10),
                "format": "json",
                "srprop": "snippet|timestamp",
            },
            headers={"Accept": "application/json"},
        )
        payload = response.json()
        results: list[RawResult] = []
        for item in (payload.get("query") or {}).get("search", []):
            title = item.get("title", "")
            if not title:
                continue
            snippet = _strip_html(item.get("snippet", ""))
            url = f"https://{lang}.wikipedia.org/wiki/" + title.replace(" ", "_")
            results.append(
                RawResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    position=len(results) + 1,
                    result_type=ResultType.REFERENCE,
                    published_at=item.get("timestamp"),
                )
            )
        return results


def _strip_html(text: str) -> str:
    from selectolax.parser import HTMLParser

    return HTMLParser(f"<span>{text}</span>").text(strip=False).strip()
