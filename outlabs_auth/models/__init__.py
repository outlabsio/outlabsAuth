"""
OutlabsAuth Models

Public exports for all SQLModel/PostgreSQL models.
"""

# Re-export everything from sql submodule
from outlabs_auth.models.sql import (
    # Enums
    AuthChallengeType,
    UserStatus,
    MembershipStatus,
    EntityClass,
    APIKeyStatus,
    ConditionOperator,
    # Core
    AuthChallenge,
    User,
    Permission,
    PermissionTag,
    PermissionTagLink,
    PermissionCondition,
    PermissionDefinitionHistory,
    RefreshToken,
    RoleDefinitionHistory,
    UserAuditEvent,
    # SimpleRBAC
    Role,
    RolePermission,
    RoleCondition,
    RoleEntityTypePermission,
    ConditionGroup,
    UserRoleMembership,
    # EnterpriseRBAC
    Entity,
    EntityClosure,
    EntityMembership,
    EntityMembershipRole,
    # API Keys
    APIKey,
    APIKeyScope,
    APIKeyIPWhitelist,
    # OAuth
    SocialAccount,
    OAuthState,
    # Activity
    ActivityMetric,
    UserActivity,
    LoginHistory,
    # Model groups
    ALL_MODELS,
    CORE_MODELS,
    SIMPLE_RBAC_MODELS,
    ENTERPRISE_RBAC_MODELS,
    API_KEY_MODELS,
    OAUTH_MODELS,
    ACTIVITY_MODELS,
)

__all__ = [
    # Enums
    "AuthChallengeType",
    "UserStatus",
    "MembershipStatus",
    "EntityClass",
    "APIKeyStatus",
    "ConditionOperator",
    # Core
    "AuthChallenge",
    "User",
    "Permission",
    "PermissionTag",
    "PermissionTagLink",
    "PermissionCondition",
    "PermissionDefinitionHistory",
    "RefreshToken",
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
    # Model groups
    "ALL_MODELS",
    "CORE_MODELS",
    "SIMPLE_RBAC_MODELS",
    "ENTERPRISE_RBAC_MODELS",
    "API_KEY_MODELS",
    "OAUTH_MODELS",
    "ACTIVITY_MODELS",
]
