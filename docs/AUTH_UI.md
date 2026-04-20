# External Admin UI

The Nuxt admin UI is no longer stored in this repository.

## Current Location

- Sibling repository: `../OutlabsAuthUI`
- Current local workspace path: `/Users/macbookm3/Documents/projects/OutlabsAuthUI`

## Boundary

- This repository owns the backend library, routers, services, migrations, and backend tests.
- The `OutlabsAuthUI` repository owns the Nuxt application, Bun toolchain, and frontend-specific tests/builds.
- Backend documentation in this repo should treat the external UI as a consumer of the backend contract, not as a tracked subproject.

## SimpleRBAC Invite Contract

For `SimpleRBAC`, the backend advertises `features.entity_hierarchy=false` and
`features.context_aware_roles=false` from `GET /auth/config`.

Admin UIs must treat that as a flat RBAC contract:

- Do not show entity membership or entity scope controls.
- Do not send `entity_id` when inviting a user.
- Send selected `role_ids` to `POST /auth/invite`.
- The backend applies those `role_ids` as direct account role memberships.

For `EnterpriseRBAC`, selected invite roles may be applied through an entity
membership when an `entity_id` is supplied.

## Local Development

Run the backend from this repository and the UI from the sibling repo.

```bash
# Backend
cd /Users/macbookm3/Documents/projects/outlabsAuth
uv run start.py

# UI
cd /Users/macbookm3/Documents/projects/OutlabsAuthUI
bun install
bun run dev
```

## Historical Note

Older docs and design notes may still mention `auth-ui/`. Those references are historical.
The source of truth for the active UI codebase is now `OutlabsAuthUI`.
