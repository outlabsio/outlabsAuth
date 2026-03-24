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
- Provider-agnostic delivery — the library generates the token and emits a typed mail intent; your app decides how to brand and send it
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
Transactional mail service receives invite intent
    |
    v
Host app composes branded message + chooses provider
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
- The plain invite token is **not** returned in the HTTP response — it is passed to the configured transactional mail service (or, if you keep custom hooks, to `on_after_invite`) instead

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
- Triggers the transactional mail service again with the new token
- Only works for users with `status=INVITED`

---

## Sending the Invite

The library generates tokens but **does not own your branded email copy or delivery provider**. The recommended integration is to inject a transactional mail service into `OutlabsAuth`, let the host app compose the message, and let a provider adapter deliver it.

### Recommended Model

Split responsibilities this way:

- **OutlabsAuth** owns the auth event, token lifecycle, and typed invite/reset intents
- **Host app** owns copy, branding, template selection, and provider policy
- **Provider adapter** owns the actual delivery transport

OutlabsAuth ships the primitives for this under `outlabs_auth.mail`:

- `AuthMailComposer`
- `DefaultAuthMailComposer`
- `ComposedAuthMailService`
- `SMTPMailProvider`
- `SendGridMailProvider`
- `MailgunMailProvider`
- `WebhookMailProvider`

### Example: Inject a Transactional Mail Service

```python
from outlabs_auth import EnterpriseRBAC
from outlabs_auth.mail import (
    ComposedAuthMailService,
    DefaultAuthMailComposer,
    MailgunMailProvider,
)

mail_service = ComposedAuthMailService(
    provider=MailgunMailProvider(
        api_key="mailgun-api-key",
        domain="mg.example.com",
        from_email="auth@example.com",
        from_name="Example Auth",
    ),
    composer=DefaultAuthMailComposer(
        app_name="Example Auth",
        invite_url_builder=lambda token: f"https://app.example.com/accept-invite?token={token}",
        password_reset_url_builder=lambda token: f"https://app.example.com/reset-password?token={token}",
        login_url_builder=lambda: "https://app.example.com/login",
        support_email="support@example.com",
    ),
)

auth = EnterpriseRBAC(
    database_url="postgresql+asyncpg://...",
    secret_key="your-secret",
    transactional_mail_service=mail_service,
)
```

### Host-Owned Branding

For production apps, it is common to replace `DefaultAuthMailComposer` with a host-specific composer that:

- renders local Jinja/React/provider templates
- chooses subjects and copy
- injects tenant or product branding
- uses provider-hosted template IDs when appropriate

The Enterprise example demonstrates this pattern in:

- [examples/enterprise_rbac/transactional_mail.py](../examples/enterprise_rbac/transactional_mail.py)

### Provider-Hosted Templates

`AuthMailMessage` supports both rendered bodies and provider-hosted templates:

- rendered mode: `subject`, `text_body`, `html_body`
- provider-template mode: `provider_template_id` + `template_data`

That allows one host app to use SMTP with locally rendered HTML, another to use SendGrid dynamic templates, and another to use Mailgun templates, all without changing auth logic.

### Notification Service vs Transactional Mail

If you have a `NotificationService` configured, the `user.invited` event is still emitted. That event is useful for analytics, audit, or fan-out workflows, but it does **not** carry the plain invite token, so it is not enough on its own to generate the invite URL.

Any notification channel subscribed to `user.invited` will receive:

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

### Lifecycle Hooks Are Still Available

You can still override `on_after_invite` or `send_invitation_email()` if you need a custom path, but that is now the escape hatch, not the primary integration model. The default `UserService` will call the configured transactional mail service when one is present.

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
from outlabs_auth.mail import (
    ComposedAuthMailService,
    DefaultAuthMailComposer,
    SMTPMailProvider,
)
from outlabs_auth.routers import get_auth_router, get_users_router

mail_service = ComposedAuthMailService(
    provider=SMTPMailProvider(
        host="smtp.example.com",
        port=587,
        user="apikey",
        password="smtp-or-provider-api-key",
        from_email="auth@example.com",
        from_name="Example Auth",
    ),
    composer=DefaultAuthMailComposer(
        app_name="Example Auth",
        invite_url_builder=lambda token: f"https://app.example.com/accept-invite?token={token}",
        password_reset_url_builder=lambda token: f"https://app.example.com/reset-password?token={token}",
        login_url_builder=lambda: "https://app.example.com/login",
        support_email="support@example.com",
    ),
)

auth = SimpleRBAC(
    database_url="postgresql+asyncpg://...",
    secret_key="your-secret",
    enable_invitations=True,          # Default
    invite_token_expire_days=7,       # Default
    transactional_mail_service=mail_service,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await auth.initialize()
    yield
    await auth.shutdown()

app = FastAPI(lifespan=lifespan)
auth.instrument_fastapi(
    app,
    exception_handler_mode="global",
    include_metrics=True,
    include_correlation_id=True,
)

# Mount routers — invite endpoints are included automatically
app.include_router(get_auth_router(auth, prefix="/v1/auth"))
app.include_router(get_users_router(auth, prefix="/v1/users"))
```

For an embedded host API that already owns logging, middleware, and `/metrics`,
keep those host surfaces in place and either skip `instrument_fastapi()` or use
its safe defaults instead of the standalone configuration above.

### Sending Invites (curl)

```bash
# 1. Invite a user
curl -X POST http://localhost:8000/v1/auth/invite \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"email": "newuser@example.com", "first_name": "Jane"}'

# Response: { "id": "...", "status": "invited", ... }
# The configured transactional mail service receives the plain token

# 2. Accept the invite (public endpoint)
curl -X POST http://localhost:8000/v1/auth/accept-invite \
  -H "Content-Type: application/json" \
  -d '{"token": "the-token-from-email", "new_password": "SecurePass123!"}'

# Response: { "access_token": "...", "refresh_token": "...", ... }

# 3. Resend if needed
curl -X POST http://localhost:8000/v1/users/{user_id}/resend-invite \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Development Tip

During development, use a console provider instead of a real mail vendor:

```python
from outlabs_auth.mail import ComposedAuthMailService

class ConsoleProvider:
    provider_name = "console"

    async def send(self, message):
        print(f"\n{'='*60}")
        print(f"TO: {message.to_email}")
        print(f"SUBJECT: {message.subject}")
        print(message.text_body)
        print(f"{'='*60}\n")
        return type("Result", (), {"accepted": True})()

mail_service = ComposedAuthMailService(
    provider=ConsoleProvider(),
    composer=DefaultAuthMailComposer(
        app_name="Example Auth",
        invite_url_builder=lambda token: f"http://localhost:3000/accept-invite?token={token}",
        password_reset_url_builder=lambda token: f"http://localhost:3000/reset-password?token={token}",
    ),
)
```

---

## Related Documentation

- **48-User-Status-System.md**: Full status lifecycle including INVITED
- **22-JWT-Tokens.md**: Token authentication after invite acceptance
- **23-User-Management-API.md**: User CRUD and role management
- **12-Data-Models.md**: Database models
- **97-Observability.md**: Monitoring invitation events
