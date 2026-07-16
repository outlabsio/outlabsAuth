# OutlabsAuth Library - API Design & Developer Experience

**Applies to**: `outlabs-auth` (alpha — the API surface is still settling before 1.0)

This document is a worked-examples companion to the README. The README quickstart is
executed by `tests/unit/test_readme_quickstart.py`, and the two runnable reference
apps are `examples/simple_rbac/main.py` and `examples/enterprise_rbac/main.py`. When
this document and those disagree, they are right.

---

## Table of Contents

1. [Installation](#installation)
2. [Quick Start](#quick-start)
3. [SimpleRBAC Examples](#simplerbac-examples)
4. [EnterpriseRBAC Examples](#enterpriserbac-examples)
   - [Basic Hierarchy](#basic-hierarchy-examples)
   - [Optional Features](#optional-features-examples)
5. [API Key Authentication](#api-key-authentication)
6. [JWT Service Tokens](#jwt-service-tokens)
7. [Multi-Source Authentication](#multi-source-authentication)
8. [FastAPI Integration Patterns](#fastapi-integration-patterns)
9. [Configuration](#configuration)
10. [Testing Your App](#testing-your-app)

---

## Installation

```bash
pip install outlabs-auth
```

You also need a PostgreSQL database reachable from the consuming app. Connection URLs
use the asyncpg driver: `postgresql+asyncpg://user:pass@host:5432/dbname`.

---

## Quick Start

### 5-Minute Quick Start (SimpleRBAC)

```python
# app.py
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from outlabs_auth import SimpleRBAC
from outlabs_auth.routers import get_auth_router, get_users_router

auth = SimpleRBAC(
    database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/myapp",
    # Must be at least 32 characters for HS256, or construction raises.
    #   python -c "import secrets; print(secrets.token_urlsafe(48))"
    secret_key=os.environ["SECRET_KEY"],
)

# Router factories dereference `auth.deps` at call time, and `auth.deps` only
# exists after `initialize()` (async) or `prime_fastapi_routing()` (sync). To
# mount at import time, prime first.
auth.prime_fastapi_routing()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await auth.initialize()  # migrations, Redis, async service wiring
    yield
    await auth.shutdown()


app = FastAPI(lifespan=lifespan)

# Installs the exception handlers AND the UnitOfWork / RequestCache middleware.
# Prefer this over a bare register_exception_handlers(): the middleware commits
# before the response starts, which is what makes a create immediately readable.
auth.instrument_fastapi(app)

app.include_router(get_auth_router(auth, prefix="/auth", tags=["Auth"]))
app.include_router(get_users_router(auth, prefix="/users", tags=["Users"]))

# Run with: uvicorn app:app --reload
```

That gives you registration, login with JWT tokens, refresh, and user management
endpoints without writing a route.

Two things this is deliberate about:

- **`prime_fastapi_routing()` before mounting at import.** Without it, the router
  factories raise `ConfigurationError: Dependencies not initialized`. If you would
  rather mount inside `lifespan()` after `initialize()`, that works and needs no
  priming — see `examples/simple_rbac/main.py`.
- **A real `secret_key`.** Anything under 32 characters is rejected at construction
  for HS256, so a placeholder never reaches the first request.

For production, run migrations explicitly with the packaged CLI (`outlabs-auth
migrate`) rather than `auto_migrate=True`.

### Protecting your own routes

```python
from fastapi import Depends, FastAPI, HTTPException

# Dependencies come from auth.deps (an AuthDeps instance). They return a plain
# dict, not a model: keys include "user", "user_id", "source", and "metadata".
@app.get("/me")
async def read_me(ctx: dict = Depends(auth.deps.require_auth())):
    user = ctx["user"]
    return {"email": user.email, "status": user.status}


@app.delete("/things/{thing_id}")
async def delete_thing(
    thing_id: str,
    ctx: dict = Depends(auth.require_permission("thing:delete")),
):
    # auth.require_permission delegates to auth.deps.require_permission
    return {"deleted": thing_id}
```

---

## SimpleRBAC Examples

Every service method takes an `AsyncSession` as its first argument. The library does
not hold an ambient session for you — you either open one with `auth.get_session()`
or take the request-scoped one via `Depends(auth.uow)` / `Depends(auth.session)`.

### Example 1: Basic User Management

```python
from outlabs_auth import SimpleRBAC

auth = SimpleRBAC(database_url=DATABASE_URL, secret_key=SECRET_KEY)
await auth.initialize()

async with auth.get_session() as session:
    # Create a user
    user = await auth.user_service.create_user(
        session,
        email="john@example.com",
        password="SecurePass123!",
        first_name="John",
        last_name="Doe",
    )

    # Create roles. Note the field is `permission_names`, not `permissions`.
    admin_role = await auth.role_service.create_role(
        session,
        name="admin",
        display_name="Administrator",
        permission_names=[
            "user:read", "user:create", "user:update", "user:delete",
            "role:read", "role:create", "role:update", "role:delete",
        ],
    )

    viewer_role = await auth.role_service.create_role(
        session,
        name="viewer",
        display_name="Viewer",
        permission_names=["user:read", "role:read"],
    )

    # Assign a role to a user (flat RBAC)
    await auth.role_service.assign_role_to_user(
        session,
        user_id=user.id,
        role_id=admin_role.id,
    )

    await session.commit()

# Check a permission — returns a bool
async with auth.get_session() as session:
    allowed = await auth.permission_service.check_permission(
        session,
        user_id=user.id,
        permission="user:delete",
    )
```

### Example 2: Custom Permissions

```python
# Define custom permissions for your domain
CUSTOM_PERMISSIONS = [
    "invoice:create",
    "invoice:approve",
    "invoice:pay",
    "report:view",
    "report:export",
]

async with auth.get_session() as session:
    accountant_role = await auth.role_service.create_role(
        session,
        name="accountant",
        display_name="Accountant",
        permission_names=[
            "invoice:create",
            "invoice:approve",
            "report:view",
            "report:export",
        ],
    )
    await session.commit()

# Use in routes
@app.post("/invoices")
async def create_invoice(
    data: InvoiceCreate,
    ctx: dict = Depends(auth.require_permission("invoice:create")),
):
    return await invoice_service.create(data)


@app.post("/invoices/{invoice_id}/approve")
async def approve_invoice(
    invoice_id: str,
    ctx: dict = Depends(auth.require_permission("invoice:approve")),
):
    return await invoice_service.approve(invoice_id, ctx["user_id"])
```

### Example 3: Multiple Permission Checks

`require_permission` accepts several permissions. By default the check passes if
**any** of them match; pass `require_all=True` to demand all of them.

```python
# Require ANY of the permissions (default)
@app.get("/reports/{report_id}")
async def get_report(
    report_id: str,
    ctx: dict = Depends(auth.deps.require_permission("report:view", "report:export")),
):
    return await report_service.get(report_id)


# Require ALL permissions
@app.delete("/users/{user_id}/complete")
async def complete_delete_user(
    user_id: str,
    ctx: dict = Depends(
        auth.deps.require_permission("user:delete", "user:purge", require_all=True)
    ),
):
    return {"message": "User completely removed"}
```

Outside of a route, `permission_service` has imperative equivalents that raise
`PermissionDeniedError` instead of returning a bool:

```python
async with auth.get_session() as session:
    await auth.permission_service.require_any_permission(
        session, user_id=user.id, permissions=["report:view", "report:export"]
    )
    await auth.permission_service.require_all_permissions(
        session, user_id=user.id, permissions=["user:delete", "user:purge"]
    )
```

---

## EnterpriseRBAC Examples

### Basic Hierarchy Examples

EnterpriseRBAC forces `enable_entity_hierarchy=True`. Everything from SimpleRBAC still
applies; entities add a tree to scope permissions against.

#### Example 1: Creating Entity Hierarchy

```python
from outlabs_auth import EnterpriseRBAC
from outlabs_auth.models.sql.enums import EntityClass

auth = EnterpriseRBAC(database_url=DATABASE_URL, secret_key=SECRET_KEY)
await auth.initialize()

async with auth.get_session() as session:
    company = await auth.entity_service.create_entity(
        session,
        name="acme_corp",
        display_name="ACME Corporation",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="company",
    )

    engineering = await auth.entity_service.create_entity(
        session,
        name="engineering",
        display_name="Engineering Department",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="department",
        parent_id=company.id,
    )

    backend_team = await auth.entity_service.create_entity(
        session,
        name="backend_team",
        display_name="Backend Team",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="team",
        parent_id=engineering.id,
    )

    # Access groups are cross-cutting rather than structural
    admins_group = await auth.entity_service.create_entity(
        session,
        name="company_admins",
        display_name="Company Administrators",
        entity_class=EntityClass.ACCESS_GROUP,
        entity_type="admin_group",
        parent_id=company.id,
    )

    await session.commit()
```

#### Example 2: Entity Memberships with Roles

```python
async with auth.get_session() as session:
    dept_manager_role = await auth.role_service.create_role(
        session,
        name="department_manager",
        display_name="Department Manager",
        permission_names=[
            "entity:read",
            "entity:update",
            "entity:read_tree",      # Can read all sub-entities
            "entity:create_tree",    # Can create sub-entities
            "user:read",
            "user:read_tree",
            "user:manage_tree",
        ],
        assignable_at_types=["department"],
    )

    await auth.membership_service.add_member(
        session,
        entity_id=engineering.id,
        user_id=user.id,
        role_ids=[dept_manager_role.id],
    )
    await session.commit()
```

#### Example 3: Tree Permissions in Routes

```python
# Permission required in one specific entity
@app.get("/entities/{entity_id}/details")
async def get_entity_details(
    entity_id: str,
    ctx: dict = Depends(auth.require_entity_permission("entity:read", "entity_id")),
):
    ...

# Tree permission — grants access across descendants.
# require_tree_permission checks the "<permission>_tree" variant of the permission
# in the named entity or any of its ancestors.
@app.post("/entities/{parent_id}/sub-entities")
async def create_sub_entity(
    parent_id: str,
    data: EntityCreate,
    ctx: dict = Depends(auth.require_tree_permission("entity:create", "parent_id")),
):
    ...
```

#### Example 4: Get a User's Accessible Entities

```python
@app.get("/my-entities")
async def get_my_entities(
    ctx: dict = Depends(auth.deps.require_auth()),
    session: AsyncSession = Depends(auth.session),
):
    entities = await auth.membership_service.get_user_entities(
        session, user_id=ctx["user"].id
    )
    return entities
```

To list every permission a user holds, use `permission_service.get_user_permissions`:

```python
perms: list[str] = await auth.permission_service.get_user_permissions(
    session, user_id=user.id
)
```

---

### Optional Features Examples

These are opt-in feature flags on EnterpriseRBAC. SimpleRBAC force-disables all three.

#### Example 1: Context-Aware Roles

```python
auth = EnterpriseRBAC(
    database_url=DATABASE_URL,
    secret_key=SECRET_KEY,
    enable_context_aware_roles=True,
)
```

With the flag on, a role can carry different permissions depending on the entity type
it is assigned at, via `entity_type_permissions` on `role_service.create_role`, and be
restricted to certain levels with `assignable_at_types`.

#### Example 2: ABAC Conditions

```python
auth = EnterpriseRBAC(
    database_url=DATABASE_URL,
    secret_key=SECRET_KEY,
    enable_abac=True,
)
```

ABAC attaches conditions to a permission. Conditions are created explicitly against a
permission via `permission_service.create_permission_condition_group` and
`permission_service.create_permission_condition`, then evaluated by
`check_permission` when you pass resource attributes:

```python
async with auth.get_session() as session:
    allowed: bool = await auth.permission_service.check_permission(
        session,
        user_id=user.id,
        permission="invoice:approve",
        entity_id=entity.id,
        resource_context={
            "amount": 35000,
            "status": "pending_approval",
            "department": "finance",
        },
    )

    if not allowed:
        raise HTTPException(403, "Permission denied")
```

`check_permission` returns a plain `bool`. To capture why a decision came out the way
it did, pass a `capture` dict — the engine fills it in place.

In a route, prefer the dependency, which resolves the resource attributes for you via
a `resource_context_provider`:

```python
@app.post("/invoices/{invoice_id}/approve")
async def approve_invoice(
    invoice_id: str,
    ctx: dict = Depends(
        auth.deps.require_permission(
            "invoice:approve",
            resource_context_provider=load_invoice_attributes,
        )
    ),
):
    ...
```

#### Example 3: Caching

Providing `redis_url` turns on Redis-backed API-key counters, rate limits, and the
permission cache (`enable_caching` defaults to whether Redis is enabled).

```python
auth = EnterpriseRBAC(
    database_url=DATABASE_URL,
    secret_key=SECRET_KEY,
    redis_url="redis://localhost:6379",
    redis_key_prefix="myapp:production",  # required namespace when Redis is on
    cache_ttl_seconds=300,
)
```

Caching is managed by the library — `check_permission` has no `use_cache` parameter.
Within a single request, `RequestCacheMiddleware` (installed by
`instrument_fastapi()`) memoizes repeated permission checks.

---

## API Key Authentication

API keys authenticate external integrations and automated systems. They are a core
feature, not an optional extension.

### Example 1: Creating API Keys

```python
async with auth.get_session() as session:
    service_user = await auth.user_service.create_user(
        session,
        email="service@example.com",
        password="SecurePass123!",
    )

    raw_key, api_key = await auth.api_key_service.create_api_key(
        session,
        owner_id=service_user.id,
        name="Production Service",
        scopes=["user:read", "entity:read"],
        ip_whitelist=["10.0.1.0/24", "192.168.1.100"],
        rate_limit_per_minute=60,
        expires_in_days=90,
        prefix_type="sk_live",
    )
    await session.commit()

# raw_key is only returned once — store it securely.
print(raw_key)  # sk_live_<64 hex chars>
```

Everything after `session` is keyword-only. Exactly one of `owner_id` or
`integration_principal_id` identifies who the key belongs to.

**How keys are stored**: the full key is hashed with SHA-256 and only the hash is
persisted. The first 16 characters (`prefix`) are stored in the clear for
identification. SHA-256 — rather than a password hash like argon2id — is the
deliberate choice here: an API key is 32 bytes of CSPRNG output, so it has no
brute-forceable structure and a slow hash would only add latency to every request.

### Example 2: API Keys for Different Environments

```python
prod_key, _ = await auth.api_key_service.create_api_key(
    session,
    owner_id=user.id,
    name="Production API",
    scopes=["user:read", "entity:read"],
    ip_whitelist=["10.0.1.0/24"],
    rate_limit_per_minute=60,
    prefix_type="sk_live",
)

test_key, _ = await auth.api_key_service.create_api_key(
    session,
    owner_id=user.id,
    name="Test API",
    scopes=["user:read", "user:create", "entity:read"],
    ip_whitelist=None,
    rate_limit_per_minute=120,
    prefix_type="sk_test",
)
```

`prefix_type` is free-form and is simply the literal prefix on the generated key —
use it to tell environments apart.

### Example 3: Using API Keys in Routes

You do not have to verify keys by hand. The API-key backend is part of the normal
authentication chain, so `require_auth()` and `require_permission()` already accept
an API key on the `X-API-Key` header, and enforce scope, IP whitelist, and rate
limits for you.

```python
@app.get("/api/users")
async def list_users(
    ctx: dict = Depends(auth.require_permission("user:read")),
    session: AsyncSession = Depends(auth.session),
):
    # Works for a user JWT or an API key. Check which one was used:
    if ctx["source"] == "api_key":
        ...
    return await auth.user_service.list_users(session)


# Restrict an endpoint to API keys only
@app.post("/webhook")
async def webhook(ctx: dict = Depends(auth.deps.require_source("api_key"))):
    return {"received": True}
```

If you do need the primitive, it is `verify_api_key`, which returns a
`(APIKey | None, usage_count)` tuple rather than raising:

```python
api_key, usage = await auth.api_key_service.verify_api_key(
    session,
    api_key_string=raw_key,
    required_scope="user:read",
    ip_address=request.client.host,
)
if api_key is None:
    raise HTTPException(401, "Invalid API key")
```

### Example 4: API Key Management Endpoints

The library ships these as router factories — mount them instead of writing the CRUD:

```python
from outlabs_auth.routers import get_api_keys_router, get_api_key_admin_router

# Self-service: callers manage their own keys
app.include_router(get_api_keys_router(auth, prefix="/api-keys", tags=["API Keys"]))

# Admin: manage keys across owners
app.include_router(
    get_api_key_admin_router(auth, prefix="/admin/api-keys", tags=["API Key Admin"])
)
```

The underlying service methods, if you want your own routes:

```python
async with auth.get_session() as session:
    # Rotate — returns (new_raw_key, new_key)
    new_raw_key, new_key = await auth.api_key_service.rotate_api_key(
        session, key_id=key_id, actor_user_id=user.id
    )

    # Revoke
    await auth.api_key_service.revoke_api_key(
        session,
        key_id=key_id,
        actor_user_id=user.id,
        reason="Revoked by administrator",
    )
    await session.commit()
```

### Example 5: Entity-Scoped API Keys (EnterpriseRBAC)

```python
raw_key, api_key = await auth.api_key_service.create_api_key(
    session,
    owner_id=user.id,
    name="Engineering Service",
    scopes=["entity:read", "entity:update", "user:read"],
    entity_id=dept.id,          # Scope the key to one entity
    inherit_from_tree=True,     # ...and its descendants
)
```

Enforcement is automatic: pass `entity_id` to `verify_api_key`, or use
`auth.require_entity_permission(...)` on the route and the API-key path checks the
key's entity scope as part of the permission check.

### Example 6: Client-Side API Key Usage

```python
# Python client
import httpx

response = httpx.get(
    "https://api.example.com/api/users",
    headers={"X-API-Key": "sk_live_..."},
)
```

```javascript
// JavaScript client
fetch('https://api.example.com/api/users', {
  headers: { 'X-API-Key': 'sk_live_...' }
})
  .then(response => response.json())
  .then(users => console.log(users));
```

```bash
# cURL
curl -X GET https://api.example.com/api/users \
  -H "X-API-Key: sk_live_..."
```

---

## JWT Service Tokens

Service tokens are self-contained JWTs for internal service-to-service calls. They
embed their permissions, so validating one costs a signature check and no database
round trip.

### Example 1: Creating a Service Token

`ServiceTokenService` is synchronous and stateless — it signs and validates, it does
not touch the database.

```python
token: str = auth.service_token_service.create_service_token(
    service_id="payment-processor",
    service_name="Payment Processor",
    permissions=["invoice:read", "invoice:update", "payment:create"],
    expires_days=30,
    metadata={"environment": "prod"},
)
```

`expires_days` must be between 1 and `service_token_max_expire_days`, or it raises
`ValueError`. Convenience wrappers exist for common shapes:
`create_api_service_token` and `create_worker_service_token`.

Service tokens are signed with a key derived from `secret_key` for domain separation.
Set `service_token_secret_key` explicitly (min 32 characters) if you want to rotate
service credentials independently of user JWTs.

### Example 2: Consuming a Service Token

```python
# Caller — service tokens travel on the standard Authorization: Bearer header,
# the same transport as user JWTs.
import httpx

httpx.post(
    "https://service-b.example.com/api/process-payment",
    headers={"Authorization": f"Bearer {token}"},
    json={"invoice_id": "inv_123", "amount": 1000},
)

# Receiver — restrict the endpoint to service tokens
@app.post("/api/process-payment")
async def process_payment(
    data: dict,
    ctx: dict = Depends(auth.deps.require_source("service_token")),
):
    # For a service token, ctx["user"] and ctx["user_id"] are None. The context
    # instead carries "service_id" and "service_name", with the full JWT payload
    # (including any metadata you embedded) under ctx["metadata"].
    return {"processed_by": ctx["service_name"]}
```

To require a permission rather than just the source, use
`auth.require_permission("payment:create")` — the service-token path resolves the
permission from the token payload with no database lookup.

### Example 3: API Keys vs Service Tokens

| | API Keys | JWT Service Tokens |
|---|---|---|
| Use for | External integrations, third-party services | Internal microservices |
| Storage | Postgres row, SHA-256 hash of the key | None — stateless JWT |
| Validation | DB lookup + hash compare (Redis-cached snapshot on the hot path) | Signature verification only |
| Lifespan | Long-lived, optional expiry | Short-lived (`expires_days`, capped by config) |
| Rotation | `rotate_api_key()` | Mint a new token |
| Revocation | Immediate, via `revoke_api_key()` | Not revocable before expiry — keep them short |
| Rate limiting | Per-key limits, enforced by the library | Not rate limited by the library |

The revocation row is the reason to keep service-token lifetimes short: there is no
deny-list, so a leaked token is valid until it expires.

### Best Practices

1. **Short lifespan**: service tokens cannot be revoked — keep `expires_days` low.
2. **Internal only**: never hand a service token to an external client.
3. **Minimal permissions**: embed only what the calling service needs.
4. **Use API keys for external parties**: they can be revoked and rate limited.

---

## Multi-Source Authentication

A single dependency accepts every configured credential type. The backends are tried
in order and the first one that produces a result wins.

Three backends are wired, in this order:

| Source (`ctx["source"]`) | Transport | Wired when |
|---|---|---|
| `jwt` | `Authorization: Bearer <token>` | always |
| `api_key` | `X-API-Key: sk_live_...` | an API-key service exists |
| `service_token` | `Authorization: Bearer <token>` | a service-token service exists |

User JWTs and service tokens share the `Authorization: Bearer` header. They are told
apart by their payloads: the JWT backend is tried first, and a service token falls
through it to the service-token backend.

There is no "superuser" or "anonymous" source. A superuser is an ordinary `jwt`-
authenticated user with `is_superuser=True` on their record — which is what
`require_superuser()` checks. Anonymous access is expressed by
`require_auth(optional=True)` returning `None`, not by an anonymous context.

Note that `is_superuser=True` bypasses every permission check unconditionally —
`check_permission` returns `True` before evaluating roles or ABAC conditions, and
`get_user_permissions` returns `["*:*"]`. It is total access, not a senior role.

### Example 1: Basic Multi-Source Setup

Dependencies return a **plain dict**, not a context object. Its keys:

- `user` — the `User` model, or `None` for service tokens and principal-owned API keys
- `user_id` — string UUID, or `None`
- `source` — `"jwt"`, `"api_key"`, or `"service_token"`
- `metadata` — the JWT payload, or API-key metadata
- `api_key` — the `APIKey` model (API-key source only)
- `integration_principal_id` — set when an API key belongs to a principal, not a user
- `service_id`, `service_name` — service-token source only

Not every key is present on every source, so reach for `.get()` when you are handling
more than one.

```python
@app.get("/api/users")
async def list_users(ctx: dict = Depends(auth.deps.require_auth())):
    """Accepts a user JWT, an API key, or a service token."""
    if ctx["source"] == "jwt":
        print(f"Authenticated as user: {ctx['user_id']}")
    elif ctx["source"] == "api_key":
        print(f"Authenticated with API key: {ctx['api_key'].prefix}")
    elif ctx["source"] == "service_token":
        print(f"Authenticated as service: {ctx['service_name']}")

    return {"source": ctx["source"]}
```

### Example 2: Optional and Filtered Authentication

```python
# Optional — returns None instead of raising 401 when no credentials are present
@app.get("/public")
async def public(ctx: dict | None = Depends(auth.deps.require_auth(optional=True))):
    if ctx is None:
        return await get_public_data()
    return await get_personalized_data(ctx["user_id"])


# Require a verified email
@app.post("/comments")
async def comment(ctx: dict = Depends(auth.deps.require_auth(verified=True))):
    ...


# Restrict to one source
@app.post("/internal/job")
async def run_job(ctx: dict = Depends(auth.deps.require_source("service_token"))):
    ...


# Superuser only
@app.post("/system/dangerous")
async def dangerous(ctx: dict = Depends(auth.deps.require_superuser())):
    ...
```

`require_auth()` takes `active` (default `True`, requires the user to be able to
authenticate), `verified` (default `False`, requires a verified email), and `optional`
(default `False`).

### Example 3: Permission Checking Across Sources

`require_permission` works the same whichever source authenticated the request — a
user's permissions come from their roles, an API key's from its scopes, a service
token's from its payload.

```python
@app.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    ctx: dict = Depends(auth.deps.require_permission("user:delete")),
):
    ...

# Both permissions required
@app.post("/admin/reset")
async def reset(
    ctx: dict = Depends(
        auth.deps.require_permission("admin:reset", "admin:confirm", require_all=True)
    ),
):
    ...

# Either permission is enough (the default)
@app.get("/reports/{report_id}")
async def get_report(
    report_id: str,
    ctx: dict = Depends(auth.deps.require_permission("report:view", "report:export")),
):
    ...
```

### Example 4: Using the Context in Business Logic

Because the context is a dict, business logic can take it without importing anything
from the library:

```python
async def approve_invoice(session, invoice_id: str, ctx: dict):
    invoice = await invoice_service.get(session, invoice_id)

    allowed = await auth.permission_service.check_permission(
        session,
        user_id=UUID(ctx["user_id"]) if ctx["user_id"] else None,
        permission="invoice:approve",
    )
    if not allowed:
        raise PermissionDeniedError("Cannot approve invoice")

    return await invoice_service.approve(session, invoice_id, ctx["user_id"])


@app.post("/invoices/{invoice_id}/approve")
async def approve_invoice_endpoint(
    invoice_id: str,
    ctx: dict = Depends(auth.deps.require_auth()),
    session: AsyncSession = Depends(auth.uow),
):
    return await approve_invoice(session, invoice_id, ctx)
```

---

## FastAPI Integration Patterns

### Pattern 1: Global Auth Instance

The auth instance is a long-lived object that owns an engine and a connection pool.
Build exactly one, at import, and reuse it.

```python
# app/core/auth.py
import os
from outlabs_auth import EnterpriseRBAC

auth = EnterpriseRBAC(
    database_url=os.environ["DATABASE_URL"],
    secret_key=os.environ["SECRET_KEY"],
)
auth.prime_fastapi_routing()

# app/api/routes/users.py
from app.core.auth import auth

@router.get("/users/me")
async def get_me(ctx: dict = Depends(auth.deps.require_auth())):
    return ctx["user"]
```

Do **not** construct the auth instance inside a FastAPI dependency — that would build
a new engine and pool per request.

### Pattern 2: Getting a Session in Your Own Routes

Two dependencies, with different transaction semantics:

```python
from sqlalchemy.ext.asyncio import AsyncSession

# auth.session — a plain session. You commit.
@app.get("/things")
async def list_things(session: AsyncSession = Depends(auth.session)):
    return await thing_service.list(session)


# auth.uow — unit of work. Commits automatically on success for write methods
# (POST/PUT/PATCH/DELETE), rolls back on error. Requires instrument_fastapi(app),
# which installs the middleware that commits before the response is sent.
@app.post("/things")
async def create_thing(
    data: ThingCreate,
    session: AsyncSession = Depends(auth.uow),
    ctx: dict = Depends(auth.deps.require_auth()),
):
    return await thing_service.create(session, data, owner_id=ctx["user_id"])
```

Prefer `auth.uow` for writes: it commits before the response starts, so a client that
immediately reads back what it just created does not race the commit.

### Pattern 3: Combining Requirements

Stack dependencies — each is checked independently.

```python
@app.post("/entities/{entity_id}/admin/action")
async def complex_action(
    entity_id: str,
    ctx: dict = Depends(auth.require_entity_permission("admin:write", "entity_id")),
    _user_only: dict = Depends(auth.deps.require_source("jwt")),
):
    return {"performed": True}
```

Authentication is memoized on `request.state` for default-parameter dependencies, so
two dependencies on one route do not authenticate twice.

### Pattern 4: Resource Ownership

The library authorizes against users, roles, entities, and ABAC attributes. Row-level
ownership ("is this *your* invoice?") is your app's concern — do it in the handler,
or feed the resource attributes into ABAC via a `resource_context_provider`.

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
            session, user_id=invoice.owner_id, permission="invoice:admin"
        )
        if not allowed:
            raise HTTPException(403, "Not the owner")

    return await invoice_service.update(session, invoice, data)
```

---

## Configuration

Configuration is passed as keyword arguments to the preset constructor. The preset
builds its own `AuthConfig` internally — there is **no** `config=` parameter.

### SimpleRBAC Configuration

```python
from outlabs_auth import SimpleRBAC

auth = SimpleRBAC(
    database_url="postgresql+asyncpg://user:pass@localhost:5432/mydb",

    # JWT settings
    secret_key=os.environ["SECRET_KEY"],  # >= 32 chars for HS256
    algorithm="HS256",
    access_token_expire_minutes=15,
    refresh_token_expire_days=30,

    # Password requirements
    password_min_length=8,
    require_special_char=True,
    require_uppercase=True,
    require_digit=True,

    # Security
    max_login_attempts=5,
    lockout_duration_minutes=30,
)
```

SimpleRBAC force-disables `enable_entity_hierarchy`, `enable_context_aware_roles`, and
`enable_abac`; passing them is ignored rather than an error.

### EnterpriseRBAC Configuration

```python
from outlabs_auth import EnterpriseRBAC

auth = EnterpriseRBAC(
    database_url=os.environ["DATABASE_URL"],
    secret_key=os.environ["SECRET_KEY"],

    # Entity settings (hierarchy is always on for this preset)
    max_entity_depth=5,
    allowed_entity_types=["company", "department", "team", "project"],
    allow_access_groups=True,

    # Optional features
    enable_context_aware_roles=True,
    enable_abac=True,
    enable_audit_log=True,

    # Redis: counters, rate limits, permission cache
    redis_url="redis://localhost:6379/0",
    redis_key_prefix="myapp:production",  # required when Redis is enabled
    cache_ttl_seconds=300,
)
```

`SimpleConfig` and `EnterpriseConfig` are exported and are the Pydantic models behind
`auth.config`. Read them to discover defaults and field docs; they are not an input to
the constructor.

### Environment-Based Configuration

```python
# app/core/auth.py
import os
from outlabs_auth import SimpleRBAC

auth = SimpleRBAC(
    database_url=os.environ["DATABASE_URL"],
    secret_key=os.environ["SECRET_KEY"],
    access_token_expire_minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE", "15")),
    redis_url=os.getenv("REDIS_URL"),
    redis_key_prefix=os.getenv("REDIS_KEY_PREFIX"),
    auto_migrate=False,
)
```

### Production Defaults

- Keep `auto_migrate=False` and run `outlabs-auth migrate` as a deploy step.
- Use a dedicated schema: `database_schema="outlabs_auth"`.
- Provide Redis for API-key counters, rate limits, and the permission cache.
- Mount the library under an app-owned prefix such as `/iam`.
- `background_job_mode` defaults to `"disabled"`; only set `"embedded"` for
  single-process development.

---

## Testing Your App

Tests need a real PostgreSQL database — the library is Postgres-only and the schema is
managed by Alembic. See `docs/TESTING_GUIDE.md` for the full harness.

### Test Fixtures

```python
# conftest.py
import pytest_asyncio
from outlabs_auth import SimpleRBAC


@pytest_asyncio.fixture
async def auth(postgres_url):
    auth = SimpleRBAC(
        database_url=postgres_url,
        secret_key="test-secret-key-at-least-32-characters-long",
        auto_migrate=True,
    )
    await auth.initialize()
    yield auth
    await auth.shutdown()


@pytest_asyncio.fixture
async def test_user(auth):
    async with auth.get_session() as session:
        user = await auth.user_service.create_user(
            session,
            email="test@example.com",
            password="Test123!@#",
        )
        await session.commit()
        return user


@pytest_asyncio.fixture
async def admin_user(auth):
    async with auth.get_session() as session:
        user = await auth.user_service.create_user(
            session,
            email="admin@example.com",
            password="Admin123!@#",
        )
        admin_role = await auth.role_service.create_role(
            session,
            name="admin",
            display_name="Administrator",
            permission_names=["user:create", "user:delete", "role:manage"],
        )
        await auth.role_service.assign_role_to_user(
            session, user_id=user.id, role_id=admin_role.id
        )
        await session.commit()
        return user


@pytest_asyncio.fixture
async def auth_headers(auth, test_user):
    async with auth.get_session() as session:
        user, tokens = await auth.auth_service.login(
            session, email="test@example.com", password="Test123!@#"
        )
        await session.commit()
    return {"Authorization": f"Bearer {tokens.access_token}"}
```

Note `auth_service.login` returns a `(User, TokenPair)` tuple.

### Unit Tests

```python
import pytest


@pytest.mark.asyncio
async def test_user_can_login(auth, test_user):
    async with auth.get_session() as session:
        user, tokens = await auth.auth_service.login(
            session, email="test@example.com", password="Test123!@#"
        )
    assert tokens.access_token
    assert tokens.refresh_token


@pytest.mark.asyncio
async def test_user_with_permission_can_access(auth, admin_user):
    async with auth.get_session() as session:
        allowed = await auth.permission_service.check_permission(
            session, user_id=admin_user.id, permission="user:delete"
        )
    assert allowed is True


@pytest.mark.asyncio
async def test_user_without_permission_cannot_access(auth, test_user):
    async with auth.get_session() as session:
        allowed = await auth.permission_service.check_permission(
            session, user_id=test_user.id, permission="user:delete"
        )
    assert allowed is False
```

### Overriding Auth in Route Tests

Because dependencies return plain dicts, faking one is just returning a dict:

```python
def override_auth(app, user, source="jwt", permissions=None):
    dependency = auth.deps.require_auth()

    async def _fake():
        return {
            "user": user,
            "user_id": str(user.id),
            "source": source,
            "metadata": {},
        }

    app.dependency_overrides[dependency] = _fake
```

Override the exact dependency object you mounted the route with — `require_auth()`
builds a new function each call, so keep a reference to the one the route uses.

### Integration Tests

```python
from fastapi.testclient import TestClient


def test_protected_route_requires_auth(client: TestClient):
    response = client.get("/users/me")
    assert response.status_code == 401


def test_protected_route_with_valid_token(client: TestClient, auth_headers):
    response = client.get("/users/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"


def test_permission_required_route(client: TestClient, auth_headers):
    response = client.delete("/users/other-user-id", headers=auth_headers)
    assert response.status_code == 403
```

---

## Best Practices

### 1. Always Use Environment Variables for Secrets

```python
# Bad
auth = SimpleRBAC(database_url=DB_URL, secret_key="hardcoded-secret")

# Good
auth = SimpleRBAC(database_url=DB_URL, secret_key=os.environ["SECRET_KEY"])
```

The 32-character minimum for HS256 is enforced at construction, so a short
placeholder fails fast rather than at first login.

### 2. Initialize Once, in the Lifespan

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await auth.initialize()
    yield
    await auth.shutdown()
```

`initialize()` is idempotent and does the async work — migrations (if
`auto_migrate=True`), Redis connections, service wiring. `shutdown()` closes the pool
and stops background jobs. If you mount routers at import, call
`prime_fastapi_routing()` first.

### 3. Use `instrument_fastapi`, Not Just the Exception Handlers

```python
# Handlers only — no UnitOfWork or RequestCache middleware
from outlabs_auth import register_exception_handlers
register_exception_handlers(app)

# Handlers AND middleware
auth.instrument_fastapi(app)
```

Call it before the app starts serving; middleware cannot be added afterwards.

### 4. Use Specific Permissions

```python
# Avoid overly broad permissions
permission_names = ["admin:all"]

# Prefer specific ones
permission_names = ["user:read", "user:create", "user:update", "role:manage"]
```

### 5. Let the Library's Exceptions Surface

Library exceptions subclass `OutlabsAuthException` and carry their own status code and
response shape. With `instrument_fastapi(app)` installed, they are rendered
consistently — do not wrap service calls in a bare `except Exception`.

```python
@app.post("/users")
async def create_user(
    data: UserCreate,
    session: AsyncSession = Depends(auth.uow),
):
    # UserAlreadyExistsError, InvalidInputError, etc. become correct HTTP
    # responses via the registered handlers.
    return await auth.user_service.create_user(
        session, email=data.email, password=data.password
    )
```

---

## Next Steps

- [DEPENDENCY_PATTERNS.md](DEPENDENCY_PATTERNS.md) - `AuthDeps` in depth
- [COMPARISON_MATRIX.md](COMPARISON_MATRIX.md) - choosing a preset
- [TESTING_GUIDE.md](TESTING_GUIDE.md) - testing strategies
- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) - running it in production
- `examples/simple_rbac/main.py`, `examples/enterprise_rbac/main.py` - runnable apps
