"""Schemas shared across routes."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Message(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: Any | None = None


# --- Users ------------------------------------------------------------------


class UserOut(ORMModel):
    id: str
    username: str
    email: str | None
    display_name: str
    role: str
    is_active: bool
    auth_source: str
    created_at: datetime
    last_login_at: datetime | None


class PreferencesOut(ORMModel):
    theme: str
    accent: str
    default_mode: str
    default_profile_id: str | None
    open_links_new_tab: bool
    keyboard_shortcuts: dict
    dashboard_layout: dict
    extra: dict


class PreferencesUpdate(BaseModel):
    theme: str | None = None
    accent: str | None = Field(default=None, max_length=32)
    default_mode: str | None = None
    default_profile_id: str | None = None
    open_links_new_tab: bool | None = None
    keyboard_shortcuts: dict | None = None
    dashboard_layout: dict | None = None
    extra: dict | None = None


class ProfileUpdateMe(BaseModel):
    display_name: str | None = Field(default=None, max_length=128)
    email: str | None = Field(default=None, max_length=255)


class SessionOut(ORMModel):
    id: str
    user_agent: str
    ip_address: str
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime


# --- Auth -------------------------------------------------------------------


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)
    method: str = Field(default="local", pattern="^(local|ldap)$")


class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=10, max_length=256)
    email: str | None = Field(default=None, max_length=255)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(max_length=256)
    new_password: str = Field(min_length=10, max_length=256)


class LoginResponse(BaseModel):
    user: UserOut
    csrf_token: str


class AuthMethodsOut(BaseModel):
    local: bool
    registration: str
    oidc: bool
    oidc_provider_name: str
    ldap: bool
