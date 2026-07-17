# 01. Getting Started

End-to-end path for embedding OutlabsAuth in a FastAPI app.

## 1. Prerequisites

- Python 3.12+
- PostgreSQL
- Redis optional for local demos; recommended in production for counters, rate limits, and permission cache

## 2. Install

```bash
pip install outlabs-auth
# or, in a uv project: uv add outlabs-auth
```

Provide at minimum:

- `DATABASE_URL` — `postgresql+asyncpg://...`
- `SECRET_KEY` — at least 32 characters for HS256

## 3. Choose a Preset

| Question | Preset |
|----------|--------|
| Flat roles, no org tree? | `SimpleRBAC` |
| Departments / teams / entity hierarchy? | `EnterpriseRBAC` |

See [13-Core-Authorization-Concepts.md](./13-Core-Authorization-Concepts.md) and
[`docs/COMPARISON_MATRIX.md`](../docs/COMPARISON_MATRIX.md).

## 4. Bootstrap Schema

Run these in a **single-process** release or prestart step (not inside every worker):

```bash
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/app
# optional: export OUTLABS_AUTH_SCHEMA=outlabs_auth

outlabs-auth migrate
outlabs-auth seed-system
outlabs-auth bootstrap-admin --email admin@example.com --password 'ChangeMe_now1!'
```

Or use the orchestrator:

```bash
outlabs-auth bootstrap --admin-email admin@example.com --admin-password 'ChangeMe_now1!'
```

Keep `auto_migrate=False` in multi-worker app runtime. Details: root README
“Recommended Production Defaults”.

## 5. Wire FastAPI

Minimal shape (also in the root README; executed by `tests/unit/test_readme_quickstart.py`):

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

For a product admin console or full management API, mount more routers (users, roles,
permissions, API keys, entities, …). Catalog:
[02-Routers-and-Prefixes.md](./02-Routers-and-Prefixes.md).

Examples mount under `/v1/...` (e.g. `/v1/auth`). Production often uses `/iam`.
Pick one prefix family and keep it consistent for the UI’s `authApiPrefix`.

## 6. Smoke Login

```bash
curl -s -X POST http://localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"ChangeMe_now1!"}'
```

Expect access + refresh tokens. Then call a protected host route with
`Authorization: Bearer <access_token>`.

## 7. Protect Host Routes

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

More patterns: [`docs/API_DESIGN.md`](../docs/API_DESIGN.md) and the examples.

## 8. Optional: OutlabsAuth UI

[OutlabsAuth UI](https://github.com/outlabsio/OutlabsAuthUI) is a sister Vite/React
admin console. Point it at your mounted API:

```bash
git clone https://github.com/outlabsio/OutlabsAuthUI.git
cd OutlabsAuthUI
bun install
cp public/app-config.template.json public/app-config.json
# apiBaseUrl = your FastAPI origin
# authApiPrefix = /auth parent prefix (e.g. /v1 if routers are under /v1/auth)
bun run dev
```

Full contract and Simple vs Enterprise invite rules: [`docs/AUTH_UI.md`](../docs/AUTH_UI.md).

## 9. Learn From Examples

| Example | Port | Best for |
|---------|------|----------|
| [`examples/simple_rbac`](../examples/simple_rbac/) | 8003 | Flat RBAC blog API |
| [`examples/enterprise_rbac`](../examples/enterprise_rbac/) | 8004 | Hierarchy, tree permissions, richer admin mounts |
| [`examples/abac_cookbook`](../examples/abac_cookbook/) | 8005 | ABAC conditions |

Configuration deep-dive: [03-Configuration.md](./03-Configuration.md).

## Checklist

- [ ] Postgres reachable; schema migrated and seeded
- [ ] `prime_fastapi_routing()` (or mount after `initialize()`)
- [ ] `instrument_fastapi(app)` for middleware + exception handlers
- [ ] Auth router mounted; smoke login works
- [ ] Host routes use `auth.deps`
- [ ] (Optional) OutlabsAuth UI `app-config.json` matches your prefix
