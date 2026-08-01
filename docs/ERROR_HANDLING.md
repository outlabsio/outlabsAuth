# OutlabsAuth Error Handling Guide

**Audience**: Developers integrating OutlabsAuth
**Status**: Production Reference
**Source of truth**: `outlabs_auth/core/exceptions.py`, `outlabs_auth/fastapi.py`, `outlabs_auth/oauth/exceptions.py`

---

## Table of Contents

1. [Error Handling Philosophy](#error-handling-philosophy)
2. [Exception Hierarchy](#exception-hierarchy)
3. [Error Codes](#error-codes)
4. [OAuth Exceptions](#oauth-exceptions)
5. [Error Handling Patterns](#error-handling-patterns)
6. [API Error Responses](#api-error-responses)
7. [Logging Errors](#logging-errors)
8. [User-Friendly Messages](#user-friendly-messages)

---

## Error Handling Philosophy

### Core Principles

1. **Fail Fast**: Detect errors early and raise exceptions immediately
2. **Specific Exceptions**: Use specific exception types, not generic `Exception`
3. **Informative Messages**: Error messages should help developers debug
4. **Security Conscious**: Don't leak sensitive information in errors
5. **Consistent Format**: All errors follow the same response structure

### Error Categories

- **Authentication Errors** (401): Login, token validation, API keys, account state
- **Authorization Errors** (403): Permission checks, access control
- **Entity / Membership Errors** (400/404/409): EnterpriseRBAC hierarchy and memberships
- **User Errors** (400/404/409): User lifecycle
- **Validation Errors** (422): Input validation
- **Rate Limiting** (429)
- **Configuration / System Errors** (500/503)

---

## Exception Hierarchy

### Base Exception

Every library exception derives from `OutlabsAuthException`. The class carries
`error_code` and `status_code` as **class attributes**, so subclasses declare
them rather than passing them to `__init__`:

```python
# outlabs_auth/core/exceptions.py

class OutlabsAuthException(Exception):
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
        return {
            "error": self.error_code,
            "message": self.message,
            "details": self.details
        }
```

**Note the constructor signature**: `message` is the only required argument.
`error_code` is optional and only needed to override the class default.
`status_code` is not a constructor argument at all.

### Hierarchy

```
OutlabsAuthException                       (AUTH_ERROR, 500)
├── AuthenticationError                    (AUTHENTICATION_ERROR, 401)
│   ├── InvalidCredentialsError            (INVALID_CREDENTIALS)
│   ├── TokenExpiredError                  (TOKEN_EXPIRED)
│   ├── TokenInvalidError                  (TOKEN_INVALID)
│   ├── RefreshTokenInvalidError           (REFRESH_TOKEN_INVALID)
│   ├── APIKeyInvalidError                 (API_KEY_INVALID)
│   ├── APIKeyExpiredError                 (API_KEY_EXPIRED)
│   ├── APIKeyLockedError                  (API_KEY_LOCKED)
│   ├── AccountLockedError                 (ACCOUNT_LOCKED)
│   └── AccountInactiveError               (ACCOUNT_INACTIVE)
│
├── AuthenticationInfrastructureError      (AUTH_INFRASTRUCTURE_UNAVAILABLE, 503)
│
├── AuthorizationError                     (AUTHORIZATION_ERROR, 403)
│   ├── PermissionDeniedError              (PERMISSION_DENIED)
│   ├── InsufficientPermissionsError       (INSUFFICIENT_PERMISSIONS)
│   ├── RoleNotFoundError                  (ROLE_NOT_FOUND, 404)
│   └── PermissionNotFoundError            (PERMISSION_NOT_FOUND, 404)
│
├── EntityError                            (ENTITY_ERROR, 400)          [EnterpriseRBAC]
│   ├── EntityNotFoundError                (ENTITY_NOT_FOUND, 404)
│   ├── CircularHierarchyError             (CIRCULAR_HIERARCHY)
│   ├── InvalidParentEntityError           (INVALID_PARENT)
│   ├── MaxDepthExceededError              (MAX_DEPTH_EXCEEDED)
│   ├── EntityTypeNotAllowedError          (ENTITY_TYPE_NOT_ALLOWED)
│   └── InvalidEntityClassError            (INVALID_ENTITY_CLASS)
│
├── MembershipError                        (MEMBERSHIP_ERROR, 400)      [EnterpriseRBAC]
│   ├── MembershipNotFoundError            (MEMBERSHIP_NOT_FOUND, 404)
│   ├── MembershipAlreadyExistsError       (MEMBERSHIP_ALREADY_EXISTS, 409)
│   └── MaxMembersExceededError            (MAX_MEMBERS_EXCEEDED)
│
├── UserError                              (USER_ERROR, 400)
│   ├── UserNotFoundError                  (USER_NOT_FOUND, 404)
│   ├── UserAlreadyExistsError             (USER_ALREADY_EXISTS, 409)
│   ├── InvalidPasswordError               (INVALID_PASSWORD)
│   └── EmailNotVerifiedError              (EMAIL_NOT_VERIFIED)
│
├── ValidationError                        (VALIDATION_ERROR, 422)
│   ├── InvalidInputError                  (INVALID_INPUT)
│   └── MissingRequiredFieldError          (MISSING_REQUIRED_FIELD)
│
├── RateLimitError                         (RATE_LIMIT_EXCEEDED, 429)
│
├── ConfigurationError                     (CONFIGURATION_ERROR, 500)
├── DatabaseError                          (DATABASE_ERROR, 500)
└── RedisError                             (REDIS_ERROR, 500)
```

**Note**: `RoleNotFoundError` and `PermissionNotFoundError` subclass
`AuthorizationError` (whose default status is 403) but override `status_code`
to 404. `AuthenticationInfrastructureError` subclasses `OutlabsAuthException`
directly, not `AuthenticationError` — it signals that a required control
(for example Redis-backed rate limiting) is unavailable, which is a 503, not a
credential failure.

### Imports

A commonly used subset is re-exported from the package root:

```python
from outlabs_auth import (
    OutlabsAuthException,
    AuthenticationError,
    AuthorizationError,
    ConfigurationError,
    InvalidCredentialsError,
    PermissionDeniedError,
    TokenExpiredError,
    TokenInvalidError,
    UserNotFoundError,
)
```

Everything else is imported from the module directly:

```python
from outlabs_auth.core.exceptions import (
    EntityNotFoundError,
    InvalidInputError,
    MembershipAlreadyExistsError,
    RateLimitError,
)
```

---

## Error Codes

Error codes are flat `SCREAMING_SNAKE_CASE` strings — there is no category
prefix. The `error_code` of each exception is listed in the hierarchy above and
is the authoritative value emitted in the `error` field of an API response.

| Code | HTTP | Raised when |
|------|------|-------------|
| `INVALID_CREDENTIALS` | 401 | Invalid email or password |
| `TOKEN_EXPIRED` | 401 | JWT has expired |
| `TOKEN_INVALID` | 401 | JWT is malformed or fails verification |
| `REFRESH_TOKEN_INVALID` | 401 | Refresh token invalid or revoked |
| `API_KEY_INVALID` | 401 | API key invalid or revoked |
| `API_KEY_EXPIRED` | 401 | API key past its expiry |
| `API_KEY_LOCKED` | 401 | API key temporarily locked after repeated failures |
| `ACCOUNT_LOCKED` | 401 | Account locked after failed login attempts |
| `ACCOUNT_INACTIVE` | 401 | Account inactive or suspended |
| `AUTH_INFRASTRUCTURE_UNAVAILABLE` | 503 | A required auth control (e.g. Redis rate limiting) is down |
| `PERMISSION_DENIED` | 403 | User lacks the required permission |
| `INSUFFICIENT_PERMISSIONS` | 403 | User lacks permissions for the operation |
| `ROLE_NOT_FOUND` | 404 | Role does not exist |
| `PERMISSION_NOT_FOUND` | 404 | Permission does not exist |
| `ENTITY_NOT_FOUND` | 404 | Entity does not exist |
| `CIRCULAR_HIERARCHY` | 400 | Move would create a cycle in the entity tree |
| `INVALID_PARENT` | 400 | Parent entity invalid or incompatible |
| `MAX_DEPTH_EXCEEDED` | 400 | Entity tree deeper than `max_entity_depth` |
| `ENTITY_TYPE_NOT_ALLOWED` | 400 | Entity type not permitted in this context |
| `INVALID_ENTITY_CLASS` | 400 | Entity class is not STRUCTURAL or ACCESS_GROUP |
| `MEMBERSHIP_NOT_FOUND` | 404 | Membership does not exist |
| `MEMBERSHIP_ALREADY_EXISTS` | 409 | User is already a member of the entity |
| `MAX_MEMBERS_EXCEEDED` | 400 | Entity is at its member cap |
| `USER_NOT_FOUND` | 404 | User does not exist |
| `USER_ALREADY_EXISTS` | 409 | Email already registered |
| `INVALID_PASSWORD` | 400 | Password fails policy requirements |
| `EMAIL_NOT_VERIFIED` | 400 | Email address not verified |
| `INVALID_INPUT` | 422 | Input data invalid |
| `MISSING_REQUIRED_FIELD` | 422 | Required field absent |
| `RATE_LIMIT_EXCEEDED` | 429 | Rate limit hit |
| `CONFIGURATION_ERROR` | 500 | Invalid library configuration |
| `DATABASE_ERROR` | 500 | PostgreSQL operation failed |
| `REDIS_ERROR` | 500 | Redis operation failed |

Codes produced by the framework-level handlers in `outlabs_auth/fastapi.py`
rather than by an exception class:

| Code | HTTP | Raised when |
|------|------|-------------|
| `VALIDATION_ERROR` | 422 | FastAPI `RequestValidationError` |
| `INTEGRITY_ERROR` | 409 | SQLAlchemy `IntegrityError` (constraint violation) |
| `INVALID_INPUT` | 422 | Bare `ValueError` escaped a handler |
| `HTTP_ERROR` | *varies* | Starlette/FastAPI `HTTPException` |
| `INTERNAL_SERVER_ERROR` | 500 | Any unhandled exception |

---

## OAuth Exceptions

OAuth errors live in `outlabs_auth/oauth/exceptions.py` and form a **separate
hierarchy rooted at `OAuthError(Exception)`**. They do *not* inherit from
`OutlabsAuthException`, carry no `error_code` or `status_code`, and are **not**
picked up by the `OutlabsAuthException` handler — catch them explicitly or let
the catch-all handler turn them into a 500.

```
OAuthError
├── InvalidStateError            state parameter invalid, expired, or missing
├── InvalidCodeError             authorization code invalid or expired
├── ProviderError                provider returned an error (carries .provider, .error,
│                                .error_description, .error_uri)
├── AccountLinkError             cannot link a provider account to a user
│   ├── AccountAlreadyLinkedError    provider account linked to another user
│   ├── ProviderAlreadyLinkedError   user already has this provider linked
│   └── CannotUnlinkLastMethodError  would leave the user with no way to log in
├── ProviderNotConfiguredError   provider not configured
├── EmailNotVerifiedError        provider did not verify the email (blocks auto-link)
├── TokenRefreshError            failed to refresh a provider token
├── InvalidNonceError            OIDC nonce validation failed (possible replay)
└── PKCEValidationError          code verifier does not match the challenge
```

`outlabs_auth.oauth.exceptions.EmailNotVerifiedError` and
`outlabs_auth.core.exceptions.EmailNotVerifiedError` are **different classes**
with the same name. Import them under an alias if you need both in one module.

---

## Error Handling Patterns

### Pattern 1: Register the shipped handlers

The library ships its handlers — you do not need to write them:

```python
from fastapi import FastAPI
from outlabs_auth import register_exception_handlers

app = FastAPI()

# mode="global": OutlabsAuthException + validation/integrity/HTTP/catch-all handlers
register_exception_handlers(app, debug=False, observability=auth.observability)

# mode="auth_only": only the OutlabsAuthException handler, leaving your app's
# own handlers for everything else
register_exception_handlers(app, mode="auth_only")
```

`register_outlabs_exception_handler(app)` is the equivalent of `mode="auth_only"`.

The `debug` flag controls whether raw exception text is included in the
`details` of integrity/value/unexpected errors. **Leave it `False` in
production** — it is what keeps internal detail out of responses.

Passing `observability=` routes unhandled exceptions through the library's
structured logger as an `unhandled_exception` event.

### Pattern 2: Catch specific exceptions

```python
from outlabs_auth import PermissionDeniedError, UserNotFoundError

async def update_user_role(session, actor_id, user_id: str, role_id: str):
    user = await auth.user_service.get_user(session, user_id)
    if not user:
        raise UserNotFoundError(f"User not found: {user_id}", details={"user_id": user_id})

    has_perm, _ = await auth.permission_service.check_permission(
        session, user_id=actor_id, permission="role:assign"
    )
    if not has_perm:
        raise PermissionDeniedError(
            "Permission denied: role:assign",
            details={"permission": "role:assign", "user_id": str(actor_id)},
        )

    await auth.role_service.assign_role(session, user_id, role_id)
    await session.commit()
```

Because every exception derives from `OutlabsAuthException`, a single `except`
catches the whole family, and `to_dict()` gives you the response body:

```python
from outlabs_auth import OutlabsAuthException

try:
    ...
except OutlabsAuthException as exc:
    logger.warning("auth_error", **exc.to_dict())
    raise
```

### Pattern 3: Catch by category

Category base classes let you handle a whole class of failure at once:

```python
from outlabs_auth import AuthenticationError, AuthorizationError

try:
    user = await auth.get_current_user(session, token)
except AuthenticationError:
    # any 401: bad credentials, expired/invalid token, locked or inactive account
    ...
except AuthorizationError:
    # any 403 (plus role/permission 404s)
    ...
```

### Pattern 4: Overriding the error code

`error_code` is a class attribute with an optional constructor override — use it
when you want a more specific code without declaring a new class:

```python
from outlabs_auth.core.exceptions import ValidationError

raise ValidationError(
    "Slug must be lowercase alphanumeric with dashes",
    error_code="INVALID_SLUG",
    details={"field": "slug"},
)
```

---

## API Error Responses

### Standard Error Response Format

`to_dict()` produces a **flat** object — `error`, `message`, `details` at the
top level:

```json
{
  "error": "USER_NOT_FOUND",
  "message": "User not found: 12345",
  "details": {
    "user_id": "12345"
  }
}
```

The HTTP status comes from the exception's `status_code`, not from the body.

### Examples

**401 Unauthorized** (invalid credentials):
```json
{
  "error": "INVALID_CREDENTIALS",
  "message": "Invalid email or password",
  "details": {}
}
```

**403 Forbidden** (permission denied):
```json
{
  "error": "PERMISSION_DENIED",
  "message": "Permission denied: user:delete",
  "details": {
    "permission": "user:delete",
    "user_id": "abc123",
    "entity_id": null
  }
}
```

**409 Conflict** (duplicate user):
```json
{
  "error": "USER_ALREADY_EXISTS",
  "message": "User already exists with email: user@example.com",
  "details": {
    "email": "user@example.com"
  }
}
```

**422 Unprocessable Entity** (request validation, from the shipped handler):
```json
{
  "error": "VALIDATION_ERROR",
  "message": "Request validation failed",
  "details": {
    "errors": [
      {"type": "string_too_short", "loc": ["body", "password"], "msg": "String should have at least 12 characters"}
    ]
  }
}
```

The validation handler strips the `input`, `ctx`, and `url` keys from each
Pydantic error (SEC-8). Pydantic v2 echoes the rejected value back in `input`,
which for a password or token field would put the submitted secret into the
response body — and from there into client logs, proxies, and error trackers.
Only the field location and reason are returned.

**429 Too Many Requests**:
```json
{
  "error": "RATE_LIMIT_EXCEEDED",
  "message": "Too many login attempts. Try again in 60 seconds.",
  "details": {}
}
```

**500 Internal Server Error** (catch-all handler, `debug=False`):
```json
{
  "error": "INTERNAL_SERVER_ERROR",
  "message": "Internal server error",
  "details": {}
}
```

**503 Service Unavailable** (auth control unavailable):
```json
{
  "error": "AUTH_INFRASTRUCTURE_UNAVAILABLE",
  "message": "Rate limiting backend unavailable",
  "details": {}
}
```

---

## Logging Errors

Every `OutlabsAuthException` serializes to a log-ready dict via `to_dict()`, and
`status_code` is a clean level selector:

```python
import logging
from outlabs_auth import OutlabsAuthException

logger = logging.getLogger("outlabs_auth")

def log_exception(exc: OutlabsAuthException, **context) -> None:
    payload = {**exc.to_dict(), "status_code": exc.status_code, **context}

    if exc.status_code >= 500:
        logger.error(payload)
    elif exc.status_code >= 400:
        logger.warning(payload)
    else:
        logger.info(payload)
```

If you have the library's observability service wired up, prefer its structured
logger — it attaches the correlation ID and hostname automatically:

```python
auth.observability.logger.warning("permission_denied", **exc.to_dict())
```

See `docs-library/97-Observability.md` and `docs-library/99-Log-Events-Reference.md`.

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

**Bad** — driver-level detail reaches the client:
```json
{
  "error": "asyncpg.exceptions.CannotConnectNowError: the database system is starting up"
}
```

**Good**:
```json
{
  "error": "DATABASE_ERROR",
  "message": "A system error occurred. Please try again later.",
  "details": {}
}
```

This is exactly what `register_exception_handlers(app, debug=False)` does for
you: raw exception text only ever lands in `details` when `debug=True`.

### Mapping Codes to Copy

The library's `message` is written for developers. For end-user copy, map the
stable `error_code` in your own application:

```python
USER_FRIENDLY_MESSAGES = {
    "INVALID_CREDENTIALS": "Invalid email or password. Please try again.",
    "TOKEN_EXPIRED": "Your session has expired. Please log in again.",
    "ACCOUNT_LOCKED": "Your account has been temporarily locked. Please try again later.",
    "ACCOUNT_INACTIVE": "This account is not active. Contact your administrator.",
    "PERMISSION_DENIED": "You don't have permission to perform this action.",
    "INVALID_PASSWORD": "Password does not meet the security requirements.",
    "USER_NOT_FOUND": "User not found.",
    "USER_ALREADY_EXISTS": "An account with this email already exists.",
    "RATE_LIMIT_EXCEEDED": "Too many attempts. Please wait and try again.",
    "DATABASE_ERROR": "A system error occurred. Please try again later.",
    "INTERNAL_SERVER_ERROR": "An unexpected error occurred. Please try again later.",
}

def get_user_friendly_message(error_code: str) -> str:
    return USER_FRIENDLY_MESSAGES.get(
        error_code,
        "An unexpected error occurred. Please contact support."
    )
```

Match on `error_code`, never on `message` — the code is the stable contract.
