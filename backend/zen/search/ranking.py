"""Ranking engine.

The default ranker uses Reciprocal Rank Fusion (RRF) — the standard, robust
method for merging ranked lists from heterogeneous sources — extended with
Zen's configurable factors:

* provider confidence (admin/profile weights)
* consensus (inherent in RRF summation)
* domain rules (pin / block / boost / lower) at instance, profile, user scope
* personal signals (domains the user bookmarked or clicked)

Rankers are replaceable through the plugin SDK (``register_ranker``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from zen.search.models import SearchResult

RRF_K = 10.0

DEFAULT_FACTOR_WEIGHTS = {
    "provider_confidence": 1.0,
    "domain_rules": 1.0,
    "personal": 1.0,
}


@dataclass(slots=True)
class RankingContext:
    """Everything a ranker may use. Built by the engine per search."""

    query: str = ""
    provider_weights: dict[str, float] = field(default_factory=dict)
    #: domain → multiplier (>1 boost, <1 lower). From rules and profile config.
    domain_weights: dict[str, float] = field(default_factory=dict)
    pinned_domains: set[str] = field(default_factory=set)
    blocked_domains: set[str] = field(default_factory=set)
    #: Domains the user has bookmarked / clicked. Empty in privacy mode.
    personal_domains: set[str] = field(default_factory=set)
    factor_weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_FACTOR_WEIGHTS))


class Ranker(Protocol):
    name: str

    def rank(self, results: list[SearchResult], ctx: RankingContext) -> list[SearchResult]: ...


def _domain_matches(domain: str, rule_domain: str) -> bool:
    """``example.com`` matches itself and any subdomain."""
    return domain == rule_domain or domain.endswith("." + rule_domain)


def _lookup_domain_factor(domain: str, weights: dict[str, float]) -> float:
    factor = 1.0
    for rule_domain, weight in weights.items():
        if _domain_matches(domain, rule_domain):
            factor *= weight
    return factor


def _in_domain_set(domain: str, domains: set[str]) -> bool:
    return any(_domain_matches(domain, d) for d in domains)


class RRFRanker:
    """Reciprocal Rank Fusion with Zen factor extensions."""

    name = "rrf"

    def rank(self, results: list[SearchResult], ctx: RankingContext) -> list[SearchResult]:
        fw = {**DEFAULT_FACTOR_WEIGHTS, **ctx.factor_weights}
        kept: list[SearchResult] = []
        for result in results:
            if ctx.blocked_domains and _in_domain_set(result.domain, ctx.blocked_domains):
                continue
            base = 0.0
            for slug, position in result.positions.items():
                provider_weight = ctx.provider_weights.get(slug, 1.0)
                confidence = 1.0 + (provider_weight - 1.0) * fw["provider_confidence"]
                base += max(confidence, 0.0) / (RRF_K + position)
            domain_factor = _lookup_domain_factor(result.domain, ctx.domain_weights)
            domain_factor = 1.0 + (domain_factor - 1.0) * fw["domain_rules"]
            score = base * max(domain_factor, 0.0)
            if ctx.personal_domains and _in_domain_set(result.domain, ctx.personal_domains):
                score *= 1.0 + 0.15 * fw["personal"]
            if ctx.pinned_domains and _in_domain_set(result.domain, ctx.pinned_domains):
                result.pinned = True
            result.score = score
            kept.append(result)
        kept.sort(key=lambda r: (not r.pinned, -r.score))
        return kept


_rankers: dict[str, Ranker] = {}


def register_ranker(ranker: Ranker, *, replace: bool = False) -> None:
    if not replace and ranker.name in _rankers:
        raise ValueError(f"Ranker '{ranker.name}' is already registered.")
    _rankers[ranker.name] = ranker


def unregister_ranker(name: str) -> None:
    if name == "rrf":
        raise ValueError("The built-in 'rrf' ranker cannot be removed.")
    _rankers.pop(name, None)


def get_ranker(name: str = "rrf") -> Ranker:
    return _rankers.get(name) or _rankers["rrf"]


def available_rankers() -> list[str]:
    return sorted(_rankers)


register_ranker(RRFRanker())
