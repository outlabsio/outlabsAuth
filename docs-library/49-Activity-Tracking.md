# Activity Tracking (DAU / MAU / …)

> **Handbook · Reference** — engagement counters for host apps.  
> Part of the [OutlabsAuth Handbook](./README.md). Design history: DD-049 in
> [`docs/DESIGN_DECISIONS.md`](../docs/DESIGN_DECISIONS.md).

Optional Redis-backed unique-user sets so dashboards can show **calendar** DAU /
MAU / QAU without treating `User.last_login` as “active today.”

---

## What you get

| Metric | Meaning |
|--------|---------|
| **DAU** | Unique users active on a calendar day (UTC) |
| **MAU** | Unique users active in a calendar month |
| **QAU** | Unique users active in a calendar quarter |

**WAU is not implemented** (no weekly keys or queries).

These are **calendar periods**, not rolling windows: MAU is “active in January,”
not “active in the last 30 days.”

`last_login` alone undercounts: long-lived refresh tokens mean users stay active
for days without a fresh login. Activity tracking records presence on
authenticated traffic instead.

---

## Requirements

- **`redis_url`** — required when tracking is on (Redis Sets)
- **`enable_activity_tracking=True`** — default is `False`

```python
auth = EnterpriseRBAC(  # or SimpleRBAC / OutlabsAuth
    database_url=...,
    secret_key=...,
    redis_url="redis://localhost:6379/0",
    enable_activity_tracking=True,
)
```

If tracking is enabled without Redis, initialization fails with a clear error.
Leave the flag off when you do not need these metrics.

---

## How it works

1. On authenticated requests (and some login paths), the library schedules
   `activity_tracker.track_activity_detached(user_id)` — non-blocking.
2. Redis Sets hold the current day / month / quarter memberships (O(1) add).
3. A background sync (default every 30 minutes) writes counts into Postgres
   `activity_metrics` for history and optionally updates `User.last_activity`.

You rarely talk to Redis yourself for dashboards older than the Redis TTL —
query `activity_metrics` for history; use tracker helpers for “right now.”

---

## Configuration knobs

| Setting | Default | Purpose |
|---------|---------|---------|
| `enable_activity_tracking` | `False` | Master switch (needs Redis) |
| `activity_sync_interval` | `1800` | Seconds between Redis → Postgres sync |
| `activity_update_user_model` | `True` | Sync `User.last_activity` in the background job |
| `activity_store_user_ids` | `False` | **No effect today** — passed through but unused |
| `activity_ttl_days` | `90` | Intended retention; cleanup still uses a hard-coded ~90-day cutoff |

---

## Querying

Access the tracker after `await auth.initialize()` via `auth.activity_tracker`
(only when enabled).

### Live (Redis)

```python
from datetime import date

dau = await auth.activity_tracker.get_daily_active_users()
mau = await auth.activity_tracker.get_monthly_active_users()
qau = await auth.activity_tracker.get_quarterly_active_users()

# Specific periods
dau_past = await auth.activity_tracker.get_daily_active_users(date(2025, 1, 15))
mau_past = await auth.activity_tracker.get_monthly_active_users(2025, 1)
qau_past = await auth.activity_tracker.get_quarterly_active_users(2025, 1)
```

Redis answers only while keys remain within TTL (roughly days for DAU, months
for MAU, longer for QAU). Older periods → Postgres.

### Historical (Postgres)

```python
from datetime import date, timedelta
from sqlmodel import select
from outlabs_auth.models.sql.activity_metric import ActivityMetric

end = date.today()
start = end - timedelta(days=30)

result = await session.execute(
    select(ActivityMetric)
    .where(
        ActivityMetric.metric_type == "dau",
        ActivityMetric.metric_date >= start,
        ActivityMetric.metric_date <= end,
    )
    .order_by(ActivityMetric.metric_date)
)
for row in result.scalars():
    print(row.metric_date, row.count)
```

Monthly rows are keyed on the **1st of the month**.

There is **no packaged HTTP router** for DAU/MAU — expose your own admin
endpoint that calls the tracker or reads `activity_metrics`.

---

## Ops notes

- Sync runs inside the auth process when tracking is enabled; multi-worker hosts
  should expect concurrent syncs to be idempotent upserts, not a separate
  required worker process.
- Prometheus / structured logs may emit activity-related signals when
  observability is on — see [Observability](./97-Observability.md) and
  [Metrics Reference](./98-Metrics-Reference.md).
- For “last seen” UX, prefer `User.last_activity` (when sync updates it) over
  inventing your own counter.

---

## Related

- [Configuration](./03-Configuration.md)
- [JWT Tokens](./22-JWT-Tokens.md) — why refresh lifetime skews `last_login`
- [Design decision DD-049](../docs/DESIGN_DECISIONS.md) — maintainer depth
