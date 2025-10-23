# Email & Password Authentication

**Tags**: #authentication #email-password #traditional-auth

Complete guide to traditional email/password authentication in OutlabsAuth.

---

## Overview

Email/password authentication is the most common authentication method for web applications.

**Flow**:
```
User → Register (email + password)
     → Verify email (optional)
     → Login (email + password)
     → Receive JWT tokens
     → Access protected resources
```

**Features**:
- ✅ argon2id password hashing
- ✅ Email verification
- ✅ Password reset flow
- ✅ Password complexity requirements
- ✅ Account lockout after failed attempts
- ✅ Lifecycle hooks for custom logic

---

## Quick Start

### Step 1: Add Auth Router

```python
from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient
from outlabs_auth import SimpleRBAC
from outlabs_auth.routers import get_auth_router

app = FastAPI()
mongo_client = AsyncIOMotorClient("mongodb://localhost:27017")
db = mongo_client["myapp"]

auth = SimpleRBAC(database=db)

@app.on_event("startup")
async def startup():
    await auth.initialize()

# Add authentication routes
app.include_router(
    get_auth_router(auth),
    prefix="/auth",
    tags=["auth"]
)
```

### Step 2: Register User

```bash
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePassword123!"
  }'
```

Response:
```json
{
  "id": "user_123",
  "email": "user@example.com",
  "is_active": true,
  "is_verified": false,
  "created_at": "2025-01-23T10:00:00Z"
}
```

### Step 3: Login

```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePassword123!"
  }'
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 900
}
```

### Step 4: Access Protected Route

```bash
curl -X GET "http://localhost:8000/users/me" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

## User Registration

### Basic Registration

```python
# Using router (recommended)
app.include_router(get_auth_router(auth), prefix="/auth")

# POST /auth/register
# {
#   "email": "user@example.com",
#   "password": "SecurePassword123!"
# }
```

### Programmatic Registration

```python
# Using service directly
user = await auth.user_service.create_user(
    email="user@example.com",
    password="SecurePassword123!",
    is_verified=False,  # Require email verification
    metadata={"source": "web"}  # Optional metadata
)
```

### Registration with Additional Fields

```python
from outlabs_auth.models import User
from pydantic import BaseModel

class UserRegistration(BaseModel):
    email: str
    password: str
    name: str
    phone: str

@app.post("/auth/register")
async def register(data: UserRegistration):
    # Create user
    user = await auth.user_service.create_user(
        email=data.email,
        password=data.password,
        is_verified=False
    )

    # Update with additional fields
    await auth.user_service.update_user(
        user.id,
        name=data.name,
        phone=data.phone
    )

    return user
```

### Registration Validation

```python
from outlabs_auth.services import UserService
from fastapi import HTTPException

class MyUserService(UserService):
    async def before_register(self, email: str, password: str, request=None):
        # Custom validation
        if not email.endswith("@company.com"):
            raise HTTPException(400, "Only company emails allowed")

        # Check password complexity
        if len(password) < 12:
            raise HTTPException(400, "Password must be at least 12 characters")

        if not any(c.isupper() for c in password):
            raise HTTPException(400, "Password must contain uppercase")

        if not any(c.isdigit() for c in password):
            raise HTTPException(400, "Password must contain number")

    async def on_after_register(self, user, request=None):
        # Send welcome email
        await email_service.send_welcome(user.email)

        # Assign default role
        await self.role_service.assign_role_to_user(user.id, "user")

        # Track analytics
        await analytics.track("user_registered", {"user_id": user.id})

auth = SimpleRBAC(
    database=db,
    user_service_class=MyUserService
)
```

---

## Email Verification

### Why Email Verification?

**Benefits**:
- ✅ Confirm user owns the email address
- ✅ Prevent fake accounts
- ✅ Reduce spam registrations
- ✅ Enable password reset

**Trade-offs**:
- ⚠️ Additional friction in signup flow
- ⚠️ Requires email service
- ⚠️ Users can forget to verify

### Enable Email Verification

```python
# Require verified email for login
auth = SimpleRBAC(
    database=db,
    require_verified_email=True  # Users must verify before login
)
```

### Verification Flow

```
1. User registers
   POST /auth/register
   → User created with is_verified=False

2. Send verification email
   → Generate verification token (JWT)
   → Send email with link: https://myapp.com/verify?token=...

3. User clicks link
   GET /verify?token=...
   → Frontend calls backend

4. Backend verifies token
   POST /auth/verify
   {"token": "eyJhbGc..."}
   → User.is_verified = True

5. User can now login
```

### Implementing Verification

```python
from outlabs_auth.services import UserService
import jwt
from datetime import datetime, timedelta

class MyUserService(UserService):
    async def on_after_register(self, user, request=None):
        # Generate verification token
        token = jwt.encode(
            {
                "sub": user.id,
                "exp": datetime.utcnow() + timedelta(hours=24),
                "type": "email_verification"
            },
            self.jwt_secret,
            algorithm="HS256"
        )

        # Send verification email
        verification_url = f"https://myapp.com/verify?token={token}"
        await email_service.send(
            to=user.email,
            subject="Verify your email",
            body=f"Click here to verify: {verification_url}"
        )

# Verification endpoint
@app.post("/auth/verify")
async def verify_email(token: str):
    try:
        # Decode token
        payload = jwt.decode(token, auth.jwt_secret, algorithms=["HS256"])
        user_id = payload["sub"]

        # Verify user
        await auth.user_service.verify_user(user_id)

        return {"message": "Email verified successfully"}

    except jwt.ExpiredSignatureError:
        raise HTTPException(400, "Verification link expired")
    except jwt.InvalidTokenError:
        raise HTTPException(400, "Invalid verification link")
```

### Resend Verification Email

```python
@app.post("/auth/resend-verification")
async def resend_verification(email: str):
    # Get user
    user = await auth.user_service.get_by_email(email)
    if not user:
        raise HTTPException(404, "User not found")

    if user.is_verified:
        raise HTTPException(400, "Email already verified")

    # Trigger on_after_register hook to resend email
    await auth.user_service.on_after_register(user)

    return {"message": "Verification email sent"}
```

---

## User Login

### Basic Login

```python
# Using router (recommended)
app.include_router(get_auth_router(auth), prefix="/auth")

# POST /auth/login
# {
#   "email": "user@example.com",
#   "password": "SecurePassword123!"
# }
```

### Programmatic Login

```python
# Using service directly
tokens = await auth.auth_service.login(
    email="user@example.com",
    password="SecurePassword123!"
)

# Returns:
# {
#   "access_token": "eyJhbGc...",
#   "refresh_token": "eyJhbGc...",
#   "token_type": "bearer",
#   "expires_in": 900
# }
```

### Login Validation

```python
from outlabs_auth.services import AuthService
from fastapi import HTTPException

class MyAuthService(AuthService):
    async def before_login(self, email: str, password: str, request=None):
        # Check if user is locked out
        lockout = await self.check_lockout(email)
        if lockout:
            raise HTTPException(
                429,
                f"Too many failed attempts. Try again in {lockout} seconds"
            )

    async def on_after_login(self, user, request=None):
        # Update last login time
        await self.user_service.update_user(
            user.id,
            last_login_at=datetime.utcnow()
        )

        # Track analytics
        await analytics.track("user_logged_in", {
            "user_id": user.id,
            "ip": request.client.host if request else None
        })

        # Send security notification
        if request and user.email_notifications_enabled:
            await email_service.send_security_alert(
                user.email,
                f"New login from {request.client.host}"
            )

auth = SimpleRBAC(
    database=db,
    auth_service_class=MyAuthService
)
```

### Login Errors

```python
# Invalid credentials
{
  "detail": "Invalid email or password"
}

# Account not verified
{
  "detail": "Please verify your email before logging in"
}

# Account inactive
{
  "detail": "Your account has been deactivated"
}

# Account locked
{
  "detail": "Too many failed login attempts. Try again later."
}
```

---

## Password Management

### Password Hashing

OutlabsAuth uses **argon2id** for password hashing (OWASP recommended).

**Why argon2id**:
- ✅ Memory-hard (resistant to GPU attacks)
- ✅ Winner of Password Hashing Competition (2015)
- ✅ Better than bcrypt for new applications
- ✅ Configurable time/memory costs

```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

# Hash password
hashed = pwd_context.hash("user_password")

# Verify password
is_valid = pwd_context.verify("user_password", hashed)
```

### Password Complexity Requirements

```python
from outlabs_auth.services import UserService
from fastapi import HTTPException
import re

class MyUserService(UserService):
    def validate_password(self, password: str):
        # Length check
        if len(password) < 12:
            raise HTTPException(400, "Password must be at least 12 characters")

        # Uppercase check
        if not re.search(r"[A-Z]", password):
            raise HTTPException(400, "Password must contain uppercase letter")

        # Lowercase check
        if not re.search(r"[a-z]", password):
            raise HTTPException(400, "Password must contain lowercase letter")

        # Digit check
        if not re.search(r"\d", password):
            raise HTTPException(400, "Password must contain number")

        # Special character check
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            raise HTTPException(400, "Password must contain special character")

        # Common password check
        common_passwords = ["password", "123456", "qwerty", ...]
        if password.lower() in common_passwords:
            raise HTTPException(400, "Password is too common")

    async def before_register(self, email: str, password: str, request=None):
        self.validate_password(password)
```

### Change Password

```python
# Using router
app.include_router(get_users_router(auth), prefix="/users")

# POST /users/me/change-password
# Authorization: Bearer {token}
# {
#   "old_password": "OldPassword123!",
#   "new_password": "NewPassword456!"
# }
```

### Change Password Programmatically

```python
@app.post("/users/me/change-password")
async def change_password(
    old_password: str,
    new_password: str,
    ctx = Depends(auth.deps.require_auth())
):
    user = ctx.metadata.get("user")

    # Verify old password
    if not pwd_context.verify(old_password, user.hashed_password):
        raise HTTPException(400, "Invalid old password")

    # Validate new password
    if old_password == new_password:
        raise HTTPException(400, "New password must be different")

    # Update password
    await auth.user_service.update_user(
        user.id,
        password=new_password
    )

    return {"message": "Password changed successfully"}
```

---

## Password Reset

### Password Reset Flow

```
1. User requests reset
   POST /auth/forgot-password
   {"email": "user@example.com"}

2. Generate reset token (JWT, 1 hour expiration)
   token = jwt.encode({"sub": user_id, "exp": ...})

3. Send reset email
   https://myapp.com/reset-password?token=...

4. User clicks link and submits new password
   POST /auth/reset-password
   {"token": "eyJhbGc...", "new_password": "NewPassword123!"}

5. Backend validates token and updates password
```

### Implementing Password Reset

```python
from outlabs_auth.services import UserService
import jwt
from datetime import datetime, timedelta

class MyUserService(UserService):
    async def on_after_forgot_password(self, user, token: str, request=None):
        # Send password reset email
        reset_url = f"https://myapp.com/reset-password?token={token}"
        await email_service.send(
            to=user.email,
            subject="Reset your password",
            body=f"Click here to reset your password: {reset_url}"
        )

# Forgot password endpoint
@app.post("/auth/forgot-password")
async def forgot_password(email: str):
    # Get user
    user = await auth.user_service.get_by_email(email)
    if not user:
        # Don't reveal if email exists
        return {"message": "If the email exists, a reset link has been sent"}

    # Generate reset token
    token = jwt.encode(
        {
            "sub": user.id,
            "exp": datetime.utcnow() + timedelta(hours=1),
            "type": "password_reset"
        },
        auth.jwt_secret,
        algorithm="HS256"
    )

    # Trigger hook to send email
    await auth.user_service.on_after_forgot_password(user, token)

    return {"message": "If the email exists, a reset link has been sent"}

# Reset password endpoint
@app.post("/auth/reset-password")
async def reset_password(token: str, new_password: str):
    try:
        # Decode token
        payload = jwt.decode(token, auth.jwt_secret, algorithms=["HS256"])
        user_id = payload["sub"]

        # Validate token type
        if payload.get("type") != "password_reset":
            raise HTTPException(400, "Invalid token type")

        # Update password
        await auth.user_service.update_user(user_id, password=new_password)

        # Trigger hook
        user = await auth.user_service.get_user(user_id)
        await auth.user_service.on_after_reset_password(user)

        return {"message": "Password reset successfully"}

    except jwt.ExpiredSignatureError:
        raise HTTPException(400, "Reset link expired")
    except jwt.InvalidTokenError:
        raise HTTPException(400, "Invalid reset link")
```

---

## Account Lockout

### Failed Login Attempts

Protect against brute-force attacks by locking accounts after failed attempts.

```python
from outlabs_auth.services import AuthService
from datetime import datetime, timedelta
import redis.asyncio as redis

class MyAuthService(AuthService):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.redis = redis.from_url("redis://localhost:6379")

    async def check_lockout(self, email: str) -> int:
        """Check if email is locked out. Returns seconds remaining."""
        key = f"login_attempts:{email}"
        attempts = await self.redis.get(key)

        if attempts and int(attempts) >= 5:
            # Get TTL
            ttl = await self.redis.ttl(key)
            return ttl if ttl > 0 else 0

        return 0

    async def record_failed_attempt(self, email: str):
        """Record failed login attempt."""
        key = f"login_attempts:{email}"
        attempts = await self.redis.incr(key)

        # Set expiration (15 minutes)
        if attempts == 1:
            await self.redis.expire(key, 900)

        # Lock account after 5 attempts
        if attempts >= 5:
            await email_service.send_security_alert(
                email,
                "Your account has been temporarily locked due to multiple failed login attempts"
            )

    async def before_login(self, email: str, password: str, request=None):
        # Check lockout
        lockout = await self.check_lockout(email)
        if lockout:
            raise HTTPException(
                429,
                f"Too many failed attempts. Try again in {lockout} seconds"
            )

    async def on_login_failed(self, email: str, request=None):
        # Record failed attempt
        await self.record_failed_attempt(email)

    async def on_after_login(self, user, request=None):
        # Clear failed attempts on successful login
        key = f"login_attempts:{user.email}"
        await self.redis.delete(key)
```

---

## User Profile Management

### Get Current User

```python
# Using router
app.include_router(get_users_router(auth), prefix="/users")

# GET /users/me
# Authorization: Bearer {token}
```

### Update Profile

```python
# Using router
# PATCH /users/me
# Authorization: Bearer {token}
# {
#   "name": "John Doe",
#   "phone": "+1234567890"
# }
```

### Update Profile Programmatically

```python
@app.patch("/users/me")
async def update_profile(
    name: str = None,
    phone: str = None,
    ctx = Depends(auth.deps.require_auth())
):
    user = ctx.metadata.get("user")

    # Update fields
    update_data = {}
    if name:
        update_data["name"] = name
    if phone:
        update_data["phone"] = phone

    await auth.user_service.update_user(user.id, **update_data)

    # Get updated user
    updated_user = await auth.user_service.get_user(user.id)
    return updated_user
```

### Delete Account

```python
@app.delete("/users/me")
async def delete_account(
    password: str,
    ctx = Depends(auth.deps.require_auth())
):
    user = ctx.metadata.get("user")

    # Verify password
    if not pwd_context.verify(password, user.hashed_password):
        raise HTTPException(400, "Invalid password")

    # Delete user
    await auth.user_service.delete_user(user.id)

    return {"message": "Account deleted successfully"}
```

---

## Lifecycle Hooks

OutlabsAuth provides 13 lifecycle hooks for email/password authentication:

### User Hooks

```python
from outlabs_auth.services import UserService

class MyUserService(UserService):
    # Registration
    async def before_register(self, email: str, password: str, request=None):
        """Called before user registration"""
        pass

    async def on_after_register(self, user, request=None):
        """Called after successful registration"""
        pass

    # Login
    async def before_login(self, email: str, password: str, request=None):
        """Called before login attempt"""
        pass

    async def on_after_login(self, user, request=None):
        """Called after successful login"""
        pass

    async def on_login_failed(self, email: str, request=None):
        """Called after failed login"""
        pass

    # Verification
    async def on_after_verify(self, user, request=None):
        """Called after email verification"""
        pass

    # Password reset
    async def on_after_forgot_password(self, user, token: str, request=None):
        """Called after password reset request"""
        pass

    async def on_after_reset_password(self, user, request=None):
        """Called after password reset"""
        pass

    # Profile updates
    async def on_after_update(self, user, request=None):
        """Called after profile update"""
        pass

    # Account deletion
    async def on_after_delete(self, user, request=None):
        """Called after account deletion"""
        pass
```

See [[131-User-Hooks|User Lifecycle Hooks]] for complete reference.

---

## Security Best Practices

### 1. Always Use HTTPS

```python
# Force HTTPS in production
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

if not DEBUG:
    app.add_middleware(HTTPSRedirectMiddleware)
```

### 2. Secure Password Requirements

```python
# Minimum requirements:
# - 12+ characters
# - Uppercase + lowercase
# - Number
# - Special character
# - Not in common password list
```

### 3. Rate Limiting

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/auth/login")
@limiter.limit("5/minute")  # Max 5 login attempts per minute
async def login(...):
    pass
```

### 4. Security Headers

```python
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.cors import CORSMiddleware

# Trusted hosts only
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["myapp.com", "*.myapp.com"]
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://myapp.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

### 5. Don't Reveal User Existence

```python
# ❌ BAD: Reveals if email exists
if not user:
    raise HTTPException(404, "User not found")

# ✅ GOOD: Generic message
return {"message": "If the email exists, a reset link has been sent"}
```

---

## Next Steps

- **[[22-JWT-Tokens|JWT Tokens]]** - Understanding access and refresh tokens
- **[[110-Security-Best-Practices|Security Best Practices]]** - Complete security guide
- **[[131-User-Hooks|User Lifecycle Hooks]]** - All available hooks
- **[[150-Tutorial-Simple-App|Tutorial]]** - Build complete app with auth

---

**Previous**: [[20-Authentication-Overview|← Authentication Overview]]
**Next**: [[22-JWT-Tokens|JWT Tokens →]]
