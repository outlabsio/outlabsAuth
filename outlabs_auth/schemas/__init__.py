"""
OutlabsAuth Schemas

Public exports for all Pydantic request/response schemas.
"""

# Common schemas
# API Key schemas
from outlabs_auth.schemas.api_key import (
    ApiKeyCreateRequest,
    ApiKeyCreateResponse,
    ApiKeyResponse,
    ApiKeyUpdateRequest,
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
    # API Key
    "ApiKeyResponse",
    "ApiKeyCreateRequest",
    "ApiKeyCreateResponse",
    "ApiKeyUpdateRequest",
    # OAuth
    "OAuthAuthorizeResponse",
    "OAuthCallbackError",
    "SocialAccountResponse",
]
