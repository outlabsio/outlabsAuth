# OutlabsAuth UI

[OutlabsAuth UI](https://github.com/outlabsio/OutlabsAuthUI) is an optional sister
repository: a shared admin console for any FastAPI app that mounts OutlabsAuth.

It is **not** bundled with the Python package. You run (or deploy) it separately and
point it at your mounted auth API.

## What It Is

- Vite + React + TypeScript SPA (Bun toolchain)
- Plugs into hosts using SimpleRBAC or EnterpriseRBAC
- Discovers capabilities from `GET {authApiPrefix}/auth/config`
- Manages users, roles, invitations, API keys, sessions/audit surfaces (as the
  backend advertises them), and entity hierarchy when Enterprise features are on

Backend capabilities still come from the mounted auth API. The UI does not embed a
second auth stack.

## Boundary

| Repository | Owns |
|------------|------|
| **outlabsAuth** (this repo) | Library, routers, services, migrations, backend tests |
| **OutlabsAuthUI** | Admin SPA, Bun toolchain, frontend tests/builds |

Treat the UI as a consumer of the backend contract, not as a subproject of this repo.

## Point the UI at Your API

1. Mount the library routers your product needs (at minimum `get_auth_router`).
   Examples use prefix `/v1/auth`, `/v1/users`, and so on.
2. Clone and run the UI:

```bash
git clone https://github.com/outlabsio/OutlabsAuthUI.git
cd OutlabsAuthUI
bun install
cp public/app-config.template.json public/app-config.json
```

3. Edit `public/app-config.json`:

```json
{
  "apiBaseUrl": "http://localhost:8004",
  "authApiPrefix": "/v1",
  "appName": "OutlabsAuth UI",
  "appSubtitle": "Shared auth admin console",
  "authBrand": "OutlabsAuth",
  "signInDescription": "Sign in against the configured auth backend to access this console."
}
```

- `apiBaseUrl` — origin of the FastAPI host (no trailing slash)
- `authApiPrefix` — common prefix under which auth routers are mounted
  (examples use `/v1`; production often uses `/iam`)

With `authApiPrefix: "/v1"`, the UI calls `/v1/auth/config`, `/v1/auth/login`,
`/v1/users`, etc.

4. Start the UI:

```bash
bun run dev
```

Default Vite URL is `http://localhost:5173`. Sign in with a bootstrap or seeded admin
from the host app.

Config precedence and deploy options: see the UI repo’s
[`docs/runtime-configuration.md`](https://github.com/outlabsio/OutlabsAuthUI/blob/main/docs/runtime-configuration.md).

## SimpleRBAC vs EnterpriseRBAC

`GET {authApiPrefix}/auth/config` advertises the preset and feature flags. The UI
adapts navigation and forms from that snapshot.

### SimpleRBAC invite contract

When `features.entity_hierarchy=false` and `features.context_aware_roles=false`:

- Do not show entity membership or entity scope controls
- Do not send `entity_id` when inviting a user
- Send selected `role_ids` to `POST {authApiPrefix}/auth/invite`
- The backend applies those `role_ids` as direct account role memberships

### EnterpriseRBAC

Selected invite roles may be applied through an entity membership when an
`entity_id` is supplied. Entity hierarchy, memberships, and related admin surfaces
appear when the backend advertises them.

## Local Development (Both Repos)

```bash
# Backend — from this repository
cd examples/enterprise_rbac   # or examples/simple_rbac
uv sync
uv run outlabs-auth migrate
uv run python reset_test_env.py
uv run uvicorn main:app --reload --port 8004   # simple_rbac: 8003

# UI — sibling of the outlabsAuth repo (from repo root: ../OutlabsAuthUI)
cd ../../../OutlabsAuthUI
bun install
cp public/app-config.template.json public/app-config.json
# apiBaseUrl + authApiPrefix must match the backend above
bun run dev
```

| Example | API port | Suggested `app-config.json` |
|---------|----------|-------------------------------|
| `examples/simple_rbac` | `8003` | `apiBaseUrl: http://localhost:8003`, `authApiPrefix: /v1` |
| `examples/enterprise_rbac` | `8004` | `apiBaseUrl: http://localhost:8004`, `authApiPrefix: /v1` |

## Historical Note

Older docs may mention `auth-ui/` or a Nuxt admin UI inside this repository. Those
references are historical. The active UI codebase is
[OutlabsAuthUI](https://github.com/outlabsio/OutlabsAuthUI) (Vite/React).
