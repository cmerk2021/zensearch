"""Administration routes. All require the admin role."""

from __future__ import annotations

from fastapi import APIRouter, File, Query, Request, UploadFile

from zen.api.deps import DB, Admin, client_ip
from zen.core.cache import get_cache
from zen.core.exceptions import NotFoundError, ValidationFailed
from zen.core.pagination import Page, PageParams
from zen.core.security import encrypt_secret
from zen.db.models import DomainRule, ProviderConfig, RuleScope
from zen.schemas.api import (
    AdminUserCreate,
    AdminUserUpdate,
    AuditEntryOut,
    DomainRuleCreate,
    DomainRuleOut,
    InstanceSettingsUpdate,
    PluginInstallRequest,
    PluginOut,
    ProfileCreate,
    ProfileOut,
    ProfileUpdate,
    ProviderConfigOut,
    ProviderConfigUpdate,
    RepositoryCreate,
    RepositoryOut,
)
from zen.schemas.common import Message, UserOut
from zen.search import health as provider_health
from zen.search.providers import BUILTIN_PROVIDERS, all_providers
from zen.services import audit
from zen.services.profiles import ProfileService
from zen.services.settings import SettingsService
from zen.services.users import UserService

router = APIRouter(prefix="/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Instance settings
# ---------------------------------------------------------------------------


@router.get("/settings")
async def get_instance_settings(admin: Admin, db: DB) -> dict:
    return await SettingsService(db).get_all(redact_secrets=True)


@router.put("/settings", response_model=Message)
async def update_instance_settings(
    payload: InstanceSettingsUpdate, request: Request, admin: Admin, db: DB
) -> Message:
    await SettingsService(db).set_many(payload.values, actor_id=admin.id)
    await audit.record(
        db,
        action="settings.updated",
        actor_id=admin.id,
        data={"keys": sorted(payload.values.keys())},
        ip_address=client_ip(request),
    )
    return Message(message=f"Updated {len(payload.values)} setting(s).")


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------


@router.get("/providers", response_model=list[ProviderConfigOut])
async def list_providers(admin: Admin, db: DB) -> list[ProviderConfigOut]:
    from sqlalchemy import select

    configs = {
        row.slug: row for row in (await db.execute(select(ProviderConfig))).scalars().all()
    }
    out = []
    for slug, cls in sorted(all_providers().items()):
        config = configs.get(slug)
        out.append(
            ProviderConfigOut(
                slug=slug,
                name=cls.name,
                description=cls.description,
                category=cls.category.value,
                requires_api_key=cls.requires_api_key,
                enabled=config.enabled if config else True,
                weight=config.weight if config else cls.default_weight,
                timeout_seconds=config.timeout_seconds if config else None,
                has_api_key=bool(config and config.api_key_encrypted),
                supports_paging=cls.supports_paging,
                builtin=slug in BUILTIN_PROVIDERS,
            )
        )
    return out


@router.patch("/providers/{slug}", response_model=Message)
async def update_provider(
    slug: str, payload: ProviderConfigUpdate, request: Request, admin: Admin, db: DB
) -> Message:
    if slug not in all_providers():
        raise NotFoundError(f"Unknown provider: {slug}")
    config = await db.get(ProviderConfig, slug)
    if config is None:
        config = ProviderConfig(slug=slug)
        db.add(config)
    if payload.enabled is not None:
        config.enabled = payload.enabled
    if payload.weight is not None:
        config.weight = payload.weight
    if payload.timeout_seconds is not None:
        config.timeout_seconds = payload.timeout_seconds
    if payload.api_key is not None:
        from zen.core.config import get_settings

        config.api_key_encrypted = (
            encrypt_secret(payload.api_key, get_settings().secret_key)
            if payload.api_key
            else ""
        )
    if payload.config is not None:
        config.config = payload.config
    await db.commit()
    await audit.record(
        db,
        action="provider.updated",
        actor_id=admin.id,
        target_type="provider",
        target_id=slug,
        ip_address=client_ip(request),
    )
    return Message(message=f"Provider '{slug}' updated.")


@router.get("/providers/health")
async def providers_health(admin: Admin) -> dict:
    return await provider_health.all_health(sorted(all_providers().keys()))


@router.post("/providers/{slug}/reset-health", response_model=Message)
async def reset_provider_health(slug: str, admin: Admin) -> Message:
    if slug not in all_providers():
        raise NotFoundError(f"Unknown provider: {slug}")
    await provider_health.reset_health(slug)
    return Message(message=f"Health state for '{slug}' reset.")


@router.post("/providers/{slug}/test")
async def test_provider(slug: str, admin: Admin, db: DB, q: str = Query(default="zen")) -> dict:
    """Run a live probe against one provider and report the outcome."""
    cls = all_providers().get(slug)
    if cls is None:
        raise NotFoundError(f"Unknown provider: {slug}")
    import time

    from zen.core.config import get_settings
    from zen.core.security import decrypt_secret
    from zen.search.http import build_search_client
    from zen.search.models import SearchQuery

    config = await db.get(ProviderConfig, slug)
    api_key = ""
    if config and config.api_key_encrypted:
        api_key = decrypt_secret(config.api_key_encrypted, get_settings().secret_key)
    provider = cls(config=config.config if config else {}, api_key=api_key)
    started = time.perf_counter()
    try:
        async with build_search_client(timeout=cls.default_timeout) as client:
            results = await provider.search(SearchQuery(text=q), client)
        return {
            "ok": True,
            "result_count": len(results),
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "sample": [{"title": r.title, "url": r.url} for r in results[:3]],
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}"[:300],
            "duration_ms": int((time.perf_counter() - started) * 1000),
        }


# ---------------------------------------------------------------------------
# Domain rules (ranking control)
# ---------------------------------------------------------------------------


@router.get("/domain-rules", response_model=list[DomainRuleOut])
async def list_domain_rules(admin: Admin, db: DB) -> list[DomainRuleOut]:
    from sqlalchemy import select

    rows = (
        await db.execute(select(DomainRule).order_by(DomainRule.domain))
    ).scalars().all()
    return [DomainRuleOut.model_validate(r) for r in rows]


@router.post("/domain-rules", response_model=DomainRuleOut, status_code=201)
async def create_domain_rule(
    payload: DomainRuleCreate, request: Request, admin: Admin, db: DB
) -> DomainRuleOut:
    domain = payload.domain.strip().lower().removeprefix("www.")
    if not domain or " " in domain or "." not in domain:
        raise ValidationFailed("A valid domain is required (e.g. example.com).")
    if payload.scope == RuleScope.PROFILE.value and not payload.profile_id:
        raise ValidationFailed("profile_id is required for profile-scoped rules.")
    rule = DomainRule(
        domain=domain,
        action=payload.action,
        weight=payload.weight,
        scope=payload.scope,
        profile_id=payload.profile_id if payload.scope == RuleScope.PROFILE.value else None,
        created_by=admin.id,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    await audit.record(
        db,
        action="domain_rule.created",
        actor_id=admin.id,
        target_type="domain_rule",
        target_id=rule.id,
        data={"domain": domain, "action": payload.action},
        ip_address=client_ip(request),
    )
    return DomainRuleOut.model_validate(rule)


@router.delete("/domain-rules/{rule_id}", response_model=Message)
async def delete_domain_rule(rule_id: str, request: Request, admin: Admin, db: DB) -> Message:
    rule = await db.get(DomainRule, rule_id)
    if rule is None:
        raise NotFoundError("Domain rule not found.")
    await db.delete(rule)
    await db.commit()
    await audit.record(
        db,
        action="domain_rule.deleted",
        actor_id=admin.id,
        target_type="domain_rule",
        target_id=rule_id,
        ip_address=client_ip(request),
    )
    return Message(message="Domain rule deleted.")


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


@router.get("/users", response_model=Page[UserOut])
async def list_users(
    admin: Admin,
    db: DB,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=25, ge=1, le=100),
    q: str | None = None,
) -> Page[UserOut]:
    result = await UserService(db).list_users(PageParams(page=page, size=size), query=q)
    return Page(
        items=[UserOut.model_validate(u) for u in result.items],
        total=result.total,
        page=result.page,
        size=result.size,
    )


@router.post("/users", response_model=UserOut, status_code=201)
async def create_user(
    payload: AdminUserCreate, request: Request, admin: Admin, db: DB
) -> UserOut:
    from zen.services.auth import AuthService

    user = await AuthService(db).create_user(
        username=payload.username,
        password=payload.password,
        email=payload.email,
        role=payload.role,
        ai_enabled=payload.ai_enabled,
    )
    await audit.record(
        db,
        action="user.created",
        actor_id=admin.id,
        target_type="user",
        target_id=user.id,
        data={"role": payload.role},
        ip_address=client_ip(request),
    )
    return UserOut.model_validate(user)


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: str, payload: AdminUserUpdate, request: Request, admin: Admin, db: DB
) -> UserOut:
    service = UserService(db)
    user = await service.get(user_id)
    if payload.role is not None:
        user = await service.set_role(user_id, payload.role, acting_admin=admin)
    if payload.is_active is not None:
        user = await service.set_active(user_id, payload.is_active, acting_admin=admin)
    if payload.ai_enabled is not None:
        user = await service.set_ai_enabled(user_id, payload.ai_enabled)
    if payload.password is not None:
        user = await service.admin_set_password(user_id, payload.password)
    await audit.record(
        db,
        action="user.updated",
        actor_id=admin.id,
        target_type="user",
        target_id=user_id,
        data=payload.model_dump(exclude_unset=True, exclude={"password"}),
        ip_address=client_ip(request),
    )
    return UserOut.model_validate(user)


@router.delete("/users/{user_id}", response_model=Message)
async def delete_user(user_id: str, request: Request, admin: Admin, db: DB) -> Message:
    await UserService(db).delete(user_id, acting_admin=admin)
    await audit.record(
        db,
        action="user.deleted",
        actor_id=admin.id,
        target_type="user",
        target_id=user_id,
        ip_address=client_ip(request),
    )
    return Message(message="User deleted.")


# ---------------------------------------------------------------------------
# Search profiles
# ---------------------------------------------------------------------------


@router.get("/profiles", response_model=list[ProfileOut])
async def admin_list_profiles(admin: Admin, db: DB) -> list[ProfileOut]:
    profiles = await ProfileService(db).list_all()
    return [ProfileOut.model_validate(p) for p in profiles]


@router.post("/profiles", response_model=ProfileOut, status_code=201)
async def create_profile(
    payload: ProfileCreate, request: Request, admin: Admin, db: DB
) -> ProfileOut:
    profile = await ProfileService(db).create(payload.model_dump())
    await audit.record(
        db,
        action="profile.created",
        actor_id=admin.id,
        target_type="profile",
        target_id=profile.id,
        ip_address=client_ip(request),
    )
    return ProfileOut.model_validate(profile)


@router.patch("/profiles/{profile_id}", response_model=ProfileOut)
async def update_profile(
    profile_id: str, payload: ProfileUpdate, request: Request, admin: Admin, db: DB
) -> ProfileOut:
    profile = await ProfileService(db).update(profile_id, payload.model_dump(exclude_unset=True))
    await audit.record(
        db,
        action="profile.updated",
        actor_id=admin.id,
        target_type="profile",
        target_id=profile_id,
        ip_address=client_ip(request),
    )
    return ProfileOut.model_validate(profile)


@router.delete("/profiles/{profile_id}", response_model=Message)
async def delete_profile(profile_id: str, request: Request, admin: Admin, db: DB) -> Message:
    await ProfileService(db).delete(profile_id)
    await audit.record(
        db,
        action="profile.deleted",
        actor_id=admin.id,
        target_type="profile",
        target_id=profile_id,
        ip_address=client_ip(request),
    )
    return Message(message="Profile deleted.")


# ---------------------------------------------------------------------------
# Plugins & repositories
# ---------------------------------------------------------------------------


@router.get("/plugins", response_model=list[PluginOut])
async def list_plugins(admin: Admin, db: DB) -> list[PluginOut]:
    from zen.plugins.manager import PluginManager

    plugins = await PluginManager(db).list_installed()
    return [PluginOut.model_validate(p) for p in plugins]


@router.post("/plugins/install", response_model=PluginOut)
async def install_plugin(
    payload: PluginInstallRequest, request: Request, admin: Admin, db: DB
) -> PluginOut:
    from zen.plugins.manager import PluginManager

    if not await SettingsService(db).get("plugins.allow_install", True):
        raise ValidationFailed("Plugin installation is disabled on this instance.")
    plugin = await PluginManager(db).install_from_repository(
        payload.plugin_id, payload.version
    )
    await audit.record(
        db,
        action="plugin.installed",
        actor_id=admin.id,
        target_type="plugin",
        target_id=plugin.slug,
        data={"version": plugin.version},
        ip_address=client_ip(request),
    )
    return PluginOut.model_validate(plugin)


@router.post("/plugins/upload", response_model=PluginOut)
async def upload_plugin(
    request: Request, admin: Admin, db: DB, file: UploadFile = File(...)
) -> PluginOut:
    from zen.plugins.manager import PluginManager
    from zen.plugins.repository import MAX_PLUGIN_SIZE

    if not await SettingsService(db).get("plugins.allow_install", True):
        raise ValidationFailed("Plugin installation is disabled on this instance.")
    blob = await file.read()
    if len(blob) > MAX_PLUGIN_SIZE:
        raise ValidationFailed("Plugin artifact exceeds the 50 MB limit.")
    plugin = await PluginManager(db).install_from_bytes(blob, source="upload")
    await audit.record(
        db,
        action="plugin.installed",
        actor_id=admin.id,
        target_type="plugin",
        target_id=plugin.slug,
        data={"version": plugin.version, "source": "upload"},
        ip_address=client_ip(request),
    )
    return PluginOut.model_validate(plugin)


@router.post("/plugins/{slug}/enable", response_model=PluginOut)
async def enable_plugin(slug: str, admin: Admin, db: DB) -> PluginOut:
    from zen.plugins.manager import PluginManager

    return PluginOut.model_validate(await PluginManager(db).set_enabled(slug, True))


@router.post("/plugins/{slug}/disable", response_model=PluginOut)
async def disable_plugin(slug: str, admin: Admin, db: DB) -> PluginOut:
    from zen.plugins.manager import PluginManager

    return PluginOut.model_validate(await PluginManager(db).set_enabled(slug, False))


@router.post("/plugins/{slug}/rollback", response_model=PluginOut)
async def rollback_plugin(slug: str, request: Request, admin: Admin, db: DB) -> PluginOut:
    from zen.plugins.manager import PluginManager

    plugin = await PluginManager(db).rollback(slug)
    await audit.record(
        db,
        action="plugin.rolled_back",
        actor_id=admin.id,
        target_type="plugin",
        target_id=slug,
        data={"version": plugin.version},
        ip_address=client_ip(request),
    )
    return PluginOut.model_validate(plugin)


@router.delete("/plugins/{slug}", response_model=Message)
async def remove_plugin(slug: str, request: Request, admin: Admin, db: DB) -> Message:
    from zen.plugins.manager import PluginManager

    await PluginManager(db).remove(slug)
    await audit.record(
        db,
        action="plugin.removed",
        actor_id=admin.id,
        target_type="plugin",
        target_id=slug,
        ip_address=client_ip(request),
    )
    return Message(message=f"Plugin '{slug}' removed.")


@router.get("/plugins/updates")
async def check_plugin_updates(admin: Admin, db: DB) -> list[dict]:
    from zen.plugins.manager import PluginManager

    return await PluginManager(db).check_updates()


@router.get("/repositories", response_model=list[RepositoryOut])
async def list_repositories(admin: Admin, db: DB) -> list[RepositoryOut]:
    from zen.plugins.repository import RepositoryService

    repos = await RepositoryService(db).list_repositories()
    return [RepositoryOut.model_validate(r) for r in repos]


@router.post("/repositories", response_model=RepositoryOut, status_code=201)
async def add_repository(
    payload: RepositoryCreate, request: Request, admin: Admin, db: DB
) -> RepositoryOut:
    from zen.plugins.repository import RepositoryService

    repo = await RepositoryService(db).add(
        name=payload.name, url=payload.url, kind=payload.kind
    )
    await audit.record(
        db,
        action="repository.added",
        actor_id=admin.id,
        target_type="repository",
        target_id=repo.id,
        data={"url": payload.url},
        ip_address=client_ip(request),
    )
    return RepositoryOut.model_validate(repo)


@router.post("/repositories/{repo_id}/sync", response_model=RepositoryOut)
async def sync_repository(repo_id: str, admin: Admin, db: DB) -> RepositoryOut:
    from zen.plugins.repository import RepositoryService

    repo = await RepositoryService(db).sync(repo_id)
    return RepositoryOut.model_validate(repo)


@router.get("/repositories/{repo_id}/catalog")
async def repository_catalog(repo_id: str, admin: Admin, db: DB) -> dict:
    from zen.plugins.repository import RepositoryService

    repos = await RepositoryService(db).list_repositories()
    repo = next((r for r in repos if r.id == repo_id), None)
    if repo is None:
        raise NotFoundError("Repository not found.")
    return repo.catalog or {"plugins": []}


@router.delete("/repositories/{repo_id}", response_model=Message)
async def remove_repository(repo_id: str, request: Request, admin: Admin, db: DB) -> Message:
    from zen.plugins.repository import RepositoryService

    await RepositoryService(db).remove(repo_id)
    await audit.record(
        db,
        action="repository.removed",
        actor_id=admin.id,
        target_type="repository",
        target_id=repo_id,
        ip_address=client_ip(request),
    )
    return Message(message="Repository removed.")


# ---------------------------------------------------------------------------
# AI administration
# ---------------------------------------------------------------------------


@router.get("/ai/status")
async def ai_admin_status(admin: Admin, db: DB) -> dict:
    from zen.ai.service import AIService

    return await AIService(db).status()


@router.post("/ai/test")
async def ai_test(payload: dict, admin: Admin, db: DB) -> dict:
    from zen.ai.base import ChatMessage
    from zen.ai.service import AIService

    prompt = str(payload.get("prompt") or "Reply with the single word: pong")
    service = AIService(db)
    text = await service._chat("admin_test", [ChatMessage(role="user", content=prompt)])
    return {"ok": True, "response": text[:2000]}


# ---------------------------------------------------------------------------
# Audit log, cache, diagnostics
# ---------------------------------------------------------------------------


@router.get("/audit", response_model=Page[AuditEntryOut])
async def list_audit(
    admin: Admin,
    db: DB,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=100),
    action: str | None = None,
) -> Page[AuditEntryOut]:
    result = await audit.list_entries(db, PageParams(page=page, size=size), action=action)
    return Page(
        items=[AuditEntryOut.model_validate(e) for e in result.items],
        total=result.total,
        page=result.page,
        size=result.size,
    )


@router.post("/cache/clear", response_model=Message)
async def clear_search_cache(admin: Admin) -> Message:
    """Clear cached search results (best effort; provider health is preserved)."""
    cache = get_cache()
    # Without SCAN-style iteration on the memory backend we recreate it; on
    # Redis we leave non-search keys intact by deleting the generation marker
    # approach is not applicable — search keys are content-hashed with TTLs,
    # so the pragmatic approach is bumping the settings generation and letting
    # TTLs expire. For memory cache, recreate the store.
    from zen.core.cache import MemoryCache, set_cache

    if isinstance(cache, MemoryCache):
        await cache.close()
        set_cache(MemoryCache())
        return Message(message="In-memory cache cleared.")
    return Message(
        message="Search caches expire automatically (TTL 300s). Redis keys left intact."
    )


@router.get("/diagnostics")
async def diagnostics(admin: Admin, db: DB) -> dict:
    import platform
    import sys

    from sqlalchemy import func, select, text

    from zen.core.config import get_settings
    from zen.db.models import Bookmark, Note, SearchHistory, User, Workspace

    settings = get_settings()
    db_ok = True
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    cache_ok = await get_cache().ping()

    async def count(model) -> int:
        return (await db.execute(select(func.count()).select_from(model))).scalar_one()

    return {
        "version": sys.version.split()[0],
        "platform": platform.platform(),
        "database": {
            "ok": db_ok,
            "backend": "sqlite" if settings.is_sqlite else "postgresql",
        },
        "cache": {"ok": cache_ok, "backend": "redis" if settings.redis_url else "memory"},
        "counts": {
            "users": await count(User),
            "workspaces": await count(Workspace),
            "bookmarks": await count(Bookmark),
            "notes": await count(Note),
            "searches": await count(SearchHistory),
        },
    }
