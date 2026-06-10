"""Layer-1 environment configuration.

Infrastructure and bootstrap settings only (ADR-0003). Everything here is
read once at process start from environment variables / an optional ``.env``
file, and is intentionally **not** editable at runtime. Server-wide behavior
belongs to instance settings (``zen.services.settings``), personal preferences
to user preferences.
"""

from __future__ import annotations

import secrets as _secrets
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment configuration with the ``ZEN_`` prefix."""

    model_config = SettingsConfigDict(
        env_prefix="ZEN_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Runtime -----------------------------------------------------------
    env: Literal["production", "development", "test"] = "production"
    host: str = "0.0.0.0"
    port: int = 8000
    base_url: str = ""
    """Public base URL (scheme + host) used for OIDC redirects and absolute links."""

    # --- Secrets -----------------------------------------------------------
    secret_key: str = ""
    """Required in production. Used for session signing and secret encryption."""

    # --- Persistence -------------------------------------------------------
    database_url: str = "sqlite+aiosqlite:///./data/zen.db"
    """SQLAlchemy async URL. PostgreSQL recommended for production (ADR-0005)."""
    database_pool_size: int = 10
    database_pool_max_overflow: int = 5
    redis_url: str = ""
    """Optional. When empty, the in-memory cache backend is used (ADR-0005)."""

    data_dir: Path = Path("./data")
    """Root for SQLite files, plugin installs, and export scratch space."""

    # --- HTTP / proxy ------------------------------------------------------
    trusted_proxies: str = ""
    """Comma-separated CIDRs/IPs whose X-Forwarded-* headers are honored."""
    cors_origins: str = ""
    """Comma-separated additional origins allowed for CORS (same-origin is default)."""
    cookie_secure: bool | None = None
    """Force Secure cookie flag. None = auto (enabled when base_url is https)."""
    cookie_domain: str = ""

    # --- Sessions ----------------------------------------------------------
    session_ttl_hours: int = 24 * 14
    session_sliding: bool = True

    # --- Outbound search traffic --------------------------------------------
    outbound_timeout_seconds: float = 8.0
    outbound_proxy: str = ""
    """Optional proxy URL (e.g. socks5://...) for all provider traffic."""
    outbound_user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )

    # --- Bootstrap ---------------------------------------------------------
    bootstrap_admin_username: str = ""
    bootstrap_admin_password: str = ""
    """If both are set and no admin exists at startup, an admin is created."""

    # --- Observability -----------------------------------------------------
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "json"
    metrics_enabled: bool = True
    metrics_require_admin: bool = True

    # --- Misc --------------------------------------------------------------
    plugins_dir: Path | None = None
    rate_limit_enabled: bool = True

    @field_validator("base_url")
    @classmethod
    def _strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")

    @model_validator(mode="after")
    def _finalize(self) -> Settings:
        if not self.secret_key:
            if self.env == "production":
                raise ValueError(
                    "ZEN_SECRET_KEY is required in production. "
                    "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
                )
            # Deterministic enough for dev/test convenience, never for production.
            object.__setattr__(self, "secret_key", _secrets.token_urlsafe(48))
        if self.plugins_dir is None:
            object.__setattr__(self, "plugins_dir", self.data_dir / "plugins")
        return self

    # --- Derived helpers ----------------------------------------------------
    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def cookie_secure_effective(self) -> bool:
        if self.cookie_secure is not None:
            return self.cookie_secure
        return self.base_url.startswith("https://")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def trusted_proxy_list(self) -> list[str]:
        return [p.strip() for p in self.trusted_proxies.split(",") if p.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide settings singleton."""
    return Settings()


def reset_settings_cache() -> None:
    """Test helper: force settings re-read on next access."""
    get_settings.cache_clear()
