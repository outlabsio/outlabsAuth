# 06. Passwordless and Messaging

Magic links, access codes, invitations, and host-owned delivery (email /
WhatsApp / SMS). The library **mints** secrets and stores **hashes**; your host
**delivers** messages.

Deep specs:

- [`docs/AUTH_EXTENSIONS.md`](../docs/AUTH_EXTENSIONS.md)
- [`docs/WHATSAPP_ACCOUNT_MESSAGING.md`](../docs/WHATSAPP_ACCOUNT_MESSAGING.md)
- [24-User-Invitations.md](./24-User-Invitations.md)

Runnable host recipes: `examples/enterprise_rbac/` (`transactional_mail.py`,
`challenge_messaging.py`).

## Design rule

| Concern | Owner |
|---------|--------|
| When a challenge/invite is needed | Library |
| Plaintext token/code (once) | Returned to host hooks / intents — never leave in NotificationService payloads |
| Templates, Twilio/Meta/SMTP credentials, branding | Host |
| Hash in Postgres + expiry + rate limits | Library |

## Feature flags

```python
auth = EnterpriseRBAC(
    database_url=...,
    secret_key=...,
    enable_invitations=True,       # default True
    enable_magic_links=True,       # default False
    enable_access_codes=True,      # default False
    # magic_link_* / access_code_* TTL and rate-limit knobs — see AuthConfig
)
```

Mount `get_auth_router` so the HTTP endpoints exist (`/auth/magic-link/...`,
`/auth/access-code/...`, `/auth/invite`, …).

## Magic links

1. Client requests a link (`POST …/auth/magic-link/request` with email)
2. Library creates `AuthChallenge` (`magic_link`), returns plaintext once to the
   delivery path
3. Host emails (or otherwise sends) the link
4. Client verifies (`POST …/auth/magic-link/verify`) → JWT session

Rate limits are email-keyed. Challenges are single-use via `used_at`.

## Access codes

Same shape as magic links, with a short numeric code.

Request/verify accept **exactly one** of `email` or `phone` (E.164) when phone
login is enabled in your build. Optional `channel`: `email` | `whatsapp` | `sms`
(phone defaults toward WhatsApp when that path is wired).

| Identifier | Typical challenge type | Requirement |
|------------|------------------------|-------------|
| Email | `access_code` | User exists (enumeration-safe responses still apply) |
| Verified phone | `whatsapp_otp` / `sms_otp` | `phone_verified` on the user |

Hosts without SMS credentials should fail clearly for `delivery_channel=sms`.

## Phone verification

Self-service verify (users router) registers WhatsApp/SMS as a delivery /
login destination:

- `POST …/users/me/phone/request-code`
- `POST …/users/me/phone/verify-code`

Challenge type: `phone_verify`. See the WhatsApp design note for host template
mapping.

## Invitations

Admin invite → mail intent with token → accept set-password flow. Full guide:
[24-User-Invitations.md](./24-User-Invitations.md). SimpleRBAC vs Enterprise
invite body rules: [`docs/AUTH_UI.md`](../docs/AUTH_UI.md).

## Host delivery wiring (enterprise example pattern)

1. **Transactional mail** — invite / reset / access-granted shaped messages via
   `outlabs_auth.mail` providers (`console`, SMTP, etc.)
2. **Challenge messaging** — magic link / access code / WhatsApp / SMS OTP via
   host `AuthChallengeDeliveryIntent` (or equivalent hooks)
3. **NotificationService** — ambient events only (lockouts, notices). **Do not**
   put plaintext OTPs on that path

Environment knobs in the enterprise example (see `.env.example`):

- `OUTLABS_AUTH_MAIL_PROVIDER`, provider credentials, optional recipient override
- Twilio WhatsApp Content SID + SMS from-number for live delivery
- Debug capture endpoints under `/dev/auth/...` for local QA (never in production)

## Checklist

- [ ] Flags enabled only for methods you deliver
- [ ] `get_auth_router` (+ `get_users_router` for phone verify / invites admin)
- [ ] Host mail and/or WhatsApp/SMS providers configured
- [ ] Rate limits and HTTPS verified in staging
- [ ] OutlabsAuth UI pointed at the same prefix if you use its invite/account flows

## Related

- [01-Getting-Started.md](./01-Getting-Started.md)
- [03-Configuration.md](./03-Configuration.md)
- [04-OAuth-and-Social-Login.md](./04-OAuth-and-Social-Login.md)
- [`docs/AUTH_UI.md`](../docs/AUTH_UI.md)
