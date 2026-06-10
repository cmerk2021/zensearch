"""Unit tests for the ranking engine."""

from zen.search.models import SearchResult
from zen.search.ranking import RankingContext, RRFRanker


def make_result(domain: str, positions: dict[str, int]) -> SearchResult:
    return SearchResult(
        title=domain,
        url=f"https://{domain}/",
        snippet="",
        domain=domain,
        providers=list(positions),
        positions=positions,
    )


def test_consensus_beats_single_provider():
    ranker = RRFRanker()
    results = [
        make_result("single.com", {"google": 1}),
        make_result("both.com", {"google": 2, "bing": 1}),
    ]
    ranked = ranker.rank(results, RankingContext())
    assert ranked[0].domain == "both.com"


def test_provider_weight_influences_order():
    ranker = RRFRanker()
    results = [
        make_result("a.com", {"google": 1}),
        make_result("b.com", {"kagi": 1}),
    ]
    ctx = RankingContext(provider_weights={"google": 1.0, "kagi": 2.0})
    ranked = ranker.rank(results, ctx)
    assert ranked[0].domain == "b.com"


def test_blocked_domains_are_removed():
    ranker = RRFRanker()
    results = [
        make_result("keep.com", {"google": 1}),
        make_result("spam.com", {"google": 2}),
        make_result("sub.spam.com", {"google": 3}),
    ]
    ctx = RankingContext(blocked_domains={"spam.com"})
    ranked = ranker.rank(results, ctx)
    assert [r.domain for r in ranked] == ["keep.com"]


def test_pinned_domains_rise_to_top():
    ranker = RRFRanker()
    results = [
        make_result("normal.com", {"google": 1, "bing": 1}),
        make_result("pinned.com", {"google": 9}),
    ]
    ctx = RankingContext(pinned_domains={"pinned.com"})
    ranked = ranker.rank(results, ctx)
    assert ranked[0].domain == "pinned.com"
    assert ranked[0].pinned is True


def test_domain_weight_boost_and_lower():
    ranker = RRFRanker()
    results = [
        make_result("boosted.com", {"google": 2}),
        make_result("neutral.com", {"google": 1}),
        make_result("lowered.com", {"google": 1}),
    ]
    ctx = RankingContext(domain_weights={"boosted.com": 3.0, "lowered.com": 0.1})
    ranked = ranker.rank(results, ctx)
    assert ranked[0].domain == "boosted.com"
    assert ranked[-1].domain == "lowered.com"


def test_subdomain_matching():
    ranker = RRFRanker()
    results = [make_result("docs.example.com", {"google": 1})]
    ctx = RankingContext(domain_weights={"example.com": 2.0})
    ranked = ranker.rank(results, ctx)
    base = RRFRanker().rank([make_result("docs.example.com", {"google": 1})], RankingContext())
    assert ranked[0].score > base[0].score


def test_personal_domains_boost():
    ranker = RRFRanker()
    results = [
        make_result("familiar.com", {"google": 2}),
        make_result("unknown.com", {"google": 2}),
    ]
    ctx = RankingContext(personal_domains={"familiar.com"})
    ranked = ranker.rank(results, ctx)
    assert ranked[0].domain == "familiar.com"


def test_factor_weights_can_neutralize_domain_rules():
    ranker = RRFRanker()
    results = [
        make_result("boosted.com", {"google": 2}),
        make_result("neutral.com", {"google": 1}),
    ]
    ctx = RankingContext(
        domain_weights={"boosted.com": 5.0},
        factor_weights={"domain_rules": 0.0},
    )
    ranked = ranker.rank(results, ctx)
    # With the factor neutralized, position wins.
    assert ranked[0].domain == "neutral.com"
