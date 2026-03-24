# OutlabsAuth Host Integration Queries

## Purpose

When `OutlabsAuth` is embedded inside a larger FastAPI product, the host app
will sometimes need **cross-domain read access** to auth-owned data:

- entity memberships with user details
- roles assignable in one entity context
- current entity memberships for one or more users

The host app should **not** solve that by inventing its own joins into
`users`, `entities`, `entity_memberships`, or `roles`.

Use the auth-owned query facade instead:

- `auth.host_query_service`

This keeps auth schema knowledge inside the library while still supporting the
"mounted plugin in the same process" model.

## Design Rule

For host-app integration:

1. Use mounted routers for external/admin API surfaces.
2. Use `auth.host_query_service` for in-process cross-domain reads.
3. Avoid direct host-side joins into auth-owned tables unless there is no
   supported facade yet.

Direct joins are treated as a temporary compatibility fallback, not the
preferred developer experience.

## Available Queries

`HostQueryService` currently exposes:

- `list_entity_members(...)`
  - Returns entity memberships with user, entity, and role projections.
  - `active_only=True` applies current-runtime semantics:
    - membership status is active
    - validity window is current
    - user status is active
    - entity status is active

- `list_roles_for_entity(...)`
  - Returns the roles that are assignable in one entity context.
  - Reuses the auth library's entity-aware role availability logic.

- `list_user_entity_memberships(...)`
  - Returns membership projections for one or more users.
  - Useful for host-side scope resolution, such as finding a canonical
    `agent_practice` or office/team context for a linked user.

- `list_users_by_ids(...)`
  - Returns canonical user projections without requiring any membership join.
  - Use this when the host app needs auth-owned identity data for a known set
    of user IDs, such as hydrating a primary account owner.

## Usage

```python
from fastapi import Depends

from src.api.deps.outlabs import get_outlabs_auth


def get_host_queries(auth = Depends(get_outlabs_auth)):
    if auth.host_query_service is None:
        raise RuntimeError("Host query service unavailable")
    return auth.host_query_service
```

```python
members, total = await auth.host_query_service.list_entity_members(
    session,
    entity_id=entity_id,
    active_only=True,
)

roles, _ = await auth.host_query_service.list_roles_for_entity(
    session,
    entity_id=entity_id,
)

memberships = await auth.host_query_service.list_user_entity_memberships(
    session,
    user_ids=[user_id],
    active_only=True,
)

users = await auth.host_query_service.list_users_by_ids(
    session,
    user_ids=[user_id],
    active_only=False,
)
```

## Returned Shapes

The facade returns stable projection dataclasses instead of raw SQLAlchemy table
objects from host-defined joins:

- `HostUserProjection`
- `HostEntityProjection`
- `HostRoleProjection`
- `HostEntityMembershipProjection`

These are intentionally read-only and designed for orchestration, not mutation.

## Why This Exists

Mounted auth is a plugin model, but plugins embedded in the same process still
need an internal integration contract.

Without this facade, every host application would eventually rediscover the
same problems:

- schema qualification
- auth table ownership leakage
- duplicated membership/role filtering logic
- ad hoc joins scattered through unrelated services

`HostQueryService` is the supported internal boundary for those reads.
