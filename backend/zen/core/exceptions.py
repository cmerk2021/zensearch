"""Domain exceptions mapped to HTTP responses at the API boundary."""

from __future__ import annotations

from typing import Any


class ZenError(Exception):
    """Base class for all domain errors."""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str = "", *, details: Any = None) -> None:
        super().__init__(message or self.__class__.__name__)
        self.message = message or self.code.replace("_", " ")
        self.details = details


class NotFoundError(ZenError):
    status_code = 404
    code = "not_found"


class ConflictError(ZenError):
    status_code = 409
    code = "conflict"


class ValidationFailed(ZenError):
    status_code = 422
    code = "validation_failed"


class AuthenticationError(ZenError):
    status_code = 401
    code = "authentication_required"


class InvalidCredentialsError(AuthenticationError):
    code = "invalid_credentials"


class PermissionDeniedError(ZenError):
    status_code = 403
    code = "permission_denied"


class CSRFError(ZenError):
    status_code = 403
    code = "csrf_failure"


class RateLimitedError(ZenError):
    status_code = 429
    code = "rate_limited"

    def __init__(self, message: str = "", *, retry_after: int = 60) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class ProviderError(ZenError):
    status_code = 502
    code = "provider_error"


class PluginError(ZenError):
    status_code = 400
    code = "plugin_error"


class PluginPermissionError(PluginError):
    code = "plugin_permission_denied"


class AIUnavailableError(ZenError):
    status_code = 503
    code = "ai_unavailable"
