"""User-facing routes: profile, preferences, profiles list, AI, meta, favicon."""

from __future__ import annotations

import base64
import re

import httpx
from fastapi import APIRouter, Depends, Query, Response

from zen.api.deps import DB, CurrentUser, OptionalUser, Writer, rate_limited
from zen.core.cache import get_cache
from zen.core.exceptions import ValidationFailed
from zen.schemas.api import (
    AITextOut,
    ExpandQueryRequest,
    KnowledgeMapOut,
    ProfileOut,
    SummarizeRequest,
)
from zen.schemas.common import (
    PreferencesOut,
    PreferencesUpdate,
    ProfileUpdateMe,
    UserOut,
)
from zen.search.models import ResultType, SearchResult
from zen.services.bootstrap import admin_exists
from zen.services.export import ExportService
from zen.services.profiles import ProfileService
from zen.services.settings import SettingsService
from zen.services.users import UserService
from zen.version import __version__

router = APIRouter(tags=["user"])


# ---------------------------------------------------------------------------
# Me
# ---------------------------------------------------------------------------


@router.get("/me", response_model=UserOut)
async def get_me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.patch("/me", response_model=UserOut)
async def update_me(payload: ProfileUpdateMe, user: CurrentUser, db: DB) -> UserOut:
    updated = await UserService(db).update_profile(user, payload.model_dump(exclude_unset=True))
    return UserOut.model_validate(updated)


@router.get("/me/preferences", response_model=PreferencesOut)
async def get_preferences(user: CurrentUser, db: DB) -> PreferencesOut:
    prefs = await UserService(db).get_preferences(user)
    return PreferencesOut.model_validate(prefs)


@router.patch("/me/preferences", response_model=PreferencesOut)
async def update_preferences(
    payload: PreferencesUpdate, user: CurrentUser, db: DB
) -> PreferencesOut:
    prefs = await UserService(db).update_preferences(
        user, payload.model_dump(exclude_unset=True)
    )
    return PreferencesOut.model_validate(prefs)


@router.get("/me/export.json")
async def export_my_data(user: CurrentUser, db: DB) -> dict:
    return await ExportService(db).export_all_json(user)


# ---------------------------------------------------------------------------
# Profiles (read-only for users; admin CRUD lives under /admin)
# ---------------------------------------------------------------------------


@router.get("/profiles", response_model=list[ProfileOut])
async def list_profiles(db: DB, user: OptionalUser) -> list[ProfileOut]:
    profiles = await ProfileService(db).list_active()
    return [ProfileOut.model_validate(p) for p in profiles]


# ---------------------------------------------------------------------------
# AI (user-facing capabilities)
# ---------------------------------------------------------------------------

ai_router = APIRouter(prefix="/ai", tags=["ai"], dependencies=[Depends(rate_limited("ai"))])


@ai_router.get("/status")
async def ai_status(db: DB, user: CurrentUser) -> dict:
    from zen.ai.service import AIService

    status = await AIService(db).status()
    # Users see availability, not configuration details.
    return {"enabled": status["enabled"], "reachable": status.get("reachable", False)}


@ai_router.post("/expand", response_model=list[str])
async def expand_query(payload: ExpandQueryRequest, user: Writer, db: DB) -> list[str]:
    from zen.ai.service import AIService

    return await AIService(db).expand_query(payload.q)


@ai_router.post("/summarize", response_model=AITextOut)
async def summarize(payload: SummarizeRequest, user: Writer, db: DB) -> AITextOut:
    from zen.ai.service import AIService

    results = [
        SearchResult(
            title=r.title,
            url=r.url,
            snippet=r.snippet,
            domain=r.domain,
            favicon_url=r.favicon_url,
            providers=r.providers,
            positions=r.positions,
            score=r.score,
            result_type=ResultType(r.result_type),
            published_at=r.published_at,
            thumbnail=r.thumbnail,
            pinned=r.pinned,
        )
        for r in payload.results
    ]
    text = await AIService(db).summarize_results(payload.q, results)
    return AITextOut(text=text)


@ai_router.post("/workspaces/{workspace_id}/digest", response_model=AITextOut)
async def workspace_digest(workspace_id: str, user: Writer, db: DB) -> AITextOut:
    from zen.ai.service import AIService

    return AITextOut(text=await AIService(db).research_digest(workspace_id, user))


@ai_router.post("/workspaces/{workspace_id}/report", response_model=AITextOut)
async def workspace_report(workspace_id: str, user: Writer, db: DB) -> AITextOut:
    from zen.ai.service import AIService

    return AITextOut(text=await AIService(db).workspace_report(workspace_id, user))


@ai_router.post("/workspaces/{workspace_id}/map", response_model=KnowledgeMapOut)
async def workspace_knowledge_map(workspace_id: str, user: Writer, db: DB) -> KnowledgeMapOut:
    from zen.ai.service import AIService

    data = await AIService(db).knowledge_map(workspace_id, user)
    return KnowledgeMapOut(nodes=data["nodes"], edges=data["edges"])


# ---------------------------------------------------------------------------
# Meta / instance info
# ---------------------------------------------------------------------------

meta_router = APIRouter(tags=["meta"])


@meta_router.get("/meta/instance")
async def instance_info(db: DB) -> dict:
    settings_service = SettingsService(db)
    return {
        "name": await settings_service.get("instance.name", "Zen"),
        "tagline": await settings_service.get("instance.tagline", "Search less. Find more."),
        "logo_url": await settings_service.get("instance.logo_url", ""),
        "version": __version__,
        "default_theme": await settings_service.get("ui.default_theme", "system"),
        "ai_enabled": bool(await settings_service.get("ai.enabled", False)),
        "bootstrap_required": not await admin_exists(db),
    }


@meta_router.post("/meta/setup")
async def first_run_setup(payload: dict, db: DB) -> dict:
    """Create the first admin account. Only available while no admin exists."""
    from zen.core.exceptions import PermissionDeniedError
    from zen.db.models import Role
    from zen.services.auth import AuthService

    if await admin_exists(db):
        raise PermissionDeniedError("Setup has already been completed.")
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    if not username or not password:
        raise ValidationFailed("Username and password are required.")
    user = await AuthService(db).create_user(
        username=username, password=password, role=Role.ADMIN.value
    )
    return {"created": True, "username": user.username}


# ---------------------------------------------------------------------------
# Favicon proxy (privacy: the browser never contacts third parties)
# ---------------------------------------------------------------------------

_DOMAIN_RE = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)(\.(?!-)[a-z0-9-]{1,63}(?<!-))+$")

_FALLBACK_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32">'
    '<rect width="32" height="32" rx="6" fill="#64748b"/>'
    '<text x="16" y="21" font-family="system-ui" font-size="14" fill="#fff" '
    'text-anchor="middle">{letter}</text></svg>'
)

FAVICON_TTL = 24 * 3600
MAX_ICON_BYTES = 128 * 1024


def _is_public_ip(ip: str) -> bool:
    import ipaddress

    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return not (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


@router.get("/favicon")
async def favicon_proxy(domain: str = Query(max_length=255)) -> Response:
    domain = domain.strip().lower()
    fallback = Response(
        content=_FALLBACK_SVG.format(letter=(domain[:1] or "?").upper()),
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=86400"},
    )
    if not _DOMAIN_RE.match(domain):
        return fallback

    cache_key = f"favicon:{domain}"
    cached = await get_cache().get(cache_key)
    if cached:
        if cached == "MISS":
            return fallback
        try:
            content_type, b64 = cached.split("|", 1)
            return Response(
                content=base64.b64decode(b64),
                media_type=content_type,
                headers={"Cache-Control": "public, max-age=86400"},
            )
        except ValueError:
            pass

    # SSRF guard: resolve and require public addresses before fetching.
    import asyncio
    import socket

    try:
        loop = asyncio.get_event_loop()
        infos = await asyncio.wait_for(
            loop.getaddrinfo(domain, 443, type=socket.SOCK_STREAM), timeout=4.0
        )
        ips = {info[4][0] for info in infos}
        if not ips or not all(_is_public_ip(ip) for ip in ips):
            await get_cache().set(cache_key, "MISS", ttl=FAVICON_TTL)
            return fallback
    except (TimeoutError, OSError):
        await get_cache().set(cache_key, "MISS", ttl=FAVICON_TTL)
        return fallback

    try:
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
            response = await client.get(f"https://{domain}/favicon.ico")
            content_type = response.headers.get("content-type", "").split(";")[0].strip()
            if (
                response.status_code == 200
                and len(response.content) <= MAX_ICON_BYTES
                and content_type.startswith("image/")
            ):
                payload = f"{content_type}|{base64.b64encode(response.content).decode()}"
                await get_cache().set(cache_key, payload, ttl=FAVICON_TTL)
                return Response(
                    content=response.content,
                    media_type=content_type,
                    headers={"Cache-Control": "public, max-age=86400"},
                )
    except httpx.HTTPError:
        pass
    await get_cache().set(cache_key, "MISS", ttl=FAVICON_TTL)
    return fallback
