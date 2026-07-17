# OutlabsAuth

**Library-first authentication and authorization for FastAPI** — RBAC, optional ABAC, API keys, and Postgres-backed permissions that live inside your app.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)
[![Stage: Alpha](https://img.shields.io/badge/stage-alpha-red.svg)](#status)
[![PyPI](https://img.shields.io/pypi/v/outlabs-auth.svg)](https://pypi.org/project/outlabs-auth/)

> **Alpha** — packaged on PyPI; the public API is still settling before 1.0.

## Why OutlabsAuth

Most auth products push you into a separate IdP or a black-box service. OutlabsAuth is the opposite: a **Python library** you mount into your FastAPI app, with your Postgres, your routes, and your deployment.

| You get | Details |
|---------|---------|
| Two presets | **SimpleRBAC** (flat roles) or **EnterpriseRBAC** (entity hierarchy + tree permissions) |
| Auth surface | JWT access/refresh, API keys, service tokens, invitations, optional OAuth / magic link / access codes |
| Admin console | Optional sister app [OutlabsAuth UI](https://github.com/outlabsio/OutlabsAuthUI) — point it at any host that mounts this library |
| Ops | Packaged Alembic migrations, CLI bootstrap, Redis-backed caches when you need them |

## Documentation

| Start here | |
|------------|--|
| [Getting Started](./docs-library/01-Getting-Started.md) | Install → migrate → mount → login → optional UI |
| [Routers & Prefixes](./docs-library/02-Routers-and-Prefixes.md) | Which `get_*_router` factories to mount |
| [Configuration](./docs-library/03-Configuration.md) | Constructor flags, Redis, schema, production defaults |
| [User docs index](./docs-library/) | Topic guides (JWT, invites, API keys, observability, …) |
| [Examples](./examples/) | Runnable SimpleRBAC + EnterpriseRBAC apps |
| [OutlabsAuth UI](./docs/AUTH_UI.md) | Sister admin console (Vite/React) |
| [API design](./docs/API_DESIGN.md) | Host DX patterns |
| [Comparison matrix](./docs/COMPARISON_MATRIX.md) | Simple vs Enterprise features |

Maintainer design specs live under [`docs/`](./docs/).

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

Optional sister repository: a **Vite/React** admin console that plugs into any app hosting this library. It reads `GET {authApiPrefix}/auth/config` and adapts to Simple vs Enterprise.

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

## CLI Bootstrap

```bash
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/app
# optional: export OUTLABS_AUTH_SCHEMA=outlabs_auth

outlabs-auth migrate
outlabs-auth seed-system
outlabs-auth bootstrap-admin --email admin@example.com --password 'ChangeMe_now1!'
```

Useful operators: `outlabs-auth doctor` (read-only preflight), `outlabs-auth bootstrap` (idempotent first-boot). See [Configuration](./docs-library/03-Configuration.md) and [`docs/DEPLOYMENT_GUIDE.md`](./docs/DEPLOYMENT_GUIDE.md).

## Production Snapshot

```python
from outlabs_auth import EnterpriseRBAC

auth = EnterpriseRBAC(
    database_url="postgresql+asyncpg://user:password@db-host/app?ssl=require",
    database_schema="outlabs_auth",
    secret_key="replace-me-with-a-long-secret",
    auto_migrate=False,
    redis_url="redis://cache-host:6379/0",
)
```

- Prefer a **direct** Postgres URL over transaction-pooler endpoints for auth-heavy apps
- Migrate in a **single-process** prestart step; then start workers
- Mount under an app-owned prefix such as `/iam`
- Point OutlabsAuth UI `authApiPrefix` at that same prefix

```bash
export DATABASE_URL='postgresql+asyncpg://user:password@db-host/app?ssl=require'
export OUTLABS_AUTH_SCHEMA='outlabs_auth'

outlabs-auth migrate
outlabs-auth seed-system
exec uvicorn myapp.main:app --host 0.0.0.0 --port 8000 --workers 2
```

## Status

**Library version**: 0.1.0a24 · **Stage**: Alpha

## License

MIT, copyright 2026 OUTLABS LLC.
