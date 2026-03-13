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

__author__ = "Outlabs"
__license__ = "Proprietary"

from outlabs_auth._version import __release_stage__, __version__
from outlabs_auth.bootstrap import (
    BootstrapAdminResult,
    PermissionSeed,
    SeedSystemResult,
    bootstrap_superuser,
    get_system_permission_catalog,
    seed_system_records,
)

# Database infrastructure
# Core Auth Classes
from outlabs_auth.core.auth import OutlabsAuth
from outlabs_auth.core.config import AuthConfig

# Exception classes
from outlabs_auth.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConfigurationError,
    InvalidCredentialsError,
    OutlabsAuthException,
    PermissionDeniedError,
    TokenExpiredError,
    TokenInvalidError,
    UserNotFoundError,
)
from outlabs_auth.database import (
    BaseModel,
    DatabaseConfig,
    DatabasePresets,
    ModelRegistry,
    create_engine,
    create_session_factory,
)
from outlabs_auth.fastapi import register_exception_handlers

# Model groups for convenience
from outlabs_auth.models.sql import (
    ACTIVITY_MODELS,
    ALL_MODELS,
    API_KEY_MODELS,
    CORE_MODELS,
    ENTERPRISE_RBAC_MODELS,
    OAUTH_MODELS,
    SIMPLE_RBAC_MODELS,
)

# SQL Models - Activity
from outlabs_auth.models.sql.activity_metric import (
    ActivityMetric,
    LoginHistory,
    UserActivity,
)

# SQL Models - API Keys
from outlabs_auth.models.sql.api_key import (
    APIKey,
    APIKeyIPWhitelist,
    APIKeyScope,
)
from outlabs_auth.models.sql.closure import EntityClosure

# SQL Models - EnterpriseRBAC
from outlabs_auth.models.sql.entity import Entity
from outlabs_auth.models.sql.entity_membership import (
    EntityMembership,
    EntityMembershipRole,
)

# SQL Models - Enums
from outlabs_auth.models.sql.enums import (
    APIKeyStatus,
    ConditionOperator,
    EntityClass,
    MembershipStatus,
    UserStatus,
)
from outlabs_auth.models.sql.oauth_state import OAuthState
from outlabs_auth.models.sql.permission import (
    Permission,
    PermissionCondition,
    PermissionTag,
    PermissionTagLink,
)
from outlabs_auth.models.sql.role import (
    ConditionGroup,
    Role,
    RoleCondition,
    RoleEntityTypePermission,
    RolePermission,
)

# SQL Models - OAuth
from outlabs_auth.models.sql.social_account import SocialAccount
from outlabs_auth.models.sql.token import RefreshToken

# SQL Models - Core
from outlabs_auth.models.sql.user import User
from outlabs_auth.models.sql.user_role_membership import UserRoleMembership

# Presets
from outlabs_auth.presets import EnterpriseRBAC, SimpleRBAC

# Services
from outlabs_auth.services import (
    AuthService,
    BaseService,
    PermissionService,
    RoleService,
    TokenPair,
    UserService,
)

__all__ = [
    # Version
    "__release_stage__",
    "__version__",
    "PermissionSeed",
    "SeedSystemResult",
    "BootstrapAdminResult",
    "get_system_permission_catalog",
    "seed_system_records",
    "bootstrap_superuser",

    # Core Auth Classes
    "OutlabsAuth",
    "AuthConfig",
    "register_exception_handlers",
    # Presets
    "SimpleRBAC",
    "EnterpriseRBAC",
    # Services
    "BaseService",
    "UserService",
    "RoleService",
    "PermissionService",
    "AuthService",
    "TokenPair",
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
