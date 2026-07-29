"""Frontend profile types (DD-059): flows, routes, redirect policy, profile.

A ``FrontendProfile`` is the flow-wide, immutable description of one
first-party frontend: where its users land for every auth flow, how mail to
them is branded, which origins redirects may target, and which audiences may
authenticate through it. Profiles are routing/branding/policy surfaces — they
are not tenants and create no credential isolation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from urllib.parse import quote, urlsplit, urlunsplit

from outlabs_auth.frontend.errors import (
    FrontendConfigurationError,
    FrontendRouteUnsupportedError,
)

_TOKEN_PLACEHOLDER = "{token}"
_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_LOCAL_DEV_HOSTS = {"localhost", "127.0.0.1", "::1"}


class FrontendFlow(str, Enum):
    """The destination-bearing auth flows a profile can route."""

    INVITE = "invite"
    PASSWORD_RESET = "password_reset"
    PASSWORD_RESET_CONFIRMATION = "password_reset_confirmation"
    ACCESS_GRANTED = "access_granted"
    MAGIC_LINK = "magic_link"
    ACCESS_CODE = "access_code"
    OAUTH_LOGIN = "oauth_login"
    OAUTH_ASSOCIATE = "oauth_associate"


#: Flows whose route template carries a ``{token}`` placeholder.
TOKEN_FLOWS = frozenset({FrontendFlow.INVITE, FrontendFlow.PASSWORD_RESET, FrontendFlow.MAGIC_LINK})


def validate_profile_key(key: str) -> str:
    """Validate a stable, non-secret profile key."""
    if not isinstance(key, str) or not key:
        raise FrontendConfigurationError("Frontend profile keys must be non-empty strings")
    if not _KEY_RE.match(key):
        raise FrontendConfigurationError(
            f"Invalid frontend profile key {key!r}: use lowercase letters, digits, and dashes "
            "(e.g. 'agent-portal'). Keys are stable, non-secret identifiers."
        )
    return key


def validate_public_origin(origin: str, *, local_dev: bool) -> str:
    """
    Validate and normalize a registered public origin.

    Origins are absolute, carry no path/query/fragment, and must be HTTPS
    outside explicitly local development (``localhost``/loopback over HTTP is
    accepted only when ``local_dev=True``).
    """
    if not isinstance(origin, str) or not origin.strip():
        raise FrontendConfigurationError("Frontend profile origins must be non-empty strings")
    candidate = origin.strip().rstrip("/")
    parts = urlsplit(candidate)
    if parts.scheme not in {"https", "http"} or not parts.netloc:
        raise FrontendConfigurationError(
            f"Invalid frontend origin {origin!r}: expected an absolute URL such as 'https://app.example.com'"
        )
    if parts.path or parts.query or parts.fragment:
        raise FrontendConfigurationError(
            f"Invalid frontend origin {origin!r}: origins carry no path, query, or fragment"
        )
    if parts.username or parts.password:
        raise FrontendConfigurationError(f"Invalid frontend origin {origin!r}: origins must not embed credentials")
    host = (parts.hostname or "").lower()
    is_local = host in _LOCAL_DEV_HOSTS or host.endswith(".localhost")
    if parts.scheme == "http" and not (local_dev and is_local):
        raise FrontendConfigurationError(
            f"Invalid frontend origin {origin!r}: public origins must be HTTPS outside local development"
        )
    return urlunsplit((parts.scheme, parts.netloc.lower(), "", "", ""))


@dataclass(frozen=True, slots=True)
class FrontendRoutes:
    """
    Typed per-flow route templates for one frontend.

    Token-carrying flows (``accept_invite``, ``password_reset``,
    ``magic_link``) must embed exactly one ``{token}`` placeholder — both
    query placement (``/auth/reset?token={token}``) and path placement
    (``/recovery/{token}``) are first-class. Non-token routes
    (``login``, ``access_code``, OAuth landings) must not contain the
    placeholder. ``None`` means this frontend does not support that flow;
    selecting the profile for it is a wiring error at startup or a
    fail-closed delivery error at send time — never a guessed link.
    """

    login: Optional[str] = None
    password_reset: Optional[str] = None
    accept_invite: Optional[str] = None
    magic_link: Optional[str] = None
    access_code: Optional[str] = None
    oauth_success: Optional[str] = None
    oauth_error: Optional[str] = None
    oauth_associate_success: Optional[str] = None

    def __post_init__(self) -> None:
        token_routes = {
            "password_reset": self.password_reset,
            "accept_invite": self.accept_invite,
            "magic_link": self.magic_link,
        }
        plain_routes = {
            "login": self.login,
            "access_code": self.access_code,
            "oauth_success": self.oauth_success,
            "oauth_error": self.oauth_error,
            "oauth_associate_success": self.oauth_associate_success,
        }
        for field_name, template in {**token_routes, **plain_routes}.items():
            if template is None:
                continue
            if not template.startswith("/"):
                raise FrontendConfigurationError(
                    f"Route template {field_name}={template!r} must be an absolute path starting with '/'"
                )
        for field_name, template in token_routes.items():
            if template is None:
                continue
            if template.count(_TOKEN_PLACEHOLDER) != 1:
                raise FrontendConfigurationError(
                    f"Route template {field_name}={template!r} must contain exactly one "
                    "'{token}' placeholder (query '?token={token}' and path '/recovery/{token}' "
                    "placements are both valid)"
                )
        for field_name, template in plain_routes.items():
            if template is not None and _TOKEN_PLACEHOLDER in template:
                raise FrontendConfigurationError(
                    f"Route template {field_name}={template!r} must not contain a '{{token}}' placeholder"
                )

    def route_for(self, flow: FrontendFlow) -> Optional[str]:
        """Return the primary route template for ``flow`` (``None`` = unsupported)."""
        return {
            FrontendFlow.INVITE: self.accept_invite,
            FrontendFlow.PASSWORD_RESET: self.password_reset,
            FrontendFlow.PASSWORD_RESET_CONFIRMATION: None,
            FrontendFlow.ACCESS_GRANTED: self.login,
            FrontendFlow.MAGIC_LINK: self.magic_link,
            FrontendFlow.ACCESS_CODE: self.access_code,
            FrontendFlow.OAUTH_LOGIN: self.oauth_success,
            FrontendFlow.OAUTH_ASSOCIATE: self.oauth_associate_success,
        }[flow]

    def error_route_for(self, flow: FrontendFlow) -> Optional[str]:
        """Return the error landing for OAuth flows (falls back to ``login``)."""
        if flow in (FrontendFlow.OAUTH_LOGIN, FrontendFlow.OAUTH_ASSOCIATE):
            return self.oauth_error or self.login
        return None


@dataclass(frozen=True, slots=True)
class RedirectPolicy:
    """
    Return-target validation policy for challenge flows.

    A request's return target is valid when it is a relative path (allowed by
    ``allow_relative_paths``) or an absolute URL whose origin is registered —
    the profile's own ``public_origins`` plus any ``extra_allowed_origins``.
    Validation produces the canonical absolute ``next_url`` on the profile's
    primary origin; anything else is rejected.
    """

    allow_relative_paths: bool = True
    extra_allowed_origins: tuple[str, ...] = ()
    default_return_path: str = "/"

    def __post_init__(self) -> None:
        if not self.default_return_path.startswith("/") or self.default_return_path.startswith("//"):
            raise FrontendConfigurationError(
                f"default_return_path={self.default_return_path!r} must be an absolute path starting with '/'"
            )

    def allowed_origins(self, profile: "FrontendProfile") -> frozenset[str]:
        return frozenset((*profile.public_origins, *self.extra_allowed_origins))

    def normalize_return_target(self, profile: "FrontendProfile", target: Optional[str]) -> Optional[str]:
        """
        Normalize ``target`` into a canonical absolute URL, or return ``None``.

        ``None`` input falls back to ``default_return_path`` on the profile's
        primary origin. Relative paths land on the primary origin. Absolute
        URLs must sit on a registered origin, keep their path/query/fragment,
        and drop any embedded credentials.
        """
        primary = profile.public_origins[0]
        if target is None or not str(target).strip():
            return f"{primary}{self.default_return_path}"
        candidate = str(target).strip()
        if candidate.startswith("/") and not candidate.startswith("//"):
            if not self.allow_relative_paths:
                return None
            return f"{primary}{candidate}"
        parts = urlsplit(candidate)
        if parts.scheme not in {"https", "http"} or not parts.netloc:
            return None
        origin = urlunsplit((parts.scheme, parts.netloc.lower(), "", "", ""))
        if origin not in self.allowed_origins(profile):
            return None
        netloc = parts.netloc
        if parts.port is not None or "@" not in netloc:
            # Keep an explicit port; drop any userinfo.
            host = parts.hostname or ""
            netloc = f"{host}:{parts.port}" if parts.port is not None else host
        else:
            netloc = parts.hostname or ""
        return urlunsplit((parts.scheme, netloc.lower(), parts.path or "/", parts.query, parts.fragment))


@dataclass(frozen=True, slots=True)
class FrontendProfile:
    """
    One first-party frontend of the platform (immutable after declaration).

    ``accepted_audiences`` lists the host-classified audiences that may
    authenticate through this frontend; empty means the profile accepts
    everyone (the shared/SSO mode).
    """

    key: str
    app_name: str
    public_origins: tuple[str, ...]
    routes: FrontendRoutes = field(default_factory=FrontendRoutes)
    redirect_policy: RedirectPolicy = field(default_factory=RedirectPolicy)
    accepted_audiences: tuple[str, ...] = ()
    support_email: Optional[str] = None

    def __post_init__(self) -> None:
        validate_profile_key(self.key)
        if not self.app_name or not str(self.app_name).strip():
            raise FrontendConfigurationError(f"Frontend profile {self.key!r} must declare an app_name")
        if not self.public_origins:
            raise FrontendConfigurationError(f"Frontend profile {self.key!r} must register at least one public origin")
        for audience in self.accepted_audiences:
            if not audience or not str(audience).strip():
                raise FrontendConfigurationError(f"Frontend profile {self.key!r} has an empty accepted_audiences entry")

    @property
    def primary_origin(self) -> str:
        return self.public_origins[0]

    def route_for(self, flow: FrontendFlow) -> Optional[str]:
        return self.routes.route_for(flow)

    def render_url(self, flow: FrontendFlow, token: Optional[str] = None) -> str:
        """
        Render the absolute URL for ``flow`` on this profile's primary origin.

        Raises ``FrontendRouteUnsupportedError`` when the flow is unsupported
        or a token-carrying flow is rendered without a token — callers fail
        closed rather than emit a guessed link.
        """
        template = self.routes.route_for(flow)
        if template is None:
            raise FrontendRouteUnsupportedError(
                f"Frontend profile {self.key!r} does not support flow {flow.value!r} (route is None)"
            )
        if flow in TOKEN_FLOWS:
            if token is None:
                raise FrontendRouteUnsupportedError(
                    f"Frontend profile {self.key!r} flow {flow.value!r} requires a token to render"
                )
            rendered = template.replace(_TOKEN_PLACEHOLDER, quote(token, safe=""))
        else:
            rendered = template
        return f"{self.primary_origin}{rendered}"
