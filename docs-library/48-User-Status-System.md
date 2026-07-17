# User Status System

> **Handbook** · What each user status means for login and admin flows.  
> Part of the [OutlabsAuth Handbook](./README.md). Related:
> [User Invitations](./24-User-Invitations.md),
> [User Management API](./23-User-Management-API.md).

## Overview

Status answers one question: **can this user authenticate?**

| Status | Can log in? | Typical meaning |
|--------|-------------|-----------------|
| `active` | Yes | Normal account |
| `invited` | No | Invite sent; password not set yet |
| `suspended` | No | Temporary block |
| `banned` | No | Permanent block |
| `deleted` | No | Soft-deleted |

Email verification, inactivity, and product policy live in **other** fields —
do not overload `status` for those.

```python
from outlabs_auth.models.sql.enums import UserStatus  # or your import path

# active | invited | suspended | banned | deleted
```

---

## Status definitions

### ACTIVE

**Can authenticate:** yes

Normal account with full authentication access.

**Behavior:** email/password login, API keys, refresh — permissions apply as usual.

**Transitions:** → suspended, banned, or deleted (admin).

---

### INVITED

**Can authenticate:** no

Created via `POST /v1/auth/invite`. No password yet; invite token fields are set.

**Behavior:** login raises an inactive-account error pointing the user at the invite email.

**Transitions:** → active on `POST /v1/auth/accept-invite`; admin may delete/cancel.

Resend: `POST /v1/users/{id}/resend-invite`. Details: [User Invitations](./24-User-Invitations.md).

---

### SUSPENDED

**Can authenticate:** no

Temporarily blocked; can be reactivated.

**Behavior:** login denied; revoke refresh tokens on suspend; API keys should not work. Optional `suspended_until` for auto-reactivation in host logic.

**Transitions:** → active, banned, or deleted.

---

### BANNED

**Can authenticate:** no

Permanent block for severe policy or security issues. Revoke refresh tokens and API keys immediately. Rarely reversed (appeal → active, or → deleted).

---

### DELETED

**Can authenticate:** no

Soft delete for retention / recovery windows. Restore via `POST /v1/users/{id}/restore` when your product allows it; hard-delete later per your retention policy (`deleted_at` is set).

---

## Authentication logic

### can_authenticate() Method

```python
def can_authenticate(self) -> bool:
    """
    Check if user can authenticate.

    Returns True only if:
    - Status is ACTIVE (not suspended/banned/deleted)
    - Account is not locked (from failed login attempts)

    Note: Email verification is checked separately by application logic if needed.
    """
    return (
        self.status == UserStatus.ACTIVE
        and not self.is_locked
    )
```

### Login Flow

```python
# In AuthService.login()
user = await UserModel.find_one(UserModel.email == email)

# Check status BEFORE password verification
if user.status != UserStatus.ACTIVE:
    # Raise specific error based on status
    if user.status == UserStatus.INVITED:
        raise AccountInactiveError("Account has not been activated yet...")
    elif user.status == UserStatus.SUSPENDED:
        raise AccountInactiveError("Account is suspended...")
    elif user.status == UserStatus.BANNED:
        raise AccountInactiveError("Account is permanently banned")
    elif user.status == UserStatus.DELETED:
        raise AccountInactiveError("Account has been deleted")
```

---

## Related Fields

### Account Lockout (Separate from Status)

**Purpose**: Temporary lockout after too many failed login attempts.

```python
failed_login_attempts: int = Field(default=0)
locked_until: Optional[datetime] = None

@property
def is_locked(self) -> bool:
    """Check if account is temporarily locked"""
    if self.locked_until:
        return datetime.now(timezone.utc) < self.locked_until
    return False
```

**Key Difference**:
- Status = Admin-controlled, persistent state
- Lockout = Automatic, temporary security measure

A user can be ACTIVE but locked (too many failed attempts).
A user can be SUSPENDED and locked (both restrictions apply).

### Email Verification (Separate from Status)

**Purpose**: Track email verification state.

```python
email_verified: bool = Field(default=False)
```

**Key Difference**:
- Status controls authentication access
- Email verification is a separate check (application decides if required)

An application might allow unverified ACTIVE users to login but with limited permissions.

---

## Status Transitions

```
┌─────────┐
│ INVITED │  ◄── Created via POST /v1/auth/invite
└────┬────┘
     │
     └──► ACTIVE (user accepts invite and sets password)

┌─────────┐
│  ACTIVE │  ◄── Default status for new users / accepted invites
└────┬────┘
     │
     ├──► SUSPENDED  (temporary block)
     │        │
     │        └──► ACTIVE (reactivation)
     │        └──► BANNED (escalation)
     │
     ├──► BANNED (permanent block)
     │        │
     │        └──► ACTIVE (rare: after appeal)
     │
     └──► DELETED (soft delete)
              │
              ├──► ACTIVE (recovery)
              └──► [HARD DELETE] (after retention period)
```

---

## Removed Statuses (Previously Considered)

### INACTIVE
**Why removed**: Too vague. Could mean:
- Not logged in recently (business logic, not auth)
- Email not verified (separate field: `email_verified`)
- Temporarily disabled (use SUSPENDED instead)

### TERMINATED
**Why removed**: Redundant with DELETED. Both mean the same thing (soft delete).

---

## Examples

### Example 1: Temporary Suspension with Auto-Expiry

```python
from datetime import datetime, timedelta, timezone

# Suspend user for 7 days
user.status = UserStatus.SUSPENDED
user.suspended_until = datetime.now(timezone.utc) + timedelta(days=7)
await user.save()

# Revoke all sessions
await auth.auth_service.revoke_all_user_tokens(str(user.id))

# Application logic to auto-reactivate (e.g., background job)
async def check_expired_suspensions():
    now = datetime.now(timezone.utc)
    suspended_users = await UserModel.find(
        UserModel.status == UserStatus.SUSPENDED,
        UserModel.suspended_until < now
    ).to_list()

    for user in suspended_users:
        user.status = UserStatus.ACTIVE
        user.suspended_until = None
        await user.save()
```

### Example 2: Permanent Ban with Reason

```python
# Ban user with detailed logging
user.status = UserStatus.BANNED
user.metadata["ban_reason"] = "Repeated ToS violations"
user.metadata["banned_at"] = datetime.now(timezone.utc).isoformat()
user.metadata["banned_by_user_id"] = admin_user_id
user.metadata["ban_context"] = {
    "violations": ["spam", "harassment"],
    "warning_count": 3,
    "final_incident": "harassment_complaint_2025_01_24"
}
await user.save()

# Immediate revocation
await auth.auth_service.revoke_all_user_tokens(str(user.id))

# Revoke API keys
api_keys = await auth.api_key_service.list_user_keys(str(user.id))
for key in api_keys:
    await auth.api_key_service.revoke_key(str(key.id))
```

### Example 3: Soft Delete with Recovery Period

```python
# User requests account deletion
user.status = UserStatus.DELETED
user.deleted_at = datetime.now(timezone.utc)
await user.save()

# Revoke all tokens
await auth.auth_service.revoke_all_user_tokens(str(user.id))

# 30-day recovery window (application logic)
async def recover_account(user_id: str, verification_token: str):
    user = await UserModel.get(user_id)

    if user.status != UserStatus.DELETED:
        raise ValueError("Account is not deleted")

    # Check within recovery period
    recovery_deadline = user.deleted_at + timedelta(days=30)
    if datetime.now(timezone.utc) > recovery_deadline:
        raise ValueError("Recovery period expired")

    # Verify token and recover
    user.status = UserStatus.ACTIVE
    user.deleted_at = None
    await user.save()

# Hard delete after retention period (background job)
async def purge_old_deleted_accounts():
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    deleted_users = await UserModel.find(
        UserModel.status == UserStatus.DELETED,
        UserModel.deleted_at < cutoff
    ).to_list()

    for user in deleted_users:
        # Optionally export for backup before deletion
        await export_user_data(user)

        # Hard delete
        await user.delete()
```

---

## API Error Responses

### ACTIVE User (Success)
```http
POST /auth/login
{
  "email": "user@example.com",
  "password": "password123"
}

Response: 200 OK
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 900
}
```

### INVITED User
```http
Response: 403 Forbidden
{
  "detail": "Account has not been activated yet. Please check your email for the invitation link.",
  "error_code": "ACCOUNT_INACTIVE",
  "status": "invited"
}
```

### SUSPENDED User
```http
Response: 403 Forbidden
{
  "detail": "Account is suspended until 2025-02-01T00:00:00Z",
  "error_code": "ACCOUNT_INACTIVE",
  "status": "suspended",
  "suspended_until": "2025-02-01T00:00:00Z"
}
```

### BANNED User
```http
Response: 403 Forbidden
{
  "detail": "Account is permanently banned",
  "error_code": "ACCOUNT_INACTIVE",
  "status": "banned"
}
```

### DELETED User
```http
Response: 403 Forbidden
{
  "detail": "Account has been deleted",
  "error_code": "ACCOUNT_INACTIVE",
  "status": "deleted",
  "deleted_at": "2025-01-15T10:30:00Z"
}
```

---

## Testing Considerations

### Unit Tests
- Test `can_authenticate()` for all status values
- Test status transitions
- Test `is_locked` property separate from status

### Integration Tests
- Test login with each status
- Test token refresh with suspended/banned/deleted users
- Test API key authentication with non-active users
- Test status changes during active session

### Invitation Tests
- Test invite creates user with INVITED status and no password
- Test accept_invite activates user and sets password
- Test expired invite tokens are rejected
- Test resend_invite regenerates token

### Security Tests
- Verify non-ACTIVE users cannot bypass with valid tokens
- Verify status checks happen before password verification
- Verify all token revocation on suspension/ban/deletion
- Verify INVITED users cannot login directly

---

## See Also

- [Data Models](./12-Data-Models.md) - Full UserModel definition
- [User Invitations](./24-User-Invitations.md) - Invitation system details
- [JWT Tokens](./22-JWT-Tokens.md) - Token revocation strategies
- [Design Decisions](./DESIGN_DECISIONS.md) - DD-048 summary

---

**Last Updated**: 2026-03-13
**Status**: Implementation Complete
