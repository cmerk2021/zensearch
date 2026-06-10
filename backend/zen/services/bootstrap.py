"""First-run bootstrap: admin account and curated default profiles."""

from __future__ import annotations

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from zen.core.config import get_settings
from zen.db.models import Role, SearchProfile, User
from zen.services.auth import AuthService

log = structlog.get_logger(__name__)

DEFAULT_PROFILES: list[dict] = [
    {
        "slug": "balanced",
        "name": "Balanced",
        "description": "General-purpose search across all enabled providers.",
        "icon": "scale",
        "providers": [],
        "is_default": True,
        "position": 0,
    },
    {
        "slug": "engineering",
        "name": "Engineering",
        "description": "Code, docs and Q&A first. GitHub and Stack Overflow boosted.",
        "icon": "wrench",
        "providers": [
            "google", "duckduckgo", "brave", "github", "stackoverflow", "wikipedia",
        ],
        "ranking": {
            "domain_weights": {
                "github.com": 1.5,
                "stackoverflow.com": 1.5,
                "developer.mozilla.org": 1.4,
                "docs.python.org": 1.4,
                "kubernetes.io": 1.3,
                "wiki.archlinux.org": 1.3,
                "medium.com": 0.7,
            }
        },
        "position": 1,
    },
    {
        "slug": "research",
        "name": "Research",
        "description": "Deep reading: reference sources boosted, social noise removed.",
        "icon": "book-open",
        "providers": ["google", "bing", "brave", "wikipedia", "duckduckgo", "mojeek"],
        "ranking": {
            "domain_weights": {
                "wikipedia.org": 1.4,
                "arxiv.org": 1.5,
                "scholar.google.com": 1.4,
                "jstor.org": 1.3,
                "nature.com": 1.3,
                "pinterest.com": 0.3,
            }
        },
        "filters": {"blocked_domains": ["facebook.com", "instagram.com", "tiktok.com"]},
        "ui": {"default_mode": "research"},
        "position": 2,
    },
    {
        "slug": "homelab",
        "name": "Homelab",
        "description": "Self-hosting, networking and home server sources prioritized.",
        "icon": "server",
        "providers": ["google", "duckduckgo", "github", "reddit", "stackoverflow"],
        "ranking": {
            "domain_weights": {
                "reddit.com": 1.3,
                "github.com": 1.4,
                "selfhosted.show": 1.3,
                "docs.docker.com": 1.4,
                "wiki.servarr.com": 1.3,
                "forums.unraid.net": 1.2,
                "pimylifeup.com": 1.2,
            }
        },
        "position": 3,
    },
    {
        "slug": "academic",
        "name": "Academic",
        "description": "Scholarly and reference material; entertainment removed.",
        "icon": "graduation-cap",
        "providers": ["google", "bing", "wikipedia", "mojeek"],
        "ranking": {
            "domain_weights": {
                "arxiv.org": 1.6,
                "wikipedia.org": 1.3,
                "pubmed.ncbi.nlm.nih.gov": 1.5,
                "ieee.org": 1.4,
                "acm.org": 1.4,
            }
        },
        "ui": {"default_mode": "focus"},
        "position": 4,
    },
    {
        "slug": "privacy",
        "name": "Privacy",
        "description": "Privacy-respecting upstreams only; no Google/Bing.",
        "icon": "shield",
        "providers": ["duckduckgo", "brave", "startpage", "mojeek", "wikipedia"],
        "ui": {"default_mode": "privacy"},
        "position": 5,
    },
]


async def bootstrap_instance(db: AsyncSession) -> None:
    """Idempotent startup seeding: profiles and env-driven admin account."""
    await _seed_profiles(db)
    await _bootstrap_admin(db)


async def _seed_profiles(db: AsyncSession) -> None:
    count = (await db.execute(select(func.count()).select_from(SearchProfile))).scalar_one()
    if count > 0:
        return
    for spec in DEFAULT_PROFILES:
        db.add(
            SearchProfile(
                slug=spec["slug"],
                name=spec["name"],
                description=spec.get("description", ""),
                icon=spec.get("icon", "search"),
                providers=spec.get("providers", []),
                ranking=spec.get("ranking", {}),
                filters=spec.get("filters", {}),
                ai=spec.get("ai", {}),
                workspace=spec.get("workspace", {}),
                ui=spec.get("ui", {}),
                is_default=spec.get("is_default", False),
                position=spec.get("position", 0),
            )
        )
    await db.commit()
    log.info("bootstrap.profiles_seeded", count=len(DEFAULT_PROFILES))


async def _bootstrap_admin(db: AsyncSession) -> None:
    settings = get_settings()
    admin_count = (
        await db.execute(
            select(func.count()).select_from(User).where(User.role == Role.ADMIN.value)
        )
    ).scalar_one()
    if admin_count > 0:
        return
    username = settings.bootstrap_admin_username
    password = settings.bootstrap_admin_password
    if not username or not password:
        log.info(
            "bootstrap.no_admin",
            hint="No admin exists. Create one via the /setup page, "
            "'zen users create-admin', or ZEN_BOOTSTRAP_ADMIN_USERNAME/PASSWORD.",
        )
        return
    auth = AuthService(db)
    await auth.create_user(username=username, password=password, role=Role.ADMIN.value)
    log.info("bootstrap.admin_created", username=username)


async def admin_exists(db: AsyncSession) -> bool:
    count = (
        await db.execute(
            select(func.count())
            .select_from(User)
            .where(User.role == Role.ADMIN.value, User.is_active.is_(True))
        )
    ).scalar_one()
    return count > 0
