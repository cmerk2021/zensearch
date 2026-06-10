"""Search routes: execution, click signals, bangs, providers, suggestions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from zen.api.deps import DB, OptionalUser, Writer, rate_limited
from zen.db.models import SearchHistory
from zen.schemas.api import ClickRequest, SearchRequest, SearchResponseOut
from zen.schemas.common import Message
from zen.search.bangs import all_bangs
from zen.search.engine import SearchEngine
from zen.search.models import ProviderCategory
from zen.search.providers import all_providers
from zen.services.bookmarks import BookmarkService
from zen.services.settings import SettingsService

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=SearchResponseOut, dependencies=[Depends(rate_limited("search"))])
async def search(
    db: DB,
    user: OptionalUser,
    q: str = Query(min_length=1, max_length=512),
    mode: str = Query(default="normal", pattern="^(normal|privacy|focus|research)$"),
    profile: str | None = Query(default=None, max_length=64),
    page: int = Query(default=1, ge=1, le=10),
    providers: str | None = Query(default=None, max_length=512),
    workspace_id: str | None = Query(default=None, max_length=36),
) -> SearchResponseOut:
    request = SearchRequest(
        q=q,
        mode=mode,
        profile=profile,
        page=page,
        providers=[p.strip() for p in providers.split(",") if p.strip()] if providers else None,
        workspace_id=workspace_id,
    )
    engine = SearchEngine(db)
    response = await engine.execute(
        query_text=request.q,
        user=user,
        mode_slug=request.mode,
        profile_slug=request.profile,
        page=request.page,
        providers_override=request.providers,
        workspace_id=request.workspace_id,
    )
    return SearchResponseOut(
        query=response.query,
        mode=response.mode,
        page=response.page,
        results=[r.to_dict() for r in response.results],
        providers=[s.to_dict() for s in response.providers],
        duration_ms=response.duration_ms,
        cached=response.cached,
        redirect=response.redirect,
        profile_slug=response.profile_slug,
        workspace_id=response.workspace_id,
    )


@router.post("/click", response_model=Message)
async def record_click(payload: ClickRequest, user: Writer, db: DB) -> Message:
    await BookmarkService(db).record_click(
        user, url=payload.url, query=payload.query, provider=payload.provider
    )
    return Message(message="Recorded.")


@router.get("/bangs")
async def list_bangs(db: DB) -> dict[str, str]:
    from zen.plugins.sdk import plugin_bangs

    custom = await SettingsService(db).get("search.custom_bangs", {}) or {}
    return all_bangs({**plugin_bangs(), **custom})


@router.get("/providers")
async def list_public_providers(db: DB) -> list[dict]:
    """Providers visible to users (for filter UI). Enablement is admin-managed."""
    from zen.db.models import ProviderConfig

    configs = {
        row.slug: row
        for row in (await db.execute(select(ProviderConfig))).scalars().all()
    }
    result = []
    for slug, cls in sorted(all_providers().items()):
        config = configs.get(slug)
        enabled = config.enabled if config else True
        if cls.requires_api_key and not (config and config.api_key_encrypted):
            enabled = False
        if enabled:
            result.append(
                {
                    "slug": slug,
                    "name": cls.name,
                    "category": cls.category.value
                    if isinstance(cls.category, ProviderCategory)
                    else str(cls.category),
                }
            )
    return result


@router.get("/suggest")
async def suggest(
    db: DB,
    user: OptionalUser,
    q: str = Query(default="", max_length=256),
) -> list[str]:
    """Personal history-based suggestions. Empty for anonymous/privacy users."""
    if user is None or not q.strip():
        return []
    like = f"{q.strip()}%"
    rows = (
        await db.execute(
            select(SearchHistory.query, func.count().label("n"))
            .where(SearchHistory.user_id == user.id, SearchHistory.query.ilike(like))
            .group_by(SearchHistory.query)
            .order_by(func.count().desc(), func.max(SearchHistory.created_at).desc())
            .limit(8)
        )
    ).all()
    return [row[0] for row in rows]
