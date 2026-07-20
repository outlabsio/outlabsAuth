# User Status System

> **Handbook** · What each user status means for login and admin flows.  
> Part of the [OutlabsAuth Handbook](./README.md). Related:
> [User Invitations](./24-User-Invitations.md),
> [User Management API](./23-User-Management-API.md).

Status answers one question: **can this user authenticate?**

| Status | Can log in? | Typical meaning | How it usually changes |
|--------|-------------|-----------------|------------------------|
| `active` | Yes | Normal account | From invite accept; admin reactivate |
| `invited` | No | Invite sent; no password yet | → `active` via accept-invite |
| `suspended` | No | Temporary block | Admin `PATCH …/status`; optional `suspended_until` |
| `banned` | No | Permanent block | Admin; rarely reversed |
| `deleted` | No | Soft-deleted | Admin delete; restore via `POST …/restore` |

Email verification, lockouts, and product policy live in **other** fields — do
not overload `status` for those.

```python
from outlabs_auth.models.sql.enums import UserStatus
# active | invited | suspended | banned | deleted
```

---

## Behavior notes

- Login checks status **before** password verification and raises an inactive /
  banned style error per status (invited users are pointed at the invite email).
- Only `active` users authenticate (JWT, API keys, refresh), subject also to
  lockout (`failed_login_attempts` / `locked_until`) when that path is enabled.
- On **suspend / ban / delete**, revoke refresh tokens (and API keys) in the same
  admin action if you need immediate cut-off; short-lived access JWTs may still
  work until expiry unless you enable Redis blacklist.
- Admin status PATCH on the users router allows `active` | `suspended` | `banned`
  only — not `deleted` (use delete / restore endpoints). See [23](./23-User-Management-API.md).

---

## Related fields (not status)

| Concern | Fields / mechanism |
|---------|-------------------|
| Invite in flight | `invite_token`, `invite_token_expires`, `invited_by_id` |
| Soft delete | `deleted_at` |
| Timed suspend | `suspended_until` (host/auto-reactivation logic) |
| Brute-force lock | `failed_login_attempts`, `locked_until` |
| Email proof | `email_verified` (separate from status) |

---

## Related

- [User Invitations](./24-User-Invitations.md)
- [User Management API](./23-User-Management-API.md)
- [Sessions & Audit](./05-Sessions-and-Audit.md)
- Maintainer decision: DD-048 in [`docs/DESIGN_DECISIONS.md`](../docs/DESIGN_DECISIONS.md)
