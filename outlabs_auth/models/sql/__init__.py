"""
OutlabsAuth SQL Models

SQLModel/SQLAlchemy models for PostgreSQL database.

This module exports all database models organized by feature:
- Core: User, Permission, RefreshToken
- SimpleRBAC: Role, UserRoleMembership
- EnterpriseRBAC: Entity, EntityClosure, EntityMembership
- API Keys: APIKey, APIKeyScope, APIKeyIPWhitelist
- OAuth: SocialAccount, OAuthState
- Activity: ActivityMetric, UserActivity, LoginHistory
"""

# === Enums ===
from .enums import (
    UserStatus,
    MembershipStatus,
    EntityClass,
    APIKeyStatus,
    ConditionOperator,
)

# === Core Models ===
from .user import User
from .permission import (
    Permission,
    PermissionTag,
    PermissionTagLink,
    PermissionCondition,
)
from .token import RefreshToken

# === SimpleRBAC Models ===
from .role import (
    Role,
    RolePermission,
    RoleCondition,
    RoleEntityTypePermission,
    ConditionGroup,
)
from .user_role_membership import UserRoleMembership

# === EnterpriseRBAC Models ===
from .entity import Entity
from .closure import EntityClosure
from .entity_membership import (
    EntityMembership,
    EntityMembershipRole,
)

# === API Key Models ===
from .api_key import (
    APIKey,
    APIKeyScope,
    APIKeyIPWhitelist,
)

# === OAuth Models ===
from .social_account import SocialAccount
from .oauth_state import OAuthState

# === Activity Models ===
from .activity_metric import (
    ActivityMetric,
    UserActivity,
    LoginHistory,
)

# === All Models (for Alembic) ===
__all__ = [
    # Enums
    "UserStatus",
    "MembershipStatus",
    "EntityClass",
    "APIKeyStatus",
    "ConditionOperator",
    # Core
    "User",
    "Permission",
    "PermissionTag",
    "PermissionTagLink",
    "PermissionCondition",
    "RefreshToken",
    # SimpleRBAC
    "Role",
    "RolePermission",
    "RoleCondition",
    "RoleEntityTypePermission",
    "ConditionGroup",
    "UserRoleMembership",
    # EnterpriseRBAC
    "Entity",
    "EntityClosure",
    "EntityMembership",
    "EntityMembershipRole",
    # API Keys
    "APIKey",
    "APIKeyScope",
    "APIKeyIPWhitelist",
    # OAuth
    "SocialAccount",
    "OAuthState",
    # Activity
    "ActivityMetric",
    "UserActivity",
    "LoginHistory",
]

# === Model Groups (for feature-based loading) ===
CORE_MODELS = [
    User,
    Permission,
    PermissionTag,
    PermissionTagLink,
    PermissionCondition,
    RefreshToken,
]

SIMPLE_RBAC_MODELS = [
    Role,
    RolePermission,
    RoleCondition,
    RoleEntityTypePermission,
    ConditionGroup,
    UserRoleMembership,
]

ENTERPRISE_RBAC_MODELS = [
    Entity,
    EntityClosure,
    EntityMembership,
    EntityMembershipRole,
]

API_KEY_MODELS = [
    APIKey,
    APIKeyScope,
    APIKeyIPWhitelist,
]

OAUTH_MODELS = [
    SocialAccount,
    OAuthState,
]

ACTIVITY_MODELS = [
    ActivityMetric,
    UserActivity,
    LoginHistory,
]

# All models for creating tables
ALL_MODELS = (
    CORE_MODELS +
    SIMPLE_RBAC_MODELS +
    ENTERPRISE_RBAC_MODELS +
    API_KEY_MODELS +
    OAUTH_MODELS +
    ACTIVITY_MODELS
)
