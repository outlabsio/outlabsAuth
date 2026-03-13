# 24. User Invitations

**Tags**: #authentication #invitations #onboarding #users

Complete guide to the user invitation system in OutlabsAuth.

---

## Overview

The invitation system lets admins onboard users by email without setting a password on their behalf. The invited user receives a token-based link, sets their own password, and their account activates automatically.

**Key characteristics**:
- Invited users are created with `status=INVITED` and no password
- Invite tokens use SHA-256 hashing (same security pattern as password reset tokens)
- Token expiry is configurable (default: 7 days)
- Provider-agnostic delivery — the library generates the token; your app decides how to send it (email, SMS, Slack, etc.)
- Works with both SimpleRBAC and EnterpriseRBAC presets

---

## Configuration

### Enable/Disable

Invitations are **enabled by default**. To disable:

```python
auth = SimpleRBAC(
    database_url="...",
    secret_key="...",
    enable_invitations=False,  # Disables invite endpoints
)
```

### Token Expiry

Control how long invite tokens remain valid:

```python
auth = SimpleRBAC(
    database_url="...",
    secret_key="...",
    invite_token_expire_days=14,  # Default: 7
)
```

### Config Detection

The `/v1/auth/config` endpoint exposes the invitation feature flag so UIs can show/hide invite functionality:

```json
{
  "preset": "SimpleRBAC",
  "features": {
    "invitations": true,
    "entity_hierarchy": false,
    ...
  }
}
```

---

## How It Works

### Flow

```
Admin calls POST /invite
    |
    v
User created (status=INVITED, no password)
    |
    v
on_after_invite hook fires with plain token
    |
    v
App sends link: {base_url}/accept-invite?token={token}
    |
    v
User visits link, sets password via POST /accept-invite
    |
    v
Account activated (status=ACTIVE, email_verified=true)
    |
    v
User can now login normally
```

### Token Security

Invite tokens follow the same security model as password reset tokens:

1. A cryptographically random token is generated (`secrets.token_urlsafe(32)`)
2. The SHA-256 hash is stored in the database (`invite_token` column)
3. The plain token is returned to the caller (never stored)
4. On acceptance, the plain token is hashed and matched against the database
5. Tokens are single-use and cleared after acceptance

---

## API Endpoints

### 1. Invite User

Create an invited user account.

**Endpoint**: `POST /v1/auth/invite`

**Required Permission**: `user:create`

**Request Body**:
```json
{
  "email": "newuser@example.com",
  "first_name": "Jane",
  "last_name": "Smith",
  "role_ids": ["role-uuid-1", "role-uuid-2"],
  "entity_id": "entity-uuid"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `email` | string | Yes | Email address to invite |
| `first_name` | string | No | First name |
| `last_name` | string | No | Last name |
| `role_ids` | string[] | No | Role IDs to assign (EnterpriseRBAC with entity_id) |
| `entity_id` | string | No | Entity to add membership to (EnterpriseRBAC) |

**Response** (201 Created):
```json
{
  "id": "user-uuid",
  "email": "newuser@example.com",
  "first_name": "Jane",
  "last_name": "Smith",
  "status": "invited",
  "email_verified": false,
  "is_superuser": false
}
```

**Error Responses**:
- `401 Unauthorized`: Not authenticated
- `403 Forbidden`: Missing `user:create` permission
- `409 Conflict`: Email already exists

**Notes**:
- If `entity_id` is provided, the user is added as a member of that entity with the specified roles
- The plain invite token is **not** returned in the HTTP response — it is passed to the `on_after_invite` hook instead (see [Sending the Invite](#sending-the-invite))

---

### 2. Accept Invite

Accept an invitation by setting a password. This is a **public endpoint** (no authentication required).

**Endpoint**: `POST /v1/auth/accept-invite`

**Request Body**:
```json
{
  "token": "the-plain-token-from-invite-link",
  "new_password": "SecurePassword123!"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `token` | string | Yes | Plain invite token from the invite link |
| `new_password` | string | Yes | Password (min 8 chars, validated against password policy) |

**Response** (200 OK):
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 900
}
```

The response includes JWT tokens so the user can be auto-logged in after accepting.

**Error Responses**:
- `400 Bad Request`: Invalid token or password doesn't meet policy
- `401 Unauthorized`: Token expired
- `409 Conflict`: Invitation already accepted (user is no longer INVITED)

**What happens on accept**:
1. User status changes from `INVITED` to `ACTIVE`
2. Password is hashed and stored
3. `email_verified` is set to `true`
4. Invite token fields are cleared
5. `user.invite_accepted` notification is emitted

---

### 3. Resend Invite

Regenerate the invite token for a user who hasn't accepted yet.

**Endpoint**: `POST /v1/users/{user_id}/resend-invite`

**Required Permission**: `user:update`

**Response** (200 OK):
```json
{
  "id": "user-uuid",
  "email": "newuser@example.com",
  "status": "invited",
  ...
}
```

**Error Responses**:
- `400 Bad Request`: User is not in `INVITED` status
- `401 Unauthorized`: Not authenticated
- `403 Forbidden`: Missing `user:update` permission
- `404 Not Found`: User not found

**Notes**:
- Invalidates the previous token (only the latest token works)
- Triggers the `on_after_invite` hook again with the new token
- Only works for users with `status=INVITED`

---

## Sending the Invite

The library generates tokens but **does not send emails**. Your application decides how to deliver the invite link using the `on_after_invite` lifecycle hook.

### Using the Lifecycle Hook

Override `on_after_invite` on your UserService subclass:

```python
from outlabs_auth import SimpleRBAC

class MyUserService(SimpleRBAC.user_service.__class__):
    async def on_after_invite(self, user, token, request=None):
        invite_url = f"https://myapp.com/accept-invite?token={token}"

        # Option 1: Send via email
        await send_email(
            to=user.email,
            subject="You've been invited!",
            body=f"Click here to join: {invite_url}",
        )

        # Option 2: Log for development
        print(f"Invite link for {user.email}: {invite_url}")
```

### Using the Notification Service

If you have a `NotificationService` configured, the `user.invited` event is automatically emitted. Any channel subscribed to that event will receive it:

```python
auth = SimpleRBAC(
    database_url="...",
    secret_key="...",
    notification_service=my_notification_service,
)

# The notification service receives:
# event: "user.invited"
# data: { user_id, email, first_name, last_name, invited_by_id, created_at }
```

Configure your notification channels to handle `user.invited` and `user.invite_accepted` events.

---

## Database Schema

The invitation system adds three columns to the `users` table:

| Column | Type | Description |
|--------|------|-------------|
| `invite_token` | `VARCHAR(255)` | SHA-256 hash of the invite token |
| `invite_token_expires` | `TIMESTAMP WITH TIME ZONE` | Token expiration datetime |
| `invited_by_id` | `UUID` (FK → users.id) | Who sent the invitation |

**Migration**: `20260313_0001_add_invite_fields_to_users.py`

Run migrations:
```bash
uv run outlabs-auth migrate upgrade head
```

Or with `auto_migrate=True`:
```python
auth = SimpleRBAC(
    database_url="...",
    secret_key="...",
    auto_migrate=True,
)
```

---

## User Status: INVITED

The `INVITED` status is a distinct user state:

| Status | Can Authenticate? | Has Password? | Description |
|--------|-------------------|---------------|-------------|
| `ACTIVE` | Yes | Yes | Normal account |
| `INVITED` | No | No | Awaiting password setup |
| `SUSPENDED` | No | Yes | Temporarily disabled |
| `BANNED` | No | Yes | Permanently disabled |
| `DELETED` | No | Yes | Soft-deleted |

An `INVITED` user who tries to log in directly receives:

> "Account has not been activated yet. Please check your email for the invitation link."

---

## Admin UI Integration

The admin UI automatically detects the invitations feature via `/v1/auth/config` and:

1. **EntityMemberAddModal** — Shows a third "Invite" tab alongside "Existing User" and "Create New"
   - Email field (required) + optional first/last name
   - No password field
   - Info banner: "They'll receive a link to set their password"
   - When search returns no results, shows "Invite this person instead" link

2. **Accept Invite page** (`/accept-invite?token=xxx`) — Public page where invited users set their password
   - Password + confirm password with match validation
   - Success state redirects to login

---

## Notification Events

| Event | When | Data |
|-------|------|------|
| `user.invited` | User invited | `user_id`, `email`, `first_name`, `last_name`, `invited_by_id`, `created_at` |
| `user.invite_accepted` | Invite accepted | `user_id`, `email`, `accepted_at` |

---

## Complete Example

### Backend Setup

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from outlabs_auth import SimpleRBAC
from outlabs_auth.routers import get_auth_router, get_users_router

auth = SimpleRBAC(
    database_url="postgresql+asyncpg://...",
    secret_key="your-secret",
    enable_invitations=True,          # Default
    invite_token_expire_days=7,       # Default
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await auth.initialize()
    yield
    await auth.shutdown()

app = FastAPI(lifespan=lifespan)
auth.instrument_fastapi(app)

# Mount routers — invite endpoints are included automatically
app.include_router(get_auth_router(auth, prefix="/v1/auth"))
app.include_router(get_users_router(auth, prefix="/v1/users"))
```

### Sending Invites (curl)

```bash
# 1. Invite a user
curl -X POST http://localhost:8000/v1/auth/invite \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"email": "newuser@example.com", "first_name": "Jane"}'

# Response: { "id": "...", "status": "invited", ... }
# The on_after_invite hook fires with the plain token

# 2. Accept the invite (public endpoint)
curl -X POST http://localhost:8000/v1/auth/accept-invite \
  -H "Content-Type: application/json" \
  -d '{"token": "the-token-from-hook", "new_password": "SecurePass123!"}'

# Response: { "access_token": "...", "refresh_token": "...", ... }

# 3. Resend if needed
curl -X POST http://localhost:8000/v1/users/{user_id}/resend-invite \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Development Tip

During development, log the invite token to the console:

```python
class DevUserService(auth.user_service.__class__):
    async def on_after_invite(self, user, token, request=None):
        print(f"\n{'='*60}")
        print(f"INVITE TOKEN for {user.email}")
        print(f"URL: http://localhost:3000/accept-invite?token={token}")
        print(f"{'='*60}\n")

auth.user_service.__class__ = DevUserService
```

---

## Related Documentation

- **48-User-Status-System.md**: Full status lifecycle including INVITED
- **22-JWT-Tokens.md**: Token authentication after invite acceptance
- **23-User-Management-API.md**: User CRUD and role management
- **12-Data-Models.md**: Database models
- **97-Observability.md**: Monitoring invitation events
