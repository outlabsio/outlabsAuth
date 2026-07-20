# OutlabsAuth - Authentication Dependency Patterns

**Applies to**: `outlabs-auth` (alpha)

The authoritative source for everything below is `outlabs_auth/dependencies/__init__.py`.

---

## Table of Contents

1. [Overview](#overview)
2. [The Authentication Context](#the-authentication-context)
3. [AuthDeps - Dependency Injection](#authdeps---dependency-injection)
4. [Multi-Source Authentication](#multi-source-authentication)
5. [API Key System](#api-key-system)
6. [Entity Permissions](#entity-permissions)
7. [Advanced Patterns](#advanced-patterns)
8. [Rate Limiting](#rate-limiting)
9. [Testing Patterns](#testing-patterns)
10. [Security Best Practices](#security-best-practices)

---

## Overview

This document covers how to use FastAPI's dependency injection with the `AuthDeps`
class to protect endpoints across every authentication source the library supports —
user JWTs, API keys, and JWT service tokens.

### Core Design Principles

1. **One-line protection for the common case**: a single `Depends(...)` on the route.
2. **Composable**: stack dependencies to combine requirements.
3. **Source-agnostic**: the same `require_permission` works whether the caller
   presented a user JWT, an API key, or a service token.
4. **Testable**: dependencies return plain dicts, so faking one needs no library types.
5. **Honest OpenAPI**: dependency signatures are generated to include every configured
   transport, so Swagger shows the real auth options.

### Why Dependency Injection?

FastAPI's DI gives clear contracts in the signature, validation before the handler
runs, easy overrides in tests, and composition of small requirements into larger ones.

---

## The Authentication Context

Every `AuthDeps` dependency returns a **plain `dict`**, not a model or a context
object. There is no `AuthContext` class to import.

The dict is produced by whichever authentication strategy matched
(`outlabs_auth/authentication/strategy.py`). Its shape by source:

| Key | `jwt` | `api_key` | `service_token` |
|---|---|---|---|
| `user` | `User` | `User`, or `None` for a principal-owned key | `None` |
| `user_id` | `str` UUID | `str` UUID, or `None` | `None` |
| `source` | `"jwt"` | `"api_key"` | `"service_token"` |
| `metadata` | JWT payload | key metadata | full token payload |
| `api_key` | — | `APIKey` model | — |
| `integration_principal_id` | — | set for principal-owned keys | — |
| `service_id` / `service_name` | — | — | `str` |

Because keys differ by source, use `.get()` in any handler that accepts more than one.

```python
@app.get("/whoami")
async def whoami(ctx: dict = Depends(auth.deps.require_auth())):
    if ctx["source"] == "service_token":
        return {"kind": "service", "name": ctx["service_name"]}

    user = ctx["user"]
    return {"kind": "user", "email": user.email}
```

### Design Benefits

1. **No import coupling**: business logic can accept the context without importing
   from the library.
2. **Trivially fakeable**: a test double is a dict literal.
3. **Source-explicit**: `ctx["source"]` says exactly how the caller authenticated,
   so a handler can treat a machine differently from a human.

### Superusers and anonymous access

There is no `superuser` source and no `anonymous` source. A superuser is an ordinary
`jwt` caller whose `User` record has `is_superuser=True`; `require_superuser()`
authenticates normally and then checks that flag. Anonymous access is
`require_auth(optional=True)` returning `None`.

Superuser status **is** an automatic bypass, at every layer and with no flag to
disable it:

- `require_permission` short-circuits to allow via `superuser_shortcut` on its fast path.
- `permission_service.check_permission` returns `True` before evaluating anything else.
- `permission_service.get_user_permissions` returns `["*:*"]`.

So `is_superuser=True` grants every permission, including ABAC-conditioned ones —
conditions are never evaluated for a superuser. Treat the flag as full control of the
system and grant it accordingly.

---

## AuthDeps - Dependency Injection

### Getting an AuthDeps

You do not construct `AuthDeps` yourself. The library builds one and exposes it as
`auth.deps`, wired to the configured backends and services.

```python
deps = auth.deps  # AuthDeps
```

`auth.deps` raises `ConfigurationError` until the instance has been initialized. Call
`await auth.initialize()`, or `auth.prime_fastapi_routing()` for the synchronous path
when you need to mount routers at import time. This is why router factories must be
called after one of those two — they dereference `auth.deps` at call time.

`OutlabsAuth` also proxies the three most common factories directly, so
`auth.require_permission(...)` is shorthand for `auth.deps.require_permission(...)`.

### The factories

Every factory returns a FastAPI dependency function. Each one authenticates the
request first, then applies its own check.

| Factory | Purpose |
|---|---|
| `require_auth(active=True, verified=False, optional=False)` | Any configured credential |
| `require_permission(*permissions, require_all=False, ...)` | One or all of the named permissions |
| `require_entity_permission(permission, entity_id_param="entity_id")` | Permission inside one entity |
| `require_tree_permission(permission, entity_id_field, *, source="path")` | Permission across an entity subtree |
| `require_source(source)` | Restrict to `"jwt"`, `"api_key"`, or `"service_token"` |
| `require_superuser()` | Authenticated and `is_superuser=True` |

#### require_auth

```python
# Any authenticated caller
@app.get("/protected")
async def protected(ctx: dict = Depends(auth.deps.require_auth())):
    return {"id": ctx["user_id"]}


# Verified email required
@app.post("/comments")
async def comment(ctx: dict = Depends(auth.deps.require_auth(verified=True))):
    ...


# Optional — None when no credentials were presented
@app.get("/feed")
async def feed(ctx: dict | None = Depends(auth.deps.require_auth(optional=True))):
    if ctx is None:
        return await public_feed()
    return await personal_feed(ctx["user_id"])
```

`active=True` (the default) requires `user.can_authenticate()`. `verified=True`
requires `user.email_verified`. Both filters only apply when the result carries a
user, so a service token is unaffected.

#### require_permission

```python
# Any one of these permissions
@app.get("/reports")
async def reports(
    ctx: dict = Depends(auth.deps.require_permission("report:read", "report:export")),
):
    ...

# All of them
@app.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    ctx: dict = Depends(
        auth.deps.require_permission("user:delete", "audit:write", require_all=True)
    ),
):
    ...
```

It also accepts `allow_entity_context_header` and a `resource_context_provider`
callable for supplying ABAC resource attributes.

#### require_source

Takes a single source string, not a list:

```python
@app.post("/webhook")
async def webhook(ctx: dict = Depends(auth.deps.require_source("api_key"))):
    return {"received": True}
```

To allow one of several sources, check `ctx["source"]` in the handler instead.

#### require_superuser

```python
@app.post("/system/dangerous")
async def dangerous(ctx: dict = Depends(auth.deps.require_superuser())):
    return {"performed": True}
```

Returns 401 when unauthenticated, 403 when authenticated without `is_superuser`.

### Generated signatures

`AuthDeps` uses `makefun` to build each dependency with a signature listing every
configured transport, so they appear correctly in the OpenAPI schema rather than as
an opaque callable. The signature is built once per instance and reused.

---

## Multi-Source Authentication

### The backend chain

`OutlabsAuth._init_backends()` wires up to three backends, tried in order:

| Order | Backend | Transport | Wired when |
|---|---|---|---|
| 1 | `jwt` | `Authorization: Bearer <token>` | always |
| 2 | `api_key` | `X-API-Key` header | an API-key service exists |
| 3 | `service_token` | `Authorization: Bearer <token>` | a service-token service exists |

User JWTs and service tokens share the `Authorization: Bearer` header and are
distinguished by payload — the service-token strategy requires `type == "service"`,
so a user JWT does not satisfy it and a service token falls through the JWT backend.

### Resolution

`_authenticate_request` drives the chain:

1. **Short-circuit.** If no backend's transport sees anything credential-shaped, skip
   the loop entirely — anonymous requests never pay for a JWT decode or a DB session.
   Then either return `None` (`optional=True`) or raise 401.
2. **Try each backend in order.** The first that returns a result wins. A backend
   signals "not mine" by returning `None`, not by raising.
3. **Apply filters.** With `active`/`verified`, a result carrying a user that fails
   the filter is skipped and the chain continues to the next backend.
4. **Memoize.** Default-parameter results are cached on `request.state`, so two
   dependencies on one route (say `require_auth()` and `require_permission()`)
   authenticate once. Non-default parameters deliberately bypass the cache.
5. **Fail closed.** An unexpected backend exception is logged and the chain continues
   to the next backend; it never authenticates the request.

Two exception types escape the loop rather than falling through, because retrying
them against another backend would be wrong:

- `RateLimitError` → **429**, with a `Retry-After` header when the quota reports one.
- `AuthenticationInfrastructureError` → **503**, likewise. This is the "auth
  infrastructure is down" signal, distinct from "your credentials are bad".

### Example

```python
@app.get("/api/data")
async def get_data(ctx: dict = Depends(auth.deps.require_auth())):
    source = ctx["source"]

    if source == "service_token":
        return await get_service_data(ctx["service_name"])

    if source == "api_key":
        return await get_partner_data(ctx["api_key"].id)

    return await get_user_data(ctx["user_id"])
```

---

## API Key System

### The model

API keys are a SQLModel table: `outlabs_auth/models/sql/api_key.py`, class `APIKey`.
Selected columns:

- `name`, `description`
- `prefix` — the first 16 characters of the key, stored in the clear for identification
- `key_hash` — SHA-256 hex digest of the full key
- `owner_id` — the owning `User`, or `integration_principal_id` for a principal-owned key
- `key_kind` (`APIKeyKind`), `status` (`APIKeyStatus`)
- `entity_id`, `inherit_from_tree` — optional entity scoping
- `rate_limit_per_minute`, `rate_limit_per_hour`, `rate_limit_per_day`
- `expires_at`, `last_used_at`, `usage_count`

Scopes and IP whitelist entries live in their own tables, keyed by `api_key_id`.

### Key generation and hashing

`APIKey.generate_key(prefix_type="sk_live")` returns `(full_key, prefix)`:

```python
key_material = secrets.token_hex(32)       # 32 bytes of CSPRNG output
full_key = f"{prefix_type}_{key_material}"
prefix = full_key[:16]
```

`APIKey.hash_key(full_key)` is a **SHA-256 hex digest**. That is deliberate, and it is
the one place where API-key handling should not copy password handling: a password is
low-entropy and needs a slow hash to make guessing expensive, whereas this key is 32
bytes of CSPRNG output with no guessable structure. A slow KDF here would add latency
to every authenticated request and buy nothing. `hash_key_bytes()` returns the raw
digest for hot-path byte comparisons; the hex form is used for storage and Redis keys.

### Verification

```python
api_key, usage_count = await auth.api_key_service.verify_api_key(
    session,
    api_key_string=raw_key,
    required_scope="user:read",     # optional
    entity_id=entity.id,            # optional
    ip_address=request.client.host, # optional
)
```

Returns `(None, ...)` for an invalid key rather than raising. It checks the hash,
status, expiry, scope, entity access, and IP whitelist, and tracks usage via a Redis
counter. `RateLimitError` propagates out of it when a quota is exceeded.

You rarely call this directly — the `api_key` backend does it for you on any
`require_auth()` / `require_permission()` route.

### Usage counters

Usage is counted in Redis (`increment_with_ttl`) rather than written to Postgres per
request, and flushed back periodically by
`api_key_service.sync_usage_counters_to_db(session)` — driven by the
`api_key_sync` worker (`outlabs_auth/workers/api_key_sync.py`). This keeps a hot API
key from generating a database write on every call.

Redis is optional. Without it, rate-limit checks are skipped
(`_check_rate_limits` returns early when no Redis client is available) — so if you
depend on API-key rate limiting, Redis is required, not a nice-to-have.

### Lifecycle

```python
# Create — everything after `session` is keyword-only
raw_key, api_key = await auth.api_key_service.create_api_key(
    session,
    owner_id=user.id,
    name="Partner API",
    scopes=["invoice:read"],
    expires_in_days=90,
    prefix_type="sk_live",
)

# Rotate — returns a brand new (raw_key, key) pair
new_raw, new_key = await auth.api_key_service.rotate_api_key(
    session, key_id=api_key.id, actor_user_id=user.id
)

# Revoke — takes effect immediately
await auth.api_key_service.revoke_api_key(
    session, key_id=api_key.id, actor_user_id=user.id, reason="Compromised"
)
```

The raw key is returned only at create and rotate. It is never recoverable
afterwards — only its SHA-256 hash is stored.

---

## Entity Permissions

Entity-scoped dependencies require `enable_entity_hierarchy=True` (i.e.
EnterpriseRBAC). SimpleRBAC force-disables it.

### require_entity_permission

Requires the permission **within one specific entity**. The entity ID is resolved, in
order, from:

1. the path param named by `entity_id_param`
2. the query param of the same name
3. the `X-Entity-Context` header — only when `entity_id_param == "entity_id"`

```python
@app.put("/entities/{entity_id}/settings")
async def update_settings(
    entity_id: str,
    settings: dict,
    ctx: dict = Depends(auth.deps.require_entity_permission("entity:update")),
):
    return {"updated": True}
```

### require_tree_permission

Requires the permission **across an entity's subtree**. It checks the `_tree` variant
of the permission (so `"entity:create"` is checked as `entity:create_tree`) in the
target entity or any of its ancestors.

`entity_id_field` names where to read the target entity ID from, selected by `source`:

```python
# From the path (default)
@app.post("/entities/{parent_id}/sub-entities")
async def create_sub_entity(
    parent_id: str,
    ctx: dict = Depends(auth.deps.require_tree_permission("entity:create", "parent_id")),
):
    ...

# From a query param
@app.get("/search")
async def search(
    ctx: dict = Depends(
        auth.deps.require_tree_permission("user:read", "scope_id", source="query")
    ),
):
    ...
```

Tree checks are backed by a closure table (`outlabs_auth/models/sql/closure.py`), so
an ancestor check is a single indexed lookup rather than a recursive walk.

### Membership without permissions

There is no `require_entity_access` / `require_entity_role` dependency. To gate on
raw membership or a role in an entity, do it in the handler:

```python
@app.get("/entities/{entity_id}/members")
async def get_members(
    entity_id: UUID,
    ctx: dict = Depends(auth.deps.require_auth()),
    session: AsyncSession = Depends(auth.session),
):
    is_member = await auth.membership_service.is_member(
        session, user_id=ctx["user"].id, entity_id=entity_id
    )
    if not is_member:
        raise HTTPException(403, f"Not a member of entity: {entity_id}")

    return await auth.membership_service.get_entity_members(session, entity_id=entity_id)
```

---

## Advanced Patterns

### Combining multiple requirements

Stack dependencies. Each is evaluated independently, and authentication is memoized so
they do not each re-authenticate.

```python
@app.post("/entities/{entity_id}/admin/action")
async def complex_action(
    entity_id: str,
    _perm: dict = Depends(auth.deps.require_entity_permission("admin:write")),
    _human: dict = Depends(auth.deps.require_source("jwt")),  # no API keys here
):
    return {"performed": True}
```

### Resource ownership

The library authorizes against users, roles, entities, and ABAC attributes. Row-level
ownership is your app's concern:

```python
@app.put("/invoices/{invoice_id}")
async def update_invoice(
    invoice_id: str,
    data: InvoiceUpdate,
    ctx: dict = Depends(auth.deps.require_auth()),
    session: AsyncSession = Depends(auth.uow),
):
    invoice = await invoice_service.get(session, invoice_id)

    if str(invoice.owner_id) != ctx["user_id"]:
        allowed = await auth.permission_service.check_permission(
            session, user_id=UUID(ctx["user_id"]), permission="invoice:admin"
        )
        if not allowed:
            raise HTTPException(403, "Not the owner")

    return await invoice_service.update(session, invoice, data)
```

Alternatively, push the resource attributes into ABAC with a
`resource_context_provider` on `require_permission` and let the policy engine decide.

### Sharing the request session

Dependencies receive the request-scoped unit-of-work session (`auth.uow`), so a
permission check and your handler's writes run on the same session and transaction.
Take it with `Depends(auth.uow)` for writes, or `Depends(auth.session)` when you want
to manage the commit yourself.

---

## Rate Limiting

The library rate limits **API keys**, per key, in Redis. There is no generic
per-auth-source rate-limiting dependency to configure.

Limits are columns on the key itself — `rate_limit_per_minute` (default 60),
`rate_limit_per_hour`, `rate_limit_per_day` — set at creation:

```python
raw_key, api_key = await auth.api_key_service.create_api_key(
    session,
    owner_id=user.id,
    name="Partner API",
    rate_limit_per_minute=60,
    rate_limit_per_hour=1000,
)
```

Enforcement lives in `api_key_service._check_rate_limits`: each window uses an
`INCR` with a TTL, and exceeding one raises `RateLimitError`. `AuthDeps` turns that
into a **429** with a `Retry-After` header, and the error body carries the limit, the
current count, and the window.

**Redis is required for this.** `_check_rate_limits` returns early when no Redis
client is available, so without Redis the limits on the key are silently inert.

For rate limiting user requests or anonymous traffic, use ordinary ASGI middleware —
that is outside this library's scope. `outlabs_auth/utils/rate_limit.py` has an
in-process `RateLimiter` used internally for auth-challenge throttling (magic links,
access codes); it is not wired to a general-purpose dependency.

---

## Testing Patterns

### Faking the context

Because dependencies return dicts, a double is a dict literal — no library types, no
mocks:

```python
def fake_context(user, source="jwt", **extra):
    return {
        "user": user,
        "user_id": str(user.id) if user else None,
        "source": source,
        "metadata": {},
        **extra,
    }
```

### Overriding dependencies

Each factory call builds a **new** function object, so `app.dependency_overrides` must
be keyed on the exact object the route was mounted with. Keep a module-level reference:

```python
# app/deps.py
require_user = auth.deps.require_auth()
require_delete = auth.deps.require_permission("user:delete")

# app/routes.py
@app.delete("/users/{user_id}")
async def delete_user(user_id: str, ctx: dict = Depends(require_delete)):
    ...

# tests/conftest.py
import pytest
from app.deps import require_delete


@pytest.fixture
def override_auth(app, test_user):
    def _override(dependency=require_delete, **kwargs):
        async def _fake():
            return fake_context(test_user, **kwargs)

        app.dependency_overrides[dependency] = _fake

    yield _override
    app.dependency_overrides.clear()
```

Overriding `auth.deps.require_permission("user:delete")` inline in a test will not
work: it creates a different function than the one the route holds.

### Test examples

```python
def test_endpoint_requires_permission(client, override_auth):
    override_auth()
    response = client.delete("/users/123")
    assert response.status_code == 200


def test_api_key_source_is_reported(client, override_auth):
    override_auth(source="api_key")
    response = client.get("/api/data")
    assert response.json()["auth_source"] == "api_key"
```

To test the real permission logic rather than the route wiring, skip the override and
seed a user with roles against a real database — the library is Postgres-only, so
these are integration tests. See `docs/TESTING_GUIDE.md`.

### Integration test

```python
@pytest.mark.asyncio
async def test_api_key_lifecycle(auth, test_user):
    async with auth.get_session() as session:
        raw_key, key = await auth.api_key_service.create_api_key(
            session,
            owner_id=test_user.id,
            name="test_key",
            scopes=["api:read"],
            expires_in_days=90,
        )
        await session.commit()

        assert raw_key.startswith("sk_live_")

        verified, _usage = await auth.api_key_service.verify_api_key(
            session, api_key_string=raw_key
        )
        assert verified is not None

        # Rotate, then the old key no longer verifies
        new_raw, _new_key = await auth.api_key_service.rotate_api_key(
            session, key_id=key.id, actor_user_id=test_user.id
        )
        await session.commit()

        old_verified, _ = await auth.api_key_service.verify_api_key(
            session, api_key_string=raw_key
        )
        assert old_verified is None

        new_verified, _ = await auth.api_key_service.verify_api_key(
            session, api_key_string=new_raw
        )
        assert new_verified is not None
```

---

## Security Best Practices

### API Key Security

#### 1. Never log or store raw keys

```python
# Bad
logger.info(f"Created key: {raw_key}")

# Good — the prefix is the identifier, and it is already stored in the clear
logger.info(f"Created key with prefix: {api_key.prefix}")
```

The raw key exists only in the return value of `create_api_key` / `rotate_api_key`.
Hand it to the caller once and let it go.

#### 2. Hash appropriately for the secret's entropy

The library stores a SHA-256 digest of the key, and that is the correct choice for a
32-byte CSPRNG secret. Do not "upgrade" this to argon2id by analogy with passwords:
the threat a slow KDF defends against — offline guessing of a low-entropy human
secret — does not apply to a random 256-bit key, and the cost lands on every request.
Password hashing is a separate path (`outlabs_auth/utils/password.py`) and does use a
slow hash, correctly.

#### 3. Scope keys narrowly

Grant the minimum scopes, and use `entity_id` (with `inherit_from_tree` only when you
mean it) to bound a key to part of the hierarchy.

#### 4. Set an expiry, and rotate

Pass `expires_in_days` at creation. Rotate with `rotate_api_key`, which mints a new
key and lets you revoke the old one once callers have moved over. Rotation does not
revoke the old key for you — revoke it explicitly when the cutover is done.

#### 5. Use IP whitelisting where the caller has stable egress

`ip_whitelist=[...]` at creation. Enforcement happens inside `verify_api_key`, so it
applies automatically on the dependency path.

#### 6. Run Redis in production

Without Redis, API-key rate limits are not enforced and usage counters are not
tracked. If the key's limits are load-bearing, Redis is a hard requirement.

### Service Token Security

1. **Short lifespan.** Service tokens are stateless JWTs with no deny-list — a leaked
   token is valid until it expires. Keep `expires_days` low; the config caps it at
   `service_token_max_expire_days`.
2. **Internal only.** Never hand one to an external client. External parties get API
   keys, which can be revoked and rate limited.
3. **Minimal permissions.** Permissions are embedded in the token, so a token issued
   with broad permissions keeps them until expiry.
4. **Consider a separate signing key.** `service_token_secret_key` (min 32 chars) lets
   service credentials rotate independently of user JWTs. Left unset, a distinct key
   is derived from `secret_key` for domain separation.

### Permission Security

1. **Least privilege**: grant the minimum permission set.
2. **Prefer specific permissions** over broad ones like `admin:all`.
3. **Scope to entities** where the hierarchy is available.
4. **Treat `is_superuser` as total access**: it bypasses every permission and ABAC
   condition, unconditionally. It is not a "senior admin" role — grant it sparingly
   and audit it.
5. **Enable the audit log** (`enable_audit_log=True`) where permission changes matter.

---

## Summary

### Key Takeaways

1. **Dependencies return dicts.** `ctx["source"]` tells you how the caller authenticated.
2. **`auth.deps` is the entry point**, available after `initialize()` or `prime_fastapi_routing()`.
3. **Three sources**: `jwt`, `api_key`, `service_token`. No superuser or anonymous source.
4. **Composable**: stack dependencies; authentication is memoized per request.
5. **API keys are SHA-256 hashed** — deliberate for a high-entropy secret.
6. **Redis is required** for API-key rate limits and usage counters.

### Quick Reference

```python
# Any authenticated caller
@app.get("/data")
async def get_data(ctx: dict = Depends(auth.deps.require_auth())):
    return {"source": ctx["source"]}

# Permission (any of), or require_all=True for all of
@app.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    ctx: dict = Depends(auth.deps.require_permission("user:delete")),
):
    ...

# Restrict to one source
@app.post("/webhook")
async def webhook(ctx: dict = Depends(auth.deps.require_source("api_key"))):
    ...

# Entity-scoped
@app.put("/entities/{entity_id}")
async def update_entity(
    entity_id: str,
    ctx: dict = Depends(auth.deps.require_entity_permission("entity:update")),
):
    ...

# Create an API key
raw_key, key = await auth.api_key_service.create_api_key(
    session, owner_id=user.id, name="prod_api", scopes=["api:read"]
)
```

---

**Related Documents**:
- [API_DESIGN.md](API_DESIGN.md) - usage examples
- [LIBRARY_ARCHITECTURE.md](LIBRARY_ARCHITECTURE.md) - technical architecture
- [SECURITY.md](SECURITY.md) - security hardening
- [TESTING_GUIDE.md](TESTING_GUIDE.md) - testing strategies
