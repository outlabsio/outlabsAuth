# 91-Auth-Router.md - Auth Router Reference

Reference for **get_auth_router()** - pre-built authentication routes.

---

## Overview

`get_auth_router()` generates a FastAPI router with authentication endpoints (login, register, logout, refresh, password reset).

---

## Usage

```python
from fastapi import FastAPI
from outlabs_auth import SimpleRBAC
from outlabs_auth.routers import get_auth_router

app = FastAPI()
auth = SimpleRBAC(database=db, secret_key="...")

# Include auth router
app.include_router(
    get_auth_router(auth),
    prefix="/auth",
    tags=["authentication"]
)
```

---

## Routes

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| `POST` | `/register` | Register new user | ❌ No |
| `POST` | `/login` | Login with email/password | ❌ No |
| `POST` | `/logout` | Logout user | ✅ Yes |
| `POST` | `/refresh` | Refresh access token | ❌ No |
| `POST` | `/forgot-password` | Request password reset | ❌ No |
| `POST` | `/reset-password` | Reset password with token | ❌ No |

---

## API Reference

### POST /register

Register new user.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "first_name": "John",
  "last_name": "Doe"
}
```

**Response (201):**
```json
{
  "id": "507f1f77bcf86cd799439011",
  "email": "user@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "email_verified": false
}
```

---

### POST /login

Login with email and password.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!"
}
```

**Response (200):**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

---

### POST /logout

Logout user (invalidates tokens if Redis is enabled).

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response (204):** No content

---

### POST /refresh

Get new access token using refresh token.

**Request Body:**
```json
{
  "refresh_token": "eyJ..."
}
```

**Response (200):**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

---

### POST /forgot-password

Request password reset email.

**Request Body:**
```json
{
  "email": "user@example.com"
}
```

**Response (204):** No content
**Note:** Always returns 204 (doesn't reveal if email exists)

---

### POST /reset-password

Reset password using reset token.

**Request Body:**
```json
{
  "token": "reset_token_here",
  "new_password": "NewSecurePass123!"
}
```

**Response (204):** No content

---

## Configuration

```python
app.include_router(
    get_auth_router(
        auth,
        prefix="/auth",                    # Default: "/auth"
        tags=["authentication"],           # Default: ["auth"]
        requires_verification=False        # Require email verification
    )
)
```

---

## Related Documentation

- **74-Auth-Service.md** - AuthService API reference
- **80-Auth-Dependencies.md** - AuthDeps dependency injection
- **90-Router-Factories-Overview.md** - Router factories overview

---

**Last Updated:** 2025-01-14
