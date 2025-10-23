# OAuth Setup

**Tags**: #oauth #social-login #authentication #google #facebook #github #apple

Complete guide to setting up OAuth providers for social login.

---

## Overview

OAuth allows users to sign in with their existing accounts from Google, Facebook, GitHub, Apple, and other providers. OutlabsAuth provides pre-configured providers that handle all OAuth complexity for you.

**Prerequisites**: [[30-OAuth-Overview|OAuth Overview]]

**Key Benefits**:
- Faster registration (no password needed)
- Better security (rely on provider's security)
- Familiar login experience
- Automatic email verification (for verified providers)

---

## Quick Start

### 1. Install OAuth Dependencies

```bash
pip install outlabs-auth[oauth]
```

### 2. Configure Providers

```python
from outlabs_auth import SimpleRBAC
from outlabs_auth.oauth.providers import GoogleProvider, GitHubProvider

# Initialize providers
providers = {
    "google": GoogleProvider(
        client_id="your-client-id.apps.googleusercontent.com",
        client_secret="your-client-secret"
    ),
    "github": GitHubProvider(
        client_id="your-github-client-id",
        client_secret="your-github-client-secret"
    )
}

# Initialize auth with OAuth
auth = SimpleRBAC(
    database=db,
    oauth_providers=providers
)
```

### 3. Add OAuth Routes

```python
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse

app = FastAPI()

@app.get("/auth/{provider}/login")
async def oauth_login(provider: str, request: Request):
    """Start OAuth flow"""
    redirect_uri = f"{request.base_url}auth/{provider}/callback"
    auth_url = await auth.oauth_service.get_authorization_url(
        provider=provider,
        redirect_uri=str(redirect_uri)
    )
    return RedirectResponse(auth_url)

@app.get("/auth/{provider}/callback")
async def oauth_callback(provider: str, code: str, state: str, request: Request):
    """Handle OAuth callback"""
    redirect_uri = f"{request.base_url}auth/{provider}/callback"
    result = await auth.oauth_service.handle_callback(
        provider=provider,
        code=code,
        state=state,
        redirect_uri=str(redirect_uri)
    )

    # User authenticated! Return tokens or redirect to frontend
    return {
        "access_token": result.access_token,
        "refresh_token": result.refresh_token,
        "user_id": str(result.user.id),
        "is_new_user": result.is_new_user
    }
```

That's it! OAuth is configured and ready to use.

---

## Provider Setup Guides

### Google OAuth

**What You Get**:
- ✅ OpenID Connect (OIDC) support
- ✅ Email automatically verified
- ✅ Refresh token support
- ✅ Token revocation support
- ✅ PKCE security

**Setup Steps**:

1. **Go to Google Cloud Console**
   - Visit: https://console.cloud.google.com/apis/credentials
   - Create a new project (or select existing)

2. **Enable Google+ API** (if not already enabled)
   - Go to "APIs & Services" → "Library"
   - Search for "Google+ API"
   - Click "Enable"

3. **Create OAuth 2.0 Client ID**
   - Go to "Credentials"
   - Click "Create Credentials" → "OAuth client ID"
   - Application type: "Web application"
   - Name: "My App - OAuth"

4. **Configure Authorized Redirect URIs**
   ```
   # Development
   http://localhost:3000/auth/google/callback
   http://127.0.0.1:3000/auth/google/callback

   # Production
   https://yourdomain.com/auth/google/callback
   ```

5. **Copy Credentials**
   - Client ID: `something.apps.googleusercontent.com`
   - Client Secret: `GOCSPX-something`

6. **Configure in Code**
   ```python
   from outlabs_auth.oauth.providers import GoogleProvider

   google = GoogleProvider(
       client_id="your-client-id.apps.googleusercontent.com",
       client_secret="your-client-secret"
   )
   ```

**Optional: Google Workspace Restriction**

Restrict to specific Google Workspace domain:

```python
google = GoogleProvider(
    client_id="your-client-id.apps.googleusercontent.com",
    client_secret="your-client-secret",
    hosted_domain="yourcompany.com"  # Only allow yourcompany.com emails
)
```

**Scopes Requested**:
- `openid` - OpenID Connect
- `email` - User's email address
- `profile` - User's profile info (name, picture)

**User Info Returned**:
```python
{
    "provider_user_id": "1234567890",
    "email": "user@gmail.com",
    "email_verified": True,  # Always true for Google
    "name": "John Doe",
    "given_name": "John",
    "family_name": "Doe",
    "picture": "https://lh3.googleusercontent.com/...",
    "locale": "en"
}
```

---

### GitHub OAuth

**What You Get**:
- ✅ Email from verified GitHub account
- ✅ Refresh token support
- ✅ Token revocation support
- ✅ PKCE security

**Setup Steps**:

1. **Go to GitHub Developer Settings**
   - Visit: https://github.com/settings/developers
   - Click "OAuth Apps" → "New OAuth App"

2. **Register Application**
   - Application name: "My App"
   - Homepage URL: `https://yourdomain.com`
   - Authorization callback URL:
   ```
   # Development
   http://localhost:3000/auth/github/callback

   # Production
   https://yourdomain.com/auth/github/callback
   ```

3. **Generate Client Secret**
   - After creating the app, click "Generate a new client secret"
   - **Copy immediately** - you won't see it again!

4. **Copy Credentials**
   - Client ID: 20-character hex string
   - Client Secret: 40-character hex string

5. **Configure in Code**
   ```python
   from outlabs_auth.oauth.providers import GitHubProvider

   github = GitHubProvider(
       client_id="your-github-client-id",
       client_secret="your-github-client-secret"
   )
   ```

**Scopes Requested**:
- `user:email` - User's email addresses (required)
- `read:user` - User's profile info

**User Info Returned**:
```python
{
    "provider_user_id": "12345678",
    "email": "user@example.com",  # Primary verified email
    "email_verified": True,  # Only if verified on GitHub
    "name": "John Doe",
    "picture": "https://avatars.githubusercontent.com/u/12345678",
    "provider_data": {
        "login": "johndoe",
        "bio": "Developer",
        ...
    }
}
```

**Note**: GitHub only returns email if `user:email` scope is granted and user has a verified email.

---

### Facebook Login

**What You Get**:
- ✅ Email (if granted by user)
- ✅ Public profile info
- ✅ Long-lived token support
- ❌ No PKCE (Facebook doesn't support it yet)

**Setup Steps**:

1. **Go to Facebook for Developers**
   - Visit: https://developers.facebook.com/apps
   - Click "Create App"

2. **Choose App Type**
   - Select "Consumer"
   - Fill in basic app information

3. **Add Facebook Login Product**
   - In app dashboard, click "Add Product"
   - Find "Facebook Login" → Click "Set Up"

4. **Configure Facebook Login Settings**
   - Go to "Facebook Login" → "Settings"
   - Valid OAuth Redirect URIs:
   ```
   # Development
   http://localhost:3000/auth/facebook/callback

   # Production
   https://yourdomain.com/auth/facebook/callback
   ```

5. **Get App Credentials**
   - Go to "Settings" → "Basic"
   - App ID: Your client ID
   - App Secret: Your client secret (click "Show")

6. **Make App Live**
   - In dev mode, only admins/testers can use OAuth
   - Go to top of dashboard → Switch to "Live" mode

7. **Configure in Code**
   ```python
   from outlabs_auth.oauth.providers import FacebookProvider

   facebook = FacebookProvider(
       client_id="your-facebook-app-id",  # App ID
       client_secret="your-facebook-app-secret"
   )
   ```

**Scopes Requested**:
- `email` - User's email address
- `public_profile` - User's public profile info (name, picture)

**User Info Returned**:
```python
{
    "provider_user_id": "1234567890",
    "email": "user@example.com",  # May be None if user denied
    "email_verified": False,  # Facebook doesn't provide verification status
    "name": "John Doe",
    "given_name": "John",
    "family_name": "Doe",
    "picture": "https://graph.facebook.com/v18.0/1234567890/picture",
    "locale": "en_US"
}
```

**Important**: Users can deny email permission. Always handle missing email gracefully.

---

### Apple Sign In

**What You Get**:
- ✅ OpenID Connect (OIDC) support
- ✅ Email (may be privacy relay)
- ✅ Refresh token support
- ✅ Token revocation support
- ✅ PKCE security
- ⚠️ Name only on first login

**Setup Steps** (More Complex):

1. **Go to Apple Developer Portal**
   - Visit: https://developer.apple.com/account/resources
   - You need a paid Apple Developer account ($99/year)

2. **Register App ID**
   - Go to "Identifiers" → "+" button
   - Select "App IDs" → Continue
   - Fill in description and Bundle ID
   - Enable "Sign in with Apple"
   - Configure as primary App ID

3. **Create Service ID** (Your OAuth Client ID)
   - Go to "Identifiers" → "+" button
   - Select "Services IDs" → Continue
   - Identifier: `com.yourcompany.service` (this is your client_id)
   - Description: "My App - Web Login"
   - Enable "Sign in with Apple"
   - Configure:
     - Primary App ID: (select the App ID from step 2)
     - Web domains: `yourdomain.com`
     - Return URLs:
     ```
     https://yourdomain.com/auth/apple/callback
     ```
   - **Note**: Apple does NOT allow `http://` or `localhost`! Use `https://` only.

4. **Create Sign in with Apple Key**
   - Go to "Keys" → "+" button
   - Key Name: "Sign in with Apple Key"
   - Enable "Sign in with Apple"
   - Configure: Select your primary App ID
   - Click "Continue" → "Register"
   - **Download the `.p8` file** - you won't see it again!
   - Note the Key ID (10-character string)

5. **Get Your Team ID**
   - In the top right of Apple Developer portal
   - Your Team ID is a 10-character string

6. **Configure in Code**
   ```python
   from outlabs_auth.oauth.providers import AppleProvider

   apple = AppleProvider(
       client_id="com.yourcompany.service",  # Service ID
       team_id="ABCD123456",  # Your Team ID
       key_id="ABCD123456",  # Key ID from step 4
       private_key_path="/path/to/AuthKey_ABCD123456.p8"  # Downloaded P8 file
   )

   # Or pass private key directly
   apple = AppleProvider(
       client_id="com.yourcompany.service",
       team_id="ABCD123456",
       key_id="ABCD123456",
       private_key="""-----BEGIN PRIVATE KEY-----
   YOUR_PRIVATE_KEY_CONTENT
   -----END PRIVATE KEY-----"""
   )
   ```

**Scopes Requested**:
- `email` - User's email address
- `name` - User's name (only on first authorization!)

**User Info Returned**:
```python
{
    "provider_user_id": "001234.a1b2c3d4...",
    "email": "user@privaterelay.appleid.com",  # May be relay address
    "email_verified": True,  # Always verified by Apple
    "name": "John Doe",  # Only on FIRST login!
    "given_name": "John",  # Only on FIRST login!
    "family_name": "Doe",  # Only on FIRST login!
}
```

**Important Apple Quirks**:

1. **Name only on first authorization**
   - Apple only sends name data on the very first login
   - Subsequent logins only return user ID and email
   - **You MUST store name on first login!**

2. **Private Relay Email**
   - User can choose to hide their email
   - You get `something@privaterelay.appleid.com`
   - Emails sent to relay address are forwarded to user
   - Relay address is stable for your app

3. **No localhost in development**
   - Apple requires `https://` URLs
   - Use a tool like ngrok for local development:
   ```bash
   ngrok http 3000
   # Use the https URL in Apple configuration
   ```

---

## Configuration Examples

### Multiple Providers

```python
from outlabs_auth import SimpleRBAC
from outlabs_auth.oauth.providers import (
    GoogleProvider,
    GitHubProvider,
    FacebookProvider,
    AppleProvider
)

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
        client_secret=os.getenv("FACEBOOK_APP_SECRET")
    ),
    "apple": AppleProvider(
        client_id=os.getenv("APPLE_SERVICE_ID"),
        team_id=os.getenv("APPLE_TEAM_ID"),
        key_id=os.getenv("APPLE_KEY_ID"),
        private_key_path=os.getenv("APPLE_PRIVATE_KEY_PATH")
    )
}

auth = SimpleRBAC(database=db, oauth_providers=providers)
```

### Environment Variables

```.env
# Google OAuth
GOOGLE_CLIENT_ID=123456789.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-abc123

# GitHub OAuth
GITHUB_CLIENT_ID=abc123def456
GITHUB_CLIENT_SECRET=1234567890abcdef1234567890abcdef12345678

# Facebook OAuth
FACEBOOK_APP_ID=123456789012345
FACEBOOK_APP_SECRET=abc123def456ghi789jkl012mno345pq

# Apple Sign In
APPLE_SERVICE_ID=com.yourcompany.service
APPLE_TEAM_ID=ABCD123456
APPLE_KEY_ID=ABCD123456
APPLE_PRIVATE_KEY_PATH=/path/to/AuthKey_ABCD123456.p8
```

### Custom Scopes

```python
# Request additional Google scopes
google = GoogleProvider(
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    scopes=["openid", "email", "profile", "https://www.googleapis.com/auth/calendar.readonly"]
)

# Request additional GitHub scopes
github = GitHubProvider(
    client_id=os.getenv("GITHUB_CLIENT_ID"),
    client_secret=os.getenv("GITHUB_CLIENT_SECRET"),
    scopes=["user:email", "read:user", "repo"]
)
```

---

## Complete FastAPI Example

```python
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from outlabs_auth import SimpleRBAC
from outlabs_auth.oauth.providers import GoogleProvider, GitHubProvider
from outlabs_auth.oauth.exceptions import OAuthError
import os

app = FastAPI()

# Initialize OAuth providers
providers = {
    "google": GoogleProvider(
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET")
    ),
    "github": GitHubProvider(
        client_id=os.getenv("GITHUB_CLIENT_ID"),
        client_secret=os.getenv("GITHUB_CLIENT_SECRET")
    )
}

auth = SimpleRBAC(database=db, oauth_providers=providers)

@app.get("/", response_class=HTMLResponse)
async def home():
    """Login page with OAuth buttons"""
    return """
    <html>
        <body>
            <h1>Login</h1>
            <a href="/auth/google/login">
                <button>Sign in with Google</button>
            </a>
            <br>
            <a href="/auth/github/login">
                <button>Sign in with GitHub</button>
            </a>
        </body>
    </html>
    """

@app.get("/auth/{provider}/login")
async def oauth_login(provider: str, request: Request):
    """
    Start OAuth flow.
    Redirects user to provider's authorization page.
    """
    if provider not in providers:
        raise HTTPException(404, f"Provider '{provider}' not configured")

    # Build redirect URI
    redirect_uri = f"{request.base_url}auth/{provider}/callback"

    try:
        # Generate authorization URL
        auth_url = await auth.oauth_service.get_authorization_url(
            provider=provider,
            redirect_uri=str(redirect_uri),
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent")
        )

        # Redirect user to provider
        return RedirectResponse(auth_url)

    except OAuthError as e:
        raise HTTPException(400, str(e))

@app.get("/auth/{provider}/callback")
async def oauth_callback(
    provider: str,
    code: str,
    state: str,
    request: Request
):
    """
    Handle OAuth callback.
    Provider redirects user here after authorization.
    """
    if provider not in providers:
        raise HTTPException(404, f"Provider '{provider}' not configured")

    redirect_uri = f"{request.base_url}auth/{provider}/callback"

    try:
        # Process OAuth callback
        result = await auth.oauth_service.handle_callback(
            provider=provider,
            code=code,
            state=state,
            redirect_uri=str(redirect_uri)
        )

        # User authenticated successfully!
        response = {
            "access_token": result.access_token,
            "refresh_token": result.refresh_token,
            "token_type": "bearer",
            "user": {
                "id": str(result.user.id),
                "email": result.user.email,
                "name": result.user.profile.get("full_name")
            },
            "is_new_user": result.is_new_user,
            "provider": provider
        }

        # Option 1: Return JSON (for SPAs)
        return response

        # Option 2: Redirect to frontend with token (for traditional apps)
        # frontend_url = f"https://yourdomain.com/auth-success?token={result.access_token}"
        # return RedirectResponse(frontend_url)

    except OAuthError as e:
        # Handle OAuth errors (invalid state, code, etc.)
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Authentication failed: {str(e)}")

@app.get("/users/me")
async def get_current_user(user = Depends(auth.deps.require_auth())):
    """Protected endpoint - requires authentication"""
    return {
        "id": str(user.id),
        "email": user.email,
        "auth_methods": user.auth_methods,
        "social_accounts": [
            {
                "provider": sa.provider,
                "connected_at": sa.connected_at
            }
            for sa in user.social_accounts
        ]
    }
```

---

## Testing OAuth Locally

### Development Challenges

1. **HTTPS Required** (especially for Apple)
2. **Public URL Required** (for callbacks)
3. **Environment Variables** (keep secrets safe)

### Solution 1: ngrok

```bash
# Install ngrok
# https://ngrok.com/download

# Start your app
uvicorn main:app --port 3000

# In another terminal, expose via ngrok
ngrok http 3000

# Output:
# Forwarding: https://abc123.ngrok.io -> http://localhost:3000

# Use https://abc123.ngrok.io/auth/google/callback in OAuth settings
```

### Solution 2: localtunnel

```bash
# Install localtunnel
npm install -g localtunnel

# Start your app
uvicorn main:app --port 3000

# In another terminal
lt --port 3000 --subdomain myapp

# Use https://myapp.loca.lt/auth/google/callback
```

### Solution 3: Development OAuth Apps

Create separate OAuth apps for development:

```
Production App:
- Redirect: https://yourdomain.com/auth/google/callback

Development App:
- Redirect: http://localhost:3000/auth/google/callback
- Use different credentials in development
```

---

## Security Best Practices

### 1. Use Environment Variables

**Never commit credentials to git!**

```python
# Good
client_id=os.getenv("GOOGLE_CLIENT_ID")

# Bad
client_id="123456789.apps.googleusercontent.com"  # ❌
```

### 2. Validate State Parameter

OutlabsAuth automatically validates state (CSRF protection). The state is:
- Stored in database before redirect
- Validated on callback
- Single-use (expires after use)
- Includes security metadata (IP, user agent)

### 3. Use PKCE When Available

OutlabsAuth automatically uses PKCE for providers that support it:
- ✅ Google (PKCE)
- ✅ GitHub (PKCE)
- ✅ Apple (PKCE)
- ❌ Facebook (no PKCE support yet)

### 4. Verify Email Before Auto-Linking

```python
# OutlabsAuth only auto-links if:
# 1. Email from OAuth provider is verified
# 2. Email matches existing user
# 3. Existing user doesn't already have that provider linked
```

### 5. Handle Private Relay Emails

```python
# Check for Apple private relay
if email.endswith("@privaterelay.appleid.com"):
    # This is a relay email
    # Emails sent here are forwarded to user
    # Treat as verified email
    pass
```

### 6. Rotate Client Secrets Regularly

- Google: Rotate every 6-12 months
- GitHub: Rotate if compromised
- Facebook: Rotate if suspicious activity
- Apple: P8 keys don't expire, but rotate Team ID if compromised

---

## Troubleshooting

### Issue 1: "redirect_uri_mismatch" Error

**Cause**: Redirect URI in code doesn't match configured URI in provider.

**Solution**:
```python
# Make sure this EXACTLY matches provider configuration
redirect_uri = "http://localhost:3000/auth/google/callback"

# Check for:
# - http vs https
# - localhost vs 127.0.0.1
# - trailing slash
# - port number
```

### Issue 2: State Invalid or Expired

**Cause**: State expired or already used.

**Solutions**:
- State expires in 10 minutes by default
- Don't refresh callback page (single-use state)
- Check database connection (state stored in DB)

### Issue 3: Email Not Provided

**Cause**: User denied email permission or provider doesn't provide email.

**Solution**:
```python
if not user_info.email:
    # Prompt user to provide email manually
    # OR reject login
    raise HTTPException(400, "Email is required")
```

### Issue 4: Apple Name Missing on Second Login

**Cause**: Apple only sends name on first authorization.

**Solution**:
```python
# Store name on first login!
if result.is_new_user and user_info.name:
    await user_service.update_user(
        user.id,
        first_name=user_info.given_name,
        last_name=user_info.family_name
    )
```

### Issue 5: Provider Returns Error

```python
try:
    result = await auth.oauth_service.handle_callback(...)
except ProviderError as e:
    print(f"Provider: {e.provider}")
    print(f"Error: {e.error}")
    print(f"Description: {e.error_description}")
```

**Common Provider Errors**:
- `invalid_grant`: Code expired or already used
- `invalid_client`: Wrong client ID/secret
- `access_denied`: User cancelled authorization

---

## Next Steps

- **[[30-OAuth-Overview|OAuth Overview]]** - How OAuth works
- **[[32-OAuth-Providers|OAuth Providers]]** - Provider comparison
- **[[33-Account-Linking|Account Linking]]** - Link multiple OAuth accounts
- **[[34-OAuth-Security|OAuth Security]]** - Advanced security topics

---

**Previous**: [[30-OAuth-Overview|← OAuth Overview]]
**Next**: [[32-OAuth-Providers|OAuth Providers →]]
