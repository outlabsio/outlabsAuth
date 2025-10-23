# 92-Users-Router.md - Users Router Reference

Reference for **get_users_router()** - pre-built user profile management routes.

---

## Overview

`get_users_router()` generates a FastAPI router with user profile management endpoints.

---

## Usage

```python
from fastapi import FastAPI
from outlabs_auth import SimpleRBAC
from outlabs_auth.routers import get_users_router

app = FastAPI()
auth = SimpleRBAC(database=db, secret_key="...")

# Include users router
app.include_router(
    get_users_router(auth),
    prefix="/users",
    tags=["users"]
)
```

---

## Routes

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| `GET` | `/me` | Get current user | ✅ Yes |
| `PUT` | `/me` | Update profile | ✅ Yes |
| `POST` | `/me/change-password` | Change password | ✅ Yes |

---

## API Reference

### GET /me

Get current user profile.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response (200):**
```json
{
  "id": "507f1f77bcf86cd799439011",
  "email": "user@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "email_verified": true,
  "status": "active"
}
```

---

### PUT /me

Update current user profile.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Request Body:**
```json
{
  "first_name": "Jane",
  "last_name": "Smith",
  "phone_number": "+1234567890"
}
```

**Response (200):**
```json
{
  "id": "507f1f77bcf86cd799439011",
  "email": "user@example.com",
  "first_name": "Jane",
  "last_name": "Smith"
}
```

---

### POST /me/change-password

Change current user password.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Request Body:**
```json
{
  "current_password": "OldPassword123!",
  "new_password": "NewSecurePass123!"
}
```

**Response (204):** No content

---

## Related Documentation

- **70-User-Service.md** - UserService API reference
- **80-Auth-Dependencies.md** - AuthDeps dependency injection
- **90-Router-Factories-Overview.md** - Router factories overview

---

**Last Updated:** 2025-01-14
