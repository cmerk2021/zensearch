"""Unit tests for the result pipeline (canonicalization, dedup, merging)."""

from zen.search.models import RawResult, ResultType
from zen.search.pipeline import (
    canonicalize_url,
    clean_text,
    extract_domain,
    merge,
    normalize,
    process,
    url_dedupe_key,
)


def test_canonicalize_strips_tracking():
    url = "https://example.com/page?utm_source=x&utm_medium=y&id=5&fbclid=abc#section"
    assert canonicalize_url(url) == "https://example.com/page?id=5"


def test_canonicalize_rejects_non_http():
    assert canonicalize_url("javascript:alert(1)") == ""
    assert canonicalize_url("ftp://example.com/file") == ""
    assert canonicalize_url("not a url") == ""
    assert canonicalize_url("") == ""


def test_canonicalize_normalizes_host_case_and_ports():
    assert canonicalize_url("HTTPS://Example.COM:443/Path") == "https://example.com/Path"
    assert canonicalize_url("http://example.com:80/") == "http://example.com/"
    assert canonicalize_url("http://example.com:8080/x") == "http://example.com:8080/x"


def test_dedupe_key_treats_www_and_scheme_as_same():
    a = url_dedupe_key(canonicalize_url("https://www.example.com/page/"))
    b = url_dedupe_key(canonicalize_url("http://example.com/page"))
    assert a == b


def test_extract_domain():
    assert extract_domain("https://www.Example.com/x") == "example.com"
    assert extract_domain("https://sub.example.co.uk/") == "sub.example.co.uk"


def test_clean_text_collapses_whitespace_and_truncates():
    assert clean_text("  a\u200b  b\n\nc  ", 100) == "a b c"
    long = clean_text("x" * 500, 100)
    assert len(long) == 100 and long.endswith("…")


def test_normalize_drops_invalid_entries():
    raw = {
        "google": [
            RawResult(title="OK", url="https://example.com/a"),
            RawResult(title="", url="https://example.com/b"),
            RawResult(title="Bad URL", url="javascript:x"),
        ]
    }
    cleaned = normalize(raw)
    assert len(cleaned["google"]) == 1


def test_merge_unions_providers_and_keeps_best_metadata():
    raw = {
        "google": [
            RawResult(title="Result", url="https://example.com/a", snippet="short", position=1)
        ],
        "bing": [
            RawResult(
                title="Result",
                url="https://www.example.com/a",
                snippet="a much longer and more descriptive snippet",
                position=3,
                thumbnail="https://img.example.com/t.png",
            )
        ],
    }
    merged = merge(normalize(raw))
    assert len(merged) == 1
    result = merged[0]
    assert set(result.providers) == {"google", "bing"}
    assert result.positions == {"google": 1, "bing": 3}
    assert "longer" in result.snippet
    assert result.thumbnail == "https://img.example.com/t.png"


def test_merge_prefers_https():
    raw = {
        "a": [RawResult(title="R", url="http://example.com/x", position=1)],
        "b": [RawResult(title="R", url="https://example.com/x", position=1)],
    }
    merged = merge(normalize(raw))
    assert merged[0].url.startswith("https://")


def test_process_full_pipeline():
    raw = {
        "google": [
            RawResult(title="A", url="https://a.com/1?utm_source=g", position=1),
            RawResult(title="B", url="https://b.com/2", position=2),
        ],
        "wikipedia": [
            RawResult(
                title="A again",
                url="https://a.com/1",
                position=1,
                result_type=ResultType.REFERENCE,
            )
        ],
    }
    results = process(raw)
    assert len(results) == 2
    first = next(r for r in results if r.domain == "a.com")
    assert set(first.providers) == {"google", "wikipedia"}
    assert first.result_type == ResultType.REFERENCE


async def test_collect_with_quorum_trims_slow_tail(monkeypatch):
    """Once a quorum of providers returns, slow stragglers are trimmed."""
    import asyncio

    from zen.search import engine as engine_mod

    monkeypatch.setattr(engine_mod, "PROVIDER_TAIL_GRACE_SECONDS", 0.05)
    eng = engine_mod.SearchEngine(db=None)

    async def fast(slug: str):
        return slug, [], 1

    async def slow(slug: str):
        await asyncio.sleep(5)
        return slug, [], 1

    tasks = {
        asyncio.create_task(fast("a")): "a",
        asyncio.create_task(fast("b")): "b",
        asyncio.create_task(fast("c")): "c",
        asyncio.create_task(slow("d")): "d",
        asyncio.create_task(slow("e")): "e",
    }
    outcomes = await eng._collect_with_quorum(tasks)

    by_slug = {slug: outcome for slug, outcome, _ in outcomes}
    assert by_slug["a"] == []
    assert by_slug["b"] == []
    assert by_slug["c"] == []
    assert isinstance(by_slug["d"], engine_mod._TailTrimmed)
    assert isinstance(by_slug["e"], engine_mod._TailTrimmed)
