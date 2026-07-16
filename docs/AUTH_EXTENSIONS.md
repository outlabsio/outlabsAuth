# OutlabsAuth Library - Authentication Extensions & Notifications

**Applies to**: both SimpleRBAC and EnterpriseRBAC

This document covers the authentication methods that sit alongside email/password, and
the notification system that delivers their messages:

- **OAuth / social login** — Google, Facebook, Apple, GitHub
- **Passwordless** — magic links and email access codes
- **Notifications** — a pluggable channel system for auth-related messages

All of it is optional. The library works with email/password alone, and every feature
below is off until you turn it on.

**Related documentation**:
- [API_DESIGN.md](API_DESIGN.md) - core authentication patterns and examples
- [DEPENDENCY_PATTERNS.md](DEPENDENCY_PATTERNS.md) - `AuthDeps` in depth
- [LIBRARY_ARCHITECTURE.md](LIBRARY_ARCHITECTURE.md) - technical architecture
- [SECURITY.md](SECURITY.md) - security hardening

---

## Table of Contents

1. [Overview](#overview)
2. [Authentication Methods Architecture](#authentication-methods-architecture)
3. [OAuth/Social Login Integration](#oauthsocial-login-integration)
4. [Alternative Authentication Methods](#alternative-authentication-methods)
5. [Notification System Design](#notification-system-design)
6. [Status](#status)
7. [Security Considerations](#security-considerations)
8. [Configuration Examples](#configuration-examples)
9. [Testing Strategies](#testing-strategies)

---

## Overview

### Design Principles

1. **Optional complexity**: email/password works without any of this.
2. **No vendor lock-in**: the library does not depend on a specific email or SMS
   provider. Bring your own, or use one of the bundled channels.
3. **Host-owned delivery**: the library mints tokens and codes; it hands them to a
   service you supply for delivery. It never assumes an SMTP server exists.
4. **Secure by default**: state validation, PKCE, nonce checks, single-use tokens,
   hashed challenge storage, and rate limiting are on by default where they apply.
5. **Universal**: everything here works identically with SimpleRBAC and EnterpriseRBAC.

---

## Authentication Methods Architecture

### Users and social accounts

The user model is `outlabs_auth/models/sql/user.py`, class `User`. A linked social
identity is a separate row rather than an embedded document:
`outlabs_auth/models/sql/social_account.py`, class `SocialAccount`, related to `User`
via `user.social_accounts`.

Selected `SocialAccount` columns:

- `user_id`, `provider`, `provider_user_id` — the identity link
- `provider_email`, `provider_email_verified`, `provider_username`
- `access_token`, `refresh_token`, `token_expires_at` — only populated when
  `store_oauth_provider_tokens=True`
- `display_name`, `avatar_url`, `profile_url`
- `last_login_at`, `token_refreshed_at`

Because a social account is its own table, a user can link several providers, and
unlinking is a row delete rather than a rewrite of the user document.

### Authentication challenges

Temporary challenges — magic links, access codes — live in
`outlabs_auth/models/sql/auth_challenge.py`, class `AuthChallenge`.

Columns of note:

- `user_id`, `challenge_type`, `recipient`
- `token_hash` — **only a hash is stored**. The plaintext token exists exactly once,
  in the return value of the method that generated it, so a database leak does not
  yield usable magic links.
- `expires_at`, `used_at` — `used_at` is what makes a challenge single-use
- `redirect_url`
- `requested_ip_address`, `requested_user_agent`

`AuthChallengeType` (`outlabs_auth/models/sql/enums.py`) is:

```python
MAGIC_LINK = "magic_link"
ACCESS_CODE = "access_code"
WHATSAPP_OTP = "whatsapp_otp"
SMS_OTP = "sms_otp"
PHONE_VERIFY = "phone_verify"
```

Expired challenges are cleaned up by the `token_cleanup` worker
(`outlabs_auth/workers/token_cleanup.py`).

---

## OAuth/Social Login Integration

### Provider abstraction

The base class is `OAuthProvider` in `outlabs_auth/oauth/provider.py`. Its abstract
surface:

- `get_authorization_url(redirect_uri, state=None, use_pkce=True, use_nonce=None, **extra)`
  — returns an `OAuthAuthorizationURL` (`url`, `state`). PKCE is on by default.
- `exchange_code(...)` (abstract) — authorization code to tokens
- `get_user_info(...)` (abstract) — fetch the profile
- `refresh_token(...)` — refresh an access token
- `revoke_token(...)` — revoke, where the provider supports it

Providers are constructed as `Provider(client_id, client_secret, scopes=None)`, with
`scopes` falling back to the provider's `default_scopes`.

Data types are exported from `outlabs_auth.oauth`: `OAuthTokenResponse`,
`OAuthUserInfo`, `OAuthAuthorizationURL`, `OAuthCallbackResult`.

The package also defines a full exception hierarchy — `OAuthError`,
`InvalidStateError`, `InvalidCodeError`, `ProviderError`, `AccountLinkError`,
`ProviderNotConfiguredError`, `EmailNotVerifiedError`, `AccountAlreadyLinkedError`,
`ProviderAlreadyLinkedError`, `CannotUnlinkLastMethodError`, `TokenRefreshError`,
`InvalidNonceError`, `PKCEValidationError` — so a caller can distinguish "this user
already linked that provider" from "the provider is down".

### Pre-built providers

Concrete classes live in `outlabs_auth/oauth/providers/`:

| Class | Module |
|---|---|
| `GoogleProvider` | `oauth/providers/google.py` |
| `FacebookProvider` | `oauth/providers/facebook.py` |
| `AppleProvider` | `oauth/providers/apple.py` |
| `GitHubProvider` | `oauth/providers/github.py` |

`outlabs_auth/oauth/provider_factories.py` additionally exposes client factories used
by the OAuth router: `get_google_client`, `get_facebook_client`, `get_github_client`,
`get_microsoft_client`, `get_discord_client`.

```python
from outlabs_auth.oauth.providers import get_google_client

google_client = get_google_client(
    client_id=os.environ["GOOGLE_CLIENT_ID"],
    client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
)
```

### Mounting the OAuth routes

There is no `auth.setup_oauth_routes(...)`. OAuth is mounted like every other part of
the library — with a router factory, one per provider.

```python
from outlabs_auth.routers.oauth import get_oauth_router

app.include_router(
    get_oauth_router(
        oauth_client=google_client,
        auth=auth,
        state_secret=os.environ["OAUTH_STATE_SECRET"],
        prefix="/auth/google",
        tags=["OAuth"],
        associate_by_email=True,        # link to an existing user with the same email
        is_verified_by_default=False,   # trust the provider's email verification?
        require_existing_user=False,    # True = invite-only, reject unknown emails
        success_redirect_url="https://app.example.com/welcome",
        error_redirect_url="https://app.example.com/login?error=1",
        cookie_secure=True,
    )
)
```

Note `get_oauth_router` is imported from `outlabs_auth.routers.oauth` — unlike the
core factories, it is not re-exported from `outlabs_auth.routers`.

Parameters worth understanding before you ship:

- **`require_existing_user=True`** rejects unknown emails, which is how you get
  invite-only OAuth with no self-registration.
- **`associate_by_email=True`** links a provider identity to an existing local account
  with the same email. Only enable this for providers whose email verification you
  trust — otherwise it is an account-takeover path.
- **`state_secret`** signs the OAuth state parameter. It is required.

To let an already-authenticated user link an additional provider, mount
`get_oauth_associate_router` from `outlabs_auth.routers.oauth_associate`.

### Provider token storage

By default, provider access and refresh tokens are **not** persisted. To keep them —
so you can call the provider's API on the user's behalf later — opt in, and supply an
encryption key:

```python
auth = SimpleRBAC(
    database_url=DATABASE_URL,
    secret_key=SECRET_KEY,
    store_oauth_provider_tokens=True,
    oauth_token_encryption_key=os.environ["OAUTH_TOKEN_ENCRYPTION_KEY"],  # Fernet key
)
```

The key is validated at construction: enabling storage without one is a
`ConfigurationError` rather than a silent plaintext write.

### OAuth security helpers

`outlabs_auth/oauth/security.py` and `outlabs_auth/oauth/state.py` implement the state
parameter, PKCE, and nonce handling. `outlabs_auth/models/sql/oauth_state.py` backs
state persistence, with `outlabs_auth/routers/oauth_state_store.py` as the store.

---

## Alternative Authentication Methods

Both passwordless methods are off by default and are implemented on `AuthService`.
Both follow the same shape: **the library mints the token and stores only its hash;
you deliver it.**

### Magic links

```python
auth = SimpleRBAC(
    database_url=DATABASE_URL,
    secret_key=SECRET_KEY,
    enable_magic_links=True,
    magic_link_expire_minutes=15,
    magic_link_request_rate_limit_max=3,
    magic_link_request_rate_limit_window_seconds=300,
)
```

The service methods:

```python
# Generate — returns the plaintext token. Only its hash is stored.
token: str = await auth.auth_service.generate_magic_link_token(
    session,
    user,
    redirect_url="https://app.example.com/dashboard",
    ip_address=request.client.host,
    user_agent=request.headers.get("user-agent"),
)

# Verify — single use. Returns (User, TokenPair).
user, tokens = await auth.auth_service.verify_magic_link(
    session,
    token,
    device_name="iPhone",
    ip_address=request.client.host,
)
```

`verify_magic_link` raises `TokenInvalidError` when the token is unknown, expired, or
already used.

### Access codes

Short numeric codes sent to a verified channel.

```python
auth = SimpleRBAC(
    database_url=DATABASE_URL,
    secret_key=SECRET_KEY,
    enable_access_codes=True,
    access_code_expire_minutes=10,
    access_code_length=6,
    access_code_request_rate_limit_max=3,
    access_code_request_rate_limit_window_seconds=300,
    access_code_verify_rate_limit_max=10,
    access_code_verify_rate_limit_window_seconds=300,
)
```

```python
code: str = await auth.auth_service.generate_access_code(session, user)
user, tokens = await auth.auth_service.verify_access_code(session, email, code)
```

Access codes are rate limited on **both** sides — requesting and verifying. The verify
limit is what stops a 6-digit code from being brute-forced; do not raise it casually.

### The bundled routes

`get_auth_router` already exposes these, so in most cases you mount the router rather
than call the service:

```
POST /register              POST /magic-link/request
POST /login                 POST /magic-link/verify
POST /refresh               POST /access-code/request
POST /logout                POST /access-code/verify
POST /forgot-password       POST /invite
POST /reset-password        POST /accept-invite
GET  /config
```

The magic-link and access-code routes are only wired when their feature flag is on.

### Delivering the message

The router needs a way to send what it generated. That is
`transactional_messaging_service` — a host-owned service for challenge delivery
(email, WhatsApp), whose types are in `outlabs_auth/messaging/types.py`:
`AuthChallengeDeliveryIntent`, `DeliveryRecipient`, `MessageDeliveryResult`.

For the transactional auth mails (invite, forgot-password, reset confirmation, access
granted), the equivalent is `transactional_mail_service`, with
`ComposedAuthMailService` (`outlabs_auth/mail/service.py`) as the bundled
implementation:

```python
from outlabs_auth.mail.providers import SMTPMailProvider

auth = SimpleRBAC(
    database_url=DATABASE_URL,
    secret_key=SECRET_KEY,
    transactional_mail_service=ComposedAuthMailService(
        composer=my_composer,
        provider=SMTPMailProvider(...),
    ),
)
```

Bundled mail providers (`outlabs_auth/mail/providers.py`): `SMTPMailProvider`,
`SendGridMailProvider`, `MailgunMailProvider`, all implementing
`TransactionalMailProvider`.

Delivery results are values, not exceptions — `MailDeliveryResult.queued()`,
`.failed()`, `.skipped_result()` — so a bounced invite does not take down the request
that triggered it.

---

## Notification System Design

Distinct from transactional mail: notifications are **fire-and-forget events** about
auth activity (someone logged in, an account locked), not messages a user is waiting
on.

### Core abstraction

`NotificationChannel` (`outlabs_auth/services/channels/base.py`) is the interface:

```python
class NotificationChannel(ABC):
    def __init__(self, enabled: bool = True, event_filter: Optional[List[str]] = None):
        ...

    @abstractmethod
    async def send(self, event: Dict[str, Any]) -> None:
        ...
```

`event_filter` lets a channel subscribe to a subset of event types, so an SMS channel
can take only the security-relevant ones.

`NotificationService` (`outlabs_auth/services/notification.py`) fans an event out to
its channels:

```python
class NotificationService:
    def __init__(
        self,
        enabled: bool = False,
        channels: Optional[List[NotificationChannel]] = None,
        observability: Optional["ObservabilityService"] = None,
    ):
        ...
```

Note `enabled` defaults to `False` — constructing the service is not enough to turn
notifications on.

Emitting is fire-and-forget by design:

```python
await auth.notification_service.emit(
    event_type="user.login",
    data={"user_id": str(user.id), "email": user.email},
    metadata={"ip": request.client.host},
)
```

`emit` returns immediately and does not wait for delivery. **Notification failures
never affect auth operations** — a dead webhook cannot fail a login.

Event types include `user.login`, `user.login_failed`, `user.locked`, `user.unlocked`,
`user.logout`, `user.created`, `user.email_verified`, `user.status_changed`,
`user.deleted`. See the `emit` docstring for the current list.

### Bundled channels

In `outlabs_auth/services/channels/`:

| Channel | Module | Purpose |
|---|---|---|
| `RabbitMQChannel` | `rabbitmq.py` | Publish events to a queue |
| `SMTPChannel` | `smtp.py` | Email via SMTP |
| `SendGridChannel` | `sendgrid.py` | Email via the SendGrid API |
| `WebhookChannel` | `webhook.py` | POST events to an HTTP endpoint |
| `TwilioChannel` | `twilio.py` | SMS |
| `TelegramChannel` | `telegram.py` | Telegram Bot API |
| `WhatsAppChannel` | `whatsapp.py` | WhatsApp via Twilio |

Each import is guarded: a channel whose optional dependency is missing imports as
`None`, with a matching `<NAME>_AVAILABLE` flag, so the package installs without
pulling in every provider SDK.

### Wiring it up

```python
from outlabs_auth.services.notification import NotificationService
from outlabs_auth.services.channels import WebhookChannel

notification_service = NotificationService(
    enabled=True,
    channels=[
        WebhookChannel(url="https://api.internal/notifications", secret=WEBHOOK_SECRET),
    ],
)

auth = SimpleRBAC(
    database_url=DATABASE_URL,
    secret_key=SECRET_KEY,
    enable_notifications=True,
    notification_service=notification_service,
)
```

Channels can be managed after construction with `add_channel()`, `remove_channel()`,
and inspected via `active_channels`.

---

## Status

Implemented and shipping:

- **OAuth / social login** — Google, Facebook, Apple, GitHub providers; Microsoft and
  Discord client factories; state, PKCE, and nonce validation; account linking and
  association; optional encrypted provider-token storage.
- **Passwordless** — magic links and email access codes, with hashed single-use
  challenges and rate limiting on request and verify.
- **Notifications** — `NotificationService` plus RabbitMQ, SMTP, SendGrid, Webhook,
  Twilio, Telegram, and WhatsApp channels.
- **Transactional auth mail** — invite, forgot-password, reset confirmation, and
  access-granted flows, with SMTP, SendGrid, and Mailgun providers.

Present in the schema but without a full flow built on them: the `WHATSAPP_OTP`,
`SMS_OTP`, and `PHONE_VERIFY` challenge types exist in `AuthChallengeType`, and
`verify_phone_verify_code` exists on `AuthService`, but these are not surfaced by
`get_auth_router` the way magic links and access codes are.

Not implemented — do not plan around these:

- **MFA / TOTP** and backup codes
- **WebAuthn / passkeys**

---

## Security Considerations

### OAuth security

1. **State parameter**: always validated; `state_secret` is a required argument.
2. **PKCE**: implemented in `outlabs_auth/oauth/security.py`.
3. **Token storage**: off by default. Turning it on without
   `oauth_token_encryption_key` is a construction error, not a plaintext write.
4. **Scope limitation**: request minimal scopes via the client factory's `scopes`.
5. **Account takeover**: `associate_by_email=True` links a provider identity to a
   local account by matching email. Enable it only for providers whose email
   verification you trust, and consider `is_verified_by_default=False` so a provider's
   unverified email cannot mark a local account verified.

### Magic link security

1. **Single use**: enforced by `used_at` on the challenge row.
2. **Hashed at rest**: only `token_hash` is stored; the plaintext is returned once.
3. **Time limited**: `magic_link_expire_minutes`, default 15.
4. **Rate limited**: `magic_link_request_rate_limit_max` per window, default 3 per 300s.
5. **Secure random**: tokens come from `secrets`, not `random`.
6. **HTTPS only**: enforce it at your edge — the library cannot.

### Access code security

1. **Rate limited on both sides**: requesting *and* verifying. The verify limit
   (default 10 per 300s) is the control that makes a 6-digit code safe. Raising it
   materially weakens the mechanism.
2. **Length**: `access_code_length`, default 6.
3. **Short expiry**: `access_code_expire_minutes`, default 10.
4. **Single use**: same `used_at` mechanism as magic links.
5. **Channel ownership**: verify the recipient owns the address before treating a code
   sent there as proof of identity.

### Notification security

Notifications carry auth event data to external systems. Filter with `event_filter`
so a channel only receives what it needs, and remember that `emit` swallows failures —
a channel that is silently down produces no error at the auth layer. Monitor delivery
at the channel, not through auth.

---

## Configuration Examples

### Minimal (email/password only)

```python
auth = SimpleRBAC(database_url=DATABASE_URL, secret_key=SECRET_KEY)
```

### With notifications

```python
from outlabs_auth.services.notification import NotificationService
from outlabs_auth.services.channels import WebhookChannel

auth = SimpleRBAC(
    database_url=DATABASE_URL,
    secret_key=SECRET_KEY,
    enable_notifications=True,
    notification_service=NotificationService(
        enabled=True,
        channels=[WebhookChannel(url="https://api.internal/notifications", secret=WEBHOOK_SECRET)],
    ),
)
```

### With OAuth providers

```python
import os
from outlabs_auth.oauth.providers import get_google_client, get_github_client
from outlabs_auth.routers.oauth import get_oauth_router

auth = SimpleRBAC(database_url=DATABASE_URL, secret_key=SECRET_KEY)
auth.prime_fastapi_routing()

state_secret = os.environ["OAUTH_STATE_SECRET"]

for name, client in {
    "google": get_google_client(
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
    ),
    "github": get_github_client(
        client_id=os.environ["GITHUB_CLIENT_ID"],
        client_secret=os.environ["GITHUB_CLIENT_SECRET"],
    ),
}.items():
    app.include_router(
        get_oauth_router(
            oauth_client=client,
            auth=auth,
            state_secret=state_secret,
            prefix=f"/auth/{name}",
            tags=["OAuth"],
        )
    )
```

### With magic links and access codes

```python
auth = SimpleRBAC(
    database_url=DATABASE_URL,
    secret_key=SECRET_KEY,
    enable_magic_links=True,
    magic_link_expire_minutes=15,
    enable_access_codes=True,
    access_code_expire_minutes=10,
    access_code_length=6,
    transactional_messaging_service=my_delivery_service,
)
auth.prime_fastapi_routing()

# The bundled router already exposes the request/verify routes for both.
app.include_router(get_auth_router(auth, prefix="/auth", tags=["Auth"]))
```

### Testing configuration

Supply a capturing delivery service instead of a real one, and assert on what it was
handed:

The contract is a single method, `async send_auth_challenge(intent)`, returning a
`MessageDeliveryResult`. The library only reads `.accepted` off the result.

```python
from outlabs_auth.messaging.types import MessageDeliveryResult


class CapturingMessagingService:
    def __init__(self):
        self.sent = []

    async def send_auth_challenge(self, intent) -> MessageDeliveryResult:
        self.sent.append(intent)
        return MessageDeliveryResult.queued(provider="capture")


capturing = CapturingMessagingService()
auth = SimpleRBAC(
    database_url=TEST_DATABASE_URL,
    secret_key="test-secret-key-at-least-32-characters-long",
    enable_magic_links=True,
    transactional_messaging_service=capturing,
)

# Assert on what the library handed the delivery layer:
#   capturing.sent[0].secret        -> the plaintext token
#   capturing.sent[0].challenge_type -> "magic_link"
```

---

## Testing Strategies

### Provider unit tests

`get_authorization_url` returns an `OAuthAuthorizationURL` (fields: `url`, `state`),
not a bare string:

```python
def test_google_authorization_url():
    provider = GoogleProvider(client_id="cid", client_secret="secret")
    result = provider.get_authorization_url(
        redirect_uri="http://localhost/callback",
        state="state123",
    )
    assert result.state == "state123"
    assert "client_id=cid" in result.url
```

Omit `state` and one is generated for you and handed back on `result.state` — store it
and compare it on the callback. PKCE is on by default (`use_pkce=True`).

### Magic link round trip

Passwordless flows touch the `auth_challenges` table, so these are integration tests
against a real PostgreSQL database.

```python
@pytest.mark.asyncio
async def test_magic_link_round_trip(auth, test_user):
    async with auth.get_session() as session:
        token = await auth.auth_service.generate_magic_link_token(session, test_user)
        await session.commit()

        user, tokens = await auth.auth_service.verify_magic_link(session, token)
        await session.commit()

        assert user.id == test_user.id
        assert tokens.access_token


@pytest.mark.asyncio
async def test_magic_link_is_single_use(auth, test_user):
    async with auth.get_session() as session:
        token = await auth.auth_service.generate_magic_link_token(session, test_user)
        await session.commit()

        await auth.auth_service.verify_magic_link(session, token)
        await session.commit()

        with pytest.raises(TokenInvalidError):
            await auth.auth_service.verify_magic_link(session, token)
```

### Notification tests

Because `emit` is fire-and-forget, a test that asserts on delivery must await the
background task rather than checking immediately after the call. Prefer testing a
channel's `send()` directly:

```python
@pytest.mark.asyncio
async def test_webhook_channel_posts_event(httpx_mock):
    channel = WebhookChannel(url="https://example.test/hook")
    await channel.send({"event_type": "user.login", "data": {"user_id": "abc"}})
    assert httpx_mock.get_requests()
```

See [TESTING_GUIDE.md](TESTING_GUIDE.md) for the full harness.
