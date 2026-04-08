# OutlabsAuth

Open-source FastAPI authentication and authorization for RBAC, ABAC, API keys, and Postgres-backed permission models.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)
[![Stage: Alpha](https://img.shields.io/badge/stage-alpha-red.svg)](#status)

> **Alpha release** - Public PyPI packaging is supported, but the API surface is still settling before 1.0.

## Status

**Current Library Version**: 0.1.0a8

**Release Stage**: Alpha

## What It Does

OutlabsAuth is a library-first auth system for FastAPI applications that want to keep authentication and authorization inside the app instead of outsourcing it to a separate service.

- SimpleRBAC and EnterpriseRBAC presets
- JWT auth, refresh tokens, API keys, service tokens, and OAuth hooks
- Postgres-backed users, roles, permissions, entities, and audit history
- FastAPI router factories, middleware, and CLI migrations

## Install

```bash
pip install outlabs-auth
```

You will also need a PostgreSQL database available to the consuming app.

## Quickstart

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from outlabs_auth import SimpleRBAC, register_exception_handlers
from outlabs_auth.routers import get_auth_router

auth = SimpleRBAC(
    database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/app",
    secret_key="change-me",
    auto_migrate=True,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await auth.initialize()
    yield
    await auth.shutdown()


app = FastAPI(lifespan=lifespan)
register_exception_handlers(app)
app.include_router(get_auth_router(auth, prefix="/auth"))
```

## More

The repository includes deeper examples, packaged CLI flows, and design notes:

- GitHub: https://github.com/outlabsio/outlabsAuth
- Examples: [`examples/`](/Users/macbookm3/Documents/projects/outlabsAuth/examples)
- Maintainer release guide: [`docs/PRIVATE_RELEASE.md`](/Users/macbookm3/Documents/projects/outlabsAuth/docs/PRIVATE_RELEASE.md)

## License

MIT, copyright 2026 OUTLABS LLC.
