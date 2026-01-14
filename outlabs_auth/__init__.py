"""
OutlabsAuth - FastAPI authentication and authorization library

A comprehensive auth library with hierarchical RBAC, tree permissions,
and multi-source authentication (JWT, API keys, service tokens).

PostgreSQL backend with SQLModel/SQLAlchemy.

Quick Start:
    >>> from outlabs_auth import OutlabsAuth
    >>> auth = OutlabsAuth(database_url="postgresql+asyncpg://...", secret_key="your-secret-key")
    >>> await auth.initialize()
"""

__version__ = "2.0.0"
__author__ = "Outlabs"
__license__ = "MIT"

# Database infrastructure
from outlabs_auth.database import (
    DatabaseConfig,
    create_engine,
    create_session_factory,
    DatabasePresets,
    BaseModel,
    ModelRegistry,
)

# SQL Models - Enums
from outlabs_auth.models.sql.enums import (
    UserStatus,
    MembershipStatus,
    EntityClass,
    APIKeyStatus,
    ConditionOperator,
)

# SQL Models - Core
from outlabs_auth.models.sql.user import User
from outlabs_auth.models.sql.permission import (
    Permission,
    PermissionTag,
    PermissionTagLink,
    PermissionCondition,
)
from outlabs_auth.models.sql.token import RefreshToken
from outlabs_auth.models.sql.role import (
    Role,
    RolePermission,
    RoleCondition,
    RoleEntityTypePermission,
    ConditionGroup,
)
from outlabs_auth.models.sql.user_role_membership import UserRoleMembership

# SQL Models - EnterpriseRBAC
from outlabs_auth.models.sql.entity import Entity
from outlabs_auth.models.sql.closure import EntityClosure
from outlabs_auth.models.sql.entity_membership import (
    EntityMembership,
    EntityMembershipRole,
)

# SQL Models - API Keys
from outlabs_auth.models.sql.api_key import (
    APIKey,
    APIKeyScope,
    APIKeyIPWhitelist,
)

# SQL Models - OAuth
from outlabs_auth.models.sql.social_account import SocialAccount
from outlabs_auth.models.sql.oauth_state import OAuthState

# SQL Models - Activity
from outlabs_auth.models.sql.activity_metric import (
    ActivityMetric,
    UserActivity,
    LoginHistory,
)

# Model groups for convenience
from outlabs_auth.models.sql import (
    ALL_MODELS,
    CORE_MODELS,
    SIMPLE_RBAC_MODELS,
    ENTERPRISE_RBAC_MODELS,
    API_KEY_MODELS,
    OAUTH_MODELS,
    ACTIVITY_MODELS,
)

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

__all__ = [
    # Version
    "__version__",

    # Database
    "DatabaseConfig",
    "create_engine",
    "create_session_factory",
    "DatabasePresets",
    "BaseModel",
    "ModelRegistry",

    # Enums
    "UserStatus",
    "MembershipStatus",
    "EntityClass",
    "APIKeyStatus",
    "ConditionOperator",

    # Core Models
    "User",
    "Permission",
    "PermissionTag",
    "PermissionTagLink",
    "PermissionCondition",
    "RefreshToken",
    "Role",
    "RolePermission",
    "RoleCondition",
    "RoleEntityTypePermission",
    "ConditionGroup",
    "UserRoleMembership",

    # EnterpriseRBAC Models
    "Entity",
    "EntityClosure",
    "EntityMembership",
    "EntityMembershipRole",

    # API Key Models
    "APIKey",
    "APIKeyScope",
    "APIKeyIPWhitelist",

    # OAuth Models
    "SocialAccount",
    "OAuthState",

    # Activity Models
    "ActivityMetric",
    "UserActivity",
    "LoginHistory",

    # Model Groups
    "ALL_MODELS",
    "CORE_MODELS",
    "SIMPLE_RBAC_MODELS",
    "ENTERPRISE_RBAC_MODELS",
    "API_KEY_MODELS",
    "OAUTH_MODELS",
    "ACTIVITY_MODELS",

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
]
