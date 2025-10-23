# 34. OAuth Security Best Practices

> **Quick Reference**: Comprehensive guide to securing OAuth flows, preventing attacks, and implementing best practices for social login.

## Overview

OAuth 2.0 is powerful but complex. Without proper security measures, OAuth can be vulnerable to:
- **CSRF attacks** (Cross-Site Request Forgery)
- **Authorization code interception**
- **Token replay attacks**
- **Account takeover via email conflicts**
- **Phishing and social engineering**

OutlabsAuth implements OAuth security best practices by default, but understanding these protections helps you use OAuth safely.

---

## Security Layers

OutlabsAuth OAuth security has 5 layers:

| Layer | Protection Against | Implementation |
|-------|-------------------|----------------|
| **1. State Parameter** | CSRF attacks | JWT-based state tokens (DD-042) |
| **2. PKCE** | Authorization code interception | S256 code challenge/verifier |
| **3. Nonce** | ID token replay (OIDC) | Random nonce validation |
| **4. Email Verification** | Account takeover | Only auto-link verified emails |
| **5. Token Storage** | Token theft | Secure storage recommendations |

---

## 1. State Parameter (CSRF Protection)

### What is CSRF in OAuth?

**Attack Scenario**:
```
1. Attacker initiates OAuth flow, gets authorization URL:
   https://provider.com/auth?state=ATTACKER_STATE&client_id=...

2. Attacker tricks victim into clicking this link

3. Victim approves OAuth (thinking it's legitimate)

4. Provider redirects to: yourapp.com/callback?code=ABC&state=ATTACKER_STATE

5. Without state validation, attacker's account gets linked to victim's provider account!
```

### How State Parameter Prevents CSRF

```
1. User clicks "Login with Google" on your app
   ↓
2. Your app generates random state token (JWT)
   state = jwt.encode({"iat": now, "exp": now+10min}, SECRET_KEY)
   ↓
3. Store state association (who initiated this?)
   ↓
4. Redirect to Google with state parameter
   https://google.com/auth?state=eyJ0eXAi...&client_id=...
   ↓
5. User approves on Google
   ↓
6. Google redirects back: /callback?code=ABC&state=eyJ0eXAi...
   ↓
7. Validate state token:
   - Decode JWT (verify signature)
   - Check expiration (max 10 minutes)
   - Check audience (prevent token reuse)
   ↓
8. State valid ✅ → Process authorization code
   State invalid ❌ → Reject (possible attack!)
```

### Implementation in OutlabsAuth

OutlabsAuth uses **JWT-based state tokens** (DD-042) instead of database storage:

```python
from outlabs_auth.oauth.state import generate_state_token, decode_state_token

# Generate state token
state = generate_state_token(
    data={"user_id": user_id} if linking else {},  # Optional user context
    secret=SECRET_KEY,
    lifetime_seconds=600  # 10 minutes
)

# State token payload:
{
    "aud": "outlabs-auth:oauth-state",  # Audience (prevents reuse)
    "iat": 1234567890,                   # Issued at
    "exp": 1234568490,                   # Expires in 10 minutes
    "user_id": "507f..."                 # Optional: for account linking
}

# Validate state token in callback
try:
    state_data = decode_state_token(state, secret=SECRET_KEY)
    user_id = state_data.get("user_id")  # For manual linking
except jwt.ExpiredSignatureError:
    raise HTTPException(400, "OAuth session expired")
except jwt.InvalidTokenError:
    raise HTTPException(400, "Invalid OAuth state")
```

**Why JWT State Tokens?**
- ✅ **Stateless**: No database writes
- ✅ **Self-expiring**: JWT exp claim handles cleanup
- ✅ **Tamper-proof**: JWT signature prevents modification
- ✅ **Scalable**: Works across load balancers without sticky sessions
- ✅ **Simple**: No cleanup jobs needed

### Best Practices

```python
# ✅ Good - generate fresh state for each OAuth flow
state = generate_state_token({}, secret=SECRET_KEY)

# ❌ Bad - reusing state tokens
cached_state = cache.get("oauth_state")  # DON'T DO THIS

# ✅ Good - short expiration (10 minutes)
lifetime_seconds=600

# ❌ Bad - long expiration
lifetime_seconds=3600  # 1 hour is too long

# ✅ Good - validate state in callback
state_data = decode_state_token(state, secret=SECRET_KEY)

# ❌ Bad - skip state validation
# if True:  # Always process callback - INSECURE!
```

---

## 2. PKCE (Proof Key for Code Exchange)

### What is Authorization Code Interception?

**Attack Scenario (Without PKCE)**:
```
1. User initiates OAuth on mobile app
2. App redirects to provider
3. User approves
4. Provider redirects: myapp://callback?code=ABC
5. Malicious app intercepts redirect (Android/iOS)
6. Attacker exchanges code for tokens
7. Attacker gains access to user's account
```

### How PKCE Prevents Interception

```
1. App generates random code_verifier
   code_verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"

2. App computes code_challenge (SHA256 hash)
   code_challenge = BASE64URL(SHA256(code_verifier))
                  = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"

3. App sends code_challenge to provider
   https://provider.com/auth?code_challenge=E9Melh...&code_challenge_method=S256

4. Provider stores code_challenge

5. User approves

6. Provider redirects with authorization code
   myapp://callback?code=ABC

7. App exchanges code + code_verifier for tokens
   POST /token
   {
     "code": "ABC",
     "code_verifier": "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
   }

8. Provider validates: SHA256(code_verifier) == stored code_challenge
   ✅ Match → Issue tokens
   ❌ Mismatch → Reject

If attacker intercepts code, they don't have code_verifier → REJECTED!
```

### Implementation in OutlabsAuth

```python
from outlabs_auth.oauth.security import generate_pkce_pair, verify_pkce

# Generate PKCE pair (S256 method)
code_verifier, code_challenge = generate_pkce_pair(method="S256")

# code_verifier: "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
# code_challenge: "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"

# Include code_challenge in authorization URL
auth_url = provider.get_authorization_url(
    redirect_uri=redirect_uri,
    use_pkce=True  # Automatically includes code_challenge
)

# Authorization URL includes:
# ?code_challenge=E9Melh...&code_challenge_method=S256

# Exchange code with code_verifier
tokens = await provider.exchange_code(
    code=code,
    redirect_uri=redirect_uri,
    code_verifier=code_verifier  # Provider validates this
)
```

**PKCE Methods**:

| Method | Security | Provider Support |
|--------|----------|------------------|
| **S256** (SHA256) | ✅ Strong | Google, GitHub, Apple |
| **plain** | ⚠️ Weak (challenge = verifier) | Facebook (no PKCE) |

**Provider Support**:
- ✅ **Google**: S256
- ✅ **GitHub**: S256
- ❌ **Facebook**: No PKCE support
- ✅ **Apple**: S256

### Best Practices

```python
# ✅ Good - always use PKCE with S256
code_verifier, code_challenge = generate_pkce_pair(method="S256")

# ❌ Bad - plain method (only if provider requires it)
code_verifier, code_challenge = generate_pkce_pair(method="plain")

# ✅ Good - store code_verifier securely (in state token)
state_data = {
    "code_verifier": code_verifier,
    "redirect_uri": redirect_uri
}
state = generate_state_token(state_data, secret=SECRET_KEY)

# ❌ Bad - store code_verifier in client-side cookie
response.set_cookie("code_verifier", code_verifier)  # INSECURE!
```

---

## 3. Nonce (OpenID Connect)

### What is ID Token Replay?

**Attack Scenario (Without Nonce)**:
```
1. Attacker intercepts ID token from legitimate OAuth flow
2. Attacker replays ID token to your application
3. Without nonce validation, app accepts replayed token
4. Attacker gains access
```

### How Nonce Prevents Replay

```
1. App generates random nonce
   nonce = "n-0S6_WzA2Mj"

2. App includes nonce in authorization request
   https://provider.com/auth?nonce=n-0S6_WzA2Mj

3. Provider includes nonce in ID token
   {
     "sub": "user123",
     "nonce": "n-0S6_WzA2Mj",  # Same nonce
     "iat": 1234567890
   }

4. App validates nonce in ID token matches expected nonce
   ✅ Match → Accept token
   ❌ Mismatch → Reject (replayed token!)
```

### Implementation in OutlabsAuth

```python
from outlabs_auth.oauth.security import generate_nonce

# Generate nonce for OpenID Connect providers
nonce = generate_nonce()  # Random URL-safe string

# Include nonce in authorization URL
auth_url = provider.get_authorization_url(
    redirect_uri=redirect_uri,
    use_nonce=True  # Auto-generated for OIDC providers
)

# Validate nonce in ID token (Apple, Google)
id_token_payload = jwt.decode(id_token, verify=False)
if id_token_payload.get("nonce") != expected_nonce:
    raise InvalidNonceError("ID token nonce mismatch - possible replay attack")
```

**Which Providers Use Nonce**:
- ✅ **Google** (OpenID Connect)
- ❌ **GitHub** (Not OIDC)
- ❌ **Facebook** (Not OIDC)
- ✅ **Apple** (OpenID Connect)

### Best Practices

```python
# ✅ Good - generate nonce for OIDC providers
if provider.is_oidc:
    nonce = generate_nonce()

# ❌ Bad - reusing nonce
nonce = "static_nonce"  # Don't reuse!

# ✅ Good - validate nonce in ID token
if id_token_payload.get("nonce") != stored_nonce:
    raise InvalidNonceError()

# ❌ Bad - skip nonce validation
# nonce = id_token_payload.get("nonce")  # Just extract, don't validate
```

---

## 4. Email Verification (Account Linking Security)

### The Email Conflict Attack

**Attack Scenario (Without Email Verification Check)**:
```
1. Attacker knows victim uses victim@example.com
2. Attacker creates fake Google account with victim@example.com
   (Google doesn't verify this email yet)
3. Attacker logs into your app with this Google account
4. Your app auto-links by email: victim@example.com already exists!
5. Attacker gains access to victim's account!
```

### How Email Verification Prevents Takeover

```
User Info from Provider:
{
  "email": "victim@example.com",
  "email_verified": false  // ⚠️ NOT VERIFIED!
}

OutlabsAuth Security Check:
if user_info.email_verified:
    # ✅ Safe to auto-link by email
    existing_user = await find_user_by_email(user_info.email)
    if existing_user:
        await link_provider_to_user(existing_user.id, provider, user_info)
else:
    # ❌ NOT safe to auto-link
    # Create separate account instead
    new_user = await create_user(user_info.email)
```

### Implementation in OutlabsAuth

```python
# In OAuthService._create_or_link_user()

# Only auto-link if email is verified by provider
if user_info.email_verified:
    # Safe to search for existing user by email
    user = await UserModel.find_one(UserModel.email == user_info.email)

    if user:
        # Auto-link to existing user (verified email!)
        social_account = await self._create_social_account(...)
        return user, social_account, False  # Linked, not new

# Email NOT verified → create separate account
user = await self.user_service.create_user(
    email=user_info.email,
    password=None,  # Passwordless OAuth user
    email_verified=user_info.email_verified
)
```

**Provider Email Verification**:

| Provider | Always Verified? | Notes |
|----------|------------------|-------|
| **Google** | ✅ Yes | `verified_email: true` |
| **GitHub** | ✅ Yes (primary) | Fetches verified primary email |
| **Facebook** | ⚠️ Sometimes | `verified` flag varies |
| **Apple** | ✅ Yes | All emails verified |

### Best Practices

```python
# ✅ Good - check email_verified before auto-linking
if user_info.email_verified:
    existing_user = await find_user_by_email(user_info.email)

# ❌ Bad - auto-link without verification
existing_user = await find_user_by_email(user_info.email)  # INSECURE!

# ✅ Good - show helpful message for unverified emails
if not user_info.email_verified:
    flash("Email not verified by provider. Created separate account. "
          "Please link manually in settings if this is your email.")

# ❌ Bad - silently create duplicate accounts
# No message to user
```

---

## 5. Token Storage

### Access Token Security

**Where to Store OAuth Tokens**:

| Location | Security | Use Case |
|----------|----------|----------|
| **Database (encrypted)** | ✅ Best | Server-side apps |
| **HTTP-only cookies** | ✅ Good | Web apps |
| **LocalStorage** | ⚠️ Risky | Only if necessary (XSS risk) |
| **SessionStorage** | ⚠️ Risky | Single-tab apps |
| **In-memory only** | ✅ Best (if viable) | Don't persist |

### Implementation in OutlabsAuth

```python
# Store OAuth tokens encrypted in database
from outlabs_auth.models.social_account import SocialAccount

social_account = SocialAccount(
    user_id=user.id,
    provider="google",
    provider_user_id=user_info.provider_user_id,
    access_token=token_response.access_token,  # TODO: Encrypt at rest
    refresh_token=token_response.refresh_token,  # TODO: Encrypt at rest
    token_expires_at=datetime.utcnow() + timedelta(seconds=expires_in)
)
await social_account.insert()
```

**TODO: Encryption at Rest**:
```python
# Future implementation
from outlabs_auth.utils.encryption import encrypt, decrypt

social_account = SocialAccount(
    access_token=encrypt(token_response.access_token, encryption_key),
    refresh_token=encrypt(token_response.refresh_token, encryption_key)
)

# When using:
decrypted_token = decrypt(social_account.access_token, encryption_key)
```

### Best Practices

```python
# ✅ Good - encrypt OAuth tokens at rest
access_token = encrypt(token_response.access_token, ENCRYPTION_KEY)

# ❌ Bad - store tokens in plain text
access_token = token_response.access_token  # In database - INSECURE!

# ✅ Good - short-lived tokens
if expires_in < 3600:  # Less than 1 hour
    # Acceptable

# ⚠️ Acceptable - long-lived with refresh
if expires_in > 3600 and has_refresh_token:
    # Refresh when expired

# ❌ Bad - long-lived without refresh
if expires_in > 86400 and not has_refresh_token:
    # 24+ hours without refresh - risky!
```

---

## Additional Security Measures

### 1. Redirect URI Validation

**Attack**: Attacker modifies redirect_uri to steal authorization code.

**Protection**:
```python
# Whitelist allowed redirect URIs
ALLOWED_REDIRECT_URIS = [
    "http://localhost:3000/auth/callback",  # Development
    "https://yourapp.com/auth/callback",    # Production
]

def validate_redirect_uri(uri: str) -> bool:
    """Validate redirect URI against whitelist."""
    return uri in ALLOWED_REDIRECT_URIS

# In authorization URL generation
if not validate_redirect_uri(redirect_uri):
    raise ValueError("Invalid redirect_uri")
```

**Provider Configuration**:
- Register exact redirect URIs with OAuth provider
- Providers reject mismatched redirect URIs
- OutlabsAuth validates on callback

### 2. HTTPS in Production

**Attack**: Man-in-the-middle attacks on HTTP connections.

**Protection**:
```python
# Enforce HTTPS redirect URIs in production
if not app.debug and not redirect_uri.startswith("https://"):
    raise ValueError("HTTPS required for OAuth redirect_uri in production")

# Exception: localhost for development
if "localhost" in redirect_uri or "127.0.0.1" in redirect_uri:
    # Allow HTTP for local development
    pass
```

### 3. Rate Limiting

**Attack**: Brute-force OAuth flows or token exchanges.

**Protection**:
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.get("/auth/{provider}")
@limiter.limit("10/minute")  # Max 10 OAuth flows per minute
async def start_oauth(provider: str):
    """Start OAuth flow with rate limiting."""
    ...

@app.get("/auth/{provider}/callback")
@limiter.limit("20/minute")  # Max 20 callbacks per minute
async def oauth_callback(provider: str, code: str, state: str):
    """Handle OAuth callback with rate limiting."""
    ...
```

### 4. Log OAuth Events

**Security Monitoring**:
```python
import logging

logger = logging.getLogger("outlabs_auth.oauth")

# Log OAuth flow start
logger.info(
    "OAuth flow started",
    extra={
        "provider": provider,
        "user_id": user_id,
        "ip_address": request.client.host,
        "user_agent": request.headers.get("user-agent")
    }
)

# Log OAuth success
logger.info(
    "OAuth flow completed",
    extra={
        "provider": provider,
        "user_id": user_id,
        "linked": result.linked_account,
        "new_user": result.is_new_user
    }
)

# Log OAuth failures
logger.warning(
    "OAuth flow failed",
    extra={
        "provider": provider,
        "error": "invalid_state",
        "ip_address": request.client.host
    }
)
```

### 5. Token Revocation

**Revoke tokens when unlinking**:
```python
async def unlink_provider(user_id: str, provider: str):
    """Unlink provider and revoke tokens."""
    # Get social account
    social_account = await SocialAccount.find_one(
        SocialAccount.user_id == ObjectId(user_id),
        SocialAccount.provider == provider
    )

    # Revoke tokens at provider
    provider_instance = self.providers[provider]
    if provider_instance.supports_revocation:
        try:
            await provider_instance.revoke_token(
                social_account.access_token
            )
        except Exception as e:
            logger.warning(f"Failed to revoke {provider} token: {e}")

    # Delete social account
    await social_account.delete()
```

---

## OAuth Attack Scenarios & Defenses

### Scenario 1: CSRF Account Takeover

**Attack**:
1. Attacker initiates OAuth flow
2. Attacker gets authorization URL with their state
3. Attacker tricks victim into clicking URL
4. Victim approves OAuth
5. Attacker's account linked to victim's provider

**Defense** (State Parameter):
```python
# OutlabsAuth generates fresh state per user session
state = generate_state_token({}, secret=SECRET_KEY)

# Validates state in callback
state_data = decode_state_token(state, secret=SECRET_KEY)
# If state invalid → reject callback
```

### Scenario 2: Authorization Code Interception

**Attack**:
1. User initiates OAuth on mobile app
2. Malicious app intercepts authorization code from deep link
3. Attacker exchanges code for tokens

**Defense** (PKCE):
```python
# App generates PKCE pair
code_verifier, code_challenge = generate_pkce_pair(method="S256")

# Provider validates code_verifier matches challenge
# Attacker doesn't have code_verifier → rejected
```

### Scenario 3: ID Token Replay

**Attack**:
1. Attacker intercepts ID token from network
2. Attacker replays token to gain access

**Defense** (Nonce):
```python
# Generate nonce for OIDC flow
nonce = generate_nonce()

# Validate nonce in ID token matches
if id_token_payload.get("nonce") != stored_nonce:
    raise InvalidNonceError()
```

### Scenario 4: Email-Based Account Takeover

**Attack**:
1. Attacker creates unverified provider account with victim's email
2. Logs into app via OAuth
3. App auto-links to victim's account

**Defense** (Email Verification):
```python
# Only auto-link if email verified by provider
if user_info.email_verified:
    existing_user = await find_user_by_email(user_info.email)
else:
    # Create separate account - don't auto-link
    new_user = await create_user(user_info.email)
```

### Scenario 5: Open Redirect

**Attack**:
1. Attacker crafts malicious redirect_uri
2. Authorization code sent to attacker's domain

**Defense** (Redirect URI Whitelist):
```python
# Validate redirect_uri against whitelist
ALLOWED_REDIRECT_URIS = ["https://yourapp.com/auth/callback"]

if redirect_uri not in ALLOWED_REDIRECT_URIS:
    raise ValueError("Invalid redirect_uri")

# Provider also validates against registered URIs
```

---

## Security Checklist

### Before Production

- [ ] **State Parameter**
  - [ ] Generate unique state per OAuth flow
  - [ ] Use JWT-based state tokens (stateless)
  - [ ] Validate state in callback
  - [ ] Short expiration (10 minutes)

- [ ] **PKCE**
  - [ ] Enable PKCE for all providers that support it
  - [ ] Use S256 method (not plain)
  - [ ] Store code_verifier securely (in state token)
  - [ ] Validate code_verifier in token exchange

- [ ] **Nonce (OIDC)**
  - [ ] Generate nonce for Google, Apple
  - [ ] Validate nonce in ID token
  - [ ] Reject replayed ID tokens

- [ ] **Email Verification**
  - [ ] Only auto-link verified emails
  - [ ] Create separate accounts for unverified emails
  - [ ] Show clear UI for email conflicts

- [ ] **Token Storage**
  - [ ] Encrypt OAuth tokens at rest
  - [ ] Use HTTP-only cookies for web apps
  - [ ] Never store tokens in LocalStorage (if avoidable)

- [ ] **HTTPS**
  - [ ] Enforce HTTPS for redirect URIs in production
  - [ ] Use HTTPS for all OAuth endpoints
  - [ ] Allow HTTP only for localhost development

- [ ] **Redirect URI**
  - [ ] Whitelist allowed redirect URIs
  - [ ] Register exact URIs with providers
  - [ ] Validate redirect_uri in authorization

- [ ] **Rate Limiting**
  - [ ] Limit OAuth flow initiation (10/min)
  - [ ] Limit OAuth callbacks (20/min)
  - [ ] Monitor for abuse

- [ ] **Logging**
  - [ ] Log OAuth flow starts
  - [ ] Log OAuth successes
  - [ ] Log OAuth failures
  - [ ] Monitor for suspicious patterns

- [ ] **Token Revocation**
  - [ ] Revoke tokens when unlinking
  - [ ] Handle revocation failures gracefully
  - [ ] Test revocation with each provider

---

## Testing OAuth Security

### Test State Validation

```python
async def test_oauth_state_validation():
    """Test state parameter CSRF protection."""
    # Generate valid state
    state = generate_state_token({}, secret=SECRET_KEY)

    # ✅ Valid state should work
    state_data = decode_state_token(state, secret=SECRET_KEY)
    assert state_data["aud"] == "outlabs-auth:oauth-state"

    # ❌ Invalid state should fail
    with pytest.raises(jwt.InvalidTokenError):
        decode_state_token("invalid_state", secret=SECRET_KEY)

    # ❌ Expired state should fail
    expired_state = generate_state_token({}, secret=SECRET_KEY, lifetime_seconds=-1)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_state_token(expired_state, secret=SECRET_KEY)

    # ❌ Tampered state should fail
    tampered_state = state[:-5] + "xxxxx"
    with pytest.raises(jwt.InvalidTokenError):
        decode_state_token(tampered_state, secret=SECRET_KEY)
```

### Test PKCE Validation

```python
async def test_pkce_validation():
    """Test PKCE code challenge/verifier."""
    # Generate PKCE pair
    code_verifier, code_challenge = generate_pkce_pair(method="S256")

    # ✅ Valid verifier should match challenge
    assert verify_pkce(code_verifier, code_challenge, method="S256")

    # ❌ Invalid verifier should not match
    assert not verify_pkce("wrong_verifier", code_challenge, method="S256")
```

### Test Email Verification

```python
async def test_email_verification_auto_link():
    """Test auto-linking only happens with verified emails."""
    # Create existing user
    existing_user = await create_test_user(email="user@example.com")

    # ✅ Verified email → auto-link
    verified_user_info = OAuthUserInfo(
        provider_user_id="123",
        email="user@example.com",
        email_verified=True
    )
    user, _, is_new = await oauth_service._create_or_link_user(
        provider="google",
        user_info=verified_user_info,
        token_response=mock_token_response
    )
    assert user.id == existing_user.id  # Linked to existing user
    assert not is_new

    # ❌ Unverified email → create separate account
    unverified_user_info = OAuthUserInfo(
        provider_user_id="456",
        email="user@example.com",
        email_verified=False
    )
    user, _, is_new = await oauth_service._create_or_link_user(
        provider="facebook",
        user_info=unverified_user_info,
        token_response=mock_token_response
    )
    assert user.id != existing_user.id  # New user created
    assert is_new
```

---

## Summary

**OAuth Security Layers**:
1. ✅ **State Parameter** - CSRF protection with JWT tokens
2. ✅ **PKCE** - Code interception protection with S256
3. ✅ **Nonce** - ID token replay protection (OIDC)
4. ✅ **Email Verification** - Account takeover prevention
5. ✅ **Secure Storage** - Encrypt tokens at rest

**Best Practices**:
- Always validate state parameter
- Use PKCE with S256 method
- Check email_verified before auto-linking
- Encrypt OAuth tokens at rest
- Enforce HTTPS in production
- Whitelist redirect URIs
- Rate limit OAuth endpoints
- Log all OAuth events
- Revoke tokens when unlinking
- Test security measures

---

## Next Steps

- **[31. OAuth Setup →](./31-OAuth-Setup.md)** - Configure OAuth providers
- **[32. OAuth Providers →](./32-OAuth-Providers.md)** - Provider comparison
- **[33. OAuth Account Linking →](./33-OAuth-Account-Linking.md)** - Link multiple accounts
- **[110. Security Best Practices →](./110-Security-Best-Practices.md)** - General security

---

## Further Reading

### OAuth Security Standards
- [OAuth 2.0 Security Best Current Practice](https://tools.ietf.org/html/draft-ietf-oauth-security-topics)
- [OAuth 2.0 for Native Apps (RFC 8252)](https://tools.ietf.org/html/rfc8252)
- [PKCE (RFC 7636)](https://tools.ietf.org/html/rfc7636)
- [OpenID Connect Core](https://openid.net/specs/openid-connect-core-1_0.html)

### Security Research
- [OAuth 2.0 Threat Model](https://tools.ietf.org/html/rfc6819)
- [OAuth Security Cheat Sheet (OWASP)](https://cheatsheetseries.owasp.org/cheatsheets/OAuth2_Cheat_Sheet.html)
