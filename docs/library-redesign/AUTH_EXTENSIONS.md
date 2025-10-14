# OutlabsAuth Library - Authentication Extensions & Notifications

**Version**: 1.0
**Date**: 2025-01-14
**Status**: Post-v1.0 Extensions Design
**Applies to**: Both SimpleRBAC and EnterpriseRBAC

---

## Table of Contents

1. [Overview](#overview)
2. [Authentication Methods Architecture](#authentication-methods-architecture)
3. [OAuth/Social Login Integration](#oauthsocial-login-integration)
4. [Alternative Authentication Methods](#alternative-authentication-methods)
5. [Notification System Design](#notification-system-design)
6. [Implementation Roadmap](#implementation-roadmap)
7. [Security Considerations](#security-considerations)
8. [Configuration Examples](#configuration-examples)
9. [Testing Strategies](#testing-strategies)
10. [Migration Guide](#migration-guide)

---

## Overview

This document outlines the design for extending OutlabsAuth beyond basic email/password authentication to support:

- **OAuth/Social Login** (Google, Facebook, Apple, etc.) - v1.2
- **Passwordless Methods** (Magic links, OTP via SMS/WhatsApp/Telegram) - v1.3
- **Notification Handling** (Pluggable system for all auth-related communications) - v1.1

**Important**: All extensions are **optional** and work with both **SimpleRBAC** and **EnterpriseRBAC** presets. The v1.0 core library works perfectly fine with just email/password authentication.

### Design Principles

1. **Optional Complexity**: Basic email/password works without any of these features
2. **No Vendor Lock-in**: Library doesn't depend on specific email/SMS providers
3. **Pluggable Architecture**: Bring your own notification service
4. **Secure by Default**: State validation, CSRF protection, rate limiting
5. **Minimal Dependencies**: OAuth support doesn't require heavy libraries
6. **Universal**: Extensions work identically with both SimpleRBAC and EnterpriseRBAC

### Extension Timeline

- **v1.0** (Core): SimpleRBAC + EnterpriseRBAC
- **v1.1** (Week 8-9): Notification system
- **v1.2** (Week 10-12): OAuth/social login
- **v1.3** (Week 13-14): Passwordless authentication
- **v1.4** (Week 15-16): Advanced features (MFA, WebAuthn)

---

## Authentication Methods Architecture

### Core Model Changes

```python
# outlabs_auth/models/user.py
from enum import Enum
from typing import List, Optional
from datetime import datetime

class AuthMethod(str, Enum):
    PASSWORD = "password"
    GOOGLE = "google"
    FACEBOOK = "facebook"
    APPLE = "apple"
    MAGIC_LINK = "magic_link"
    SMS_OTP = "sms_otp"
    WHATSAPP_OTP = "whatsapp_otp"
    TELEGRAM_OTP = "telegram_otp"

class SocialAccount(BaseModel):
    """Linked social account"""
    provider: str  # "google", "facebook", "apple"
    provider_user_id: str
    email: Optional[str]
    display_name: Optional[str]
    avatar_url: Optional[str]
    connected_at: datetime
    last_used: Optional[datetime]
    is_primary: bool = False
    raw_data: Dict[str, Any] = Field(default_factory=dict)

class UserModel(BaseDocument):
    # Core fields
    email: EmailStr
    hashed_password: Optional[str] = None  # Optional for social-only users

    # Authentication
    auth_methods: List[AuthMethod] = Field(default_factory=list)
    social_accounts: List[SocialAccount] = Field(default_factory=list)
    primary_auth_method: AuthMethod = AuthMethod.PASSWORD

    # Security
    requires_password_setup: bool = False  # For social users who need password
    mfa_enabled: bool = False
    mfa_methods: List[str] = Field(default_factory=list)
```

### Authentication Challenge System

For temporary auth challenges (magic links, OTPs):

```python
# outlabs_auth/models/auth_challenge.py
class ChallengeType(str, Enum):
    MAGIC_LINK = "magic_link"
    EMAIL_OTP = "email_otp"
    SMS_OTP = "sms_otp"
    WHATSAPP_OTP = "whatsapp_otp"
    PASSWORD_RESET = "password_reset"
    EMAIL_VERIFICATION = "email_verification"

class AuthChallenge(BaseDocument):
    """Temporary authentication challenges"""
    user_id: str
    challenge_type: ChallengeType
    code: str  # Random token or OTP code
    recipient: str  # Email or phone number
    expires_at: datetime
    attempts: int = 0
    max_attempts: int = 3
    used: bool = False
    used_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Settings:
        indexes = [
            IndexModel([("code", 1)], unique=True),
            IndexModel([("expires_at", 1)], expireAfterSeconds=0),
        ]
```

---

## OAuth/Social Login Integration

### Provider Abstraction

```python
# outlabs_auth/providers/base.py
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from pydantic import BaseModel

class OAuthToken(BaseModel):
    access_token: str
    token_type: str
    expires_in: Optional[int]
    refresh_token: Optional[str]
    scope: Optional[str]
    id_token: Optional[str]  # For OIDC providers

class OAuthUserInfo(BaseModel):
    id: str  # Provider's user ID
    email: Optional[str]
    email_verified: Optional[bool]
    name: Optional[str]
    given_name: Optional[str]
    family_name: Optional[str]
    picture: Optional[str]
    locale: Optional[str]
    raw_data: Dict[str, Any]

class OAuthProvider(ABC):
    """Base OAuth provider interface"""

    name: str
    display_name: str

    @abstractmethod
    def get_authorization_url(
        self,
        state: str,
        redirect_uri: str,
        scopes: Optional[List[str]] = None
    ) -> str:
        """Generate authorization URL"""
        pass

    @abstractmethod
    async def exchange_code(
        self,
        code: str,
        redirect_uri: str
    ) -> OAuthToken:
        """Exchange authorization code for tokens"""
        pass

    @abstractmethod
    async def get_user_info(self, token: OAuthToken) -> OAuthUserInfo:
        """Get user information from provider"""
        pass

    @abstractmethod
    async def revoke_token(self, token: str) -> bool:
        """Revoke access token (optional)"""
        return True
```

### Pre-built Providers

```python
# outlabs_auth/providers/google.py
import httpx
from urllib.parse import urlencode

class GoogleProvider(OAuthProvider):
    name = "google"
    display_name = "Google"

    AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret

    def get_authorization_url(
        self,
        state: str,
        redirect_uri: str,
        scopes: Optional[List[str]] = None
    ) -> str:
        scopes = scopes or ["openid", "email", "profile"]
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes),
            "state": state,
            "access_type": "offline",  # For refresh token
            "prompt": "consent"
        }
        return f"{self.AUTHORIZE_URL}?{urlencode(params)}"

    async def exchange_code(
        self,
        code: str,
        redirect_uri: str
    ) -> OAuthToken:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "code": code,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code"
                }
            )
            response.raise_for_status()
            return OAuthToken(**response.json())

    async def get_user_info(self, token: OAuthToken) -> OAuthUserInfo:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.USERINFO_URL,
                headers={"Authorization": f"Bearer {token.access_token}"}
            )
            response.raise_for_status()
            data = response.json()

            return OAuthUserInfo(
                id=data["id"],
                email=data.get("email"),
                email_verified=data.get("verified_email"),
                name=data.get("name"),
                given_name=data.get("given_name"),
                family_name=data.get("family_name"),
                picture=data.get("picture"),
                locale=data.get("locale"),
                raw_data=data
            )

# Similar implementations for:
# - FacebookProvider
# - AppleProvider (more complex due to JWT)
# - GitHubProvider
# - MicrosoftProvider
```

### OAuth Service Integration

```python
# outlabs_auth/services/oauth.py
class OAuthService:
    """Handle OAuth authentication flows"""

    def __init__(
        self,
        user_service: UserService,
        providers: Dict[str, OAuthProvider],
        notification_handler: NotificationHandler
    ):
        self.user_service = user_service
        self.providers = providers
        self.notification_handler = notification_handler

    async def authenticate_with_provider(
        self,
        provider_name: str,
        code: str,
        redirect_uri: str,
        create_if_not_exists: bool = True,
        auto_link_by_email: bool = True
    ) -> Tuple[UserModel, TokenPair, bool]:  # (user, tokens, is_new_user)
        """
        Complete OAuth authentication flow
        Returns user, tokens, and whether this is a new user
        """
        provider = self.providers.get(provider_name)
        if not provider:
            raise ValueError(f"Unknown provider: {provider_name}")

        # Exchange code for tokens
        oauth_token = await provider.exchange_code(code, redirect_uri)

        # Get user info
        user_info = await provider.get_user_info(oauth_token)

        # Find existing user
        user = await self._find_existing_user(
            provider_name,
            user_info,
            auto_link_by_email
        )

        is_new_user = False

        if user:
            # Update existing user
            await self._update_social_account(user, provider_name, user_info)
        elif create_if_not_exists:
            # Create new user
            user = await self._create_user_from_oauth(provider_name, user_info)
            is_new_user = True
        else:
            raise UserNotFoundError(
                f"No user found for {provider_name} account"
            )

        # Generate tokens
        tokens = await self.user_service.generate_tokens(user)

        # Send notification if new user
        if is_new_user:
            await self.notification_handler.send(NotificationEvent(
                type="welcome_oauth",
                recipient=user.email,
                data={
                    "provider": provider.display_name,
                    "name": user.profile.full_name,
                    "requires_password": user.requires_password_setup
                }
            ))

        return user, tokens, is_new_user

    async def link_provider_to_user(
        self,
        user_id: str,
        provider_name: str,
        code: str,
        redirect_uri: str
    ) -> SocialAccount:
        """Link a social account to existing user"""
        # Implementation...
        pass

    async def unlink_provider(
        self,
        user_id: str,
        provider_name: str
    ) -> bool:
        """Unlink a social account"""
        # Verify user has alternative auth method
        # Remove social account
        pass
```

---

## Alternative Authentication Methods

### Magic Link Implementation

```python
# outlabs_auth/services/passwordless.py
class PasswordlessService:
    """Handle magic links and OTP authentication"""

    def __init__(
        self,
        database: Any,
        notification_handler: NotificationHandler,
        config: PasswordlessConfig
    ):
        self.database = database
        self.notification_handler = notification_handler
        self.config = config

    async def send_magic_link(
        self,
        email: str,
        redirect_url: Optional[str] = None
    ) -> bool:
        """Send magic link to email"""
        # Find or create user
        user = await self.user_service.find_by_email(email)
        if not user and self.config.create_users_on_first_login:
            user = await self.user_service.create_user(
                email=email,
                auth_methods=[AuthMethod.MAGIC_LINK]
            )
        elif not user:
            # Don't reveal if user exists
            return True

        # Create challenge
        challenge = await self.create_challenge(
            user_id=str(user.id),
            challenge_type=ChallengeType.MAGIC_LINK,
            recipient=email,
            expires_in_minutes=self.config.magic_link_expiry_minutes
        )

        # Build magic link
        magic_link = f"{self.config.app_url}/auth/magic/{challenge.code}"
        if redirect_url:
            magic_link += f"?redirect={redirect_url}"

        # Send notification
        await self.notification_handler.send(NotificationEvent(
            type="magic_link",
            recipient=email,
            data={
                "link": magic_link,
                "expires_in_minutes": self.config.magic_link_expiry_minutes,
                "user_name": user.profile.first_name
            }
        ))

        return True

    async def verify_magic_link(self, code: str) -> TokenPair:
        """Verify magic link and generate tokens"""
        challenge = await self.get_valid_challenge(
            code,
            ChallengeType.MAGIC_LINK
        )

        # Mark as used
        await self.mark_challenge_used(challenge)

        # Generate tokens
        user = await self.user_service.get(challenge.user_id)
        return await self.user_service.generate_tokens(user)

    async def send_otp(
        self,
        recipient: str,
        channel: str = "email"  # email, sms, whatsapp, telegram
    ) -> bool:
        """Send OTP code"""
        # Determine challenge type based on channel
        challenge_type = {
            "email": ChallengeType.EMAIL_OTP,
            "sms": ChallengeType.SMS_OTP,
            "whatsapp": ChallengeType.WHATSAPP_OTP,
        }[channel]

        # Generate 6-digit code
        code = ''.join(random.choices('0123456789', k=6))

        # Create challenge
        challenge = await self.create_challenge(
            user_id=str(user.id),
            challenge_type=challenge_type,
            recipient=recipient,
            code=code,
            expires_in_minutes=self.config.otp_expiry_minutes
        )

        # Send notification
        await self.notification_handler.send(NotificationEvent(
            type=f"otp_{channel}",
            recipient=recipient,
            data={
                "code": code,
                "expires_in_minutes": self.config.otp_expiry_minutes
            }
        ))

        return True

    async def verify_otp(
        self,
        recipient: str,
        code: str,
        channel: str = "email"
    ) -> TokenPair:
        """Verify OTP and generate tokens"""
        # Implementation similar to magic link
        pass
```

---

## Notification System Design

### Core Abstraction

```python
# outlabs_auth/notifications/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime

class NotificationEvent(BaseModel):
    """Standard notification event"""
    type: str  # Type of notification
    recipient: str  # Email, phone, or user ID
    data: Dict[str, Any]  # Event-specific data
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    priority: str = "normal"  # low, normal, high

    class Config:
        # Define standard data contracts per type
        schema_extra = {
            "examples": {
                "magic_link": {
                    "type": "magic_link",
                    "recipient": "user@example.com",
                    "data": {
                        "link": "https://app.com/auth/magic/abc123",
                        "expires_in_minutes": 15,
                        "user_name": "John"
                    }
                },
                "otp_sms": {
                    "type": "otp_sms",
                    "recipient": "+1234567890",
                    "data": {
                        "code": "123456",
                        "expires_in_minutes": 5
                    }
                }
            }
        }

class NotificationHandler(ABC):
    """Base notification handler interface"""

    @abstractmethod
    async def send(self, event: NotificationEvent) -> bool:
        """Send notification"""
        pass

    async def validate_event(self, event: NotificationEvent) -> bool:
        """Optional validation before sending"""
        return True

class NoOpHandler(NotificationHandler):
    """No-operation handler for testing"""
    async def send(self, event: NotificationEvent) -> bool:
        return True
```

### Pre-built Handlers

```python
# outlabs_auth/notifications/handlers.py
import httpx
import json
from typing import Optional, Dict, Any

class WebhookHandler(NotificationHandler):
    """Send notifications via webhook"""

    def __init__(
        self,
        webhook_url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 30,
        retry_count: int = 3
    ):
        self.webhook_url = webhook_url
        self.headers = headers or {}
        self.timeout = timeout
        self.retry_count = retry_count

    async def send(self, event: NotificationEvent) -> bool:
        payload = event.dict()

        for attempt in range(self.retry_count):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        self.webhook_url,
                        json=payload,
                        headers=self.headers
                    )
                    response.raise_for_status()
                    return True
            except Exception as e:
                if attempt == self.retry_count - 1:
                    raise
                await asyncio.sleep(2 ** attempt)  # Exponential backoff

        return False

class QueueHandler(NotificationHandler):
    """Push notifications to a message queue"""

    def __init__(self, queue_client: Any, queue_name: str = "auth_notifications"):
        self.queue_client = queue_client
        self.queue_name = queue_name

    async def send(self, event: NotificationEvent) -> bool:
        message = event.dict()
        await self.queue_client.publish(self.queue_name, message)
        return True

class CallbackHandler(NotificationHandler):
    """Direct callback function handler"""

    def __init__(self, callback: Callable[[NotificationEvent], Awaitable[bool]]):
        self.callback = callback

    async def send(self, event: NotificationEvent) -> bool:
        return await self.callback(event)

class CompositeHandler(NotificationHandler):
    """Combine multiple handlers"""

    def __init__(self, handlers: List[NotificationHandler]):
        self.handlers = handlers

    async def send(self, event: NotificationEvent) -> bool:
        results = await asyncio.gather(
            *[handler.send(event) for handler in self.handlers],
            return_exceptions=True
        )
        return all(r for r in results if not isinstance(r, Exception))

class FilteredHandler(NotificationHandler):
    """Apply filters to notifications"""

    def __init__(
        self,
        handler: NotificationHandler,
        filter_func: Callable[[NotificationEvent], bool]
    ):
        self.handler = handler
        self.filter_func = filter_func

    async def send(self, event: NotificationEvent) -> bool:
        if self.filter_func(event):
            return await self.handler.send(event)
        return True
```

### Integration with Auth System

```python
# outlabs_auth/presets/simple.py
class SimpleRBAC(OutlabsAuth):
    def __init__(
        self,
        database: Any,
        config: Optional[SimpleConfig] = None,
        notification_handler: Optional[NotificationHandler] = None,
        oauth_providers: Optional[Dict[str, OAuthProvider]] = None
    ):
        super().__init__(database, config)

        # Set notification handler (default to NoOp)
        self.notification_handler = notification_handler or NoOpHandler()

        # Initialize OAuth if providers given
        if oauth_providers:
            self.oauth_service = OAuthService(
                user_service=self.user_service,
                providers=oauth_providers,
                notification_handler=self.notification_handler
            )

        # Initialize passwordless if configured
        if config.enable_magic_links or config.enable_otp:
            self.passwordless_service = PasswordlessService(
                database=database,
                notification_handler=self.notification_handler,
                config=config.passwordless_config
            )
```

---

## Implementation Roadmap

### Phase 1: Core Authentication (v1.0) ✅
**Status**: Completed
- Basic email/password
- JWT tokens
- No external dependencies

### Phase 2: Notification System (v1.1)
**Timeline**: Week 8-9 (2 weeks)
**Goal**: Pluggable notification abstraction

**Deliverables**:
- NotificationHandler abstraction
- Pre-built handlers (Webhook, Queue, Callback)
- Integration with existing auth flows
- Notification event types
- Testing utilities
- Documentation and examples

### Phase 3: OAuth Support (v1.2)
**Timeline**: Week 10-12 (3 weeks)
**Goal**: Social login integration

**Deliverables**:
- Provider abstraction
- Google, Facebook, Apple providers
- Account linking logic
- Auto-registration flow
- OAuth routes helper
- Security (state validation, PKCE)

### Phase 4: Passwordless Auth (v1.3)
**Timeline**: Week 13-14 (2 weeks)
**Goal**: Magic links and OTP

**Deliverables**:
- AuthChallenge model
- Magic links
- OTP support (Email, SMS)
- Challenge management system
- Rate limiting

### Phase 5: Advanced Features (v1.4)
**Timeline**: Week 15-16 (2 weeks)
**Goal**: MFA, WebAuthn, advanced channels

**Deliverables**:
- WhatsApp/Telegram OTP
- MFA support (TOTP)
- Backup codes
- Device tracking
- WebAuthn research

---

## Security Considerations

### OAuth Security

1. **State Parameter**: Always validate state to prevent CSRF
2. **PKCE**: Implement for public clients
3. **Token Storage**: Never log tokens
4. **Scope Limitation**: Request minimal scopes
5. **Account Takeover**: Verify email ownership before linking

**See**: [SECURITY.md](SECURITY.md#oauth-security) for detailed OAuth security guidelines

### Magic Link Security

1. **Single Use**: Links expire after first use
2. **Time Limited**: Short expiry (15 minutes default)
3. **Rate Limiting**: Prevent abuse
4. **Secure Random**: Use cryptographically secure tokens
5. **HTTPS Only**: Enforce secure transport

**See**: [SECURITY.md](SECURITY.md#magic-link-security) for detailed magic link security guidelines

### OTP Security

1. **Rate Limiting**: Max attempts per code
2. **Code Complexity**: 6+ digits minimum
3. **Expiry**: 5-10 minute window
4. **Channel Verification**: Verify phone/email ownership
5. **Replay Protection**: Prevent code reuse

**See**: [SECURITY.md](SECURITY.md#otp-security) for detailed OTP security guidelines

---

## Configuration Examples

### Minimal Setup (Email/Password Only)

```python
auth = SimpleRBAC(database=db)
# No notifications, no OAuth, just basic auth
```

### With Internal Notification API

```python
notification_handler = WebhookHandler(
    webhook_url="https://api.internal/notifications/send",
    headers={"X-API-Key": os.getenv("INTERNAL_API_KEY")}
)

auth = SimpleRBAC(
    database=db,
    notification_handler=notification_handler
)
```

### With OAuth Providers

```python
oauth_providers = {
    "google": GoogleProvider(
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET")
    ),
    "facebook": FacebookProvider(
        client_id=os.getenv("FACEBOOK_CLIENT_ID"),
        client_secret=os.getenv("FACEBOOK_CLIENT_SECRET")
    )
}

auth = SimpleRBAC(
    database=db,
    notification_handler=notification_handler,
    oauth_providers=oauth_providers
)

# Auto-register OAuth routes
auth.setup_oauth_routes(app, base_url="https://myapp.com")
```

### With Magic Links and OTP

```python
passwordless_config = PasswordlessConfig(
    enable_magic_links=True,
    enable_otp=True,
    magic_link_expiry_minutes=15,
    otp_expiry_minutes=5,
    otp_length=6
)

auth = SimpleRBAC(
    database=db,
    notification_handler=notification_handler,
    config=SimpleConfig(passwordless_config=passwordless_config)
)

# Routes
@app.post("/auth/magic-link")
async def send_magic_link(email: str):
    await auth.passwordless_service.send_magic_link(email)
    return {"message": "Check your email"}

@app.post("/auth/magic-link/verify")
async def verify_magic_link(code: str):
    tokens = await auth.passwordless_service.verify_magic_link(code)
    return tokens
```

### Multi-Channel Notifications

```python
# Different handlers for different notification types
email_handler = WebhookHandler("https://email-service.internal")
sms_handler = WebhookHandler("https://sms-gateway.internal")

# Route notifications based on type
def route_notification(event: NotificationEvent) -> NotificationHandler:
    if event.type.startswith("otp_sms"):
        return sms_handler
    return email_handler

notification_handler = CallbackHandler(
    lambda event: route_notification(event).send(event)
)
```

### Testing Configuration

```python
# For tests, capture notifications instead of sending
captured_notifications = []

test_handler = CallbackHandler(
    lambda event: captured_notifications.append(event)
)

auth = SimpleRBAC(
    database=test_db,
    notification_handler=test_handler
)

# In tests, assert on captured_notifications
```

---

## Testing Strategies

### Unit Tests for Providers

```python
@pytest.mark.asyncio
async def test_google_provider():
    provider = GoogleProvider("client_id", "client_secret")

    # Test authorization URL generation
    url = provider.get_authorization_url("state123", "http://localhost/callback")
    assert "state=state123" in url
    assert "client_id=client_id" in url
```

### Integration Tests for OAuth Flow

```python
@pytest.mark.asyncio
async def test_oauth_complete_flow(auth, mock_google_provider):
    # Mock provider responses
    mock_google_provider.get_user_info.return_value = OAuthUserInfo(
        id="google123",
        email="user@gmail.com",
        name="Test User"
    )

    # Complete OAuth flow
    user, tokens, is_new = await auth.oauth_service.authenticate_with_provider(
        "google", "auth_code_123", "http://localhost/callback"
    )

    assert user.email == "user@gmail.com"
    assert AuthMethod.GOOGLE in user.auth_methods
    assert is_new == True
```

### Testing Notifications

```python
@pytest.mark.asyncio
async def test_magic_link_sends_notification(auth, notification_capture):
    # Send magic link
    await auth.passwordless_service.send_magic_link("test@example.com")

    # Check notification was sent
    assert len(notification_capture) == 1
    event = notification_capture[0]
    assert event.type == "magic_link"
    assert event.recipient == "test@example.com"
    assert "link" in event.data
```

**See**: [TESTING_GUIDE.md](TESTING_GUIDE.md) for comprehensive testing patterns

---

## Migration Guide

### From Hardcoded Email Sending

```python
# BEFORE: Email sending in auth logic
async def send_verification_email(user):
    msg = create_email_message(user.email, "Verify your email")
    await smtp_client.send(msg)

# AFTER: Notification handler
async def handle_notification(event: NotificationEvent):
    if event.type == "email_verification":
        msg = create_email_message(
            event.recipient,
            "Verify your email",
            event.data["link"]
        )
        await smtp_client.send(msg)
    return True

auth = SimpleRBAC(
    database=db,
    notification_handler=CallbackHandler(handle_notification)
)
```

### Adding OAuth to Existing App

```python
# 1. Add OAuth configuration
oauth_providers = {
    "google": GoogleProvider(...)
}

# 2. Update auth initialization
auth = SimpleRBAC(
    database=db,
    notification_handler=existing_handler,
    oauth_providers=oauth_providers
)

# 3. Register OAuth routes
auth.setup_oauth_routes(app, base_url="https://myapp.com")

# 4. Update frontend to show social login buttons
```

---

## Future Enhancements

### Near Term (v1.5)
- WebAuthn/Passkeys support
- Session management improvements
- Enhanced account linking strategies
- Notification templates system

### Medium Term (v2.0)
- Plugin system for custom providers
- GraphQL subscription support
- Real-time auth events
- Advanced MFA flows

### Long Term
- Biometric authentication
- Decentralized identity support
- Zero-knowledge proofs

---

## Related Documentation

- **[SECURITY.md](SECURITY.md)** - Security best practices for OAuth, magic links, and OTP
- **[TESTING_GUIDE.md](TESTING_GUIDE.md)** - Testing patterns for authentication extensions
- **[API_DESIGN.md](API_DESIGN.md)** - Configuration examples and code patterns
- **[DESIGN_DECISIONS.md](DESIGN_DECISIONS.md)** - DD-022 through DD-027 (extension decisions)
- **[IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md)** - Phases 7-10 (post-v1.0)

---

**Last Updated**: 2025-01-14
**Next Review**: After Phase 7 (v1.1) implementation
**Status**: Design phase - ready for v1.1 implementation
