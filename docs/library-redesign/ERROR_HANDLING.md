# OutlabsAuth Error Handling Guide

**Version**: 1.0
**Date**: 2025-01-14
**Audience**: Developers integrating OutlabsAuth
**Status**: Production Reference

---

## Table of Contents

1. [Error Handling Philosophy](#error-handling-philosophy)
2. [Exception Hierarchy](#exception-hierarchy)
3. [Error Codes](#error-codes)
4. [Common Exceptions](#common-exceptions)
5. [Error Handling Patterns](#error-handling-patterns)
6. [API Error Responses](#api-error-responses)
7. [Logging Errors](#logging-errors)
8. [User-Friendly Messages](#user-friendly-messages)
9. [Debugging Errors](#debugging-errors)
10. [Production Error Handling](#production-error-handling)

---

## Error Handling Philosophy

### Core Principles

1. **Fail Fast**: Detect errors early and raise exceptions immediately
2. **Specific Exceptions**: Use specific exception types, not generic `Exception`
3. **Informative Messages**: Error messages should help developers debug
4. **Security Conscious**: Don't leak sensitive information in errors
5. **Consistent Format**: All errors follow the same response structure

### Error Categories

- **Authentication Errors**: Login, token validation, sessions
- **Authorization Errors**: Permission checks, access control
- **Validation Errors**: Input validation, data constraints
- **Not Found Errors**: Resource not found
- **Conflict Errors**: Duplicate resources, constraint violations
- **System Errors**: Database errors, service unavailable

---

## Exception Hierarchy

### Base Exception

```python
# outlabs_auth/exceptions.py

class OutlabsAuthException(Exception):
    """Base exception for all OutlabsAuth errors"""

    def __init__(
        self,
        message: str,
        error_code: str,
        status_code: int = 500,
        details: Optional[dict] = None
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict:
        """Convert exception to dictionary for API response"""
        return {
            "error": {
                "message": self.message,
                "code": self.error_code,
                "details": self.details
            }
        }
```

### Exception Hierarchy

```
OutlabsAuthException
├── AuthenticationException (401)
│   ├── InvalidCredentialsException
│   ├── TokenExpiredException
│   ├── InvalidTokenException
│   ├── UserInactiveException
│   └── AccountLockedException
│
├── AuthorizationException (403)
│   ├── PermissionDeniedException
│   ├── InsufficientPermissionsException
│   └── EntityAccessDeniedException
│
├── ValidationException (400)
│   ├── InvalidEmailException
│   ├── WeakPasswordException
│   ├── InvalidEntityTypeException
│   └── InvalidPermissionFormatException
│
├── NotFoundException (404)
│   ├── UserNotFoundException
│   ├── RoleNotFoundException
│   ├── EntityNotFoundException
│   └── PermissionNotFoundException
│
├── ConflictException (409)
│   ├── UserAlreadyExistsException
│   ├── RoleAlreadyExistsException
│   ├── EntityAlreadyExistsException
│   └── DuplicateSlugException
│
└── SystemException (500)
    ├── DatabaseException
    ├── CacheException
    └── ServiceUnavailableException
```

---

## Error Codes

### Error Code Format

```
<CATEGORY>_<SPECIFIC_ERROR>

Examples:
- AUTH_INVALID_CREDENTIALS
- AUTH_TOKEN_EXPIRED
- AUTHZ_PERMISSION_DENIED
- VAL_WEAK_PASSWORD
- NOT_FOUND_USER
- CONFLICT_USER_EXISTS
```

### Complete Error Code List

#### Authentication (AUTH_*)

| Code | HTTP | Description |
|------|------|-------------|
| `AUTH_INVALID_CREDENTIALS` | 401 | Invalid email or password |
| `AUTH_TOKEN_EXPIRED` | 401 | Access token has expired |
| `AUTH_TOKEN_INVALID` | 401 | Token is malformed or invalid |
| `AUTH_USER_INACTIVE` | 401 | User account is deactivated |
| `AUTH_ACCOUNT_LOCKED` | 401 | Account locked due to failed attempts |
| `AUTH_REFRESH_TOKEN_INVALID` | 401 | Refresh token is invalid or revoked |

#### Authorization (AUTHZ_*)

| Code | HTTP | Description |
|------|------|-------------|
| `AUTHZ_PERMISSION_DENIED` | 403 | User lacks required permission |
| `AUTHZ_INSUFFICIENT_PERMISSIONS` | 403 | Insufficient permissions for action |
| `AUTHZ_ENTITY_ACCESS_DENIED` | 403 | Access denied to entity |
| `AUTHZ_ROLE_REQUIRED` | 403 | Specific role required |

#### Validation (VAL_*)

| Code | HTTP | Description |
|------|------|-------------|
| `VAL_INVALID_EMAIL` | 400 | Email format is invalid |
| `VAL_WEAK_PASSWORD` | 400 | Password doesn't meet requirements |
| `VAL_INVALID_ENTITY_TYPE` | 400 | Entity type is invalid |
| `VAL_INVALID_PERMISSION` | 400 | Permission format is invalid |
| `VAL_MISSING_REQUIRED_FIELD` | 400 | Required field is missing |
| `VAL_INVALID_FIELD_VALUE` | 400 | Field value is invalid |

#### Not Found (NOT_FOUND_*)

| Code | HTTP | Description |
|------|------|-------------|
| `NOT_FOUND_USER` | 404 | User not found |
| `NOT_FOUND_ROLE` | 404 | Role not found |
| `NOT_FOUND_ENTITY` | 404 | Entity not found |
| `NOT_FOUND_PERMISSION` | 404 | Permission not found |

#### Conflict (CONFLICT_*)

| Code | HTTP | Description |
|------|------|-------------|
| `CONFLICT_USER_EXISTS` | 409 | User with email already exists |
| `CONFLICT_ROLE_EXISTS` | 409 | Role with name already exists |
| `CONFLICT_ENTITY_EXISTS` | 409 | Entity with slug already exists |
| `CONFLICT_DUPLICATE_SLUG` | 409 | Slug must be unique |

#### System (SYS_*)

| Code | HTTP | Description |
|------|------|-------------|
| `SYS_DATABASE_ERROR` | 500 | Database operation failed |
| `SYS_CACHE_ERROR` | 500 | Cache operation failed |
| `SYS_SERVICE_UNAVAILABLE` | 503 | Service temporarily unavailable |

---

## Common Exceptions

### Authentication Exceptions

```python
# outlabs_auth/exceptions.py

class AuthenticationException(OutlabsAuthException):
    """Base class for authentication errors"""
    def __init__(self, message: str, error_code: str, details: Optional[dict] = None):
        super().__init__(message, error_code, status_code=401, details=details)


class InvalidCredentialsException(AuthenticationException):
    """Raised when login credentials are invalid"""
    def __init__(self, details: Optional[dict] = None):
        super().__init__(
            message="Invalid email or password",
            error_code="AUTH_INVALID_CREDENTIALS",
            details=details
        )


class TokenExpiredException(AuthenticationException):
    """Raised when access token has expired"""
    def __init__(self, details: Optional[dict] = None):
        super().__init__(
            message="Access token has expired",
            error_code="AUTH_TOKEN_EXPIRED",
            details=details
        )


class InvalidTokenException(AuthenticationException):
    """Raised when token is malformed or invalid"""
    def __init__(self, details: Optional[dict] = None):
        super().__init__(
            message="Invalid token",
            error_code="AUTH_TOKEN_INVALID",
            details=details
        )


class UserInactiveException(AuthenticationException):
    """Raised when user account is deactivated"""
    def __init__(self, user_id: str, details: Optional[dict] = None):
        super().__init__(
            message="User account is inactive",
            error_code="AUTH_USER_INACTIVE",
            details={"user_id": user_id, **(details or {})}
        )
```

### Authorization Exceptions

```python
class AuthorizationException(OutlabsAuthException):
    """Base class for authorization errors"""
    def __init__(self, message: str, error_code: str, details: Optional[dict] = None):
        super().__init__(message, error_code, status_code=403, details=details)


class PermissionDeniedException(AuthorizationException):
    """Raised when user lacks required permission"""
    def __init__(
        self,
        permission: str,
        user_id: str,
        entity_id: Optional[str] = None,
        details: Optional[dict] = None
    ):
        super().__init__(
            message=f"Permission denied: {permission}",
            error_code="AUTHZ_PERMISSION_DENIED",
            details={
                "permission": permission,
                "user_id": user_id,
                "entity_id": entity_id,
                **(details or {})
            }
        )


class EntityAccessDeniedException(AuthorizationException):
    """Raised when access to entity is denied"""
    def __init__(
        self,
        entity_id: str,
        user_id: str,
        details: Optional[dict] = None
    ):
        super().__init__(
            message=f"Access denied to entity",
            error_code="AUTHZ_ENTITY_ACCESS_DENIED",
            details={
                "entity_id": entity_id,
                "user_id": user_id,
                **(details or {})
            }
        )
```

### Validation Exceptions

```python
class ValidationException(OutlabsAuthException):
    """Base class for validation errors"""
    def __init__(self, message: str, error_code: str, details: Optional[dict] = None):
        super().__init__(message, error_code, status_code=400, details=details)


class WeakPasswordException(ValidationException):
    """Raised when password doesn't meet requirements"""
    def __init__(self, requirements: list[str], details: Optional[dict] = None):
        super().__init__(
            message="Password does not meet security requirements",
            error_code="VAL_WEAK_PASSWORD",
            details={
                "requirements": requirements,
                **(details or {})
            }
        )


class InvalidEmailException(ValidationException):
    """Raised when email format is invalid"""
    def __init__(self, email: str, details: Optional[dict] = None):
        super().__init__(
            message=f"Invalid email format: {email}",
            error_code="VAL_INVALID_EMAIL",
            details={"email": email, **(details or {})}
        )
```

### Not Found Exceptions

```python
class NotFoundException(OutlabsAuthException):
    """Base class for not found errors"""
    def __init__(self, message: str, error_code: str, details: Optional[dict] = None):
        super().__init__(message, error_code, status_code=404, details=details)


class UserNotFoundException(NotFoundException):
    """Raised when user is not found"""
    def __init__(self, user_id: Optional[str] = None, email: Optional[str] = None):
        identifier = user_id or email or "unknown"
        super().__init__(
            message=f"User not found: {identifier}",
            error_code="NOT_FOUND_USER",
            details={"user_id": user_id, "email": email}
        )


class RoleNotFoundException(NotFoundException):
    """Raised when role is not found"""
    def __init__(self, role_id: str):
        super().__init__(
            message=f"Role not found: {role_id}",
            error_code="NOT_FOUND_ROLE",
            details={"role_id": role_id}
        )
```

### Conflict Exceptions

```python
class ConflictException(OutlabsAuthException):
    """Base class for conflict errors"""
    def __init__(self, message: str, error_code: str, details: Optional[dict] = None):
        super().__init__(message, error_code, status_code=409, details=details)


class UserAlreadyExistsException(ConflictException):
    """Raised when user with email already exists"""
    def __init__(self, email: str):
        super().__init__(
            message=f"User already exists with email: {email}",
            error_code="CONFLICT_USER_EXISTS",
            details={"email": email}
        )


class RoleAlreadyExistsException(ConflictException):
    """Raised when role with name already exists"""
    def __init__(self, name: str):
        super().__init__(
            message=f"Role already exists with name: {name}",
            error_code="CONFLICT_ROLE_EXISTS",
            details={"name": name}
        )
```

---

## Error Handling Patterns

### Pattern 1: Try-Except with Specific Exceptions

```python
from outlabs_auth.exceptions import (
    UserNotFoundException,
    PermissionDeniedException
)

async def update_user_role(user_id: str, role_id: str):
    """Update user role with proper error handling"""
    try:
        # Validate user exists
        user = await auth.user_service.get_user(user_id)
        if not user:
            raise UserNotFoundException(user_id=user_id)

        # Check permission
        has_perm, _ = await auth.permission_service.check_permission(
            user_id=current_user.id,
            permission="role:assign"
        )
        if not has_perm:
            raise PermissionDeniedException(
                permission="role:assign",
                user_id=current_user.id
            )

        # Update role
        await auth.role_service.assign_role(user_id, role_id)

        return {"status": "success", "user_id": user_id, "role_id": role_id}

    except UserNotFoundException as e:
        # Log error
        logger.warning(f"User not found: {user_id}")
        # Re-raise for FastAPI to handle
        raise

    except PermissionDeniedException as e:
        # Log security event
        logger.warning(f"Permission denied: {e.details}")
        raise

    except Exception as e:
        # Catch unexpected errors
        logger.error(f"Unexpected error updating user role: {str(e)}")
        raise SystemException(
            message="An unexpected error occurred",
            error_code="SYS_INTERNAL_ERROR"
        )
```

### Pattern 2: FastAPI Exception Handler

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from outlabs_auth.exceptions import OutlabsAuthException

app = FastAPI()

@app.exception_handler(OutlabsAuthException)
async def outlabs_auth_exception_handler(
    request: Request,
    exc: OutlabsAuthException
):
    """Handle all OutlabsAuth exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict()
    )

# Example endpoint
@app.post("/users")
async def create_user(user_data: CreateUserRequest):
    try:
        user = await auth.user_service.create_user(
            email=user_data.email,
            password=user_data.password,
            name=user_data.name
        )
        return user
    except UserAlreadyExistsException:
        # FastAPI automatically uses exception handler
        raise
```

### Pattern 3: Validation with Custom Errors

```python
from pydantic import BaseModel, validator
from outlabs_auth.exceptions import WeakPasswordException

class CreateUserRequest(BaseModel):
    email: str
    password: str
    name: str

    @validator('password')
    def validate_password(cls, password: str):
        """Validate password strength"""
        errors = []

        if len(password) < 12:
            errors.append("Password must be at least 12 characters")

        if not any(c.isupper() for c in password):
            errors.append("Password must contain uppercase letter")

        if not any(c.islower() for c in password):
            errors.append("Password must contain lowercase letter")

        if not any(c.isdigit() for c in password):
            errors.append("Password must contain number")

        if not any(c in "!@#$%^&*" for c in password):
            errors.append("Password must contain special character")

        if errors:
            raise WeakPasswordException(requirements=errors)

        return password
```

### Pattern 4: Context Manager for Error Handling

```python
from contextlib import asynccontextmanager
from outlabs_auth.exceptions import DatabaseException

@asynccontextmanager
async def database_transaction():
    """Context manager for database transactions with error handling"""
    session = await create_session()
    try:
        yield session
        await session.commit()
    except Exception as e:
        await session.rollback()
        logger.error(f"Database transaction failed: {str(e)}")
        raise DatabaseException(
            message="Database transaction failed",
            error_code="SYS_DATABASE_ERROR",
            details={"error": str(e)}
        )
    finally:
        await session.close()

# Usage
async def create_user_with_role(email: str, password: str, role_id: str):
    async with database_transaction() as session:
        user = await create_user(session, email, password)
        await assign_role(session, user.id, role_id)
        return user
```

---

## API Error Responses

### Standard Error Response Format

```json
{
  "error": {
    "message": "User not found",
    "code": "NOT_FOUND_USER",
    "details": {
      "user_id": "12345"
    }
  }
}
```

### Error Response Examples

**401 Unauthorized** (Invalid Credentials):
```json
{
  "error": {
    "message": "Invalid email or password",
    "code": "AUTH_INVALID_CREDENTIALS",
    "details": {}
  }
}
```

**403 Forbidden** (Permission Denied):
```json
{
  "error": {
    "message": "Permission denied: user:delete",
    "code": "AUTHZ_PERMISSION_DENIED",
    "details": {
      "permission": "user:delete",
      "user_id": "abc123",
      "entity_id": null
    }
  }
}
```

**404 Not Found**:
```json
{
  "error": {
    "message": "User not found: user@example.com",
    "code": "NOT_FOUND_USER",
    "details": {
      "user_id": null,
      "email": "user@example.com"
    }
  }
}
```

**409 Conflict**:
```json
{
  "error": {
    "message": "User already exists with email: user@example.com",
    "code": "CONFLICT_USER_EXISTS",
    "details": {
      "email": "user@example.com"
    }
  }
}
```

**500 Internal Server Error**:
```json
{
  "error": {
    "message": "Database operation failed",
    "code": "SYS_DATABASE_ERROR",
    "details": {
      "error": "Connection timeout"
    }
  }
}
```

---

## Logging Errors

### Structured Error Logging

```python
import logging
import json
from datetime import datetime

class ErrorLogger:
    """Structured error logging"""

    def __init__(self, logger_name: str = "outlabs_auth"):
        self.logger = logging.getLogger(logger_name)

    def log_error(
        self,
        exception: OutlabsAuthException,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
        **kwargs
    ):
        """Log error with structured data"""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "error_code": exception.error_code,
            "error_message": exception.message,
            "status_code": exception.status_code,
            "details": exception.details,
            "user_id": user_id,
            "request_id": request_id,
            **kwargs
        }

        # Log at appropriate level
        if exception.status_code >= 500:
            self.logger.error(json.dumps(log_data))
        elif exception.status_code >= 400:
            self.logger.warning(json.dumps(log_data))
        else:
            self.logger.info(json.dumps(log_data))

# Usage
error_logger = ErrorLogger()

try:
    user = await auth.user_service.get_user(user_id)
except UserNotFoundException as e:
    error_logger.log_error(
        exception=e,
        user_id=current_user.id,
        request_id=request.headers.get("X-Request-ID"),
        action="get_user",
        endpoint="/users/{user_id}"
    )
    raise
```

### Log Levels for Different Errors

| Error Type | Log Level | When to Use |
|------------|-----------|-------------|
| Authentication | WARNING | Failed login attempts |
| Authorization | WARNING | Permission denials |
| Validation | INFO | Invalid input data |
| Not Found | INFO | Resource not found |
| Conflict | INFO | Duplicate resources |
| System | ERROR | Database errors, crashes |

---

## User-Friendly Messages

### Principle: Don't Leak Implementation Details

**Bad**:
```json
{
  "error": "pymongo.errors.ServerSelectionTimeoutError: localhost:27017: [Errno 61] Connection refused"
}
```

**Good**:
```json
{
  "error": {
    "message": "Service temporarily unavailable. Please try again later.",
    "code": "SYS_SERVICE_UNAVAILABLE",
    "details": {}
  }
}
```

### User-Friendly Error Messages

```python
# outlabs_auth/errors.py

USER_FRIENDLY_MESSAGES = {
    "AUTH_INVALID_CREDENTIALS": "Invalid email or password. Please try again.",
    "AUTH_TOKEN_EXPIRED": "Your session has expired. Please log in again.",
    "AUTH_ACCOUNT_LOCKED": "Your account has been temporarily locked. Please try again later.",
    "AUTHZ_PERMISSION_DENIED": "You don't have permission to perform this action.",
    "VAL_WEAK_PASSWORD": "Password must be at least 12 characters with uppercase, lowercase, number, and special character.",
    "NOT_FOUND_USER": "User not found.",
    "CONFLICT_USER_EXISTS": "An account with this email already exists.",
    "SYS_DATABASE_ERROR": "A system error occurred. Please try again later.",
}

def get_user_friendly_message(error_code: str) -> str:
    """Get user-friendly error message"""
    return USER_FRIENDLY_MESSAGES.get(
        error_code,
        "An unexpected error occurred. Please contact support."
    )
```

---

## Debugging Errors

### Error Context

```python
class OutlabsAuthException(Exception):
    """Enhanced exception with debugging context"""

    def __init__(
        self,
        message: str,
        error_code: str,
        status_code: int = 500,
        details: Optional[dict] = None,
        debug_info: Optional[dict] = None  # Only in development
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        self.debug_info = debug_info or {}
        super().__init__(self.message)

    def to_dict(self, include_debug: bool = False) -> dict:
        """Convert to dict, optionally include debug info"""
        result = {
            "error": {
                "message": self.message,
                "code": self.error_code,
                "details": self.details
            }
        }

        if include_debug and self.debug_info:
            result["error"]["debug"] = self.debug_info

        return result

# Usage
try:
    user = await UserModel.find_one(UserModel.id == user_id)
    if not user:
        raise UserNotFoundException(
            user_id=user_id,
            debug_info={
                "query": {"id": user_id},
                "collection": "users",
                "stack_trace": traceback.format_exc()
            }
        )
except UserNotFoundException as e:
    # In development, include debug info
    if settings.ENVIRONMENT == "development":
        return JSONResponse(
            status_code=e.status_code,
            content=e.to_dict(include_debug=True)
        )
    else:
        # In production, hide debug info
        return JSONResponse(
            status_code=e.status_code,
            content=e.to_dict(include_debug=False)
        )
```

### Permission Explainer for Debugging

```python
# Use the built-in permission explainer
explanation = await auth.permissions.explain(
    user_id=user.id,
    permission="entity:update",
    entity_id=entity.id
)

# Returns:
{
    "allowed": False,
    "reason": "User has no role in this entity",
    "resolution_path": [
        "Checked user roles in entity 'engineering'",
        "No roles found",
        "Checked tree permissions from parents",
        "No tree permissions found",
        "Permission denied"
    ],
    "debug_info": {
        "user_roles": [],
        "entity_path": ["platform", "organization", "engineering"],
        "checked_permissions": ["entity:update", "entity:update_tree", "entity:update_all"]
    }
}
```

---

## Production Error Handling

### Error Monitoring

**Sentry Integration**:
```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

# Initialize Sentry
sentry_sdk.init(
    dsn="your-sentry-dsn",
    integrations=[FastApiIntegration()],
    traces_sample_rate=0.1,
    environment="production"
)

# Errors are automatically captured
try:
    user = await auth.user_service.create_user(email, password)
except UserAlreadyExistsException as e:
    # Automatically sent to Sentry
    sentry_sdk.capture_exception(e)
    raise
```

### Error Alerts

**Alert Rules** (Prometheus):
```yaml
groups:
  - name: error_alerts
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        annotations:
          summary: "High error rate (>5%)"

      - alert: AuthenticationFailures
        expr: rate(auth_login_failures_total[5m]) > 10
        for: 2m
        annotations:
          summary: "High authentication failure rate"
```

### Error Recovery

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
async def fetch_user_with_retry(user_id: str):
    """Retry fetching user on database errors"""
    try:
        return await UserModel.get(user_id)
    except DatabaseException as e:
        logger.warning(f"Database error, retrying: {str(e)}")
        raise  # Retry
```

---

## Best Practices

### Do's ✅

- Use specific exception types
- Include helpful error details
- Log errors appropriately
- Return consistent error format
- Sanitize error messages in production
- Use error codes for programmatic handling
- Test error scenarios
- Monitor error rates
- Set up alerts for critical errors

### Don'ts ❌

- Don't expose sensitive data in errors
- Don't return stack traces to users
- Don't use generic `Exception`
- Don't ignore exceptions
- Don't leak implementation details
- Don't log sensitive data (passwords, tokens)
- Don't return different formats for errors

---

## Summary

### Quick Reference

**Raising Exceptions**:
```python
from outlabs_auth.exceptions import UserNotFoundException

# Raise specific exception
raise UserNotFoundException(user_id=user_id)
```

**Handling Exceptions**:
```python
try:
    user = await auth.user_service.get_user(user_id)
except UserNotFoundException as e:
    logger.warning(f"User not found: {user_id}")
    raise
```

**FastAPI Handler**:
```python
@app.exception_handler(OutlabsAuthException)
async def handler(request: Request, exc: OutlabsAuthException):
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict()
    )
```

---

**Last Updated**: 2025-01-14
**Next Review**: Quarterly
**Owner**: Engineering Team
