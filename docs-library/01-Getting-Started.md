# Getting Started

Get from zero to a working login in one sitting. When you are done you will have:

- OutlabsAuth installed against Postgres  
- Schema migrated and an admin user  
- Auth routes mounted on FastAPI  
- A successful login that returns JWT tokens  

Optional: point [OutlabsAuth UI](https://github.com/outlabsio/OutlabsAuthUI) at
the same API.

New here? Skim [Introduction](./00-Introduction.md) first (two minutes).

---

## Prerequisites

- Python 3.12+
- A PostgreSQL database you can reach
- Redis is optional for local demos. For production counters and shared
  permission cache, plan on Redis — or use `cache_backend="memory"` on a
  **single-process** host (see [Configuration](./03-Configuration.md))

## 1. Install

```bash
pip install outlabs-auth
# or: uv add outlabs-auth
```

You will need at least:

| Variable | Meaning |
|----------|---------|
| `DATABASE_URL` | `postgresql+asyncpg://…` |
| `SECRET_KEY` | JWT signing secret, **≥ 32 characters** for HS256 |

Generate a secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## 2. Pick a preset

| Need | Preset |
|------|--------|
| Flat roles, no org tree | `SimpleRBAC` |
| Departments / teams / hierarchy | `EnterpriseRBAC` |

Details: [Choosing a Preset](./07-Choosing-a-Preset.md).

## 3. Create the schema (once per environment)

Run this in a **single-process** release or prestart step — not inside every
app worker:

```bash
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/app
# optional: export OUTLABS_AUTH_SCHEMA=outlabs_auth

outlabs-auth migrate
outlabs-auth seed-system
outlabs-auth bootstrap-admin --email admin@example.com --password 'ChangeMe_now1!'
```

Or the one-shot orchestrator:

```bash
outlabs-auth bootstrap --admin-email admin@example.com --admin-password 'ChangeMe_now1!'
```

Keep `auto_migrate=False` when you run multiple uvicorn workers. More:
[Configuration](./03-Configuration.md).

## 4. Wire FastAPI

This is the minimal shape. The same block is executed by
`tests/unit/test_readme_quickstart.py`, so it cannot silently rot.

```python
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from outlabs_auth import SimpleRBAC
from outlabs_auth.routers import get_auth_router

auth = SimpleRBAC(
    database_url=os.environ["DATABASE_URL"],
    secret_key=os.environ["SECRET_KEY"],
)
auth.prime_fastapi_routing()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await auth.initialize()
    yield
    await auth.shutdown()


app = FastAPI(lifespan=lifespan)
auth.instrument_fastapi(app)
app.include_router(get_auth_router(auth, prefix="/auth"))
```

Two habits that matter:

1. Call **`prime_fastapi_routing()`** before mounting routers at import time
   (or mount inside `lifespan` after `initialize()` — see the SimpleRBAC example).
2. Call **`instrument_fastapi(app)`** so commits finish before the response is
   sent and exception handlers are registered.

For an admin console you will also mount users, roles, permissions, and so on.
Catalog: [Routers & Prefixes](./02-Routers-and-Prefixes.md).

Examples use `/v1/auth`, `/v1/users`, …. Production often uses `/iam`. Pick one
prefix family and keep it consistent for OutlabsAuth UI’s `authApiPrefix`.

## 5. Smoke login

```bash
curl -s -X POST http://localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"ChangeMe_now1!"}'
```

You should get an access token and a refresh token. Call protected routes with:

```http
Authorization: Bearer <access_token>
```

## 6. Protect your own routes

```python
from fastapi import Depends

@app.get("/me")
async def me(user=Depends(auth.deps.authenticated())):
    return {"id": str(user.id), "email": user.email}


@app.delete("/items/{item_id}")
async def delete_item(
    item_id: str,
    _=Depends(auth.deps.require_permission("item:delete")),
):
    ...
```

More host patterns live in the examples and [`docs/API_DESIGN.md`](../docs/API_DESIGN.md)
(that file is denser — use it when you need edge cases).

## 7. Optional: OutlabsAuth UI

The sister admin console is a separate repo. Point it at your API:

```bash
git clone https://github.com/outlabsio/OutlabsAuthUI.git
cd OutlabsAuthUI
bun install
cp public/app-config.template.json public/app-config.json
# apiBaseUrl  = http://localhost:8000  (your API origin)
# authApiPrefix = "" if you mounted at /auth
#               = /v1 if you mounted at /v1/auth, /v1/users, …
bun run dev
```

Full wiring and Simple vs Enterprise invite rules:
[`docs/AUTH_UI.md`](../docs/AUTH_UI.md).

## 8. Learn from examples

| Example | Port | Best for |
|---------|------|----------|
| [`examples/simple_rbac`](../examples/simple_rbac/) | 8003 | Flat RBAC |
| [`examples/enterprise_rbac`](../examples/enterprise_rbac/) | 8004 | Hierarchy + richer mounts |
| [`examples/abac_cookbook`](../examples/abac_cookbook/) | 8005 | ABAC conditions |

## Checklist

- [ ] Postgres reachable; migrated and seeded
- [ ] `prime_fastapi_routing()` (or mount after `initialize()`)
- [ ] `instrument_fastapi(app)`
- [ ] Auth router mounted; smoke login works
- [ ] Host routes use `auth.deps`
- [ ] (Optional) OutlabsAuth UI `app-config.json` matches your prefix

## Where to go next

- [Configuration](./03-Configuration.md) — production defaults, Redis, memory cache  
- [Routers & Prefixes](./02-Routers-and-Prefixes.md) — full management API  
- [User Management API](./23-User-Management-API.md) — users admin surface  
- [OAuth](./04-OAuth-and-Social-Login.md) · [Sessions](./05-Sessions-and-Audit.md) · [Passwordless](./06-Passwordless-and-Messaging.md)
