"""Unit tests for provider HTML/JSON parsers using captured fixtures."""

import httpx
import pytest
import respx

from zen.search.models import SearchQuery
from zen.search.providers.bing import BingProvider
from zen.search.providers.duckduckgo import DuckDuckGoProvider
from zen.search.providers.github import GitHubProvider
from zen.search.providers.google import GoogleProvider
from zen.search.providers.reddit import RedditProvider
from zen.search.providers.stackoverflow import StackOverflowProvider
from zen.search.providers.wikipedia import WikipediaProvider
from zen.search.providers.youtube import YouTubeProvider

GOOGLE_HTML = """
<html><body>
<div id="search">
  <div class="g">
    <a href="/url?q=https://fastapi.tiangolo.com/&sa=U"><h3>FastAPI</h3></a>
    <div class="VwiC3b">FastAPI is a modern, fast web framework for building APIs with Python based on standard type hints.</div>
  </div>
  <div class="g">
    <a href="https://github.com/fastapi/fastapi"><h3>fastapi/fastapi GitHub</h3></a>
    <div class="VwiC3b">FastAPI framework, high performance, easy to learn, fast to code, ready for production and more text here.</div>
  </div>
  <div class="g">
    <a href="https://www.google.com/internal"><h3>Should be excluded</h3></a>
  </div>
</div>
</body></html>
"""

BING_HTML = """
<html><body><ol id="b_results">
<li class="b_algo">
  <h2><a href="https://www.python.org/">Welcome to Python.org</a></h2>
  <div class="b_caption"><p>The official home of the Python Programming Language.</p></div>
</li>
<li class="b_algo">
  <h2><a href="https://docs.python.org/3/">3.13 Documentation</a></h2>
  <div class="b_caption"><p>The official Python documentation.</p></div>
</li>
</ol></body></html>
"""

DDG_HTML = """
<html><body>
<div class="result web-result">
  <h2 class="result__title"><a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.rust-lang.org%2F&rut=abc">Rust Programming Language</a></h2>
  <a class="result__snippet" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.rust-lang.org%2F">A language empowering everyone to build reliable and efficient software.</a>
</div>
<div class="result result--ad">
  <h2 class="result__title"><a class="result__a" href="https://ad.example.com/">Sponsored thing</a></h2>
</div>
</body></html>
"""


def test_google_parser():
    results = GoogleProvider().parse(GOOGLE_HTML)
    assert len(results) == 2
    assert results[0].url == "https://fastapi.tiangolo.com/"
    assert results[0].title == "FastAPI"
    assert "modern" in results[0].snippet
    assert results[1].url == "https://github.com/fastapi/fastapi"


def test_bing_parser():
    results = BingProvider().parse(BING_HTML)
    assert len(results) == 2
    assert results[0].url == "https://www.python.org/"
    assert "official home" in results[0].snippet


def test_bing_redirect_decoding():
    # u param: base64url of https://example.com/ prefixed with a1
    decoded = BingProvider._decode_url(
        "https://www.bing.com/ck/a?!&&p=x&u=a1aHR0cHM6Ly9leGFtcGxlLmNvbS8&ntb=1"
    )
    assert decoded == "https://example.com/"
    assert BingProvider._decode_url("https://direct.example.com/page") == (
        "https://direct.example.com/page"
    )


def test_duckduckgo_parser_unwraps_and_skips_ads():
    results = DuckDuckGoProvider().parse(DDG_HTML)
    assert len(results) == 1
    assert results[0].url == "https://www.rust-lang.org/"
    assert "reliable" in results[0].snippet


@respx.mock
async def test_wikipedia_provider():
    respx.get(url__regex=r"https://en\.wikipedia\.org/w/api\.php.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "query": {
                    "search": [
                        {
                            "title": "Python (programming language)",
                            "snippet": 'high-level <span class="searchmatch">language</span>',
                            "timestamp": "2024-01-01T00:00:00Z",
                        }
                    ]
                }
            },
        )
    )
    async with httpx.AsyncClient() as client:
        results = await WikipediaProvider().search(SearchQuery(text="python"), client)
    assert len(results) == 1
    assert results[0].url == "https://en.wikipedia.org/wiki/Python_(programming_language)"
    assert "high-level language" in results[0].snippet


@respx.mock
async def test_github_provider():
    respx.get(url__regex=r"https://api\.github\.com/search/repositories.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "full_name": "fastapi/fastapi",
                        "html_url": "https://github.com/fastapi/fastapi",
                        "description": "FastAPI framework",
                        "stargazers_count": 75000,
                        "language": "Python",
                        "pushed_at": "2024-06-01T00:00:00Z",
                    }
                ]
            },
        )
    )
    async with httpx.AsyncClient() as client:
        results = await GitHubProvider().search(SearchQuery(text="fastapi"), client)
    assert len(results) == 1
    assert results[0].title == "fastapi/fastapi"
    assert "75,000" in results[0].snippet


@respx.mock
async def test_reddit_provider():
    respx.get(url__regex=r"https://www\.reddit\.com/search\.json.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "children": [
                        {
                            "data": {
                                "title": "Best self-hosted search?",
                                "permalink": "/r/selfhosted/comments/abc/best/",
                                "selftext": "",
                                "subreddit_name_prefixed": "r/selfhosted",
                                "score": 412,
                                "num_comments": 89,
                            }
                        }
                    ]
                }
            },
        )
    )
    async with httpx.AsyncClient() as client:
        results = await RedditProvider().search(SearchQuery(text="search"), client)
    assert len(results) == 1
    assert results[0].url.startswith("https://www.reddit.com/r/selfhosted/")
    assert "412" in results[0].snippet


@respx.mock
async def test_stackoverflow_provider():
    respx.get(url__regex=r"https://api\.stackexchange\.com/2\.3/search/advanced.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "title": "How do I use async &amp; await?",
                        "link": "https://stackoverflow.com/q/1",
                        "is_answered": True,
                        "answer_count": 5,
                        "score": 100,
                        "tags": ["python", "async"],
                    }
                ]
            },
        )
    )
    async with httpx.AsyncClient() as client:
        results = await StackOverflowProvider().search(SearchQuery(text="async"), client)
    assert len(results) == 1
    assert results[0].title == "How do I use async & await?"
    assert "✓ answered" in results[0].snippet


def test_youtube_parser():
    html = (
        "<html><script>var ytInitialData = "
        '{"contents": {"x": [{"videoRenderer": {"videoId": "abc123", '
        '"title": {"runs": [{"text": "Zen demo"}]}, '
        '"ownerText": {"runs": [{"text": "ZenChannel"}]}, '
        '"lengthText": {"simpleText": "10:32"}, '
        '"viewCountText": {"simpleText": "1,234 views"}, '
        '"thumbnail": {"thumbnails": [{"url": "https://i.ytimg.com/x.jpg"}]}}}]}}'
        ";</script></html>"
    )
    results = YouTubeProvider().parse(html)
    assert len(results) == 1
    assert results[0].url == "https://www.youtube.com/watch?v=abc123"
    assert results[0].title == "Zen demo"
    assert "ZenChannel" in results[0].snippet


def test_youtube_parser_handles_missing_data():
    assert YouTubeProvider().parse("<html>no data island</html>") == []


def test_provider_info_contract():
    from zen.search.providers import all_providers

    for slug, cls in all_providers().items():
        info = cls.info()
        assert info["slug"] == slug
        assert info["name"]
        assert isinstance(info["default_weight"], float | int)


@pytest.mark.parametrize("provider_count", [12])
def test_builtin_provider_count(provider_count):
    from zen.search.providers import BUILTIN_PROVIDERS

    assert len(BUILTIN_PROVIDERS) == provider_count
