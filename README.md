# OutlabsAuth

**Library-first authentication and authorization for FastAPI** — RBAC, optional ABAC, API keys, and Postgres-backed permissions that live inside your app.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)
[![Stage: Alpha](https://img.shields.io/badge/stage-alpha-red.svg)](#status)
[![PyPI](https://img.shields.io/pypi/v/outlabs-auth.svg)](https://pypi.org/project/outlabs-auth/)
[![Source](https://img.shields.io/badge/source-GitHub-black.svg)](https://github.com/outlabsio/outlabsAuth)

> **Alpha release** - packaged on PyPI; the public API is still settling before 1.0.

## Why OutlabsAuth

Most auth products push you into a separate IdP or a black-box service. OutlabsAuth is the opposite: a **Python library** you mount into your FastAPI app, with your Postgres, your routes, and your deployment.

| You get | Details |
|---------|---------|
| Two presets | **SimpleRBAC** (flat roles) or **EnterpriseRBAC** (entity hierarchy + tree permissions) |
| Auth surface | JWT access/refresh, API keys, service tokens, invitations, optional OAuth / magic link / access codes |
| Admin console | Optional sister app [OutlabsAuth UI](https://github.com/outlabsio/OutlabsAuthUI) — point it at any host that mounts this library |
| Ops | Packaged Alembic migrations, CLI bootstrap, Redis when needed, optional in-process permission cache (`cache_backend="memory"`) |

## Documentation

**Implementers** start in the [OutlabsAuth Handbook](./docs-library/)
(`docs-library/`) — human-readable guides written for people integrating the
library. A Nuxt docs site lives beside this repo at
[`../outlabsAuth-docs`](../outlabsAuth-docs) (Nuxt UI docs template); re-port
with `python3 scripts/port_handbook.py` from that project.

| Guide | What it covers |
|-------|----------------|
| [Handbook home](./docs-library/) | Reading paths, full guide index |
| [Introduction](./docs-library/00-Introduction.md) | Mental model in a few minutes |
| [Getting Started](./docs-library/01-Getting-Started.md) | Install → migrate → mount → login → optional UI |
| [Choosing a Preset](./docs-library/07-Choosing-a-Preset.md) | SimpleRBAC vs EnterpriseRBAC in plain language |
| [Routers & Prefixes](./docs-library/02-Routers-and-Prefixes.md) | Which `get_*_router` factories to mount |
| [Configuration](./docs-library/03-Configuration.md) | Constructor flags, Redis, schema, production defaults |
| [Background Maintenance](./docs-library/09-Background-Maintenance.md) | Typed one-shot cleanup/sync, external ownership, activation, and rollback |
| [OAuth](./docs-library/04-OAuth-and-Social-Login.md) · [Sessions & audit](./docs-library/05-Sessions-and-Audit.md) · [Passwordless](./docs-library/06-Passwordless-and-Messaging.md) | Optional auth extensions |
| [Examples](./examples/) | Runnable SimpleRBAC + EnterpriseRBAC apps |
| [OutlabsAuth UI](./docs/AUTH_UI.md) | Sister admin console (Vite/React) |

**Maintainers** (design decisions, audits, release process): [`docs/`](./docs/).
Deep host DX / feature matrix when you need them:
[API design](./docs/API_DESIGN.md),
[Comparison matrix](./docs/COMPARISON_MATRIX.md).

## Choose a Preset

```
Need departments / teams / org tree?
  NO  → SimpleRBAC
  YES → EnterpriseRBAC
```

| Need | Preset |
|------|--------|
| Flat users → roles → permissions | **SimpleRBAC** |
| Hierarchy, memberships, tree permissions | **EnterpriseRBAC** |

## Install

```bash
pip install outlabs-auth
```

You need PostgreSQL. Provide at least:

- a `postgresql+asyncpg://...` URL
- a JWT `secret_key` (≥ 32 characters for HS256)

## Quickstart

```python
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from outlabs_auth import SimpleRBAC
from outlabs_auth.routers import get_auth_router

auth = SimpleRBAC(
    database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/app",
    # Must be at least 32 characters when signing with HS256, or construction
    # fails. Generate one with:
    #   python -c "import secrets; print(secrets.token_urlsafe(48))"
    secret_key=os.environ["SECRET_KEY"],
)

# Builds the engine, services and dependencies synchronously. Required *before*
# any router factory runs: they dereference `auth.deps`, which otherwise only
# exists after `initialize()` — and that's async, so it cannot run at import.
auth.prime_fastapi_routing()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await auth.initialize()  # async work: migrations, Redis, service wiring
    yield
    await auth.shutdown()


app = FastAPI(lifespan=lifespan)

# Installs the exception handlers *and* the UnitOfWork/RequestCache middleware.
# Prefer this over bare register_exception_handlers(): the middleware commits
# before the response is sent, which is what makes a create immediately readable.
auth.instrument_fastapi(app)

app.include_router(get_auth_router(auth, prefix="/auth"))
```

`tests/unit/test_readme_quickstart.py` executes this block, so it cannot rot.

Deliberate details:

- **`prime_fastapi_routing()` before mounting** — otherwise `ConfigurationError: Dependencies not initialized`
- **Real `secret_key`** — placeholders under 32 characters fail at construction under HS256

You can also mount inside `lifespan()` after `initialize()` (no priming) — see `examples/simple_rbac/main.py`.

For production, run migrations with the CLI (`auto_migrate=False`). Continue with [Getting Started](./docs-library/01-Getting-Started.md) and [Configuration](./docs-library/03-Configuration.md).

## OutlabsAuth UI

Optional sister repository: a **Vite/React** admin console that plugs into any app hosting this library. It reads public feature flags from `GET {authApiPrefix}/auth/config`, then loads the permission catalog from authenticated `GET {authApiPrefix}/auth/config/permissions` when needed.

```bash
# Terminal 1 — Enterprise example API
cd examples/enterprise_rbac
uv sync && uv run outlabs-auth migrate && uv run python reset_test_env.py
uv run uvicorn main:app --reload --port 8004

# Terminal 2 — from the outlabsAuth repo root
cd ../OutlabsAuthUI   # https://github.com/outlabsio/OutlabsAuthUI
bun install
cp public/app-config.template.json public/app-config.json
# apiBaseUrl: http://localhost:8004   authApiPrefix: /v1
bun run dev
```

Sign in with a seeded admin (e.g. `admin@acme.com` / `Testpass1!`). Full wiring: [`docs/AUTH_UI.md`](./docs/AUTH_UI.md).

## CLI Operations and Administration

The CLI has two operating planes: local database lifecycle commands and
authenticated administration through a mounted OutlabsAuth API. The optional
admin UI is not required for CLI workflows.

### Local database lifecycle

```bash
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/app
# optional: export OUTLABS_AUTH_SCHEMA=outlabs_auth

outlabs-auth migrate
outlabs-auth seed-system
printf '%s\n' "$INITIAL_ADMIN_PASSWORD" | \
  outlabs-auth bootstrap-admin --email admin@example.com --password-stdin
```

Useful operators: `outlabs-auth doctor` (read-only preflight) and
`outlabs-auth bootstrap` (idempotent first-boot). Namespaced forms such as
`outlabs-auth db migrate` and `outlabs-auth ops doctor` are also available;
the original spellings remain supported.

### Remote administration

Contexts contain target metadata only. Tokens are never written to the context
file. Human logins use a separate, target-bound owner-only session store;
unattended automation can keep using a named environment variable.

```bash
outlabs-auth context add local \
  --base-url http://127.0.0.1:8004 \
  --api-prefix /v1

outlabs-auth capabilities
outlabs-auth auth login --email admin@example.com  # hidden password prompt
outlabs-auth auth status
outlabs-auth whoami
outlabs-auth users list --status active --all
outlabs-auth users get admin@example.com
outlabs-auth permissions explain reports:read --user admin@example.com
```

The CLI also has typed lifecycle commands for self-service accounts, users,
roles, permissions and ABAC policy, entities, memberships, API keys,
integration principals/system keys, sessions, audit events, and entity-type
configuration. References accept UUIDs or unambiguous human identifiers such
as email, role name, entity slug, and API-key name.

```bash
outlabs-auth permissions create --name reports:read --display-name "Read reports"
outlabs-auth roles create \
  --name report-reader --display-name "Report reader" \
  --permission reports:read
outlabs-auth memberships add \
  --user analyst@example.com --entity engineering \
  --role report-reader --yes
outlabs-auth users access-report analyst@example.com
```

For unattended agents, configure a least-privilege API key instead of a human
session when host policy permits it:

```bash
outlabs-auth context add production \
  --base-url https://api.example.com \
  --api-prefix /iam \
  --credential-type api-key
export OUTLABS_AUTH_API_KEY='scoped-key-value'
```

To create a least-privilege key while signed in as a human, declare where its
one-time secret must go. The CLI validates the destination before creating the
key and writes it with mode `0600`:

```bash
outlabs-auth api-keys grantable-scopes --entity engineering
outlabs-auth api-keys create \
  --name coding-agent --scope user:read --scope permission:read \
  --entity engineering --secret-file ./coding-agent.key --yes
```

Coding agents and scripts should select the versioned JSON contract globally:

```bash
outlabs-auth --output json --non-interactive users list --all
outlabs-auth --output json commands memberships add --shallow
```

Successes and failures both emit one JSON document on stdout with stable error
codes and exit categories. `commands` exposes the live command/option schema,
while guarded `api request` provides a bounded relative-path escape hatch for
new mounted endpoints.

For repeatable administration, review and save a target-bound plan before any
write:

```bash
outlabs-auth --output json plan examples/cli/state.example.json --out state.plan.json
outlabs-auth --output json --non-interactive apply state.plan.json --yes
```

Design and compatibility contract: [`docs/CLI_DESIGN.md`](./docs/CLI_DESIGN.md).
Coding-agent operating guide: [`docs/CLI_AGENT_GUIDE.md`](./docs/CLI_AGENT_GUIDE.md).
Declarative manifest contract: [`docs/CLI_MANIFEST.md`](./docs/CLI_MANIFEST.md).
Configuration and deployment: [Configuration](./docs-library/03-Configuration.md) and
[`docs/DEPLOYMENT_GUIDE.md`](./docs/DEPLOYMENT_GUIDE.md).

## Production Snapshot

```python
from outlabs_auth import EnterpriseRBAC

auth = EnterpriseRBAC(
    database_url="postgresql+asyncpg://user:password@db-host/app?ssl=require",
    database_schema="outlabs_auth",
    secret_key="replace-me-with-a-long-secret",
    auto_migrate=False,
    redis_url="redis://cache-host:6379/0",
    background_job_mode="disabled",
)
```

- Prefer a **direct** Postgres URL over transaction-pooler endpoints for auth-heavy apps
- Migrate in a **single-process** prestart step; then start workers
- Mount under an app-owned prefix such as `/iam`
- Point OutlabsAuth UI `authApiPrefix` at that same prefix
- Run one external `auth.run_maintenance_once()` owner; never one loop per API replica

```bash
export DATABASE_URL='postgresql+asyncpg://user:password@db-host/app?ssl=require'
export OUTLABS_AUTH_SCHEMA='outlabs_auth'

outlabs-auth migrate
outlabs-auth seed-system
exec uvicorn myapp.main:app --host 0.0.0.0 --port 8000 --workers 2
```

## Status

**Current Library Version**: 0.1.0a29

**Publication Status**: Approved immutable release source for PyPI publication.

**Release Stage**: Alpha

## License

MIT, copyright 2026 OUTLABS LLC.
