# JWT Tokens

**Tags**: #authentication #jwt #tokens #stateless

Complete guide to JSON Web Tokens (JWT) in OutlabsAuth.

---

## What are JWT Tokens?

**JWT (JSON Web Token)** is a compact, URL-safe token format for securely transmitting information between parties as a JSON object.

**Structure**: `header.payload.signature`

**Example**:
```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyXzEyMyIsImV4cCI6MTY0MjU5NjAwMH0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c
```

**Decoded**:
```json
// Header
{
  "alg": "HS256",
  "typ": "JWT"
}

// Payload
{
  "sub": "user_123",
  "exp": 1642596000,
  "iat": 1642594200,
  "type": "access",
  "aud": "outlabs-auth"
}

// Signature (cryptographic)
```

---

## Token Types

OutlabsAuth uses two token types:

### 1. Access Token (15 minutes)

**Purpose**: Short-lived token for API requests

**Lifetime**: 15 minutes (configurable)

**Claims**:
```json
{
  "sub": "user_123",           // Subject (user ID)
  "exp": 1642596000,           // Expiration (Unix timestamp)
  "iat": 1642594200,           // Issued at
  "type": "access",            // Token type
  "aud": "outlabs-auth",       // Audience (prevents cross-app token reuse)
  "jti": "Abc123XyZ789..."     // JWT ID (for immediate revocation/blacklisting)
}
```

**Usage**:
```bash
GET /protected
Authorization: Bearer eyJhbGc...
```

**Security**: Short expiration limits damage if compromised

### 2. Refresh Token (30 days)

**Purpose**: Long-lived token to get new access tokens

**Lifetime**: 30 days (configurable)

**Claims**:
```json
{
  "sub": "user_123",
  "exp": 1645188000,           // 30 days from now
  "iat": 1642594200,
  "type": "refresh",
  "aud": "outlabs-auth",       // Audience (prevents cross-app token reuse)
  "jti": "Xyz789Abc123..."     // JWT ID (ensures token uniqueness, prevents collisions)
}
```

**Note**: The `jti` (JWT ID) was added to refresh tokens to prevent collisions when multiple sessions are created simultaneously for the same user. Each refresh token is guaranteed to be unique.

**Usage**:
```bash
POST /auth/refresh
{
  "refresh_token": "eyJhbGc..."
}
```

**Security**: Stored securely (httpOnly cookie recommended)

---

## Token Flow

```
┌─────────────────────────────────────────────────────────┐
│                    Login Flow                            │
└─────────────────────────────────────────────────────────┘

1. User logs in
   POST /auth/login
   {"email": "user@example.com", "password": "..."}

2. Backend generates tokens
   access_token = jwt.encode({
       "sub": user.id,
       "exp": now + 15min,
       "iat": now,
       "type": "access",
       "aud": "outlabs-auth",
       "jti": secrets.token_urlsafe(16)  # Unique JWT ID for blacklisting
   })

   refresh_token = jwt.encode({
       "sub": user.id,
       "exp": now + 30days,
       "iat": now,
       "type": "refresh",
       "aud": "outlabs-auth",
       "jti": secrets.token_urlsafe(16)  # Unique JWT ID (prevents collisions)
   })

3. Return both tokens
   {
       "access_token": "eyJ...",
       "refresh_token": "eyJ...",
       "expires_in": 900
   }

┌─────────────────────────────────────────────────────────┐
│                  Request Flow                            │
└─────────────────────────────────────────────────────────┘

4. Client stores tokens
   localStorage.setItem("access_token", token)
   // OR httpOnly cookie (more secure)

5. Client makes request with access token
   GET /protected
   Authorization: Bearer eyJ...

6. Backend validates token
   - Decode JWT
   - Verify signature
   - Check expiration
   - Extract user_id from "sub" claim

7. Return protected resource

┌─────────────────────────────────────────────────────────┐
│                  Refresh Flow                            │
└─────────────────────────────────────────────────────────┘

8. Access token expires (15 min later)

9. Client detects 401 Unauthorized

10. Client uses refresh token
    POST /auth/refresh
    {"refresh_token": "eyJ..."}

11. Backend validates refresh token
    - Decode JWT
    - Verify signature
    - Check expiration
    - Check type = "refresh"

12. Generate new access token
    new_access_token = jwt.encode({
        "sub": user.id,
        "exp": now + 15min,
        "type": "access"
    })

13. Return new access token
    {"access_token": "eyJ...", "expires_in": 900}

14. Client updates stored token and retries request
```

---

## Configuration

### JWT Settings

```python
from outlabs_auth import SimpleRBAC

auth = SimpleRBAC(
    database=db,
    secret_key="your-super-secret-key-change-in-production",
    algorithm="HS256",  # or "RS256" for asymmetric
    jwt_audience="your-app-name",  # Prevents cross-app token reuse
    access_token_expire_minutes=15,  # 15 minutes
    refresh_token_expire_days=30,  # 30 days
)
```

### Generate Strong Secret

```python
import secrets

# Generate 32-byte secret
secret = secrets.token_urlsafe(32)
print(secret)
# Output: xvKp7gHN3jF9mP2qR5sT8wY1zA3bC6dE9fG2hJ5kL8m
```

**Store in environment variables**:
```bash
# .env
JWT_SECRET=xvKp7gHN3jF9mP2qR5sT8wY1zA3bC6dE9fG2hJ5kL8m
```

### Algorithm Choice

#### HS256 (Symmetric)

**How it works**: Single shared secret for signing and verification

**Pros**:
- ✅ Faster (no asymmetric crypto)
- ✅ Simpler setup
- ✅ Good for most applications

**Cons**:
- ⚠️ Same secret signs and verifies
- ⚠️ Can't share with third parties

**Use when**: Single application, no token sharing needed

```python
auth = SimpleRBAC(
    database=db,
    secret_key="shared-secret",
    algorithm="HS256",
    jwt_audience="my-app"
)
```

#### RS256 (Asymmetric)

**How it works**: Private key signs, public key verifies

**Pros**:
- ✅ Public key can be shared
- ✅ Better for microservices
- ✅ Third parties can verify

**Cons**:
- ⚠️ Slower than HS256
- ⚠️ More complex setup

**Use when**: Multiple services need to verify tokens

```python
# Generate keys
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

# Private key
private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
    backend=default_backend()
)

private_pem = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
)

# Public key
public_key = private_key.public_key()
public_pem = public_key.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
)

# Use in OutlabsAuth
auth = SimpleRBAC(
    database=db,
    secret_key=private_pem,  # Private key for signing
    algorithm="RS256",
    jwt_audience="my-app"
)
```

---

## Token Validation

### Automatic Validation

OutlabsAuth automatically validates tokens in route dependencies:

```python
@app.get("/protected")
async def protected(ctx = Depends(auth.deps.require_auth())):
    # Token already validated by dependency
    user = ctx.metadata.get("user")
    return {"user_id": user.id}
```

**Validation steps**:
1. Extract token from `Authorization: Bearer {token}` header
2. Decode JWT
3. Verify signature
4. Check expiration (`exp` claim)
5. Check audience (`aud` claim)
6. Check token type (`type` claim)
7. Get user from database
8. Check user can authenticate (active and not locked)

### Manual Validation

```python
from jose import jwt, JWTError
from datetime import datetime, timezone

def validate_access_token(token: str, secret: str, audience: str = "outlabs-auth") -> dict:
    try:
        # Decode and verify (automatically checks signature, expiration, audience)
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience=audience,
            options={"verify_exp": True}
        )

        # Check token type
        if payload.get("type") != "access":
            raise Exception("Invalid token type")

        return payload

    except jwt.ExpiredSignatureError:
        raise Exception("Token expired")
    except JWTError as e:
        raise Exception(f"Invalid token: {e}")
```

---

## Token Refresh

### Automatic Refresh (Frontend)

```javascript
// axios interceptor for automatic refresh
axios.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // If 401 and haven't retried yet
    if (error.response.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        // Get new access token using refresh token
        const refreshToken = localStorage.getItem('refresh_token');
        const response = await axios.post('/auth/refresh', {
          refresh_token: refreshToken
        });

        const { access_token } = response.data;

        // Update stored token
        localStorage.setItem('access_token', access_token);

        // Retry original request with new token
        originalRequest.headers['Authorization'] = `Bearer ${access_token}`;
        return axios(originalRequest);

      } catch (refreshError) {
        // Refresh failed, redirect to login
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);
```

### Manual Refresh (Backend)

```python
@app.post("/auth/refresh")
async def refresh_token(refresh_token: str):
    try:
        # Validate refresh token
        payload = jwt.decode(
            refresh_token,
            auth.jwt_secret,
            algorithms=[auth.jwt_algorithm]
        )

        # Check token type
        if payload.get("type") != "refresh":
            raise HTTPException(400, "Invalid token type")

        # Get user
        user_id = payload["sub"]
        user = await auth.user_service.get_user_by_id(user_id)

        if not user or not user.can_authenticate():
            raise HTTPException(401, "User not found or cannot authenticate")

        # Generate new access token
        new_access_token = jwt.encode(
            {
                "sub": user.id,
                "exp": datetime.utcnow() + timedelta(seconds=900),
                "iat": datetime.utcnow(),
                "type": "access"
            },
            auth.jwt_secret,
            algorithm=auth.jwt_algorithm
        )

        return {
            "access_token": new_access_token,
            "token_type": "bearer",
            "expires_in": 900
        }

    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Refresh token expired")
    except jwt.JWTError:
        raise HTTPException(401, "Invalid refresh token")
```

---

## Token Revocation

### Why Revocation?

**Problem**: JWTs are stateless - once issued, they're valid until expiration.

**Need revocation for**:
- User logout
- Password change
- Account deletion
- Security breach

### Strategy 1: Short Expiration (Recommended)

**Approach**: Keep access tokens short-lived (15 min)

**Benefits**:
- ✅ No database lookup needed
- ✅ Stateless
- ✅ Scales infinitely

**Trade-off**:
- ⚠️ Max 15 min window if compromised

```python
auth = SimpleRBAC(
    database=db,
    access_token_expire_minutes=15  # 15 minutes
)
```

### Strategy 2: Token Blacklist

**Approach**: Store revoked token IDs in Redis

**Implementation**:
```python
import redis.asyncio as redis

class TokenBlacklist:
    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url)

    async def revoke(self, token: str, ttl: int):
        """Revoke token for remaining TTL"""
        payload = jwt.decode(token, verify=False)
        jti = payload.get("jti")  # JWT ID

        if jti:
            await self.redis.setex(
                f"revoked:{jti}",
                ttl,
                "1"
            )

    async def is_revoked(self, token: str) -> bool:
        """Check if token is revoked"""
        payload = jwt.decode(token, verify=False)
        jti = payload.get("jti")

        if jti:
            return await self.redis.exists(f"revoked:{jti}")
        return False

# Use in auth dependency
blacklist = TokenBlacklist("redis://localhost:6379")

async def require_auth_with_revocation():
    async def dependency(authorization: str = Header(None)):
        if not authorization:
            raise HTTPException(401)

        token = authorization.replace("Bearer ", "")

        # Check blacklist
        if await blacklist.is_revoked(token):
            raise HTTPException(401, "Token revoked")

        # Validate token
        # ... rest of validation

    return dependency
```

### Strategy 3: Refresh Token Rotation

**Approach**: Issue new refresh token with each refresh

**Benefits**:
- ✅ Limits refresh token reuse
- ✅ Detects token theft

```python
@app.post("/auth/refresh")
async def refresh_token(refresh_token: str):
    # Validate old refresh token
    payload = jwt.decode(refresh_token, auth.jwt_secret)
    user_id = payload["sub"]

    # Generate NEW access token
    new_access_token = jwt.encode({...})

    # Generate NEW refresh token
    new_refresh_token = jwt.encode({
        "sub": user_id,
        "exp": datetime.utcnow() + timedelta(days=30),
        "type": "refresh"
    })

    # Revoke old refresh token
    await blacklist.revoke(refresh_token, ttl=2592000)

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token  # NEW refresh token!
    }
```

---

## Token Storage

### Frontend Storage Options

#### Option 1: localStorage (Simplest)

```javascript
// Store tokens
localStorage.setItem('access_token', accessToken);
localStorage.setItem('refresh_token', refreshToken);

// Retrieve tokens
const token = localStorage.getItem('access_token');

// Use in requests
axios.get('/protected', {
  headers: { Authorization: `Bearer ${token}` }
});
```

**Pros**:
- ✅ Simple to implement
- ✅ Persists across tabs

**Cons**:
- ⚠️ Vulnerable to XSS attacks
- ⚠️ Accessible by JavaScript

#### Option 2: httpOnly Cookies (Most Secure)

```python
# Backend: Set cookie on login
@app.post("/auth/login")
async def login(response: Response, credentials: dict):
    tokens = await auth.auth_service.login(...)

    # Set httpOnly cookie
    response.set_cookie(
        key="access_token",
        value=tokens["access_token"],
        httponly=True,  # Not accessible by JavaScript
        secure=True,    # HTTPS only
        samesite="strict",  # CSRF protection
        max_age=900     # 15 minutes
    )

    return {"message": "Logged in"}

# Frontend: Cookies sent automatically
fetch('/protected', {
  credentials: 'include'  // Include cookies
});
```

**Pros**:
- ✅ Immune to XSS
- ✅ Automatic CSRF protection
- ✅ Sent automatically with requests

**Cons**:
- ⚠️ More complex setup
- ⚠️ Requires CORS configuration

#### Option 3: Memory + Refresh Cookie (Hybrid)

```javascript
// Store access token in memory (secure)
let accessToken = null;

// Store refresh token in httpOnly cookie
// Access token lost on page refresh, use refresh token to get new one

async function getAccessToken() {
  if (!accessToken) {
    // Get new access token using refresh cookie
    const response = await fetch('/auth/refresh', {
      credentials: 'include'
    });
    const data = await response.json();
    accessToken = data.access_token;
  }
  return accessToken;
}
```

**Pros**:
- ✅ Access token immune to XSS (memory only)
- ✅ Refresh token secure (httpOnly cookie)
- ✅ Best security

**Cons**:
- ⚠️ Most complex
- ⚠️ Access token lost on refresh (acceptable)

---

## Custom Claims

Add custom data to JWT payload:

```python
from outlabs_auth.services import AuthService

class MyAuthService(AuthService):
    async def generate_access_token(self, user):
        # Get user roles
        roles = await self.role_service.get_user_roles(user.id)

        # Generate token with custom claims
        token = jwt.encode(
            {
                "sub": user.id,
                "exp": datetime.utcnow() + timedelta(seconds=900),
                "type": "access",
                # Custom claims
                "email": user.email,
                "roles": [role.name for role in roles],
                "is_superuser": user.is_superuser,
            },
            self.jwt_secret,
            algorithm=self.jwt_algorithm
        )

        return token

# Access custom claims in route
@app.get("/admin")
async def admin_route(ctx = Depends(auth.deps.require_auth())):
    token_payload = ctx.get("token_payload")  # JWT claims
    roles = token_payload.get("roles", [])

    if "admin" not in roles:
        raise HTTPException(403, "Admin access required")

    return {"message": "Welcome, admin!"}
```

---

## Security Best Practices

### 1. Use Strong Secrets

```python
# ❌ BAD
JWT_SECRET = "secret"

# ✅ GOOD
JWT_SECRET = secrets.token_urlsafe(32)
```

### 2. Short Access Tokens

```python
# ❌ BAD: Long expiration
access_token_lifetime=86400  # 24 hours

# ✅ GOOD: Short expiration
access_token_lifetime=900  # 15 minutes
```

### 3. Validate Everything

```python
# Always check:
# - Signature
# - Expiration
# - Token type
# - User exists and is active
```

### 4. Use HTTPS

```python
# Never send tokens over HTTP
# Always use HTTPS in production
```

### 5. Don't Store Sensitive Data

```python
# ❌ BAD: Sensitive data in token
token = jwt.encode({
    "sub": user.id,
    "password": user.password,  # NEVER!
    "ssn": user.ssn  # NEVER!
})

# ✅ GOOD: Only non-sensitive IDs
token = jwt.encode({
    "sub": user.id,  # OK
    "email": user.email,  # OK (if needed)
    "roles": ["admin"]  # OK
})
```

---

## Token Revocation

### Overview

OutlabsAuth supports **configurable token revocation strategies**:

| Mode | Access Token Revocation | Refresh Token Revocation | Configuration |
|------|------------------------|-------------------------|---------------|
| **Standard** | 15-min window | Immediate (MongoDB) | `store_refresh_tokens=True`<br>`enable_token_blacklist=False` |
| **High Security** | Immediate (Redis) | Immediate (MongoDB) | `store_refresh_tokens=True`<br>`enable_token_blacklist=True` |
| **Stateless** | 15-min window | N/A (no storage) | `store_refresh_tokens=False`<br>`enable_token_blacklist=False` |

### Standard Mode (Default)

```python
auth = EnterpriseRBAC(
    database=db,
    secret_key=secret,
    store_refresh_tokens=True,      # Store refresh tokens in MongoDB
    enable_token_blacklist=False    # Access tokens valid until expiration
)

# Logout behavior:
# - Refresh token: Revoked immediately in MongoDB
# - Access token: Valid for remaining lifetime (up to 15 min)
```

**Why this works:**
- Access tokens are short-lived (15 min) - acceptable security window
- Refresh tokens revoked immediately - can't get new access tokens
- No Redis required - simpler infrastructure

### High Security Mode

```python
auth = EnterpriseRBAC(
    database=db,
    secret_key=secret,
    redis_url="redis://localhost:6379",
    store_refresh_tokens=True,       # Store refresh tokens in MongoDB
    enable_token_blacklist=True      # Blacklist access tokens in Redis
)

# Logout behavior:
# - Refresh token: Revoked immediately in MongoDB
# - Access token: Blacklisted immediately in Redis
```

**Use cases:**
- Banking applications
- Healthcare systems
- High-security environments
- Compliance requirements (HIPAA, PCI-DSS)

### How Blacklisting Works

**On Logout:**
```python
# 1. Access token JTI added to Redis blacklist
await redis.set(
    f"blacklist:jwt:{jti}",
    "revoked",
    ttl=remaining_token_lifetime  # Auto-expires with token
)

# 2. Refresh token revoked in MongoDB
token.is_revoked = True
await token.save()
```

**On Authentication:**
```python
# 1. Decode JWT (validate signature, expiration)
payload = jwt.decode(token, secret)

# 2. Check blacklist (if Redis available)
jti = payload.get("jti")
if redis.exists(f"blacklist:jwt:{jti}"):
    raise TokenRevokedError()

# 3. Continue with user lookup
```

### JTI Claim

The `jti` (JWT ID) claim is a **unique identifier** for each access token:

```json
{
  "sub": "user_123",
  "exp": 1642596000,
  "jti": "Abc123XyZ789..."  // ← Unique ID for this token
}
```

**Purpose:**
- Enables individual token blacklisting
- Generated with `secrets.token_urlsafe(16)` (cryptographically secure)
- Required for immediate access token revocation

### Automatic Cleanup

Expired and revoked tokens are automatically cleaned up:

```python
auth = EnterpriseRBAC(
    database=db,
    secret_key=secret,
    enable_token_cleanup=True,           # Enable automatic cleanup
    token_cleanup_interval_hours=24      # Run every 24 hours
)

# Cleanup removes:
# - Expired refresh tokens (past expires_at date)
# - Old revoked tokens (revoked > 7 days ago)
```

**Cleanup is a background task** that runs inside the FastAPI application. It respects the configured interval and only runs if `store_refresh_tokens=True`.

---

## Next Steps

- **[[23-API-Keys|API Keys]]** - Long-lived credentials
- **[[24-Service-Tokens|Service Tokens]]** - Microservice authentication
- **[[91-Auth-Router|Auth Router]]** - Logout endpoint details
- **[[110-Security-Best-practices|Security Best Practices]]** - Complete security guide

---

**Previous**: [[21-Email-Password-Auth|← Email & Password Auth]]
**Next**: [[23-API-Keys|API Keys →]]
