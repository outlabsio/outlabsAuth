# Deployment

> **Handbook** · Ship OutlabsAuth in production without fighting the schema.  
> Part of the [OutlabsAuth Handbook](./README.md). Deep maintainer guide:
> [`docs/DEPLOYMENT_GUIDE.md`](../docs/DEPLOYMENT_GUIDE.md).

---

## Checklist

1. **Postgres** — `postgresql+asyncpg://…` (prefer a direct URL over a transaction pooler for auth-heavy traffic)
2. **Secret** — `secret_key` ≥ 32 characters (HS256)
3. **Schema** — dedicated schema such as `outlabs_auth` (`database_schema=` / `OUTLABS_AUTH_SCHEMA`)
4. **Migrate once** — `auto_migrate=False` in multi-worker runtimes; run CLI in prestart
5. **Redis** — for shared permission cache, counters, rate limits, token blacklist; or `cache_backend="memory"` on a **single** process only
6. **Mount prefix** — stable (`/v1`, `/iam`, …) and match OutlabsAuth UI `authApiPrefix`
7. **Observability** — embedded mode + host `/metrics` registry ([97](./97-Observability.md))

```bash
export DATABASE_URL=postgresql+asyncpg://...
export OUTLABS_AUTH_SCHEMA=outlabs_auth

outlabs-auth doctor
outlabs-auth migrate
outlabs-auth seed-system
outlabs-auth bootstrap-admin --email admin@example.com --password '…'
# or: outlabs-auth bootstrap --admin-email … --admin-password …
```

Details: [Configuration](./03-Configuration.md), [Getting Started](./01-Getting-Started.md).

---

## Multi-worker / multi-instance

| Concern | Guidance |
|---------|----------|
| Migrations | One-shot prestart / release job — never every uvicorn worker |
| Permission cache | `redis` (+ `redis_url`) so invalidation is shared |
| Memory cache | Only for single-process hosts |
| Refresh revoke / sessions | `store_refresh_tokens=True` (default) |
| Immediate access kill | `enable_token_blacklist=True` + Redis |

---

## Health

`outlabs-auth doctor` is read-only and safe on prod for preflight. Exit `0`
healthy, `1` check failure, `2` missing `DATABASE_URL`.

---

## Related

- [Configuration](./03-Configuration.md)
- [Getting Started](./01-Getting-Started.md)
- [Observability](./97-Observability.md)
- [OutlabsAuth UI](../docs/AUTH_UI.md)
- [`docs/DEPLOYMENT_GUIDE.md`](../docs/DEPLOYMENT_GUIDE.md)
- [`docs/SECURITY.md`](../docs/SECURITY.md)
