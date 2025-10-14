# OutlabsAuth Security Guide

**Version**: 1.0
**Date**: 2025-01-14
**Audience**: Developers deploying OutlabsAuth to production
**Status**: Production Reference

---

## Table of Contents

1. [Security Overview](#security-overview)
2. [Threat Model](#threat-model)
3. [JWT Security](#jwt-security)
4. [Password Security](#password-security)
5. [Authentication Security](#authentication-security)
6. [Authorization Security](#authorization-security)
7. [Network Security](#network-security)
8. [Database Security](#database-security)
9. [Secrets Management](#secrets-management)
10. [Rate Limiting & Abuse Prevention](#rate-limiting--abuse-prevention)
11. [Audit Logging](#audit-logging)
12. [Security Checklist](#security-checklist)
13. [Common Vulnerabilities](#common-vulnerabilities)
14. [Incident Response](#incident-response)

---

## Security Overview

OutlabsAuth is an authentication and authorization library designed with security as a priority. This guide covers:

- **Defense in depth**: Multiple layers of security controls
- **Secure defaults**: Safe configurations out of the box
- **Best practices**: Industry-standard security patterns
- **Production hardening**: Steps to secure production deployments

### Security Principles

1. **Least Privilege**: Users get minimum permissions needed
2. **Defense in Depth**: Multiple security layers
3. **Fail Secure**: Errors deny access by default
4. **Audit Everything**: Comprehensive logging of security events
5. **Secrets Protection**: Never log or expose secrets

---

## Threat Model

### Assets We Protect

1. **User Credentials**: Passwords, tokens, refresh tokens
2. **User Data**: Personal information, profiles
3. **Authorization Data**: Roles, permissions, entity memberships
4. **Session Data**: Active sessions, refresh tokens
5. **Admin Access**: Platform admin accounts

### Threat Actors

1. **External Attackers**: Brute force, credential stuffing, API abuse
2. **Malicious Users**: Privilege escalation, unauthorized access
3. **Compromised Accounts**: Stolen credentials, session hijacking
4. **Insider Threats**: Malicious administrators
5. **Automated Bots**: Scraping, enumeration, DOS attacks

### Attack Vectors

1. **Authentication Bypass**: Weak passwords, brute force, credential stuffing
2. **Privilege Escalation**: Permission bugs, hierarchy bypass
3. **Session Hijacking**: Token theft, XSS, MITM
4. **Injection Attacks**: NoSQL injection, command injection
5. **Denial of Service**: Rate limit bypass, resource exhaustion
6. **Data Exposure**: Information leakage, verbose errors

---

## JWT Security

### Token Configuration

**Access Tokens** (Short-lived):
```python
from outlabs_auth import SimpleRBAC, AuthConfig

config = AuthConfig(
    secret_key="CHANGE-THIS-IN-PRODUCTION",  # Must be random
    access_token_expire_minutes=15,          # Short expiry
    algorithm="HS256",                       # HMAC SHA-256
)

auth = SimpleRBAC(database=db, config=config)
```

**Best Practices**:
- ✅ Use strong random secret key (32+ bytes)
- ✅ Keep access tokens short-lived (15 minutes)
- ✅ Use HS256 or RS256 algorithm
- ✅ Rotate secret keys periodically
- ❌ Never commit secret keys to source control
- ❌ Never reuse keys across environments

### Secret Key Generation

```python
import secrets

# Generate cryptographically secure secret key
secret_key = secrets.token_urlsafe(32)
print(secret_key)  # Store in environment variable
```

**Production Secret Management**:
```bash
# Generate secret key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Store in environment
export SECRET_KEY="<generated-key>"

# Or use secrets manager (recommended)
export SECRET_KEY=$(aws secretsmanager get-secret-value --secret-id outlabs-auth-secret --query SecretString --output text)
```

### Refresh Token Security

**Configuration**:
```python
config = AuthConfig(
    refresh_token_expire_days=30,  # Longer expiry
    max_refresh_tokens_per_user=5, # Limit concurrent sessions
)
```

**Storage**:
- ✅ Store refresh tokens in database
- ✅ Hash refresh tokens before storage
- ✅ Support token revocation
- ✅ Limit tokens per user
- ❌ Never store refresh tokens in local storage (use httpOnly cookies)

**Revocation**:
```python
# Revoke specific token
await auth.auth_service.logout(refresh_token=token)

# Revoke all user tokens
await auth.auth_service.revoke_all_tokens(user_id=user.id)
```

### Token Validation

```python
from fastapi import Depends, HTTPException
from outlabs_auth.exceptions import TokenExpiredException, InvalidTokenException

@app.get("/protected")
async def protected_route(user=Depends(auth.get_current_user)):
    # Token automatically validated
    # Expired/invalid tokens raise HTTPException(401)
    return {"user": user.email}
```

**Validation Checks**:
- ✅ Signature verification
- ✅ Expiration check
- ✅ Not-before check (nbf)
- ✅ Issuer validation (iss)
- ✅ Audience validation (aud)

---

## Password Security

### Password Hashing

OutlabsAuth uses **bcrypt** with work factor 12:

```python
from outlabs_auth.security import hash_password, verify_password

# Hash password (bcrypt rounds=12)
hashed = hash_password("user_password")

# Verify password
is_valid = verify_password("user_password", hashed)
```

**Why bcrypt?**:
- Adaptive work factor (resistant to hardware improvements)
- Built-in salt
- Slow by design (resistant to brute force)
- Industry standard

### Password Requirements

**Recommended Policy**:
```python
from outlabs_auth import AuthConfig

config = AuthConfig(
    min_password_length=12,           # Minimum 12 characters
    require_uppercase=True,           # At least one uppercase
    require_lowercase=True,           # At least one lowercase
    require_numbers=True,             # At least one number
    require_special_chars=True,       # At least one special char
    password_history_count=5,         # Prevent reuse of last 5
    password_max_age_days=90,         # Expire after 90 days
)
```

**Implementation**:
```python
from outlabs_auth.validators import validate_password_strength

# Validate password strength
try:
    validate_password_strength(
        password="MySecureP@ssw0rd",
        min_length=12,
        require_uppercase=True,
        require_numbers=True,
        require_special=True
    )
except ValueError as e:
    # Password doesn't meet requirements
    return {"error": str(e)}
```

### Password Reset Security

**Secure Reset Flow**:
```python
# 1. Generate secure reset token (expiring)
reset_token = await auth.auth_service.create_password_reset_token(
    email="user@example.com",
    expires_minutes=60  # Token expires in 1 hour
)

# 2. Send token via email (never via URL)
await send_email(
    to=user.email,
    subject="Password Reset",
    template="password_reset",
    token=reset_token
)

# 3. Validate token and reset password
await auth.auth_service.reset_password(
    token=reset_token,
    new_password="NewSecurePassword123!"
)
```

**Best Practices**:
- ✅ Use time-limited reset tokens (1 hour)
- ✅ Single-use tokens (invalidate after use)
- ✅ Rate limit reset requests
- ✅ Don't reveal if email exists
- ✅ Revoke all sessions after reset
- ❌ Never send passwords via email
- ❌ Never put tokens in URL query params (use POST body)

---

## Authentication Security

### Login Security

**Rate Limiting**:
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/auth/login")
@limiter.limit("5/minute")  # 5 attempts per minute
async def login(credentials: LoginRequest):
    try:
        tokens = await auth.auth_service.login(
            email=credentials.email,
            password=credentials.password
        )
        return tokens
    except InvalidCredentialsException:
        # Generic error (don't reveal if user exists)
        raise HTTPException(401, "Invalid credentials")
```

**Brute Force Protection**:
```python
# Account lockout after failed attempts
config = AuthConfig(
    max_login_attempts=5,           # Lock after 5 failures
    lockout_duration_minutes=15,    # Lockout for 15 minutes
    lockout_reset_on_success=True,  # Reset counter on success
)
```

### Multi-Factor Authentication (MFA)

**TOTP Implementation** (Coming in v1.1):
```python
# Enable MFA for user
mfa_secret = await auth.auth_service.enable_mfa(user_id=user.id)

# User scans QR code and provides TOTP code
is_valid = await auth.auth_service.verify_mfa(
    user_id=user.id,
    code="123456"
)

# Login with MFA
tokens = await auth.auth_service.login_with_mfa(
    email="user@example.com",
    password="password",
    mfa_code="123456"
)
```

### Session Management

**Secure Session Configuration**:
```python
config = AuthConfig(
    access_token_expire_minutes=15,  # Short-lived
    refresh_token_expire_days=30,    # Long-lived
    max_refresh_tokens_per_user=5,   # Limit concurrent sessions
    revoke_on_password_change=True,  # Invalidate all sessions
)
```

**Session Monitoring**:
```python
# List active sessions
sessions = await auth.auth_service.get_user_sessions(user_id=user.id)

# Revoke specific session
await auth.auth_service.revoke_session(session_id=session.id)

# Revoke all sessions except current
await auth.auth_service.revoke_other_sessions(
    user_id=user.id,
    current_token=token
)
```

---

## Authorization Security

### Permission Checks

**Always Check Permissions**:
```python
from fastapi import Depends

# Using dependency injection (recommended)
@app.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    current_user=Depends(auth.require_permission("user:delete"))
):
    # Permission already checked
    await user_service.delete(user_id)
    return {"status": "deleted"}

# Manual check
@app.delete("/users/{user_id}")
async def delete_user(user_id: str, current_user=Depends(auth.get_current_user)):
    has_perm, source = await auth.permission_service.check_permission(
        user_id=current_user.id,
        permission="user:delete"
    )
    if not has_perm:
        raise HTTPException(403, "Permission denied")

    await user_service.delete(user_id)
    return {"status": "deleted"}
```

**Entity Context Permissions**:
```python
# Check permission in entity context
@app.put("/entities/{entity_id}")
async def update_entity(
    entity_id: str,
    current_user=Depends(auth.require_entity_permission("entity:update", "entity_id"))
):
    # Permission checked for specific entity
    # Tree permissions automatically checked
    await entity_service.update(entity_id)
    return {"status": "updated"}
```

### Least Privilege Principle

**Role Design**:
```python
# Bad: Over-privileged role
admin_role = {
    "name": "admin",
    "permissions": ["*:*"]  # ❌ Too broad
}

# Good: Specific permissions
admin_role = {
    "name": "admin",
    "permissions": [
        "user:create", "user:read", "user:update", "user:delete",
        "role:create", "role:read", "role:update", "role:delete",
        "entity:create", "entity:read", "entity:update", "entity:delete",
    ]
}

# Better: Separate admin roles by domain
user_admin_role = {
    "name": "user_admin",
    "permissions": ["user:create", "user:read", "user:update", "user:delete"]
}

entity_admin_role = {
    "name": "entity_admin",
    "permissions": ["entity:create", "entity:read", "entity:update", "entity:delete"]
}
```

### Tree Permission Security

**Hierarchical Access Control**:
```python
# Enterprise preset with tree permissions
from outlabs_auth import EnterpriseRBAC

auth = EnterpriseRBAC(database=db)

# User with tree permission at parent
# Can access all descendant entities
has_perm, source = await auth.permission_service.check_permission(
    user_id=user.id,
    permission="entity:update",
    entity_id=child_entity.id  # Checks parent tree permissions
)
```

**Best Practices**:
- ✅ Use tree permissions for hierarchical structures
- ✅ Test permission boundaries thoroughly
- ✅ Document who has tree permissions
- ⚠️ Tree permissions are powerful - grant carefully

---

## Network Security

### HTTPS/TLS

**Always Use HTTPS in Production**:
```python
# Redirect HTTP to HTTPS
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

app.add_middleware(HTTPSRedirectMiddleware)
```

**Secure Headers**:
```python
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.sessions import SessionMiddleware

# Trust only your domain
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["yourdomain.com", "*.yourdomain.com"]
)

# Secure session cookies
app.add_middleware(
    SessionMiddleware,
    secret_key=config.secret_key,
    https_only=True,      # HTTPS only
    same_site="strict",   # CSRF protection
    max_age=900           # 15 minutes
)
```

**Security Headers**:
```python
from fastapi import Request, Response

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response
```

### CORS Configuration

**Restrictive CORS**:
```python
from fastapi.middleware.cors import CORSMiddleware

# Production CORS (restrictive)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://yourdomain.com",
        "https://app.yourdomain.com"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=600
)
```

**Development CORS** (never use in production):
```python
# Development only (allow all origins)
if os.getenv("ENVIRONMENT") == "development":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"]
    )
```

---

## Database Security

### MongoDB Security

**Connection Security**:
```python
from motor.motor_asyncio import AsyncIOMotorClient

# Secure connection with authentication
client = AsyncIOMotorClient(
    f"mongodb://{username}:{password}@{host}:{port}",
    authSource="admin",
    tls=True,                    # Enable TLS
    tlsAllowInvalidCertificates=False,
    serverSelectionTimeoutMS=5000
)
```

**Database User Permissions**:
```javascript
// MongoDB user with least privilege
use outlabs_auth;
db.createUser({
  user: "outlabs_auth_app",
  pwd: passwordPrompt(),
  roles: [
    { role: "readWrite", db: "outlabs_auth" }
  ]
});
```

### Query Security

**Prevent NoSQL Injection**:
```python
# Good: Use Beanie ODM (parameterized queries)
user = await UserModel.find_one(UserModel.email == email)

# Bad: String concatenation (vulnerable)
# Don't do this!
# db.users.find({"email": email})  # Injection risk
```

**Input Validation**:
```python
from pydantic import BaseModel, EmailStr, constr

class CreateUserRequest(BaseModel):
    email: EmailStr  # Validates email format
    name: constr(min_length=1, max_length=100)  # Length constraints
    password: constr(min_length=12)  # Minimum length

# FastAPI validates input automatically
@app.post("/users")
async def create_user(user: CreateUserRequest):
    # Input already validated by Pydantic
    pass
```

### Data Encryption

**Encryption at Rest**:
```bash
# MongoDB encrypted storage engine
mongod --enableEncryption \
  --encryptionKeyFile /path/to/keyfile \
  --encryptionCipherMode AES256-CBC
```

**Field-Level Encryption** (for sensitive data):
```python
from cryptography.fernet import Fernet

class UserModel(Document):
    email: str
    hashed_password: str
    ssn: Optional[str] = None  # Sensitive - encrypt before storage

    @classmethod
    async def create_with_encrypted_ssn(cls, email: str, password: str, ssn: str):
        cipher = Fernet(encryption_key)
        encrypted_ssn = cipher.encrypt(ssn.encode())

        user = cls(
            email=email,
            hashed_password=hash_password(password),
            ssn=encrypted_ssn.decode()
        )
        await user.save()
        return user
```

### Backup Security

**Secure Backups**:
```bash
# Encrypt backups
mongodump --uri="mongodb://..." --out=/tmp/backup
tar czf backup.tar.gz /tmp/backup
gpg --symmetric --cipher-algo AES256 backup.tar.gz

# Store encrypted backup securely
aws s3 cp backup.tar.gz.gpg s3://secure-backups/ --sse AES256
```

---

## Secrets Management

### Environment Variables

**Never Commit Secrets**:
```bash
# .env (add to .gitignore)
SECRET_KEY=your-secret-key-here
DATABASE_URL=mongodb://user:pass@host:27017/db
REDIS_URL=redis://user:pass@host:6379
SMTP_PASSWORD=smtp-password
```

**Load from Environment**:
```python
import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    secret_key: str
    database_url: str
    redis_url: Optional[str] = None

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
```

### Secrets Managers (Production)

**AWS Secrets Manager**:
```python
import boto3
import json

def get_secret(secret_name: str) -> dict:
    client = boto3.client('secretsmanager', region_name='us-east-1')
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

# Load secrets
secrets = get_secret("outlabs-auth-prod")
config = AuthConfig(
    secret_key=secrets['SECRET_KEY'],
    database_url=secrets['DATABASE_URL']
)
```

**HashiCorp Vault**:
```python
import hvac

client = hvac.Client(url='https://vault.company.com')
client.auth.approle.login(
    role_id=os.getenv('VAULT_ROLE_ID'),
    secret_id=os.getenv('VAULT_SECRET_ID')
)

# Read secrets
secrets = client.secrets.kv.v2.read_secret_version(path='outlabs-auth/prod')
config = AuthConfig(secret_key=secrets['data']['data']['SECRET_KEY'])
```

### Secret Rotation

**Regular Secret Rotation**:
```python
# 1. Generate new secret key
new_secret = secrets.token_urlsafe(32)

# 2. Update config with both keys (transition period)
config = AuthConfig(
    secret_key=new_secret,
    old_secret_key=current_secret,  # Accept both during transition
    secret_rotation_days=7          # Transition period
)

# 3. After transition, remove old key
config = AuthConfig(secret_key=new_secret)
```

---

## Rate Limiting & Abuse Prevention

### Rate Limiting Configuration

**Install Dependencies**:
```bash
pip install slowapi redis
```

**Basic Rate Limiting**:
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Rate limit login endpoint
@app.post("/auth/login")
@limiter.limit("5/minute")  # 5 requests per minute per IP
async def login(request: Request, credentials: LoginRequest):
    tokens = await auth.auth_service.login(
        email=credentials.email,
        password=credentials.password
    )
    return tokens

# Rate limit password reset
@app.post("/auth/forgot-password")
@limiter.limit("3/hour")  # 3 requests per hour
async def forgot_password(request: Request, email: EmailStr):
    await auth.auth_service.send_password_reset(email)
    return {"message": "If email exists, reset link sent"}
```

### Advanced Rate Limiting

**Per-User Rate Limiting**:
```python
from slowapi import Limiter

def get_user_identifier(request: Request):
    # Try to get user from token
    try:
        user = auth.get_current_user_sync(request)
        return user.id
    except:
        # Fall back to IP
        return get_remote_address(request)

limiter = Limiter(key_func=get_user_identifier)

@app.post("/api/expensive-operation")
@limiter.limit("10/minute")  # Per user, not per IP
async def expensive_operation(request: Request):
    pass
```

**Distributed Rate Limiting** (Redis):
```python
from slowapi import Limiter
from slowapi.util import get_remote_address
import redis

redis_client = redis.from_url("redis://localhost:6379")
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="redis://localhost:6379"  # Shared across instances
)
```

### Account Enumeration Prevention

**Don't Reveal if User Exists**:
```python
@app.post("/auth/login")
async def login(credentials: LoginRequest):
    try:
        tokens = await auth.auth_service.login(
            email=credentials.email,
            password=credentials.password
        )
        return tokens
    except InvalidCredentialsException:
        # Generic error - don't reveal if user exists
        raise HTTPException(401, "Invalid email or password")

@app.post("/auth/forgot-password")
async def forgot_password(email: EmailStr):
    # Always return success - don't reveal if email exists
    await auth.auth_service.send_password_reset(email)
    return {"message": "If the email exists, a reset link has been sent"}
```

---

## Audit Logging

### Enable Audit Logging

**Configuration**:
```python
from outlabs_auth import EnterpriseRBAC

auth = EnterpriseRBAC(
    database=db,
    enable_audit_log=True  # Enable comprehensive logging
)
```

### What Gets Logged

**Security Events**:
- ✅ Login attempts (success and failure)
- ✅ Logout events
- ✅ Token refresh
- ✅ Password changes
- ✅ Password reset requests
- ✅ Permission checks (failed only)
- ✅ Role assignments/removals
- ✅ Entity membership changes
- ✅ User creation/deletion
- ✅ Admin actions

**Log Format**:
```python
{
    "event_type": "login_failed",
    "timestamp": "2025-01-14T10:30:00Z",
    "user_email": "user@example.com",
    "ip_address": "192.168.1.1",
    "user_agent": "Mozilla/5.0...",
    "reason": "invalid_password",
    "metadata": {
        "attempt_count": 3
    }
}
```

### Querying Audit Logs

```python
# Get user's login history
logs = await auth.audit_service.get_user_events(
    user_id=user.id,
    event_types=["login_success", "login_failed"],
    start_date=datetime.now() - timedelta(days=30)
)

# Get failed permission checks
logs = await auth.audit_service.get_events(
    event_type="permission_denied",
    start_date=datetime.now() - timedelta(days=7)
)

# Get admin actions
logs = await auth.audit_service.get_events(
    event_type="role_assigned",
    actor_role="platform_admin"
)
```

### Log Retention

**Retention Policy**:
```python
config = EnterpriseConfig(
    audit_log_retention_days=90,    # Keep for 90 days
    archive_to_s3=True,             # Archive old logs
    s3_bucket="audit-logs-archive"
)
```

---

## Security Checklist

### Pre-Production Checklist

#### Configuration
- [ ] Strong random secret key (32+ bytes)
- [ ] Secret key stored in secrets manager (not .env)
- [ ] Access tokens short-lived (≤15 minutes)
- [ ] HTTPS enforced in production
- [ ] Security headers configured
- [ ] CORS configured restrictively
- [ ] Rate limiting enabled
- [ ] Audit logging enabled

#### Authentication
- [ ] Password requirements enforced (12+ chars)
- [ ] Bcrypt used for password hashing
- [ ] Account lockout after failed attempts
- [ ] Password reset tokens time-limited
- [ ] No passwords in logs
- [ ] No account enumeration vulnerabilities

#### Authorization
- [ ] All endpoints have permission checks
- [ ] Least privilege principle applied
- [ ] Tree permissions tested thoroughly
- [ ] No overly broad permissions (e.g., `*:*`)
- [ ] Entity context permissions working

#### Database
- [ ] MongoDB authentication enabled
- [ ] TLS encryption for connections
- [ ] Database user has least privilege
- [ ] Backups encrypted
- [ ] Beanie ODM used (no raw queries)

#### Secrets
- [ ] No secrets in source control
- [ ] Secrets manager used in production
- [ ] Secret rotation plan in place
- [ ] Separate secrets per environment

#### Monitoring
- [ ] Audit logs configured
- [ ] Failed login attempts monitored
- [ ] Permission denials monitored
- [ ] Anomaly detection configured
- [ ] Alerts for security events

#### Testing
- [ ] Security tests passing
- [ ] Permission boundaries tested
- [ ] Rate limiting tested
- [ ] Token expiration tested
- [ ] Penetration testing completed

---

## Common Vulnerabilities

### 1. Broken Authentication

**Vulnerability**:
```python
# Bad: No rate limiting, no lockout
@app.post("/auth/login")
async def login(credentials: LoginRequest):
    user = await UserModel.find_one(UserModel.email == credentials.email)
    if user and verify_password(credentials.password, user.hashed_password):
        return create_token(user)
    raise HTTPException(401)
```

**Fix**:
```python
# Good: Rate limiting + account lockout
@app.post("/auth/login")
@limiter.limit("5/minute")
async def login(request: Request, credentials: LoginRequest):
    # Check if account is locked
    if await is_account_locked(credentials.email):
        raise HTTPException(429, "Account temporarily locked")

    try:
        tokens = await auth.auth_service.login(
            email=credentials.email,
            password=credentials.password
        )
        return tokens
    except InvalidCredentialsException:
        # Increment failed attempts
        await increment_failed_attempts(credentials.email)
        raise HTTPException(401, "Invalid credentials")
```

### 2. Broken Authorization

**Vulnerability**:
```python
# Bad: No permission check
@app.delete("/users/{user_id}")
async def delete_user(user_id: str, current_user=Depends(auth.get_current_user)):
    # ❌ Any authenticated user can delete any user
    await user_service.delete(user_id)
    return {"status": "deleted"}
```

**Fix**:
```python
# Good: Permission check
@app.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    current_user=Depends(auth.require_permission("user:delete"))
):
    # ✅ Only users with permission can delete
    await user_service.delete(user_id)
    return {"status": "deleted"}
```

### 3. Sensitive Data Exposure

**Vulnerability**:
```python
# Bad: Returns password hash
@app.get("/users/{user_id}")
async def get_user(user_id: str):
    user = await UserModel.get(user_id)
    return user  # ❌ Includes hashed_password field
```

**Fix**:
```python
# Good: Use response schema
class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    # hashed_password excluded

@app.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: str):
    user = await UserModel.get(user_id)
    return user  # ✅ Only safe fields returned
```

### 4. Insecure Token Storage

**Vulnerability**:
```javascript
// Bad: Store token in localStorage
localStorage.setItem('access_token', token)  // ❌ Vulnerable to XSS
```

**Fix**:
```javascript
// Good: Use httpOnly cookies
// Set on server:
response.set_cookie(
    key="access_token",
    value=token,
    httponly=True,   // ✅ Not accessible to JavaScript
    secure=True,     // ✅ HTTPS only
    samesite="strict" // ✅ CSRF protection
)
```

### 5. Mass Assignment

**Vulnerability**:
```python
# Bad: Update all fields from request
@app.put("/users/{user_id}")
async def update_user(user_id: str, update_data: dict):
    user = await UserModel.get(user_id)
    # ❌ User could set is_admin=True
    for key, value in update_data.items():
        setattr(user, key, value)
    await user.save()
```

**Fix**:
```python
# Good: Explicit allowed fields
class UpdateUserRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    # is_admin field excluded

@app.put("/users/{user_id}")
async def update_user(user_id: str, update_data: UpdateUserRequest):
    user = await UserModel.get(user_id)
    # ✅ Only allowed fields can be updated
    if update_data.name:
        user.name = update_data.name
    if update_data.email:
        user.email = update_data.email
    await user.save()
```

---

## Incident Response

### Security Incident Plan

**1. Detection**
- Monitor audit logs for suspicious activity
- Set up alerts for anomalies
- Review failed login attempts
- Check permission denials

**2. Containment**
```python
# Immediately lock compromised account
await auth.user_service.lock_account(user_id=compromised_user.id)

# Revoke all tokens
await auth.auth_service.revoke_all_tokens(user_id=compromised_user.id)

# Disable compromised API keys
await auth.api_key_service.revoke_keys(user_id=compromised_user.id)
```

**3. Investigation**
```python
# Get user's recent activity
activity = await auth.audit_service.get_user_events(
    user_id=compromised_user.id,
    start_date=datetime.now() - timedelta(days=7)
)

# Check permission grants
permissions = await auth.permission_service.get_user_permissions(
    user_id=compromised_user.id
)

# Review entity access
entities = await auth.membership_service.get_user_entities(
    user_id=compromised_user.id
)
```

**4. Recovery**
```python
# Reset user password
await auth.auth_service.force_password_reset(user_id=compromised_user.id)

# Remove malicious role assignments
await auth.role_service.remove_user_roles(
    user_id=compromised_user.id,
    role_ids=suspicious_roles
)

# Restore from backup if needed
await restore_from_backup(backup_date=incident_date)
```

**5. Post-Incident**
- Document the incident
- Update security controls
- Review and update policies
- Conduct security training

### Emergency Contacts

**Security Team**:
- Security Lead: security@outlabs.io
- On-Call Engineer: oncall@outlabs.io
- Emergency: +1-XXX-XXX-XXXX

**Disclosure**:
For security vulnerabilities, email: security@outlabs.io

---

## Additional Resources

### Security Tools

- **OWASP ZAP**: Security testing
- **Bandit**: Python security linter
- **Safety**: Dependency vulnerability scanner
- **Trivy**: Container security scanner

### Security Standards

- **OWASP Top 10**: https://owasp.org/Top10/
- **NIST Cybersecurity Framework**: https://www.nist.gov/cyberframework
- **CIS Controls**: https://www.cisecurity.org/controls

### Training

- OWASP Secure Coding Practices
- SANS Security Awareness Training
- Internal security workshops

---

**Last Updated**: 2025-01-14
**Next Review**: Quarterly (Every 3 months)
**Owner**: Security Team

**Questions or concerns?** Contact security@outlabs.io
