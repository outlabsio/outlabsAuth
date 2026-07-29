"""Error types for frontend profiles and resolution (DD-059).

Two families:

- Configuration errors (``FrontendConfigurationError`` and subclasses) are
  wiring-time failures: they should surface while the host declares its
  registry or builds its mail service, never at send time.
- Resolution errors (``FrontendResolutionError`` and subclasses) are runtime
  fail-closed signals: callers turn them into a structured delivery failure,
  never into a guessed default.
"""

from __future__ import annotations

from typing import Any, Optional


class FrontendConfigurationError(ValueError):
    """Invalid frontend profile declaration or wiring."""


class UnknownFrontendProfileError(FrontendConfigurationError):
    """A profile key was referenced that is not in the registry."""


class FrontendRouteUnsupportedError(FrontendConfigurationError):
    """A profile was selected for a flow its routes declare unsupported."""


class FrontendResolutionError(Exception):
    """
    Runtime resolution failure — the delivery pipeline must fail closed.

    Carries a stable machine-readable ``reason`` for structured results and
    audit/log records. Never swallow this into a default profile.
    """

    def __init__(
        self,
        reason: str,
        message: str,
        *,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.details = details or {}

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"{type(self).__name__}(reason={self.reason!r}, details={self.details!r})"


class FrontendUnresolvedError(FrontendResolutionError):
    """The resolver could not classify this context and no default applies."""

    def __init__(self, message: str, *, details: Optional[dict[str, Any]] = None) -> None:
        super().__init__("frontend_unresolved", message, details=details)


class FrontendResolverFailedError(FrontendResolutionError):
    """The host resolver raised — a hard failure, never default-eligible."""

    def __init__(self, message: str, *, details: Optional[dict[str, Any]] = None) -> None:
        super().__init__("frontend_resolver_failed", message, details=details)


class FrontendProfileMismatchError(FrontendResolutionError):
    """The requested profile contradicts the resolved identity profile."""

    def __init__(self, message: str, *, details: Optional[dict[str, Any]] = None) -> None:
        super().__init__("frontend_profile_mismatch", message, details=details)


class UnknownRequestedProfileError(FrontendResolutionError):
    """The caller requested a profile key that is not registered."""

    def __init__(self, message: str, *, details: Optional[dict[str, Any]] = None) -> None:
        super().__init__("frontend_profile_unknown", message, details=details)


class WrongApplicationError(FrontendResolutionError):
    """
    Sign-in gate rejection (DD-059 slice 4): this user may not authenticate
    through the requested application. Routers map it to a stable 403 with
    code ``wrong_application``; the OAuth callback maps it to an error
    redirect with the same code.
    """

    def __init__(self, message: str, *, details: Optional[dict[str, Any]] = None) -> None:
        super().__init__("wrong_application", message, details=details)
