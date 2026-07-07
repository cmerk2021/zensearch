"""FastAPI dependencies: database, identity, roles, CSRF, rate limits."""

from __future__ import annotations

import ipaddress
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from zen.core.config import get_settings
from zen.core.exceptions import (
    AuthenticationError,
    CSRFError,
    PermissionDeniedError,
)
from zen.core.rate_limit import DEFAULT_LIMITS, RateLimit, check_rate_limit
from zen.core.security import constant_time_compare
from zen.db.base import get_db_session
from zen.db.models import User
from zen.services.auth import SESSION_COOKIE, AuthService
from zen.services.settings import SettingsService

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

DB = Annotated[AsyncSession, Depends(get_db_session)]


def client_ip(request: Request) -> str:
    """Resolve the real client IP, honoring X-Forwarded-For only from trusted proxies."""
    peer = request.client.host if request.client else ""
    trusted = get_settings().trusted_proxy_list
    if not trusted or not peer:
        return peer or "unknown"
    try:
        peer_addr = ipaddress.ip_address(peer)
    except ValueError:
        return peer
    is_trusted = False
    for entry in trusted:
        try:
            if "/" in entry:
                if peer_addr in ipaddress.ip_network(entry, strict=False):
                    is_trusted = True
                    break
            elif peer_addr == ipaddress.ip_address(entry):
                is_trusted = True
                break
        except ValueError:
            continue
    if not is_trusted:
        return peer
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        try:
            ipaddress.ip_address(first)
            return first
        except ValueError:
            return peer
    return peer


async def get_current_user_optional(request: Request, db: DB) -> User | None:
    token = request.cookies.get(SESSION_COOKIE, "")
    if not token:
        return None
    resolved = await AuthService(db).resolve_session(token)
    if resolved is None:
        return None
    user, session = resolved
    if request.method not in SAFE_METHODS:
        header = request.headers.get("x-csrf-token", "")
        if not header or not constant_time_compare(header, session.csrf_token):
            raise CSRFError("Missing or invalid CSRF token.")
    request.state.session = session
    request.state.user = user
    return user


async def get_current_user(
    user: Annotated[User | None, Depends(get_current_user_optional)],
) -> User:
    if user is None:
        raise AuthenticationError("Authentication required.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_current_user_optional)]


async def require_writer(user: CurrentUser) -> User:
    if not user.can_write:
        raise PermissionDeniedError("Read-only accounts cannot perform this action.")
    return user


async def require_admin(user: CurrentUser) -> User:
    if not user.is_admin:
        raise PermissionDeniedError("Administrator access required.")
    return user


async def require_ai_user(user: CurrentUser) -> User:
    if not user.can_write:
        raise PermissionDeniedError("Read-only accounts cannot use AI features.")
    if not user.ai_enabled:
        raise PermissionDeniedError("AI features are not enabled for your account.")
    return user


Writer = Annotated[User, Depends(require_writer)]
Admin = Annotated[User, Depends(require_admin)]
AIUser = Annotated[User, Depends(require_ai_user)]


def rate_limited(bucket: str):
    """Dependency factory enforcing the configured limit for a bucket."""

    async def dependency(request: Request, db: DB) -> None:
        settings = get_settings()
        if not settings.rate_limit_enabled:
            return
        specs = await SettingsService(db).get("security.rate_limits", {}) or {}
        spec = specs.get(bucket)
        limit = RateLimit.parse(str(spec)) if spec else DEFAULT_LIMITS.get(
            bucket, DEFAULT_LIMITS["api"]
        )
        user = getattr(request.state, "user", None)
        identity = user.id if user is not None else client_ip(request)
        await check_rate_limit(bucket, identity, limit)

    return dependency
