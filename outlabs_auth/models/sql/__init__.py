"""
OutlabsAuth SQL Models

SQLModel/SQLAlchemy models for PostgreSQL database.

This module exports all database models organized by feature:
- Core: User, Permission, RefreshToken
- Audit: UserAuditEvent
- SimpleRBAC: Role, UserRoleMembership
- EnterpriseRBAC: Entity, EntityClosure, EntityMembership
- API Keys: APIKey, APIKeyScope, APIKeyIPWhitelist
- OAuth: SocialAccount, OAuthState
- Activity: ActivityMetric, UserActivity, LoginHistory
- System Configuration: SystemConfig
"""

# === Enums ===
# === Activity Models ===
from .activity_metric import (
    ActivityMetric,
    LoginHistory,
    UserActivity,
)
from .auth_challenge import AuthChallenge

# === API Key Models ===
from .api_key import (
    APIKey,
    APIKeyIPWhitelist,
    APIKeyScope,
)
from .closure import EntityClosure

# === EnterpriseRBAC Models ===
from .entity import Entity
from .entity_membership import (
    EntityMembership,
    EntityMembershipRole,
)
from .entity_membership_history import EntityMembershipHistory
from .integration_principal import (
    IntegrationPrincipal,
    IntegrationPrincipalRole,
)
from .enums import (
    AuthChallengeType,
    APIKeyKind,
    APIKeyStatus,
    ConditionOperator,
    EntityClass,
    IntegrationPrincipalScopeKind,
    IntegrationPrincipalStatus,
    MembershipStatus,
    UserStatus,
)
from .oauth_state import OAuthState
from .permission import (
    Permission,
    PermissionCondition,
    PermissionTag,
    PermissionTagLink,
)
from .permission_definition_history import PermissionDefinitionHistory

# === SimpleRBAC Models ===
from .role import (
    ConditionGroup,
    Role,
    RoleCondition,
    RoleEntityTypePermission,
    RolePermission,
)

# === OAuth Models ===
from .social_account import SocialAccount

# === System Configuration ===
from .system_config import (
    DEFAULT_ENTITY_TYPE_CONFIG,
    ConfigKeys,
    SystemConfig,
)
from .token import RefreshToken

# === Core Models ===
from .role_definition_history import RoleDefinitionHistory
from .user_audit_event import UserAuditEvent
from .user import User
from .user_role_membership import UserRoleMembership

# === All Models (for Alembic) ===
__all__ = [
    # Enums
    "UserStatus",
    "AuthChallengeType",
    "MembershipStatus",
    "EntityClass",
    "APIKeyKind",
    "APIKeyStatus",
    "IntegrationPrincipalStatus",
    "IntegrationPrincipalScopeKind",
    "ConditionOperator",
    # Core
    "User",
    "Permission",
    "PermissionTag",
    "PermissionTagLink",
    "PermissionCondition",
    "PermissionDefinitionHistory",
    "RefreshToken",
    "AuthChallenge",
    "RoleDefinitionHistory",
    "UserAuditEvent",
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
    "EntityMembershipHistory",
    "IntegrationPrincipal",
    "IntegrationPrincipalRole",
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
    # System Configuration
    "SystemConfig",
    "ConfigKeys",
    "DEFAULT_ENTITY_TYPE_CONFIG",
]

# === Model Groups (for feature-based loading) ===
CORE_MODELS = [
    User,
    Permission,
    PermissionTag,
    PermissionTagLink,
    PermissionCondition,
    PermissionDefinitionHistory,
    RefreshToken,
    RoleDefinitionHistory,
    UserAuditEvent,
]

AUTH_CHALLENGE_MODELS = [
    AuthChallenge,
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
    EntityMembershipHistory,
]

API_KEY_MODELS = [
    IntegrationPrincipal,
    IntegrationPrincipalRole,
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

SYSTEM_CONFIG_MODELS = [
    SystemConfig,
]

# All models for creating tables
ALL_MODELS = (
    CORE_MODELS
    + SIMPLE_RBAC_MODELS
    + ENTERPRISE_RBAC_MODELS
    + API_KEY_MODELS
    + OAUTH_MODELS
    + AUTH_CHALLENGE_MODELS
    + ACTIVITY_MODELS
    + SYSTEM_CONFIG_MODELS
)
