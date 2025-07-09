"""
Schema modules for request/response validation
"""
from .auth_schema import (
    LoginRequest,
    TokenResponse,
    RefreshTokenRequest,
    LogoutRequest,
    PasswordResetRequest,
    PasswordResetConfirm,
    EmailVerificationRequest,
    UserInfoResponse,
    ChangePasswordRequest,
    RegisterRequest
)
from .entity_schema import (
    EntityCreate,
    EntityUpdate,
    EntityResponse,
    EntityTreeResponse,
    EntityMemberAdd,
    EntityMemberUpdate,
    EntityMemberResponse,
    EntitySearchParams,
    EntityListResponse,
    EntityPermissionCheck,
    EntityPermissionResponse
)
from .role_schema import (
    RoleCreate,
    RoleUpdate,
    RoleResponse,
    RoleListResponse,
    RoleSearchParams,
    RoleAssignmentRequest,
    RoleAssignmentResponse,
    RolePermissionTemplate,
    RoleTemplateResponse,
    RoleUsageStats,
    RoleUsageStatsResponse
)

__all__ = [
    # Auth schemas
    "LoginRequest",
    "TokenResponse",
    "RefreshTokenRequest",
    "LogoutRequest",
    "PasswordResetRequest",
    "PasswordResetConfirm",
    "EmailVerificationRequest",
    "UserInfoResponse",
    "ChangePasswordRequest",
    "RegisterRequest",
    # Entity schemas
    "EntityCreate",
    "EntityUpdate",
    "EntityResponse",
    "EntityTreeResponse",
    "EntityMemberAdd",
    "EntityMemberUpdate",
    "EntityMemberResponse",
    "EntitySearchParams",
    "EntityListResponse",
    "EntityPermissionCheck",
    "EntityPermissionResponse",
    # Role schemas
    "RoleCreate",
    "RoleUpdate",
    "RoleResponse",
    "RoleListResponse",
    "RoleSearchParams",
    "RoleAssignmentRequest",
    "RoleAssignmentResponse",
    "RolePermissionTemplate",
    "RoleTemplateResponse",
    "RoleUsageStats",
    "RoleUsageStatsResponse"
]