"""Result processing pipeline: normalization, canonicalization, dedup, enrichment."""

from __future__ import annotations

import re
import urllib.parse

from zen.search.models import RawResult, ResultType, SearchResult

MAX_SNIPPET_LENGTH = 400
MAX_TITLE_LENGTH = 300

#: Query parameters stripped during canonicalization (tracking noise).
TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "utm_id",
    "fbclid", "gclid", "gclsrc", "dclid", "msclkid", "twclid", "igshid",
    "mc_cid", "mc_eid", "ref", "ref_src", "ref_url", "referrer",
    "spm", "scm", "share_id", "si", "feature",
    "_hsenc", "_hsmi", "hsa_acc", "hsa_cam",
    "vero_id", "wickedid", "yclid", "rb_clickid", "s_cid", "ws_ab_test",
}

_WHITESPACE = re.compile(r"[\s\u200b\u200e\u200f]+")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def clean_text(text: str, max_length: int) -> str:
    text = _WHITESPACE.sub(" ", text).strip()
    text = _CONTROL.sub("", text)
    if len(text) > max_length:
        text = text[: max_length - 1].rstrip() + "…"
    return text


def canonicalize_url(url: str) -> str:
    """Normalize a URL for storage/display: strip tracking params and fragments."""
    try:
        parsed = urllib.parse.urlsplit(url.strip())
    except ValueError:
        return ""
    if parsed.scheme not in ("http", "https"):
        return ""
    host = parsed.hostname or ""
    if not host:
        return ""
    port = parsed.port
    netloc = host.lower()
    if port and not (parsed.scheme == "http" and port == 80) and not (
        parsed.scheme == "https" and port == 443
    ):
        netloc = f"{netloc}:{port}"
    query_pairs = [
        (k, v)
        for k, v in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        if k.lower() not in TRACKING_PARAMS
    ]
    query = urllib.parse.urlencode(query_pairs)
    path = parsed.path or "/"
    return urllib.parse.urlunsplit((parsed.scheme.lower(), netloc, path, query, ""))


def url_dedupe_key(canonical_url: str) -> str:
    """Key treating http/https and www/apex as the same resource."""
    parsed = urllib.parse.urlsplit(canonical_url)
    host = (parsed.hostname or "").removeprefix("www.")
    path = parsed.path.rstrip("/") or "/"
    key = f"{host}{path}"
    if parsed.query:
        key += f"?{parsed.query}"
    return key


def extract_domain(url: str) -> str:
    try:
        host = urllib.parse.urlsplit(url).hostname or ""
    except ValueError:
        return ""
    return host.lower().removeprefix("www.")


def favicon_url_for(domain: str) -> str:
    """Server-proxied favicon (privacy: the client never talks to third parties)."""
    if not domain:
        return ""
    return f"/api/v1/favicon?domain={urllib.parse.quote(domain)}"


def normalize(raw_results: dict[str, list[RawResult]]) -> dict[str, list[RawResult]]:
    """Clean raw provider output; drop invalid entries. Keyed by provider slug."""
    cleaned: dict[str, list[RawResult]] = {}
    for slug, results in raw_results.items():
        keep: list[RawResult] = []
        for result in results:
            url = canonicalize_url(result.url)
            if not url:
                continue
            title = clean_text(result.title, MAX_TITLE_LENGTH)
            if not title:
                continue
            result.url = url
            result.title = title
            result.snippet = clean_text(result.snippet, MAX_SNIPPET_LENGTH)
            keep.append(result)
        cleaned[slug] = keep
    return cleaned


def merge(raw_results: dict[str, list[RawResult]]) -> list[SearchResult]:
    """Deduplicate across providers, merging provenance and best metadata."""
    merged: dict[str, SearchResult] = {}
    order: list[str] = []
    for slug, results in raw_results.items():
        for raw in results:
            key = url_dedupe_key(raw.url)
            existing = merged.get(key)
            if existing is None:
                domain = extract_domain(raw.url)
                merged[key] = SearchResult(
                    title=raw.title,
                    url=raw.url,
                    snippet=raw.snippet,
                    domain=domain,
                    favicon_url=favicon_url_for(domain),
                    providers=[slug],
                    positions={slug: raw.position},
                    result_type=raw.result_type,
                    published_at=raw.published_at,
                    thumbnail=raw.thumbnail,
                )
                order.append(key)
                continue
            if slug not in existing.providers:
                existing.providers.append(slug)
            current = existing.positions.get(slug)
            if current is None or raw.position < current:
                existing.positions[slug] = raw.position
            # Prefer richer metadata.
            if len(raw.snippet) > len(existing.snippet):
                existing.snippet = raw.snippet
            if not existing.thumbnail and raw.thumbnail:
                existing.thumbnail = raw.thumbnail
            if not existing.published_at and raw.published_at:
                existing.published_at = raw.published_at
            # Prefer https over http.
            if existing.url.startswith("http://") and raw.url.startswith("https://"):
                existing.url = raw.url
            # Prefer general web typing only if existing was generic.
            if existing.result_type == ResultType.WEB and raw.result_type != ResultType.WEB:
                existing.result_type = raw.result_type
    return [merged[k] for k in order]


def process(raw_results: dict[str, list[RawResult]]) -> list[SearchResult]:
    """Full pipeline: normalize → merge/dedupe → enrich."""
    return merge(normalize(raw_results))
