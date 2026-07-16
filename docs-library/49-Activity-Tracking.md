# DD-049: Activity Tracking System (DAU/MAU/WAU/QAU)

**Status**: ✅ Implemented
**Created**: 2025-01-24
**Implemented**: 2025-01-24
**Related**: DD-033 (Redis Counters), DD-036 (Performance Optimizations)

## Overview

### What is Activity Tracking?

Activity tracking measures user engagement through time-based metrics:

- **DAU** (Daily Active Users): Unique users active on a calendar day
- **MAU** (Monthly Active Users): Unique users active in a calendar month
- **QAU** (Quarterly Active Users): Unique users active in a calendar quarter

**WAU is not implemented.** Despite the DD title and several docstrings naming
it, there is no weekly key, query method, or `metric_type` - only daily,
monthly, and quarterly. See [Future Enhancements](#future-enhancements).

Note these are **calendar periods, not rolling windows**: MAU is "active in
January", not "active in the last 30 days". The daily set resets at UTC
midnight, the monthly set on the 1st, and the quarterly set at the start of
each quarter.

These metrics are essential for:
- Product analytics and dashboards
- Growth monitoring and forecasting
- User engagement analysis
- Retention cohort studies
- Business intelligence and reporting

### Why Not Use `last_login`?

The existing `User.last_login` field is **insufficient** for accurate activity tracking:

```python
# ❌ PROBLEM: Refresh tokens last 30 days
user.last_login = "2025-01-01T10:00:00Z"

# User's token is still valid on 2025-01-24 (23 days later)
# They're actively using the app daily, but last_login is stale
# This would show them as "inactive" for 23 days - WRONG!
```

**Key Issues**:
1. **Tokens last 30 days** - users don't re-login unless token expires
2. **No activity between logins** - API calls, page views, actions not tracked
3. **Inaccurate DAU/MAU** - would severely undercount active users
4. **Token refresh doesn't update it** - refresh flow bypasses login

### Solution: Redis-First Activity Tracking

Track activity on **every authenticated request** using:
1. **Redis Sets** for real-time tracking (O(1) operations, 99%+ write reduction)
2. **Background worker** for historical aggregation to PostgreSQL
3. **Optional `last_activity` field** on `User` (batched sync)

---

## Architecture

### High-Level Design

```
┌─────────────────┐
│ Auth Request    │
│ (JWT/API Key)   │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────┐
│  AuthDeps Middleware            │
│  - Verify token/key             │
│  - Extract user_id              │
│  - track_activity_detached()    │  ← Non-blocking
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│  ActivityTracker Service        │
│  - Redis SADD (O(1), pipelined) │
│  - Track: daily, monthly, QAU   │
│  - Update last_activity (Redis) │
└────────┬────────────────────────┘
         │
         ▼
    ┌────────┐
    │ Redis  │  active_users:daily:2025-01-24 → SET {user_id_1, user_id_2, ...}
    │ Sets   │  active_users:monthly:2025-01  → SET {user_id_1, ...}
    └────┬───┘  active_users:quarterly:2025-Q1 → SET {user_id_1, ...}
         │
         │ (Background sync — every activity_sync_interval, default 30 min)
         ▼
┌─────────────────────────────────┐
│  sync_to_database(session)      │
│  1. SCARD each Redis Set        │
│  2. Upsert ActivityMetric rows  │
│  3. Batch update User.last_act. │
│  4. Delete metrics > 90 days    │
└────────┬────────────────────────┘
         │
         ▼
    ┌────────────┐
    │ PostgreSQL │  activity_metrics: (metric_date=2025-01-24, metric_type="dau",
    │ Historical │                     count=1247, unique_users=1247)
    └────────────┘  users: (last_activity="2025-01-24T14:30:00Z")
```

Note the sync uses **SCARD** (a count), not SMEMBERS - it stores counts, never
the member ids.

### Key Components

#### 1. ActivityTracker Service (`outlabs_auth/services/activity_tracker.py`)

Core service responsible for:
- **Redis Set operations** (SADD, SCARD) via the library's `RedisClient`
- **Period key generation** (daily/monthly/quarterly)
- **Fire-and-forget tracking** (non-blocking, via `track_activity_detached`)
- **TTL management** (auto-expire old keys)
- **Query methods** (real-time counts from Redis)
- **`sync_to_database(session)`** (Redis → PostgreSQL aggregation)

#### 2. ActivityMetric Model (`outlabs_auth/models/sql/activity_metric.py`)

Historical snapshot table:
```python
class ActivityMetric(BaseModel, table=True):
    __tablename__ = "activity_metrics"
    __table_args__ = (
        UniqueConstraint("metric_date", "metric_type", name="uq_activity_metric_date_type"),
        Index("ix_activity_metrics_date", "metric_date"),
        Index("ix_activity_metrics_type", "metric_type"),
    )

    metric_date: date       # Date for this metric
    metric_type: str        # "dau", "mau", "qau", "logins", "registrations", "api_calls"
    count: int = 0          # Count for this metric
    unique_users: int = 0   # Unique user count (for DAU/MAU)
    snapshot_at: datetime   # When this snapshot was taken
```

The unique constraint on `(metric_date, metric_type)` is what makes the sync an
**upsert** - re-running it for the same day updates the row rather than
appending a second one.

Two sibling tables are declared in the same module - `user_activities`
(`UserActivity`) and `login_history` (`LoginHistory`). They are created and
migrated, but **no library service writes to them**; `ActivityTracker` only
writes `activity_metrics`. They exist for host applications to populate.

#### 3. User.last_activity

`User` carries both fields:
```python
class User(BaseModel, table=True):
    last_login: Optional[datetime] = None     # Only on login
    last_activity: Optional[datetime] = None  # Any authenticated action
```

**Update Strategy**:
- Store in Redis first: `last_activity:{user_id}` → timestamp
- Background sync writes it to PostgreSQL on the sync interval
- Avoids database write storms on every request
- Controlled by `activity_update_user_model` (default: `True`)

#### 4. Background Sync

`sync_to_database(session)` is the aggregation cycle. It:
- Upserts `dau` / `mau` / `qau` rows from the Redis set cardinalities
- Batch-updates `User.last_activity` from the `last_activity:*` keys
- Deletes `ActivityMetric` rows older than 90 days

The library can run it for you, or you can drive it yourself - see
[Running the Sync](#running-the-sync).

---

## Configuration

### Redis Dependency

**Activity tracking REQUIRES Redis** (uses Sets for O(1) operations).

```python
from outlabs_auth import OutlabsAuth

# ✅ VALID: Redis provided
auth = OutlabsAuth(
    database_url="postgresql+asyncpg://user:pass@localhost:5432/mydb",
    secret_key=secret,
    redis_url="redis://localhost:6379",
    enable_activity_tracking=True,
)

# ❌ INVALID: No Redis but tracking enabled
auth = OutlabsAuth(
    database_url=database_url,
    secret_key=secret,
    enable_activity_tracking=True,  # ERROR: requires redis_url
)

# ✅ VALID: Graceful - no tracking if Redis not available
auth = OutlabsAuth(
    database_url=database_url,
    secret_key=secret,
    enable_activity_tracking=False,  # OK - tracking disabled
)
```

**Validation** raises with:
```
Activity tracking requires Redis. Either:
1. Provide redis_url parameter, or
2. Set enable_activity_tracking=False
```

### Configuration Options

```python
class AuthConfig:
    # Activity Tracking Settings (DD-049 - requires Redis)
    enable_activity_tracking: bool = False
    """Enable DAU/MAU/WAU/QAU activity tracking (requires Redis)"""

    activity_sync_interval: int = 1800
    """Activity sync interval in seconds (default: 30 minutes)"""

    activity_update_user_model: bool = True
    """Update User.last_activity field via background sync"""

    activity_store_user_ids: bool = False
    """Store user IDs in ActivityMetric for cohort analysis (increases storage)"""

    activity_ttl_days: int = 90
    """Days to keep ActivityMetric records (default: 90 days)"""
```

**Note on `activity_store_user_ids`**: the setting exists and is passed through
to `ActivityTracker.store_user_ids`, but **nothing reads it** - `ActivityMetric`
has no user-id column, and the sync stores only counts. Setting it to `True`
has no effect today.

**Note on `activity_ttl_days`**: the config field exists, but
`_cleanup_old_metrics()` currently uses a hard-coded 90-day cutoff rather than
reading it. Changing the setting will not change the retention window.

### Configuration Presets

#### Preset 1: No Redis (SimpleRBAC Default)

```python
from outlabs_auth import SimpleRBAC

auth = SimpleRBAC(
    database_url=database_url,
    secret_key=secret,
    # No Redis, no activity tracking
)
```

**Features**: Basic authentication, no activity metrics

#### Preset 2: Redis for Security Only

```python
from outlabs_auth import SimpleRBAC

auth = SimpleRBAC(
    database_url=database_url,
    secret_key=secret,
    redis_url="redis://localhost:6379",
    store_refresh_tokens=False,      # Stateless mode
    enable_activity_tracking=False,  # Only use Redis for blacklist
)
```

**Features**: Immediate logout via blacklist, no activity tracking

#### Preset 3: Full Observability (EnterpriseRBAC)

```python
from outlabs_auth import EnterpriseRBAC

auth = EnterpriseRBAC(
    database_url=database_url,
    secret_key=secret,
    redis_url="redis://localhost:6379",
    enable_activity_tracking=True,    # DAU/MAU tracking
    activity_sync_interval=3600,      # Sync every hour
    activity_update_user_model=True,  # Update last_activity field
)
```

**Features**: Full activity tracking, historical metrics

### Configuration Matrix

| Redis | Refresh tokens | Activity | Use Case |
|-------|----------------|----------|----------|
| ❌ No | PostgreSQL | ❌ Off | Basic auth, no Redis |
| ✅ Yes | PostgreSQL | ❌ Off | Standard auth, Redis available but not used for tracking |
| ✅ Yes | PostgreSQL + blacklist | ❌ Off | High-security logout only |
| ✅ Yes | PostgreSQL + blacklist | ✅ On | Security + activity tracking |
| ✅ Yes | Stateless | ✅ On | Stateless auth + activity metrics |

---

## Data Models

### Redis Keys

#### Daily Active Users
```
Key:    active_users:daily:2025-01-24
Type:   SET
Members: ["user_id_1", "user_id_2", "user_id_3", ...]
TTL:    48 hours (expires 2025-01-26)
```

**Operations**:
- `SADD active_users:daily:2025-01-24 user_id_123` - O(1) add
- `SCARD active_users:daily:2025-01-24` - O(1) count

Writes are issued as a **single pipelined round trip** per request when the
Redis client exposes `record_activity_pipeline` (all three SADDs, their
EXPIREs, and the `last_activity` SET together). Clients without that helper
fall back to sequential operations.

#### Monthly Active Users
```
Key:    active_users:monthly:2025-01
Type:   SET
Members: ["user_id_1", "user_id_2", ...]
TTL:    90 days (expires 2025-04-01)
```

#### Quarterly Active Users
```
Key:    active_users:quarterly:2025-Q1
Type:   SET
Members: ["user_id_1", "user_id_2", ...]
TTL:    1 year (expires 2026-01-01)
```

#### Last Activity (per user)
```
Key:    last_activity:user_id_123
Type:   STRING
Value:  "2025-01-24T14:30:00Z"
TTL:    7 days
```

### PostgreSQL Tables

#### activity_metrics

One row per `(metric_date, metric_type)`:

| id | metric_date | metric_type | count | unique_users | snapshot_at |
|----|-------------|-------------|-------|--------------|-------------|
| uuid | 2025-01-24 | `dau` | 1247 | 1247 | 2025-01-24T23:59:00Z |
| uuid | 2025-01-01 | `mau` | 45892 | 45892 | 2025-01-24T23:59:00Z |
| uuid | 2025-01-01 | `qau` | 128453 | 128453 | 2025-01-24T23:59:00Z |

Note the **`metric_date` is the period's start date**, not a free-text label:
monthly metrics use the first of the month, quarterly metrics use the first
month of the quarter. `count` and `unique_users` are both set to the Redis set
cardinality by the sync.

**Constraints & Indexes**:
```python
UniqueConstraint("metric_date", "metric_type", name="uq_activity_metric_date_type")
Index("ix_activity_metrics_date", "metric_date")
Index("ix_activity_metrics_type", "metric_type")
```

#### users.last_activity

```python
last_login: Optional[datetime]     # Only on login
last_activity: Optional[datetime]  # Any authenticated action
```

**Differences**:
- `last_login`: Updated only when user logs in (email/password or OAuth)
- `last_activity`: Updated on ANY authenticated request (login, API call, token refresh)

### TTL Strategy

| Key Type | TTL | Reason |
|----------|-----|--------|
| Daily | 48 hours | Keep yesterday + today for overlap queries |
| Monthly | 90 days | Keep current + 2 previous months |
| Quarterly | 1 year | Keep current + 3 previous quarters |
| Last Activity | 7 days | Enough for weekly sync, then rely on PostgreSQL |

---

## Integration Points

### 1. AuthDeps Middleware (Primary Integration)

Track activity on **every authenticated request**:

```python
# In outlabs_auth/dependencies/__init__.py - after a strategy authenticates

if self.activity_tracker and result.get("user"):
    self.activity_tracker.track_activity_detached(
        str(result["user"].id)
    )
```

**Key Points**:
- Fire-and-forget via `track_activity_detached()` - never blocks the request
- Only tracks authenticated users
- Gracefully skips if activity tracking disabled
- Consistent with notification pattern (non-blocking events)

**Why `track_activity_detached()` and not a bare `asyncio.create_task()`?**
The helper retains a reference to the task (the event loop only holds weak
references, so an un-held task can be garbage-collected mid-run) and routes any
escaping exception to the logger instead of surfacing as "Task exception was
never retrieved".

### 2. Login Event

Tracked in `AuthService.login()` on successful authentication:

```python
# In outlabs_auth/services/auth.py - login()

# Update last_login
user.last_login = datetime.now(timezone.utc)
# No flush here — the user update, refresh token insert, and audit event
# share the caller's transaction and flush together at commit.

# Emit notification
if self.notifications:
    await self.notifications.emit(
        "user.login",
        data={"user_id": str(user.id), "email": user.email, ...},
        metadata={"ip": ip_address, "device": device_name, ...},
    )

# Track activity
if self.activity_tracker:
    self.activity_tracker.track_activity_detached(str(user.id))
```

### 3. Token Refresh Tracking

Tracked in `AuthService.refresh_access_token()` - a refresh indicates an active
session:

```python
# In outlabs_auth/services/auth.py - refresh_access_token()

# Track activity
if self.activity_tracker:
    self.activity_tracker.track_activity_detached(str(user.id))
```

### 4. API Key Usage Tracking

API key authentication is tracked **automatically via AuthDeps middleware** (same as JWT):

```python
# API key requests flow through AuthDeps.require_auth()
# Activity tracking happens after successful authentication

# Flow:
# 1. Request with API key → ApiKeyStrategy.authenticate()
# 2. Returns authenticated user
# 3. AuthDeps.require_auth() receives user → tracks activity
# 4. Request continues

# No explicit tracking needed in API key service!
# All authentication backends (JWT, API Key, Service Token)
# use the same tracking point for consistency.
```

**Why not track in API key service?**
- **DRY principle**: Single tracking point for all auth types
- **Consistency**: Same behavior for JWT, API Key, Service Token
- **Maintainability**: One place to update tracking logic
- **Non-blocking**: Fire-and-forget pattern in middleware

---

## Performance Characteristics

### Write Performance

**Redis SADD Operations**:
- **Time Complexity**: O(1)
- **Write Reduction**: 99%+ (only first activity per period writes)
- **Throughput**: 100K+ ops/sec (Redis SET operations)

**Example**:
```python
# User makes 1000 API calls in one day
for i in range(1000):
    tracker.track_activity_detached(user_id)

# ✅ RESULT: the set membership is established once
# ✅ Subsequent SADDs are no-ops (already in set)
# ✅ Huge write reduction vs a database write per request
```

### Memory Usage

**Redis Set Members**:
- ~16 bytes per user ID (UUID string)
- 1 million DAU = ~16 MB per day
- 3 periods (daily, monthly, quarterly) = ~48 MB per active day

**PostgreSQL Storage**:

`activity_metrics` stores counts only - three rows per sync
(dau/mau/qau), upserted in place. Storage is negligible: a few hundred rows per
year, and rows older than 90 days are deleted on each sync.

### Read Performance

| Operation | Complexity | Description |
|-----------|------------|-------------|
| Get DAU (today) | O(1) | `SCARD active_users:daily:2025-01-24` |
| Get MAU (current) | O(1) | `SCARD active_users:monthly:2025-01` |
| Get historical DAU | O(1) | Indexed `activity_metrics` lookup by `(metric_date, metric_type)` |
| Get last 30 days | O(N) | Range scan on `metric_date`, N = 30 rows |

### Background Sync Overhead

**Per `sync_to_database()` call** (default: every 30 min):
1. `SCARD` 3 Redis Sets - O(1) each
2. Upsert 3 `ActivityMetric` rows - O(1)
3. Batch update `User.last_activity` - SCAN `last_activity:*`, MGET each page,
   then one `executemany` UPDATE per 100-user batch
4. Delete `ActivityMetric` rows older than 90 days

The `last_activity` batch update is the dominant cost and scales with active
users; the metric upserts do not. Both the page fetch (MGET instead of
per-user GET) and the update (one executemany instead of a SELECT + ORM flush
per user) are batched to keep round trips proportional to batches, not users.

Set `activity_update_user_model=False` to skip step 3 entirely if you do not
need `User.last_activity` persisted.

---

## Query Patterns

### Real-Time Queries (Redis)

#### Get DAU (Today)
```python
dau = await activity_tracker.get_daily_active_users()
print(f"DAU (today): {dau}")  # 1,247 users
```

#### Get MAU (Current Month)
```python
mau = await activity_tracker.get_monthly_active_users()
print(f"MAU (current): {mau}")  # 45,892 users
```

#### Get QAU (Current Quarter)
```python
qau = await activity_tracker.get_quarterly_active_users()
print(f"QAU (current): {qau}")  # 128,453 users
```

#### Get Specific Date
```python
from datetime import date

dau_jan_15 = await activity_tracker.get_daily_active_users(date(2025, 1, 15))
print(f"DAU (Jan 15): {dau_jan_15}")
```

`get_daily_active_users` takes a `datetime.date` (not a string);
`get_monthly_active_users(year, month)` and
`get_quarterly_active_users(year, quarter)` take integers. All default to the
current period.

Note these read **Redis**, so they only answer for periods still within the
Redis TTL (48h daily, 90d monthly, 1y quarterly). Anything older must come from
`activity_metrics`.

### Historical Queries (PostgreSQL)

#### Get Last 30 Days
```python
from datetime import date, timedelta
from sqlmodel import select

end_date = date.today()
start_date = end_date - timedelta(days=30)

result = await session.execute(
    select(ActivityMetric)
    .where(
        ActivityMetric.metric_type == "dau",
        ActivityMetric.metric_date >= start_date,
        ActivityMetric.metric_date <= end_date,
    )
    .order_by(ActivityMetric.metric_date)
)
metrics = result.scalars().all()

# Plot DAU over time
for metric in metrics:
    print(f"{metric.metric_date}: {metric.count} users")
```

#### Calculate Growth Rate
```python
# Compare this month vs last month — monthly rows are keyed on the 1st
result = await session.execute(
    select(ActivityMetric).where(
        ActivityMetric.metric_type == "mau",
        ActivityMetric.metric_date.in_([date(2025, 1, 1), date(2024, 12, 1)]),
    )
)
by_date = {m.metric_date: m for m in result.scalars()}

current_month = by_date.get(date(2025, 1, 1))
previous_month = by_date.get(date(2024, 12, 1))

if current_month and previous_month and previous_month.count:
    growth = (current_month.count - previous_month.count) / previous_month.count * 100
    print(f"MAU Growth: {growth:.1f}%")
```

#### Calculate Average DAU
```python
from sqlalchemy import func

# Average DAU for January 2025 — computed in the database
result = await session.execute(
    select(func.avg(ActivityMetric.count)).where(
        ActivityMetric.metric_type == "dau",
        ActivityMetric.metric_date >= date(2025, 1, 1),
        ActivityMetric.metric_date < date(2025, 2, 1),
    )
)
avg_dau = result.scalar_one()
print(f"Average DAU (Jan): {avg_dau:.0f}")
```

### Cohort Analysis

**Not supported by this system.** `activity_metrics` stores counts only - there
is no per-user column - and the Redis sets that do hold user ids expire on their
TTL (48h daily, 90d monthly, 1y quarterly) and are never persisted.

Retention, churn, and engagement segmentation therefore cannot be computed from
`activity_metrics`. If you need them, either:

- Populate the `user_activities` table from your application (it has
  `user_id` + `activity_date` + per-type counts and is created for you, but
  nothing in the library writes it), or
- Read the Redis sets directly with `SMEMBERS`/`SINTER` **within the TTL
  window**, and persist whatever you need yourself.

---

## Running the Sync

Activity tracking is **already implemented** in the library - you enable it,
you do not build it. The only integration decision is *who runs the periodic
sync*.

### Option 1: External scheduler (recommended for production)

`run_background_jobs_once()` runs exactly one deterministic maintenance cycle
and starts no long-lived task. Drive it from Cron, a worker deployment, or any
host-owned scheduler:

```python
results = await auth.run_background_jobs_once()
# {"activity_sync": {"daily": 1247, "monthly": 45892, "quarterly": 128453,
#                    "users_updated": 1247, "errors": 0}, ...}
```

This also covers token cleanup and API key usage sync in the same cycle.

### Option 2: Embedded loop (single-process development)

Pass `background_job_mode="embedded"` and the library starts its own
`asyncio` loop that calls `sync_to_database()` every
`activity_sync_interval` seconds:

```python
auth = OutlabsAuth(
    database_url=database_url,
    secret_key=secret,
    redis_url="redis://localhost:6379",
    enable_activity_tracking=True,
    activity_sync_interval=1800,
    background_job_mode="embedded",
)
await auth.initialize()
```

Web processes should leave `background_job_mode` at `"disabled"` (the default)
and run the sync from exactly one dedicated worker process - otherwise every
web replica races to write the same metric rows.

### Option 3: Call the sync directly

```python
async with auth.get_session() as session:
    stats = await auth.activity_tracker.sync_to_database(session)
    await session.commit()
```

`sync_to_database()` never raises - it catches, logs, and reports failures in
`stats["errors"]`.


## API Usage Examples

### Basic Setup

```python
from outlabs_auth import OutlabsAuth

auth = OutlabsAuth(
    database_url="postgresql+asyncpg://user:pass@localhost:5432/mydb",
    secret_key="your-secret-key-at-least-32-characters",
    redis_url="redis://localhost:6379",
    enable_activity_tracking=True,
    activity_sync_interval=3600,  # Sync every hour
)

# Initialize
await auth.initialize()
```

### FastAPI Integration

```python
from fastapi import FastAPI, Depends
from outlabs_auth.dependencies import AuthDeps

app = FastAPI()
deps = AuthDeps(auth)

@app.get("/api/data")
async def get_data(ctx = Depends(deps.require_auth())):
    """Activity is tracked automatically on every authenticated request."""
    return {"message": "Hello", "user": ctx.metadata.get("user")}
```

### Query Real-Time Metrics

```python
# Get current DAU/MAU/QAU
dau = await auth.activity_tracker.get_daily_active_users()
mau = await auth.activity_tracker.get_monthly_active_users()
qau = await auth.activity_tracker.get_quarterly_active_users()

print(f"Current Metrics:")
print(f"  DAU: {dau:,}")
print(f"  MAU: {mau:,}")
print(f"  QAU: {qau:,}")
```

### Query Historical Data

```python
from datetime import date, timedelta

from sqlmodel import select

from outlabs_auth.models.sql.activity_metric import ActivityMetric

# Get last 30 days of DAU
end_date = date.today()
start_date = end_date - timedelta(days=30)

async with auth.get_session() as session:
    result = await session.execute(
        select(ActivityMetric)
        .where(
            ActivityMetric.metric_type == "dau",
            ActivityMetric.metric_date >= start_date,
        )
        .order_by(ActivityMetric.metric_date)
    )
    metrics = result.scalars().all()

# Export for dashboard
data = [
    {"date": m.metric_date.isoformat(), "active_users": m.count}
    for m in metrics
]
```

### Analytics Dashboard Endpoint

```python
@app.get("/admin/analytics/activity")
async def get_activity_analytics(
    metric_type: str = "dau",  # dau, mau, qau
    days: int = 30,
    ctx = Depends(deps.require_permission("analytics:read")),
):
    """Get activity metrics for analytics dashboard."""

    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    async with auth.get_session() as session:
        result = await session.execute(
            select(ActivityMetric)
            .where(
                ActivityMetric.metric_type == metric_type,
                ActivityMetric.metric_date >= start_date,
                ActivityMetric.metric_date <= end_date,
            )
            .order_by(ActivityMetric.metric_date)
        )
        metrics = result.scalars().all()

    return {
        "metric_type": metric_type,
        "date_range": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
        },
        "metrics": [
            {
                "metric_date": m.metric_date.isoformat(),
                "count": m.count,
                "unique_users": m.unique_users,
                "snapshot_at": m.snapshot_at.isoformat(),
            }
            for m in metrics
        ],
    }
```

---

## Testing Strategy

The tracker's own tests live in
`tests/unit/services/test_activity_tracker.py` and run against a **mocked
Redis client** - no Redis server required.

### Fixtures

```python
@pytest.fixture
def mock_redis():
    """Mock Redis client without the pipeline helper (exercises the per-op fallback path)."""
    redis = AsyncMock()
    redis.sadd = AsyncMock(return_value=1)
    redis.expire = AsyncMock(return_value=True)
    redis.set_raw = AsyncMock(return_value=True)
    redis.scard = AsyncMock(return_value=0)
    redis.scan = AsyncMock(return_value=(0, []))
    redis.get_raw = AsyncMock(return_value=None)
    del redis.record_activity_pipeline
    return redis


@pytest.fixture
def activity_tracker(mock_redis):
    return ActivityTracker(
        redis_client=mock_redis,
        enabled=True,
        update_user_model=True,
        store_user_ids=False,
    )
```

Deleting `record_activity_pipeline` off the mock is deliberate - it forces the
per-operation fallback path so the assertions can see individual `sadd`/
`expire` calls. To test the pipelined path instead, leave the attribute on the
mock and assert against `record_activity_pipeline`.

### Unit Tests

```python
class TestActivityTracking:
    @pytest.mark.asyncio
    async def test_track_activity_adds_to_daily_set(self, activity_tracker, mock_redis):
        """Track activity adds user to daily Redis Set."""
        user_id = "user_123"
        with patch.object(
            activity_tracker, "_make_daily_key", return_value="active_users:daily:test"
        ) as mock_key:
            await activity_tracker.track_activity(user_id)

        mock_key.assert_called_once()
        assert isinstance(mock_key.call_args.args[0], date)
        mock_redis.sadd.assert_any_call("active_users:daily:test", user_id)
        mock_redis.expire.assert_any_call("active_users:daily:test", 48 * 3600)

    @pytest.mark.asyncio
    async def test_track_activity_adds_to_monthly_set(self, activity_tracker, mock_redis):
        """Track activity adds user to monthly Redis Set."""
        user_id = "user_123"
        await activity_tracker.track_activity(user_id)

        now = datetime.now(timezone.utc)
        monthly_key = f"active_users:monthly:{now.year:04d}-{now.month:02d}"
        mock_redis.sadd.assert_any_call(monthly_key, user_id)
        mock_redis.expire.assert_any_call(monthly_key, 90 * 86400)
```

### Testing the Sync

`sync_to_database()` takes an `AsyncSession`, so exercising it end-to-end needs
a database session (see `tests/conftest.py` for the session fixtures). Because
it swallows all exceptions, assert on the returned `stats` dict rather than
expecting a raise:

```python
stats = await tracker.sync_to_database(session)
assert stats["errors"] == 0
assert stats["daily"] == 2
```

### A Note on Timing Assertions

Avoid wall-clock assertions like `assert avg_time < 5` - they are flaky on
shared CI. The existing suite asserts on **call shape** (which Redis commands
ran, with which keys and TTLs) instead, which is what the pipelining
optimization actually needs to protect.

---

## Migration & Rollout

### Enabling on Existing Systems

**Step 1**: Update dependencies
```bash
pip install --upgrade outlabs-auth
```

**Step 2**: Enable activity tracking (Redis is required)
```python
auth = OutlabsAuth(
    database_url=database_url,
    secret_key=secret,
    redis_url="redis://localhost:6379",  # NEW
    enable_activity_tracking=True,       # NEW
)
```

**Step 3**: Apply database migrations

The `activity_metrics` table and the `users.last_activity` column ship as
Alembic migrations in `outlabs_auth/migrations/versions/`. Either run your
migration step as usual, or pass `auto_migrate=True` to `OutlabsAuth`. There is
no manual index creation to do.

**Step 4**: Run the sync

Pick one of the options in [Running the Sync](#running-the-sync) - an external
scheduler calling `run_background_jobs_once()` for production, or
`background_job_mode="embedded"` for single-process development. Do not
hand-roll a loop.

### Backfilling Historical Data

**If you have existing login data**, you can seed rough historical metrics from
`users.last_login`:

```python
from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlmodel import select

from outlabs_auth.models.sql.activity_metric import ActivityMetric
from outlabs_auth.models.sql.user import User


async def backfill_activity_from_logins(session):
    """
    Backfill activity metrics from last_login timestamps.

    Note: This will UNDERCOUNT active users (tokens last 30 days).
    Use only for rough historical estimates.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)

    result = await session.execute(select(User).where(User.last_login >= cutoff))
    users = result.scalars().all()

    daily_counts = Counter(u.last_login.date() for u in users)

    for day, count in daily_counts.items():
        session.add(
            ActivityMetric(
                metric_date=day,
                metric_type="dau",
                count=count,
                unique_users=count,
                snapshot_at=datetime.now(timezone.utc),
            )
        )

    await session.commit()
    print(f"Backfilled {len(daily_counts)} days of activity data")
```

**Important**: `(metric_date, metric_type)` is unique, so this will conflict on
any day the real sync has already written. Backfill only days that predate
rollout, or upsert instead of inserting.

**Warning**: This will significantly undercount active users because:
- Users don't re-login for 30 days (token lifetime)
- API key usage not reflected in last_login
- Token refresh activity not captured

Note also that the sync deletes `ActivityMetric` rows older than 90 days, so
backfilled history beyond that window will be cleaned up on the next cycle.

**Recommendation**: Use backfilled data as baseline only, not for growth calculations.

---

## Monitoring & Observability

When an `ObservabilityService` is wired into `OutlabsAuth`, the tracker emits
both structured logs and Prometheus metrics.

### Emitted Metrics

| Metric | Type | Labels | Emitted by |
|--------|------|--------|------------|
| `outlabs_auth_activity_track_total` | counter | `period` (daily/monthly/quarterly) | `track_activity()` |
| `outlabs_auth_activity_sync_duration_seconds` | histogram | - | `sync_to_database()` |
| `outlabs_auth_activity_sync_records_total` | counter | `metric_type` (dau/mau/qau) | `sync_to_database()` |

Note `activity_track_total` increments **three times per tracked request** (one
per period), so it counts period-writes, not requests.

### Emitted Log Events

| Event | Level | Fields |
|-------|-------|--------|
| `activity_tracked` | DEBUG | `user_id`, `period` |
| `activity_sync_complete` | INFO, or WARNING when `errors > 0` | `duration_ms`, `records_synced`, `metric_types`, `errors` |

The tracker also logs on its own `outlabs_auth.services.activity_tracker`
logger:
```python
logger.debug(f"Tracked activity for user {user_id}")               # per track
logger.info("Activity sync completed: DAU=..., MAU=..., QAU=...")  # per sync
logger.error(f"Failed to track activity for user {user_id}: {e}")  # swallowed errors
```

Because `track_activity()` and `sync_to_database()` never raise, **the logs and
the `errors` counter are the only failure signal** - a broken Redis will not
surface as a failed request.

### What to Watch

1. **Redis Set Sizes** - daily set cardinality, monthly growth rate, memory usage
2. **Sync health** - `activity_sync_duration_seconds`, and `errors > 0` on `activity_sync_complete`
3. **Tracking volume** - `activity_track_total` flatlining means tracking has silently stopped

### Alerts

Set up alerts for:
- `activity_sync_complete` with `errors > 0` (repeated)
- Redis memory usage (> 80% capacity)
- `activity_track_total` dropping to zero while traffic continues
- Abnormal DAU drops (> 20% day-over-day)

---

## Best Practices

### 1. Start Simple
- Begin with `enable_activity_tracking=False`
- Enable after Redis is stable and tested
- Monitor performance impact (should be negligible)

### 2. Set Appropriate Sync Intervals
- **High traffic** (> 100K DAU): Sync every 15-30 min
- **Medium traffic** (10K-100K DAU): Sync every 30-60 min
- **Low traffic** (< 10K DAU): Sync every 1-2 hours

### 3. Run the Sync From One Process
- Leave `background_job_mode="disabled"` in web processes
- Drive `run_background_jobs_once()` from a single worker or Cron
- Multiple replicas syncing concurrently race on the same metric rows

### 4. Skip the User Update If You Don't Need It
- `activity_update_user_model=False` removes the sync's dominant cost
- DAU/MAU/QAU still work - only `User.last_activity` stops being persisted

### 5. TTL Management
- Keep Redis TTLs reasonable (48h daily, 90d monthly)
- `ActivityMetric` rows are deleted after 90 days by the sync; export to a
  warehouse first if you need longer history

### 6. Privacy Considerations
- User IDs live only in Redis, and only until the set TTL expires
- `activity_metrics` holds counts, never user ids - it is already anonymous
- For GDPR deletion, remove the user from the live Redis sets (`SREM`); there is
  nothing user-identifying to purge from `activity_metrics`

---

## Comparison with Alternatives

### vs. Updating `last_activity` on Every Request

| Approach | Writes | Accuracy | Scalability |
|----------|--------|----------|-------------|
| **PostgreSQL direct** | 1 write/request | 100% | ❌ Poor (write amplification on `users`) |
| **Redis Sets** | 1 write/user/day | 100% | ✅ Excellent (100K+ ops/sec) |
| **HyperLogLog** | 1 write/request | ~98% (probabilistic) | ✅ Excellent (low memory) |

**Winner**: Redis Sets (exact counts, large write reduction, scalable)

### vs. Writing `last_activity` Inline

```python
# ❌ ANTI-PATTERN: Don't do this
async def some_dependency(user: User, session: AsyncSession):
    user.last_activity = datetime.now(timezone.utc)
    await session.commit()  # Database write on EVERY request!
```

**Problems**:
- A write (and a row lock on `users`) on every authenticated request
- Puts database latency in the request path
- Doesn't provide DAU/MAU metrics
- Poor performance at scale

The Redis-first design keeps the request path at one pipelined Redis round trip
and defers all `users` writes to the batched sync.

### vs. Application-Level Tracking

Some apps track activity in application logs or analytics tools:

**Pros**:
- Flexible (can track any event)
- Works with existing analytics stack

**Cons**:
- Not integrated with auth system
- Requires separate infrastructure
- Difficult to query in real-time
- May miss server-side activity (API keys, service tokens)

**Verdict**: Use both - this system for auth-specific metrics, analytics tools for broader product metrics.

---

## Future Enhancements

### Phase 1 (Current)
- ✅ Basic DAU/MAU/QAU tracking
- ✅ Redis Sets for real-time data
- ✅ PostgreSQL (`activity_metrics`) for historical snapshots
- ✅ Background sync worker

### Phase 2 (Future)
- Weekly Active Users (WAU) metric
- Rolling 7-day, 28-day windows
- Real-time dashboard widgets
- Export to analytics platforms (Mixpanel, Amplitude)

### Phase 3 (Advanced)
- Cohort retention analysis
- Engagement scoring (daily users vs weekly vs monthly)
- Predictive churn detection
- A/B test integration (track by experiment group)

---

## Related Documentation

- **DD-033**: Redis Counters for API Keys (similar pattern)
- **DD-036**: Performance Optimizations (closure tables)
- **12-Data-Models.md**: User model and database schema
- **22-JWT-Tokens.md**: Authentication flow and token refresh

---

## Summary

**Activity tracking provides accurate DAU/MAU/QAU metrics** by:

1. **Redis Sets** for O(1) tracking (large write reduction)
2. **Fire-and-forget** integration (non-blocking, via `track_activity_detached`)
3. **Background sync** to PostgreSQL `activity_metrics` (historical data)
4. **Optional `User.last_activity`** (batched updates)
5. **Graceful degradation** - tracking never raises into the request path

**Configuration**:
- Requires Redis (validation enforced)
- Opt-in via `enable_activity_tracking=True`
- Configurable sync interval

**Performance**:
- One pipelined Redis round trip per authenticated request
- ~16 MB/day of Redis for 1M DAU (x3 for the three period sets)
- Sync cost is dominated by the `User.last_activity` batch update, which can be
  turned off with `activity_update_user_model=False`

**Use Cases**:
- Product analytics dashboards
- Growth monitoring and forecasting
- User engagement analysis

**Not covered**: WAU, cohort/retention analysis, and per-user history. The
tracker records daily/monthly/quarterly **counts** only.
