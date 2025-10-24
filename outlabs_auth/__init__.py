"""
OutlabsAuth - FastAPI authentication and authorization library

A comprehensive auth library with hierarchical RBAC, tree permissions,
and multi-source authentication (JWT, API keys, service tokens).

Quick Start:
    >>> from outlabs_auth import OutlabsAuth
    >>> auth = OutlabsAuth(database=mongo_db, secret_key="your-secret-key")
    >>> await auth.initialize()
"""

__version__ = "1.0.0"
__author__ = "Outlabs"
__license__ = "MIT"

# Core authentication class
from outlabs_auth.core.auth import OutlabsAuth

# Preset wrappers
from outlabs_auth.presets.simple import SimpleRBAC
from outlabs_auth.presets.enterprise import EnterpriseRBAC

# Configuration classes
from outlabs_auth.core.config import AuthConfig, SimpleConfig, EnterpriseConfig

# Exception classes
from outlabs_auth.core.exceptions import (
    OutlabsAuthException,
    AuthenticationError,
    AuthorizationError,
    InvalidCredentialsError,
    TokenExpiredError,
    TokenInvalidError,
    PermissionDeniedError,
    UserNotFoundError,
    ConfigurationError,
)

# Models
from outlabs_auth.models.user import UserModel, UserStatus
from outlabs_auth.models.role import RoleModel
from outlabs_auth.models.permission import PermissionModel, Condition
from outlabs_auth.models.token import RefreshTokenModel

# Dependencies
from outlabs_auth.dependencies.auth import AuthDeps

__all__ = [
    # Version
    "__version__",

    # Core
    "OutlabsAuth",

    # Presets
    "SimpleRBAC",
    "EnterpriseRBAC",

    # Configuration
    "AuthConfig",
    "SimpleConfig",
    "EnterpriseConfig",

    # Exceptions
    "OutlabsAuthException",
    "AuthenticationError",
    "AuthorizationError",
    "InvalidCredentialsError",
    "TokenExpiredError",
    "TokenInvalidError",
    "PermissionDeniedError",
    "UserNotFoundError",
    "ConfigurationError",

    # Models
    "UserModel",
    "UserStatus",
    "RoleModel",
    "PermissionModel",
    "Condition",
    "RefreshTokenModel",

    # Dependencies
    "AuthDeps",
]
