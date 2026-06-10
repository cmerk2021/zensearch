"""Unit tests for bangs and search modes."""

from zen.search.bangs import all_bangs, parse_bang, resolve_bang
from zen.search.models import SearchResult
from zen.search.modes import apply_focus_filter, get_mode


def test_parse_bang_positions():
    assert parse_bang("!gh fastapi") == ("gh", "fastapi")
    assert parse_bang("fastapi !gh") == ("gh", "fastapi")
    assert parse_bang("rust !so borrow checker") == ("so", "rust borrow checker")
    assert parse_bang("no bang here") is None
    assert parse_bang("not!abang") is None


def test_resolve_bang_encodes_query():
    url = resolve_bang("!gh fastapi middleware")
    assert url == "https://github.com/search?q=fastapi+middleware"


def test_resolve_unknown_bang_returns_none():
    assert resolve_bang("!doesnotexist query") is None


def test_custom_bangs_shadow_builtins():
    custom = {"gh": "https://internal.git.example.com/search?q={q}"}
    url = resolve_bang("!gh thing", custom)
    assert url.startswith("https://internal.git.example.com/")
    assert "gh" in all_bangs(custom)


def test_mode_behaviors():
    assert get_mode("normal").record_history is True
    privacy = get_mode("privacy")
    assert privacy.record_history is False
    assert privacy.use_personalization is False
    assert privacy.use_cache is False
    assert get_mode("focus").filter_focus_categories is True
    assert get_mode("research").associate_workspace is True
    assert get_mode("nonexistent").slug == "normal"


def _result(domain: str) -> SearchResult:
    return SearchResult(
        title=domain, url=f"https://{domain}/", snippet="", domain=domain
    )


def test_focus_filter_blocks_distractions():
    results = [
        _result("github.com"),
        _result("facebook.com"),
        _result("m.facebook.com"),
        _result("amazon.com"),
        _result("docs.python.org"),
    ]
    filtered = apply_focus_filter(results)
    domains = [r.domain for r in filtered]
    assert domains == ["github.com", "docs.python.org"]


def test_focus_filter_extra_domains():
    results = [_result("github.com"), _result("custom-distraction.io")]
    filtered = apply_focus_filter(results, {"custom-distraction.io"})
    assert [r.domain for r in filtered] == ["github.com"]
