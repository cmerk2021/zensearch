"""Stack Overflow search via the Stack Exchange API."""

from __future__ import annotations

import html

import httpx

from zen.search.http import resilient_get
from zen.search.models import ProviderCategory, RawResult, ResultType, SearchQuery
from zen.search.providers.base import SearchProvider


class StackOverflowProvider(SearchProvider):
    slug = "stackoverflow"
    name = "Stack Overflow"
    category = ProviderCategory.QA
    default_weight = 1.0
    description = "Stack Overflow questions via the official Stack Exchange API."

    API = "https://api.stackexchange.com/2.3/search/advanced"

    async def search(self, query: SearchQuery, client: httpx.AsyncClient) -> list[RawResult]:
        params = {
            "q": query.text,
            "site": "stackoverflow",
            "order": "desc",
            "sort": "relevance",
            "pagesize": "10",
            "page": str(query.page),
            "filter": "default",
        }
        if self.api_key:
            params["key"] = self.api_key
        response = await resilient_get(
            client, self.API, params=params, headers={"Accept": "application/json"}
        )
        payload = response.json()
        results: list[RawResult] = []
        for item in payload.get("items", []):
            title = html.unescape(item.get("title", ""))
            url = item.get("link", "")
            if not title or not url:
                continue
            answered = item.get("is_answered", False)
            answers = item.get("answer_count", 0)
            score = item.get("score", 0)
            tags = ", ".join(item.get("tags", [])[:4])
            status = "✓ answered" if answered else f"{answers} answers"
            results.append(
                RawResult(
                    title=title,
                    url=url,
                    snippet=f"{status} · score {score} · {tags}",
                    position=len(results) + 1,
                    result_type=ResultType.QA,
                    extra={"answered": answered, "score": score},
                )
            )
        return results
