# OutlabsAuth UI

[OutlabsAuth UI](https://github.com/outlabsio/OutlabsAuthUI) is an optional sister
repository: a shared admin console for any FastAPI app that mounts OutlabsAuth.

It is **not** bundled with the Python package. You run (or deploy) it separately and
point it at your mounted auth API.

## What It Is

- Nuxt 4 + Nuxt UI 4 static single-page app (`ssr: false`), Bun toolchain, MIT licensed
- One build serves any backend: each deployment names its API in a runtime
  `app-config.json`; no backend address is baked into the build
- Plugs into hosts using SimpleRBAC or EnterpriseRBAC
- Discovers capabilities from `GET {authApiPrefix}/auth/config` and adapts pages,
  navigation and actions to the preset, the mounted surfaces and the signed-in
  admin's permissions
- Covers sign-in (password, magic link, email and phone codes, OAuth, self-signup,
  recovery, invitations), users, roles and permissions (with ABAC conditions),
  personal API keys, service accounts and their keys, sessions, the audit log,
  settings, and the entity hierarchy when Enterprise features are on

Backend capabilities still come from the mounted auth API. The UI does not embed a
second auth stack. Which capabilities the console has built, partly built or not yet
built is tracked in its
[`CAPABILITIES.md`](https://github.com/outlabsio/OutlabsAuthUI/blob/main/CAPABILITIES.md);
rows marked "backend" wait on a change in this repository.

## Boundary

| Repository | Owns |
|------------|------|
| **outlabsAuth** (this repo) | Library, routers, services, migrations, backend tests, the seeded example backends |
| **OutlabsAuthUI** | Admin SPA, Bun toolchain, Playwright and Vitest suites, release gate, static deploy |

Treat the UI as a consumer of the backend contract, not as a subproject of this repo.
The console targets a checked-in OpenAPI snapshot of the library routes (currently
`0.1.0a34`) and API contract `outlabs-auth.api/v1`, which `GET {authApiPrefix}/auth/config`
reports as `api_contract_version`. A route or schema change here reaches the console only
when that repository refreshes its snapshot.

## Point the UI at Your API

1. Mount the library routers your product needs (at minimum `get_auth_router`; the
   admin screens need the fuller sets in
   [Routers & Prefixes](../docs-library/02-Routers-and-Prefixes.md)). Examples use
   prefix `/v1/auth`, `/v1/users`, and so on.
2. Allow the console's origin in CORS, with credentials. In development the console
   runs on `http://localhost:3000`, which both examples already allow.
3. Clone and install the UI (Bun 1.3.3+ and Node.js 22.18+):

```bash
git clone https://github.com/outlabsio/OutlabsAuthUI.git
cd OutlabsAuthUI
bun install
cp public/app-config.template.json public/app-config.json   # untracked
```

4. Edit `public/app-config.json`. The template's API values target the EnterpriseRBAC
   example; its other keys are branding and the `authUi` sign-in options:

```json
{
  "apiBaseUrl": "http://localhost:8004",
  "authApiPrefix": "/v1",
  "frontendProfileKey": "console",
  "appName": "OutlabsAuth UI",
  "appSubtitle": "Shared auth admin console",
  "authBrand": "OutlabsAuth",
  "signInDescription": "Sign in against the configured auth backend to access this console."
}
```

- `apiBaseUrl` — origin of the FastAPI host (no trailing slash)
- `authApiPrefix` — common prefix under which auth routers are mounted; it must start
  with `/` (examples use `/v1`; production often uses `/iam`; use `/` when
  `get_auth_router` is mounted at `/auth`)
- `frontendProfileKey` — the frontend-profile key the console sends as `app` on sign-in,
  invite, recovery, passwordless and OAuth requests. It must name a `FrontendProfile`
  the host registers (the EnterpriseRBAC example registers `console`); an unregistered
  key makes sign-in fail with `wrong_application`. Remove it for a host without
  frontend profiles (such as the SimpleRBAC example): such a host ignores it on sign-in
  and challenge flows, but OAuth authorize rejects a supplied `app` with HTTP 400.

With `authApiPrefix: "/v1"`, the UI calls `/v1/auth/config`, `/v1/auth/login`,
`/v1/users`, etc.

5. Start the UI:

```bash
bun run dev   # http://localhost:3000
```

Sign in with a bootstrap or seeded admin from the host app. During `bun run dev` the
console also reads `NUXT_PUBLIC_*` variables (the UI's `.env.example`), below
`public/app-config.json`; production builds ignore them and read only the
`app-config.json` staged for each deployment.

Configuration reference (precedence, `authUi`, branding, hosting constraints): the UI
repository's [README, "Configuration"](https://github.com/outlabsio/OutlabsAuthUI#configuration).

## SimpleRBAC vs EnterpriseRBAC

`GET {authApiPrefix}/auth/config` advertises the preset and feature flags. The UI
adapts navigation and forms from that snapshot.

The active permission catalog is intentionally separate: authenticated admin
screens fetch `GET {authApiPrefix}/auth/config/permissions` with a bearer token.
That route requires `permission:read`; the public config never returns permission
names.

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

## Deploying the Console

The console ships as a static artifact (`bun run generate` → `.output/public`, with a
hash-based Content-Security-Policy) served by Cloudflare Workers static assets:
`bun run deploy:cloudflare --config <deployment app-config.json> --env <name>`. Each
deployment's `app-config.json` lives outside the UI repository and is staged by the deploy
preflight, which also refuses a commit without a passing release-gate record (below). The
procedure and the full per-deployment cutover checklist are in the UI repository's
[`PRODUCTION.md`](https://github.com/outlabsio/OutlabsAuthUI/blob/main/PRODUCTION.md).

On the backend host, before the first cutover:

- `apiBaseUrl` uses `https://` (plain `http://` is accepted only for localhost)
- CORS allows the console origin exactly (scheme, host, port) with credentials, sends
  `Access-Control-Max-Age` and exposes `Retry-After`
- `frontendProfileKey` names a registered profile whose public origin is the console
  origin, so emailed reset, invite, magic-link and sign-in-code links open the console
- OAuth success, error and associate redirects point at the console
  (`/auth/oauth/callback`, `/auth/login`, `/app/account`), and the console and API are
  same-site (one registrable domain): the OAuth state cookie is `SameSite=Lax`
- the console is served at the root of its own hostname (sub-paths are not supported)

## Release Gate Against the Examples

The console has no hosted CI. Its release gate runs on the releasing machine against this
repository's two seeded examples, each with its own disposable database:

```bash
# in OutlabsAuthUI, on a clean commit, with both examples running
bun run release:check --enterprise http://localhost:8004 --simple http://localhost:8003
```

It runs the static gates and the full Playwright suite against each preset and writes
`.release/gate.json`; the deploy accepts only a commit with a passing record from the last
7 days. The suite depends on these examples' `/v1` prefix, the personas and passwords
seeded by `reset_test_env.py`, CORS for `http://localhost:3000` and `:3001`, the
EnterpriseRBAC `console` frontend profile, and the development-only `/dev/auth/*/latest`
token captures. Treat a change to any of them as a console contract change.

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
# the template targets the EnterpriseRBAC example; for simple_rbac set
# apiBaseUrl to http://localhost:8003 and remove frontendProfileKey
bun run dev   # http://localhost:3000
```

| Example | API port | Suggested `app-config.json` |
|---------|----------|-------------------------------|
| `examples/simple_rbac` | `8003` | `apiBaseUrl: http://localhost:8003`, `authApiPrefix: /v1`, no `frontendProfileKey` |
| `examples/enterprise_rbac` | `8004` | `apiBaseUrl: http://localhost:8004`, `authApiPrefix: /v1`, `frontendProfileKey: console` (the template as shipped) |

## Historical Note

Older docs may mention `auth-ui/` or a Nuxt admin UI inside this repository, or describe
OutlabsAuth UI as a Vite/React app on port 5173. Those references are historical: the
in-tree UI was removed, and on 2026-10-02 the external repository replaced its React
console with the Nuxt console described here (the React version remains in that
repository's history). The active UI codebase is
[OutlabsAuthUI](https://github.com/outlabsio/OutlabsAuthUI).
