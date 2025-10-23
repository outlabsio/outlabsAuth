"""OAuth/Social Login package for OutlabsAuth."""

from .provider import OAuthProvider
from .models import (
    OAuthTokenResponse,
    OAuthUserInfo,
    OAuthAuthorizationURL,
    OAuthCallbackResult,
)
from .exceptions import (
    OAuthError,
    InvalidStateError,
    InvalidCodeError,
    ProviderError,
    AccountLinkError,
    ProviderNotConfiguredError,
    EmailNotVerifiedError,
    AccountAlreadyLinkedError,
    ProviderAlreadyLinkedError,
    CannotUnlinkLastMethodError,
    TokenRefreshError,
    InvalidNonceError,
    PKCEValidationError,
)
from .security import (
    generate_state,
    generate_nonce,
    generate_pkce_pair,
    verify_pkce,
    build_authorization_url,
    constant_time_compare,
)

__all__ = [
    # Base classes
    "OAuthProvider",
    
    # Data models
    "OAuthTokenResponse",
    "OAuthUserInfo",
    "OAuthAuthorizationURL",
    "OAuthCallbackResult",
    
    # Exceptions
    "OAuthError",
    "InvalidStateError",
    "InvalidCodeError",
    "ProviderError",
    "AccountLinkError",
    "ProviderNotConfiguredError",
    "EmailNotVerifiedError",
    "AccountAlreadyLinkedError",
    "ProviderAlreadyLinkedError",
    "CannotUnlinkLastMethodError",
    "TokenRefreshError",
    "InvalidNonceError",
    "PKCEValidationError",
    
    # Security utilities
    "generate_state",
    "generate_nonce",
    "generate_pkce_pair",
    "verify_pkce",
    "build_authorization_url",
    "constant_time_compare",
]
