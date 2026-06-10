"""Reddit search via the public JSON endpoint."""

from __future__ import annotations

import httpx

from zen.search.http import resilient_get
from zen.search.models import ProviderCategory, RawResult, ResultType, SearchQuery
from zen.search.providers.base import SearchProvider


class RedditProvider(SearchProvider):
    slug = "reddit"
    name = "Reddit"
    category = ProviderCategory.SOCIAL
    default_weight = 0.9
    supports_paging = False
    description = "Reddit posts via the public JSON search endpoint."

    BASE = "https://www.reddit.com/search.json"

    async def search(self, query: SearchQuery, client: httpx.AsyncClient) -> list[RawResult]:
        response = await resilient_get(
            client,
            self.BASE,
            params={
                "q": query.text,
                "limit": "15",
                "sort": "relevance",
                "include_over_18": "off" if query.safe_search else "on",
            },
            headers={"Accept": "application/json"},
        )
        payload = response.json()
        results: list[RawResult] = []
        for child in (payload.get("data") or {}).get("children", []):
            post = child.get("data") or {}
            title = post.get("title", "")
            permalink = post.get("permalink", "")
            if not title or not permalink:
                continue
            selftext = (post.get("selftext") or "")[:300]
            subreddit = post.get("subreddit_name_prefixed", "")
            score = post.get("score", 0)
            comments = post.get("num_comments", 0)
            snippet = selftext or f"{subreddit} · {score:,} points · {comments:,} comments"
            results.append(
                RawResult(
                    title=title,
                    url=f"https://www.reddit.com{permalink}",
                    snippet=snippet,
                    position=len(results) + 1,
                    result_type=ResultType.SOCIAL,
                    extra={"subreddit": subreddit, "score": score, "comments": comments},
                )
            )
        return results
