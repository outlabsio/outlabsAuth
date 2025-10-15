"""
Exception hierarchy for OutlabsAuth

Based on docs/ERROR_HANDLING.md
"""
from typing import Optional, Dict, Any


class OutlabsAuthException(Exception):
    """
    Base exception for all OutlabsAuth errors.

    All exceptions include:
    - error_code: Machine-readable error code
    - message: Human-readable error message
    - details: Optional additional context
    """

    error_code: str = "AUTH_ERROR"
    status_code: int = 500

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        if error_code:
            self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses"""
        return {
            "error": self.error_code,
            "message": self.message,
            "details": self.details
        }


# ============================================================================
# Authentication Exceptions
# ============================================================================


class AuthenticationError(OutlabsAuthException):
    """Base class for authentication errors"""
    error_code = "AUTHENTICATION_ERROR"
    status_code = 401


class InvalidCredentialsError(AuthenticationError):
    """Invalid username or password"""
    error_code = "INVALID_CREDENTIALS"


class TokenExpiredError(AuthenticationError):
    """JWT token has expired"""
    error_code = "TOKEN_EXPIRED"


class TokenInvalidError(AuthenticationError):
    """JWT token is invalid or malformed"""
    error_code = "TOKEN_INVALID"


class RefreshTokenInvalidError(AuthenticationError):
    """Refresh token is invalid or revoked"""
    error_code = "REFRESH_TOKEN_INVALID"


class APIKeyInvalidError(AuthenticationError):
    """API key is invalid or revoked"""
    error_code = "API_KEY_INVALID"


class APIKeyExpiredError(AuthenticationError):
    """API key has expired"""
    error_code = "API_KEY_EXPIRED"


class APIKeyLockedError(AuthenticationError):
    """API key is temporarily locked due to failures"""
    error_code = "API_KEY_LOCKED"


class AccountLockedError(AuthenticationError):
    """User account is locked due to failed login attempts"""
    error_code = "ACCOUNT_LOCKED"


class AccountInactiveError(AuthenticationError):
    """User account is inactive or suspended"""
    error_code = "ACCOUNT_INACTIVE"


# ============================================================================
# Authorization Exceptions
# ============================================================================


class AuthorizationError(OutlabsAuthException):
    """Base class for authorization errors"""
    error_code = "AUTHORIZATION_ERROR"
    status_code = 403


class PermissionDeniedError(AuthorizationError):
    """User does not have required permission"""
    error_code = "PERMISSION_DENIED"


class RoleNotFoundError(AuthorizationError):
    """Specified role does not exist"""
    error_code = "ROLE_NOT_FOUND"
    status_code = 404


class InsufficientPermissionsError(AuthorizationError):
    """User lacks required permissions for this operation"""
    error_code = "INSUFFICIENT_PERMISSIONS"


# ============================================================================
# Entity Exceptions (EnterpriseRBAC only)
# ============================================================================


class EntityError(OutlabsAuthException):
    """Base class for entity-related errors"""
    error_code = "ENTITY_ERROR"
    status_code = 400


class EntityNotFoundError(EntityError):
    """Entity does not exist"""
    error_code = "ENTITY_NOT_FOUND"
    status_code = 404


class CircularHierarchyError(EntityError):
    """Detected circular reference in entity hierarchy"""
    error_code = "CIRCULAR_HIERARCHY"


class InvalidParentEntityError(EntityError):
    """Parent entity is invalid or incompatible"""
    error_code = "INVALID_PARENT"


class MaxDepthExceededError(EntityError):
    """Entity hierarchy exceeds maximum depth"""
    error_code = "MAX_DEPTH_EXCEEDED"


class EntityTypeNotAllowedError(EntityError):
    """Entity type is not allowed in this context"""
    error_code = "ENTITY_TYPE_NOT_ALLOWED"


class InvalidEntityClassError(EntityError):
    """Invalid entity class (must be STRUCTURAL or ACCESS_GROUP)"""
    error_code = "INVALID_ENTITY_CLASS"


# ============================================================================
# Membership Exceptions (EnterpriseRBAC only)
# ============================================================================


class MembershipError(OutlabsAuthException):
    """Base class for membership-related errors"""
    error_code = "MEMBERSHIP_ERROR"
    status_code = 400


class MembershipNotFoundError(MembershipError):
    """Membership does not exist"""
    error_code = "MEMBERSHIP_NOT_FOUND"
    status_code = 404


class MembershipAlreadyExistsError(MembershipError):
    """User is already a member of this entity"""
    error_code = "MEMBERSHIP_ALREADY_EXISTS"
    status_code = 409


class MaxMembersExceededError(MembershipError):
    """Entity has reached maximum number of members"""
    error_code = "MAX_MEMBERS_EXCEEDED"


# ============================================================================
# User Exceptions
# ============================================================================


class UserError(OutlabsAuthException):
    """Base class for user-related errors"""
    error_code = "USER_ERROR"
    status_code = 400


class UserNotFoundError(UserError):
    """User does not exist"""
    error_code = "USER_NOT_FOUND"
    status_code = 404


class UserAlreadyExistsError(UserError):
    """User with this email already exists"""
    error_code = "USER_ALREADY_EXISTS"
    status_code = 409


class InvalidPasswordError(UserError):
    """Password does not meet requirements"""
    error_code = "INVALID_PASSWORD"


class EmailNotVerifiedError(UserError):
    """Email address has not been verified"""
    error_code = "EMAIL_NOT_VERIFIED"


# ============================================================================
# Validation Exceptions
# ============================================================================


class ValidationError(OutlabsAuthException):
    """Base class for validation errors"""
    error_code = "VALIDATION_ERROR"
    status_code = 422


class InvalidInputError(ValidationError):
    """Input data is invalid"""
    error_code = "INVALID_INPUT"


class MissingRequiredFieldError(ValidationError):
    """Required field is missing"""
    error_code = "MISSING_REQUIRED_FIELD"


# ============================================================================
# Rate Limiting Exceptions
# ============================================================================


class RateLimitError(OutlabsAuthException):
    """Rate limit exceeded"""
    error_code = "RATE_LIMIT_EXCEEDED"
    status_code = 429


# ============================================================================
# Configuration Exceptions
# ============================================================================


class ConfigurationError(OutlabsAuthException):
    """Invalid configuration"""
    error_code = "CONFIGURATION_ERROR"
    status_code = 500


class DatabaseError(OutlabsAuthException):
    """Database operation failed"""
    error_code = "DATABASE_ERROR"
    status_code = 500


class RedisError(OutlabsAuthException):
    """Redis operation failed"""
    error_code = "REDIS_ERROR"
    status_code = 500
