# 70-User-Service.md - UserService API Reference

Complete API reference for the **UserService** - user management and profile operations.

---

## Table of Contents

1. [Overview](#overview)
2. [Accessing UserService](#accessing-userservice)
3. [User Management Methods](#user-management-methods)
4. [Profile Management](#profile-management)
5. [Status Management](#status-management)
6. [Search and Listing](#search-and-listing)
7. [Security Operations](#security-operations)
8. [Lifecycle Hooks](#lifecycle-hooks)
9. [Error Handling](#error-handling)
10. [Complete Examples](#complete-examples)

---

## Overview

**UserService** handles all user-related operations including:

- ✅ User creation and registration
- ✅ Profile management (name, phone, avatar)
- ✅ Password management
- ✅ Status management (active, suspended, banned)
- ✅ User listing and search
- ✅ Email verification
- ✅ Security features (account lockout, failed attempts)
- ✅ Lifecycle hooks for custom logic

### User Model Fields

```python
class UserModel:
    # Authentication
    email: str               # Unique email (indexed)
    hashed_password: str     # argon2id hashed password
    auth_methods: list[str]  # ["PASSWORD", "GOOGLE", ...]

    # Profile
    profile: UserProfile     # first_name, last_name, phone, avatar_url

    # Status
    status: UserStatus       # ACTIVE, INACTIVE, SUSPENDED, BANNED, TERMINATED
    is_superuser: bool       # Admin override
    email_verified: bool     # Email verification status

    # Security
    last_login: datetime
    last_password_change: datetime
    failed_login_attempts: int
    locked_until: datetime

    # Metadata
    metadata: dict           # Additional key-value data
```

### User Status Values

```python
from outlabs_auth.models.user import UserStatus

UserStatus.ACTIVE       # Normal active user
UserStatus.INACTIVE     # Temporarily inactive
UserStatus.SUSPENDED    # Suspended by admin
UserStatus.BANNED       # Permanently banned
UserStatus.TERMINATED   # Account terminated (soft delete)
```

---

## Accessing UserService

### SimpleRBAC

```python
from outlabs_auth import SimpleRBAC

auth = SimpleRBAC(database=db, secret_key="...")
await auth.initialize()

# Access UserService
user_service = auth.user_service
```

### EnterpriseRBAC

```python
from outlabs_auth import EnterpriseRBAC

auth = EnterpriseRBAC(database=db, secret_key="...")
await auth.initialize()

# Access UserService
user_service = auth.user_service
```

---

## User Management Methods

### create_user()

Create a new user account.

```python
user = await auth.user_service.create_user(
    email="john@example.com",
    password="SecurePass123!",
    first_name="John",
    last_name="Doe",
    phone_number="+1234567890",      # Optional
    avatar_url="https://...",         # Optional
    metadata={"department": "eng"},   # Optional
    is_superuser=False,               # Optional (default: False)
    tenant_id=None                    # Optional (multi-tenant)
)
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `email` | `str` | ✅ Yes | User email (normalized to lowercase) |
| `password` | `str` | ✅ Yes | Plain text password (will be hashed) |
| `first_name` | `str` | ✅ Yes | User's first name |
| `last_name` | `str` | ✅ Yes | User's last name |
| `phone_number` | `str` | ❌ No | Phone number |
| `avatar_url` | `str` | ❌ No | Avatar image URL |
| `metadata` | `dict` | ❌ No | Additional user data |
| `is_superuser` | `bool` | ❌ No | Superuser privileges (default: False) |
| `tenant_id` | `str` | ❌ No | Tenant ID for multi-tenant mode |

**Returns:** `UserModel`

**Raises:**
- `UserAlreadyExistsError` - Email already registered
- `InvalidPasswordError` - Password doesn't meet requirements

**Example:**

```python
try:
    user = await auth.user_service.create_user(
        email="alice@example.com",
        password="MySecurePassword123!",
        first_name="Alice",
        last_name="Smith"
    )
    print(f"Created user: {user.email}")
    print(f"User ID: {str(user.id)}")
except UserAlreadyExistsError:
    print("User already exists")
except InvalidPasswordError as e:
    print(f"Invalid password: {e.message}")
```

**Password Requirements:**

- Minimum 8 characters (configurable)
- At least one uppercase letter
- At least one lowercase letter
- At least one digit
- At least one special character

Configure in initialization:

```python
auth = SimpleRBAC(
    database=db,
    secret_key="...",
    min_password_length=12,  # Default: 8
)
```

### get_user_by_id()

Get user by ID.

```python
user = await auth.user_service.get_user_by_id("507f1f77bcf86cd799439011")
if user:
    print(user.email)
else:
    print("User not found")
```

**Parameters:**
- `user_id` (str): User ID

**Returns:** `Optional[UserModel]` - User or `None` if not found

**Example:**

```python
user = await auth.user_service.get_user_by_id(str(current_user.id))
if user:
    print(f"Full name: {user.profile.full_name}")
```

### get_user_by_email()

Get user by email address.

```python
user = await auth.user_service.get_user_by_email("john@example.com")
if user:
    print(f"User ID: {str(user.id)}")
```

**Parameters:**
- `email` (str): User email (case-insensitive)

**Returns:** `Optional[UserModel]` - User or `None` if not found

**Example:**

```python
# Check if user exists before creating
existing = await auth.user_service.get_user_by_email("alice@example.com")
if existing:
    print("User already exists")
else:
    # Create new user
    user = await auth.user_service.create_user(...)
```

### delete_user()

Delete user account (hard delete).

```python
deleted = await auth.user_service.delete_user("507f1f77bcf86cd799439011")
if deleted:
    print("User deleted")
else:
    print("User not found")
```

**Parameters:**
- `user_id` (str): User ID

**Returns:** `bool` - `True` if deleted, `False` if not found

**Warning:** This is a **hard delete** - user data is permanently removed.

**Alternative (Soft Delete):** Use `update_user_status()` with `UserStatus.TERMINATED`:

```python
# Soft delete (recommended)
user = await auth.user_service.update_user_status(
    user_id,
    UserStatus.TERMINATED
)
```

**Example with Confirmation:**

```python
# Delete with confirmation
user = await auth.user_service.get_user_by_id(user_id)
if user:
    if user.is_superuser:
        raise ValueError("Cannot delete superuser")

    # Delete user
    deleted = await auth.user_service.delete_user(user_id)

    # Clean up related data
    if deleted:
        await cleanup_user_data(user_id)  # Your custom cleanup
```

---

## Profile Management

### update_user()

Update user profile information.

```python
user = await auth.user_service.update_user(
    user_id="507f1f77bcf86cd799439011",
    first_name="Jane",              # Optional
    last_name="Smith",              # Optional
    phone_number="+9876543210",     # Optional
    avatar_url="https://...",       # Optional
    metadata={"department": "sales"}  # Optional (merged with existing)
)
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | `str` | ✅ Yes | User ID |
| `first_name` | `str` | ❌ No | Updated first name |
| `last_name` | `str` | ❌ No | Updated last name |
| `phone_number` | `str` | ❌ No | Updated phone number |
| `avatar_url` | `str` | ❌ No | Updated avatar URL |
| `metadata` | `dict` | ❌ No | Additional data (merged with existing) |

**Returns:** `UserModel` - Updated user

**Raises:**
- `UserNotFoundError` - User doesn't exist

**Example:**

```python
# Update only specific fields
user = await auth.user_service.update_user(
    user_id=str(current_user.id),
    first_name="Jane"
)

# Update multiple fields
user = await auth.user_service.update_user(
    user_id=str(current_user.id),
    first_name="Jane",
    last_name="Doe",
    avatar_url="https://cdn.example.com/avatar.jpg",
    metadata={
        "department": "engineering",
        "team": "backend",
        "location": "Remote"
    }
)

print(f"Updated: {user.profile.full_name}")
```

**Note:** Metadata is **merged** with existing metadata, not replaced:

```python
# Initial metadata
user.profile.preferences = {"theme": "dark", "language": "en"}

# Update metadata
await auth.user_service.update_user(
    user_id=str(user.id),
    metadata={"timezone": "UTC"}
)

# Result: {"theme": "dark", "language": "en", "timezone": "UTC"}
```

### change_password()

Change user password.

```python
user = await auth.user_service.change_password(
    user_id="507f1f77bcf86cd799439011",
    new_password="NewSecurePass123!"
)
```

**Parameters:**
- `user_id` (str): User ID
- `new_password` (str): New plain text password (will be hashed)

**Returns:** `UserModel` - Updated user

**Raises:**
- `UserNotFoundError` - User doesn't exist
- `InvalidPasswordError` - Password doesn't meet requirements

**Side Effects:**
- Resets `failed_login_attempts` to 0
- Clears `locked_until` (unlocks account)
- Updates `last_password_change` timestamp
- Emits `user.password_changed` notification

**Example:**

```python
# Change password with validation
try:
    user = await auth.user_service.change_password(
        user_id=str(current_user.id),
        new_password="NewSecurePassword123!"
    )
    print("Password changed successfully")

    # Optional: Log out all sessions
    await auth.auth_service.logout_all_sessions(str(user.id))
except InvalidPasswordError as e:
    print(f"Password error: {e.message}")
```

**Password Change Flow in API:**

```python
from fastapi import Depends, HTTPException
from outlabs_auth.dependencies import AuthDeps

deps = AuthDeps(auth)

@app.post("/users/me/change-password")
async def change_my_password(
    current_password: str,
    new_password: str,
    user = Depends(deps.authenticated())
):
    # Verify current password
    is_valid = auth.verify_password(current_password, user.hashed_password)
    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid current password")

    # Change password
    await auth.user_service.change_password(
        user_id=str(user.id),
        new_password=new_password
    )

    return {"message": "Password changed successfully"}
```

---

## Status Management

### update_user_status()

Update user account status.

```python
from outlabs_auth.models.user import UserStatus

user = await auth.user_service.update_user_status(
    user_id="507f1f77bcf86cd799439011",
    status=UserStatus.SUSPENDED
)
```

**Parameters:**
- `user_id` (str): User ID
- `status` (UserStatus): New status

**Returns:** `UserModel` - Updated user

**Raises:**
- `UserNotFoundError` - User doesn't exist

**Status Values:**

| Status | Description | Can Authenticate? |
|--------|-------------|-------------------|
| `ACTIVE` | Normal active user | ✅ Yes |
| `INACTIVE` | Temporarily inactive | ❌ No |
| `SUSPENDED` | Suspended by admin | ❌ No* |
| `BANNED` | Permanently banned | ❌ No |
| `TERMINATED` | Account terminated | ❌ No |

*Suspended users cannot authenticate, but can be reactivated.

**Example:**

```python
from outlabs_auth.models.user import UserStatus

# Suspend user
user = await auth.user_service.update_user_status(
    user_id=user_id,
    status=UserStatus.SUSPENDED
)
print(f"User suspended: {user.email}")

# Reactivate user
user = await auth.user_service.update_user_status(
    user_id=user_id,
    status=UserStatus.ACTIVE
)
print(f"User reactivated: {user.email}")

# Ban user permanently
user = await auth.user_service.update_user_status(
    user_id=user_id,
    status=UserStatus.BANNED
)
```

**Side Effects:**
- Emits `user.status_changed` notification
- Logs old and new status

**Admin Route Example:**

```python
@app.put("/admin/users/{user_id}/status")
async def update_user_status(
    user_id: str,
    status: UserStatus,
    admin = Depends(deps.requires("user:manage"))
):
    user = await auth.user_service.update_user_status(user_id, status)
    return {
        "user_id": str(user.id),
        "email": user.email,
        "status": user.status.value
    }
```

### verify_email()

Mark user email as verified.

```python
user = await auth.user_service.verify_email("507f1f77bcf86cd799439011")
print(f"Email verified: {user.email_verified}")  # True
```

**Parameters:**
- `user_id` (str): User ID

**Returns:** `UserModel` - Updated user

**Raises:**
- `UserNotFoundError` - User doesn't exist

**Example with Email Verification Flow:**

```python
# 1. User requests verification email
@app.post("/auth/request-verify-email")
async def request_verify_email(user = Depends(deps.authenticated())):
    if user.email_verified:
        raise HTTPException(status_code=400, detail="Email already verified")

    # Generate verification token
    token = await auth.auth_service.create_email_verification_token(str(user.id))

    # Send email (your implementation)
    await email_service.send_verification_email(user.email, token)

    return {"message": "Verification email sent"}

# 2. User clicks link with token
@app.post("/auth/verify-email")
async def verify_email(token: str):
    # Verify token and get user ID
    user_id = await auth.auth_service.verify_email_token(token)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    # Mark email as verified
    user = await auth.user_service.verify_email(user_id)

    return {
        "message": "Email verified successfully",
        "email": user.email
    }
```

---

## Search and Listing

### list_users()

List users with pagination.

```python
users, total = await auth.user_service.list_users(
    page=1,
    limit=20,
    status=UserStatus.ACTIVE,  # Optional filter
    tenant_id=None              # Optional (multi-tenant)
)
```

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `page` | `int` | ❌ No | `1` | Page number (1-indexed) |
| `limit` | `int` | ❌ No | `20` | Results per page |
| `status` | `UserStatus` | ❌ No | `None` | Filter by status |
| `tenant_id` | `str` | ❌ No | `None` | Filter by tenant |

**Returns:** `tuple[list[UserModel], int]` - (users, total_count)

**Example:**

```python
# Get first page
users, total = await auth.user_service.list_users(page=1, limit=10)
print(f"Showing {len(users)} of {total} users")

for user in users:
    print(f"- {user.email} ({user.status.value})")

# Pagination
total_pages = (total + limit - 1) // limit
print(f"Total pages: {total_pages}")

# Filter by status
active_users, active_total = await auth.user_service.list_users(
    page=1,
    limit=50,
    status=UserStatus.ACTIVE
)
print(f"Active users: {active_total}")
```

**API Route Example:**

```python
from pydantic import BaseModel

class UserListResponse(BaseModel):
    users: list[dict]
    total: int
    page: int
    limit: int
    total_pages: int

@app.get("/admin/users", response_model=UserListResponse)
async def list_users(
    page: int = 1,
    limit: int = 20,
    status: Optional[UserStatus] = None,
    admin = Depends(deps.requires("user:list"))
):
    users, total = await auth.user_service.list_users(
        page=page,
        limit=limit,
        status=status
    )

    total_pages = (total + limit - 1) // limit

    return {
        "users": [
            {
                "id": str(u.id),
                "email": u.email,
                "name": u.profile.full_name,
                "status": u.status.value,
                "created_at": u.created_at.isoformat() if u.created_at else None
            }
            for u in users
        ],
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages
    }
```

### search_users()

Search users by email or name.

```python
users = await auth.user_service.search_users(
    search_term="john",
    limit=20
)
```

**Parameters:**
- `search_term` (str): Search query (searches email, first name, last name)
- `limit` (int): Maximum results (default: 20)

**Returns:** `list[UserModel]` - Matching users

**Search Behavior:**
- Case-insensitive
- Partial matches (regex)
- Searches: email, first_name, last_name

**Example:**

```python
# Search by email
users = await auth.user_service.search_users("john@")
for user in users:
    print(user.email)
# Output: john@example.com, johnny@example.com

# Search by name
users = await auth.user_service.search_users("smith")
for user in users:
    print(f"{user.profile.full_name} ({user.email})")
# Output: John Smith (john@example.com), Alice Smith (alice@example.com)

# Search with limit
users = await auth.user_service.search_users("example", limit=5)
print(f"Found {len(users)} users")  # Max 5 results
```

**API Route Example:**

```python
@app.get("/admin/users/search")
async def search_users(
    q: str,
    limit: int = 20,
    admin = Depends(deps.requires("user:list"))
):
    users = await auth.user_service.search_users(q, limit)

    return {
        "results": [
            {
                "id": str(u.id),
                "email": u.email,
                "name": u.profile.full_name,
                "avatar_url": u.profile.avatar_url
            }
            for u in users
        ],
        "count": len(users)
    }
```

---

## Security Operations

### Account Locking

Users are automatically locked after failed login attempts.

**Check if User is Locked:**

```python
user = await auth.user_service.get_user_by_email("john@example.com")
if user.is_locked:
    print(f"Account locked until: {user.locked_until}")
else:
    print("Account not locked")
```

**Unlock Account:**

```python
# Method 1: Change password (automatically unlocks)
await auth.user_service.change_password(user_id, "NewPassword123!")

# Method 2: Manual unlock
user = await UserModel.get(user_id)
user.failed_login_attempts = 0
user.locked_until = None
await user.save()
```

**Lock Configuration:**

```python
auth = SimpleRBAC(
    database=db,
    secret_key="...",
    max_failed_login_attempts=5,     # Default: 5
    account_lockout_duration=900     # Default: 900 seconds (15 min)
)
```

### Check Authentication Status

```python
user = await auth.user_service.get_user_by_email("john@example.com")

# Can user authenticate?
if user.can_authenticate():
    print("User can log in")
else:
    print(f"User cannot log in: status={user.status}, locked={user.is_locked}")
```

**Conditions for `can_authenticate()`:**
- Status is `ACTIVE` or `SUSPENDED`
- Account is not locked (`is_locked == False`)

---

## Lifecycle Hooks

Override hooks to add custom logic at key lifecycle events.

### Available Hooks

| Hook | When Called | Use Cases |
|------|-------------|-----------|
| `on_after_register` | After user creation | Welcome email, analytics, default setup |
| `on_after_login` | After successful login | Track last login, analytics, notifications |
| `on_after_update` | After profile update | Audit log, cache invalidation, sync |
| `on_before_delete` | Before user deletion | Prevent deletion, check dependencies |
| `on_after_delete` | After user deletion | Cleanup, cancellation email |
| `on_after_request_verify` | After email verification request | Send verification email |
| `on_after_verify` | After email verification | Welcome email, grant permissions |
| `on_after_forgot_password` | After password reset request | Send reset email |
| `on_after_reset_password` | After password reset | Send confirmation, invalidate sessions |
| `on_failed_login` | After failed login | Track attempts, send alert |

### Custom UserService with Hooks

```python
from outlabs_auth.services.user import UserService
from fastapi import Request
from typing import Optional, Any, Dict

class MyUserService(UserService):
    """Custom user service with lifecycle hooks."""

    async def on_after_register(
        self,
        user: Any,
        request: Optional[Request] = None
    ) -> None:
        """Called after successful user registration."""
        # Send welcome email
        await email_service.send_welcome_email(user.email, user.profile.first_name)

        # Track in analytics
        await analytics.track("user_registered", {
            "user_id": str(user.id),
            "email": user.email,
            "created_at": user.created_at.isoformat() if user.created_at else None
        })

        # Create default preferences
        await preferences_service.create_defaults(str(user.id))

    async def on_after_login(
        self,
        user: Any,
        request: Optional[Request] = None,
        response: Any = None
    ) -> None:
        """Called after successful login."""
        # Update last login timestamp
        user.last_login = datetime.now(timezone.utc)
        await user.save()

        # Track login
        await analytics.track("user_login", {
            "user_id": str(user.id),
            "ip": request.client.host if request else None
        })

        # Check for suspicious activity
        if request and await is_suspicious_login(user, request):
            await security_service.send_login_alert(user.email, request.client.host)

    async def on_after_update(
        self,
        user: Any,
        update_dict: Dict[str, Any],
        request: Optional[Request] = None
    ) -> None:
        """Called after user profile update."""
        # Audit log
        await audit_log.log("user_updated", str(user.id), update_dict)

        # Invalidate caches
        await cache.invalidate(f"user:{str(user.id)}")

        # Sync to external system
        await crm_service.sync_user(user)

    async def on_before_delete(
        self,
        user: Any,
        request: Optional[Request] = None
    ) -> None:
        """Called before user deletion."""
        # Prevent deletion of superusers
        if user.is_superuser:
            raise ValueError("Cannot delete superuser account")

        # Check for active subscriptions
        if await has_active_subscription(str(user.id)):
            raise ValueError("Cancel subscription before deleting account")

    async def on_after_delete(
        self,
        user: Any,
        request: Optional[Request] = None
    ) -> None:
        """Called after user deletion."""
        # Clean up related data
        await cleanup_user_files(str(user.id))
        await cleanup_user_sessions(str(user.id))

        # Send cancellation email
        await email_service.send_account_deleted_email(user.email)

        # Audit log
        await audit_log.log("user_deleted", str(user.id), {
            "email": user.email,
            "deleted_by": request.user.id if request and hasattr(request, "user") else None
        })

    async def on_failed_login(
        self,
        email: str,
        request: Optional[Request] = None
    ) -> None:
        """Called after failed login attempt."""
        # Track failed attempts
        await security_service.track_failed_login(
            email,
            request.client.host if request else None
        )

        # Send alert after threshold
        failed_count = await security_service.get_failed_count(email)
        if failed_count >= 3:
            await email_service.send_security_alert(email, failed_count)
```

### Using Custom Service

```python
from outlabs_auth import OutlabsAuth

# Inject custom service
auth = OutlabsAuth(database=db, secret_key="...")

# Replace default UserService with custom one
auth.user_service = MyUserService(
    database=db,
    config=auth.config,
    notification_service=auth.notification_service
)

await auth.initialize()
```

---

## Error Handling

### Exception Types

```python
from outlabs_auth.core.exceptions import (
    UserAlreadyExistsError,
    UserNotFoundError,
    InvalidPasswordError,
)
```

### Error Handling Pattern

```python
from fastapi import HTTPException

@app.post("/users")
async def create_user_endpoint(
    email: str,
    password: str,
    first_name: str,
    last_name: str,
    admin = Depends(deps.requires("user:create"))
):
    try:
        user = await auth.user_service.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )
        return {
            "id": str(user.id),
            "email": user.email,
            "name": user.profile.full_name
        }
    except UserAlreadyExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except InvalidPasswordError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Log unexpected error
        logger.error(f"Failed to create user: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
```

---

## Complete Examples

### User Registration Flow

```python
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from outlabs_auth import SimpleRBAC
from outlabs_auth.dependencies import AuthDeps
from outlabs_auth.core.exceptions import UserAlreadyExistsError, InvalidPasswordError

app = FastAPI()
auth = SimpleRBAC(database=db, secret_key="...")
deps = AuthDeps(auth)

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str

@app.post("/auth/register")
async def register(data: RegisterRequest):
    try:
        # Create user
        user = await auth.user_service.create_user(
            email=data.email,
            password=data.password,
            first_name=data.first_name,
            last_name=data.last_name
        )

        # Generate email verification token
        verify_token = await auth.auth_service.create_email_verification_token(str(user.id))

        # Send verification email
        await email_service.send_verification_email(user.email, verify_token)

        # Return tokens for immediate login (optional)
        tokens = await auth.auth_service.create_tokens(str(user.id))

        return {
            "message": "Registration successful. Please verify your email.",
            "user": {
                "id": str(user.id),
                "email": user.email,
                "name": user.profile.full_name
            },
            **tokens
        }
    except UserAlreadyExistsError:
        raise HTTPException(status_code=409, detail="Email already registered")
    except InvalidPasswordError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

### User Profile Management

```python
class UpdateProfileRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    avatar_url: Optional[str] = None

@app.get("/users/me")
async def get_my_profile(user = Depends(deps.authenticated())):
    """Get current user profile."""
    return {
        "id": str(user.id),
        "email": user.email,
        "first_name": user.profile.first_name,
        "last_name": user.profile.last_name,
        "full_name": user.profile.full_name,
        "phone": user.profile.phone,
        "avatar_url": user.profile.avatar_url,
        "email_verified": user.email_verified,
        "status": user.status.value,
        "created_at": user.created_at.isoformat() if user.created_at else None
    }

@app.put("/users/me")
async def update_my_profile(
    data: UpdateProfileRequest,
    user = Depends(deps.authenticated())
):
    """Update current user profile."""
    updated_user = await auth.user_service.update_user(
        user_id=str(user.id),
        first_name=data.first_name,
        last_name=data.last_name,
        phone_number=data.phone_number,
        avatar_url=data.avatar_url
    )

    return {
        "message": "Profile updated successfully",
        "user": {
            "id": str(updated_user.id),
            "name": updated_user.profile.full_name,
            "email": updated_user.email
        }
    }
```

### Admin User Management

```python
@app.get("/admin/users")
async def admin_list_users(
    page: int = 1,
    limit: int = 20,
    status: Optional[UserStatus] = None,
    admin = Depends(deps.requires("user:list"))
):
    """List all users (admin only)."""
    users, total = await auth.user_service.list_users(
        page=page,
        limit=limit,
        status=status
    )

    return {
        "users": [
            {
                "id": str(u.id),
                "email": u.email,
                "name": u.profile.full_name,
                "status": u.status.value,
                "is_superuser": u.is_superuser,
                "email_verified": u.email_verified,
                "created_at": u.created_at.isoformat() if u.created_at else None
            }
            for u in users
        ],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": (total + limit - 1) // limit
        }
    }

@app.put("/admin/users/{user_id}/status")
async def admin_update_user_status(
    user_id: str,
    status: UserStatus,
    admin = Depends(deps.requires("user:manage"))
):
    """Update user status (admin only)."""
    user = await auth.user_service.update_user_status(user_id, status)

    return {
        "message": "User status updated",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "status": user.status.value
        }
    }

@app.delete("/admin/users/{user_id}")
async def admin_delete_user(
    user_id: str,
    admin = Depends(deps.requires("user:delete"))
):
    """Delete user (admin only)."""
    deleted = await auth.user_service.delete_user(user_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")

    return {"message": "User deleted successfully"}
```

---

## Summary

**UserService** provides complete user management:

✅ **User Creation** - `create_user()` with validation
✅ **Profile Management** - `update_user()` for profile changes
✅ **Password Management** - `change_password()` with validation
✅ **Status Management** - `update_user_status()` for account states
✅ **User Lookup** - `get_user_by_id()`, `get_user_by_email()`
✅ **Search** - `search_users()` by email/name
✅ **Listing** - `list_users()` with pagination
✅ **Email Verification** - `verify_email()`
✅ **Security** - Account locking, failed attempts
✅ **Lifecycle Hooks** - Custom logic at key events
✅ **Notifications** - Event emission for external systems

---

## Related Documentation

- **60-SimpleRBAC-API.md** - SimpleRBAC API reference
- **61-EnterpriseRBAC-API.md** - EnterpriseRBAC API reference
- **71-Role-Service.md** - RoleService API reference
- **72-Permission-Service.md** - PermissionService API reference
- **20-Authentication.md** - Authentication system overview

---

**Last Updated:** 2025-01-14
