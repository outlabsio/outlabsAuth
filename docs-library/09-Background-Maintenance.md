# Background Maintenance

> **Handbook** · Run cleanup and sync work safely outside FastAPI processes.
> Part of the [OutlabsAuth Handbook](./README.md).

OutlabsAuth periodically cleans expired tokens, aggregates optional activity
metrics, and flushes Redis-backed API-key usage. Production APIs should not own
those recurring loops.

```text
one scheduler clock -> one bounded invocation -> auth.run_maintenance_once()
```

| Component | Responsibility |
|-----------|----------------|
| API processes | Serve requests with `background_job_mode="disabled"` |
| Host scheduler | Decide when maintenance is due |
| Worker or one-shot job | Initialize the host's Auth instance and run one cycle |
| OutlabsAuth | Execute enabled steps and return a typed report |

The scheduler and executor may share a machine or run separately. A supervised
local worker is a normal production choice. Use cloud execution only when
availability, private-network access, latency, or isolation requires it.

## Programmatic entry point

Use the same host-owned Auth factory as the API, with embedded jobs disabled:

```python
async def run_auth_maintenance():
    auth = build_auth(background_job_mode="disabled")
    try:
        await auth.initialize()
        report = await auth.run_maintenance_once()
        if not report.ok:
            raise RuntimeError(
                f"auth maintenance incomplete: "
                f"missing={report.missing_steps!r} "
                f"errors={report.reported_errors}"
            )
        return report
    finally:
        await auth.shutdown()
```

`run_maintenance_once()` returns an immutable `MaintenanceReport`:

| Field | Meaning |
|-------|---------|
| `ok` | No configured step is missing and no step reported errors |
| `expected_steps` | Steps implied by the Auth configuration |
| `completed_steps` | Steps present in this invocation's result |
| `missing_steps` | Configured steps that did not run |
| `error_steps` | Completed steps whose result contains `errors > 0` |
| `reported_errors` | Sum of per-step error counts |
| `results` | Aggregate, secret-free results returned by the steps |

The expected steps are `token_cleanup` when token cleanup/storage is enabled,
`activity_sync` when activity tracking is enabled, and `api_key_usage_sync`
when Redis is enabled. This makes an unavailable configured Redis dependency a
failed report instead of an empty success.

`run_background_jobs_once()` remains available for compatibility and returns
the original raw dictionary. New scheduler and queue integrations should use
the typed method.

## CLI entry point

For Cron, a systemd timer, or a Kubernetes CronJob:

```bash
export DATABASE_URL='postgresql+asyncpg://auth_worker:...@db-host/app'
export OUTLABS_AUTH_SCHEMA='outlabs_auth'
export SECRET_KEY='...'

# Required when Redis-backed Auth features are configured:
export REDIS_URL='redis://cache-host:6379/0'
export OUTLABS_AUTH_REDIS_KEY_PREFIX='myapp:production'

outlabs-auth run-maintenance
```

The command prints the serialized `MaintenanceReport`. It exits `0` only when
`ok=true`, exits `1` for missing/error-bearing steps, and retains Click's exit
`2` for missing required configuration. Keep credentials in the executor
environment or secret store, never in command arguments or schedule payloads.

The CLI constructs `SimpleRBAC`. Hosts with EnterpriseRBAC, custom feature
flags, or injected services should use the programmatic entry point.

## Delivery and cadence

One cycle is at least once and is not a transaction across all steps. Earlier
steps may commit before a later step fails. The built-in operations are
retry-safe; retry the invocation rather than trying to roll back the cycle.

The host owns cadence. `run_maintenance_once()` executes every enabled step on
every invocation; the embedded-loop interval settings do not suppress work in
the one-shot path.

## Safe activation

1. Keep every API replica on `background_job_mode="disabled"`.
2. Use restricted runtime credentials, never migration-owner credentials.
3. Start the desired schedule paused and forbid overlap.
4. Confirm the executor can reach Postgres and configured Redis.
5. Run an explicit one-shot canary and require `report.ok`.
6. Activate the schedule, wait a complete interval, and observe one full run.
7. Monitor scheduler advancement, worker availability, report fields, and job
   outcomes independently of the API `/health` endpoint.

For rollback: stop the clock, pause the schedule, drain in-flight work, then
stop the worker. Keep API maintenance disabled; a reviewed manual one-shot is
safer than restoring an embedded loop.

## Optional TaskQ composition

TaskQ is one host integration, not an OutlabsAuth dependency. Register an
application-owned task that calls `run_maintenance_once()`, translate
`report.ok=false` into the queue's retry outcome, and start from a paused,
source-owned manifest. The TaskQ scheduler only enqueues; the worker needs the
application's Postgres/Redis connectivity.

Use an explicit one-shot job for the attended canary. Activating an interval
schedule normally starts from now, so its first occurrence is not due until one
complete interval has elapsed.

## Related

- [Configuration](./03-Configuration.md)
- [Deployment](./08-Deployment.md)
- [Activity Tracking](./49-Activity-Tracking.md)
- [Testing](./95-Testing-Guide.md)
- [Observability](./97-Observability.md)
