# User Invitations

> **Handbook** · Onboarding by email.  
> Part of the [OutlabsAuth Handbook](./README.md). Related:
> [Passwordless & Messaging](./06-Passwordless-and-Messaging.md),
> [User Status](./48-User-Status-System.md),
> [User Management API](./23-User-Management-API.md).

Invite users by email without setting a password for them. They open a
token-based link, choose a password, and the account activates
(`INVITED` → `ACTIVE`) with a JWT session.

| Concern | Owner |
|---------|--------|
| Mint invite token, hash + expiry in Postgres | Library |
| Branding, email provider, copy | Host (`on_after_invite` / mail intent) |
| Accept link + set password | Client → `POST …/auth/accept-invite` |

Invite tokens are SHA-256 hashed at rest. Default expiry: 7 days
(`invite_token_expire_days`). Works with SimpleRBAC and EnterpriseRBAC.

---

## Endpoints

Mount `get_auth_router` and `get_users_router` (examples use `/v1`):

| Action | Method + path | Auth |
|--------|---------------|------|
| Create invite | `POST /v1/auth/invite` | `user:create` |
| Accept invite | `POST /v1/auth/accept-invite` | Public |
| Resend invite | `POST /v1/users/{user_id}/resend-invite` | `user:update` |

Create/resend return `UserResponse` — the plaintext token is **not** in the JSON
body; it goes to the host delivery hook. Accept returns `LoginResponse`.

---

## Configuration

```python
auth = SimpleRBAC(
    database_url=...,
    secret_key=...,
    enable_invitations=True,       # default — surfaced on GET /auth/config
    invite_token_expire_days=7,
)
```

`GET /v1/auth/config` → `features.invitations` for UI show/hide.

> **Caveat:** `enable_invitations=False` currently hides the feature in config /
> UI discovery. Invite HTTP routes remain registered — treat the flag as a
> product switch.

---

## Flow

```
Admin POST /v1/auth/invite
  → User INVITED (no password)
  → Host gets plaintext token once (mail intent / on_after_invite)
  → Host emails accept URL + token
User POST /v1/auth/accept-invite { token, new_password }
  → ACTIVE + LoginResponse (access + refresh)
```

On accept: password stored, `email_verified=true`, invite token fields cleared.

---

## Invite payload (`InviteUserRequest`)

| Field | Required | Notes |
|-------|----------|-------|
| `email` | Yes | |
| `first_name` / `last_name` | No | |
| `is_superuser` | No | Only current superusers may set |
| `role_ids` | No | Without `entity_id`: direct roles. With `entity_id`: roles on that membership |
| `entity_id` | No | Enterprise membership (needs membership service) |

**Accept** (`AcceptInviteRequest`): `token`, `new_password` (length policy enforced).

**Resend:** only for `status=invited`; invalidates the previous token.

---

## Host delivery

Library mints tokens; **you** brand and send. Recommended path:
`outlabs_auth.mail` (`ComposedAuthMailService`, composers, SMTP / SendGrid /
Mailgun / Postmark / Resend / webhook providers). Runnable:
`examples/enterprise_rbac/transactional_mail.py`.

Also: `on_after_invite` hook if you already own delivery outside the mail
helpers. See [Passwordless & Messaging](./06-Passwordless-and-Messaging.md).

---

## Related

- [User Status](./48-User-Status-System.md)
- [User Management API](./23-User-Management-API.md)
- [Passwordless & Messaging](./06-Passwordless-and-Messaging.md)
- [OutlabsAuth UI](../docs/AUTH_UI.md) — invite UX for Simple vs Enterprise
