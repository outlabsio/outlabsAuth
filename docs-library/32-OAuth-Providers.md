# 32. OAuth Provider Comparison

> **Quick Reference**: Detailed comparison of Google, GitHub, Facebook, and Apple OAuth providers to help you choose the right authentication method for your application.

## Overview

OutlabsAuth supports four major OAuth providers out of the box:

| Provider | Best For | Complexity | Email Verified | Refresh Tokens |
|----------|----------|------------|----------------|----------------|
| **Google** | General apps, B2B | ⭐ Easy | ✅ Yes | ✅ Yes |
| **GitHub** | Developer tools | ⭐ Easy | ✅ Yes | ✅ Yes |
| **Facebook** | Social apps, consumer | ⭐⭐ Medium | ⚠️ Sometimes | ⚠️ Long-lived only |
| **Apple** | iOS apps, privacy-focused | ⭐⭐⭐ Complex | ✅ Yes | ✅ Yes |

---

## Quick Start Comparison

### Setup Time

```python
# Google - Easiest setup (3 steps)
provider = GoogleProvider(
    client_id="your-id.apps.googleusercontent.com",
    client_secret="your-secret"
)

# GitHub - Simple setup (3 steps)
provider = GitHubProvider(
    client_id="your-client-id",
    client_secret="your-client-secret"
)

# Facebook - Medium setup (5 steps, needs app review for production)
provider = FacebookProvider(
    client_id="your-app-id",
    client_secret="your-app-secret"
)

# Apple - Complex setup (7 steps, requires P8 key generation)
provider = AppleProvider(
    client_id="com.yourcompany.service",
    team_id="ABCD123456",
    key_id="ABCD123456",
    private_key_path="/path/to/AuthKey_ABCD123456.p8"
)
```

**Setup Complexity Breakdown:**

- **Google**: OAuth Console → Create Client ID → Copy credentials ✅
- **GitHub**: Settings → New OAuth App → Copy credentials ✅
- **Facebook**: Create App → Add Facebook Login → Configure → Submit for Review ⚠️
- **Apple**: Create Service ID → Generate P8 Key → Configure domains → Complex JWT setup ⚠️⚠️

---

## Feature Comparison Matrix

### OAuth Capabilities

| Feature | Google | GitHub | Facebook | Apple |
|---------|--------|--------|----------|-------|
| **OpenID Connect** | ✅ Yes | ❌ No | ❌ No | ✅ Yes |
| **PKCE Support** | ✅ Yes | ✅ Yes | ❌ No | ✅ Yes |
| **Refresh Tokens** | ✅ Yes | ✅ Yes | ⚠️ Long-lived | ✅ Yes |
| **Token Revocation** | ✅ Yes | ✅ Yes | ❌ No | ✅ Yes |
| **Email Verified** | ✅ Always | ✅ Always | ⚠️ Sometimes | ✅ Always |
| **Profile Picture** | ✅ High-res | ✅ Avatar URL | ✅ Yes | ❌ No |
| **User Name** | ✅ Always | ✅ Always | ✅ Always | ⚠️ First login only |

### Security Features

| Feature | Google | GitHub | Facebook | Apple |
|---------|--------|--------|----------|-------|
| **State Parameter** | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes |
| **Nonce Support** | ✅ OIDC | ❌ No | ❌ No | ✅ OIDC |
| **PKCE** | ✅ Recommended | ✅ Recommended | ❌ Not supported | ✅ Recommended |
| **ID Token** | ✅ JWT (OIDC) | ❌ No | ❌ No | ✅ JWT (OIDC) |
| **Client Auth** | Client Secret | Client Secret | Client Secret | JWT (ES256) |
| **Private Email** | ❌ No | ❌ No | ⚠️ Optional | ✅ Hide My Email |

### User Data Fields

| Field | Google | GitHub | Facebook | Apple |
|-------|--------|--------|----------|-------|
| **User ID** | Numeric string | Numeric ID | Numeric ID | Team-scoped ID |
| **Email** | ✅ Always | ✅ Always | ⚠️ Optional | ✅ Always |
| **Email Verified** | ✅ `verified_email` | ✅ Primary email | ⚠️ `verified` flag | ✅ ID token claim |
| **Full Name** | ✅ `name` | ✅ `name` or `login` | ✅ `name` | ⚠️ First login only |
| **First Name** | ✅ `given_name` | ❌ No | ✅ `first_name` | ⚠️ First login only |
| **Last Name** | ✅ `family_name` | ❌ No | ✅ `last_name` | ⚠️ First login only |
| **Picture** | ✅ High-res URL | ✅ `avatar_url` | ✅ Profile picture | ❌ No |
| **Locale** | ✅ `locale` | ❌ No | ❌ No | ✅ ID token |

---

## Detailed Provider Comparison

### 1. Google OAuth

**Best for**: General-purpose apps, B2B applications, Google Workspace integration

#### Pros
- ✅ **Easiest setup**: 3-step process in Google Cloud Console
- ✅ **OpenID Connect**: Standardized, secure ID tokens
- ✅ **Always verified emails**: Google verifies all email addresses
- ✅ **Rich user data**: Name, picture, locale all included
- ✅ **Refresh tokens**: Long-lived with `access_type=offline`
- ✅ **Excellent documentation**: Google has comprehensive OAuth guides
- ✅ **High-res profile pictures**: Quality avatar images
- ✅ **Workspace integration**: Can restrict to specific domains (`hd` parameter)

#### Cons
- ❌ **Google account required**: Users without Google accounts cannot use
- ⚠️ **Token expiry**: Access tokens expire in 1 hour (need refresh)
- ⚠️ **Privacy concerns**: Some users avoid Google for privacy reasons

#### Special Features
- **Hosted Domain Restriction**: Limit to Google Workspace domain
  ```python
  provider = GoogleProvider(
      client_id="...",
      client_secret="...",
      hosted_domain="yourcompany.com"  # Only @yourcompany.com emails
  )
  ```
- **Incremental Authorization**: Request additional scopes later
- **Offline Access**: `access_type=offline` for refresh tokens

#### Token Lifetimes
- **Access Token**: 1 hour
- **Refresh Token**: No expiration (can be revoked)
- **ID Token**: 1 hour

#### User Info Response
```json
{
  "id": "107353926327...",
  "email": "user@gmail.com",
  "verified_email": true,
  "name": "John Doe",
  "given_name": "John",
  "family_name": "Doe",
  "picture": "https://lh3.googleusercontent.com/...",
  "locale": "en"
}
```

---

### 2. GitHub OAuth

**Best for**: Developer tools, coding platforms, technical applications

#### Pros
- ✅ **Simple setup**: Quick OAuth app registration
- ✅ **Developer-friendly**: Great for technical audiences
- ✅ **Refresh tokens**: Added in 2021, 8-hour expiry
- ✅ **Verified emails**: Primary email always verified
- ✅ **Token revocation**: Can revoke access via API
- ✅ **PKCE support**: Enhanced security for public clients
- ✅ **No app review**: Instant production use

#### Cons
- ❌ **Not OpenID Connect**: Custom implementation
- ❌ **Limited user data**: No separate first/last name
- ❌ **Developer audience only**: Non-technical users may not have accounts
- ⚠️ **Email scope required**: Must request `user:email` scope
- ⚠️ **Short refresh token**: Only 8 hours

#### Special Features
- **Organization Access**: Request access to user's organizations
- **Repository Scopes**: Fine-grained access to repos
- **Two API Calls**: Separate calls for profile and emails
  ```python
  # GitHub fetches user profile + emails separately
  profile = await get("/user")
  emails = await get("/user/emails")  # Requires user:email scope
  ```

#### Token Lifetimes
- **Access Token**: 8 hours
- **Refresh Token**: 6 months
- **No ID Token**: Not OpenID Connect

#### User Info Response
```json
{
  "id": 12345678,
  "login": "johndoe",
  "name": "John Doe",
  "email": null,  // Often null in profile
  "avatar_url": "https://avatars.githubusercontent.com/...",
  "bio": "Software developer"
}
```

**Email Response** (separate call):
```json
[
  {
    "email": "john@example.com",
    "primary": true,
    "verified": true
  }
]
```

---

### 3. Facebook Login

**Best for**: Social apps, consumer applications, B2C

#### Pros
- ✅ **Massive user base**: 3 billion+ active users
- ✅ **Social features**: Friend lists, social graph access
- ✅ **Profile pictures**: High-quality profile images
- ✅ **Long-lived tokens**: 60-day tokens (vs short-lived refresh pattern)
- ✅ **Mobile SDK**: Excellent iOS/Android integration

#### Cons
- ❌ **No PKCE**: Doesn't support PKCE flow
- ❌ **No refresh tokens**: Uses token exchange instead
- ❌ **No revocation**: No standard token revocation endpoint
- ❌ **Not OpenID Connect**: Custom implementation
- ⚠️ **App Review Required**: Production apps need Facebook approval
- ⚠️ **Email optional**: Users can decline email permission
- ⚠️ **Verification inconsistent**: Not all emails are verified
- ⚠️ **Privacy concerns**: Facebook's data privacy reputation

#### Special Features
- **Short-lived → Long-lived Token Exchange**:
  ```python
  # Exchange 2-hour token for 60-day token
  long_token = await provider.exchange_short_lived_token(short_token)
  ```
- **Graph API Version**: Configurable API version
  ```python
  provider = FacebookProvider(
      client_id="...",
      client_secret="...",
      api_version="v18.0"  # Specify version
  )
  ```
- **Field Selection**: Must specify fields in user info request
  ```python
  # Facebook requires explicit field list
  params = {
      "fields": "id,name,email,first_name,last_name,picture,verified"
  }
  ```

#### Token Lifetimes
- **Short-lived Access Token**: 2 hours (default)
- **Long-lived Access Token**: 60 days (after exchange)
- **No Refresh Token**: Use token exchange instead
- **No ID Token**: Not OpenID Connect

#### User Info Response
```json
{
  "id": "123456789",
  "name": "John Doe",
  "email": "john@example.com",  // May be missing
  "first_name": "John",
  "last_name": "Doe",
  "verified": true,  // Account verified, NOT email verified
  "picture": {
    "data": {
      "url": "https://platform-lookaside.fbsbx.com/..."
    }
  }
}
```

---

### 4. Apple Sign In

**Best for**: iOS apps, privacy-focused applications, Apple ecosystem

#### Pros
- ✅ **Privacy-first**: Hide My Email, minimal data sharing
- ✅ **iOS requirement**: Required for iOS apps with social login
- ✅ **OpenID Connect**: Standardized, secure ID tokens
- ✅ **Verified emails**: All emails verified by Apple
- ✅ **PKCE support**: Enhanced security
- ✅ **Refresh tokens**: Long-lived refresh tokens
- ✅ **Token revocation**: Proper revocation support
- ✅ **Premium perception**: Apple's trusted brand

#### Cons
- ❌ **Most complex setup**: 7-step process with P8 key generation
- ❌ **JWT client secret**: Must generate ES256 JWT for auth
- ❌ **No profile picture**: Apple doesn't provide user photos
- ❌ **No userinfo endpoint**: Must parse ID token
- ⚠️ **Name only on first login**: Subsequent logins don't include name
- ⚠️ **Private email addresses**: May get `@privaterelay.appleid.com`
- ⚠️ **Strict redirect URIs**: Must use HTTPS in production
- ⚠️ **Team-scoped user IDs**: Different per developer team

#### Special Features
- **Hide My Email**: Users can hide real email
  ```json
  {
    "email": "abc123def456@privaterelay.appleid.com"
  }
  ```
- **JWT Client Secret**: Generate on each request
  ```python
  # Apple uses JWT instead of client_secret
  client_secret = self._generate_client_secret()  # ES256 JWT
  ```
- **Name Only Once**: Store name on first login
  ```python
  # First login: name included
  # Subsequent logins: name is null
  # IMPORTANT: Save user.name on first auth!
  ```
- **ID Token Parsing**: User info in JWT
  ```python
  user_info = provider.parse_id_token(token_response.id_token)
  ```

#### Token Lifetimes
- **Access Token**: 1 hour
- **Refresh Token**: 6 months
- **ID Token**: 10 minutes
- **Client Secret JWT**: 1 hour (generate per request)

#### ID Token Payload
```json
{
  "sub": "001234.abc123def456...",
  "email": "john@example.com",
  "email_verified": true,
  "is_private_email": false,
  "aud": "com.yourcompany.service",
  "iss": "https://appleid.apple.com",
  "iat": 1234567890,
  "exp": 1234567900
}
```

**Note**: Name is only in the initial callback (not in ID token):
```json
// Initial callback includes:
{
  "user": {
    "name": {
      "firstName": "John",
      "lastName": "Doe"
    },
    "email": "john@example.com"
  }
}
// Subsequent logins: No name field!
```

---

## Scope Comparison

### Google Scopes

| Scope | Purpose | Required |
|-------|---------|----------|
| `openid` | OpenID Connect | ✅ Yes |
| `email` | Email address | ✅ Yes |
| `profile` | Name, picture, locale | ✅ Recommended |

**Additional Scopes**:
- `https://www.googleapis.com/auth/userinfo.profile` - Profile info
- `https://www.googleapis.com/auth/drive.readonly` - Google Drive read
- `https://www.googleapis.com/auth/calendar.readonly` - Calendar read

### GitHub Scopes

| Scope | Purpose | Required |
|-------|---------|----------|
| `user:email` | Email addresses | ✅ Yes |
| `read:user` | Profile info | ✅ Recommended |

**Additional Scopes**:
- `repo` - Repository access
- `read:org` - Organization membership
- `gist` - Gist access

### Facebook Scopes

| Scope | Purpose | Required |
|-------|---------|----------|
| `email` | Email address | ✅ Yes |
| `public_profile` | Name, picture | ✅ Yes |

**Additional Scopes** (require app review):
- `user_friends` - Friend list
- `user_posts` - User posts
- `pages_read_engagement` - Page insights

### Apple Scopes

| Scope | Purpose | Required |
|-------|---------|----------|
| `email` | Email address | ✅ Yes |
| `name` | Full name | ✅ Recommended |

**Note**: Apple has limited scopes compared to other providers. Focus is on minimal data collection.

---

## OAuth Flow Comparison

### Standard Flow (Google, GitHub, Facebook)

```
1. Get authorization URL
   ↓
2. Redirect user to provider
   ↓
3. User approves access
   ↓
4. Provider redirects with code
   ↓
5. Exchange code for token
   ↓
6. Fetch user info
   ↓
7. Create/login user
```

### Apple Flow (Slightly Different)

```
1. Get authorization URL
   ↓
2. Redirect user to Apple
   ↓
3. User approves (Face ID/Touch ID)
   ↓
4. Apple redirects with code + user data (first time only)
   ↓
5. Exchange code for token (JWT client secret required)
   ↓
6. Parse ID token for user info (no separate endpoint)
   ↓
7. Create/login user (save name on first login!)
```

---

## Performance Comparison

### Token Exchange Speed

| Provider | Avg Response Time | Notes |
|----------|-------------------|-------|
| **Google** | ~200ms | Fast, reliable CDN |
| **GitHub** | ~150ms | Very fast |
| **Facebook** | ~300ms | Slower, more processing |
| **Apple** | ~250ms | JWT generation overhead |

### User Info Fetch Speed

| Provider | Avg Response Time | API Calls |
|----------|-------------------|-----------|
| **Google** | ~100ms | 1 call |
| **GitHub** | ~150ms | 2 calls (profile + emails) |
| **Facebook** | ~120ms | 1 call |
| **Apple** | ~0ms | No call (ID token parsing) |

**Winner**: Apple (ID token parsing, no network call) 🏆

---

## Error Handling Comparison

### Invalid Code Errors

```python
# Google
InvalidCodeError: "Authorization code invalid or expired"
# error: "invalid_grant"

# GitHub
InvalidCodeError: "Authorization code invalid or expired"
# error: "bad_verification_code"

# Facebook
InvalidCodeError: "Authorization code invalid or expired"
# error.code varies, check message

# Apple
InvalidCodeError: "Authorization code invalid or expired"
# error: "invalid_grant"
```

### Revocation Support

| Provider | Method | Endpoint | Response |
|----------|--------|----------|----------|
| **Google** | POST | `/revoke` | 200 OK |
| **GitHub** | DELETE | `/applications/{client_id}/token` | 204 No Content |
| **Facebook** | ❌ Not supported | N/A | N/A |
| **Apple** | POST | `/auth/revoke` | 200 OK |

---

## When to Use Each Provider

### Choose Google When:
- ✅ You need reliable, verified email addresses
- ✅ Your audience has Google accounts (most people)
- ✅ You want OpenID Connect standardization
- ✅ You're building B2B apps (Google Workspace)
- ✅ You need high-quality profile pictures
- ✅ You want the simplest setup

### Choose GitHub When:
- ✅ Your app is for developers
- ✅ You need repository or organization access
- ✅ Your audience is technical
- ✅ You want quick setup with no app review
- ✅ You're building developer tools or coding platforms

### Choose Facebook When:
- ✅ You're building social/consumer apps
- ✅ You need access to social graph (friends, posts)
- ✅ Your audience is broad consumer base
- ✅ You need mobile SDK integration (iOS/Android)
- ✅ Social features are core to your app
- ❌ BUT: Be prepared for app review process

### Choose Apple When:
- ✅ You're building iOS apps (required if you have social login)
- ✅ Privacy is a core value for your app
- ✅ Your audience values Apple's ecosystem
- ✅ You want premium brand perception
- ✅ You can handle complex setup (P8 keys, JWT)
- ⚠️ BUT: Store user names on first login!

---

## Multi-Provider Strategy

### Recommended Combinations

#### 1. **General SaaS App**
```python
providers = {
    "google": GoogleProvider(...),    # Primary (80% of users)
    "github": GitHubProvider(...),    # Developers
}
```
**Reasoning**: Covers vast majority with minimal complexity.

#### 2. **Developer Platform**
```python
providers = {
    "github": GitHubProvider(...),    # Primary for developers
    "google": GoogleProvider(...),    # Backup option
}
```
**Reasoning**: GitHub first for dev-focused audience.

#### 3. **Consumer/Social App**
```python
providers = {
    "google": GoogleProvider(...),    # Broad coverage
    "facebook": FacebookProvider(...), # Social features
    "apple": AppleProvider(...),      # iOS requirement
}
```
**Reasoning**: Maximum reach, covers iOS requirement.

#### 4. **Enterprise B2B App**
```python
providers = {
    "google": GoogleProvider(
        ...,
        hosted_domain="clientcompany.com"  # Restrict to domain
    ),
}
```
**Reasoning**: Google Workspace integration, domain restriction.

#### 5. **Privacy-Focused App**
```python
providers = {
    "apple": AppleProvider(...),      # Privacy-first
    "google": GoogleProvider(...),    # Backup
}
```
**Reasoning**: Emphasize privacy with Apple as primary.

---

## Provider-Specific Gotchas

### Google
- ⚠️ **Refresh Token**: Only returned on first authorization or with `prompt=consent`
  ```python
  extra_params={"access_type": "offline", "prompt": "consent"}
  ```
- ⚠️ **Email Changes**: Users can change Google email (handle updates)
- ⚠️ **Deleted Accounts**: Google accounts can be deleted (handle gracefully)

### GitHub
- ⚠️ **Email Scope**: `user:email` scope is mandatory for email access
- ⚠️ **Private Emails**: Users can hide email (may get `@users.noreply.github.com`)
- ⚠️ **Organization Access**: Requires user approval per organization
- ⚠️ **Two API Calls**: Profile + emails = 2 network requests

### Facebook
- ⚠️ **App Review**: Production requires Facebook approval (2-7 days)
- ⚠️ **Email Optional**: Users can decline email permission
- ⚠️ **Token Exchange**: Must exchange short-lived → long-lived manually
- ⚠️ **No Revocation**: Cannot revoke tokens programmatically
- ⚠️ **API Versioning**: Must update version annually

### Apple
- ⚠️ **Name Only Once**: Save `user.name` on first login or lose it forever!
- ⚠️ **Private Emails**: May receive `@privaterelay.appleid.com`
- ⚠️ **HTTPS Required**: Production must use HTTPS redirect URIs
- ⚠️ **P8 Key Security**: Keep private key secure, rotate periodically
- ⚠️ **JWT Generation**: Must generate client_secret JWT on each request
- ⚠️ **Team-Scoped IDs**: User IDs different across developer teams

---

## Testing Comparison

### Local Development

| Provider | Works on localhost | Notes |
|----------|-------------------|-------|
| **Google** | ✅ Yes | `http://localhost:3000` allowed |
| **GitHub** | ✅ Yes | `http://localhost:3000` allowed |
| **Facebook** | ⚠️ Partial | Need ngrok for some features |
| **Apple** | ❌ No | HTTPS required (use ngrok) |

### Test Accounts

| Provider | Test Accounts | Notes |
|----------|--------------|-------|
| **Google** | ✅ Any Google account | Use personal accounts |
| **GitHub** | ✅ Any GitHub account | Use personal accounts |
| **Facebook** | ✅ Test users | Can create test users in app |
| **Apple** | ⚠️ Sandbox | TestFlight or Sandbox mode |

---

## Migration Considerations

### Changing User IDs

**Each provider uses different user ID formats:**

```python
# Google: Numeric string
"107353926327..."

# GitHub: Integer
12345678

# Facebook: Numeric string
"123456789"

# Apple: Team-scoped opaque string
"001234.abc123def456gh789ijk012..."
```

**IMPORTANT**: Store provider name + provider_user_id separately!

```python
class OAuthAccount(Document):
    provider: str  # "google", "github", "facebook", "apple"
    provider_user_id: str  # Provider's user ID
    user_id: str  # Your internal user ID
    email: str
    metadata: dict
```

### Email Conflicts

**Handle when same email exists across providers:**

```python
# Scenario: user@example.com logs in with Google, then GitHub
# Options:

# 1. Link to existing account (recommended)
existing_user = await find_user_by_email(email)
await link_oauth_account(existing_user.id, "github", github_user_id)

# 2. Create separate account
# (Not recommended - confusing for users)

# 3. Ask user to confirm account linking
# (Best UX - let user decide)
```

### Private/Proxy Emails

**Apple and GitHub can provide proxy emails:**

```python
# Apple Hide My Email
"abc123def456@privaterelay.appleid.com"

# GitHub private email
"12345678+johndoe@users.noreply.github.com"

# IMPORTANT: These are permanent for the user
# Store them as-is, don't try to resolve to "real" email
```

---

## Code Examples

### Complete Multi-Provider Setup

```python
from outlabs_auth import SimpleRBAC
from outlabs_auth.oauth.providers import (
    GoogleProvider,
    GitHubProvider,
    FacebookProvider,
    AppleProvider
)

# Initialize all providers
providers = {
    "google": GoogleProvider(
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET")
    ),
    "github": GitHubProvider(
        client_id=os.getenv("GITHUB_CLIENT_ID"),
        client_secret=os.getenv("GITHUB_CLIENT_SECRET")
    ),
    "facebook": FacebookProvider(
        client_id=os.getenv("FACEBOOK_APP_ID"),
        client_secret=os.getenv("FACEBOOK_APP_SECRET"),
        api_version="v18.0"
    ),
    "apple": AppleProvider(
        client_id=os.getenv("APPLE_SERVICE_ID"),
        team_id=os.getenv("APPLE_TEAM_ID"),
        key_id=os.getenv("APPLE_KEY_ID"),
        private_key_path="/path/to/AuthKey.p8"
    )
}

# Initialize auth with OAuth
auth = SimpleRBAC(
    database=mongo_client,
    oauth_providers=providers
)
```

### Provider-Specific Flows

#### Google with Workspace Restriction

```python
provider = GoogleProvider(
    client_id="...",
    client_secret="...",
    hosted_domain="yourcompany.com"  # Only @yourcompany.com
)

# Get authorization URL
auth_url = provider.get_authorization_url(
    redirect_uri="https://yourapp.com/auth/google/callback",
    use_pkce=True
)

# Exchange code
tokens = await provider.exchange_code(
    code=code,
    redirect_uri=redirect_uri,
    code_verifier=code_verifier
)

# Get user info
user = await provider.get_user_info(tokens.access_token)
# user.email will be verified @yourcompany.com
```

#### GitHub with Email Fetch

```python
provider = GitHubProvider(
    client_id="...",
    client_secret="..."
)

# GitHub automatically fetches emails (needs user:email scope)
user = await provider.get_user_info(tokens.access_token)
# user.email is primary verified email
# user.email_verified is True if email verified
```

#### Facebook Token Exchange

```python
provider = FacebookProvider(
    client_id="...",
    client_secret="..."
)

# Exchange code (returns short-lived token)
tokens = await provider.exchange_code(code, redirect_uri)
# tokens.expires_in = 7200 (2 hours)

# Exchange for long-lived token (60 days)
long_tokens = await provider.exchange_short_lived_token(
    tokens.access_token
)
# long_tokens.expires_in = 5184000 (60 days)
```

#### Apple with Name Capture

```python
provider = AppleProvider(
    client_id="com.yourcompany.service",
    team_id="...",
    key_id="...",
    private_key_path="/path/to/AuthKey.p8"
)

# IMPORTANT: On first login, Apple sends user data in callback
# You must capture it before token exchange!

# In your callback endpoint:
@app.post("/auth/apple/callback")
async def apple_callback(request: Request):
    form = await request.form()

    # First login: Apple sends user data
    if "user" in form:
        user_data = json.loads(form["user"])
        # SAVE THIS NOW - you won't get it again!
        name = user_data.get("name", {})
        first_name = name.get("firstName")
        last_name = name.get("lastName")
        # Store in session or database

    # Exchange code
    code = form["code"]
    tokens = await provider.exchange_code(code, redirect_uri)

    # Parse ID token for email
    user_info = provider.parse_id_token(tokens.id_token)

    # Create or update user
    # Use saved name if available (first login)
    # Otherwise, user_info.name will be None
```

---

## Summary Table

| Aspect | Google | GitHub | Facebook | Apple |
|--------|--------|--------|----------|-------|
| **Setup Difficulty** | ⭐ Easy | ⭐ Easy | ⭐⭐ Medium | ⭐⭐⭐ Hard |
| **Best For** | General apps | Dev tools | Social apps | iOS apps |
| **OpenID Connect** | ✅ Yes | ❌ No | ❌ No | ✅ Yes |
| **PKCE** | ✅ Yes | ✅ Yes | ❌ No | ✅ Yes |
| **Email Verified** | ✅ Always | ✅ Always | ⚠️ Sometimes | ✅ Always |
| **Refresh Tokens** | ✅ Yes | ✅ Yes (8h) | ⚠️ Exchange | ✅ Yes |
| **Revocation** | ✅ Yes | ✅ Yes | ❌ No | ✅ Yes |
| **User Data** | Rich | Basic | Rich | Minimal |
| **Privacy Focus** | Medium | Medium | Low | ✅ High |
| **Production Ready** | ✅ Instant | ✅ Instant | ⚠️ Review needed | ✅ Instant |

---

## Next Steps

- **[31. OAuth Setup →](./31-OAuth-Setup.md)** - Detailed setup for each provider
- **[33. OAuth Account Linking →](./33-OAuth-Account-Linking.md)** - Link multiple OAuth accounts
- **[25. Multi-Source Auth →](./25-Multi-Source-Auth.md)** - Combine OAuth with API keys

---

## Further Reading

### Official Documentation
- [Google OAuth 2.0](https://developers.google.com/identity/protocols/oauth2)
- [GitHub OAuth Apps](https://docs.github.com/en/developers/apps/building-oauth-apps)
- [Facebook Login](https://developers.facebook.com/docs/facebook-login)
- [Apple Sign In](https://developer.apple.com/sign-in-with-apple/)

### Security Best Practices
- [OAuth 2.0 Security Best Practices](https://tools.ietf.org/html/draft-ietf-oauth-security-topics)
- [PKCE (RFC 7636)](https://tools.ietf.org/html/rfc7636)
- [OpenID Connect Core](https://openid.net/specs/openid-connect-core-1_0.html)
