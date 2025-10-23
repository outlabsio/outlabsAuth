# 90-Router-Factories-Overview.md - Router Factories Overview

Overview of **pre-built FastAPI routers** for rapid application development.

---

## Overview

OutlabsAuth provides **router factory functions** that generate pre-configured FastAPI routers with authentication and authorization routes.

### Available Routers

| Router | Function | Routes | Description |
|--------|----------|--------|-------------|
| **Auth Router** | `get_auth_router()` | `/login`, `/logout`, `/refresh` | Authentication endpoints |
| **Users Router** | `get_users_router()` | `/me`, `/me/password`, etc. | User profile management |
| **API Keys Router** | `get_api_keys_router()` | `/api-keys`, `/api-keys/{id}` | API key management |
| **OAuth Router** | `get_oauth_router()` | `/oauth/{provider}`, `/oauth/callback` | OAuth login |
| **OAuth Associate** | `get_oauth_associate_router()` | `/oauth/associate/{provider}` | Link OAuth accounts |

---

## Quick Start

```python
from fastapi import FastAPI
from outlabs_auth import SimpleRBAC
from outlabs_auth.routers import (
    get_auth_router,
    get_users_router,
    get_api_keys_router
)

app = FastAPI()
auth = SimpleRBAC(database=db, secret_key="...")

# Include pre-built routers
app.include_router(get_auth_router(auth), prefix="/auth", tags=["auth"])
app.include_router(get_users_router(auth), prefix="/users", tags=["users"])
app.include_router(get_api_keys_router(auth), prefix="/api-keys", tags=["api-keys"])
```

---

## Router Details

### get_auth_router()

Authentication endpoints (login, logout, refresh).

**Routes:**
- `POST /login` - Login with email/password
- `POST /logout` - Logout (revoke refresh token)
- `POST /refresh` - Refresh access token

**See:** **91-Auth-Router.md**

---

### get_users_router()

User profile management.

**Routes:**
- `GET /me` - Get current user
- `PUT /me` - Update profile
- `POST /me/change-password` - Change password

**See:** **92-Users-Router.md**

---

### get_api_keys_router()

API key management (requires `enable_api_keys=True`).

**Routes:**
- `GET /api-keys` - List user's API keys
- `POST /api-keys` - Create new API key
- `DELETE /api-keys/{id}` - Revoke API key

**See:** **93-API-Keys-Router.md**

---

### get_oauth_router()

OAuth/social login (requires `enable_oauth=True`).

**Routes:**
- `GET /oauth/{provider}` - Start OAuth flow
- `GET /oauth/callback` - OAuth callback

**See:** **94-OAuth-Router.md**

---

### get_oauth_associate_router()

Link OAuth accounts to existing users.

**Routes:**
- `GET /oauth/associate/{provider}` - Link account
- `GET /oauth/associate/callback` - Association callback

**See:** **95-OAuth-Associate-Router.md**

---

## Customization

All routers support customization via parameters:

```python
# Custom prefix and tags
app.include_router(
    get_auth_router(auth),
    prefix="/api/v1/auth",
    tags=["authentication"]
)

# Custom dependencies
from fastapi import Depends

async def rate_limit():
    # Your rate limiting logic
    pass

app.include_router(
    get_auth_router(auth),
    prefix="/auth",
    dependencies=[Depends(rate_limit)]
)
```

---

## Related Documentation

- **91-Auth-Router.md** - Auth router reference
- **92-Users-Router.md** - Users router reference
- **93-API-Keys-Router.md** - API keys router reference
- **94-OAuth-Router.md** - OAuth router reference
- **95-OAuth-Associate-Router.md** - OAuth associate router reference

---

**Last Updated:** 2025-01-14
