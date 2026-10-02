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

`enable_invitations=False` is an enforcement switch: invite, accept-invite, and
resend-invite endpoints return 404 in addition to hiding the feature in config
and UI discovery.

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
| `entity_id` | No | Enterprise membership (needs membership service); the first membership roots the invitee at that tree |

Enterprise scope rules (DD-056, DD-061): the inviter must hold every permission the
roles carry; a **system-wide** role in `role_ids` without `entity_id` makes the
invitee a global actor, so only a global inviter (superuser or system-wide role
holder) may grant it (403 with `details.system_wide_role_ids`). Without
`entity_id`, `role_ids` are direct grants: a role outside the inviter's scope
answers 404 (no account is created), containment is checked where each role
takes effect, and an org-scoped role must belong to the invitee's root. A
tenant-scoped inviter's invitee is rooted at the inviter's own root so it stays
visible to that tenant; a global inviter's invitee is rooted in the
organization of its direct roles (roles from two organizations: 422). With `entity_id`, the entity must be
inside the inviter's tenant (DD-061): another tenant's entity answers 404 and
no account is created. For a non-global inviter it must also lie in the tree of
the inviter's own root: an entity reached only through a membership left in
another tenant's tree by an earlier cross-root move answers 403 (decision 17),
because the invitee would be rooted in that tenant.

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
