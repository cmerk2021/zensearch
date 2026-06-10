"""Layer-2 instance settings service (ADR-0003).

Settings are stored as JSON documents in ``instance_settings``, validated
against the defaults registry below, cached in-process with a short TTL, and
invalidated cluster-wide through a generation key in the cache backend.
Secret-valued keys are encrypted at rest and redacted on read APIs.
"""

from __future__ import annotations

import json
import time
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zen.core.cache import get_cache
from zen.core.config import get_settings
from zen.core.exceptions import ValidationFailed
from zen.core.security import decrypt_secret, encrypt_secret, redact_secret
from zen.db.models import InstanceSetting

log = structlog.get_logger(__name__)

#: Known settings and their defaults. Unknown keys are rejected.
DEFAULTS: dict[str, Any] = {
    # Branding
    "instance.name": "Zen",
    "instance.tagline": "Search less. Find more.",
    "instance.logo_url": "",
    # Authentication policy
    "auth.registration": "closed",  # open | closed
    "auth.allow_local_login": True,
    "auth.session_ttl_hours": 336,
    "auth.oidc.enabled": False,
    "auth.oidc.provider_name": "SSO",
    "auth.oidc.issuer": "",
    "auth.oidc.client_id": "",
    "auth.oidc.client_secret": "",
    "auth.oidc.scopes": "openid profile email",
    "auth.oidc.admin_groups": [],
    "auth.oidc.auto_create_users": True,
    "auth.ldap.enabled": False,
    "auth.ldap.server": "",
    "auth.ldap.bind_dn_template": "",
    "auth.ldap.user_search_base": "",
    "auth.ldap.user_filter": "(uid={username})",
    "auth.ldap.start_tls": True,
    # Search behavior
    "search.ranker": "rrf",
    "search.factor_weights": {},
    "search.custom_bangs": {},
    "search.focus_blocked_domains": [],
    "search.default_mode": "normal",
    "search.safe_search": True,
    # Privacy
    "privacy.search_history_enabled": True,
    "privacy.search_history_retention_days": 90,
    "privacy.click_tracking_enabled": True,
    # AI
    "ai.enabled": False,
    "ai.backend": "ollama",  # ollama | lmstudio | openai | openrouter
    "ai.base_url": "",
    "ai.api_key": "",
    "ai.model": "",
    "ai.temperature": 0.3,
    "ai.max_tokens": 1024,
    "ai.timeout_seconds": 120,
    # UI defaults
    "ui.default_theme": "system",
    "ui.results_density": "comfortable",
    # Security
    "security.rate_limits": {
        "auth": "10/300",
        "search": "60/60",
        "api": "600/60",
        "ai": "30/300",
    },
    "security.audit_enabled": True,
    # Workspaces policy
    "workspaces.max_per_user": 0,  # 0 = unlimited
    # Plugins
    "plugins.allow_install": True,
}

#: Keys whose values are encrypted at rest and redacted in read APIs.
SECRET_KEYS: frozenset[str] = frozenset({"auth.oidc.client_secret", "ai.api_key"})

_LOCAL_TTL_SECONDS = 5.0
_GENERATION_KEY = "settings:generation"

# Process-local snapshot: (loaded_at_monotonic, generation, data)
_snapshot: tuple[float, str, dict[str, Any]] | None = None


def _wrap(value: Any) -> dict:
    return {"v": value}


def _unwrap(stored: dict) -> Any:
    return stored.get("v") if isinstance(stored, dict) else stored


class SettingsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _load_all(self) -> dict[str, Any]:
        global _snapshot
        now = time.monotonic()
        generation = await get_cache().get(_GENERATION_KEY) or "0"
        if (
            _snapshot is not None
            and now - _snapshot[0] < _LOCAL_TTL_SECONDS
            and _snapshot[1] == generation
        ):
            return _snapshot[2]
        rows = (await self.db.execute(select(InstanceSetting))).scalars().all()
        data = dict(DEFAULTS)
        for row in rows:
            if row.key in DEFAULTS:
                data[row.key] = _unwrap(row.value)
        _snapshot = (now, generation, data)
        return data

    async def get(self, key: str, default: Any = None) -> Any:
        data = await self._load_all()
        if key in data:
            value = data[key]
            if key in SECRET_KEYS and value:
                try:
                    return decrypt_secret(value, get_settings().secret_key)
                except ValueError:
                    log.error("settings.secret_decrypt_failed", key=key)
                    return ""
            return value
        return default

    async def get_all(self, *, redact_secrets: bool = True) -> dict[str, Any]:
        data = dict(await self._load_all())
        for key in SECRET_KEYS:
            raw = data.get(key) or ""
            if not raw:
                continue
            if redact_secrets:
                try:
                    plain = decrypt_secret(raw, get_settings().secret_key)
                except ValueError:
                    plain = ""
                data[key] = redact_secret(plain)
            else:
                try:
                    data[key] = decrypt_secret(raw, get_settings().secret_key)
                except ValueError:
                    data[key] = ""
        return data

    async def set(self, key: str, value: Any, *, actor_id: str | None = None) -> None:
        if key not in DEFAULTS:
            raise ValidationFailed(f"Unknown instance setting: {key}")
        self._validate(key, value)
        if key in SECRET_KEYS:
            value = encrypt_secret(str(value or ""), get_settings().secret_key)
        row = await self.db.get(InstanceSetting, key)
        if row is None:
            row = InstanceSetting(key=key, value=_wrap(value), updated_by=actor_id)
            self.db.add(row)
        else:
            row.value = _wrap(value)
            row.updated_by = actor_id
        await self.db.commit()
        await self._bump_generation()
        log.info("settings.updated", key=key, actor=actor_id)

    async def set_many(self, values: dict[str, Any], *, actor_id: str | None = None) -> None:
        for key in values:
            if key not in DEFAULTS:
                raise ValidationFailed(f"Unknown instance setting: {key}")
        for key, value in values.items():
            self._validate(key, value)
        for key, value in values.items():
            stored = value
            if key in SECRET_KEYS:
                stored = encrypt_secret(str(value or ""), get_settings().secret_key)
            row = await self.db.get(InstanceSetting, key)
            if row is None:
                self.db.add(InstanceSetting(key=key, value=_wrap(stored), updated_by=actor_id))
            else:
                row.value = _wrap(stored)
                row.updated_by = actor_id
        await self.db.commit()
        await self._bump_generation()
        log.info("settings.updated_many", keys=sorted(values), actor=actor_id)

    async def reset(self, key: str, *, actor_id: str | None = None) -> None:
        row = await self.db.get(InstanceSetting, key)
        if row is not None:
            await self.db.delete(row)
            await self.db.commit()
            await self._bump_generation()
            log.info("settings.reset", key=key, actor=actor_id)

    @staticmethod
    def _validate(key: str, value: Any) -> None:
        default = DEFAULTS[key]
        if key in SECRET_KEYS:
            if value is not None and not isinstance(value, str):
                raise ValidationFailed(f"Setting {key} must be a string.")
            return
        if isinstance(default, bool):
            if not isinstance(value, bool):
                raise ValidationFailed(f"Setting {key} must be a boolean.")
        elif (isinstance(default, int) and not isinstance(default, bool)) or isinstance(default, float):
            if not isinstance(value, int | float):
                raise ValidationFailed(f"Setting {key} must be a number.")
        elif isinstance(default, str):
            if not isinstance(value, str):
                raise ValidationFailed(f"Setting {key} must be a string.")
        elif isinstance(default, list):
            if not isinstance(value, list):
                raise ValidationFailed(f"Setting {key} must be a list.")
        elif isinstance(default, dict) and not isinstance(value, dict):
            raise ValidationFailed(f"Setting {key} must be an object.")
        # Domain-specific checks
        if key == "auth.registration" and value not in ("open", "closed"):
            raise ValidationFailed("auth.registration must be 'open' or 'closed'.")
        if key == "ai.backend" and value not in ("ollama", "lmstudio", "openai", "openrouter"):
            raise ValidationFailed("ai.backend must be one of: ollama, lmstudio, openai, openrouter.")
        if key == "search.default_mode" and value not in ("normal", "privacy", "focus", "research"):
            raise ValidationFailed("search.default_mode is not a valid mode.")
        if key == "ui.default_theme" and value not in ("system", "light", "dark", "amoled"):
            raise ValidationFailed("ui.default_theme is not a valid theme.")
        if key == "security.rate_limits" and isinstance(value, dict):
            from zen.core.rate_limit import RateLimit

            for bucket, spec in value.items():
                try:
                    RateLimit.parse(str(spec))
                except (TypeError, ValueError) as exc:
                    raise ValidationFailed(
                        f"Invalid rate limit spec for '{bucket}': {spec}"
                    ) from exc

    @staticmethod
    async def _bump_generation() -> None:
        await get_cache().incr(_GENERATION_KEY)

    @staticmethod
    def invalidate_local() -> None:
        """Test helper: drop the process-local snapshot."""
        global _snapshot
        _snapshot = None


def export_defaults() -> str:
    """Render the defaults registry as JSON (used by docs generation and CLI)."""
    return json.dumps(DEFAULTS, indent=2, sort_keys=True)
