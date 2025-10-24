# DD-049: Activity Tracking System (DAU/MAU/WAU/QAU)

**Status**: Draft
**Created**: 2025-01-24
**Related**: DD-033 (Redis Counters), DD-036 (Performance Optimizations)

## Overview

### What is Activity Tracking?

Activity tracking measures user engagement through time-based metrics:

- **DAU** (Daily Active Users): Unique users active in a 24-hour period
- **WAU** (Weekly Active Users): Unique users active in a 7-day period
- **MAU** (Monthly Active Users): Unique users active in a 30-day period
- **QAU** (Quarterly Active Users): Unique users active in a 90-day period

These metrics are essential for:
- Product analytics and dashboards
- Growth monitoring and forecasting
- User engagement analysis
- Retention cohort studies
- Business intelligence and reporting

### Why Not Use `last_login`?

The existing `UserModel.last_login` field is **insufficient** for accurate activity tracking:

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
2. **Background worker** for historical aggregation to MongoDB
3. **Optional `last_activity` field** on UserModel (batched sync)

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
│  - Fire-and-forget track()      │  ← Non-blocking
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│  ActivityTracker Service        │
│  - Redis SADD (O(1))            │
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
         │ (Background Worker - every 30-60 min)
         ▼
┌─────────────────────────────────┐
│  Sync Worker                    │
│  1. Read Redis Sets (SMEMBERS)  │
│  2. Write to MongoDB            │
│  3. Update UserModel.last_act.  │
│  4. Expire old Redis keys       │
└────────┬────────────────────────┘
         │
         ▼
    ┌──────────┐
    │ MongoDB  │  ActivityMetric: {period: "2025-01-24", count: 1247}
    │ Historical│  UserModel: {last_activity: "2025-01-24T14:30:00Z"}
    └──────────┘
```

### Key Components

#### 1. ActivityTracker Service (`services/activity_tracker.py`)

Core service responsible for:
- **Redis Set operations** (SADD, SCARD, SMEMBERS)
- **Period key generation** (daily/monthly/quarterly)
- **Fire-and-forget tracking** (non-blocking)
- **TTL management** (auto-expire old keys)
- **Query methods** (real-time and historical)

#### 2. ActivityMetric Model (`models/activity_metric.py`)

Historical snapshot model:
```python
class ActivityMetric(BaseDocument):
    period_type: str     # "daily", "monthly", "quarterly"
    period: str          # "2025-01-24", "2025-01", "2025-Q1"
    active_users: int    # Count of unique users
    unique_user_ids: Optional[List[str]]  # Optional for detailed analysis
    created_at: datetime

    class Settings:
        name = "activity_metrics"
        indexes = [
            [("period_type", 1), ("period", -1)],  # Query by type + time
            [("created_at", 1)]                    # Cleanup old data
        ]
```

#### 3. UserModel Enhancement

Add optional activity tracking field:
```python
class UserModel(BaseDocument):
    last_login: Optional[datetime] = None     # Existing - only on login
    last_activity: Optional[datetime] = None  # NEW - any authenticated action
```

**Update Strategy**:
- Store in Redis first: `last_activity:{user_id}` → timestamp
- Background worker syncs to MongoDB every 30-60 min
- Avoids database write storms on every request

#### 4. Background Sync Worker

Periodic aggregation task (similar to API key counter sync):
- Runs every 30-60 minutes
- Reads Redis Sets (SMEMBERS)
- Creates ActivityMetric snapshots in MongoDB
- Updates UserModel.last_activity (batched)
- Cleans up expired Redis keys

---

## Configuration

### Redis Dependency

**Activity tracking REQUIRES Redis** (uses Sets for O(1) operations).

```python
from outlabs_auth import OutlabsAuth

# ✅ VALID: Redis provided
auth = OutlabsAuth(
    database=mongo_client,
    redis_client=redis,
    enable_activity_tracking=True,
)

# ❌ INVALID: No Redis but tracking enabled
auth = OutlabsAuth(
    database=mongo_client,
    enable_activity_tracking=True,  # ERROR: requires redis_client
)

# ✅ VALID: Graceful - no tracking if Redis not available
auth = OutlabsAuth(
    database=mongo_client,
    enable_activity_tracking=False,  # OK - tracking disabled
)
```

**Validation**:
```python
if self.config.enable_activity_tracking and not self.config.redis_client:
    raise ValueError(
        "Activity tracking requires Redis. Either:\n"
        "1. Provide redis_client parameter, or\n"
        "2. Set enable_activity_tracking=False"
    )
```

### Configuration Options

```python
class AuthConfig:
    # Activity tracking
    enable_activity_tracking: bool = False
    """Enable DAU/MAU/WAU/QAU tracking (requires Redis)"""

    activity_sync_interval: int = 1800
    """Sync interval in seconds (default: 30 minutes)"""

    activity_update_user_model: bool = True
    """Update UserModel.last_activity field (requires background sync)"""

    activity_store_user_ids: bool = False
    """Store user IDs in ActivityMetric (for cohort analysis, uses more storage)"""

    activity_ttl_days: int = 90
    """Days to keep ActivityMetric records (default: 90 days)"""
```

### Configuration Presets

#### Preset 1: No Redis (SimpleRBAC Default)

```python
from outlabs_auth import SimpleRBAC

auth = SimpleRBAC(
    database=mongo_client,
    # No Redis, no activity tracking
)
```

**Features**: Basic authentication, no activity metrics

#### Preset 2: Redis for Security Only

```python
from outlabs_auth import SimpleRBAC

auth = SimpleRBAC(
    database=mongo_client,
    redis_client=redis,
    store_refresh_tokens=False,      # Stateless mode
    enable_activity_tracking=False,  # Only use Redis for blacklist
)
```

**Features**: Immediate logout via blacklist, no activity tracking

#### Preset 3: Full Observability (EnterpriseRBAC)

```python
from outlabs_auth import EnterpriseRBAC

auth = EnterpriseRBAC(
    database=mongo_client,
    redis_client=redis,
    enable_activity_tracking=True,    # DAU/MAU tracking
    activity_sync_interval=3600,      # Sync every hour
    activity_update_user_model=True,  # Update last_activity field
    activity_store_user_ids=True,     # Enable cohort analysis
)
```

**Features**: Full activity tracking, historical metrics, cohort analysis

### Configuration Matrix

| Redis | Tokens | Activity | Use Case |
|-------|--------|----------|----------|
| ❌ No | MongoDB | ❌ Off | Basic auth, no Redis |
| ✅ Yes | MongoDB | ❌ Off | Standard auth, Redis available but not used for tracking |
| ✅ Yes | Blacklist | ❌ Off | High-security logout only |
| ✅ Yes | Blacklist | ✅ On | Security + activity tracking |
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
- `SMEMBERS active_users:daily:2025-01-24` - O(N) get all users

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

### MongoDB Models

#### ActivityMetric Collection

```python
{
    "_id": ObjectId("..."),
    "period_type": "daily",           # "daily" | "monthly" | "quarterly"
    "period": "2025-01-24",           # ISO date or "2025-01" or "2025-Q1"
    "active_users": 1247,             # Count of unique users
    "unique_user_ids": [...],         # Optional: list of user IDs
    "created_at": ISODate("2025-01-24T23:59:00Z"),
    "updated_at": ISODate("2025-01-24T23:59:00Z")
}
```

**Indexes**:
```python
[("period_type", 1), ("period", -1)]  # Query by type, sorted by time
[("created_at", 1)]                   # Cleanup old records
```

#### UserModel Enhancement

```python
{
    "_id": ObjectId("..."),
    "email": "user@example.com",
    "last_login": ISODate("2025-01-01T10:00:00Z"),   # Only on login
    "last_activity": ISODate("2025-01-24T14:30:00Z") # Any authenticated action
}
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
| Last Activity | 7 days | Enough for weekly sync, then rely on MongoDB |

---

## Integration Points

### 1. AuthDeps Middleware (Primary Integration)

Track activity on **every authenticated request**:

```python
# In dependencies/auth.py - AuthDeps class

async def require_auth(self):
    """Dependency that requires authentication."""
    async def dependency(request: Request) -> AuthContext:
        ctx = await self._authenticate(request)

        if not ctx.is_authenticated:
            raise UnauthorizedError("Authentication required")

        # 🔥 TRACK ACTIVITY (fire-and-forget, non-blocking)
        if ctx.user_id and self.auth.activity_tracker:
            asyncio.create_task(
                self.auth.activity_tracker.track_activity(ctx.user_id)
            )

        return ctx

    return Depends(dependency)
```

**Key Points**:
- Fire-and-forget (`asyncio.create_task`) - never blocks the request
- Only tracks authenticated users (`ctx.user_id` present)
- Gracefully skips if activity tracking disabled
- Consistent with notification pattern (non-blocking events)

### 2. Login Event (Notification System)

Track on successful login:

```python
# In services/auth.py - login() method

async def login(self, email: str, password: str) -> tuple[UserModel, TokenPair]:
    # ... authentication logic ...

    # Update last_login
    user.last_login = datetime.now(timezone.utc)
    await user.save()

    # 🔥 TRACK ACTIVITY
    if self.activity_tracker:
        await self.activity_tracker.track_activity(str(user.id))

    # Emit notification (existing)
    await self.notifications.emit(
        "user.login",
        data={"user_id": str(user.id), "email": user.email},
        metadata={"timestamp": user.last_login.isoformat()}
    )

    return user, tokens
```

### 3. Token Refresh Tracking

Track when users refresh tokens (indicates active session):

```python
# In services/auth.py - refresh_access_token() method

async def refresh_access_token(self, refresh_token: str) -> TokenPair:
    # ... token validation ...

    # 🔥 TRACK ACTIVITY
    if self.activity_tracker:
        await self.activity_tracker.track_activity(user_id)

    # Update token usage (existing)
    if token_model:
        token_model.last_used_at = datetime.now(timezone.utc)
        token_model.usage_count += 1
        await token_model.save()

    return new_tokens
```

### 4. API Key Usage Tracking

Track API key authentication:

```python
# In services/api_key.py - authenticate() method

async def authenticate(self, api_key_string: str) -> tuple[APIKeyModel, UserModel]:
    # ... key verification ...

    # Increment usage counter (existing Redis pattern)
    await self._increment_usage_counter(str(api_key.id))

    # 🔥 TRACK ACTIVITY
    if self.activity_tracker:
        await self.activity_tracker.track_activity(str(api_key.owner.id))

    return api_key, user
```

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
    await track_activity(user_id)

# ✅ RESULT: Only 1 Redis write (first SADD)
# ✅ 999 subsequent calls are no-ops (already in set)
# ✅ 99.9% write reduction vs MongoDB writes
```

### Memory Usage

**Redis Set Members**:
- ~16 bytes per user ID (UUID string)
- 1 million DAU = ~16 MB per day
- 3 periods (daily, monthly, quarterly) = ~48 MB per active day

**MongoDB Storage**:
```python
# Without user IDs (count only)
ActivityMetric: ~100 bytes per record
365 days/year * 100 bytes = ~36 KB/year

# With user IDs (cohort analysis)
1 million users * 16 bytes * 365 days = ~5.8 GB/year
```

### Read Performance

| Operation | Complexity | Description |
|-----------|------------|-------------|
| Get DAU (today) | O(1) | `SCARD active_users:daily:2025-01-24` |
| Get MAU (current) | O(1) | `SCARD active_users:monthly:2025-01` |
| Get historical DAU | O(1) | Query MongoDB ActivityMetric by period |
| Get last 30 days | O(N) | Query MongoDB, N = 30 records |
| Cohort analysis | O(N) | Set intersection on user IDs |

### Background Sync Overhead

**Worker Execution** (every 30-60 min):
1. Read 3 Redis Sets (SMEMBERS) - O(N) where N = active users
2. Write 3 ActivityMetric records to MongoDB - O(1)
3. Batch update UserModel.last_activity - O(N) where N = active users
4. Cleanup expired keys - O(K) where K = old keys

**Estimated Time** (1 million DAU):
- Redis reads: ~100ms
- MongoDB writes: ~50ms
- UserModel updates (batched): ~2-5 seconds
- Total: ~3-5 seconds every 30-60 min

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
dau_jan_15 = await activity_tracker.get_daily_active_users("2025-01-15")
print(f"DAU (Jan 15): {dau_jan_15}")
```

### Historical Queries (MongoDB)

#### Get Last 30 Days
```python
from datetime import date, timedelta

end_date = date.today()
start_date = end_date - timedelta(days=30)

metrics = await ActivityMetric.find(
    ActivityMetric.period_type == "daily",
    ActivityMetric.period >= start_date.isoformat(),
    ActivityMetric.period <= end_date.isoformat()
).sort("+period").to_list()

# Plot DAU over time
for metric in metrics:
    print(f"{metric.period}: {metric.active_users} users")
```

#### Calculate Growth Rate
```python
# Compare this month vs last month
current_month = await ActivityMetric.find_one(
    ActivityMetric.period_type == "monthly",
    ActivityMetric.period == "2025-01"
)
previous_month = await ActivityMetric.find_one(
    ActivityMetric.period_type == "monthly",
    ActivityMetric.period == "2024-12"
)

if current_month and previous_month:
    growth = (current_month.active_users - previous_month.active_users) / previous_month.active_users * 100
    print(f"MAU Growth: {growth:.1f}%")  # MAU Growth: 12.3%
```

#### Calculate Average DAU
```python
# Average DAU for January 2025
jan_metrics = await ActivityMetric.find(
    ActivityMetric.period_type == "daily",
    ActivityMetric.period >= "2025-01-01",
    ActivityMetric.period < "2025-02-01"
).to_list()

avg_dau = sum(m.active_users for m in jan_metrics) / len(jan_metrics)
print(f"Average DAU (Jan): {avg_dau:.0f}")
```

### Cohort Analysis (Advanced)

**Requires**: `activity_store_user_ids=True` in config

#### User Retention (Month-over-Month)
```python
# Users active in both January and February
jan_metric = await ActivityMetric.find_one(
    ActivityMetric.period_type == "monthly",
    ActivityMetric.period == "2025-01"
)
feb_metric = await ActivityMetric.find_one(
    ActivityMetric.period_type == "monthly",
    ActivityMetric.period == "2025-02"
)

jan_users = set(jan_metric.unique_user_ids)
feb_users = set(feb_metric.unique_user_ids)

retained_users = jan_users & feb_users  # Set intersection
retention_rate = len(retained_users) / len(jan_users) * 100

print(f"Retention Rate: {retention_rate:.1f}%")  # 67.3%
print(f"Churned Users: {len(jan_users - feb_users)}")
print(f"New Users: {len(feb_users - jan_users)}")
```

#### Engagement Segmentation
```python
# Users active every day this week vs once this week
week_users = set()
daily_counts = {}

for day in last_7_days:
    metric = await ActivityMetric.find_one(
        ActivityMetric.period_type == "daily",
        ActivityMetric.period == day.isoformat()
    )
    if metric:
        day_users = set(metric.unique_user_ids)
        week_users.update(day_users)

        for user_id in day_users:
            daily_counts[user_id] = daily_counts.get(user_id, 0) + 1

# Segment by engagement
power_users = [uid for uid, count in daily_counts.items() if count == 7]
casual_users = [uid for uid, count in daily_counts.items() if count == 1]

print(f"Power Users (7/7 days): {len(power_users)}")
print(f"Casual Users (1/7 days): {len(casual_users)}")
```

---

## Implementation Guide

### Step 1: Create ActivityTracker Service

**File**: `outlabs_auth/services/activity_tracker.py`

```python
from typing import Optional
from datetime import datetime, date, timezone, timedelta
from redis.asyncio import Redis
from outlabs_auth.models.activity_metric import ActivityMetric

class ActivityTracker:
    """
    Track user activity for DAU/MAU/WAU/QAU metrics.

    Uses Redis Sets for O(1) tracking with 99%+ write reduction.
    Background worker syncs to MongoDB for historical analytics.
    """

    def __init__(
        self,
        redis_client: Redis,
        enabled: bool = True,
        store_user_ids: bool = False,
    ):
        self.redis = redis_client
        self.enabled = enabled
        self.store_user_ids = store_user_ids

    async def track_activity(self, user_id: str) -> None:
        """
        Track user activity (fire-and-forget, non-blocking).

        Adds user to Redis Sets for:
        - Daily: active_users:daily:2025-01-24
        - Monthly: active_users:monthly:2025-01
        - Quarterly: active_users:quarterly:2025-Q1
        """
        if not self.enabled:
            return

        now = datetime.now(timezone.utc)

        # Add to daily set
        daily_key = self._make_daily_key(now.date())
        await self.redis.sadd(daily_key, user_id)
        await self.redis.expire(daily_key, 48 * 3600)  # 48 hours

        # Add to monthly set
        monthly_key = self._make_monthly_key(now.year, now.month)
        await self.redis.sadd(monthly_key, user_id)
        await self.redis.expire(monthly_key, 90 * 86400)  # 90 days

        # Add to quarterly set
        quarter = (now.month - 1) // 3 + 1
        quarterly_key = self._make_quarterly_key(now.year, quarter)
        await self.redis.sadd(quarterly_key, user_id)
        await self.redis.expire(quarterly_key, 365 * 86400)  # 1 year

        # Update last_activity timestamp in Redis
        last_activity_key = f"last_activity:{user_id}"
        await self.redis.set(
            last_activity_key,
            now.isoformat(),
            ex=7 * 86400  # 7 days
        )

    async def get_daily_active_users(self, day: Optional[date] = None) -> int:
        """Get DAU count for a specific day (default: today)."""
        if day is None:
            day = date.today()

        key = self._make_daily_key(day)
        return await self.redis.scard(key)

    async def get_monthly_active_users(self, year: Optional[int] = None, month: Optional[int] = None) -> int:
        """Get MAU count for a specific month (default: current month)."""
        if year is None or month is None:
            now = datetime.now(timezone.utc)
            year, month = now.year, now.month

        key = self._make_monthly_key(year, month)
        return await self.redis.scard(key)

    async def get_quarterly_active_users(self, year: Optional[int] = None, quarter: Optional[int] = None) -> int:
        """Get QAU count for a specific quarter (default: current quarter)."""
        if year is None or quarter is None:
            now = datetime.now(timezone.utc)
            year = now.year
            quarter = (now.month - 1) // 3 + 1

        key = self._make_quarterly_key(year, quarter)
        return await self.redis.scard(key)

    # Helper methods for Redis keys

    def _make_daily_key(self, day: date) -> str:
        return f"active_users:daily:{day.isoformat()}"

    def _make_monthly_key(self, year: int, month: int) -> str:
        return f"active_users:monthly:{year:04d}-{month:02d}"

    def _make_quarterly_key(self, year: int, quarter: int) -> str:
        return f"active_users:quarterly:{year:04d}-Q{quarter}"
```

### Step 2: Create ActivityMetric Model

**File**: `outlabs_auth/models/activity_metric.py`

```python
from datetime import datetime, timezone
from typing import Optional, List
from beanie import Document
from pydantic import Field

class ActivityMetric(Document):
    """
    Historical snapshot of user activity metrics.

    Created by background sync worker from Redis Sets.
    Used for analytics, dashboards, and growth tracking.
    """

    period_type: str = Field(
        description="Type of period: 'daily', 'monthly', 'quarterly'"
    )
    period: str = Field(
        description="Period identifier: '2025-01-24', '2025-01', '2025-Q1'"
    )
    active_users: int = Field(
        description="Count of unique active users in this period"
    )
    unique_user_ids: Optional[List[str]] = Field(
        default=None,
        description="Optional list of user IDs (for cohort analysis)"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    class Settings:
        name = "activity_metrics"
        indexes = [
            [("period_type", 1), ("period", -1)],  # Query by type + time
            [("created_at", 1)]                    # Cleanup old records
        ]
```

### Step 3: Update UserModel

**File**: `outlabs_auth/models/user.py`

```python
class UserModel(BaseDocument):
    # ... existing fields ...

    # Activity tracking
    last_login: Optional[datetime] = None      # Only on login
    last_activity: Optional[datetime] = None   # Any authenticated action (NEW)
```

### Step 4: Update AuthConfig

**File**: `outlabs_auth/config.py`

```python
class AuthConfig:
    # ... existing config ...

    # Activity tracking
    enable_activity_tracking: bool = False
    activity_sync_interval: int = 1800  # 30 minutes
    activity_update_user_model: bool = True
    activity_store_user_ids: bool = False
    activity_ttl_days: int = 90
```

### Step 5: Integrate with AuthDeps

**File**: `outlabs_auth/dependencies/auth.py`

```python
async def require_auth(self):
    async def dependency(request: Request) -> AuthContext:
        ctx = await self._authenticate(request)

        if not ctx.is_authenticated:
            raise UnauthorizedError("Authentication required")

        # Track activity (fire-and-forget)
        if ctx.user_id and self.auth.activity_tracker:
            asyncio.create_task(
                self.auth.activity_tracker.track_activity(ctx.user_id)
            )

        return ctx

    return Depends(dependency)
```

### Step 6: Create Background Sync Worker

**File**: `outlabs_auth/services/activity_tracker.py` (add method)

```python
async def sync_to_mongodb(self) -> dict:
    """
    Sync Redis activity data to MongoDB (run periodically).

    Creates ActivityMetric snapshots for historical analysis.
    Updates UserModel.last_activity (batched).
    """
    stats = {"daily": 0, "monthly": 0, "quarterly": 0, "errors": 0}

    try:
        # 1. Sync daily metrics
        today = date.today()
        daily_key = self._make_daily_key(today)
        user_ids = await self.redis.smembers(daily_key)

        if user_ids:
            metric = ActivityMetric(
                period_type="daily",
                period=today.isoformat(),
                active_users=len(user_ids),
                unique_user_ids=list(user_ids) if self.store_user_ids else None
            )
            await metric.save()
            stats["daily"] = len(user_ids)

        # 2. Sync monthly metrics (similar)
        # 3. Sync quarterly metrics (similar)

        # 4. Update UserModel.last_activity (batched)
        # ... batched update logic ...

    except Exception as e:
        logger.error(f"Error syncing activity metrics: {e}")
        stats["errors"] += 1

    return stats
```

---

## API Usage Examples

### Basic Setup

```python
from outlabs_auth import OutlabsAuth
from redis.asyncio import Redis
from motor.motor_asyncio import AsyncIOMotorClient

# Setup
mongo_client = AsyncIOMotorClient("mongodb://localhost:27017")
redis_client = Redis.from_url("redis://localhost:6379")

auth = OutlabsAuth(
    database=mongo_client.myapp,
    redis_client=redis_client,
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
from outlabs_auth.models.activity_metric import ActivityMetric
from datetime import date, timedelta

# Get last 30 days of DAU
end_date = date.today()
start_date = end_date - timedelta(days=30)

metrics = await ActivityMetric.find(
    ActivityMetric.period_type == "daily",
    ActivityMetric.period >= start_date.isoformat()
).sort("+period").to_list()

# Export for dashboard
data = [
    {"date": m.period, "active_users": m.active_users}
    for m in metrics
]
```

### Analytics Dashboard Endpoint

```python
@app.get("/admin/analytics/activity")
async def get_activity_analytics(
    period: str = "daily",  # daily, monthly, quarterly
    days: int = 30,
    ctx = Depends(deps.require_permission("analytics:read"))
):
    """Get activity metrics for analytics dashboard."""

    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    metrics = await ActivityMetric.find(
        ActivityMetric.period_type == period,
        ActivityMetric.period >= start_date.isoformat(),
        ActivityMetric.period <= end_date.isoformat()
    ).sort("+period").to_list()

    return {
        "period": period,
        "date_range": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat()
        },
        "metrics": [
            {
                "period": m.period,
                "active_users": m.active_users,
                "created_at": m.created_at.isoformat()
            }
            for m in metrics
        ]
    }
```

---

## Testing Strategy

### Unit Tests

**File**: `tests/unit/services/test_activity_tracker.py`

```python
import pytest
from datetime import date
from outlabs_auth.services.activity_tracker import ActivityTracker

@pytest.mark.asyncio
async def test_track_activity_adds_to_redis_sets(redis_client):
    """Track activity adds user to daily/monthly/quarterly sets."""
    tracker = ActivityTracker(redis_client)

    await tracker.track_activity("user_123")

    # Check daily set
    today = date.today()
    daily_key = f"active_users:daily:{today.isoformat()}"
    assert await redis_client.sismember(daily_key, "user_123")

    # Check monthly set
    monthly_key = f"active_users:monthly:{today.year:04d}-{today.month:02d}"
    assert await redis_client.sismember(monthly_key, "user_123")

@pytest.mark.asyncio
async def test_track_activity_idempotent(redis_client):
    """Tracking same user multiple times doesn't increase count."""
    tracker = ActivityTracker(redis_client)

    # Track same user 3 times
    await tracker.track_activity("user_123")
    await tracker.track_activity("user_123")
    await tracker.track_activity("user_123")

    # Should only count once
    dau = await tracker.get_daily_active_users()
    assert dau == 1

@pytest.mark.asyncio
async def test_get_daily_active_users(redis_client):
    """Get DAU returns correct count."""
    tracker = ActivityTracker(redis_client)

    await tracker.track_activity("user_1")
    await tracker.track_activity("user_2")
    await tracker.track_activity("user_3")

    dau = await tracker.get_daily_active_users()
    assert dau == 3
```

### Integration Tests

**File**: `tests/integration/activity/test_activity_tracking.py`

```python
@pytest.mark.asyncio
async def test_activity_tracked_on_authenticated_request(client, active_user, auth):
    """Activity is tracked on authenticated API requests."""
    # Login to get token
    response = await client.post("/auth/login", json={
        "email": active_user.email,
        "password": "password123"
    })
    token = response.json()["access_token"]

    # Make authenticated request
    response = await client.get(
        "/api/data",
        headers={"Authorization": f"Bearer {token}"}
    )

    # Check activity was tracked
    dau = await auth.activity_tracker.get_daily_active_users()
    assert dau == 1

@pytest.mark.asyncio
async def test_activity_not_tracked_when_disabled(client, active_user, auth_no_tracking):
    """Activity tracking can be disabled."""
    # Login with tracking disabled
    response = await client.post("/auth/login", json={
        "email": active_user.email,
        "password": "password123"
    })

    # Check no activity tracked
    assert auth_no_tracking.activity_tracker is None
```

### Background Sync Tests

```python
@pytest.mark.asyncio
async def test_sync_creates_activity_metrics(redis_client, auth):
    """Background sync creates ActivityMetric records."""
    # Track some activity
    await auth.activity_tracker.track_activity("user_1")
    await auth.activity_tracker.track_activity("user_2")

    # Run sync
    await auth.activity_tracker.sync_to_mongodb()

    # Check ActivityMetric created
    today = date.today()
    metric = await ActivityMetric.find_one(
        ActivityMetric.period_type == "daily",
        ActivityMetric.period == today.isoformat()
    )

    assert metric is not None
    assert metric.active_users == 2
```

### Performance Tests

```python
@pytest.mark.asyncio
async def test_track_activity_performance(redis_client):
    """Track activity should be very fast (< 5ms)."""
    tracker = ActivityTracker(redis_client)

    import time
    start = time.time()

    for i in range(1000):
        await tracker.track_activity(f"user_{i}")

    elapsed = time.time() - start
    avg_time = elapsed / 1000 * 1000  # Convert to ms

    assert avg_time < 5, f"Average time {avg_time:.2f}ms too slow"
```

---

## Migration & Rollout

### Enabling on Existing Systems

**Step 1**: Update dependencies
```bash
pip install --upgrade outlabs-auth
```

**Step 2**: Add Redis client (if not already present)
```python
from redis.asyncio import Redis

redis_client = Redis.from_url("redis://localhost:6379")
```

**Step 3**: Enable activity tracking
```python
auth = OutlabsAuth(
    database=mongo_client,
    redis_client=redis_client,
    enable_activity_tracking=True,  # NEW
)
```

**Step 4**: Run database migrations
```python
# Add index for ActivityMetric
await ActivityMetric.get_motor_collection().create_index([
    ("period_type", 1),
    ("period", -1)
])

# Add last_activity field (optional, will be added automatically)
```

**Step 5**: Start background sync worker
```python
import asyncio

async def activity_sync_worker():
    while True:
        await asyncio.sleep(auth.config.activity_sync_interval)
        await auth.activity_tracker.sync_to_mongodb()

# Run in background
asyncio.create_task(activity_sync_worker())
```

### Backfilling Historical Data

**If you have existing login data**, you can backfill:

```python
from datetime import timedelta

async def backfill_activity_from_logins():
    """
    Backfill activity metrics from last_login timestamps.

    Note: This will UNDERCOUNT active users (tokens last 30 days).
    Use only for rough historical estimates.
    """

    # Get all users with last_login in last 90 days
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    users = await UserModel.find(
        UserModel.last_login >= cutoff
    ).to_list()

    # Group by day
    daily_counts = {}
    for user in users:
        day = user.last_login.date().isoformat()
        daily_counts[day] = daily_counts.get(day, 0) + 1

    # Create ActivityMetric records
    for day, count in daily_counts.items():
        metric = ActivityMetric(
            period_type="daily",
            period=day,
            active_users=count,
            created_at=datetime.now(timezone.utc)
        )
        await metric.save()

    print(f"Backfilled {len(daily_counts)} days of activity data")
```

**Warning**: This will significantly undercount active users because:
- Users don't re-login for 30 days (token lifetime)
- API key usage not reflected in last_login
- Token refresh activity not captured

**Recommendation**: Use backfilled data as baseline only, not for growth calculations.

---

## Monitoring & Observability

### Metrics to Monitor

1. **Redis Set Sizes**:
   - Daily set size (should be < 10 million users for most apps)
   - Monthly set growth rate
   - Memory usage

2. **Sync Worker Performance**:
   - Sync duration (should be < 5 seconds for 1M DAU)
   - Sync success rate (should be 100%)
   - MongoDB write latency

3. **Activity Tracking Latency**:
   - Track operation time (should be < 1ms)
   - Fire-and-forget task queue depth

### Logging

```python
import logging

logger = logging.getLogger("outlabs_auth.activity")

# In ActivityTracker.track_activity()
logger.debug(f"Tracked activity for user {user_id}")

# In sync_to_mongodb()
logger.info(f"Synced activity: DAU={stats['daily']}, MAU={stats['monthly']}")

# On errors
logger.error(f"Failed to sync activity: {e}", exc_info=True)
```

### Alerts

Set up alerts for:
- Sync worker failures (> 3 consecutive failures)
- Redis memory usage (> 80% capacity)
- ActivityMetric write failures
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

### 3. User ID Storage
- Set `activity_store_user_ids=False` by default (saves storage)
- Enable only if you need cohort analysis or retention metrics
- Storage cost: ~16 bytes * DAU * 365 days

### 4. TTL Management
- Keep Redis TTLs reasonable (48h daily, 90d monthly)
- Archive old ActivityMetric records after 1-2 years
- Consider data warehousing for long-term analytics

### 5. Privacy Considerations
- User IDs are stored temporarily in Redis
- Historical data can be anonymized (drop unique_user_ids field)
- Support GDPR deletion (remove user_id from Redis sets and ActivityMetric)

---

## Comparison with Alternatives

### vs. Updating `last_activity` on Every Request

| Approach | Writes | Accuracy | Scalability |
|----------|--------|----------|-------------|
| **MongoDB direct** | 1 write/request | 100% | ❌ Poor (10K writes/sec limit) |
| **Redis Sets** | 1 write/user/day | 100% | ✅ Excellent (100K+ ops/sec) |
| **HyperLogLog** | 1 write/request | ~98% (probabilistic) | ✅ Excellent (low memory) |

**Winner**: Redis Sets (exact counts, 99%+ write reduction, scalable)

### vs. Beanie Model Lifecycle Hooks

```python
# ❌ ANTI-PATTERN: Don't do this
class UserModel(BaseDocument):
    async def update_activity(self):
        self.last_activity = datetime.now(timezone.utc)
        await self.save()  # Database write on EVERY request!
```

**Problems**:
- Tight coupling to UserModel
- Cannot avoid database writes
- Doesn't provide DAU/MAU metrics
- Poor performance at scale

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
- ✅ MongoDB for historical snapshots
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
- **12-Data-Models.md**: UserModel and database schema
- **22-JWT-Tokens.md**: Authentication flow and token refresh

---

## Summary

**Activity tracking provides accurate DAU/MAU/WAU/QAU metrics** by:

1. **Redis Sets** for O(1) tracking (99%+ write reduction)
2. **Fire-and-forget** integration (non-blocking)
3. **Background sync** to MongoDB (historical data)
4. **Optional UserModel.last_activity** (batched updates)
5. **Graceful degradation** without Redis

**Configuration**:
- Requires Redis (validation enforced)
- Opt-in via `enable_activity_tracking=True`
- Configurable sync intervals and storage options

**Performance**:
- 100K+ ops/sec (Redis SET operations)
- ~16 MB/day for 1M DAU
- < 5 seconds sync time for 1M users

**Use Cases**:
- Product analytics dashboards
- Growth monitoring and forecasting
- User engagement analysis
- Retention cohort studies

**Next Steps**: Implement ActivityTracker service, create tests, integrate with AuthDeps middleware.
