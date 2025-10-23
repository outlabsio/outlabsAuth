# OAuth/Social Login Design Document (v1.2)

**Status**: Planning  
**Version**: 1.0  
**Date**: 2025-10-15  
**Goal**: Make OAuth integration dead-simple while handling all complexity internally

---

## Design Principles

### 1. **Minimal Configuration Required**
Users should only need to provide:
- Client ID
- Client Secret  
- Redirect URI (we provide sensible defaults)

Everything else (scopes, endpoints, token exchange, user info parsing) is handled internally.

### 2. **Pre-configured Providers**
We provide battle-tested configurations for popular providers:
- Google OAuth 2.0
- Facebook Login
- Apple Sign In
- GitHub OAuth
- Microsoft/Azure AD
- Twitter OAuth 2.0

### 3. **Automatic Account Linking**
Intelligent account linking by verified email:
- Auto-link if email verified by provider
- Create new account if email not verified
- Prevent account takeover attacks

### 4. **Security by Default**
- PKCE (Proof Key for Code Exchange) for all providers
- State parameter validation (CSRF protection)
- Nonce validation for OpenID Connect
- Token validation and signature verification
- Automatic token refresh

### 5. **Extensible Architecture**
Easy to add custom providers:
```python
class CustomOAuthProvider(OAuthProvider):
    # Implement 3 methods, done!
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      User Application                        │
├─────────────────────────────────────────────────────────────┤
│  auth = SimpleRBAC(                                          │
│      ...,                                                    │
│      oauth_providers={                                       │
│          "google": GoogleProvider(                           │
│              client_id="...",                                │
│              client_secret="..."                             │
│          )                                                   │
│      }                                                       │
│  )                                                           │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                      OAuthService                            │
├─────────────────────────────────────────────────────────────┤
│  • get_authorization_url()                                   │
│  • handle_callback()                                         │
│  • link_provider()                                           │
│  • unlink_provider()                                         │
│  • Security validation (state, PKCE, nonce)                  │
└─────────────────────────────────────────────────────────────┘
                           │
            ┌──────────────┼──────────────┐
            ▼              ▼              ▼
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
    │   Google     │ │   Facebook   │ │    Apple     │
    │   Provider   │ │   Provider   │ │   Provider   │
    ├──────────────┤ ├──────────────┤ ├──────────────┤
    │ Pre-config'd │ │ Pre-config'd │ │ Pre-config'd │
    │ • Scopes     │ │ • Scopes     │ │ • Scopes     │
    │ • Endpoints  │ │ • Endpoints  │ │ • Endpoints  │
    │ • Parsing    │ │ • Parsing    │ │ • Parsing    │
    └──────────────┘ └──────────────┘ └──────────────┘
```

---

## Core Components

### 1. OAuthProvider (Abstract Base Class)

Every provider implements this simple interface:

```python
class OAuthProvider(ABC):
    """Abstract OAuth provider - users rarely interact with this."""
    
    # Provider metadata (pre-configured)
    name: str  # "google", "facebook", etc.
    display_name: str  # "Google", "Facebook", etc.
    
    @abstractmethod
    def get_authorization_url(
        self,
        state: str,
        redirect_uri: str,
        code_challenge: Optional[str] = None,  # PKCE
        nonce: Optional[str] = None  # OIDC
    ) -> str:
        """Generate OAuth authorization URL with all parameters."""
        pass
    
    @abstractmethod
    async def exchange_code(
        self,
        code: str,
        redirect_uri: str,
        code_verifier: Optional[str] = None  # PKCE
    ) -> OAuthTokenResponse:
        """Exchange authorization code for access token."""
        pass
    
    @abstractmethod
    async def get_user_info(
        self,
        access_token: str
    ) -> OAuthUserInfo:
        """Fetch user info from provider using access token."""
        pass
    
    # Optional methods with sensible defaults
    async def refresh_token(self, refresh_token: str) -> OAuthTokenResponse:
        """Refresh access token (default implementation provided)."""
        pass
    
    async def revoke_token(self, token: str) -> bool:
        """Revoke token (optional, not all providers support)."""
        pass
```

### 2. Pre-configured Providers

Users instantiate with minimal config:

```python
# Google - just credentials, everything else pre-configured
google = GoogleProvider(
    client_id="YOUR_GOOGLE_CLIENT_ID",
    client_secret="YOUR_GOOGLE_CLIENT_SECRET"
    # That's it! Scopes, endpoints, parsing all pre-configured
)

# Facebook - same pattern
facebook = FacebookProvider(
    client_id="YOUR_FB_APP_ID",
    client_secret="YOUR_FB_APP_SECRET"
)

# Apple - slightly more config (team ID, key ID, private key)
apple = AppleProvider(
    client_id="YOUR_SERVICE_ID",
    team_id="YOUR_TEAM_ID",
    key_id="YOUR_KEY_ID",
    private_key_path="/path/to/AuthKey_XXXXX.p8"
)
```

### 3. OAuthService (High-level API)

Users interact with this simple API:

```python
# 1. Generate login URL
url = await auth.oauth.get_authorization_url(
    provider="google",
    redirect_uri="https://myapp.com/auth/callback"
)
# Returns: https://accounts.google.com/o/oauth2/v2/auth?client_id=...&state=...

# 2. Handle callback (does everything automatically)
result = await auth.oauth.handle_callback(
    provider="google",
    code="authorization_code",
    state="state_from_url",
    redirect_uri="https://myapp.com/auth/callback"
)
# Returns: {
#     "user": UserModel,
#     "is_new_user": True/False,
#     "access_token": "jwt_token",
#     "refresh_token": "refresh_token",
#     "linked_account": True/False
# }

# 3. Link to existing user (optional)
await auth.oauth.link_provider(
    user_id="user_id",
    provider="facebook",
    code="authorization_code",
    state="state",
    redirect_uri="https://myapp.com/auth/callback"
)

# 4. Unlink provider
await auth.oauth.unlink_provider(
    user_id="user_id",
    provider="google"
)
```

---

## Data Models

### SocialAccount Model

```python
class SocialAccount(BaseDocument):
    """Links user to OAuth provider account."""
    
    # Relationships
    user_id: ObjectId  # Reference to UserModel
    
    # Provider info
    provider: str  # "google", "facebook", "apple", etc.
    provider_user_id: str  # User ID from provider
    
    # User data from provider (cached)
    email: str
    email_verified: bool
    display_name: Optional[str]
    avatar_url: Optional[str]
    
    # OAuth tokens (encrypted)
    access_token: Optional[str]  # Encrypted
    refresh_token: Optional[str]  # Encrypted
    token_expires_at: Optional[datetime]
    
    # Provider-specific data
    provider_data: Dict[str, Any]  # Full profile from provider
    
    # Metadata
    linked_at: datetime
    last_used_at: Optional[datetime]
    
    # Indexes
    class Settings:
        indexes = [
            [("user_id", ASCENDING)],
            [("provider", ASCENDING), ("provider_user_id", ASCENDING)],  # Unique
            [("provider", ASCENDING), ("email", ASCENDING)]
        ]
```

### OAuthState Model (Security)

```python
class OAuthState(BaseDocument):
    """Temporary state for OAuth flow validation."""
    
    state: str  # Random state parameter (CSRF protection)
    provider: str
    
    # PKCE
    code_verifier: Optional[str]  # For PKCE flow
    code_challenge: Optional[str]
    
    # OIDC
    nonce: Optional[str]  # For OpenID Connect
    
    # Context
    redirect_uri: str
    original_url: Optional[str]  # Where to redirect after login
    user_id: Optional[ObjectId]  # If linking to existing user
    
    # Expiration
    expires_at: datetime  # 10 minutes
    
    # Metadata
    created_at: datetime
    ip_address: Optional[str]
    user_agent: Optional[str]
```

### UserModel Updates

```python
class UserModel(BaseDocument):
    # Existing fields...
    
    # NEW: Auth methods
    auth_methods: List[str] = []  # ["PASSWORD", "GOOGLE", "FACEBOOK"]
    
    # Password now optional (can login with OAuth only)
    hashed_password: Optional[str] = None
    
    # Social accounts (virtual relationship)
    # social_accounts: List[SocialAccount]  # Accessed via query
```

---

## Provider Configurations

### Google OAuth 2.0

**Pre-configured:**
- Authorization URL: `https://accounts.google.com/o/oauth2/v2/auth`
- Token URL: `https://oauth2.googleapis.com/token`
- User Info URL: `https://www.googleapis.com/oauth2/v2/userinfo`
- Scopes: `["openid", "email", "profile"]`
- Supports: PKCE, token refresh

**User provides:**
- `client_id`
- `client_secret`

### Facebook Login

**Pre-configured:**
- Authorization URL: `https://www.facebook.com/v18.0/dialog/oauth`
- Token URL: `https://graph.facebook.com/v18.0/oauth/access_token`
- User Info URL: `https://graph.facebook.com/me?fields=id,name,email,picture`
- Scopes: `["email", "public_profile"]`
- Supports: Token refresh, long-lived tokens

**User provides:**
- `client_id` (App ID)
- `client_secret` (App Secret)

### Apple Sign In

**Pre-configured:**
- Authorization URL: `https://appleid.apple.com/auth/authorize`
- Token URL: `https://appleid.apple.com/auth/token`
- Scopes: `["email", "name"]`
- Supports: OpenID Connect, JWT validation

**User provides:**
- `client_id` (Service ID)
- `team_id`
- `key_id`
- `private_key` (P8 file content or path)

**Special handling:**
- Apple uses JWT for client authentication
- We handle JWT generation internally
- Email relay (@privaterelay.appleid.com) supported

### GitHub OAuth

**Pre-configured:**
- Authorization URL: `https://github.com/login/oauth/authorize`
- Token URL: `https://github.com/login/oauth/access_token`
- User Info URL: `https://api.github.com/user`
- Scopes: `["user:email"]`
- Supports: Token revocation

**User provides:**
- `client_id`
- `client_secret`

### Microsoft/Azure AD

**Pre-configured:**
- Authorization URL: `https://login.microsoftonline.com/common/oauth2/v2.0/authorize`
- Token URL: `https://login.microsoftonline.com/common/oauth2/v2.0/token`
- User Info URL: `https://graph.microsoft.com/v1.0/me`
- Scopes: `["openid", "email", "profile"]`
- Supports: OpenID Connect, PKCE

**User provides:**
- `client_id`
- `client_secret`
- `tenant` (optional, defaults to "common")

---

## Account Linking Strategy

### Automatic Linking Rules

1. **Email Verified by Provider + Email Exists**
   - ✅ Auto-link to existing user
   - ✅ Add provider to `auth_methods`
   - ✅ Create `SocialAccount` record
   - ✅ User can now login with OAuth or password

2. **Email Not Verified by Provider**
   - ❌ Do NOT auto-link (security risk)
   - ✅ Create new user account
   - ⚠️ Email will be unverified in our system

3. **Email Doesn't Exist**
   - ✅ Create new user
   - ✅ Mark email as verified (if verified by provider)
   - ✅ Add provider to `auth_methods`
   - ✅ Send welcome notification

4. **Manual Linking (User Settings)**
   - ✅ User must be authenticated
   - ✅ Complete OAuth flow
   - ✅ Link to authenticated user's account
   - ✅ Verify email matches (optional but recommended)

### Security Validations

**Before Auto-linking:**
- ✅ Email must be verified by provider
- ✅ Provider must be trusted (our pre-configured ones)
- ✅ Email domain not in blocklist
- ✅ User account not suspended/banned

**Prevent Account Takeover:**
- ❌ Cannot link if provider email differs from user email
- ❌ Cannot link if user already has this provider linked
- ❌ Cannot link multiple users to same provider account

---

## Security Implementation

### 1. PKCE (Proof Key for Code Exchange)

**Why:** Protects against authorization code interception

**Implementation:**
```python
# Generate code verifier and challenge
code_verifier = secrets.token_urlsafe(32)  # Random 32-byte string
code_challenge = base64.urlsafe_b64encode(
    hashlib.sha256(code_verifier.encode()).digest()
).decode().rstrip('=')

# Store verifier in OAuthState
await OAuthState.create(
    state=state,
    code_verifier=code_verifier,
    code_challenge=code_challenge,
    ...
)

# Send challenge in auth URL
url = f"{auth_url}?...&code_challenge={code_challenge}&code_challenge_method=S256"

# On callback, verify with stored verifier
token_response = await provider.exchange_code(
    code=code,
    code_verifier=stored_state.code_verifier
)
```

### 2. State Parameter (CSRF Protection)

**Why:** Prevents cross-site request forgery

**Implementation:**
```python
# Generate random state
state = secrets.token_urlsafe(32)

# Store in database with expiration (10 minutes)
await OAuthState.create(
    state=state,
    provider="google",
    expires_at=datetime.utcnow() + timedelta(minutes=10),
    ...
)

# On callback, validate state matches
stored_state = await OAuthState.find_one(
    OAuthState.state == state,
    OAuthState.expires_at > datetime.utcnow()
)
if not stored_state:
    raise InvalidStateError()

# Delete after use (one-time use)
await stored_state.delete()
```

### 3. Nonce (OpenID Connect)

**Why:** Prevents replay attacks in ID tokens

**Implementation:**
```python
# Generate nonce for OIDC providers (Google, Apple, Microsoft)
nonce = secrets.token_urlsafe(32)

# Store in OAuthState
await OAuthState.create(..., nonce=nonce)

# Validate nonce in ID token
id_token_payload = jwt.decode(id_token, ...)
if id_token_payload.get("nonce") != stored_state.nonce:
    raise InvalidNonceError()
```

### 4. Token Storage

**Tokens are encrypted at rest:**
```python
from cryptography.fernet import Fernet

# Encrypt tokens before storage
encrypted_token = fernet.encrypt(access_token.encode())

# Decrypt when needed
decrypted_token = fernet.decrypt(encrypted_token).decode()
```

---

## FastAPI Integration

### Endpoints

We provide convenient FastAPI routes:

```python
# 1. Initiate OAuth flow
@app.get("/auth/oauth/{provider}")
async def oauth_login(
    provider: str,
    redirect_uri: Optional[str] = None,
    auth: SimpleRBAC = Depends(get_auth)
):
    """Redirect to provider's OAuth page."""
    url = await auth.oauth.get_authorization_url(
        provider=provider,
        redirect_uri=redirect_uri or f"{BASE_URL}/auth/oauth/{provider}/callback"
    )
    return RedirectResponse(url)

# 2. Handle callback
@app.get("/auth/oauth/{provider}/callback")
async def oauth_callback(
    provider: str,
    code: str,
    state: str,
    auth: SimpleRBAC = Depends(get_auth)
):
    """Handle OAuth callback from provider."""
    result = await auth.oauth.handle_callback(
        provider=provider,
        code=code,
        state=state,
        redirect_uri=f"{BASE_URL}/auth/oauth/{provider}/callback"
    )
    
    # Set JWT tokens in cookies or return JSON
    response = RedirectResponse("/dashboard")
    response.set_cookie("access_token", result["access_token"])
    return response

# 3. Link provider to authenticated user
@app.post("/auth/oauth/{provider}/link")
async def link_provider(
    provider: str,
    code: str,
    state: str,
    user: UserModel = Depends(deps.authenticated()),
    auth: SimpleRBAC = Depends(get_auth)
):
    """Link OAuth provider to current user."""
    await auth.oauth.link_provider(
        user_id=str(user.id),
        provider=provider,
        code=code,
        state=state,
        redirect_uri=f"{BASE_URL}/auth/oauth/{provider}/link-callback"
    )
    return {"success": True}

# 4. Unlink provider
@app.delete("/auth/oauth/{provider}")
async def unlink_provider(
    provider: str,
    user: UserModel = Depends(deps.authenticated()),
    auth: SimpleRBAC = Depends(get_auth)
):
    """Unlink OAuth provider from current user."""
    await auth.oauth.unlink_provider(
        user_id=str(user.id),
        provider=provider
    )
    return {"success": True}

# 5. List linked providers
@app.get("/auth/oauth")
async def list_providers(
    user: UserModel = Depends(deps.authenticated()),
    auth: SimpleRBAC = Depends(get_auth)
):
    """List user's linked OAuth providers."""
    accounts = await auth.oauth.list_linked_providers(str(user.id))
    return {
        "providers": [
            {
                "provider": account.provider,
                "email": account.email,
                "display_name": account.display_name,
                "avatar_url": account.avatar_url,
                "linked_at": account.linked_at
            }
            for account in accounts
        ]
    }
```

---

## Usage Examples

### Example 1: Simple Setup (Google Only)

```python
from outlabs_auth import SimpleRBAC
from outlabs_auth.oauth import GoogleProvider

# Initialize with Google OAuth
auth = SimpleRBAC(
    database=mongo_client,
    secret_key="your-secret",
    oauth_providers={
        "google": GoogleProvider(
            client_id=os.getenv("GOOGLE_CLIENT_ID"),
            client_secret=os.getenv("GOOGLE_CLIENT_SECRET")
        )
    }
)

await auth.initialize()

# That's it! OAuth endpoints ready to use
```

### Example 2: Multiple Providers

```python
from outlabs_auth.oauth import (
    GoogleProvider,
    FacebookProvider,
    AppleProvider,
    GitHubProvider
)

auth = SimpleRBAC(
    database=mongo_client,
    secret_key="your-secret",
    oauth_providers={
        "google": GoogleProvider(
            client_id=os.getenv("GOOGLE_CLIENT_ID"),
            client_secret=os.getenv("GOOGLE_CLIENT_SECRET")
        ),
        "facebook": FacebookProvider(
            client_id=os.getenv("FACEBOOK_APP_ID"),
            client_secret=os.getenv("FACEBOOK_APP_SECRET")
        ),
        "apple": AppleProvider(
            client_id=os.getenv("APPLE_SERVICE_ID"),
            team_id=os.getenv("APPLE_TEAM_ID"),
            key_id=os.getenv("APPLE_KEY_ID"),
            private_key_path="/path/to/AuthKey.p8"
        ),
        "github": GitHubProvider(
            client_id=os.getenv("GITHUB_CLIENT_ID"),
            client_secret=os.getenv("GITHUB_CLIENT_SECRET")
        )
    }
)
```

### Example 3: Custom Provider

```python
from outlabs_auth.oauth import OAuthProvider

class LinkedInProvider(OAuthProvider):
    name = "linkedin"
    display_name = "LinkedIn"
    
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.auth_url = "https://www.linkedin.com/oauth/v2/authorization"
        self.token_url = "https://www.linkedin.com/oauth/v2/accessToken"
        self.user_info_url = "https://api.linkedin.com/v2/me"
        self.scopes = ["r_liteprofile", "r_emailaddress"]
    
    def get_authorization_url(self, state, redirect_uri, **kwargs):
        # Implementation...
        pass
    
    async def exchange_code(self, code, redirect_uri, **kwargs):
        # Implementation...
        pass
    
    async def get_user_info(self, access_token):
        # Implementation...
        pass

# Use custom provider
auth = SimpleRBAC(
    ...,
    oauth_providers={
        "linkedin": LinkedInProvider(
            client_id=os.getenv("LINKEDIN_CLIENT_ID"),
            client_secret=os.getenv("LINKEDIN_CLIENT_SECRET")
        )
    }
)
```

---

## Testing Strategy

### Unit Tests

1. **Provider Tests** (per provider)
   - Authorization URL generation
   - Token exchange
   - User info parsing
   - Token refresh
   - Error handling

2. **OAuthService Tests**
   - State generation and validation
   - PKCE flow
   - Account linking logic
   - Security validations

3. **Model Tests**
   - SocialAccount CRUD
   - OAuthState expiration
   - Encryption/decryption

### Integration Tests

1. **Complete OAuth Flows**
   - New user registration via OAuth
   - Existing user login via OAuth
   - Account linking
   - Account unlinking

2. **Security Tests**
   - CSRF prevention (invalid state)
   - Code interception (PKCE validation)
   - Replay attacks (nonce validation)
   - Account takeover prevention

3. **Multi-provider Tests**
   - User with multiple providers
   - Switching between providers
   - Un linking last provider (should fail if no password)

### Mock Testing

Since we can't hit real OAuth endpoints in tests:

```python
class MockGoogleProvider(GoogleProvider):
    """Mock Google provider for testing."""
    
    async def exchange_code(self, code, redirect_uri, **kwargs):
        # Return fake token response
        return OAuthTokenResponse(
            access_token="fake_access_token",
            token_type="Bearer",
            expires_in=3600
        )
    
    async def get_user_info(self, access_token):
        # Return fake user info
        return OAuthUserInfo(
            provider_user_id="123456789",
            email="test@gmail.com",
            email_verified=True,
            name="Test User"
        )
```

---

## Error Handling

### OAuth-specific Exceptions

```python
class OAuthError(Exception):
    """Base OAuth error."""
    pass

class InvalidStateError(OAuthError):
    """State parameter invalid or expired."""
    pass

class InvalidCodeError(OAuthError):
    """Authorization code invalid or expired."""
    pass

class ProviderError(OAuthError):
    """Error from OAuth provider."""
    def __init__(self, provider: str, error: str, description: str):
        self.provider = provider
        self.error = error
        self.description = description

class AccountLinkError(OAuthError):
    """Cannot link account."""
    pass

class ProviderNotConfiguredError(OAuthError):
    """Provider not configured."""
    pass
```

### User-friendly Error Messages

```python
# Invalid/expired state
"OAuth session expired. Please try logging in again."

# Provider error
"Unable to authenticate with Google. Please try again later."

# Account linking failed
"This Google account is already linked to another user."

# Email mismatch
"The email from Facebook doesn't match your account email."

# Cannot unlink last provider
"You must have at least one login method. Add a password before unlinking Google."
```

---

## Dependencies

### Required
- `httpx` - Async HTTP client for OAuth requests
- `pyjwt[crypto]` - JWT validation (Apple, Microsoft)
- `cryptography` - Token encryption at rest

### Optional (per provider)
- None! All providers use standard OAuth 2.0/OIDC

---

## Migration Path

### From v1.0 to v1.2

Existing users are not affected:
- Password authentication still works
- No breaking changes to existing APIs
- OAuth is purely additive

### Enabling OAuth

```python
# Before (v1.0)
auth = SimpleRBAC(database=db, secret_key="secret")

# After (v1.2) - just add oauth_providers
auth = SimpleRBAC(
    database=db,
    secret_key="secret",
    oauth_providers={  # NEW - optional
        "google": GoogleProvider(...)
    }
)
```

---

## Next Steps

1. ✅ Design document complete
2. ⏳ Implement base `OAuthProvider` class
3. ⏳ Implement `GoogleProvider` (first provider)
4. ⏳ Implement `OAuthService` (high-level API)
5. ⏳ Add models (`SocialAccount`, `OAuthState`)
6. ⏳ Implement security (PKCE, state, nonce)
7. ⏳ Add FastAPI integration
8. ⏳ Implement remaining providers
9. ⏳ Write comprehensive tests
10. ⏳ Create example application
11. ⏳ Documentation and guides

---

## Open Questions

1. **Token Refresh Strategy**
   - Should we automatically refresh expired tokens?
   - Store refresh tokens indefinitely or with expiration?
   - **Decision**: Auto-refresh on use, store indefinitely until unlinked

2. **Email Conflict Resolution**
   - What if OAuth email exists but isn't verified in our system?
   - **Decision**: Allow login if provider verified, prompt re-verification

3. **Profile Sync**
   - Should we update user profile (name, avatar) from OAuth provider?
   - **Decision**: Yes, on first link only. User can update manually after.

4. **Multi-tenant Support**
   - How does OAuth work in multi-tenant scenarios?
   - **Decision**: Provider config per tenant, or shared across tenants (tenant_id in state)

---

**Status**: Ready for implementation  
**Estimated Effort**: 2-3 weeks  
**Next**: Begin with `OAuthProvider` base class and `GoogleProvider`
