# User Management API

> **Handbook** · HTTP surface for user admin and self-service.  
> Part of the [OutlabsAuth Handbook](./README.md). Mount details:
> [Routers & Prefixes](./02-Routers-and-Prefixes.md).

Paths below assume the common example mount `prefix="/v1/users"`. Your host may
use `/iam/users` or another base — only the suffix after that prefix matters.

When this page and a running app disagree, trust **live OpenAPI** at
`{your-api}/docs` and `outlabs_auth/routers/users.py`.

---

## What to mount

| Factory | When |
|---------|------|
| `get_users_router(auth, prefix="/v1/users")` | Full admin + self-service (examples, OutlabsAuth UI) |
| `get_self_service_users_router(...)` | Tiny embed: own profile + permission **names** only |

```python
from outlabs_auth.routers import get_users_router

app.include_router(get_users_router(auth, prefix="/v1/users"))
```

Optional: `requires_verification=True` tightens auth on `/me*` routes.

Invites are mostly on the **auth** router — see [User Invitations](./24-User-Invitations.md).
This router only exposes `POST /{user_id}/resend-invite`. Entity membership
CRUD lives on the memberships router — see [Entity Memberships](./54-Entity-Memberships.md).

---

## Permissions at a glance

| Action | Typical permission |
|--------|--------------------|
| Create user | `user:create` |
| List / get / roles / audit / sessions (admin) | `user:read` |
| Update profile, status, roles, revoke sessions/keys | `user:update` |
| Soft-delete | `user:delete` |
| Grant/revoke `is_superuser` | Superuser only (`require_superuser`) |
| `/me*` self-service | Authenticated (optional email verification) |

---

## Simple vs Enterprise scope

Same router for both presets. Behavior depends on flags:

| Concern | Behavior |
|---------|----------|
| **SimpleRBAC** (`enable_entity_hierarchy=False`) | Scope filtering is effectively off — list/get are system-wide for permitted actors |
| **Enterprise** + `enforce_user_scope=True` (default) | Non-global actors only see/mutate users in their entity trees. Out of scope → **404** (not 403). Self always allowed |
| `root_entity_id` on list | Narrows within the actor’s scope; never widens it |
| `/orphaned`, `/{id}/membership-history` | Meaningful when membership service exists (Enterprise); otherwise empty pages |

Set `enforce_user_scope=False` only as a transitional escape hatch.

---

## Admin CRUD and lifecycle

| Method | Path | Permission | Notes |
|--------|------|------------|-------|
| `POST` | `/` | `user:create` | Admin create (not public register). Only superusers may set `is_superuser` |
| `GET` | `/` | `user:read` | Paginated list. Query: `page`, `limit`, `search`, `status`, `is_superuser`, `root_entity_id` |
| `GET` | `/{user_id}` | `user:read` | Single user (scoped) |
| `PATCH` | `/{user_id}` | `user:update` | Admin profile update |
| `DELETE` | `/{user_id}` | `user:delete` | Soft delete |
| `PATCH` | `/{user_id}/password` | `user:update` | Admin set password (no current password) |
| `PATCH` | `/{user_id}/status` | `user:update` | `active` / `suspended` / `banned` only — not `deleted` |
| `POST` | `/{user_id}/restore` | `user:update` | Restore a deleted identity (does not restore grants/credentials) |
| `PATCH` | `/{user_id}/superuser` | Superuser | Grant/revoke platform superuser; cannot revoke yourself |
| `POST` | `/{user_id}/resend-invite` | `user:update` | New invite token for `INVITED` users |

List `status` filter: `active` | `suspended` | `banned` | `deleted`.

**Create body** (`UserCreateRequest`): email, password, optional names / phone /
`is_superuser`.  
**Update body** (`UserUpdateRequest`): email, names, phone (partial).  
**Responses**: `UserResponse` (UUID `id`, profile fields, status flags).  
**List**: `PaginatedResponse[UserResponse]` (`items`, `total`, `page`, `limit`, `pages`).

---

## Self-service (`/me`)

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| `GET` | `/me` | Authenticated | Own profile |
| `PATCH` | `/me` | Authenticated | Own profile (`UserUpdateRequest`) |
| `POST` | `/me/change-password` | Authenticated | `ChangePasswordRequest` (current + new) → 204 |
| `POST` | `/me/phone/request-code` | Authenticated | OTP to registered phone (rate-limited) → 204 |
| `POST` | `/me/phone/verify-code` | Authenticated | `PhoneVerifyCodeRequest` → `UserResponse` |

---

## Roles and effective permissions

Direct role memberships (flat RBAC and Enterprise “direct” roles):

| Method | Path | Permission | Notes |
|--------|------|------------|-------|
| `GET` | `/{user_id}/roles` | `user:read` | `?include_inactive` → `RoleResponse[]` |
| `GET` | `/{user_id}/role-memberships` | `user:read` | Membership rows + embedded role |
| `POST` | `/{user_id}/roles` | `user:update` | `AssignRoleRequest` → membership (201). Actor must hold all permissions on the role |
| `DELETE` | `/{user_id}/roles/{role_id}` | `user:update` | Soft-revoke |
| `PATCH` | `/{user_id}/role-memberships/{membership_id}` | `user:update` | Validity window / status |
| `GET` | `/{user_id}/permissions` | Self **or** `user:read` | Effective perms: direct roles **and** entity-membership roles when present → `UserPermissionSource[]` |

Entity-scoped role assignment (membership + roles on an entity) is **not** here —
use [Entity Memberships](./54-Entity-Memberships.md).

---

## Orphans and membership history (Enterprise)

| Method | Path | Permission | Notes |
|--------|------|------------|-------|
| `GET` | `/orphaned` | `user:read` | Users with no active entity memberships. Empty for non-global scoped actors or without membership service |
| `GET` | `/{user_id}/membership-history` | `user:read` | Append-only entity membership lifecycle events |

---

## Personal API keys (admin view)

| Method | Path | Permission | Notes |
|--------|------|------------|-------|
| `GET` | `/{user_id}/api-keys` | `user:read` | List personal keys (no secrets) |
| `DELETE` | `/{user_id}/api-keys/{key_id}` | `user:update` | Admin revoke |

Self-service key minting and system/integration keys:
[API Key Host Integration](./50-API-Key-Host-Integration.md).

---

## Sessions, social accounts, audit (elsewhere)

Do not duplicate those tables here:

| Area | Guide |
|------|-------|
| List / revoke sessions (`/me/sessions`, `/{user_id}/sessions`) | [Sessions & Audit](./05-Sessions-and-Audit.md) |
| Per-user audit (`/{user_id}/audit-events`) + cross-user search | same |
| Link / unlink social (`/me/social-accounts`) | [OAuth & Social Login](./04-OAuth-and-Social-Login.md) |

---

## Minimal self-service router

For hosts that only need “who am I?”:

```python
from outlabs_auth.routers import get_self_service_users_router

app.include_router(get_self_service_users_router(auth, prefix="/v1/account"))
```

| Method | Path | Response |
|--------|------|----------|
| `GET` | `/me` | `UserResponse` |
| `GET` | `/me/permissions` | `list[str]` — permission **names** only (not `UserPermissionSource`) |

---

## Schemas quick reference

| Model | Role |
|-------|------|
| `UserResponse` | Profile payload |
| `UserCreateRequest` / `UserUpdateRequest` | Admin create / patch |
| `ChangePasswordRequest` / `AdminResetPasswordRequest` | Password changes |
| `UserStatusUpdateRequest` / `UserSuperuserUpdateRequest` | Status / superuser |
| `PhoneVerifyCodeRequest` | Phone OTP confirm |
| `AssignRoleRequest` / `UserRoleMembershipUpdate` | Direct roles |
| `UserRoleMembershipResponse` / `UserRoleMembershipDetailResponse` | Membership rows |
| `UserPermissionSource` | Effective permission + source metadata |
| `OrphanedUserResponse` / `MembershipHistoryEventResponse` | Enterprise helpers |
| `PaginatedResponse[T]` | List envelopes |

---

## Related

- [User Status](./48-User-Status-System.md)
- [User Invitations](./24-User-Invitations.md)
- [Sessions & Audit](./05-Sessions-and-Audit.md)
- [Core Authorization Concepts](./13-Core-Authorization-Concepts.md)
