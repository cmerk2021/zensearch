"""GitHub repository search via the official REST API."""

from __future__ import annotations

import httpx

from zen.search.http import resilient_get
from zen.search.models import ProviderCategory, RawResult, ResultType, SearchQuery
from zen.search.providers.base import SearchProvider


class GitHubProvider(SearchProvider):
    slug = "github"
    name = "GitHub"
    category = ProviderCategory.CODE
    default_weight = 1.0
    description = (
        "GitHub repository search via the official API. Optional token raises "
        "rate limits from 10 to 30 requests/minute."
    )

    API = "https://api.github.com/search/repositories"

    async def search(self, query: SearchQuery, client: httpx.AsyncClient) -> list[RawResult]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        response = await resilient_get(
            client,
            self.API,
            params={
                "q": query.text,
                "per_page": "10",
                "page": str(query.page),
                "sort": "",  # best match
            },
            headers=headers,
        )
        payload = response.json()
        results: list[RawResult] = []
        for item in payload.get("items", []):
            full_name = item.get("full_name", "")
            url = item.get("html_url", "")
            if not full_name or not url:
                continue
            description = item.get("description") or ""
            stars = item.get("stargazers_count", 0)
            language = item.get("language") or ""
            snippet_parts = [description] if description else []
            meta = " · ".join(p for p in (f"★ {stars:,}", language) if p and p != "★ 0")
            if meta:
                snippet_parts.append(meta)
            results.append(
                RawResult(
                    title=full_name,
                    url=url,
                    snippet=" — ".join(snippet_parts),
                    position=len(results) + 1,
                    result_type=ResultType.CODE,
                    published_at=item.get("pushed_at"),
                    extra={"stars": stars, "language": language},
                )
            )
        return results
