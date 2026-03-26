# 50. API Key Host Integration

This guide describes the supported API key integration surface for host
applications embedding OutlabsAuth.

The short version:

- use mounted routers for API key management APIs
- use `auth.authorize_api_key(...)` for custom host-side runtime checks
- do not build host integrations around direct DB reads or raw primitive
  service calls

## Current Status

As of 2026-03-26, this backend integration surface is implemented for
EnterpriseRBAC `personal` keys.

What is already in place:

- the entity-first admin router
- the auth-owned runtime helper
- derived effectiveness fields on API key responses
- auth-owned observability for API key policy, validation, and lifecycle events

What is not started yet:

- UI adoption in `../OutlabsAuthUI`
- future `system_integration` and service-account work

## Current Backend Test Position

The backend surface described in this guide is already covered by focused
Python tests in:

- `tests/integration/test_api_key_admin_endpoints.py`
- `tests/integration/test_api_key_lifecycle.py`
- `tests/integration/test_api_keys_router_callback_paths.py`
- `tests/integration/test_enterprise_api_key_policy_matrix.py`
- `tests/unit/services/test_api_key_service.py`
- `tests/unit/test_auth_core_lifecycle.py`
- `tests/unit/observability/test_observability_integration.py`

The main remaining backend test work before UI adoption is:

- exhaust the remaining denial branches through the admin HTTP surface
- add route-flow observability assertions for the new admin/runtime API key
  paths
- add more pagination, search, and filter edge-case coverage
- add more admin-created key IP-whitelist and rate-limit edge-case coverage

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

### 2. Entity-First Admin API Key Router

For EnterpriseRBAC admin products, mount:

```python
from outlabs_auth.routers import get_api_key_admin_router

app.include_router(
    get_api_key_admin_router(auth, prefix="/v1/admin/entities"),
)
```

This is the supported admin surface for entity-anchored API keys. The current
v1 contract includes:

- `GET /{entity_id}/grantable-scopes`
- `GET /{entity_id}/api-keys`
- `POST /{entity_id}/api-keys`
- `GET /{entity_id}/api-keys/{key_id}`
- `PATCH /{entity_id}/api-keys/{key_id}`
- `DELETE /{entity_id}/api-keys/{key_id}`
- `POST /{entity_id}/api-keys/{key_id}/rotate`

The list route supports pagination plus `owner_id`, `status`, `key_kind`, and
`search` filters.

Admin responses include derived runtime state:

- `is_currently_effective`
- `ineffective_reasons`

That lets host products render “stored but currently ineffective” keys without
inventing their own runtime policy evaluation.

### 3. Runtime Authorization Helper

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
like the packaged API key backend:

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

    return {"user_id": auth_result["user_id"]}
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

## V1 Enterprise Semantics

For the current EnterpriseRBAC admin model:

- only `personal` keys are supported
- admin-managed keys must be entity-anchored
- admin-managed keys must be explicitly scoped
- runtime access is still reduced by the owner's current permissions and entity
  state
- inactive owners and inactive anchor entities deny runtime use

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
