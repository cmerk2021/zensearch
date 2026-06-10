"""Authentication service: local credentials, sessions, OIDC, and LDAP.

All identity paths converge on the same opaque-session mechanism (ADR-0006).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zen.core.config import get_settings
from zen.core.exceptions import (
    AuthenticationError,
    InvalidCredentialsError,
    PermissionDeniedError,
    ValidationFailed,
)
from zen.core.security import (
    generate_token,
    hash_password,
    hash_token,
    validate_password_strength,
    verify_password,
)
from zen.db.base import utcnow
from zen.db.models import AuthSource, Role, User, UserPreferences, UserSession
from zen.services import audit
from zen.services.settings import SettingsService

log = structlog.get_logger(__name__)

SESSION_COOKIE = "zen_session"
CSRF_COOKIE = "zen_csrf"


def _ensure_aware(dt: datetime) -> datetime:
    """SQLite returns naive datetimes; normalize to UTC-aware."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.settings = SettingsService(db)

    # ------------------------------------------------------------------
    # Local credentials
    # ------------------------------------------------------------------

    async def authenticate_local(self, username: str, password: str) -> User:
        if not await self.settings.get("auth.allow_local_login", True):
            raise PermissionDeniedError("Local login is disabled on this instance.")
        username = username.strip().lower()
        user = (
            await self.db.execute(select(User).where(User.username == username))
        ).scalar_one_or_none()
        if user is None or not user.password_hash:
            # Constant-ish time: hash anyway to reduce username probing signal.
            hash_password(password)
            raise InvalidCredentialsError("Invalid username or password.")
        if not verify_password(password, user.password_hash):
            raise InvalidCredentialsError("Invalid username or password.")
        if not user.is_active:
            raise PermissionDeniedError("This account is disabled.")
        return user

    async def register_local(self, username: str, password: str, email: str | None = None) -> User:
        registration = await self.settings.get("auth.registration", "closed")
        if registration != "open":
            raise PermissionDeniedError("Registration is closed on this instance.")
        return await self.create_user(
            username=username, password=password, email=email, role=Role.USER.value
        )

    async def create_user(
        self,
        *,
        username: str,
        password: str | None,
        email: str | None = None,
        role: str = Role.USER.value,
        display_name: str = "",
        auth_source: str = AuthSource.LOCAL.value,
        external_id: str | None = None,
    ) -> User:
        username = username.strip().lower()
        if not username or len(username) < 2 or len(username) > 64:
            raise ValidationFailed("Username must be 2-64 characters.")
        if not all(c.isalnum() or c in "._-" for c in username):
            raise ValidationFailed("Username may contain letters, digits, '.', '_' and '-'.")
        if role not in (Role.ADMIN.value, Role.USER.value, Role.READONLY.value):
            raise ValidationFailed(f"Unknown role: {role}")
        existing = (
            await self.db.execute(select(User).where(User.username == username))
        ).scalar_one_or_none()
        if existing is not None:
            raise ValidationFailed("Username is already taken.")
        password_hash = None
        if password is not None:
            problems = validate_password_strength(password)
            if problems:
                raise ValidationFailed(" ".join(problems))
            password_hash = hash_password(password)
        user = User(
            username=username,
            email=(email or "").strip().lower() or None,
            password_hash=password_hash,
            display_name=display_name or username,
            role=role,
            auth_source=auth_source,
            external_id=external_id,
        )
        user.preferences = UserPreferences()
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        log.info("user.created", username=username, role=role, source=auth_source)
        return user

    async def change_password(self, user: User, current: str, new: str) -> None:
        if user.auth_source != AuthSource.LOCAL.value:
            raise ValidationFailed("Password is managed by your identity provider.")
        if not user.password_hash or not verify_password(current, user.password_hash):
            raise InvalidCredentialsError("Current password is incorrect.")
        problems = validate_password_strength(new)
        if problems:
            raise ValidationFailed(" ".join(problems))
        user.password_hash = hash_password(new)
        await self.db.commit()
        await audit.record(self.db, action="user.password_changed", actor_id=user.id)

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    async def create_session(
        self, user: User, *, user_agent: str = "", ip_address: str = ""
    ) -> tuple[UserSession, str, str]:
        """Create a session; returns (session, raw_token, csrf_token)."""
        token = generate_token()
        csrf = generate_token()
        ttl_hours = int(await self.settings.get("auth.session_ttl_hours", 336))
        session = UserSession(
            user_id=user.id,
            token_hash=hash_token(token),
            csrf_token=csrf,
            user_agent=user_agent[:400],
            ip_address=ip_address[:64],
            expires_at=utcnow() + timedelta(hours=ttl_hours),
        )
        self.db.add(session)
        user.last_login_at = utcnow()
        await self.db.commit()
        await self.db.refresh(session)
        return session, token, csrf

    async def resolve_session(self, raw_token: str) -> tuple[User, UserSession] | None:
        if not raw_token:
            return None
        token_hash = hash_token(raw_token)
        session = (
            await self.db.execute(
                select(UserSession).where(UserSession.token_hash == token_hash)
            )
        ).scalar_one_or_none()
        if session is None or session.revoked_at is not None:
            return None
        now = utcnow()
        if _ensure_aware(session.expires_at) < now:
            return None
        user = await self.db.get(User, session.user_id)
        if user is None or not user.is_active:
            return None
        # Sliding expiry: refresh at most once per hour to limit writes.
        if get_settings().session_sliding and (
            now - _ensure_aware(session.last_seen_at)
        ) > timedelta(hours=1):
            ttl_hours = int(await self.settings.get("auth.session_ttl_hours", 336))
            session.last_seen_at = now
            session.expires_at = now + timedelta(hours=ttl_hours)
            await self.db.commit()
        return user, session

    async def revoke_session(self, session: UserSession) -> None:
        session.revoked_at = utcnow()
        await self.db.commit()

    async def revoke_all_sessions(self, user: User, *, except_session_id: str | None = None) -> int:
        sessions = (
            await self.db.execute(
                select(UserSession).where(
                    UserSession.user_id == user.id, UserSession.revoked_at.is_(None)
                )
            )
        ).scalars().all()
        count = 0
        for session in sessions:
            if except_session_id and session.id == except_session_id:
                continue
            session.revoked_at = utcnow()
            count += 1
        await self.db.commit()
        return count

    async def list_sessions(self, user: User) -> list[UserSession]:
        now = utcnow()
        rows = (
            await self.db.execute(
                select(UserSession)
                .where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))
                .order_by(UserSession.last_seen_at.desc())
            )
        ).scalars().all()
        return [s for s in rows if _ensure_aware(s.expires_at) > now]

    # ------------------------------------------------------------------
    # OIDC (Authentik / Authelia / generic)
    # ------------------------------------------------------------------

    async def oidc_config(self) -> dict:
        enabled = await self.settings.get("auth.oidc.enabled", False)
        return {
            "enabled": bool(enabled),
            "provider_name": await self.settings.get("auth.oidc.provider_name", "SSO"),
            "issuer": await self.settings.get("auth.oidc.issuer", ""),
            "client_id": await self.settings.get("auth.oidc.client_id", ""),
            "client_secret": await self.settings.get("auth.oidc.client_secret", ""),
            "scopes": await self.settings.get("auth.oidc.scopes", "openid profile email"),
            "admin_groups": await self.settings.get("auth.oidc.admin_groups", []),
            "auto_create": await self.settings.get("auth.oidc.auto_create_users", True),
        }

    async def resolve_oidc_identity(self, claims: dict) -> User:
        """Map verified OIDC claims to a Zen user, creating one when allowed."""
        config = await self.oidc_config()
        sub = str(claims.get("sub", ""))
        if not sub:
            raise AuthenticationError("OIDC response missing 'sub' claim.")
        preferred = (
            claims.get("preferred_username") or claims.get("email") or f"oidc-{sub[:12]}"
        )
        email = claims.get("email")
        groups = claims.get("groups") or []
        is_admin = bool(
            config["admin_groups"] and any(g in config["admin_groups"] for g in groups)
        )

        user = (
            await self.db.execute(
                select(User).where(
                    User.auth_source == AuthSource.OIDC.value, User.external_id == sub
                )
            )
        ).scalar_one_or_none()
        if user is None:
            if not config["auto_create"]:
                raise PermissionDeniedError(
                    "No account exists for this identity and auto-creation is disabled."
                )
            username = await self._unique_username(str(preferred).lower())
            user = await self.create_user(
                username=username,
                password=None,
                email=email,
                role=Role.ADMIN.value if is_admin else Role.USER.value,
                display_name=str(claims.get("name") or preferred),
                auth_source=AuthSource.OIDC.value,
                external_id=sub,
            )
        else:
            # Sync role from groups when admin groups are configured.
            if config["admin_groups"]:
                new_role = Role.ADMIN.value if is_admin else Role.USER.value
                if user.role != Role.READONLY.value and user.role != new_role:
                    user.role = new_role
            if email and user.email != email:
                user.email = email
            await self.db.commit()
        if not user.is_active:
            raise PermissionDeniedError("This account is disabled.")
        return user

    async def _unique_username(self, base: str) -> str:
        base = "".join(c for c in base if c.isalnum() or c in "._-") or "user"
        candidate = base
        suffix = 0
        while True:
            existing = (
                await self.db.execute(select(User).where(User.username == candidate))
            ).scalar_one_or_none()
            if existing is None:
                return candidate
            suffix += 1
            candidate = f"{base}{suffix}"

    # ------------------------------------------------------------------
    # LDAP
    # ------------------------------------------------------------------

    async def authenticate_ldap(self, username: str, password: str) -> User:
        if not await self.settings.get("auth.ldap.enabled", False):
            raise PermissionDeniedError("LDAP authentication is disabled.")
        try:
            import ldap3
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise AuthenticationError(
                "LDAP support requires the 'ldap' extra: pip install zen-server[ldap]"
            ) from exc

        server_url = await self.settings.get("auth.ldap.server", "")
        template = await self.settings.get("auth.ldap.bind_dn_template", "")
        start_tls = await self.settings.get("auth.ldap.start_tls", True)
        if not server_url or not template:
            raise AuthenticationError("LDAP is not fully configured.")
        username = username.strip().lower()
        if any(c in username for c in "()*\\\0,=+<>#;\"'"):
            raise InvalidCredentialsError("Invalid username or password.")
        bind_dn = template.format(username=username)

        import asyncio

        def _bind() -> bool:
            server = ldap3.Server(server_url, get_info=ldap3.NONE, connect_timeout=5)
            conn = ldap3.Connection(server, user=bind_dn, password=password)
            if start_tls:
                conn.start_tls()
            ok = conn.bind()
            conn.unbind()
            return ok

        try:
            ok = await asyncio.get_event_loop().run_in_executor(None, _bind)
        except Exception as exc:
            raise AuthenticationError(f"LDAP connection failed: {exc}") from exc
        if not ok:
            raise InvalidCredentialsError("Invalid username or password.")

        user = (
            await self.db.execute(
                select(User).where(
                    User.auth_source == AuthSource.LDAP.value, User.username == username
                )
            )
        ).scalar_one_or_none()
        if user is None:
            user = await self.create_user(
                username=username,
                password=None,
                role=Role.USER.value,
                auth_source=AuthSource.LDAP.value,
                external_id=bind_dn,
            )
        if not user.is_active:
            raise PermissionDeniedError("This account is disabled.")
        return user

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    async def purge_expired_sessions(self) -> int:
        from sqlalchemy import delete, or_

        cutoff = utcnow()
        result = await self.db.execute(
            delete(UserSession).where(
                or_(UserSession.expires_at < cutoff, UserSession.revoked_at.is_not(None))
            )
        )
        await self.db.commit()
        return result.rowcount or 0
