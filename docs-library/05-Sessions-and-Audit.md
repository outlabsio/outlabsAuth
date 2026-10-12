# Sessions and Audit

Let users (and admins) see **active devices / logins** and search **audit
events**. Mount `get_users_router` for sessions and per-user history; mount
`get_audit_router` when you need cross-user search.

## Sessions (active logins)

Under the hood, a “session” is a stored refresh-token row
(`store_refresh_tokens=True`, the default). The users router lists those rows as
sessions **without** returning secrets.

Mount users (examples use `/v1/users`):

```python
from outlabs_auth.routers import get_users_router

app.include_router(get_users_router(auth, prefix="/v1/users"))
```

### Self-service

| Method | Path | Permission |
|--------|------|------------|
| `GET` | `/v1/users/me/sessions` | Authenticated |
| `DELETE` | `/v1/users/me/sessions/{session_id}` | Authenticated (own session) |
| `DELETE` | `/v1/users/me/sessions` | Authenticated — revoke all (`?keep_current=true` keeps the calling session) |

Response fields (see `UserSessionResponse`): `id`, `device_name`, `ip_address`,
`user_agent`, `created_at`, `last_used_at`, `expires_at`, `usage_count`,
`is_current`.

Access tokens carry a `sid` claim naming their session family, so the list can
mark `is_current: true` on the caller's own session and
`DELETE /v1/users/me/sessions?keep_current=true` can implement "sign out other
devices". Tokens minted before 0.1.0a35 carry no `sid`: they match no row, and
`keep_current=true` answers 400 until the user signs in again.

With frontend profiles configured (`0.1.0a25+`), sessions also record which
frontend minted them as an `azp` claim — preserved and re-validated at refresh
rotation. See [Multi-Frontend Support](../docs/MULTI_FRONTEND_SUPPORT.md).

### Admin

| Method | Path | Permission |
|--------|------|------------|
| `GET` | `/v1/users/{user_id}/sessions` | `user:read` |
| `DELETE` | `/v1/users/{user_id}/sessions/{session_id}` | `user:update` |
| `DELETE` | `/v1/users/{user_id}/sessions` | `user:update` (all for that user) |

Scoped actors (Enterprise + `enforce_user_scope`) only see targets in their
access scope. Admin revokes emit audit events when audit is wired.

### Lifecycle and replay barriers (a37)

Deleting or restoring an account retires its pending login/recovery challenges
and advances its durable session generation. Restore returns an identity without
restoring its former privilege; pre-boundary access/refresh proofs remain refused.

Reusing a rotated refresh token aborts the caller transaction, then commits session
revocation and the generation barrier in an independent transaction before refusing
the request. Unrelated pending caller writes roll back. A containment failure
propagates rather than reporting successful revocation. Qualified hosts use ordinary
configured-engine sessions and enough pool capacity for the independent checkout.
Externally held connections, connection-local schema/search-path overrides and
single-connection pools require separate host qualification. See
[Auth recovery](../docs/AUTH_RECOVERY.md) before admission, restore or rollback.

a38 adds `AuthService.security_transaction_factory`, an optional async context
manager factory receiving the rolled-back caller session. A host with an external
write journal may set it on `auth.auth_service` after initialization. Its yielded
session must durably commit and acknowledge **only containment effects** before
the SDK's `commit()` returns; refusal and cancellation must propagate. Never
silently borrow an uncommitted request transaction or enqueue revocation after
the refusal response. Without the hook, the independent configured-engine
transaction remains the default. Qualify rotated-token replay through the actual
mounted host, including unrelated pending-write rollback, replacement bearer/
refresh denial, store failure and the host's recovery generation.

### Do not confuse with `get_session_router`

`get_session_router` is a **minimal login/refresh/logout** surface for embedded
hosts — not the session *inventory* API. Prefer `get_auth_router` for full auth
plus `get_users_router` for session list/revoke.

## Audit events

User-centric audit is driven by `user_audit_service`, which is created during
`auth.initialize()` (always available after init). Mount the routers below to
expose it over HTTP.

`enable_audit_log` on `AuthConfig` is a separate/legacy feature-status flag — it
does **not** gate these routes.

### Per-user history

| Method | Path | Permission |
|--------|------|------------|
| `GET` | `/v1/users/{user_id}/audit-events` | `user:read` |

Supports filters such as `category`, `event_type`, pagination.

### Cross-user search

```python
from outlabs_auth.routers import get_audit_router

app.include_router(get_audit_router(auth, prefix="/v1/audit-events"))
```

| Method | Path | Permission |
|--------|------|------------|
| `GET` | `/v1/audit-events` | `user:read` |

Query params include `category`, `event_type`, `subject_user_id`,
`actor_user_id`, `entity_id`, `occurred_from`, `occurred_to`, plus pagination.

Scoped Enterprise actors only receive events whose `root_entity_id` is in their
access scope. Global/superuser actors see the wider set according to scope
resolution.

Besides user lifecycle events the log carries structural changes:
`category=entity` (`entity.created`, `entity.updated` with a field-level diff,
`entity.moved`, `entity.archived`, rooted at the entity's tenant) and
`category=config` (`config.entity_types_updated`, platform-wide, visible to
global actors only). These events have no subject user.

### Definition history

Role and permission definitions keep an append-only history (who changed what,
with before/after snapshots):

| Method | Path | Permission |
|--------|------|------------|
| `GET` | `/v1/roles/{role_id}/history` | `role:read` + role visibility |
| `GET` | `/v1/permissions/{permission_id}/history` | `permission:read` |

If `user_audit_service` is not available, search returns an empty page rather
than failing hard.

## OutlabsAuth UI

With users (+ audit) routers mounted under the same `authApiPrefix`, the sister
admin console can show session and audit surfaces that the backend advertises.
Point the UI as described in [`docs/AUTH_UI.md`](../docs/AUTH_UI.md).

## Related

- [02-Routers-and-Prefixes.md](./02-Routers-and-Prefixes.md)
- [03-Configuration.md](./03-Configuration.md)
- [22-JWT-Tokens.md](./22-JWT-Tokens.md)
- Live OpenAPI on a running example (`/docs`)

## Unreleased transactional lifecycle observer

The local `0.1.0a38` candidate adds optional `lifecycle_observers` to the
Auth constructor. Public a37 does not provide this option. Do not enable it in
a deployed consumer before the library/host artifact and writer coverage gates
in `docs/S2_S3_FOUNDATION_2026-10-11.md` qualify.

An observer is an async callable `(session, event)`. `event` is a frozen scalar
`LifecycleEvent` with a unique event UUID, aware UTC occurrence time, kind,
applicable user/entity/root/membership/actor UUIDs, frozen names, lifecycle
statuses and source. It carries no passwords, email addresses or tokens.

Write host-owned evidence through that exact AsyncSession. The caller owns the
transaction; the observer must not commit, roll back, open another transaction,
change IAM authority or perform mail/network side effects. Observer failure
poisons the active transaction, so a caught error cannot be committed until
rollback. A failed savepoint can be discarded by rolling back that savepoint;
rolling back a later savepoint cannot clear a failure in its outer transaction.

Membership changes/removals, user suspension/retained deletion/hard deletion and
archive cascades invoke the observer before destructive cleanup. Evidence must
use independent host storage without cascading IAM foreign keys to survive
hard deletion. Repeated revocation emits no duplicate removal. Generic
structural hard deletion is refused; use the archive workflow and retain its
evidence. Direct database edits are outside the supported service lifecycle.

No configured observers means no observer queries or events. The callback is
not an external delivery guarantee: write an outbox with the evidence, commit,
then deliver separately. Without verified provider idempotency, record UNKNOWN
outcomes and the possibility of duplicate physical delivery. Crosswalks,
source-owned contributions, recovery fencing and cohort completeness remain
host responsibilities.

The unreleased a38 `user_service.send_invitation_email_result(...)` uses the same
canonical invitation composition and provider as the existing boolean
`send_invitation_email(...)` hook. It returns `MailDeliveryResult`, retaining
provider and message ID for a durable host receipt. Existing boolean callers
keep their contract. Provider acceptance does not establish delivery or
idempotency; metadata such as a logical delivery ID is not an idempotency key.
Retain safe receipt identifiers only, since provider error/details can contain
personal data or credentials. A missing provider returns an explicit skipped
result. UNKNOWN reconciliation, transport draining, explicit resend, encrypted
outbox keys and recovery remain host-owned operational responsibilities.


## Unreleased explicit staff host facade

The local a38 candidate offers
`auth.host_query_service.staff_administration(auth, trusted_internal_root_id=...)`.
Configure the control-root UUID on the server and retain one facade instance
for the application lifetime: contexts and entity cursors are instance-bound.
Authenticate through the facade
with the actual request and exact host AsyncSession; its context cannot cross
a transaction, session or installation. Human JWTs and personal keys intersect
current target-bound grants; machine credentials cannot borrow staff authority.

Use `authorize(action=..., entity_id=...)` for detail and
`authorize_account(action=..., user_id=...)` for root-owned account actions.
For sensitive effects request `protected_write=True`, check `allowed`, and
perform the effect in that same bounded transaction before committing. Set host
lock/statement budgets and roll back failures. The library holds the qualifying
policy rows and rechecks them after waits. Multi-target operations still need
qualified ordering, failure handling and writer inventory.

`entity_page(action=..., limit=..., cursor=...)` filters/counts/pages authorized
entity projections in SQL. A list admission is not write authorization.
`create_personal_key` is explicit JWT-only self-service with exact bounded
scopes and a durable anchor; ordinary mounted SDK key policy stays in force.
`update_personal_key` narrows an owned key's exact scopes and may shorten expiry.
It cannot transfer owner/anchor, expand inheritance, reactivate a key or extend
its deadline. `rotate_personal_key` rechecks live grants after locking the old
key, creates the replacement and revokes the original in the same transaction,
retaining exact scopes, anchor, inheritance, IP/rate restrictions and expiry.
The deadline is checked again after authority waits. No commit occurs inside
these SDK methods; a caller rollback restores the original and discards the
replacement. `revoke_personal_key` remains available after grants end.

These management methods require the owner's current human JWT. A personal key
cannot mint or manage a second key. `personal_key_page(limit=..., after=...)`
returns only that owner's credential metadata, with SQL filtering before count
and UUID keyset pagination. It exposes no key secret/hash/prefix and grants no
customer credential-management authority. Use this explicit facade for the
qualified staff workflow; existing mounted key routes keep ordinary policy.

The unreleased package also exports `get_staff_router` from
`outlabs_auth.routers`. Mount it explicitly using the same application-lifetime
facade and install `auth.instrument_fastapi(app)` before startup. Its default
`/staff` surface provides action-qualified `/entities` discovery (`entity:read`)
and JWT-owned `/keys` create, list, narrow, rotate and revoke operations. It does
not mount customer account/session/password/OAuth or membership mutations.
The host must pair and qualify those operations separately.

Staff-minted keys retain `staff_managed` provenance. Ordinary SDK/mounted update
and rotation refuse those keys; ordinary self-revocation also requires a human
JWT. A database fence prevents provenance removal, owner/anchor/inheritance
changes, reactivation and expiry expansion. Existing ordinary credentials keep
their policy. This provenance does not establish restricted database privileges
or a complete native-writer inventory.

Unanchored legacy runtime keys require explicit opt-in; update/rotation refuse
unanchored, revoked, expired or non-expiring keys. Complete IAM route pairing,
customer credential inventory/management, large-tree numeric budgets and
restricted DML privileges remain gates. Nothing activates this facade on
existing routes.

Qualification and remaining release/consumer gates are recorded in
`docs/S2_MOUNTED_IAM_PERFORMANCE_2026-10-11.md`; do not adopt an unreleased
local build in a deployed consumer. Public a37 does not provide this facade.


## Unreleased native and source membership ownership

Public a37 has no source contribution writer. The unreleased a38 candidate adds
`MembershipService.set_source_membership` for trusted host reconciliation of
already mapped accounts. The host must review a complete source cut, acquire
compatible writer fences and compare actual target state before calling it.
This SDK method has no HTTP route and does not create users or invitations.

Existing attachments and role grants retain native ownership at migration.
Each source relationship has a stable opaque UUID and its own exact role subset.
Effective roles are the union of native and source intentions. A native role
replacement changes its native subset; independently sourced roles remain until
that source withdraws them. Reassigning a role already held through a source
records native intention, so subsequent source removal preserves it.

Withdraw one source with `role_ids=None`. Another source or a native attachment
keeps the membership. Withdrawing the last source-only attachment revokes the
membership and records history while preserving the account. Source replay
cannot override native suspension, revocation or validity, transfer accounts,
change credentials/preferences or restore a natively revoked membership.
Source-only return has the narrower proof contract below. Withdraw source claims
before hard-deleting claimed memberships/roles.

The host owns atomic application, stable mappings, accepted source watermarks,
frozen relationship evidence, recovery admission and delivery. Database child
fences include empty collections, but restricted runtime permissions and exact
consumer/package/schema acceptance remain activation gates. See
`docs/S3_MEMBERSHIP_OWNERSHIP_2026-10-12.md` for the qualified boundary.

### Reviewed population and source return (unreleased a38)

`UserService.create_source_user` creates an explicitly reviewed UUID under an
active independent customer root. The account starts `invited`, without a
password, verified email, session, recovery challenge or delivery hook. Existing
email or UUID collisions are errors; the method never adopts an account by its
email. The host owns source aliases, customer-root role templates, the atomic
population receipt and a pending setup intent. Pending intent is not evidence
that an invitation was delivered or that the user can log in.

Migration `20261012_0031` retains a source-only withdrawal proof containing the
membership UUID, its write revision and the account security epoch. Source
return may reactivate that same membership only while those values match and
no native attachment or validity override exists. Native removal, same-value
lifecycle edits, role DML, hard deletion or an account security boundary blocks
return. Explicit native reactivation records native ownership. Earlier source
withdrawals without proof need explicit native acknowledgement.

A host changing its schema, recovery generation or mapping policy must retain
its original opaque source claim namespace. A qualified host adapter retires the
predecessor and applies its successor atomically, retaining old crosswalks,
accepted watermarks and frozen removal episodes. Handoff does not authorise
identity transfers, a new cohort, source lease ownership or delivery. See
`docs/S3_POPULATION_SOURCE_RETURN_2026-10-12.md` for current qualification.

### Opt-in customer account and membership operations (unreleased a38)

The explicitly mounted staff router includes customer account detail/list,
first/last-name edits, active/suspended status, retained deletion and restore.
Account actions require one qualifying grant covering the actual customer root.
Lists exclude platform-protected subjects before count and pagination. Root
transfer, email/password/privilege edits and self/Internal administration are
absent from these inputs.

Membership detail, native role replacement, creation, removal and explicit
reactivation use the stored subject/customer/entity boundary. Only active
customer-owned roles are assignable. Creation and update require their own
respective actions; native source overlap is preserved. Retained platform
classification and global roles through either direct or entity membership
assignments deny limited staff administration. Ordinary IAM routes do not gain
staff grants. Existing compatible-writer, full-consumer and release gates remain.
