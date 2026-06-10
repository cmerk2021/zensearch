"""Reference Zen plugin: Hacker News search via the Algolia API.

Demonstrates the two most common plugin capabilities — a search provider and
a bang. Package as a zip with zen-plugin.json at the root:

    zip -j example-hackernews-1.0.0.zip zen-plugin.json hackernews_provider.py
"""

import httpx

from zen.search.http import resilient_get
from zen.search.models import ProviderCategory, RawResult, ResultType, SearchQuery
from zen.search.providers.base import SearchProvider


class HackerNewsProvider(SearchProvider):
    slug = "hackernews"
    name = "Hacker News"
    category = ProviderCategory.SOCIAL
    default_weight = 0.8
    supports_paging = True
    description = "Hacker News stories via the Algolia search API."

    API = "https://hn.algolia.com/api/v1/search"

    async def search(self, query: SearchQuery, client: httpx.AsyncClient) -> list[RawResult]:
        response = await resilient_get(
            client,
            self.API,
            params={
                "query": query.text,
                "tags": "story",
                "hitsPerPage": "12",
                "page": str(query.page - 1),
            },
            headers={"Accept": "application/json"},
        )
        payload = response.json()
        results: list[RawResult] = []
        for hit in payload.get("hits", []):
            title = hit.get("title") or ""
            object_id = hit.get("objectID") or ""
            if not title or not object_id:
                continue
            url = hit.get("url") or f"https://news.ycombinator.com/item?id={object_id}"
            points = hit.get("points") or 0
            comments = hit.get("num_comments") or 0
            results.append(
                RawResult(
                    title=title,
                    url=url,
                    snippet=f"{points} points · {comments} comments on Hacker News",
                    position=len(results) + 1,
                    result_type=ResultType.SOCIAL,
                    published_at=hit.get("created_at"),
                )
            )
        return results


def setup(ctx) -> None:
    ctx.register_search_provider(HackerNewsProvider)
    ctx.register_bang("hnews", "https://hn.algolia.com/?q={q}")
