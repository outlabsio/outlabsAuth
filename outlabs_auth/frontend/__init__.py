"""Multi-frontend support (DD-059): profiles, registry, and resolution.

One outlabsAuth deployment serves one platform with N first-party frontends.
A ``FrontendProfile`` is the flow-wide, immutable declaration of one
frontend; the ``FrontendProfileResolver`` is the canonical pipeline entry
point every destination-bearing flow consults. Profiles provide routing,
branding, and sign-in policy — not tenant or credential isolation.
"""

from outlabs_auth.frontend.errors import (
    FrontendConfigurationError,
    FrontendProfileMismatchError,
    FrontendResolutionError,
    FrontendResolverFailedError,
    FrontendRouteUnsupportedError,
    FrontendUnresolvedError,
    UnknownFrontendProfileError,
    UnknownRequestedProfileError,
    WrongApplicationError,
)
from outlabs_auth.frontend.flows import (
    ChallengeFrontendDispatch,
    consume_verified_challenge,
    enforce_sign_in_gate,
    prepare_challenge_dispatch,
    require_app,
)
from outlabs_auth.frontend.registry import FrontendProfileRegistry
from outlabs_auth.frontend.resolution import (
    FrontendProfileResolver,
    FrontendResolution,
    FrontendResolutionContext,
    HostResolverFn,
    route_by_root_entity_slug,
    route_by_root_entity_type,
)
from outlabs_auth.frontend.types import (
    TOKEN_FLOWS,
    FrontendFlow,
    FrontendProfile,
    FrontendRoutes,
    RedirectPolicy,
)

__all__ = [
    "ChallengeFrontendDispatch",
    "FrontendConfigurationError",
    "FrontendFlow",
    "FrontendProfile",
    "FrontendProfileMismatchError",
    "FrontendProfileRegistry",
    "FrontendProfileResolver",
    "FrontendResolution",
    "FrontendResolutionContext",
    "FrontendResolutionError",
    "FrontendResolverFailedError",
    "FrontendRouteUnsupportedError",
    "FrontendRoutes",
    "FrontendUnresolvedError",
    "HostResolverFn",
    "RedirectPolicy",
    "TOKEN_FLOWS",
    "UnknownFrontendProfileError",
    "UnknownRequestedProfileError",
    "WrongApplicationError",
    "consume_verified_challenge",
    "enforce_sign_in_gate",
    "prepare_challenge_dispatch",
    "require_app",
    "route_by_root_entity_slug",
    "route_by_root_entity_type",
]
