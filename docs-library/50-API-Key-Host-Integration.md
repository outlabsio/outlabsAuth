# 50. API Key Host Integration

This guide describes the supported API key integration surface for host
applications embedding OutlabsAuth.

The short version:

- use mounted routers for API key management APIs
- use `auth.authorize_api_key(...)` for custom host-side runtime checks
- do not build host integrations around direct DB reads or raw primitive
  service calls

## Current Status

As of 2026-04-06, the backend integration surface is implemented for:

- `personal` user-owned API keys
- EnterpriseRBAC `system_integration` API keys owned by
  `IntegrationPrincipal`
- host-side runtime authorization through `auth.authorize_api_key(...)`

What is already in place:

- the self-service router for `personal` keys
- the Enterprise integration-principal admin router for durable
  `system_integration` keys
- the entity inventory router for anchored-key listing and incident response
- owner-aware runtime authorization
- derived effectiveness fields on API key responses
- auth-owned observability for API key policy, validation, and lifecycle events
- the reference `OutlabsAuthUI` workspace for integration principals,
  system keys, and anchored-key inventory

What is still outside the backend surface:

- host-product-specific onboarding and operator workflows beyond the reference UI
- product-specific scope allowlists and naming conventions layered on top of
  the shared auth model

## Current Backend Test Position

The backend surface described in this guide is already covered by focused
Python tests in:

- `tests/integration/test_api_key_admin_endpoints.py`
- `tests/integration/test_api_key_lifecycle.py`
- `tests/integration/test_api_keys_router_callback_paths.py`
- `tests/integration/test_enterprise_api_key_policy_matrix.py`
- `tests/unit/services/test_api_key_service.py`
- `tests/unit/test_auth_core_lifecycle.py`
- `tests/unit/test_auth_deps_permission_sources.py`
- `tests/unit/authentication/test_strategy.py`
- `tests/unit/observability/test_observability_integration.py`

The main remaining backend test work after the current UI reference slice is:

- exhaust the remaining denial branches through the admin HTTP surface
- add route-flow observability assertions for the new admin/runtime API key
  paths
- add more pagination, search, and filter edge-case coverage
- add more admin-created key IP-whitelist and rate-limit edge-case coverage

## Current UI and E2E Position

The reference `OutlabsAuthUI` workspace now covers the main EnterpriseRBAC
operator flows in:

- `../OutlabsAuthUI/e2e/api-keys/api-keys-workspace.spec.ts`
- `../OutlabsAuthUI/e2e/api-keys/api-keys-persona-access.spec.ts`

That coverage currently proves:

- admin happy-path lifecycle for entity-scoped and platform-global integrations
- root-scoped, hierarchy-scoped, and entity-only admin personas
- direct API lifecycle checks with bearer tokens for the acting personas
- runtime `X-API-Key` use against a path-scoped host route
- post-revoke runtime denial
- read-only persona denial in both UI and direct API paths

## Supported Surfaces

### 1. Self-Service API Key Router

For owner-managed API key CRUD, mount:

```python
from outlabs_auth.routers import get_api_keys_router

app.include_router(
    get_api_keys_router(auth, prefix="/v1/api-keys"),
)
```

This is the supported self-service surface for:

- listing a user's own API keys
- creating user-owned API keys
- reading one key
- updating one key
- revoking one key
- rotating one key

### 2. Integration-Principal Admin Router

For EnterpriseRBAC admin products that need durable non-human integrations,
mount:

```python
from outlabs_auth.routers import get_integration_principals_router

app.include_router(
    get_integration_principals_router(auth, prefix="/v1/admin"),
)
```

This is the supported admin surface for `system_integration` keys.

Entity-scoped routes:

- `GET /entities/{entity_id}/integration-principals`
- `POST /entities/{entity_id}/integration-principals`
- `GET /entities/{entity_id}/integration-principals/{principal_id}`
- `PATCH /entities/{entity_id}/integration-principals/{principal_id}`
- `DELETE /entities/{entity_id}/integration-principals/{principal_id}`
- `GET /entities/{entity_id}/integration-principals/{principal_id}/api-keys`
- `POST /entities/{entity_id}/integration-principals/{principal_id}/api-keys`
- `GET /entities/{entity_id}/integration-principals/{principal_id}/api-keys/{key_id}`
- `PATCH /entities/{entity_id}/integration-principals/{principal_id}/api-keys/{key_id}`
- `DELETE /entities/{entity_id}/integration-principals/{principal_id}/api-keys/{key_id}`
- `POST /entities/{entity_id}/integration-principals/{principal_id}/api-keys/{key_id}/rotate`

Platform-global superuser routes:

- `GET /system/integration-principals`
- `POST /system/integration-principals`
- `GET /system/integration-principals/{principal_id}`
- `PATCH /system/integration-principals/{principal_id}`
- `DELETE /system/integration-principals/{principal_id}`
- `GET /system/integration-principals/{principal_id}/api-keys`
- `POST /system/integration-principals/{principal_id}/api-keys`
- `GET /system/integration-principals/{principal_id}/api-keys/{key_id}`
- `PATCH /system/integration-principals/{principal_id}/api-keys/{key_id}`
- `DELETE /system/integration-principals/{principal_id}/api-keys/{key_id}`
- `POST /system/integration-principals/{principal_id}/api-keys/{key_id}/rotate`

### 3. Entity Inventory and Incident-Response Router

For EnterpriseRBAC inventory and incident response across keys anchored to an
entity, mount:

```python
from outlabs_auth.routers import get_api_key_admin_router

app.include_router(
    get_api_key_admin_router(auth, prefix="/v1/admin/entities"),
)
```

This surface is intentionally inventory-only plus revoke:

- `GET /{entity_id}/api-keys`
- `GET /{entity_id}/api-keys/{key_id}`
- `DELETE /{entity_id}/api-keys/{key_id}`

The list route supports pagination plus `owner_id`, `status`, `key_kind`, and
`search` filters, and includes both personal and integration-principal-owned
keys anchored to the entity.

Responses include derived runtime state:

- `owner_id`
- `owner_type`
- `is_currently_effective`
- `ineffective_reasons`

That lets host products render “stored but currently ineffective” keys without
inventing their own runtime policy evaluation.

### 4. Runtime Authorization Helper

For host-defined routes that need to accept API keys directly, use:

```python
auth_result = await auth.authorize_api_key(
    session,
    api_key_string,
    required_scope="contacts:read",
    entity_id=entity_id,
    ip_address=client_ip,
)
```

This is the supported in-process boundary for runtime API key authorization.

It returns `None` when the key should not be allowed, or an auth result shaped
like the packaged API key backend.

Personal-key example:

```python
{
    "user": user,
    "user_id": "...",
    "source": "api_key",
    "api_key": api_key_model,
    "metadata": {
        "key_id": "...",
        "key_prefix": "sk_live_...",
        "key_kind": "personal",
        "scopes": [...],
        "usage_count": 7,
        "entity_id": "...",
        "is_currently_effective": True,
        "ineffective_reasons": [],
    },
}
```

Principal-backed `system_integration` keys resolve differently:

```python
{
    "user": None,
    "user_id": None,
    "integration_principal": principal,
    "integration_principal_id": "...",
    "source": "api_key",
    "api_key": api_key_model,
    "metadata": {
        "key_id": "...",
        "key_prefix": "sk_live_...",
        "key_kind": "system_integration",
        "owner_type": "integration_principal",
        "scopes": [...],
        "principal_allowed_scopes": [...],
        "entity_id": "...",
    },
}
```

## Recommended Host Pattern

For custom host routes:

```python
from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession


@router.get("/contacts/{entity_id}")
async def list_contacts(
    entity_id: UUID,
    request: Request,
    session: AsyncSession = Depends(auth.uow),
):
    api_key = request.headers.get("X-API-Key")
    auth_result = await auth.authorize_api_key(
        session,
        api_key,
        required_scope="contacts:read",
        entity_id=entity_id,
        ip_address=request.client.host if request.client else None,
    )
    if auth_result is None:
        raise HTTPException(status_code=401, detail="Invalid API key")

    owner_type = auth_result.get("api_key").owner_type if auth_result.get("api_key") else None
    return {
        "owner_type": owner_type,
        "user_id": auth_result.get("user_id"),
        "integration_principal_id": auth_result.get("integration_principal_id"),
    }
```

This keeps runtime behavior aligned with the packaged auth flows.

## What Hosts Should Avoid

Host applications should not treat these as their integration boundary:

- direct reads from `api_keys`, `api_key_scopes`, or `api_key_ip_whitelist`
- direct host-side calls to `auth.api_key_service.verify_api_key(...)`
- host-side reimplementation of grantable scope calculation
- host-side duplication of derived effectiveness logic

Those are auth-owned internals. They may still be useful inside library tests or
advanced internal customization, but they are not the intended host contract.

## Current Semantics

### SimpleRBAC

- self-service `personal` keys only
- no integration-principal routes
- service tokens remain the non-human/internal automation primitive

### EnterpriseRBAC

- self-service `personal` keys remain human-owned
- durable non-human automation uses `IntegrationPrincipal` plus
  `system_integration` keys
- entity-scoped principals are bounded to one entity tree and root
- platform-global principals are superuser-managed only
- runtime access for `personal` keys is reduced by:
  - stored scopes
  - current human owner permissions
  - personal-key allowlist
  - entity scope
- runtime access for `system_integration` keys is reduced by:
  - stored scopes
  - principal `allowed_scopes`
  - system-key allowlist
  - principal scope
- principal-backed keys are RBAC-only in this slice; ABAC-conditioned
  permissions are denied
- inactive owners, inactive principals, and inactive anchor entities deny
  runtime use

## Credential Chooser

- Use `personal` API keys for human-owned automation tied to one user.
- Use `system_integration` API keys when you need DB-backed non-human
  credentials with inventory, rotate, revoke, audit, or IP allowlists.
- Use service tokens for internal platform services that do not need that
  database-managed lifecycle.

## Enterprise Example Review Personas

The EnterpriseRBAC example now seeds a concrete review matrix for API-key
management:

- `admin@acme.com`: superuser, may create entity-scoped and platform-global
  integration principals and keys
- `org-admin@acme.com`: root-scoped admin, may manage entity-scoped
  integrations anywhere under `ACME Realty`
- `regional-admin@acme.com`: West Coast hierarchy admin, may manage
  entity-scoped integrations within that branch only
- `manager@sf.acme.com`: San Francisco office-local admin, may manage
  office-local integrations at that entity
- `east-admin@acme.com`: East Coast hierarchy admin, denied for West Coast
  entity paths
- `auditor@acme.com` and operational users: denied for API-key admin surfaces

### Service Tokens

- service tokens remain separate from API keys
- use them for internal platform services that do not need DB-backed inventory,
  revoke, rotate, audit, or IP allowlists
- use `system_integration` keys when you need those DB-backed lifecycle and
  management capabilities

For the full design background and planned future phases, see
[`docs/API_KEY_SCOPE_AND_GRANT_POLICY_EPIC.md`](../docs/API_KEY_SCOPE_AND_GRANT_POLICY_EPIC.md).

## Observability

Core API key observability is emitted by the auth layer itself:

- validation success/failure
- runtime policy denials
- grant-policy denials
- rate-limit hits
- lifecycle operations such as create, update, revoke, and rotate

Hosts do not need to wrap these surfaces in their own auth-specific metrics to
get the core OutlabsAuth signals.
