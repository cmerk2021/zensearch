"""YouTube search by extracting the ytInitialData JSON island."""

from __future__ import annotations

import json
import re

import httpx

from zen.search.http import resilient_get
from zen.search.models import ProviderCategory, RawResult, ResultType, SearchQuery
from zen.search.providers.base import SearchProvider

_YT_INITIAL_DATA = re.compile(r"var ytInitialData\s*=\s*(\{.+?\});\s*</script>", re.DOTALL)


class YouTubeProvider(SearchProvider):
    slug = "youtube"
    name = "YouTube"
    category = ProviderCategory.VIDEO
    default_weight = 0.9
    supports_paging = False
    description = "YouTube videos parsed from the results page data island."

    BASE = "https://www.youtube.com/results"

    async def search(self, query: SearchQuery, client: httpx.AsyncClient) -> list[RawResult]:
        response = await resilient_get(
            client,
            self.BASE,
            params={"search_query": query.text, "hl": query.locale or "en"},
            headers={"Cookie": "CONSENT=YES+1; SOCS=CAI"},
        )
        return self.parse(response.text)

    def parse(self, html: str) -> list[RawResult]:
        match = _YT_INITIAL_DATA.search(html)
        if not match:
            return []
        try:
            data = json.loads(match.group(1))
        except ValueError:
            return []
        results: list[RawResult] = []
        for renderer in self._walk_video_renderers(data):
            video_id = renderer.get("videoId", "")
            title_runs = (renderer.get("title") or {}).get("runs") or []
            title = "".join(r.get("text", "") for r in title_runs)
            if not video_id or not title:
                continue
            owner = ""
            owner_runs = ((renderer.get("ownerText") or {}).get("runs")) or []
            if owner_runs:
                owner = owner_runs[0].get("text", "")
            length = ((renderer.get("lengthText") or {}).get("simpleText")) or ""
            views = ((renderer.get("viewCountText") or {}).get("simpleText")) or ""
            published = ((renderer.get("publishedTimeText") or {}).get("simpleText")) or None
            thumbs = ((renderer.get("thumbnail") or {}).get("thumbnails")) or []
            thumbnail = thumbs[-1].get("url") if thumbs else None
            snippet = " · ".join(p for p in (owner, length, views) if p)
            results.append(
                RawResult(
                    title=title,
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    snippet=snippet,
                    position=len(results) + 1,
                    result_type=ResultType.VIDEO,
                    published_at=published,
                    thumbnail=thumbnail,
                )
            )
            if len(results) >= 12:
                break
        return results

    @staticmethod
    def _walk_video_renderers(data: dict):
        """Depth-first walk yielding every videoRenderer dict."""
        stack: list = [data]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                renderer = node.get("videoRenderer")
                if isinstance(renderer, dict):
                    yield renderer
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)
