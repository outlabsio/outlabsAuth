# API Key Host Integration

> **Handbook** · Issue and check API keys from your FastAPI host.  
> Part of the [OutlabsAuth Handbook](./README.md).

Two key kinds, three routers to mount, one runtime helper for your own routes.

| Kind | Owner | Typical use |
|------|-------|-------------|
| `personal` | A user | Self-service keys that act as that user |
| `system_integration` | An `IntegrationPrincipal` | Non-human / service integrations (admin-managed) |

**Do:** mount the routers below and call `auth.authorize_api_key(...)`.  
**Don’t:** read `api_keys` tables directly or call `api_key_service.verify_api_key`
from host code.

```python
from outlabs_auth.routers import (
    get_api_keys_router,
    get_api_key_admin_router,
    get_integration_principals_router,
)

app.include_router(get_api_keys_router(auth, prefix="/v1/api-keys"))
app.include_router(get_integration_principals_router(auth, prefix="/v1/admin"))
app.include_router(get_api_key_admin_router(auth, prefix="/v1/admin/entities"))
```

Admin listing of another user’s personal keys also lives on the users router —
[User Management API](./23-User-Management-API.md).

---

## Routers

### Personal (`/v1/api-keys`)

Self-service CRUD + rotate for the authenticated user’s own keys.

### Integration principals (`/v1/admin`)

Enterprise-oriented admin for `system_integration` keys:

- Entity-scoped: `/entities/{entity_id}/integration-principals[/{id}/api-keys…]`
- Platform-global (superuser): `/system/integration-principals[…]`

Includes create / patch / delete principal, list/create/rotate/revoke keys.

### Entity inventory (`/v1/admin/entities`)

Incident response across keys anchored to an entity:

- `GET /{entity_id}/api-keys` (filters: `owner_id`, `status`, `key_kind`, `search`)
- `GET /{entity_id}/api-keys/{key_id}`
- `DELETE /{entity_id}/api-keys/{key_id}`

Responses include derived `is_currently_effective` / `ineffective_reasons`.

---

## Runtime authorization

```python
auth_result = await auth.authorize_api_key(
    session,
    api_key_string,  # e.g. from X-API-Key
    required_scope="contacts:read",
    entity_id=entity_id,
    ip_address=client_ip,
)
# None → deny; else dict with source="api_key", scopes, owner metadata, …
```

**Personal keys** resolve a `user` / `user_id`.  
**System integration keys** resolve an `integration_principal` (no user).

Host pattern sketch:

```python
@router.get("/contacts/{entity_id}")
async def list_contacts(entity_id: UUID, request: Request, session=Depends(auth.uow)):
    result = await auth.authorize_api_key(
        session,
        request.headers.get("X-API-Key"),
        required_scope="contacts:read",
        entity_id=entity_id,
        ip_address=request.client.host if request.client else None,
    )
    if result is None:
        raise HTTPException(status_code=401, detail="Invalid API key")
    ...
```

---

## Simple vs Enterprise

| | SimpleRBAC | EnterpriseRBAC |
|---|------------|----------------|
| Personal keys | Yes | Yes |
| Integration principals / system keys | No (use JWT **service tokens** for internal automation) | Yes |
| Entity inventory admin router | Optional / limited | Yes |

Enterprise runtime also folds in owner/principal activity, allowlists, entity
scope, and stored scopes. **Principal-backed keys are RBAC-only** — if ABAC is
on and the required permission has conditions, those keys are denied
([ABAC](./26-ABAC.md)).

---

## Credential chooser

| Need | Use |
|------|-----|
| Human-owned automation | `personal` API key |
| Durable non-human key with inventory / rotate / IP allowlist | `system_integration` |
| Internal platform service without DB-managed key lifecycle | JWT **service tokens** |

Example personas and mounts: [`examples/enterprise_rbac`](../examples/enterprise_rbac/).  
Design epic (maintainer): [`docs/API_KEY_SCOPE_AND_GRANT_POLICY_EPIC.md`](../docs/API_KEY_SCOPE_AND_GRANT_POLICY_EPIC.md).

Auth-layer metrics/logs cover validation, denials, rate limits, and lifecycle —
see [Observability](./97-Observability.md).

## Related

- [Routers & Prefixes](./02-Routers-and-Prefixes.md)
- [User Management API](./23-User-Management-API.md)
- [ABAC](./26-ABAC.md)
- [OutlabsAuth UI](../docs/AUTH_UI.md)
