"""
OutlabsAuth Schemas

Public exports for all Pydantic request/response schemas.
"""

# Common schemas
# API Key schemas
from outlabs_auth.schemas.api_key import (
    ApiKeyCreateRequest,
    ApiKeyCreateResponse,
    ApiKeyGrantableScopesResponse,
    ApiKeyResponse,
    ApiKeyUpdateRequest,
    SystemIntegrationApiKeyCreateRequest,
    SystemIntegrationApiKeyUpdateRequest,
)

# Auth schemas
from outlabs_auth.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    RefreshRequest,
    RefreshResponse,
    RegisterRequest,
    ResetPasswordRequest,
)
from outlabs_auth.schemas.common import PaginatedResponse

# Entity schemas (EnterpriseRBAC)
from outlabs_auth.schemas.entity import (
    EntityCreateRequest,
    EntityResponse,
    EntityUpdateRequest,
)

# EntityMembership schemas (EnterpriseRBAC)
from outlabs_auth.schemas.membership import (
    EntityMemberResponse,
    MembershipCreateRequest,
    MembershipResponse,
    MembershipUpdateRequest,
)
from outlabs_auth.schemas.membership_history import (
    MembershipHistoryEventResponse,
    OrphanedUserResponse,
)
from outlabs_auth.schemas.integration_principal import (
    IntegrationPrincipalCreateRequest,
    IntegrationPrincipalResponse,
    IntegrationPrincipalUpdateRequest,
)

# OAuth schemas
from outlabs_auth.schemas.oauth import (
    OAuthAuthorizeResponse,
    OAuthCallbackError,
    SocialAccountResponse,
)

# Permission schemas
from outlabs_auth.schemas.permission import (
    PermissionCheckRequest,
    PermissionCheckResponse,
)

# Role schemas
from outlabs_auth.schemas.role import (
    RoleCreateRequest,
    RoleResponse,
    RoleScopeEnum,
    RoleSummary,
    RoleUpdateRequest,
)

# User schemas
from outlabs_auth.schemas.user import (
    ChangePasswordRequest,
    UserCreateRequest,
    UserResponse,
    UserUpdateRequest,
)
from outlabs_auth.schemas.user_audit import UserAuditEventResponse

# UserRoleMembership schemas (SimpleRBAC)
from outlabs_auth.schemas.user_role_membership import (
    AssignRoleRequest,
    RevokeRoleRequest,
    UserRoleMembershipCreate,
    UserRoleMembershipDetailResponse,
    UserRoleMembershipResponse,
    UserRoleMembershipUpdate,
)

__all__ = [
    # Common
    "PaginatedResponse",
    # Auth
    "LoginRequest",
    "LoginResponse",
    "RegisterRequest",
    "RefreshRequest",
    "RefreshResponse",
    "ForgotPasswordRequest",
    "ResetPasswordRequest",
    "LogoutRequest",
    # User
    "UserResponse",
    "UserCreateRequest",
    "UserUpdateRequest",
    "ChangePasswordRequest",
    "UserAuditEventResponse",
    # Role
    "RoleResponse",
    "RoleCreateRequest",
    "RoleUpdateRequest",
    # Permission
    "PermissionCheckRequest",
    "PermissionCheckResponse",
    # UserRoleMembership
    "UserRoleMembershipResponse",
    "UserRoleMembershipDetailResponse",
    "UserRoleMembershipCreate",
    "UserRoleMembershipUpdate",
    "AssignRoleRequest",
    "RevokeRoleRequest",
    # Entity
    "EntityResponse",
    "EntityCreateRequest",
    "EntityUpdateRequest",
    # EntityMembership
    "MembershipResponse",
    "MembershipCreateRequest",
    "MembershipUpdateRequest",
    "MembershipHistoryEventResponse",
    "OrphanedUserResponse",
    # Integration Principals
    "IntegrationPrincipalResponse",
    "IntegrationPrincipalCreateRequest",
    "IntegrationPrincipalUpdateRequest",
    # API Key
    "ApiKeyResponse",
    "ApiKeyCreateRequest",
    "ApiKeyCreateResponse",
    "ApiKeyUpdateRequest",
    "ApiKeyGrantableScopesResponse",
    "SystemIntegrationApiKeyCreateRequest",
    "SystemIntegrationApiKeyUpdateRequest",
    # OAuth
    "OAuthAuthorizeResponse",
    "OAuthCallbackError",
    "SocialAccountResponse",
]
