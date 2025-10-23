# 33. OAuth Account Linking

> **Quick Reference**: Link multiple OAuth providers to a single user account, allowing users to log in with Google, GitHub, Facebook, or Apple interchangeably.

## Overview

Account linking allows users to:
- **Connect multiple auth methods** to one account (e.g., both Google and GitHub)
- **Switch between providers** when logging in
- **Unlink providers** they no longer want to use
- **Never lose access** as long as they have at least one method linked

**Security Benefits**:
- Prevents duplicate accounts for the same person
- Auto-links verified emails safely
- Protects against last-method removal
- Prevents account hijacking

---

## How Account Linking Works

### Automatic vs Manual Linking

OutlabsAuth supports two linking strategies:

| Strategy | When | How | Security Check |
|----------|------|-----|----------------|
| **Auto-Linking** | New OAuth login | Match by verified email | Email must be verified by provider |
| **Manual Linking** | User settings | User initiates while logged in | User must be authenticated |

---

## Account Structure

### User with Multiple Linked Accounts

```
┌─────────────────────────────────────────┐
│ User: john@example.com                  │
│ ID: 507f1f77bcf86cd799439011            │
│ auth_methods: ["PASSWORD", "GOOGLE", "GITHUB"] │
└─────────────────────────────────────────┘
          │
          ├──── SocialAccount (Google)
          │     provider: "google"
          │     provider_user_id: "107353926327..."
          │     email: "john@example.com"
          │
          └──── SocialAccount (GitHub)
                provider: "github"
                provider_user_id: "12345678"
                email: "john@example.com"

User can log in with:
✅ Password + email
✅ Google (john@example.com)
✅ GitHub (john@example.com)
```

---

## Auto-Linking (By Verified Email)

### How It Works

```
1. User logs in with Google
   Email: john@example.com (verified ✅)
   ↓
2. Check: Does user with john@example.com exist?
   Yes → Auto-link Google to existing user
   No → Create new user
   ↓
3. User can now log in with:
   - Original password
   - Google OAuth
```

### Auto-Linking Flow Diagram

```
OAuth Callback
      ↓
Is email verified by provider?
      ├─ No → Create new user (no linking)
      └─ Yes → Search for user by email
                ↓
          User exists?
                ├─ No → Create new user
                └─ Yes → Link provider to existing user
```

### Security Requirements

**Auto-linking ONLY happens when**:
- ✅ Email is verified by the OAuth provider
- ✅ User with that email exists in your system
- ✅ Provider is not already linked to this user
- ✅ Provider account is not linked to another user

**Auto-linking NEVER happens when**:
- ❌ Email is not verified by provider (security risk!)
- ❌ User doesn't exist (creates new account instead)
- ❌ Provider already linked (returns existing link)

### Code Example: Auto-Linking

```python
# This is automatic - no code needed!
# Just initiate OAuth flow normally

@app.get("/auth/{provider}")
async def oauth_login(provider: str):
    """Start OAuth flow - auto-links if email verified."""
    auth_url = await auth.oauth_service.get_authorization_url(
        provider=provider,
        redirect_uri=f"{BASE_URL}/auth/{provider}/callback"
    )
    return RedirectResponse(auth_url)

@app.get("/auth/{provider}/callback")
async def oauth_callback(provider: str, code: str, state: str):
    """Handle OAuth callback - auto-linking happens here."""
    result = await auth.oauth_service.handle_callback(
        provider=provider,
        code=code,
        state=state,
        redirect_uri=f"{BASE_URL}/auth/{provider}/callback"
    )

    if result.linked_account:
        # Linked to existing user!
        print(f"Auto-linked {provider} to existing user {result.user_id}")
    else:
        # New user created
        print(f"Created new user {result.user_id}")

    # Set cookies and redirect
    response = RedirectResponse("/dashboard")
    response.set_cookie("access_token", result.access_token)
    return response
```

---

## Manual Linking (User-Initiated)

### When to Use Manual Linking

**Use manual linking when**:
- User is already logged in and wants to add another provider
- User wants to link a different email address
- Building a "Connected Accounts" settings page
- Email is not verified (safety - let user manually approve)

### Manual Linking Flow

```
1. User is logged in (has JWT)
   ↓
2. User clicks "Connect GitHub" in settings
   ↓
3. Backend generates OAuth URL with user_id
   ↓
4. User authorizes on GitHub
   ↓
5. Callback links GitHub to current user
   ↓
6. User now has multiple login methods
```

### Manual Linking Flow Diagram

```
User Authenticated (JWT)
      ↓
Click "Connect Provider"
      ↓
Generate OAuth URL with user_id
      ↓
User authorizes on provider
      ↓
Callback receives code + state
      ↓
Validate state contains user_id
      ↓
Link provider to user_id
      ↓
Update user.auth_methods
```

### Code Example: Manual Linking

```python
from fastapi import Depends, HTTPException
from outlabs_auth.dependencies import AuthDeps

deps = AuthDeps(auth)

# 1. Generate link URL (user must be authenticated)
@app.get("/settings/link/{provider}")
async def start_link_provider(
    provider: str,
    auth_result = Depends(deps.require_auth())
):
    """
    Start manual linking flow (user is logged in).
    """
    user_id = auth_result["metadata"]["user"]["id"]

    # Generate OAuth URL with user_id embedded in state
    auth_url = await auth.oauth_service.get_authorization_url(
        provider=provider,
        redirect_uri=f"{BASE_URL}/settings/link/{provider}/callback",
        user_id=user_id  # 🔑 Key: Include user_id for manual linking
    )

    return {"authorization_url": auth_url}

# 2. Handle callback (links to existing user)
@app.get("/settings/link/{provider}/callback")
async def link_provider_callback(
    provider: str,
    code: str,
    state: str
):
    """
    Handle OAuth callback for manual linking.
    """
    result = await auth.oauth_service.handle_callback(
        provider=provider,
        code=code,
        state=state,
        redirect_uri=f"{BASE_URL}/settings/link/{provider}/callback"
    )

    # result.linked_account will be True (manual link)
    # result.is_new_user will be False (existing user)

    return {
        "message": f"{provider} linked successfully!",
        "user_id": result.user_id,
        "linked": result.linked_account
    }
```

---

## Unlinking Accounts

### Safety Rules

**You CAN unlink when**:
- ✅ User has a password (can log in with password)
- ✅ User has other OAuth providers linked
- ✅ User has at least ONE other authentication method

**You CANNOT unlink when**:
- ❌ It's the only authentication method (would lock user out!)
- ❌ User has no password and this is the last provider

### Unlinking Flow

```
User has: Password + Google + GitHub
      ↓
Unlink GitHub
      ↓
User now has: Password + Google ✅
Still can log in!

---

User has: Only Google (no password)
      ↓
Try to unlink Google
      ↓
ERROR: CannotUnlinkLastMethodError ❌
User would be locked out!
```

### Code Example: Unlinking

```python
from outlabs_auth.oauth.exceptions import CannotUnlinkLastMethodError

@app.delete("/settings/unlink/{provider}")
async def unlink_provider(
    provider: str,
    auth_result = Depends(deps.require_auth())
):
    """
    Unlink OAuth provider from user account.
    """
    user_id = auth_result["metadata"]["user"]["id"]

    try:
        success = await auth.oauth_service.unlink_provider(
            user_id=user_id,
            provider=provider
        )

        if success:
            return {"message": f"{provider} unlinked successfully"}
        else:
            raise HTTPException(404, f"{provider} not linked to this account")

    except CannotUnlinkLastMethodError:
        raise HTTPException(
            400,
            "Cannot unlink your last authentication method. "
            "Please add a password or link another provider first."
        )
```

---

## List Linked Providers

### View All Connected Accounts

```python
@app.get("/settings/linked-accounts")
async def list_linked_accounts(
    auth_result = Depends(deps.require_auth())
):
    """
    List all OAuth providers linked to user.
    """
    user_id = auth_result["metadata"]["user"]["id"]

    # Get all linked social accounts
    accounts = await auth.oauth_service.list_linked_providers(user_id)

    # Return summary
    return {
        "user_id": user_id,
        "has_password": auth_result["metadata"]["user"]["hashed_password"] is not None,
        "linked_providers": [
            {
                "provider": account.provider,
                "email": account.email,
                "display_name": account.display_name,
                "avatar_url": account.avatar_url,
                "linked_at": account.linked_at,
                "last_used": account.last_used_at
            }
            for account in accounts
        ]
    }
```

**Example Response**:

```json
{
  "user_id": "507f1f77bcf86cd799439011",
  "has_password": true,
  "linked_providers": [
    {
      "provider": "google",
      "email": "john@example.com",
      "display_name": "John Doe",
      "avatar_url": "https://lh3.googleusercontent.com/...",
      "linked_at": "2025-01-10T14:30:00Z",
      "last_used": "2025-01-14T09:15:00Z"
    },
    {
      "provider": "github",
      "email": "john@example.com",
      "display_name": "johndoe",
      "avatar_url": "https://avatars.githubusercontent.com/...",
      "linked_at": "2025-01-12T16:45:00Z",
      "last_used": "2025-01-13T10:20:00Z"
    }
  ]
}
```

---

## Complete Use Cases

### Use Case 1: Settings Page with Account Linking

```python
from fastapi import FastAPI, Depends, HTTPException
from outlabs_auth.dependencies import AuthDeps
from outlabs_auth.oauth.exceptions import (
    ProviderAlreadyLinkedError,
    AccountAlreadyLinkedError,
    CannotUnlinkLastMethodError
)

app = FastAPI()
deps = AuthDeps(auth)

# Connected Accounts Page
@app.get("/settings/connected-accounts")
async def connected_accounts(auth_result = Depends(deps.require_auth())):
    """
    Settings page: show all linked providers and available providers.
    """
    user_id = auth_result["metadata"]["user"]["id"]
    user = auth_result["metadata"]["user"]

    # Get linked accounts
    linked = await auth.oauth_service.list_linked_providers(user_id)
    linked_provider_names = {acc.provider for acc in linked}

    # Available providers
    all_providers = ["google", "github", "facebook", "apple"]
    available = [p for p in all_providers if p not in linked_provider_names]

    return {
        "user": {
            "id": user_id,
            "email": user["email"],
            "has_password": user["hashed_password"] is not None
        },
        "linked_providers": [
            {
                "provider": acc.provider,
                "email": acc.email,
                "display_name": acc.display_name,
                "avatar_url": acc.avatar_url,
                "linked_at": acc.linked_at.isoformat(),
                "last_used": acc.last_used_at.isoformat() if acc.last_used_at else None,
                "can_unlink": user["hashed_password"] is not None or len(linked) > 1
            }
            for acc in linked
        ],
        "available_providers": available
    }

# Link new provider
@app.get("/settings/link/{provider}")
async def link_provider(
    provider: str,
    auth_result = Depends(deps.require_auth())
):
    """
    Generate OAuth URL to link a new provider.
    """
    user_id = auth_result["metadata"]["user"]["id"]

    auth_url = await auth.oauth_service.get_authorization_url(
        provider=provider,
        redirect_uri=f"{BASE_URL}/settings/link/{provider}/callback",
        user_id=user_id  # Manual linking
    )

    return {"authorization_url": auth_url}

@app.get("/settings/link/{provider}/callback")
async def link_callback(provider: str, code: str, state: str):
    """
    Handle OAuth callback for account linking.
    """
    try:
        result = await auth.oauth_service.handle_callback(
            provider=provider,
            code=code,
            state=state,
            redirect_uri=f"{BASE_URL}/settings/link/{provider}/callback"
        )

        # Redirect to settings with success message
        return RedirectResponse(
            "/settings/connected-accounts?linked=success"
        )

    except ProviderAlreadyLinkedError:
        return RedirectResponse(
            "/settings/connected-accounts?error=already_linked"
        )

    except AccountAlreadyLinkedError:
        return RedirectResponse(
            "/settings/connected-accounts?error=account_taken"
        )

# Unlink provider
@app.delete("/settings/unlink/{provider}")
async def unlink(
    provider: str,
    auth_result = Depends(deps.require_auth())
):
    """
    Unlink OAuth provider.
    """
    user_id = auth_result["metadata"]["user"]["id"]

    try:
        await auth.oauth_service.unlink_provider(user_id, provider)
        return {"message": f"{provider} unlinked successfully"}

    except CannotUnlinkLastMethodError:
        raise HTTPException(
            400,
            "Cannot unlink your last login method. Add a password first."
        )
```

---

### Use Case 2: Auto-Linking with Conflict Resolution

```python
@app.get("/auth/{provider}/callback")
async def oauth_callback(provider: str, code: str, state: str):
    """
    OAuth callback with conflict detection.
    """
    try:
        result = await auth.oauth_service.handle_callback(
            provider=provider,
            code=code,
            state=state,
            redirect_uri=f"{BASE_URL}/auth/{provider}/callback"
        )

        # Check if linked vs new user
        if result.linked_account:
            # Auto-linked to existing account
            flash_message = f"Logged in with {provider}. This account is now linked!"
        elif result.is_new_user:
            # New user created
            flash_message = f"Welcome! Your account has been created with {provider}."
        else:
            # Existing OAuth user
            flash_message = f"Welcome back!"

        # Set JWT cookies
        response = RedirectResponse("/dashboard")
        response.set_cookie("access_token", result.access_token, httponly=True)
        response.set_cookie("refresh_token", result.refresh_token, httponly=True)
        response.set_cookie("flash", flash_message)
        return response

    except AccountAlreadyLinkedError as e:
        # This provider account is linked to another user
        return RedirectResponse(
            "/login?error=account_already_linked"
            f"&message={e.message}"
        )
```

---

### Use Case 3: Email Conflict Handling

```python
@app.get("/auth/{provider}/callback")
async def oauth_callback_with_email_conflict(
    provider: str,
    code: str,
    state: str
):
    """
    OAuth callback with email conflict detection.

    Scenario: User has john@example.com with password.
    They log in with GitHub (john@example.com, not verified).
    What happens?
    """
    result = await auth.oauth_service.handle_callback(
        provider=provider,
        code=code,
        state=state,
        redirect_uri=f"{BASE_URL}/auth/{provider}/callback"
    )

    # Check email conflict
    user = await auth.user_service.get_user(result.user_id)

    # Find if email exists in other accounts
    existing_user_by_email = await UserModel.find_one(
        UserModel.email == user.email,
        UserModel.id != user.id  # Different user
    )

    if existing_user_by_email:
        # Email exists for another user
        # This means email was NOT verified by provider
        # (otherwise auto-linking would have happened)

        flash_message = (
            f"An account with {user.email} already exists. "
            "If this is your account, please log in with password "
            "and link your {provider} account in settings."
        )

        # For security, we created a separate account
        # User should merge manually
        response = RedirectResponse("/dashboard")
        response.set_cookie("flash", flash_message, max_age=60)
        response.set_cookie("access_token", result.access_token, httponly=True)
        return response

    # No conflict - proceed normally
    response = RedirectResponse("/dashboard")
    response.set_cookie("access_token", result.access_token, httponly=True)
    return response
```

---

## Security Considerations

### 1. Email Verification is Critical

**Why it matters**:
```
Without email verification:
1. Attacker creates fake Google account with victim@example.com
2. Google doesn't verify this email
3. Attacker logs into your app with OAuth
4. Without verification check: Would link to victim's account! 🚨

With email verification:
1. Attacker creates fake Google account
2. Google doesn't verify email
3. Attacker logs into your app
4. No auto-linking (email not verified) ✅
5. Creates separate account (harmless)
```

**Implementation**:
```python
# OutlabsAuth ONLY auto-links if email_verified = True
if user_info.email_verified:
    # Safe to auto-link by email
    user = await UserModel.find_one(UserModel.email == user_info.email)
else:
    # NOT safe - create separate account
    user = None
```

### 2. Prevent Account Takeover

**Security checks**:

```python
# Check 1: Provider account not linked to another user
existing_social = await SocialAccount.find_one(
    SocialAccount.provider == provider,
    SocialAccount.provider_user_id == user_info.provider_user_id
)
if existing_social and existing_social.user_id != current_user_id:
    raise AccountAlreadyLinkedError()

# Check 2: User doesn't already have this provider
user_provider = await SocialAccount.find_one(
    SocialAccount.user_id == user_id,
    SocialAccount.provider == provider
)
if user_provider:
    raise ProviderAlreadyLinkedError()

# Check 3: Cannot unlink last method
has_password = user.hashed_password is not None
other_providers = await SocialAccount.find(...).count()
if not has_password and other_providers == 0:
    raise CannotUnlinkLastMethodError()
```

### 3. State Parameter (CSRF Protection)

**How it works**:

```python
# 1. Generate state when creating OAuth URL
state = generate_random_string(32)  # Cryptographically secure

# 2. Store state in database
await OAuthState(
    state=state,
    provider=provider,
    user_id=user_id if manual_linking else None,
    expires_at=datetime.utcnow() + timedelta(minutes=10)
).insert()

# 3. Validate state in callback
stored_state = await OAuthState.find_one(
    OAuthState.state == state,
    OAuthState.provider == provider,
    OAuthState.expires_at > datetime.utcnow()
)
if not stored_state:
    raise InvalidStateError()

# 4. Delete state after use (one-time use)
await stored_state.delete()
```

### 4. Token Storage

**Encrypt OAuth tokens at rest**:

```python
# TODO: OutlabsAuth should encrypt tokens before storing
social_account = SocialAccount(
    access_token=encrypt(token_response.access_token),  # Encrypt!
    refresh_token=encrypt(token_response.refresh_token)  # Encrypt!
)

# When using token:
decrypted_token = decrypt(social_account.access_token)
user_info = await provider.get_user_info(decrypted_token)
```

---

## Database Schema

### SocialAccount Model

```python
from beanie import Document
from datetime import datetime
from typing import Optional

class SocialAccount(Document):
    """Links a user to an OAuth provider."""

    # Relationships
    user_id: ObjectId  # Reference to UserModel

    # Provider info
    provider: str  # "google", "github", "facebook", "apple"
    provider_user_id: str  # Provider's user ID

    # Cached user data
    email: str
    email_verified: bool
    display_name: Optional[str]
    avatar_url: Optional[str]

    # OAuth tokens (should be encrypted)
    access_token: Optional[str]
    refresh_token: Optional[str]
    token_expires_at: Optional[datetime]

    # Provider-specific data
    provider_data: dict  # Full profile from provider

    # Metadata
    linked_at: datetime
    last_used_at: Optional[datetime]

    class Settings:
        name = "social_accounts"
        indexes = [
            "user_id",  # Find all accounts for user
            [("provider", 1), ("provider_user_id", 1)],  # Unique constraint
            [("provider", 1), ("email", 1)]  # Find by provider + email
        ]
```

### Example Records

```python
# User with multiple linked accounts
UserModel(
    id=ObjectId("507f1f77bcf86cd799439011"),
    email="john@example.com",
    hashed_password="$argon2id$...",  # Has password
    auth_methods=["PASSWORD", "GOOGLE", "GITHUB"]
)

SocialAccount(
    user_id=ObjectId("507f1f77bcf86cd799439011"),
    provider="google",
    provider_user_id="107353926327...",
    email="john@example.com",
    email_verified=True,
    display_name="John Doe",
    avatar_url="https://lh3.googleusercontent.com/...",
    linked_at=datetime(2025, 1, 10, 14, 30)
)

SocialAccount(
    user_id=ObjectId("507f1f77bcf86cd799439011"),
    provider="github",
    provider_user_id="12345678",
    email="john@example.com",
    email_verified=True,
    display_name="johndoe",
    avatar_url="https://avatars.githubusercontent.com/...",
    linked_at=datetime(2025, 1, 12, 16, 45)
)
```

---

## Common Scenarios

### Scenario 1: User Creates Account with Password, Later Links Google

```
Day 1:
  User registers: john@example.com + password
  auth_methods: ["PASSWORD"]

Day 5:
  User goes to Settings → Connect Google
  Clicks "Connect Google"
  Approves on Google
  ✅ Google linked successfully
  auth_methods: ["PASSWORD", "GOOGLE"]

Now user can log in with:
  ✅ Email + password
  ✅ Google OAuth
```

### Scenario 2: User Signs Up with Google, Later Adds Password

```
Day 1:
  User signs up with Google
  auth_methods: ["GOOGLE"]
  hashed_password: null (no password)

Day 3:
  User goes to Settings → Set Password
  Sets password
  ✅ Password created
  auth_methods: ["GOOGLE", "PASSWORD"]
  hashed_password: "$argon2id$..."

Now user can log in with:
  ✅ Google OAuth
  ✅ Email + password
```

### Scenario 3: User with Google Tries to Sign Up with GitHub (Same Email)

```
Existing account:
  email: john@example.com
  auth_methods: ["GOOGLE"]

User clicks "Sign in with GitHub":
  GitHub returns: john@example.com (verified ✅)

Auto-linking happens:
  ✅ GitHub linked to existing account
  auth_methods: ["GOOGLE", "GITHUB"]

Result: User didn't create duplicate account!
```

### Scenario 4: User Tries to Unlink Last Method

```
Current state:
  auth_methods: ["GOOGLE"]
  hashed_password: null

User tries to unlink Google:
  ❌ CannotUnlinkLastMethodError

Error message:
  "Cannot unlink your last authentication method.
   Please add a password or link another provider first."
```

### Scenario 5: Email Exists But Not Verified

```
Existing account:
  email: john@example.com
  auth_methods: ["PASSWORD"]

User logs in with Facebook:
  Facebook returns: john@example.com (verified=False ⚠️)

Auto-linking DOES NOT happen:
  Security risk! Email not verified by Facebook.

Result:
  ✅ Creates NEW user (separate account)
  User should manually merge in settings
```

---

## Error Handling

### Common Errors

```python
from outlabs_auth.oauth.exceptions import (
    ProviderAlreadyLinkedError,
    AccountAlreadyLinkedError,
    CannotUnlinkLastMethodError,
    InvalidStateError,
    EmailNotVerifiedError
)

try:
    result = await auth.oauth_service.handle_callback(...)
except InvalidStateError:
    # State parameter invalid or expired
    # Possible CSRF attack or user took too long
    return {"error": "OAuth session expired. Please try again."}

except ProviderAlreadyLinkedError:
    # User already has this provider linked
    return {"error": "You've already linked this provider."}

except AccountAlreadyLinkedError as e:
    # This provider account is linked to another user
    return {
        "error": "account_taken",
        "message": f"This {e.provider} account is already linked to another user."
    }

except CannotUnlinkLastMethodError:
    # Trying to unlink last authentication method
    return {
        "error": "last_method",
        "message": "Please add a password or link another provider first."
    }
```

---

## Frontend Integration

### React Example: Connected Accounts Page

```jsx
import { useState, useEffect } from 'react';

function ConnectedAccounts() {
  const [accounts, setAccounts] = useState(null);

  useEffect(() => {
    fetch('/settings/connected-accounts', {
      headers: { 'Authorization': `Bearer ${accessToken}` }
    })
      .then(res => res.json())
      .then(data => setAccounts(data));
  }, []);

  const linkProvider = async (provider) => {
    // Get OAuth URL
    const res = await fetch(`/settings/link/${provider}`, {
      headers: { 'Authorization': `Bearer ${accessToken}` }
    });
    const { authorization_url } = await res.json();

    // Redirect to OAuth provider
    window.location.href = authorization_url;
  };

  const unlinkProvider = async (provider) => {
    if (!confirm(`Unlink ${provider}?`)) return;

    await fetch(`/settings/unlink/${provider}`, {
      method: 'DELETE',
      headers: { 'Authorization': `Bearer ${accessToken}` }
    });

    // Refresh accounts
    window.location.reload();
  };

  if (!accounts) return <div>Loading...</div>;

  return (
    <div>
      <h2>Connected Accounts</h2>

      {/* Linked Providers */}
      <div>
        <h3>Linked Providers</h3>
        {accounts.linked_providers.map(acc => (
          <div key={acc.provider} className="provider-card">
            <img src={acc.avatar_url} alt={acc.display_name} />
            <div>
              <strong>{acc.provider}</strong>
              <p>{acc.email}</p>
              <small>Linked on {new Date(acc.linked_at).toLocaleDateString()}</small>
            </div>
            {acc.can_unlink && (
              <button onClick={() => unlinkProvider(acc.provider)}>
                Unlink
              </button>
            )}
          </div>
        ))}
      </div>

      {/* Available Providers */}
      <div>
        <h3>Add Provider</h3>
        {accounts.available_providers.map(provider => (
          <button key={provider} onClick={() => linkProvider(provider)}>
            Connect {provider}
          </button>
        ))}
      </div>

      {/* Password Status */}
      <div>
        <h3>Password</h3>
        {accounts.user.has_password ? (
          <p>✅ Password set</p>
        ) : (
          <button onClick={() => navigate('/settings/set-password')}>
            Set Password
          </button>
        )}
      </div>
    </div>
  );
}
```

---

## Best Practices

### 1. Always Auto-Link Verified Emails

**DO**:
```python
if user_info.email_verified:
    # Safe to auto-link
    user = await UserModel.find_one(UserModel.email == user_info.email)
```

**DON'T**:
```python
# INSECURE! Email not verified!
user = await UserModel.find_one(UserModel.email == user_info.email)
```

### 2. Require At Least One Auth Method

**DO**:
```python
# Check before unlinking
has_password = user.hashed_password is not None
other_providers = await SocialAccount.find(...).count()
if not has_password and other_providers == 0:
    raise CannotUnlinkLastMethodError()
```

**DON'T**:
```python
# Bad - could lock user out!
await social_account.delete()
```

### 3. Show Clear UI for Linked Accounts

**DO**:
- Show all linked providers with icons
- Indicate which provider was used for current session
- Show if password is set
- Disable unlink button for last method

**DON'T**:
- Hide linked accounts in obscure settings
- Allow unlinking last method without warning

### 4. Handle Email Conflicts Gracefully

**DO**:
```python
# If email exists but not verified, create separate account
# Show message: "Email already in use. Log in and link in settings."
```

**DON'T**:
```python
# Don't auto-link unverified emails!
# Don't show error - creates separate account instead
```

### 5. Encrypt OAuth Tokens

**DO**:
```python
# Encrypt before storing
access_token=encrypt(token_response.access_token)
```

**DON'T**:
```python
# Plain text in database!
access_token=token_response.access_token
```

---

## Summary

| Feature | Auto-Linking | Manual Linking | Unlinking |
|---------|-------------|----------------|-----------|
| **When** | OAuth login (new user) | User settings (authenticated) | User settings |
| **Security** | Email must be verified | User must be authenticated | Must have other auth method |
| **Use Case** | Prevent duplicate accounts | Add more login options | Remove unwanted providers |
| **User Action** | Logs in with OAuth | Clicks "Connect Provider" | Clicks "Unlink" |
| **Result** | One account, multiple logins | More flexibility | Fewer login options |

**Key Takeaways**:
- ✅ Auto-link by verified email to prevent duplicates
- ✅ Manual linking for user-controlled connections
- ✅ Always require at least one authentication method
- ✅ Encrypt OAuth tokens at rest
- ✅ Use state parameter for CSRF protection

---

## Next Steps

- **[31. OAuth Setup →](./31-OAuth-Setup.md)** - Set up OAuth providers
- **[32. OAuth Provider Comparison →](./32-OAuth-Providers.md)** - Compare Google, GitHub, Facebook, Apple
- **[22. JWT Authentication →](./22-JWT-Authentication.md)** - Understand JWT tokens returned after OAuth

---

## Further Reading

### Account Linking Security
- [OAuth 2.0 Account Linking Best Practices](https://tools.ietf.org/html/draft-ietf-oauth-security-topics)
- [OWASP Account Takeover Prevention](https://owasp.org/www-community/attacks/Credential_stuffing)

### Implementation Guides
- [Google Account Linking](https://developers.google.com/identity/account-linking)
- [Auth0 Account Linking](https://auth0.com/docs/users/user-account-linking)
