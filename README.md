# OutlabsAuth

Open-source FastAPI authentication and authorization for RBAC, ABAC, API keys, and Postgres-backed permission models.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)
[![Stage: Alpha](https://img.shields.io/badge/stage-alpha-red.svg)](#status)

> **Alpha release** - Public PyPI packaging is supported, but the API surface is still settling before 1.0.

## Status

**Current Library Version**: 0.1.0a21

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

The consuming app owns its own configuration. In practice that means you provide:

- a PostgreSQL connection URL
- a JWT signing secret
- any app-specific entity, membership, or host-query integrations you want on top of the base library

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

This example uses `auto_migrate=True` for convenience. For production, run migrations explicitly with the packaged CLI instead of relying on startup migration.

## CLI Bootstrap

After installation, the package exposes an `outlabs-auth` CLI for schema setup and initial seeding.

```bash
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/app
# optional: export OUTLABS_AUTH_SCHEMA=auth

outlabs-auth migrate
outlabs-auth seed-system
outlabs-auth bootstrap-admin --email admin@example.com --password change-me
```

## Recommended Production Defaults

For real deployments, use the library with explicit, optimized baseline
settings rather than the convenience quickstart defaults.

### App configuration baseline

```python
from outlabs_auth import EnterpriseRBAC

auth = EnterpriseRBAC(
    database_url="postgresql+asyncpg://user:password@db-host/app?ssl=require",
    database_schema="outlabs_auth",
    secret_key="replace-me",
    auto_migrate=False,
    redis_url="redis://cache-host:6379/0",  # Enables Redis counters + permission cache
)
```

Recommended defaults:

- use an explicit auth schema such as `outlabs_auth`
- keep `auto_migrate=False` in normal runtime
- provide Redis for production API-key counters, rate limits, and permission caching
- mount the library under an app-owned prefix such as `/iam`

### Database connection guidance

For managed Postgres providers that offer both direct and transaction-pooler
URLs, prefer the direct runtime URL for auth-heavy apps.

Why:

- OutlabsAuth already uses SQLAlchemy connection pooling
- auth and permission checks often perform multiple small round trips
- transaction-pooler endpoints add measurable latency for those query patterns
- non-public auth schemas depend on reliable per-connection schema resolution

Use:

- `postgresql+asyncpg://...`

Avoid as the primary runtime URL when you can:

- transaction-pooler URLs such as provider `-pooler` endpoints

### Bootstrap and worker startup

Do not rely on `auto_migrate=True` inside a multi-worker application runtime.

Recommended pattern:

1. Run the packaged CLI in a single-process release or prestart step.
2. Start the application workers only after that step succeeds.

Example:

```bash
export DATABASE_URL='postgresql+asyncpg://user:password@db-host/app?ssl=require'
export OUTLABS_AUTH_SCHEMA='outlabs_auth'

outlabs-auth migrate
outlabs-auth seed-system

exec uvicorn myapp.main:app --host 0.0.0.0 --port 8000 --workers 2
```

This avoids worker races and keeps schema ownership explicit.

### Current operator workflow

Today, the recommended operational commands are:

- `outlabs-auth migrate`
- `outlabs-auth seed-system`
- `outlabs-auth bootstrap-admin`
- `outlabs-auth tables`
- `outlabs-auth current`
- `outlabs-auth doctor` — read-only preflight diagnostics. Runs five checks
  (connectivity, target schema, Alembic version table, revision matches code,
  core auth tables) against `DATABASE_URL` + `OUTLABS_AUTH_SCHEMA`. Supports
  `--format text` (default) and `--format json`. Exit codes: `0` healthy, `1`
  one or more checks failed, `2` `DATABASE_URL` not set. Passwords in the URL
  are redacted in all output. Safe to run against production — it issues no
  writes.
- `outlabs-auth bootstrap` — idempotent first-boot orchestrator. Classifies
  the schema, builds a deterministic plan (migrate → seed → optional admin),
  and executes it. Aborts explicitly on drift, partially-bootstrapped, or
  missing-schema states rather than auto-repairing. Flags: `--dry-run`,
  `--skip-seed`, `--admin-email`/`--admin-password` (also via
  `OUTLABS_AUTH_BOOTSTRAP_*` env vars), `--format text|json`. Same exit-code
  semantics as doctor. Runs a final doctor pass on success to confirm the
  healthy end state.

## More

The repository includes deeper examples, packaged CLI flows, and design notes:

- GitHub: https://github.com/outlabsio/outlabsAuth
- Examples: [`examples/`](/Users/macbookm3/Documents/projects/outlabsAuth/examples)
- Maintainer release guide: [`docs/PRIVATE_RELEASE.md`](/Users/macbookm3/Documents/projects/outlabsAuth/docs/PRIVATE_RELEASE.md)

## License

MIT, copyright 2026 OUTLABS LLC.
