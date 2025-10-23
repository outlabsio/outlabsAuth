# Authentication Overview

**Tags**: #authentication #overview #authn

Overview of OutlabsAuth's authentication system and supported methods.

---

## What is Authentication?

**Authentication (AuthN)** is the process of verifying a user's identity.

**Question**: "Who are you?"

**Methods**:
- Email/Password
- OAuth (Google, Facebook, GitHub, etc.)
- API Keys
- JWT Service Tokens

**Result**: User credentials → Access granted (JWT token)

---

## Authentication Methods

### 1. Email/Password Authentication

Traditional username/password authentication.

**Flow**:
```
User → Register → Email + Password
     → Verify Email (optional)
     → Login → Email + Password
     → Receive JWT tokens
```

**Features**:
- ✅ argon2id password hashing (best practice)
- ✅ Email verification
- ✅ Password reset flow
- ✅ Password complexity requirements
- ✅ Account lockout after failed attempts

**Use Cases**:
- Traditional web applications
- Mobile apps
- Internal tools

**See**: [[21-Email-Password-Auth|Email & Password Authentication]]

---

### 2. JWT Tokens

JSON Web Tokens for stateless authentication.

**Two Token Types**:

#### Access Token (15 minutes)
```json
{
  "sub": "user_123",
  "exp": 1642596000,
  "type": "access"
}
```
- Short-lived (15 min default)
- Used for API requests
- Included in `Authorization: Bearer {token}` header

#### Refresh Token (30 days)
```json
{
  "sub": "user_123",
  "exp": 1645188000,
  "type": "refresh"
}
```
- Long-lived (30 days default)
- Used to get new access tokens
- Stored securely (httpOnly cookie recommended)

**Flow**:
```
Login → Access Token + Refresh Token
     → Use Access Token for API calls
     → Access Token expires (15 min)
     → Use Refresh Token to get new Access Token
     → Repeat
```

**Features**:
- ✅ Stateless (no database lookup on every request)
- ✅ HS256/RS256 algorithms
- ✅ Configurable expiration
- ✅ Automatic refresh
- ✅ Revocation support

**See**: [[22-JWT-Tokens|JWT Tokens]]

---

### 3. API Keys

Long-lived credentials for programmatic access.

**Format**: `ola_1234567890abcdef1234567890abcdef`

**Structure**:
- `ola_` - Prefix (scannable, identifiable)
- `123456789012` - 12-character public ID
- Full key hashed with argon2id

**Features**:
- ✅ argon2id hashing (not bcrypt!)
- ✅ Rate limiting per key
- ✅ Temporary locks after failed attempts
- ✅ Usage tracking (Redis counters)
- ✅ Rotation support
- ✅ Revocation

**Use Cases**:
- API services
- CLI tools
- Server-to-server communication
- Webhooks

**See**: [[23-API-Keys|API Keys]]

---

### 4. JWT Service Tokens (DD-034)

Ultra-fast JWT tokens for internal microservices.

**Performance**: ~0.5ms authentication (vs ~50ms for API keys)

**Characteristics**:
- Long expiration (90 days default)
- No rate limiting
- No failed attempt tracking
- Minimal validation

**Use Cases**:
- Microservice-to-microservice
- Internal services only
- Trusted environments

**Security**: Only use in trusted internal networks!

**See**: [[24-Service-Tokens|JWT Service Tokens]]

---

### 5. OAuth/Social Login

Authenticate via third-party providers.

**Supported Providers**:
- Google
- Facebook
- GitHub
- Microsoft
- Discord

**Flow**:
```
User → Click "Sign in with Google"
     → Redirect to Google
     → User authenticates with Google
     → Google redirects back with code
     → Exchange code for access token
     → Get user info from Google
     → Create/update user in your app
     → Return JWT tokens
```

**Features**:
- ✅ Stateless OAuth (JWT state tokens)
- ✅ Account linking
- ✅ No password management
- ✅ Email verification from provider
- ✅ CSRF protection

**See**: [[30-OAuth-Overview|OAuth Overview]]

---

## Multi-Source Authentication (DD-034)

**Try multiple authentication methods in sequence**.

**Supported Sources**:
1. JWT (Bearer token)
2. API Key (X-API-Key header)
3. Service Token (X-Service-Token header)
4. Cookie
5. Superuser bypass
6. Anonymous access

**Flow**:
```python
backends = [
    AuthBackend("jwt", BearerTransport(), JWTStrategy()),
    AuthBackend("api_key", ApiKeyTransport(), ApiKeyStrategy()),
    AuthBackend("service", HeaderTransport("X-Service-Token"), ServiceTokenStrategy()),
]

# Try each backend until one succeeds
for backend in backends:
    try:
        credentials = await backend.transport.get_credentials(request)
        user = await backend.strategy.validate(credentials)
        return user  # Success!
    except Exception:
        continue  # Try next backend

# All failed
raise HTTPException(401, "Authentication failed")
```

**Use Cases**:
- APIs with multiple client types
- Gradual migration (support old + new auth)
- Flexible authentication requirements

**See**: [[25-Multi-Source-Auth|Multi-Source Authentication]]

---

## Authentication Architecture

### Transport/Strategy Pattern (DD-038)

**Separation of concerns**: How credentials are delivered vs how they're validated.

#### Transport: How credentials are delivered

```python
class BearerTransport:
    async def get_credentials(self, request: Request) -> Optional[str]:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return auth_header[7:]  # Extract token
        return None

class ApiKeyTransport:
    async def get_credentials(self, request: Request) -> Optional[str]:
        return request.headers.get("X-API-Key")

class CookieTransport:
    async def get_credentials(self, request: Request) -> Optional[str]:
        return request.cookies.get("access_token")
```

#### Strategy: How credentials are validated

```python
class JWTStrategy:
    async def validate(self, token: str) -> User:
        # Decode JWT
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        user_id = payload["sub"]

        # Get user from database
        user = await user_service.get_user(user_id)
        return user

class ApiKeyStrategy:
    async def validate(self, key: str) -> User:
        # Extract prefix and ID
        prefix, key_id = parse_api_key(key)

        # Get API key from database
        api_key = await api_key_service.get_by_prefix_and_id(prefix, key_id)

        # Verify hash
        if not verify_argon2(key, api_key.hashed_key):
            raise InvalidCredentials()

        # Get user
        user = await user_service.get_user(api_key.user_id)
        return user
```

#### Composition

```python
# JWT via Bearer header
jwt_backend = AuthBackend(
    name="jwt",
    transport=BearerTransport(),
    strategy=JWTStrategy(secret="secret")
)

# API Key via custom header
api_key_backend = AuthBackend(
    name="api_key",
    transport=ApiKeyTransport(),
    strategy=ApiKeyStrategy()
)
```

**Benefits**:
- ✅ Composable (mix and match)
- ✅ Testable (test transport and strategy separately)
- ✅ Extensible (add custom transports/strategies)
- ✅ Clear separation of concerns

**See**: [[100-Transport-Strategy-Pattern|Transport/Strategy Pattern]]

---

## Authentication Flow Examples

### Example 1: Email/Password Login

```
1. User submits credentials
   POST /auth/login
   {"email": "user@example.com", "password": "secret"}

2. Backend validates
   → Get user by email
   → Verify password hash (argon2id)
   → Check if user is active
   → Check if email is verified (optional)

3. Generate tokens
   → Access token (15 min)
   → Refresh token (30 days)

4. Return tokens
   {
     "access_token": "eyJhbGc...",
     "refresh_token": "eyJhbGc...",
     "token_type": "bearer",
     "expires_in": 900
   }

5. Client uses access token
   GET /protected
   Authorization: Bearer eyJhbGc...

6. Access token expires (15 min)
   → Client uses refresh token
   POST /auth/refresh
   {"refresh_token": "eyJhbGc..."}

   → Get new access token
   {"access_token": "eyJhbGc...", "expires_in": 900}
```

### Example 2: API Key Authentication

```
1. User creates API key (while authenticated)
   POST /api-keys
   Authorization: Bearer eyJhbGc...
   {"name": "Production API Key"}

2. Backend generates key
   → Generate random 32-byte key
   → Add "ola_" prefix + 12-char ID
   → Hash full key with argon2id
   → Store hash + metadata in database

3. Return full key (ONCE!)
   {
     "id": "key_123",
     "key": "ola_abc123xyz789_full_key_here",
     "name": "Production API Key",
     "created_at": "2025-01-23T10:00:00Z"
   }

4. Client saves key securely

5. Client uses key for requests
   GET /protected
   X-API-Key: ola_abc123xyz789_full_key_here

6. Backend validates
   → Extract prefix + ID
   → Look up key in database
   → Verify hash (argon2id)
   → Check rate limits
   → Check temporary locks
   → Return user
```

### Example 3: OAuth Login (Google)

```
1. User clicks "Sign in with Google"
   GET /auth/google/authorize

2. Backend generates state token
   → JWT with aud="outlabs-auth:oauth-state"
   → 10 minute expiration
   → No database write!

3. Redirect to Google
   https://accounts.google.com/o/oauth2/v2/auth?
     client_id=...
     &redirect_uri=https://myapp.com/auth/google/callback
     &state=eyJhbGc...
     &scope=openid+email+profile

4. User authenticates with Google
   → Username/password
   → 2FA (if enabled)
   → Grant permissions

5. Google redirects to callback
   GET /auth/google/callback?code=4/abc123&state=eyJhbGc...

6. Backend validates
   → Verify state token (JWT signature + expiration)
   → Exchange code for access token
   → Get user info from Google
   → Check if social account exists
   → Create/update user
   → Generate JWT tokens

7. Return tokens
   {
     "access_token": "eyJhbGc...",
     "refresh_token": "eyJhbGc...",
     "token_type": "bearer",
     "expires_in": 900
   }
```

---

## Security Best Practices

### 1. Password Security

**Hashing**: argon2id (not bcrypt, not sha256!)

```python
# Hash password
hashed = argon2id.hash("user_password")

# Verify password
is_valid = argon2id.verify("user_password", hashed)
```

**Why argon2id**:
- ✅ Memory-hard (resistant to GPU attacks)
- ✅ OWASP recommended
- ✅ Winner of Password Hashing Competition (2015)
- ✅ Better than bcrypt for new applications

### 2. JWT Security

**Secrets**:
- Use strong random secrets (32+ bytes)
- Rotate secrets periodically
- Store secrets in environment variables (never in code!)

```python
# Generate secret
import secrets
secret = secrets.token_urlsafe(32)
```

**Algorithms**:
- HS256 (symmetric, shared secret)
- RS256 (asymmetric, public/private key)

**Expiration**:
- Short access tokens (15 min)
- Long refresh tokens (30 days)
- Always check expiration

### 3. API Key Security

**Storage**: argon2id hashing (never store plaintext!)

**Prefixes**: `ola_` for scannability
- GitHub can scan for leaked keys
- Developers can identify keys in logs
- Rotation is easier

**Rate Limiting**: Per-key limits
- Prevent abuse
- Track usage
- Temporary locks after failed attempts

### 4. OAuth Security

**State Tokens**: CSRF protection
- JWT-signed
- 10-minute expiration
- Audience claim validation

**Associate by Email**: Defaults to False
- Prevent account hijacking
- Only enable for trusted providers (Google, Microsoft)

**Verified Emails**: Check provider verification
- Trust Google, Microsoft, Apple
- Don't trust GitHub, Discord by default

### 5. Multi-Source Security

**Fallback Order**: Most secure first
1. JWT (short-lived, user-specific)
2. API Key (long-lived, revocable)
3. Service Token (internal only, trusted)

**Never Skip Validation**: Always validate credentials, even for internal services.

---

## Performance Considerations

### Authentication Performance

| Method | Validation Time | Use Case |
|--------|----------------|----------|
| JWT Service Token | ~0.3ms | Internal microservices |
| JWT Access Token | ~0.5ms | User requests |
| API Key | ~50ms | External API clients |
| OAuth | ~200-500ms | User login (one-time) |

**Optimization Tips**:
1. Use JWT for user requests (fast validation)
2. Use service tokens for microservices (fastest)
3. Cache permission checks (not authentication!)
4. Use Redis for API key counters

### Scaling Authentication

**Stateless JWT**: No database lookup per request
- ✅ Scales infinitely
- ✅ No session storage
- ✅ Works across multiple servers

**API Key Counters**: Redis tracking (DD-033)
- ✅ 99%+ reduction in database writes
- ✅ Periodic flush to MongoDB
- ✅ High performance

**Refresh Token Rotation**: Balance security and UX
- Short access tokens (15 min) - Security
- Long refresh tokens (30 days) - UX
- Automatic refresh on expiration

---

## Router Factories

Pre-built FastAPI routers for authentication:

### get_auth_router()

```python
from outlabs_auth.routers import get_auth_router

app.include_router(
    get_auth_router(auth),
    prefix="/auth",
    tags=["auth"]
)
```

**Endpoints**:
- `POST /register` - User registration
- `POST /login` - Email/password login
- `POST /refresh` - Refresh access token
- `POST /logout` - Logout (invalidate tokens)
- `POST /forgot-password` - Request password reset
- `POST /reset-password` - Reset password with token
- `POST /verify` - Verify email

**See**: [[91-Auth-Router|Auth Router Reference]]

### get_users_router()

```python
from outlabs_auth.routers import get_users_router

app.include_router(
    get_users_router(auth),
    prefix="/users",
    tags=["users"]
)
```

**Endpoints**:
- `GET /me` - Get current user profile
- `PATCH /me` - Update profile
- `POST /me/change-password` - Change password

**See**: [[92-Users-Router|Users Router Reference]]

### get_api_keys_router()

```python
from outlabs_auth.routers import get_api_keys_router

app.include_router(
    get_api_keys_router(auth),
    prefix="/api-keys",
    tags=["api-keys"]
)
```

**Endpoints**:
- `POST /` - Create API key
- `GET /` - List user's API keys
- `DELETE /{key_id}` - Revoke API key
- `POST /{key_id}/rotate` - Rotate API key

**See**: [[93-API-Keys-Router|API Keys Router Reference]]

### get_oauth_router()

```python
from outlabs_auth.oauth.providers import get_google_client
from outlabs_auth.routers import get_oauth_router

google = get_google_client(client_id="...", client_secret="...")

app.include_router(
    get_oauth_router(google, auth, state_secret="..."),
    prefix="/auth/google",
    tags=["auth"]
)
```

**Endpoints**:
- `GET /authorize` - Start OAuth flow
- `GET /callback` - Complete OAuth flow

**See**: [[94-OAuth-Router|OAuth Router Reference]]

---

## Next Steps

Explore specific authentication methods:

- **[[21-Email-Password-Auth|Email & Password]]** - Traditional authentication
- **[[22-JWT-Tokens|JWT Tokens]]** - Token-based authentication
- **[[23-API-Keys|API Keys]]** - API key authentication
- **[[24-Service-Tokens|Service Tokens]]** - Microservice authentication
- **[[25-Multi-Source-Auth|Multi-Source]]** - Multiple auth methods
- **[[30-OAuth-Overview|OAuth]]** - Social login

---

**Previous**: [[04-Basic-Concepts|← Basic Concepts]]
**Next**: [[21-Email-Password-Auth|Email & Password Auth →]]
