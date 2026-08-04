# Background Maintenance

> **Handbook** · Run OutlabsAuth cleanup and sync work outside the API process.
> Part of the [OutlabsAuth Handbook](./README.md).

OutlabsAuth has periodic maintenance work: expired-token cleanup, optional
activity aggregation, and Redis-backed API-key usage sync. In production, keep
that work out of FastAPI workers.

The production rule is:

```text
one scheduler clock -> one worker invocation -> run_background_jobs_once()
```

| Component | Responsibility |
|-----------|----------------|
| API / web processes | Serve requests with `background_job_mode="disabled"` |
| Host scheduler | Decide when work is due; optionally enqueue a task |
| Worker or one-shot job | Initialize OutlabsAuth and run one maintenance cycle |
| OutlabsAuth | Perform the enabled cleanup and sync steps |

The scheduler and worker may run on the same machine or on different machines.
A locally supervised worker is a normal production choice. Put it in the cloud
only when availability or network access requires that placement. The process
that executes maintenance needs direct access to the host application's
Postgres database and, when configured, Redis.

---

## Supported entry points

### CLI

The CLI is the simplest Cron, systemd-timer, Kubernetes CronJob, or one-shot
integration:

```bash
export DATABASE_URL='postgresql+asyncpg://auth_worker:...@db-host/app'
export OUTLABS_AUTH_SCHEMA='outlabs_auth'
export SECRET_KEY='...'

# Required only when this host uses Redis-backed auth features:
export REDIS_URL='redis://cache-host:6379/0'
export OUTLABS_AUTH_REDIS_KEY_PREFIX='myapp:production'

outlabs-auth run-maintenance
```

The command initializes OutlabsAuth with background loops disabled, performs
one cycle, prints a JSON result, and exits. Keep secrets in the worker's secret
store or environment; do not put them in command-line flags or schedule
payloads.

The CLI uses the standard `SimpleRBAC` maintenance configuration. If the host
has custom feature flags or service wiring, use the programmatic entry point so
the worker and API share the same auth factory.

### Programmatic

Use `run_background_jobs_once()` from a queue task or host-owned worker:

```python
async def run_auth_maintenance() -> dict[str, object]:
    auth = build_auth(background_job_mode="disabled")  # same host config as the API
    try:
        await auth.initialize()
        return await auth.run_background_jobs_once()
    finally:
        await auth.shutdown()
```

`build_auth()` is host code in this example. It should select the same preset,
schema, Redis prefix, and feature flags as the API. It must not start embedded
loops. `"taskq"`, `"cron"`, and similar values are not OutlabsAuth modes; those
schedulers call the one-shot API while the library remains in `"disabled"`
mode.

---

## What one cycle does

`run_background_jobs_once()` runs the applicable steps in this order:

1. expired and revoked refresh-token cleanup, when enabled;
2. activity aggregation, when activity tracking is enabled;
3. API-key usage sync, when the API-key service and Redis are available.

The returned dictionary contains only the steps that applied. For example, the
`api_key_usage_sync` key is absent when Redis is not configured or available.
The built-in result values are aggregate counts and statistics, suitable for
structured logs and job telemetry.

Inspect the result as well as the process exit status. Activity and API-key sync
can report a non-zero nested `errors` count without making the overall command
exit non-zero. Alert on those counts and on an unexpectedly absent step.

### Delivery and retry semantics

A cycle is **not one transaction across all three steps**. Token cleanup and
activity sync each commit independently, and API-key sync has its own durable
batch/receipt flow. A later failure can therefore leave earlier work committed.

Treat delivery as **at least once**:

- retry a failed invocation rather than trying to roll back the whole cycle;
- do not interpret a missing result key as a successful zero-count run;
- record the exit status and returned per-step counts;
- make any host wrapper idempotent and tolerant of partial progress.

The built-in operations are designed to be safely retried. In particular,
API-key usage sync stages Redis counters and records a database receipt so a
retry does not double-apply a committed batch.

---

## Production safety contract

Before activation, verify all of the following:

- exactly one logical scheduler clock owns this database and environment;
- every API replica uses `background_job_mode="disabled"`;
- the executor uses restricted runtime credentials, not migration-owner
  credentials;
- the executor can reach Postgres and the host's Redis, when Redis is enabled;
- secrets live in the executor environment, never in a schedule manifest;
- the schedule starts paused, forbids overlapping executions, and its worker
  queue has a concurrency of one unless the host has proved parallel runs safe;
- scheduler lag, worker availability, job outcomes, and returned step counts
  are monitored independently of the API `/health` endpoint.

Do not rely on the one-clock rule alone for correctness. Schedulers and queues
can redeliver work, so the execution path must retain at-least-once semantics.

### Choosing an interval

The host owns the cadence. Pick it from the actual freshness requirement and
the slowest acceptable cleanup delay; there is no universal five-minute rule.

The external one-shot call runs **every enabled, applicable step on every
invocation**. Settings such as `token_cleanup_interval_hours`,
`activity_sync_interval`, and `api_key_usage_sync_interval` control embedded
loops; they do not skip work inside `run_background_jobs_once()`. It is fine for
a single host schedule to run all steps more frequently than some strictly
require, provided the observed load is acceptable.

### Preventing accidental production execution

Pausing a schedule prevents new scheduled occurrences; it does not make a
worker's database configuration safe. Treat environment identity as part of
worker startup:

- use distinct database credentials, Redis prefixes, task namespaces, and
  queues for development, staging, and production;
- never fall back to a production URL when a local environment variable or
  dotenv file is missing;
- require an explicit environment label and fail startup when it conflicts
  with the selected queue or expected database identity;
- log the environment, database host/name, schema, Redis prefix, and queue at
  startup with credentials redacted;
- inspect and drain stale queued jobs before attaching a worker to a production
  queue.

A local worker can intentionally serve production. The safety boundary is its
explicit configuration and restricted credentials, not whether it runs in a
container or in the cloud.

---

## Optional TaskQ pattern

TaskQ is one possible host scheduler; it is not an OutlabsAuth dependency. A
typical integration registers a host task that calls
`run_background_jobs_once()`, then starts with a paused manifest like this:

```yaml
version: 1
namespace: myapp
source: api-deployment
schedules:
  auth-maintenance:
    display_name: OutlabsAuth deterministic maintenance
    task: myapp.auth.maintenance
    queue: auth_maintenance
    interval_seconds: 300
    catchup: fire_once
    overlap: forbid
    max_lateness_seconds: 900
    state: paused
    payload:
      mode: all
```

The task name and payload belong to the host adapter; they are not built into
OutlabsAuth. The scheduler only enqueues. A supervised worker—local or
remote—executes the task and needs Postgres/Redis connectivity.

With interval schedules, activation normally means **from now**: the first
occurrence becomes due after one full interval. If you want an immediate
canary, enqueue one explicit one-shot job instead of changing catch-up behavior.

The same rules apply to Cron, Celery Beat, Kubernetes CronJobs, and managed
schedulers: one clock, no overlap, external execution, and retry-safe delivery.

---

## Staged activation

1. Run `outlabs-auth doctor`, migrate, and confirm the schema is at head.
2. Validate the executor's environment identity and create the schedule paused.
3. Confirm all API replicas have embedded background jobs disabled.
4. Confirm its queue has no stale jobs, then start the worker and exactly one
   scheduler while the schedule remains paused.
5. Run one explicit maintenance invocation and inspect its JSON result.
6. Activate the interval schedule and verify one occurrence reaches one worker.
7. Confirm scheduler advancement, due lag, job success, and step counts.

This sequence reduces the chance that a deploy creates two maintenance owners
or points an incorrectly configured worker at production.

## Rollback

Use a stop-first rollback:

1. stop the scheduler clock;
2. pause the schedule;
3. let an in-flight job finish or drain it, then stop the worker;
4. keep API maintenance disabled and use manual one-shot runs if necessary.

Only restore `background_job_mode="embedded"` as a temporary fallback when the
host is provably single-process. It is unsafe as a fallback in a multi-replica
API because every replica can become a scheduler.

## Tests for a host integration

- Run the one-shot entry point against a representative Postgres/Redis test
  environment and assert the expected result keys.
- Repeat the invocation and simulate a retry after partial completion.
- Prove one scheduled occurrence creates one worker job.
- Prove API startup does not start a second maintenance owner.
- Rehearse pause, drain, and manual one-shot rollback before production.

---

## Related

- [Configuration](./03-Configuration.md)
- [Deployment](./08-Deployment.md)
- [Testing](./95-Testing-Guide.md)
- [Observability](./97-Observability.md)
- [Maintainer deployment guide](../docs/DEPLOYMENT_GUIDE.md)
