"""Authentication routes: local login, sessions, registration, OIDC."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
import urllib.parse

import httpx
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse

from zen.api.deps import DB, CurrentUser, client_ip, rate_limited
from zen.core.config import get_settings
from zen.core.exceptions import AuthenticationError, NotFoundError, ValidationFailed
from zen.schemas.common import (
    AuthMethodsOut,
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    Message,
    RegisterRequest,
    SessionOut,
    UserOut,
)
from zen.services import audit
from zen.services.auth import CSRF_COOKIE, SESSION_COOKIE, AuthService
from zen.services.settings import SettingsService

router = APIRouter(prefix="/auth", tags=["auth"])

OIDC_STATE_COOKIE = "zen_oidc_state"


def _set_session_cookies(response: Response, token: str, csrf: str, max_age: int) -> None:
    settings = get_settings()
    secure = settings.cookie_secure_effective
    common = {
        "max_age": max_age,
        "secure": secure,
        "samesite": "lax",
        "path": "/",
    }
    if settings.cookie_domain:
        common["domain"] = settings.cookie_domain
    response.set_cookie(SESSION_COOKIE, token, httponly=True, **common)
    # CSRF cookie is intentionally readable by the frontend (double-submit).
    response.set_cookie(CSRF_COOKIE, csrf, httponly=False, **common)


def _clear_session_cookies(response: Response) -> None:
    settings = get_settings()
    kwargs = {"path": "/"}
    if settings.cookie_domain:
        kwargs["domain"] = settings.cookie_domain
    response.delete_cookie(SESSION_COOKIE, **kwargs)
    response.delete_cookie(CSRF_COOKIE, **kwargs)


@router.get("/methods", response_model=AuthMethodsOut)
async def auth_methods(db: DB) -> AuthMethodsOut:
    settings_service = SettingsService(db)
    return AuthMethodsOut(
        local=bool(await settings_service.get("auth.allow_local_login", True)),
        registration=str(await settings_service.get("auth.registration", "closed")),
        oidc=bool(await settings_service.get("auth.oidc.enabled", False)),
        oidc_provider_name=str(await settings_service.get("auth.oidc.provider_name", "SSO")),
        ldap=bool(await settings_service.get("auth.ldap.enabled", False)),
    )


@router.post(
    "/login", response_model=LoginResponse, dependencies=[Depends(rate_limited("auth"))]
)
async def login(payload: LoginRequest, request: Request, response: Response, db: DB) -> LoginResponse:
    auth = AuthService(db)
    if payload.method == "ldap":
        user = await auth.authenticate_ldap(payload.username, payload.password)
    else:
        user = await auth.authenticate_local(payload.username, payload.password)
    _session, token, csrf = await auth.create_session(
        user, user_agent=request.headers.get("user-agent", ""), ip_address=client_ip(request)
    )
    ttl_hours = int(await SettingsService(db).get("auth.session_ttl_hours", 336))
    _set_session_cookies(response, token, csrf, max_age=ttl_hours * 3600)
    await audit.record(
        db, action="auth.login", actor_id=user.id, ip_address=client_ip(request),
        data={"method": payload.method},
    )
    return LoginResponse(user=UserOut.model_validate(user), csrf_token=csrf)


@router.post(
    "/register", response_model=LoginResponse, dependencies=[Depends(rate_limited("auth"))]
)
async def register(
    payload: RegisterRequest, request: Request, response: Response, db: DB
) -> LoginResponse:
    auth = AuthService(db)
    user = await auth.register_local(payload.username, payload.password, payload.email)
    _session, token, csrf = await auth.create_session(
        user, user_agent=request.headers.get("user-agent", ""), ip_address=client_ip(request)
    )
    ttl_hours = int(await SettingsService(db).get("auth.session_ttl_hours", 336))
    _set_session_cookies(response, token, csrf, max_age=ttl_hours * 3600)
    await audit.record(
        db, action="auth.register", actor_id=user.id, ip_address=client_ip(request)
    )
    return LoginResponse(user=UserOut.model_validate(user), csrf_token=csrf)


@router.post("/logout", response_model=Message)
async def logout(request: Request, response: Response, user: CurrentUser, db: DB) -> Message:
    session = getattr(request.state, "session", None)
    if session is not None:
        await AuthService(db).revoke_session(session)
    _clear_session_cookies(response)
    return Message(message="Logged out.")


@router.post("/password", response_model=Message)
async def change_password(
    payload: ChangePasswordRequest, user: CurrentUser, db: DB
) -> Message:
    await AuthService(db).change_password(user, payload.current_password, payload.new_password)
    return Message(message="Password updated.")


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(user: CurrentUser, db: DB) -> list[SessionOut]:
    sessions = await AuthService(db).list_sessions(user)
    return [SessionOut.model_validate(s) for s in sessions]


@router.delete("/sessions/{session_id}", response_model=Message)
async def revoke_session(session_id: str, request: Request, user: CurrentUser, db: DB) -> Message:
    sessions = await AuthService(db).list_sessions(user)
    target = next((s for s in sessions if s.id == session_id), None)
    if target is None:
        raise NotFoundError("Session not found.")
    await AuthService(db).revoke_session(target)
    return Message(message="Session revoked.")


@router.post("/sessions/revoke-all", response_model=Message)
async def revoke_all_sessions(request: Request, user: CurrentUser, db: DB) -> Message:
    current = getattr(request.state, "session", None)
    count = await AuthService(db).revoke_all_sessions(
        user, except_session_id=current.id if current else None
    )
    return Message(message=f"Revoked {count} session(s).")


# ---------------------------------------------------------------------------
# OIDC (generic; covers Authentik, Authelia, Keycloak, etc.)
# ---------------------------------------------------------------------------


def _sign_state(payload: dict) -> str:
    secret = get_settings().secret_key.encode()
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    signature = hmac.new(secret, body.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{body}.{signature}"


def _verify_state(token: str) -> dict | None:
    try:
        body, signature = token.rsplit(".", 1)
        secret = get_settings().secret_key.encode()
        expected = hmac.new(secret, body.encode(), hashlib.sha256).hexdigest()[:32]
        if not hmac.compare_digest(signature, expected):
            return None
        payload = json.loads(base64.urlsafe_b64decode(body.encode()))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except (ValueError, TypeError):
        return None


async def _oidc_discovery(issuer: str) -> dict:
    url = issuer.rstrip("/") + "/.well-known/openid-configuration"
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()


def _redirect_uri() -> str:
    base = get_settings().base_url
    if not base:
        raise ValidationFailed(
            "ZEN_BASE_URL must be configured for OIDC login (used for the redirect URI)."
        )
    return f"{base}/api/v1/auth/oidc/callback"


@router.get("/oidc/login")
async def oidc_login(db: DB) -> RedirectResponse:
    config = await AuthService(db).oidc_config()
    if not config["enabled"] or not config["issuer"] or not config["client_id"]:
        raise AuthenticationError("OIDC is not configured on this instance.")
    discovery = await _oidc_discovery(config["issuer"])
    verifier = secrets.token_urlsafe(48)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .decode()
        .rstrip("=")
    )
    nonce = secrets.token_urlsafe(16)
    state_token = _sign_state(
        {"nonce": nonce, "verifier": verifier, "exp": time.time() + 600}
    )
    params = {
        "response_type": "code",
        "client_id": config["client_id"],
        "redirect_uri": _redirect_uri(),
        "scope": config["scopes"],
        "state": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    url = discovery["authorization_endpoint"] + "?" + urllib.parse.urlencode(params)
    response = RedirectResponse(url, status_code=302)
    response.set_cookie(
        OIDC_STATE_COOKIE,
        state_token,
        max_age=600,
        httponly=True,
        secure=get_settings().cookie_secure_effective,
        samesite="lax",
        path="/api/v1/auth/oidc",
    )
    return response


@router.get("/oidc/callback")
async def oidc_callback(request: Request, db: DB, code: str = "", state: str = "") -> RedirectResponse:
    if not code or not state:
        raise AuthenticationError("OIDC callback missing code or state.")
    state_payload = _verify_state(request.cookies.get(OIDC_STATE_COOKIE, ""))
    if state_payload is None or state_payload.get("nonce") != state:
        raise AuthenticationError("OIDC state validation failed. Please retry login.")
    auth = AuthService(db)
    config = await auth.oidc_config()
    discovery = await _oidc_discovery(config["issuer"])
    async with httpx.AsyncClient(timeout=15.0) as client:
        token_response = await client.post(
            discovery["token_endpoint"],
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": _redirect_uri(),
                "client_id": config["client_id"],
                "client_secret": config["client_secret"],
                "code_verifier": state_payload["verifier"],
            },
            headers={"Accept": "application/json"},
        )
        if token_response.status_code != 200:
            raise AuthenticationError(
                f"OIDC token exchange failed ({token_response.status_code})."
            )
        tokens = token_response.json()
        access_token = tokens.get("access_token", "")
        if not access_token:
            raise AuthenticationError("OIDC token exchange returned no access token.")
        userinfo_response = await client.get(
            discovery["userinfo_endpoint"],
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if userinfo_response.status_code != 200:
            raise AuthenticationError("OIDC userinfo request failed.")
        claims = userinfo_response.json()

    user = await auth.resolve_oidc_identity(claims)
    _session, token, csrf = await auth.create_session(
        user,
        user_agent=request.headers.get("user-agent", ""),
        ip_address=client_ip(request),
    )
    ttl_hours = int(await SettingsService(db).get("auth.session_ttl_hours", 336))
    response = RedirectResponse("/", status_code=302)
    _set_session_cookies(response, token, csrf, max_age=ttl_hours * 3600)
    response.delete_cookie(OIDC_STATE_COOKIE, path="/api/v1/auth/oidc")
    await audit.record(
        db, action="auth.login", actor_id=user.id, ip_address=client_ip(request),
        data={"method": "oidc"},
    )
    return response
