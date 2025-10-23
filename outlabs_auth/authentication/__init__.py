"""
Authentication module for OutlabsAuth.

Implements the Transport/Strategy pattern from FastAPI-Users (DD-038).
"""

from outlabs_auth.authentication.backend import AuthBackend
from outlabs_auth.authentication.strategy import (
    Strategy,
    JWTStrategy,
    ApiKeyStrategy,
    ServiceTokenStrategy,
)
from outlabs_auth.authentication.transport import (
    Transport,
    BearerTransport,
    ApiKeyTransport,
    HeaderTransport,
)

__all__ = [
    # Core classes
    "AuthBackend",
    "Transport",
    "Strategy",
    # Transports
    "BearerTransport",
    "ApiKeyTransport",
    "HeaderTransport",
    # Strategies
    "JWTStrategy",
    "ApiKeyStrategy",
    "ServiceTokenStrategy",
]
