"""Search orchestration: the engine that executes a Zen search end-to-end.

Flow (ADR-0009, modes, profiles):

1. Bang resolution → immediate redirect.
2. Mode + profile resolution.
3. Provider selection: registry ∩ admin-enabled ∩ profile ∩ mode ∩ circuit.
4. Concurrent execution with per-provider timeout envelopes.
5. Pipeline: normalize → dedupe/merge → enrich.
6. Ranking with instance/profile/user signals.
7. Mode filters, history recording, caching.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import math
import time

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from zen.core.cache import get_cache
from zen.core.config import get_settings
from zen.db.models import (
    Bookmark,
    ClickEvent,
    DomainRule,
    ProviderConfig,
    RuleAction,
    RuleScope,
    SearchHistory,
    SearchProfile,
    User,
)
from zen.observability import metrics
from zen.search import health as provider_health
from zen.search.bangs import resolve_bang
from zen.search.http import build_search_client
from zen.search.models import (
    ProviderStatus,
    RawResult,
    SearchQuery,
    SearchResponse,
    SearchResult,
)
from zen.search.modes import FOCUS_EXCLUDED_CATEGORIES, apply_focus_filter, get_mode
from zen.search.pipeline import process
from zen.search.providers import all_providers
from zen.search.ranking import RankingContext, get_ranker
from zen.services.settings import SettingsService

log = structlog.get_logger(__name__)

RESULT_CACHE_TTL = 300
PERSONAL_SIGNALS_TTL = 300
MAX_RESULTS = 50

#: Once this fraction of providers has returned, only wait a short grace period
#: for the remainder before trimming the slow tail. This bounds tail latency so
#: one slow upstream cannot hold the whole search hostage.
PROVIDER_QUORUM_FRACTION = 0.6
PROVIDER_TAIL_GRACE_SECONDS = 2.0


class _TailTrimmed(Exception):
    """Marker: a provider was cancelled because it exceeded the tail deadline."""


class SearchEngine:
    """Stateless orchestrator; all state flows through arguments and caches."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.settings_service = SettingsService(db)

    async def execute(
        self,
        *,
        query_text: str,
        user: User | None,
        mode_slug: str = "normal",
        profile_slug: str | None = None,
        page: int = 1,
        providers_override: list[str] | None = None,
        workspace_id: str | None = None,
    ) -> SearchResponse:
        started = time.perf_counter()
        query_text = query_text.strip()
        mode = get_mode(mode_slug)

        # 1. Bangs --------------------------------------------------------
        from zen.plugins.sdk import plugin_bangs

        custom_bangs = {
            **plugin_bangs(),
            **(await self.settings_service.get("search.custom_bangs", {}) or {}),
        }
        redirect = resolve_bang(query_text, custom_bangs)
        if redirect:
            return SearchResponse(
                query=query_text, mode=mode.slug, page=page, redirect=redirect
            )

        # 2. Profile ------------------------------------------------------
        profile = await self._resolve_profile(profile_slug, user)

        # 3. Providers ----------------------------------------------------
        provider_configs = await self._provider_configs()
        selected = self._select_providers(
            provider_configs=provider_configs,
            profile=profile,
            filter_focus=mode.filter_focus_categories,
            override=providers_override,
        )

        # 4. Cache lookup ---------------------------------------------------
        cache_key = self._cache_key(query_text, page, mode.slug, profile, sorted(selected))
        if mode.use_cache:
            cached = await get_cache().get(cache_key)
            if cached:
                try:
                    response = self._response_from_cache(json.loads(cached))
                    response.cached = True
                    response.workspace_id = workspace_id if mode.associate_workspace else None
                    metrics.SEARCHES_TOTAL.labels(mode=mode.slug, cached="true").inc()
                    return response
                except (ValueError, KeyError, TypeError):
                    pass

        # 5-7. Fetch providers (network-bound) concurrently with building the
        # ranking context (DB-bound). They are independent — the provider tasks
        # never touch the DB session — so overlapping them removes the DB round
        # trips from the critical path. ``settings_service`` and the ranking
        # context share ``self.db``; the provider branch does not, keeping the
        # single AsyncSession free of concurrent use.
        ranker_name = await self.settings_service.get("search.ranker", "rrf")
        (statuses, raw_results), ctx = await asyncio.gather(
            self._run_providers(selected, provider_configs, query_text, page),
            self._build_ranking_context(
                query_text, user, profile, provider_configs, mode.use_personalization
            ),
        )

        # 6. Pipeline -------------------------------------------------------
        results = process(raw_results)

        # 7. Ranking --------------------------------------------------------
        results = get_ranker(ranker_name).rank(results, ctx)

        # 8. Mode filters ----------------------------------------------------
        if mode.filter_focus_categories:
            extra = set(await self.settings_service.get("search.focus_blocked_domains", []))
            results = apply_focus_filter(results, extra)
        results = results[:MAX_RESULTS]

        duration_ms = int((time.perf_counter() - started) * 1000)
        response = SearchResponse(
            query=query_text,
            mode=mode.slug,
            page=page,
            results=results,
            providers=statuses,
            duration_ms=duration_ms,
            profile_slug=profile.slug if profile else None,
            workspace_id=workspace_id if mode.associate_workspace else None,
        )

        # 9. Record + cache ---------------------------------------------------
        if mode.record_history and user is not None:
            await self._record_history(response, user, profile, workspace_id)
        if mode.use_cache and any(s.ok for s in statuses):
            await get_cache().set(
                cache_key, json.dumps(self._response_to_cache(response)), ttl=RESULT_CACHE_TTL
            )
        metrics.SEARCHES_TOTAL.labels(mode=mode.slug, cached="false").inc()
        metrics.SEARCH_DURATION.observe(duration_ms / 1000)
        return response

    # ------------------------------------------------------------------
    # Provider selection & execution
    # ------------------------------------------------------------------

    async def _provider_configs(self) -> dict[str, ProviderConfig]:
        rows = (await self.db.execute(select(ProviderConfig))).scalars().all()
        return {row.slug: row for row in rows}

    def _select_providers(
        self,
        *,
        provider_configs: dict[str, ProviderConfig],
        profile: SearchProfile | None,
        filter_focus: bool,
        override: list[str] | None,
    ) -> list[str]:
        registry = all_providers()
        selected: list[str] = []
        profile_providers = set(profile.providers or []) if profile else set()
        for slug, cls in registry.items():
            config = provider_configs.get(slug)
            enabled = config.enabled if config is not None else True
            if not enabled:
                continue
            if cls.requires_api_key and not (config and config.api_key_encrypted):
                continue
            if profile_providers and slug not in profile_providers:
                continue
            if filter_focus and cls.category in FOCUS_EXCLUDED_CATEGORIES:
                continue
            selected.append(slug)
        if override:
            allowed = set(selected)
            selected = [s for s in override if s in allowed]
        return selected

    async def _run_providers(
        self,
        selected: list[str],
        provider_configs: dict[str, ProviderConfig],
        query_text: str,
        page: int,
    ) -> tuple[list[ProviderStatus], dict[str, list[RawResult]]]:
        registry = all_providers()
        settings = get_settings()
        secret_key = settings.secret_key
        statuses: list[ProviderStatus] = []
        raw_results: dict[str, list[RawResult]] = {}
        runnable: list[tuple[str, float]] = []

        for slug in selected:
            available, reason = await provider_health.is_available(slug)
            if not available:
                statuses.append(
                    ProviderStatus(
                        slug=slug,
                        name=registry[slug].name,
                        ok=False,
                        skipped=True,
                        skip_reason=reason,
                    )
                )
                continue
            config = provider_configs.get(slug)
            timeout = (
                config.timeout_seconds
                if config and config.timeout_seconds
                else registry[slug].default_timeout
            )
            runnable.append((slug, timeout))

        if not runnable:
            return statuses, raw_results

        max_timeout = max(t for _, t in runnable)
        async with build_search_client(timeout=max_timeout) as client:

            async def run_one(slug: str, timeout: float) -> tuple[str, list[RawResult] | Exception, int]:
                cls = registry[slug]
                config = provider_configs.get(slug)
                api_key = ""
                if config and config.api_key_encrypted:
                    from zen.core.security import decrypt_secret

                    try:
                        api_key = decrypt_secret(config.api_key_encrypted, secret_key)
                    except ValueError:
                        log.warning("provider.key_decrypt_failed", provider=slug)
                provider = cls(config=config.config if config else {}, api_key=api_key)
                query = SearchQuery(text=query_text, page=page)
                start = time.perf_counter()
                try:
                    results = await asyncio.wait_for(
                        provider.search(query, client), timeout=timeout
                    )
                    elapsed = int((time.perf_counter() - start) * 1000)
                    return slug, results, elapsed
                except Exception as exc:
                    elapsed = int((time.perf_counter() - start) * 1000)
                    return slug, exc, elapsed

            outcomes = await self._collect_with_quorum(
                {
                    asyncio.create_task(run_one(slug, timeout)): slug
                    for slug, timeout in runnable
                }
            )

        for slug, outcome, elapsed in outcomes:
            cls = registry[slug]
            if isinstance(outcome, _TailTrimmed):
                statuses.append(
                    ProviderStatus(
                        slug=slug,
                        name=cls.name,
                        ok=False,
                        skipped=True,
                        skip_reason="slow response (tail-trimmed)",
                        duration_ms=elapsed,
                    )
                )
                continue
            if isinstance(outcome, Exception):
                error = f"{type(outcome).__name__}: {outcome}"[:300]
                statuses.append(
                    ProviderStatus(
                        slug=slug, name=cls.name, ok=False, duration_ms=elapsed, error=error
                    )
                )
                await provider_health.record_failure(slug, error)
                metrics.PROVIDER_REQUESTS.labels(provider=slug, outcome="error").inc()
                log.warning("provider.failed", provider=slug, error=error)
                continue
            raw_results[slug] = outcome
            statuses.append(
                ProviderStatus(
                    slug=slug,
                    name=cls.name,
                    ok=True,
                    result_count=len(outcome),
                    duration_ms=elapsed,
                )
            )
            await provider_health.record_success(slug, elapsed)
            metrics.PROVIDER_REQUESTS.labels(provider=slug, outcome="ok").inc()
            metrics.PROVIDER_LATENCY.labels(provider=slug).observe(elapsed / 1000)
        return statuses, raw_results

    async def _collect_with_quorum(
        self, tasks: dict[asyncio.Task, str]
    ) -> list[tuple[str, list[RawResult] | Exception, int]]:
        """Gather provider results, trimming the slow tail once a quorum returns.

        Providers all run concurrently. As soon as ``PROVIDER_QUORUM_FRACTION`` of
        them have completed, any still-running providers get only
        ``PROVIDER_TAIL_GRACE_SECONDS`` more before being cancelled. Cancelled
        providers are reported as skipped (not failed) so the tail trimming does
        not pollute circuit-breaker health state.
        """
        pending: set[asyncio.Task] = set(tasks)
        outcomes: list[tuple[str, list[RawResult] | Exception, int]] = []
        total = len(tasks)
        quorum = max(1, math.ceil(total * PROVIDER_QUORUM_FRACTION))
        loop = asyncio.get_event_loop()
        deadline: float | None = None
        completed = 0

        while pending:
            timeout = None
            if deadline is not None:
                timeout = max(0.0, deadline - loop.time())
            done, pending = await asyncio.wait(
                pending, timeout=timeout, return_when=asyncio.FIRST_COMPLETED
            )
            if not done:
                # Tail grace elapsed: cancel the stragglers.
                for task in pending:
                    task.cancel()
                for task in pending:
                    with contextlib.suppress(asyncio.CancelledError, Exception):
                        await task
                    outcomes.append((tasks[task], _TailTrimmed(), 0))
                break
            for task in done:
                outcomes.append(task.result())
            completed += len(done)
            if deadline is None and completed >= quorum and pending:
                deadline = loop.time() + PROVIDER_TAIL_GRACE_SECONDS
        return outcomes

    # ------------------------------------------------------------------
    # Ranking context
    # ------------------------------------------------------------------

    async def _build_ranking_context(
        self,
        query_text: str,
        user: User | None,
        profile: SearchProfile | None,
        provider_configs: dict[str, ProviderConfig],
        use_personalization: bool,
    ) -> RankingContext:
        registry = all_providers()
        provider_weights: dict[str, float] = {}
        for slug, cls in registry.items():
            config = provider_configs.get(slug)
            provider_weights[slug] = config.weight if config else cls.default_weight

        domain_weights: dict[str, float] = {}
        pinned: set[str] = set()
        blocked: set[str] = set()

        conditions = [DomainRule.scope == RuleScope.INSTANCE.value]
        if profile is not None:
            conditions.append(
                (DomainRule.scope == RuleScope.PROFILE.value)
                & (DomainRule.profile_id == profile.id)
            )
        if user is not None and use_personalization:
            conditions.append(
                (DomainRule.scope == RuleScope.USER.value) & (DomainRule.user_id == user.id)
            )
        from sqlalchemy import or_

        rules = (
            (await self.db.execute(select(DomainRule).where(or_(*conditions)))).scalars().all()
        )
        for rule in rules:
            if rule.action == RuleAction.BLOCK.value:
                blocked.add(rule.domain)
            elif rule.action == RuleAction.PIN.value:
                pinned.add(rule.domain)
            elif rule.action == RuleAction.BOOST.value:
                domain_weights[rule.domain] = domain_weights.get(rule.domain, 1.0) * max(
                    rule.weight, 1.0
                )
            elif rule.action == RuleAction.LOWER.value:
                domain_weights[rule.domain] = domain_weights.get(rule.domain, 1.0) * min(
                    max(rule.weight, 0.0), 1.0
                )

        factor_weights = dict(
            await self.settings_service.get("search.factor_weights", {}) or {}
        )
        if profile is not None:
            ranking = profile.ranking or {}
            for domain, weight in (ranking.get("domain_weights") or {}).items():
                try:
                    domain_weights[domain] = domain_weights.get(domain, 1.0) * float(weight)
                except (TypeError, ValueError):
                    continue
            factor_weights.update(ranking.get("factor_weights") or {})
            for domain in (profile.filters or {}).get("blocked_domains", []):
                blocked.add(domain)

        personal: set[str] = set()
        if user is not None and use_personalization:
            personal = await self._personal_domains(user.id)

        return RankingContext(
            query=query_text,
            provider_weights=provider_weights,
            domain_weights=domain_weights,
            pinned_domains=pinned,
            blocked_domains=blocked,
            personal_domains=personal,
            factor_weights=factor_weights or {},
        )

    async def _personal_domains(self, user_id: str) -> set[str]:
        cache_key = f"personal:domains:{user_id}"
        cached = await get_cache().get(cache_key)
        if cached:
            try:
                return set(json.loads(cached))
            except ValueError:
                pass
        bookmark_domains = (
            await self.db.execute(
                select(Bookmark.domain)
                .where(Bookmark.owner_id == user_id, Bookmark.domain != "")
                .group_by(Bookmark.domain)
                .limit(500)
            )
        ).scalars().all()
        click_domains = (
            await self.db.execute(
                select(ClickEvent.domain)
                .where(ClickEvent.user_id == user_id, ClickEvent.domain != "")
                .group_by(ClickEvent.domain)
                .order_by(func.max(ClickEvent.created_at).desc())
                .limit(500)
            )
        ).scalars().all()
        domains = set(bookmark_domains) | set(click_domains)
        await get_cache().set(cache_key, json.dumps(sorted(domains)), ttl=PERSONAL_SIGNALS_TTL)
        return domains

    # ------------------------------------------------------------------
    # Profile, history, cache helpers
    # ------------------------------------------------------------------

    async def _resolve_profile(
        self, profile_slug: str | None, user: User | None
    ) -> SearchProfile | None:
        if profile_slug:
            profile = (
                await self.db.execute(
                    select(SearchProfile).where(
                        SearchProfile.slug == profile_slug, SearchProfile.is_active.is_(True)
                    )
                )
            ).scalar_one_or_none()
            if profile is not None:
                return profile
        if user is not None:
            from zen.db.models import UserPreferences

            prefs = await self.db.get(UserPreferences, user.id)
            if prefs is not None and prefs.default_profile_id:
                profile = await self.db.get(SearchProfile, prefs.default_profile_id)
                if profile is not None and profile.is_active:
                    return profile
        return (
            await self.db.execute(
                select(SearchProfile).where(
                    SearchProfile.is_default.is_(True), SearchProfile.is_active.is_(True)
                )
            )
        ).scalar_one_or_none()

    async def _record_history(
        self,
        response: SearchResponse,
        user: User,
        profile: SearchProfile | None,
        workspace_id: str | None,
    ) -> None:
        retention = await self.settings_service.get("privacy.search_history_enabled", True)
        if not retention:
            return
        entry = SearchHistory(
            user_id=user.id,
            workspace_id=workspace_id,
            query=response.query,
            mode=response.mode,
            profile_id=profile.id if profile else None,
            providers=[s.slug for s in response.providers if s.ok],
            result_count=len(response.results),
            duration_ms=response.duration_ms,
        )
        self.db.add(entry)
        await self.db.commit()

    @staticmethod
    def _cache_key(
        query: str, page: int, mode: str, profile: SearchProfile | None, providers: list[str]
    ) -> str:
        basis = json.dumps(
            {
                "q": query.lower(),
                "page": page,
                "mode": mode,
                "profile": profile.slug if profile else "",
                "providers": providers,
            },
            separators=(",", ":"),
        )
        return "search:results:" + hashlib.sha256(basis.encode()).hexdigest()

    @staticmethod
    def _response_to_cache(response: SearchResponse) -> dict:
        return {
            "query": response.query,
            "mode": response.mode,
            "page": response.page,
            "results": [r.to_dict() for r in response.results],
            "providers": [s.to_dict() for s in response.providers],
            "duration_ms": response.duration_ms,
            "profile_slug": response.profile_slug,
        }

    @staticmethod
    def _response_from_cache(data: dict) -> SearchResponse:
        return SearchResponse(
            query=data["query"],
            mode=data["mode"],
            page=data["page"],
            results=[SearchResult.from_dict(r) for r in data["results"]],
            providers=[ProviderStatus(**s) for s in data["providers"]],
            duration_ms=data["duration_ms"],
            profile_slug=data.get("profile_slug"),
        )
