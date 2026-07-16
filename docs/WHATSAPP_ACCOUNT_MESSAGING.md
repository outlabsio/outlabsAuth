# WhatsApp Account Messaging

**Status**: Design accepted for Phase A/B; Phase C deferred  
**Date**: 2026-07-16  
**Related**: [DD-025](./DESIGN_DECISIONS.md#dd-025-no-built-in-emailsms-service), [DD-058](./DESIGN_DECISIONS.md#dd-058-whatsapp-as-host-owned-delivery-channel-for-auth-challenges), transactional mail (`outlabs_auth/mail/`), notification channels (`outlabs_auth/services/channels/whatsapp.py`)

## Purpose

Describe how host FastAPI apps can deliver OutlabsAuth account messages (access codes, magic links, and optionally invites/resets) over WhatsApp **without** the library owning Meta/Twilio credentials, templates, or branding.

Contract (same as email):

1. **Library** decides *when* a message is needed and supplies a typed payload.
2. **Host app** decides *whether* to send email, WhatsApp, both, or neither; owns providers, templates, and credentials.

## Two messaging layers (do not mix for OTPs)

| Layer | Secrets in payload? | Host owns templates/providers? | Fit for WhatsApp OTP? |
|---|---|---|---|
| Transactional mail (`outlabs_auth/mail/`) | Yes (invite/reset tokens) | Yes | Email-shaped; recipient may include optional `phone` for host dual-channel |
| Challenge delivery intents / `on_after_*` hooks | Yes (plain token/code) | Yes | **Correct path for OTP / magic link** |
| `NotificationService` + `WhatsAppChannel` | **No** — events omit plain codes | Yes | Ambient alerts only (lockouts, login notices). **Not** OTP delivery alone |

```text
Invite / forgot / reset / access-granted
  → MailIntent → host composer → host mail provider

Magic link / access code
  → AuthChallenge (hash in DB) + plain secret to hook / AuthChallengeDeliveryIntent
  → host messaging service (email and/or WhatsApp template)
  → NotificationService may emit "requested" WITHOUT the secret

WhatsAppChannel (Twilio)
  → optional sideband for lifecycle/security events
  → host message_builder + host phone lookup
```

Putting plain OTP/magic-link secrets into `NotificationService.emit` is rejected: queues/webhooks would amplify leakage. Keep challenge secrets on the transactional/hook path.

## User phone as registered delivery destination

`User` already has:

- `phone` (optional)
- `phone_verified` (flag; **no verification flow yet**)

Product model for Phase A/B:

- **Email remains the login identifier** (request endpoints stay email-keyed).
- Phone/WhatsApp is an optional **delivery destination** registered on the account (self-service or admin).
- Do **not** require WhatsApp as a login identity in this pass.

WhatsApp production concerns stay **host-owned**: Meta-approved templates (or Twilio Content SIDs), E.164 numbers, opt-in / sandbox rules.

## Payload fields hosts need for WhatsApp templates

`AuthChallengeDeliveryIntent` (and mail recipients that include phone) expose:

| Field | Use in templates |
|---|---|
| `recipient.user_id` | Host DB lookup / audit correlation |
| `recipient.email` | Identity; fallback or dual-channel email |
| `recipient.phone` | WhatsApp `to` (E.164) when set |
| `recipient.phone_verified` | Host policy (e.g. only send if verified) |
| `recipient.first_name` / `last_name` | Personalization variables |
| `challenge_type` | `magic_link` or `access_code` → choose template |
| `secret` | OTP digits or magic-link token (map to template variables; never log in production) |
| `expires_at` | “expires in N minutes” copy |
| `redirect_url` | Deep link / continue URL when applicable |
| `request_base_url` | Absolute link builders when host needs API origin |
| `metadata` | Host-specific extras |

Example host WhatsApp template variables for access codes:

```text
content_sid = HX...   # host-approved Twilio Content SID
content_variables = {"1": "{{secret}}", "2": "{{expires_minutes}}"}
to = "whatsapp:+15551234567"
```

The library never selects Meta vs Twilio and never embeds template copy.

## Phases

### Phase A — Host-only (works with hooks today)

Override (or wrap) on the host:

- `on_after_access_code_requested`
- `on_after_magic_link_requested`
- Optionally invite / forgot-password for dual-channel

Look up `user.phone`, build template variables, send via Twilio/Meta. Invite/reset can remain on `ComposedAuthMailService`.

The enterprise example demonstrates a **console WhatsApp** path for access codes when `user.phone` is set (no real Twilio credentials required for local demos).

### Phase B — First-class challenge delivery intents (library)

Shipped as:

- `outlabs_auth/messaging/` — `AuthChallengeDeliveryIntent`, `DeliveryRecipient`, `MessageDeliveryResult`
- Optional `transactional_messaging_service` on `OutlabsAuth` / `UserService`
- Default passwordless hooks call `send_magic_link_delivery` / `send_access_code_delivery` when that service is configured; otherwise remain no-ops for hosts that only override hooks
- `MailRecipient.phone` / `phone_verified` optional fields for dual-channel invite/reset composers

Host implements something like:

```python
class HostChallengeMessagingService:
    async def send_auth_challenge(self, intent: AuthChallengeDeliveryIntent) -> MessageDeliveryResult:
        # Compose email and/or WhatsApp Content API payload; library stays vendor-agnostic.
        ...
```

### Phase C — Host wire-up (partially shipped)

Shipped:

- `UserUpdateRequest.phone` + `update_user_fields(..., phone_provided=...)` — changing phone clears `phone_verified`
- `phone_verified` on `UserResponse`
- Sidecar Account + admin user profile fields for WhatsApp phone (E.164)
- Enterprise host Twilio WhatsApp Content API path when `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`, and `TWILIO_WHATSAPP_ACCESS_CODE_CONTENT_SID` are set (otherwise console spike)

Still deferred:

- Phone verification OTP flow that sets `phone_verified`
- Request-by-phone / WhatsApp as login identifier
- New `AuthChallengeType` values (`SMS_OTP`, `WHATSAPP_OTP`)
- Channel query params and per-channel rate limits

Roadmap/AUTH_EXTENSIONS language about multi-channel OTP as a login method is aspirational relative to the live enum (`magic_link` / `access_code` only).

## What not to do

- Treat existing `WhatsAppChannel` as the OTP delivery path without also changing emit payloads.
- Bake Twilio/Meta into `ComposedAuthMailService`.
- Force every host to support WhatsApp — keep it optional via injection / hook overrides.
- Put plain challenge secrets on notification event buses.

## Example wiring pointers

- Enterprise mail (email intents): `examples/enterprise_rbac/transactional_mail.py`
- Enterprise challenge messaging (console spike + optional Twilio): `examples/enterprise_rbac/challenge_messaging.py`
- Optional Twilio ambient channel (non-secret events): `outlabs_auth/services/channels/whatsapp.py`

### Enterprise Twilio env vars

| Variable | Purpose |
|---|---|
| `TWILIO_ACCOUNT_SID` | Twilio account |
| `TWILIO_AUTH_TOKEN` | Twilio auth token |
| `TWILIO_WHATSAPP_FROM` | Sender (`whatsapp:+...` or `+...`) |
| `TWILIO_WHATSAPP_ACCESS_CODE_CONTENT_SID` | Approved Content SID for access codes |
| `TWILIO_WHATSAPP_REQUIRE_VERIFIED` | When `true`, skip send unless `phone_verified` |
