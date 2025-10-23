# OAuth Overview

**Tags**: #oauth #social-login #authentication #oauth2

Complete overview of OutlabsAuth's OAuth/social login system.

---

## What is OAuth?

**OAuth 2.0** is an authorization framework that lets users grant your application access to their accounts on other services (Google, Facebook, GitHub, etc.) without sharing passwords.

**Use Cases**:
- "Sign in with Google"
- "Sign in with Facebook"
- "Sign in with GitHub"
- Social account linking

**Benefits**:
- ✅ No password management for users
- ✅ Faster registration/login
- ✅ Verified emails (providers verify)
- ✅ Better conversion rates
- ✅ Access to user profile data

---

## OAuth Flow

### Standard OAuth 2.0 Authorization Code Flow

```
┌─────────┐                                  ┌─────────────┐
│  User   │                                  │ Your FastAPI│
│ Browser │                                  │     App     │
└─────────┘                                  └─────────────┘
     │                                               │
     │  1. Click "Sign in with Google"              │
     │─────────────────────────────────────────────>│
     │                                               │
     │  2. Redirect to Google (with state token)    │
     │<─────────────────────────────────────────────│
     │                                               │
┌─────────┐                                         │
│ Google  │                                         │
│ Auth    │                                         │
└─────────┘                                         │
     │                                               │
     │  3. User authenticates with Google           │
     │     (username/password, 2FA, etc.)           │
     │                                               │
     │  4. User grants permissions                  │
     │     ("Allow app to access your email")       │
     │                                               │
     │  5. Redirect to callback (with code + state) │
     │──────────────────────────────────────────────>│
     │                                               │
     │                                  6. Validate state token
     │                                  7. Exchange code for access token
     │                                  8. Get user info from Google
     │                                  9. Create/update user
     │                                 10. Generate JWT tokens
     │                                               │
     │  11. Return JWT tokens                        │
     │<─────────────────────────────────────────────│
     │                                               │
     │  12. Access protected resources               │
     │─────────────────────────────────────────────>│
     │                                               │
```

### Key Concepts

1. **Authorization URL**: Where user goes to authenticate with provider
2. **Callback URL**: Where provider redirects after authentication
3. **Authorization Code**: Short-lived code exchanged for access token
4. **State Token**: CSRF protection (prevents account hijacking)
5. **Access Token**: Token to fetch user info from provider
6. **User Info**: Email, name, profile picture from provider

---

## OutlabsAuth OAuth Implementation

### Key Features

#### 1. Stateless OAuth (DD-042)

**Problem**: Traditional OAuth requires storing state in database.

**Solution**: JWT-based state tokens (no database writes!).

```python
# Generate state token (JWT)
state = generate_state_token({}, state_secret, lifetime_seconds=600)

# State token contains:
{
  "aud": "outlabs-auth:oauth-state",
  "iat": 1234567890,
  "exp": 1234568490  # 10 minutes
}

# Validate on callback (no database lookup!)
decoded = decode_state_token(state, state_secret)
```

**Benefits**:
- ✅ No database writes
- ✅ Zero storage costs
- ✅ Scales infinitely
- ✅ CSRF protection via signature

#### 2. httpx-oauth Integration (DD-045)

**Library**: `httpx-oauth` - Async OAuth clients for FastAPI.

**Why httpx-oauth**:
- ✅ Async/await (FastAPI native)
- ✅ Multiple providers (Google, Facebook, GitHub, etc.)
- ✅ Well-maintained (Frankie567, creator of FastAPI-Users)
- ✅ Easy to use

**Pre-configured Clients**:
```python
from outlabs_auth.oauth.providers import (
    get_google_client,
    get_facebook_client,
    get_github_client,
    get_microsoft_client,
    get_discord_client,
)

google = get_google_client(client_id="...", client_secret="...")
```

#### 3. Router Factories (DD-043, DD-044)

**Two Router Factories**:

1. **`get_oauth_router()`** - New user registration or login
   ```python
   # GET /auth/google/authorize - Start OAuth flow
   # GET /auth/google/callback - Complete OAuth flow
   ```

2. **`get_oauth_associate_router()`** - Link OAuth to existing account
   ```python
   # GET /auth/google/associate/authorize - Start linking (requires auth)
   # GET /auth/google/associate/callback - Complete linking
   ```

**Both use same state token pattern**, but associate router includes `user_id` in state to prevent account hijacking.

#### 4. Account Linking Security (DD-046)

**Problem**: Email-based account linking can be exploited:
1. Attacker registers with victim's email on provider
2. Attacker triggers OAuth flow
3. Application links attacker's OAuth account to victim's existing account
4. Attacker gains access to victim's account

**Solution**: `associate_by_email` defaults to **False**.

```python
router = get_oauth_router(
    google,
    auth,
    state_secret="...",
    associate_by_email=False  # Default: Don't auto-link by email
)
```

**Safe Linking**: Use `get_oauth_associate_router()` which validates authenticated user.

---

## Quick Start

### Step 1: Install OAuth Dependencies

```bash
pip install outlabs-auth[oauth]
```

### Step 2: Get OAuth Credentials

#### Google OAuth

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create project
3. Enable "Google+ API"
4. Create OAuth 2.0 credentials
5. Add authorized redirect URI: `http://localhost:8000/auth/google/callback`
6. Copy Client ID and Client Secret

#### GitHub OAuth

1. Go to [GitHub Settings > Developer settings > OAuth Apps](https://github.com/settings/developers)
2. Create new OAuth App
3. Set callback URL: `http://localhost:8000/auth/github/callback`
4. Copy Client ID and Client Secret

### Step 3: Add OAuth Routes

```python
from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient
from outlabs_auth import SimpleRBAC
from outlabs_auth.oauth.providers import get_google_client, get_github_client
from outlabs_auth.routers import get_oauth_router

app = FastAPI()
mongo_client = AsyncIOMotorClient("mongodb://localhost:27017")
db = mongo_client["myapp"]
auth = SimpleRBAC(database=db)

# Initialize auth
@app.on_event("startup")
async def startup():
    await auth.initialize()

# Google OAuth
google = get_google_client(
    client_id="123456789.apps.googleusercontent.com",
    client_secret="your-google-secret"
)

app.include_router(
    get_oauth_router(
        google,
        auth,
        state_secret="different-secret-from-jwt",  # Use different secret!
        associate_by_email=True,  # Link to existing users by email
        is_verified_by_default=True  # Trust Google's verification
    ),
    prefix="/auth/google",
    tags=["auth"]
)

# GitHub OAuth
github = get_github_client(
    client_id="your-github-client-id",
    client_secret="your-github-secret"
)

app.include_router(
    get_oauth_router(
        github,
        auth,
        state_secret="different-secret-from-jwt",
        associate_by_email=False,  # Don't auto-link (GitHub email might not be verified)
        is_verified_by_default=False
    ),
    prefix="/auth/github",
    tags=["auth"]
)
```

### Step 4: Frontend Integration

```javascript
// React/Vue/Angular example
async function signInWithGoogle() {
  // 1. Get authorization URL from backend
  const response = await fetch('http://localhost:8000/auth/google/authorize');
  const data = await response.json();

  // 2. Redirect user to Google
  window.location.href = data.authorization_url;
}

// After OAuth callback, backend redirects to frontend with tokens
// GET /callback?access_token=...&refresh_token=...

// 3. Extract tokens from URL or handle in frontend route
const params = new URLSearchParams(window.location.search);
const accessToken = params.get('access_token');
const refreshToken = params.get('refresh_token');

// 4. Store tokens and use for API calls
localStorage.setItem('access_token', accessToken);
localStorage.setItem('refresh_token', refreshToken);
```

---

## Supported Providers

### Google

```python
from outlabs_auth.oauth.providers import get_google_client

google = get_google_client(
    client_id="123456789.apps.googleusercontent.com",
    client_secret="your-secret"
)

# Scopes: openid, email, profile
# Returns: email, name, profile picture
```

**Setup**: [[31-OAuth-Setup#Google|Google OAuth Setup]]

### Facebook

```python
from outlabs_auth.oauth.providers import get_facebook_client

facebook = get_facebook_client(
    client_id="your-facebook-app-id",
    client_secret="your-secret"
)

# Scopes: email, public_profile
# Returns: email, name, profile picture
```

**Setup**: [[31-OAuth-Setup#Facebook|Facebook OAuth Setup]]

### GitHub

```python
from outlabs_auth.oauth.providers import get_github_client

github = get_github_client(
    client_id="your-github-client-id",
    client_secret="your-secret"
)

# Scopes: user:email
# Returns: email, username, avatar
```

**Setup**: [[31-OAuth-Setup#GitHub|GitHub OAuth Setup]]

### Microsoft

```python
from outlabs_auth.oauth.providers import get_microsoft_client

microsoft = get_microsoft_client(
    client_id="your-azure-app-id",
    client_secret="your-secret",
    tenant="common"  # or specific tenant ID
)

# Scopes: openid, email, profile
# Returns: email, name
```

**Setup**: [[31-OAuth-Setup#Microsoft|Microsoft OAuth Setup]]

### Discord

```python
from outlabs_auth.oauth.providers import get_discord_client

discord = get_discord_client(
    client_id="your-discord-app-id",
    client_secret="your-secret"
)

# Scopes: identify, email
# Returns: email, username, avatar
```

**Setup**: [[31-OAuth-Setup#Discord|Discord OAuth Setup]]

---

## Account Linking

### Scenario 1: New User (Registration via OAuth)

```python
# User clicks "Sign in with Google"
# → No existing account
# → Create new user with Google account linked

@app.get("/auth/google/callback")
async def callback(code: str, state: str):
    # 1. Validate state
    # 2. Exchange code for token
    # 3. Get user info
    # 4. Check if social account exists
    social_account = await db.social_accounts.find_one({
        "provider": "google",
        "provider_user_id": google_user_id
    })

    if not social_account:
        # 5. Create new user
        user = await auth.user_service.create_user(
            email=google_email,
            password=None,  # No password for OAuth users
            is_verified=True  # Trust Google's verification
        )

        # 6. Link social account
        await db.social_accounts.insert_one({
            "user_id": user.id,
            "provider": "google",
            "provider_user_id": google_user_id,
            "email": google_email,
            "email_verified": True
        })

    # 7. Generate JWT tokens
    # 8. Return tokens
```

### Scenario 2: Existing OAuth User (Login)

```python
# User clicks "Sign in with Google"
# → Social account already linked
# → Log in existing user

@app.get("/auth/google/callback")
async def callback(code: str, state: str):
    # 1-4. Same as above

    social_account = await db.social_accounts.find_one({
        "provider": "google",
        "provider_user_id": google_user_id
    })

    if social_account:
        # 5. Get existing user
        user = await auth.user_service.get_user(social_account["user_id"])

        # 6. Update user info (optional)
        await auth.user_service.update_user(
            user.id,
            email=google_email,
            name=google_name
        )

    # 7. Generate JWT tokens
    # 8. Return tokens
```

### Scenario 3: Link OAuth to Existing Account

```python
# User already has email/password account
# → Wants to add Google login
# → Use associate router

app.include_router(
    get_oauth_associate_router(
        google,
        auth,
        state_secret="..."
    ),
    prefix="/auth/google/associate",
    tags=["auth"]
)

# User must be authenticated
@app.get("/auth/google/associate/authorize")
async def authorize(user = Depends(auth.deps.require_auth())):
    # State token includes user_id
    state = generate_state_token({"user_id": user.id}, state_secret)
    # ... generate authorization URL
```

**Security**: State token includes `user_id`, callback validates it matches authenticated user.

### Scenario 4: Email-Based Auto-Linking (⚠️ Risky)

```python
# If associate_by_email=True:
# → Check if user with same email exists
# → Automatically link OAuth account

router = get_oauth_router(
    google,
    auth,
    state_secret="...",
    associate_by_email=True  # ⚠️ Only for trusted providers!
)

# In callback:
if not social_account:
    # Check if user with this email exists
    existing_user = await auth.user_service.get_by_email(google_email)

    if existing_user:
        # Link to existing user
        await db.social_accounts.insert_one({
            "user_id": existing_user.id,
            "provider": "google",
            "provider_user_id": google_user_id
        })
```

**⚠️ Security Warning**: Only use `associate_by_email=True` for providers that verify emails (Google, Microsoft). Do NOT use for GitHub, Discord, or custom providers.

---

## Security Considerations

### 1. State Token CSRF Protection (DD-042)

**Attack**: OAuth state fixation attack

**Protection**: JWT-signed state tokens with:
- `aud` claim: `"outlabs-auth:oauth-state"`
- `exp` claim: 10-minute expiration
- Cryptographic signature

**Implementation**:
```python
# Generate (in /authorize)
state = generate_state_token({}, state_secret, lifetime_seconds=600)

# Validate (in /callback)
try:
    decoded = decode_state_token(state, state_secret)
    # Valid: aud matches, exp not exceeded, signature valid
except jwt.ExpiredSignatureError:
    raise HTTPException(400, "OAuth state expired")
except jwt.InvalidAudienceError:
    raise HTTPException(400, "Invalid OAuth state")
```

### 2. Account Hijacking Prevention (DD-046)

**Attack**: Email-based account takeover

**Protection**: `associate_by_email=False` by default

**Safe Alternatives**:
1. Use `get_oauth_associate_router()` for explicit linking
2. Require re-authentication before linking
3. Send confirmation email before linking

### 3. Verified Emails

**Trusted Providers** (email always verified):
- Google
- Microsoft
- Apple

**Untrusted Providers** (email might not be verified):
- GitHub (user can add unverified email)
- Discord (user can change email without verification)
- Facebook (depends on settings)

**Recommendation**:
```python
# Trusted provider
app.include_router(
    get_oauth_router(
        google,
        auth,
        state_secret="...",
        is_verified_by_default=True  # ✅ Trust Google
    ),
    prefix="/auth/google"
)

# Untrusted provider
app.include_router(
    get_oauth_router(
        github,
        auth,
        state_secret="...",
        is_verified_by_default=False  # ⚠️ Don't trust GitHub
    ),
    prefix="/auth/github"
)
```

### 4. Separate State Secret

**Always use different secret for OAuth state than JWT tokens**:

```python
# ❌ BAD: Same secret
JWT_SECRET = "my-secret"
OAUTH_STATE_SECRET = "my-secret"  # Same secret!

# ✅ GOOD: Different secrets
JWT_SECRET = "jwt-secret-abc123"
OAUTH_STATE_SECRET = "oauth-state-secret-xyz789"  # Different!
```

**Why**: If JWT secret is compromised, OAuth state tokens should remain secure.

---

## Common Patterns

### Pattern 1: Multiple Providers

```python
# Google
app.include_router(
    get_oauth_router(google, auth, state_secret="..."),
    prefix="/auth/google",
    tags=["auth"]
)

# GitHub
app.include_router(
    get_oauth_router(github, auth, state_secret="..."),
    prefix="/auth/github",
    tags=["auth"]
)

# Facebook
app.include_router(
    get_oauth_router(facebook, auth, state_secret="..."),
    prefix="/auth/facebook",
    tags=["auth"]
)
```

### Pattern 2: Default Role for OAuth Users

```python
from outlabs_auth.services import UserService

class MyUserService(UserService):
    async def on_after_oauth_register(self, user, provider, request=None):
        # Assign default role to OAuth users
        await self.role_service.assign_role_to_user(user.id, "oauth_user")

        # Track analytics
        await analytics.track("oauth_registration", {
            "user_id": user.id,
            "provider": provider
        })

auth = SimpleRBAC(
    database=db,
    user_service_class=MyUserService
)
```

### Pattern 3: Frontend Redirect After OAuth

```python
router = get_oauth_router(
    google,
    auth,
    state_secret="...",
    redirect_url="https://myapp.com/auth/callback"  # Frontend URL
)

# Backend callback redirects to frontend with tokens:
# https://myapp.com/auth/callback?access_token=...&refresh_token=...
```

### Pattern 4: Custom User Info Mapping

```python
from outlabs_auth.routers import get_oauth_router

router = get_oauth_router(
    google,
    auth,
    state_secret="...",
    user_fields_mapper=lambda google_user: {
        "email": google_user["email"],
        "name": google_user.get("name"),
        "avatar_url": google_user.get("picture"),
        "locale": google_user.get("locale"),
    }
)
```

---

## Testing OAuth Locally

### Local Development Setup

```python
# Use ngrok for HTTPS callback
# 1. Install ngrok: https://ngrok.com/
# 2. Start ngrok: ngrok http 8000
# 3. Use ngrok URL as callback:

google = get_google_client(
    client_id="...",
    client_secret="..."
)

app.include_router(
    get_oauth_router(google, auth, state_secret="..."),
    prefix="/auth/google"
)

# Register callback URL in Google Console:
# https://abc123.ngrok.io/auth/google/callback
```

### Testing Without Browser

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_oauth_authorize():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/auth/google/authorize")

    assert response.status_code == 200
    data = response.json()
    assert "authorization_url" in data
    assert "accounts.google.com" in data["authorization_url"]

@pytest.mark.asyncio
async def test_oauth_callback_invalid_state():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(
            "/auth/google/callback",
            params={"code": "fake", "state": "invalid"}
        )

    assert response.status_code == 400
    assert "Invalid state" in response.json()["detail"]
```

---

## Troubleshooting

### Error: "redirect_uri_mismatch"

**Problem**: Callback URL doesn't match registered URL in provider console.

**Solution**:
1. Check registered URL in provider console
2. Match exactly (including http/https, port, trailing slash)
3. For local dev, use ngrok or set up local HTTPS

### Error: "Invalid state token"

**Problem**: State token expired or tampered with.

**Solution**:
1. Check state secret matches between authorize and callback
2. Complete OAuth flow within 10 minutes
3. Don't modify state parameter in URL

### Error: "User email not verified"

**Problem**: Provider returned unverified email, but app requires verification.

**Solution**:
```python
router = get_oauth_router(
    github,
    auth,
    state_secret="...",
    is_verified_by_default=False,  # Don't trust unverified emails
    require_verified_email=False  # Allow unverified emails (send verification later)
)
```

### Error: "Account already exists"

**Problem**: User with same email already exists.

**Solution**:
```python
router = get_oauth_router(
    google,
    auth,
    state_secret="...",
    associate_by_email=True  # Auto-link to existing account
)
```

---

## API Reference

### Router Factories

**`get_oauth_router()`** - [[94-OAuth-Router|OAuth Router Reference]]

**`get_oauth_associate_router()`** - [[95-OAuth-Associate-Router|OAuth Associate Router Reference]]

### Provider Clients

**`get_google_client()`** - [[32-OAuth-Providers#Google|Google Client]]

**`get_facebook_client()`** - [[32-OAuth-Providers#Facebook|Facebook Client]]

**`get_github_client()`** - [[32-OAuth-Providers#GitHub|GitHub Client]]

### State Token Functions

**`generate_state_token()`** - [[104-JWT-State-Tokens#Generate|Generate State Token]]

**`decode_state_token()`** - [[104-JWT-State-Tokens#Decode|Decode State Token]]

---

## Next Steps

- **[[31-OAuth-Setup|OAuth Setup Guide]]** - Provider-specific setup instructions
- **[[33-OAuth-Account-Linking|Account Linking]]** - Safe account linking patterns
- **[[34-OAuth-Security|OAuth Security]]** - Security best practices
- **[[152-Tutorial-OAuth-Integration|Tutorial]]** - Complete OAuth integration guide

---

**Previous**: [[25-Multi-Source-Auth|← Multi-Source Auth]]
**Next**: [[31-OAuth-Setup|OAuth Setup Guide →]]
