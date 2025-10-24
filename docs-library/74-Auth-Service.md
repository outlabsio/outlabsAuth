# 74-Auth-Service.md - AuthService API Reference

Complete API reference for the **AuthService** - authentication and JWT token management.

---

## Table of Contents

1. [Overview](#overview)
2. [Accessing AuthService](#accessing-authservice)
3. [Login](#login)
4. [Logout](#logout)
5. [Token Refresh](#token-refresh)
6. [Current User](#current-user)
7. [Session Management](#session-management)
8. [Account Security](#account-security)
9. [Error Handling](#error-handling)
10. [Complete Examples](#complete-examples)

---

## Overview

**AuthService** handles user authentication and JWT token management.

### Features

- ✅ Email/password authentication
- ✅ JWT access & refresh tokens
- ✅ Account lockout (failed login attempts)
- ✅ Multi-device session support
- ✅ Refresh token revocation
- ✅ Logout from all devices
- ✅ Notification events (login, logout, lockout)

### Token Architecture

```
Access Token (JWT)
- Type: "access"
- Expiration: 15 minutes (default)
- Use: API authentication
- Storage: Memory/localStorage (frontend)

Refresh Token (JWT)
- Type: "refresh"
- Expiration: 30 days (default)
- Use: Get new access token
- Storage: httpOnly cookie (recommended) or secure storage
- Hash stored in MongoDB for revocation
```

### Token Pair Response

```python
class TokenPair:
    access_token: str   # JWT access token
    refresh_token: str  # JWT refresh token
    token_type: str     # "bearer"

    def to_dict():
        return {
            "access_token": "eyJ...",
            "refresh_token": "eyJ...",
            "token_type": "bearer"
        }
```

---

## Accessing AuthService

### SimpleRBAC

```python
from outlabs_auth import SimpleRBAC

auth = SimpleRBAC(database=db, secret_key="...")
await auth.initialize()

# Access AuthService
auth_service = auth.auth_service
```

### Configuration

```python
auth = SimpleRBAC(
    database=db,
    secret_key="your-secret-key-min-32-chars",
    algorithm="HS256",
    access_token_expire_minutes=15,      # Access token TTL
    refresh_token_expire_days=30,        # Refresh token TTL
    max_login_attempts=5,                # Lockout threshold
    lockout_duration_minutes=15          # Lockout duration
)
```

---

## Login

### login()

Authenticate user with email and password.

```python
user, tokens = await auth.auth_service.login(
    email="user@example.com",
    password="MyPassword123!",
    device_name="iPhone 12",           # Optional
    ip_address="192.168.1.100",        # Optional
    user_agent="Mozilla/5.0..."        # Optional
)
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `email` | `str` | ✅ Yes | User email address |
| `password` | `str` | ✅ Yes | Plain text password |
| `device_name` | `str` | ❌ No | Device identifier (e.g., "iPhone 12") |
| `ip_address` | `str` | ❌ No | Client IP address |
| `user_agent` | `str` | ❌ No | User agent string |

**Returns:** `Tuple[UserModel, TokenPair]` - (authenticated_user, token_pair)

**Raises:**
- `InvalidCredentialsError` - Email or password is incorrect
- `AccountLockedError` - Account locked due to failed login attempts
- `AccountInactiveError` - Account is not active (suspended, banned, etc.)

**Example:**

```python
try:
    user, tokens = await auth.auth_service.login(
        email="alice@example.com",
        password="SecurePass123!",
        device_name="Chrome on MacOS",
        ip_address=request.client.host
    )

    # Return tokens to client
    return {
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "token_type": tokens.token_type,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "name": user.profile.full_name
        }
    }

except InvalidCredentialsError as e:
    # Wrong password
    raise HTTPException(
        status_code=401,
        detail=e.message,
        headers={"X-Failed-Attempts": str(e.details.get("failed_attempts", 0))}
    )

except AccountLockedError as e:
    # Account locked
    raise HTTPException(
        status_code=423,
        detail=e.message,
        headers={"X-Locked-Until": e.details.get("locked_until", "")}
    )

except AccountInactiveError as e:
    # Account inactive
    raise HTTPException(status_code=403, detail=e.message)
```

### Login Flow

```
1. Validate and normalize email
2. Find user by email
3. Check if account is locked
4. Check if account is active
5. Verify password
   ├─ If incorrect:
   │  ├─ Increment failed_login_attempts
   │  ├─ Lock account if threshold reached
   │  ├─ Emit "user.login_failed" notification
   │  └─ Raise InvalidCredentialsError
   └─ If correct:
      ├─ Reset failed_login_attempts
      ├─ Update last_login timestamp
      ├─ Emit "user.login" notification
      ├─ Create JWT access + refresh tokens
      ├─ Store refresh token hash in database
      └─ Return user + tokens
```

### Multi-Device Support

Each login creates a **separate refresh token session**:

```python
# Login from iPhone
user, tokens1 = await auth.auth_service.login(
    email="alice@example.com",
    password="password",
    device_name="iPhone 12"
)

# Login from laptop (different session)
user, tokens2 = await auth.auth_service.login(
    email="alice@example.com",
    password="password",
    device_name="MacBook Pro"
)

# Both sessions are independent
# tokens1.refresh_token != tokens2.refresh_token
```

---

## Logout

### logout()

Logout user with configurable revocation strategy.

```python
success = await auth.auth_service.logout(
    refresh_token=refresh_token,
    blacklist_access_token=False,  # Optional: immediate access token revocation
    access_token_jti="abc123...",   # Required if blacklist_access_token=True
    redis_client=redis              # Required if blacklist_access_token=True
)
```

**Parameters:**
- `refresh_token` (str): Refresh token to revoke
- `blacklist_access_token` (bool, optional): If True, blacklist access token in Redis. Default: False
- `access_token_jti` (str, optional): JWT ID from access token (required if blacklist_access_token=True)
- `redis_client` (RedisClient, optional): Redis client for blacklisting (required if blacklist_access_token=True)

**Returns:** `bool` - `True` if revoked, `False` if not found

**Configuration:**
- Respects `config.store_refresh_tokens` - if False, skips MongoDB revocation
- Respects `config.enable_token_blacklist` - if False, skips Redis blacklisting
- Gracefully degrades if Redis unavailable

**Example - Standard Logout:**

```python
from fastapi import Depends

@app.post("/auth/logout", status_code=204)
async def logout(
    data: LogoutRequest,
    auth_result = Depends(auth.deps.require_auth())
):
    """Standard logout - revoke refresh token."""
    await auth.auth_service.logout(data.refresh_token)
    return None
```

**Example - Immediate Revocation (High Security):**

```python
@app.post("/auth/logout", status_code=204)
async def logout(
    data: LogoutRequest,
    auth_result = Depends(auth.deps.require_auth())
):
    """High-security logout - immediate access token revocation."""
    jti = auth_result.get("jti")

    await auth.auth_service.logout(
        refresh_token=data.refresh_token,
        blacklist_access_token=True,
        access_token_jti=jti,
        redis_client=auth.redis_client
    )
    return None
```

### Logout Behavior

**When `store_refresh_tokens=True` (default):**
```
1. Hash the refresh token
2. Find token in database (by hash)
3. If found:
   ├─ Mark as revoked (is_revoked = True)
   ├─ Set revoked_at timestamp
   ├─ Set revoked_reason = "User logout"
   ├─ Emit "user.logout" notification
   └─ Return True
4. If not found:
   └─ Return False
5. (Optional) If blacklist_access_token=True and enable_token_blacklist=True:
   ├─ Add access token JTI to Redis blacklist
   ├─ Set TTL to remaining token lifetime
   └─ Access token immediately invalid
```

**When `store_refresh_tokens=False` (stateless mode):**
```
1. Skip MongoDB revocation (no refresh tokens stored)
2. If blacklist_access_token=True and enable_token_blacklist=True:
   ├─ Add access token JTI to Redis blacklist
   └─ Return True if blacklisted, False otherwise
3. Otherwise return False
```

### Security Modes

| Config | Access Token After Logout | Refresh Token After Logout | Use Case |
|--------|---------------------------|----------------------------|----------|
| `store_refresh_tokens=True`<br>`enable_token_blacklist=False` | Valid for 15 min | Revoked immediately | **Default** - Most applications |
| `store_refresh_tokens=True`<br>`enable_token_blacklist=True` | Revoked immediately (if Redis) | Revoked immediately | **High Security** - Banking, healthcare |
| `store_refresh_tokens=False`<br>`enable_token_blacklist=False` | Valid for 15 min | N/A (stateless JWT) | **Internal Tools** - Minimal DB writes |
| `store_refresh_tokens=False`<br>`enable_token_blacklist=True` | Revoked immediately (if Redis) | N/A (stateless JWT) | **Redis-only** revocation |

---

## Token Refresh

### refresh_access_token()

Get new access token using refresh token.

```python
new_tokens = await auth.auth_service.refresh_access_token(refresh_token)
print(f"New access token: {new_tokens.access_token}")
```

**Parameters:**
- `refresh_token` (str): Valid refresh token

**Returns:** `TokenPair` - New access token + same refresh token

**Raises:**
- `RefreshTokenInvalidError` - Refresh token is invalid or revoked
- `TokenExpiredError` - Refresh token has expired
- `UserNotFoundError` - User no longer exists
- `AccountInactiveError` - Account is not active

**Example:**

```python
from fastapi import Cookie, HTTPException
from outlabs_auth.core.exceptions import (
    RefreshTokenInvalidError,
    TokenExpiredError,
    AccountInactiveError
)

@app.post("/auth/refresh")
async def refresh_token(refresh_token: str = Cookie(None)):
    """Get new access token using refresh token."""
    if not refresh_token:
        raise HTTPException(status_code=400, detail="No refresh token provided")

    try:
        tokens = await auth.auth_service.refresh_access_token(refresh_token)

        return {
            "access_token": tokens.access_token,
            "refresh_token": tokens.refresh_token,  # Same refresh token
            "token_type": tokens.token_type
        }

    except RefreshTokenInvalidError as e:
        raise HTTPException(status_code=401, detail=e.message)

    except TokenExpiredError as e:
        raise HTTPException(status_code=401, detail="Refresh token expired")

    except AccountInactiveError as e:
        raise HTTPException(status_code=403, detail=e.message)
```

### Refresh Flow

```
1. Verify JWT structure
2. Check if refresh token exists in database
3. Verify token is not revoked
4. Verify token is not expired
5. Get user from database
6. Check user account is active
7. Create new access token
8. Update token usage stats (last_used_at, usage_count)
9. Return new access token + same refresh token
```

### Token Rotation

**Current Implementation:** Refresh token is **reused** (not rotated).

```python
tokens1 = await auth.auth_service.login(email, password)
# tokens1.refresh_token = "abc123"

# Refresh access token
tokens2 = await auth.auth_service.refresh_access_token(tokens1.refresh_token)
# tokens2.refresh_token = "abc123" (same!)
# tokens2.access_token = "xyz789" (new!)
```

**For Token Rotation:** See **22-JWT-Tokens.md** for implementing refresh token rotation pattern.

---

## Current User

### get_current_user()

Get current user from access token.

```python
user = await auth.auth_service.get_current_user(access_token)
print(f"Current user: {user.email}")
```

**Parameters:**
- `access_token` (str): JWT access token

**Returns:** `UserModel` - Authenticated user

**Raises:**
- `TokenInvalidError` - Token is invalid
- `TokenExpiredError` - Token has expired
- `UserNotFoundError` - User doesn't exist
- `AccountInactiveError` - Account is not active

**Example:**

```python
from fastapi import Header, HTTPException
from outlabs_auth.core.exceptions import (
    TokenInvalidError,
    TokenExpiredError,
    UserNotFoundError
)

@app.get("/users/me")
async def get_me(authorization: str = Header(None)):
    """Get current user profile."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No authorization header")

    # Extract token
    access_token = authorization.replace("Bearer ", "")

    try:
        user = await auth.auth_service.get_current_user(access_token)

        return {
            "id": str(user.id),
            "email": user.email,
            "first_name": user.profile.first_name,
            "last_name": user.profile.last_name,
            "email_verified": user.email_verified,
            "status": user.status.value
        }

    except TokenExpiredError:
        raise HTTPException(status_code=401, detail="Token expired")

    except TokenInvalidError as e:
        raise HTTPException(status_code=401, detail=e.message)

    except UserNotFoundError:
        raise HTTPException(status_code=404, detail="User not found")
```

**Note:** For most routes, use `AuthDeps.authenticated()` dependency instead of calling `get_current_user()` manually. See **80-Auth-Dependencies.md**.

---

## Session Management

### revoke_all_user_tokens()

Revoke all refresh tokens for a user (logout from all devices).

```python
count = await auth.auth_service.revoke_all_user_tokens(str(user.id))
print(f"Revoked {count} sessions")
```

**Parameters:**
- `user_id` (str): User ID

**Returns:** `int` - Number of tokens revoked

**Example:**

```python
@app.post("/auth/logout-all")
async def logout_all_devices(user = Depends(deps.authenticated())):
    """Logout from all devices."""
    count = await auth.auth_service.revoke_all_user_tokens(str(user.id))

    return {
        "message": f"Logged out from {count} device(s)",
        "sessions_revoked": count
    }
```

### Use Cases

**Security Incidents:**
```python
# User reports compromised account
await auth.auth_service.revoke_all_user_tokens(str(user.id))
# Force password change
await auth.user_service.change_password(str(user.id), new_password)
```

**Password Change:**
```python
@app.post("/users/me/change-password")
async def change_password(
    current_password: str,
    new_password: str,
    user = Depends(deps.authenticated())
):
    # Verify current password
    if not auth.verify_password(current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Invalid current password")

    # Change password
    await auth.user_service.change_password(str(user.id), new_password)

    # Revoke all sessions (force re-login)
    await auth.auth_service.revoke_all_user_tokens(str(user.id))

    return {"message": "Password changed. Please log in again."}
```

### List Active Sessions

```python
from outlabs_auth.models.token import RefreshTokenModel

@app.get("/auth/sessions")
async def list_sessions(user = Depends(deps.authenticated())):
    """List all active sessions for current user."""
    tokens = await RefreshTokenModel.find(
        RefreshTokenModel.user.ref.id == user.id,
        RefreshTokenModel.is_revoked == False
    ).to_list()

    return {
        "sessions": [
            {
                "id": str(t.id),
                "device_name": t.device_name,
                "ip_address": t.ip_address,
                "user_agent": t.user_agent,
                "created_at": t.created_at.isoformat(),
                "last_used_at": t.last_used_at.isoformat() if t.last_used_at else None,
                "expires_at": t.expires_at.isoformat()
            }
            for t in tokens
        ],
        "count": len(tokens)
    }
```

---

## Account Security

### Account Lockout

Accounts are automatically locked after failed login attempts.

**Configuration:**
```python
auth = SimpleRBAC(
    database=db,
    secret_key="...",
    max_login_attempts=5,          # Lock after 5 failed attempts
    lockout_duration_minutes=15    # Lock for 15 minutes
)
```

**Lockout Flow:**
```
1. Wrong password entered
2. Increment user.failed_login_attempts
3. If failed_login_attempts >= max_login_attempts:
   ├─ Set locked_until = now + lockout_duration_minutes
   ├─ Emit "user.locked" notification
   └─ Raise AccountLockedError
```

**Check if User is Locked:**
```python
user = await auth.user_service.get_user_by_email(email)
if user.is_locked:
    print(f"Account locked until: {user.locked_until}")
```

**Unlock Account:**
```python
# Method 1: Wait for lockout_duration to expire
# Account automatically unlocks when locked_until passes

# Method 2: Manual unlock
user = await auth.user_service.get_user_by_id(user_id)
user.failed_login_attempts = 0
user.locked_until = None
await user.save()

# Method 3: Change password (automatically unlocks)
await auth.user_service.change_password(user_id, "NewPassword123!")
```

### Failed Login Tracking

```python
# After failed login
user = await auth.user_service.get_user_by_email(email)
print(f"Failed attempts: {user.failed_login_attempts} / {auth.config.max_login_attempts}")

# Notification event
if notifications_enabled:
    # "user.login_failed" event emitted with:
    {
        "user_id": str(user.id),
        "email": user.email,
        "failed_attempts": user.failed_login_attempts,
        "max_attempts": config.max_login_attempts
    }
```

---

## Error Handling

### Exception Types

```python
from outlabs_auth.core.exceptions import (
    InvalidCredentialsError,
    AccountLockedError,
    AccountInactiveError,
    TokenInvalidError,
    TokenExpiredError,
    RefreshTokenInvalidError,
    UserNotFoundError,
)
```

### Error Handling Pattern

```python
from fastapi import HTTPException
from outlabs_auth.core.exceptions import (
    InvalidCredentialsError,
    AccountLockedError,
    AccountInactiveError,
    TokenExpiredError
)

@app.post("/auth/login")
async def login_endpoint(email: str, password: str):
    try:
        user, tokens = await auth.auth_service.login(email, password)

        return {
            "access_token": tokens.access_token,
            "refresh_token": tokens.refresh_token,
            "token_type": tokens.token_type,
            "user": {"id": str(user.id), "email": user.email}
        }

    except InvalidCredentialsError as e:
        # Wrong email/password
        raise HTTPException(
            status_code=401,
            detail=e.message,
            headers={
                "X-Failed-Attempts": str(e.details.get("failed_attempts", 0)),
                "X-Max-Attempts": str(e.details.get("max_attempts", 5))
            }
        )

    except AccountLockedError as e:
        # Account locked
        raise HTTPException(
            status_code=423,  # Locked
            detail=e.message,
            headers={"X-Locked-Until": e.details.get("locked_until", "")}
        )

    except AccountInactiveError as e:
        # Account inactive (suspended, banned, etc.)
        raise HTTPException(status_code=403, detail=e.message)

@app.post("/auth/refresh")
async def refresh_endpoint(refresh_token: str):
    try:
        tokens = await auth.auth_service.refresh_access_token(refresh_token)
        return tokens.to_dict()

    except (RefreshTokenInvalidError, TokenExpiredError) as e:
        raise HTTPException(status_code=401, detail=str(e))
```

---

## Complete Examples

### Complete Authentication API

```python
from fastapi import FastAPI, Depends, HTTPException, Response, Cookie
from pydantic import BaseModel, EmailStr
from outlabs_auth import SimpleRBAC
from outlabs_auth.dependencies import AuthDeps
from outlabs_auth.core.exceptions import (
    InvalidCredentialsError,
    AccountLockedError,
    AccountInactiveError,
    TokenExpiredError,
    RefreshTokenInvalidError
)

app = FastAPI()
auth = SimpleRBAC(database=db, secret_key="...")
deps = AuthDeps(auth)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

# ============================================
# Login
# ============================================

@app.post("/auth/login", response_model=TokenResponse)
async def login(data: LoginRequest, response: Response):
    """Login with email and password."""
    try:
        user, tokens = await auth.auth_service.login(
            email=data.email,
            password=data.password
        )

        # Set refresh token in httpOnly cookie (recommended)
        response.set_cookie(
            key="refresh_token",
            value=tokens.refresh_token,
            httponly=True,
            secure=True,  # HTTPS only
            samesite="lax",
            max_age=30 * 24 * 60 * 60  # 30 days
        )

        return TokenResponse(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token
        )

    except InvalidCredentialsError as e:
        raise HTTPException(status_code=401, detail=e.message)

    except AccountLockedError as e:
        raise HTTPException(status_code=423, detail=e.message)

    except AccountInactiveError as e:
        raise HTTPException(status_code=403, detail=e.message)

# ============================================
# Logout
# ============================================

@app.post("/auth/logout")
async def logout(
    response: Response,
    refresh_token: str = Cookie(None)
):
    """Logout (revoke refresh token)."""
    if refresh_token:
        await auth.auth_service.logout(refresh_token)

    # Clear refresh token cookie
    response.delete_cookie(key="refresh_token")

    return {"message": "Logged out successfully"}

# ============================================
# Refresh Token
# ============================================

@app.post("/auth/refresh", response_model=TokenResponse)
async def refresh_token(refresh_token: str = Cookie(None)):
    """Get new access token using refresh token."""
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token provided")

    try:
        tokens = await auth.auth_service.refresh_access_token(refresh_token)
        return TokenResponse(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token
        )

    except (RefreshTokenInvalidError, TokenExpiredError) as e:
        raise HTTPException(status_code=401, detail=str(e))

# ============================================
# Current User
# ============================================

@app.get("/users/me")
async def get_current_user(user = Depends(deps.authenticated())):
    """Get current user profile."""
    return {
        "id": str(user.id),
        "email": user.email,
        "first_name": user.profile.first_name,
        "last_name": user.profile.last_name,
        "email_verified": user.email_verified
    }

# ============================================
# Logout All Devices
# ============================================

@app.post("/auth/logout-all")
async def logout_all_devices(
    response: Response,
    user = Depends(deps.authenticated())
):
    """Logout from all devices."""
    count = await auth.auth_service.revoke_all_user_tokens(str(user.id))

    # Clear current device's cookie
    response.delete_cookie(key="refresh_token")

    return {
        "message": f"Logged out from {count} device(s)",
        "sessions_revoked": count
    }

# ============================================
# List Active Sessions
# ============================================

from outlabs_auth.models.token import RefreshTokenModel

@app.get("/auth/sessions")
async def list_active_sessions(user = Depends(deps.authenticated())):
    """List all active sessions."""
    tokens = await RefreshTokenModel.find(
        RefreshTokenModel.user.ref.id == user.id,
        RefreshTokenModel.is_revoked == False
    ).to_list()

    return {
        "sessions": [
            {
                "id": str(t.id),
                "device_name": t.device_name,
                "ip_address": t.ip_address,
                "created_at": t.created_at.isoformat(),
                "last_used_at": t.last_used_at.isoformat() if t.last_used_at else None,
                "expires_at": t.expires_at.isoformat()
            }
            for t in tokens
        ],
        "count": len(tokens)
    }

# ============================================
# Revoke Specific Session
# ============================================

@app.delete("/auth/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    user = Depends(deps.authenticated())
):
    """Revoke specific session."""
    token = await RefreshTokenModel.get(session_id)

    if not token:
        raise HTTPException(status_code=404, detail="Session not found")

    # Verify ownership
    token_user = await token.user.fetch()
    if str(token_user.id) != str(user.id):
        raise HTTPException(status_code=403, detail="Not your session")

    # Revoke
    token.is_revoked = True
    token.revoked_at = datetime.now(timezone.utc)
    token.revoked_reason = "User revoked session"
    await token.save()

    return {"message": "Session revoked"}
```

---

## Summary

**AuthService** provides complete authentication and session management:

✅ **Login** - Email/password authentication with account lockout
✅ **Logout** - Revoke refresh tokens (single or all devices)
✅ **Token Refresh** - Get new access token using refresh token
✅ **Current User** - Get user from access token
✅ **Session Management** - Multi-device sessions with tracking
✅ **Account Security** - Automatic lockout after failed login attempts
✅ **Notifications** - Events for login, logout, lockout
✅ **Token Storage** - Refresh token hashes stored in MongoDB for revocation

**Token Lifecycle:**
- **Access Token**: 15 min (default) → Used for API authentication
- **Refresh Token**: 30 days (default) → Used to get new access token
- **Refresh Flow**: Access expired? → Use refresh token → Get new access token
- **Revocation**: Logout → Revoke refresh token → Can't get new access tokens

---

## Related Documentation

- **21-Email-Password-Auth.md** - Email/password authentication overview
- **22-JWT-Tokens.md** - JWT token management details
- **60-SimpleRBAC-API.md** - SimpleRBAC API reference
- **70-User-Service.md** - UserService API reference
- **80-Auth-Dependencies.md** - AuthDeps for FastAPI routes

---

**Last Updated:** 2025-01-14
