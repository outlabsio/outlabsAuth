# EnterpriseRBAC Example - Real Estate Leads Platform

This example demonstrates OutlabsAuth's **EnterpriseRBAC** preset: entity hierarchy,
tree permissions, multi-root orgs, and a host lead domain on top of the library.

Seed data comes from `reset_test_env.py` (ACME Realty + Summit orgs). Run that
script before relying on the credentials below.

## What This Demonstrates

- **Flexible entity types** — orgs define their own tree vocabulary (no hardcoded enum of “department”)
- **Tree permissions** — `_tree` actions inherit down the hierarchy
- **Multi-root isolation** — ACME and Summit are separate roots; scope does not leak
- **Scoped admins** — org / region / office personas for permission review
- **Host integration** — leads CRUD, team directory via `auth.host_query_service`, transactional mail wiring
- **Machine credentials** — personal API keys, integration principals, service tokens
- **Optional admin UI** — [OutlabsAuth UI](https://github.com/outlabsio/OutlabsAuthUI) pointed at `/v1`

## Features

- Entity hierarchy + entity type suggestions
- Tree permissions (`lead:read_tree`, `lead:update_tree`, …)
- Host app team directory via `auth.host_query_service`
- Host-owned transactional auth mail wiring
- Granular roles and ABAC condition demos in the seed
- Lead management (CRUD, assignment, status pipeline)
- API-key and integration-principal admin surfaces under `/v1`

## ✅ API Integration Check (Release Smoke Test)

`api_integration_check.py` drives the **running** API over HTTP against the
seeded scenarios and asserts the behavior an operator cares about before a
release (45 checks): persona logins across both org roots, entity-scoped
grants, sibling-team and cross-root isolation (via a membership-only user),
tree-permission inheritance down the hierarchy, cache-served verdict
stability, and the next-request visibility arcs — role grant/revoke,
role-permission add/remove, membership suspend/reactivate, entity archive,
API-key revoke, and refresh-token logout all take effect on the very next
request even with Redis caching enabled.

The one-command release flow (seed → boot → admin/ABAC smoke → assertion
suite → teardown) lives at the repo root:

```bash
uv run python scripts/run_enterprise_example_smoke.py
```

Or run the pieces individually (e.g. against a staging host):

```bash
python reset_test_env.py                                  # seed known state
uvicorn main:app --port 8004                              # start the API
python api_integration_check.py                           # 45 checks, exit 0 on pass
python api_integration_check.py --base-url http://staging-host:8004
```

It is rerunnable and creates only throwaway data on top of the seed
(unique-suffixed users/roles/leads, a temporary membership it removes again,
an API key it revokes again, one archived entity). See
`docs/PRIVATE_RELEASE.md` → "API Integration Validation" for the runbook
entry and the seeded-data gotchas.

## 🔑 Machine Credentials (Current v1 Surface)

The current EnterpriseRBAC example also demonstrates the OutlabsAuth machine
credential model:

- `personal` API keys remain self-service and user-owned
- `system_integration` API keys are owned by `IntegrationPrincipal`
- service tokens stay separate for internal platform-to-platform automation

The example app mounts the auth-owned API-key surfaces under `/v1`:

- `/v1/api-keys/*` for self-service `personal` keys
- `/v1/admin/entities/{entity_id}/api-keys*` for anchored-key inventory and
  incident-response revoke
- `/v1/admin/entities/{entity_id}/integration-principals*` for entity-scoped
  non-human integrations
- `/v1/admin/system/integration-principals*` for platform-global
  superuser-managed integrations

Recommended review personas for this slice:

- `admin@acme.com`: superuser, may create entity-scoped and platform-global
  integration principals and keys
- `org-admin@acme.com`: root-scoped admin for `ACME Realty`
- `regional-admin@acme.com`: West Coast hierarchy admin only
- `manager@sf.acme.com`: San Francisco office-local admin only
- `east-admin@acme.com`: East Coast hierarchy admin only
- `auditor@acme.com`: read-only and denied for API-key admin surfaces

The example host route used for runtime key verification is:

- `GET /v1/entities/{entity_id}/team-directory`

That route is intentionally path-scoped, so it is useful for validating that a
minted key works inside its allowed entity scope and stops working after revoke.

## 🚀 Quick Start

### Option 1: Docker Compose (Recommended)

The cleanest way to run the example is as a standalone consumer app:

```bash
cd examples/enterprise_rbac
uv sync

# Optional: validate a local wheel instead of the published package
# uv pip install --reinstall ../../dist/outlabs_auth-<version>-py3-none-any.whl

# Bootstrap auth schema
uv run outlabs-auth migrate

# Seed example-owned data
uv run python reset_test_env.py

# Start the API
uv run uvicorn main:app --reload --port 8004
```

The API will be available at `http://localhost:8004` with auto-reload enabled.

**Requirements:**
- PostgreSQL running locally
- Redis running locally (optional, but recommended)

### Transactional Auth Mail

This example now demonstrates the recommended auth-mail integration model:

- `OutlabsAuth` emits typed invite/reset/access-granted intents
- the example app composes branded messages
- delivery is selected by the host app

The wiring lives in `examples/enterprise_rbac/transactional_mail.py`.

Current behavior:

- `OUTLABS_AUTH_MAIL_PROVIDER` selects the host transport (`auto|mailgun|sendgrid|postmark|resend|smtp|webhook|console`)
- `auto` picks the first fully configured provider; otherwise console
- `MAIL_RECIPIENT_OVERRIDE` (or legacy `MAILGUN_RECIPIENT_OVERRIDE`) redirects all invite/reset mail to a sandbox inbox while stamping `intended_recipient` metadata

Relevant env vars from `.env.example`:

- `FRONTEND_URL`
- `API_PUBLIC_URL` (public API origin used for OAuth callback URLs; default `http://localhost:8004`)
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` (optional; mounts invite-only Google login at `/v1/oauth/google` and account linking at `/v1/oauth-associate/google`)
- `OUTLABS_AUTH_MAIL_PROVIDER`
- `MAIL_FROM` / `MAIL_FROM_NAME` / `MAIL_RECIPIENT_OVERRIDE`
- Mailgun: `MAILGUN_*`
- SendGrid: `SENDGRID_API_KEY`
- Postmark: `POSTMARK_SERVER_TOKEN`
- Resend: `RESEND_API_KEY`
- SMTP / webhook: see `.env.example`

### Challenge messaging (WhatsApp + SMS)

Host-owned delivery for access-code / OTP intents lives in `challenge_messaging.py`:

- Without Twilio env: console spikes print WhatsApp Content API and SMS-shaped payloads
- WhatsApp live when `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`, and a real `TWILIO_WHATSAPP_ACCESS_CODE_CONTENT_SID` are set
- SMS live when the same account credentials plus `TWILIO_SMS_FROM` (E.164) are set
- Multiplex routes by `delivery_channel` (`whatsapp` vs `sms`); email challenges stay on transactional mail

### Environment

Set the standard consumer-app environment before first boot:

```bash
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/realestate_enterprise_rbac
export SECRET_KEY=enterprise-rbac-secret-change-in-production-please
# Optional
export REDIS_URL=redis://localhost:6379/0
```

### Seed Demo Data

```bash
# Create all scenarios with demo users, entities, roles, and leads
uv run python reset_test_env.py
```

This creates review personas and hierarchy for **ACME Realty** and **Summit**
(users, roles, entities, sample leads, lifecycle fixtures). Exact counts are
printed at the end of `reset_test_env.py`.

### Explore the API

Visit the interactive documentation:
- **Swagger UI**: http://localhost:8004/docs
- **Health Check**: http://localhost:8004/health

## Demo Credentials

All seeded passwords are `Testpass1!` unless noted. Source of truth:
`reset_test_env.py` (printed again at the end of a reset).

### Start here

| Email | Persona |
|-------|---------|
| `admin@acme.com` | Superuser |
| `org-admin@acme.com` | ACME root-scoped admin |
| `regional-admin@acme.com` | West Coast hierarchy admin |
| `east-admin@acme.com` | East Coast hierarchy admin |
| `manager@sf.acme.com` | San Francisco office admin |
| `auditor@acme.com` | Read-only ACME auditor |
| `lead@sf.acme.com` | SF residential team lead |
| `agent@sf.acme.com` | SF residential agent |
| `commercial@sf.acme.com` | SF commercial agent |
| `summit-admin@summit.com` | Second-root (Summit) admin |
| `agent@austin.summit.com` | Summit growth agent |

### Lifecycle fixtures

| Email | Notes |
|-------|-------|
| `invited@acme.com` | Pending invite (no password) |
| `suspended@ny.acme.com` | Suspended operator |
| `locked@la.acme.com` | Locked account fixture |
| `unverified@austin.summit.com` | Unverified email fixture |

### What to try

- Login as `admin@acme.com` → full admin + API-key / integration surfaces
- Login as `org-admin@acme.com` → ACME root; not platform-global superuser
- Login as `agent@sf.acme.com` vs `east-admin@acme.com` → sibling branch isolation
- Login as `summit-admin@summit.com` → second root; ACME data stays out of scope
- Point [OutlabsAuth UI](https://github.com/outlabsio/OutlabsAuthUI) at `http://localhost:8004` with `authApiPrefix: /v1`

## 📚 API Endpoints

### Standard OutlabsAuth Routes

All implementations include these standardized routes:

#### Authentication
- `POST /v1/auth/register` - Register new user
- `POST /v1/auth/login` - Login with email/password
- `POST /v1/auth/refresh` - Refresh access token
- `POST /v1/auth/logout` - Logout
- `GET /v1/auth/config` - Preset + feature flags (admin UI discovery)
- `GET /v1/auth/me` - Get current user info
- Magic link / access-code / invite routes when those flags are enabled (see OpenAPI)

#### Sessions, social accounts, audit
- `GET/DELETE /v1/users/me/sessions` — list / revoke own sessions (also revoke-all)
- `GET/DELETE /v1/users/{user_id}/sessions` — admin session inventory (`user:read` / `user:update`)
- `GET/DELETE /v1/users/me/social-accounts` — list / unlink linked OAuth providers
- `GET /v1/users/{user_id}/audit-events` — per-user audit timeline
- `GET /v1/audit-events` — cross-user audit search (`get_audit_router`)

#### Entity Management
- `GET /v1/entities` - List entities
- `POST /v1/entities` - Create entity
- `GET /v1/entities/suggestions` - Entity type suggestions
- `GET /v1/entities/{entity_id}` - Get entity details
- `GET /v1/entities/{entity_id}/children` - Get child entities
- `GET /v1/entities/{entity_id}/descendants` - Get descendant tree
- `PUT /v1/entities/{entity_id}` - Update entity
- `DELETE /v1/entities/{entity_id}` - Delete entity

#### User, Role, Membership, Permission Management
- Full CRUD for users, roles, memberships
- Membership lifecycle controls:
  - add entity memberships with scoped roles
  - suspend one entity membership without suspending the whole account
  - apply membership validity windows (`valid_from`, `valid_until`)
  - remove one entity membership with audit-preserving soft revoke
- Permission checking endpoints
- See Swagger UI (`/docs`) for the complete live list

### Domain-Specific Routes (Lead Management)

- `POST /v1/leads` - Create new lead
- `GET /v1/leads` - List leads (filtered by permissions)
- `GET /v1/leads/{lead_id}` - Get lead details
- `PUT /v1/leads/{lead_id}` - Update lead
- `DELETE /v1/leads/{lead_id}` - Delete lead
- `POST /v1/leads/{lead_id}/assign` - Assign lead to agent
- `POST /v1/leads/{lead_id}/notes` - Add note to lead
- `GET /v1/entities/{entity_id}/team-directory` - Example host-side team directory using `auth.host_query_service`

## Test Scenarios

### 1. Entity type suggestions

```bash
# After login, pick a parent entity id from GET /v1/entities
curl -s "http://localhost:8004/v1/entities/suggestions?parent_id={parent_id}" \
  -H "Authorization: Bearer {TOKEN}"
```

Expected: existing child types at that level (counts + examples) so hosts can
steer naming without hardcoding a global taxonomy.

### 2. Tree / branch isolation

| Login as | Expect |
|----------|--------|
| `admin@acme.com` | Broad admin access across ACME (superuser) |
| `regional-admin@acme.com` | West Coast scope; not East Coast admin |
| `east-admin@acme.com` | East Coast scope; sibling of West |
| `agent@sf.acme.com` | SF residential team leads only |
| `summit-admin@summit.com` | Summit root; ACME entities/leads out of scope |

Use `POST /v1/auth/login` then `GET /v1/leads` and `GET /v1/entities` to compare.

### 3. Multi-root

ACME and Summit are separate roots. Switching identity should not leak
memberships or lead visibility across roots (except true superuser paths).

## Architecture Notes

### Example hierarchy shape (ACME)

```
ACME Realty (root)
├── West Coast
│   └── San Francisco office
│       ├── SF Residential (team)
│       └── SF Commercial (team)
└── East Coast
    └── NYC office
```

Summit is a second root used for multi-org tests. Exact keys and display names
come from the seed script.

### Entity classifications

**STRUCTURAL** — organizational containers in the tree.

**ACCESS_GROUP** — work locations where domain objects (leads) typically attach.

### Permission model (host + library)

Host lead permissions in this example include `lead:read`, `lead:create`,
`lead:update`, `lead:delete`, `lead:assign`, plus `_tree` variants for subtree
access. Specialist and after-hours ABAC demos are seeded for review — inspect
roles/permissions in Swagger or OutlabsAuth UI after login.

## 🔗 Connect Admin UI

[OutlabsAuth UI](https://github.com/outlabsio/OutlabsAuthUI) is a sister Vite/React
admin console. Point it at this example’s API:

```bash
# Sibling of the outlabsAuth repo (not inside examples/)
cd ../../../OutlabsAuthUI   # or: git clone https://github.com/outlabsio/OutlabsAuthUI.git
bun install
cp public/app-config.template.json public/app-config.json
```

Set `public/app-config.json` to:

```json
{
  "apiBaseUrl": "http://localhost:8004",
  "authApiPrefix": "/v1",
  "appName": "OutlabsAuth UI",
  "appSubtitle": "EnterpriseRBAC example",
  "authBrand": "OutlabsAuth",
  "signInDescription": "Sign in with a seeded demo admin from this example."
}
```

```bash
bun run dev
```

Open the Vite URL (default `http://localhost:5173`) and sign in with a seeded
account from `reset_test_env.py` (for example `admin@acme.com` / `Testpass1!`).

The UI reads `GET /v1/auth/config` and adapts for Enterprise features (entity
hierarchy, memberships, entity-type settings). More detail:
[`docs/AUTH_UI.md`](../../docs/AUTH_UI.md).

## 📖 Key Concepts

### 1. Entity Type Flexibility

Entity types are **just strings** - not hardcoded. This allows each organization to use their own terminology.

**Problem**: Without guidance → inconsistent names like "brokerage", "broker", "office", "borkerage" (typo)

**Solution**: Entity Type Suggestions API returns existing types at that level

### 2. Tree Permissions

Permissions with `_tree` suffix apply to entire subtree:
- Agent: `lead:read` → Only their team
- Broker: `lead:read_tree` → Entire brokerage tree

### 3. Multiple Organizational Models

The same system handles:
- Deep hierarchies (5+ levels)
- Flat structures (1 entity)
- Different naming conventions
- Hybrid models

## 🛠️ Development

### Environment Variables

```bash
# PostgreSQL connection (matches the default in main.py)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/realestate_enterprise_rbac

# JWT secret (CHANGE IN PRODUCTION!)
SECRET_KEY=your-secret-key-change-in-production-please

# Optional: Redis for caching
REDIS_URL=redis://localhost:6379
```

### Adding New Scenarios

1. Extend `reset_test_env.py`
2. Add entities with `create_entity()`
3. Create users and memberships
4. Create sample leads
5. Add it to the reset manifest output

## 🐛 Troubleshooting

### PostgreSQL Connection Failed
```bash
docker ps | grep postgres
docker start postgres
```

### "Entity not found" errors
```bash
uv run python reset_test_env.py  # Re-seed
```

### Permission denied
- Check user has correct role
- Verify entity membership
- Check tree permissions for child entities

## 📝 Next Steps

1. Test all scenarios in Swagger UI
2. Connect the admin UI
3. Try entity suggestions
4. Test tree permissions with different roles
5. Explore the API

## 📄 Related Documentation

- **REQUIREMENTS.md** - Detailed use case analysis
- **PROGRESS.md** - Implementation progress
- **IMPLEMENTATION_PLAN.md** (root) - Project vision

---

**Built with OutlabsAuth EnterpriseRBAC** 🚀
