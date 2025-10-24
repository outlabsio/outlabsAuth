# User Status System

**Decision**: DD-048
**Date**: 2025-01-24
**Status**: Active

---

## Overview

OutlabsAuth uses a simple, clear user status system with 4 statuses that control authentication access. This document defines the semantics and behavior of each status.

---

## Design Philosophy

**Core Principle**: User status is an **authentication concern**, not a business logic concern.

The status field answers one question: **Can this user authenticate?**

- ✅ **ACTIVE** → Yes
- ❌ **SUSPENDED** → No (temporarily)
- ❌ **BANNED** → No (permanently)
- ❌ **DELETED** → No (soft-deleted)

Other concerns (email verification, inactivity tracking, policy violations) are handled through separate fields or application logic.

---

## User Status Enum

```python
from enum import Enum

class UserStatus(str, Enum):
    """User account status controlling authentication access"""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    BANNED = "banned"
    DELETED = "deleted"
```

---

## Status Definitions

### 1. ACTIVE

**Can authenticate**: ✅ Yes

**Description**: Normal, active user account with full authentication access.

**Use Cases**:
- Standard user accounts
- Default status for newly created users
- Users who have passed email verification (if required)

**Behavior**:
- Can login with email/password
- Can use API keys
- Can refresh access tokens
- All permissions apply normally

**Transitions**:
- Can be changed to SUSPENDED (temporary block)
- Can be changed to BANNED (permanent block)
- Can be changed to DELETED (soft delete)

---

### 2. SUSPENDED

**Can authenticate**: ❌ No

**Description**: Temporarily blocked account that can be reactivated.

**Use Cases**:
- Temporary ban for policy violation (e.g., "banned for 7 days")
- Payment/subscription issues (e.g., "account suspended until payment resolved")
- Under investigation (e.g., "suspicious activity detected")
- Cooling-off period after multiple warnings

**Behavior**:
- Cannot login - raises `AccountInactiveError`
- All existing tokens remain valid until expiration (refresh tokens should be revoked on suspension)
- API keys do not work
- Can be manually reactivated to ACTIVE by admin
- Can be auto-reactivated if `suspended_until` date passes (application logic)

**Related Fields**:
```python
suspended_until: Optional[datetime] = None  # Optional auto-expiry
```

**Error Response**:
```json
{
  "detail": "Account is suspended until 2025-02-01T00:00:00Z",
  "status": "suspended",
  "suspended_until": "2025-02-01T00:00:00Z"
}
```

**Transitions**:
- Can be changed to ACTIVE (reactivation)
- Can be changed to BANNED (escalation)
- Can be changed to DELETED (user deletion)

**Best Practices**:
- Always set `suspended_until` if suspension is temporary
- Revoke all refresh tokens when suspending user
- Consider blacklisting active access tokens if immediate revocation needed (requires Redis)
- Log suspension reason in audit log

---

### 3. BANNED

**Can authenticate**: ❌ No

**Description**: Permanently blocked account for security or severe policy violations.

**Use Cases**:
- Security threat detected (e.g., "account compromised")
- Fraud detected (e.g., "payment fraud")
- Severe Terms of Service violation (e.g., "harassment, illegal content")
- Repeated policy violations after multiple suspensions

**Behavior**:
- Cannot login - raises `AccountInactiveError`
- All existing tokens remain valid until expiration (should be revoked immediately)
- API keys do not work
- Intended to be permanent (but can be manually changed if appeal successful)

**Error Response**:
```json
{
  "detail": "Account is permanently banned",
  "status": "banned"
}
```

**Transitions**:
- Rarely changed (intended to be permanent)
- Can be changed to ACTIVE (only after appeal review)
- Can be changed to DELETED (data cleanup)

**Best Practices**:
- Revoke ALL refresh tokens immediately
- Revoke ALL active API keys
- Consider blacklisting current access token (requires Redis)
- Log ban reason in audit log with detailed context
- Store ban reason in `metadata` field for record-keeping

```python
user.status = UserStatus.BANNED
user.metadata["ban_reason"] = "Fraud detected: multiple chargebacks"
user.metadata["banned_at"] = datetime.now(timezone.utc).isoformat()
user.metadata["banned_by"] = admin_user_id
```

---

### 4. DELETED

**Can authenticate**: ❌ No

**Description**: Soft-deleted account for data retention and audit compliance.

**Use Cases**:
- User requested account deletion (e.g., "delete my account")
- GDPR "right to be forgotten" with retention period (e.g., "keep 30 days for legal compliance")
- Compliance requirements (e.g., "audit log retention")
- Account recovery grace period (e.g., "30-day recovery window")

**Behavior**:
- Cannot login - raises `AccountInactiveError`
- All data remains in database
- Can be hard-deleted (permanently) after retention period
- Can be restored to ACTIVE if within recovery period

**Related Fields**:
```python
deleted_at: Optional[datetime] = None  # Soft delete timestamp
```

**Error Response**:
```json
{
  "detail": "Account has been deleted",
  "status": "deleted",
  "deleted_at": "2025-01-15T10:30:00Z"
}
```

**Transitions**:
- Can be changed to ACTIVE (account recovery)
- Eventually hard-deleted (purged from database) after retention period

**Best Practices**:
- Always set `deleted_at` timestamp
- Revoke all refresh tokens
- Revoke all API keys
- Set retention period based on compliance requirements (30-90 days typical)
- Use background job to hard-delete after retention period

```python
# Soft delete
user.status = UserStatus.DELETED
user.deleted_at = datetime.now(timezone.utc)
await user.save()

# Hard delete after retention period (e.g., 30 days later)
retention_cutoff = datetime.now(timezone.utc) - timedelta(days=30)
deleted_users = await UserModel.find(
    UserModel.status == UserStatus.DELETED,
    UserModel.deleted_at < retention_cutoff
).to_list()

for user in deleted_users:
    await user.delete()  # Permanent deletion
```

---

## Authentication Logic

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
    if user.status == UserStatus.SUSPENDED:
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
│  ACTIVE │  ◄── Default status for new users
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

### Security Tests
- Verify non-ACTIVE users cannot bypass with valid tokens
- Verify status checks happen before password verification
- Verify all token revocation on suspension/ban/deletion

---

## See Also

- [Data Models](./12-Data-Models.md) - Full UserModel definition
- [Email/Password Authentication](./21-Email-Password-Auth.md) - Login flow
- [JWT Tokens](./22-JWT-Tokens.md) - Token revocation strategies
- [Design Decisions](./DESIGN_DECISIONS.md) - DD-048 summary

---

**Last Updated**: 2025-01-24
**Status**: Implementation Complete
