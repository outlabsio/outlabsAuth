# Performance Optimization Guide

## Overview

This guide outlines performance optimization strategies for outlabsAuth, focusing on permission resolution, caching, and database query optimization.

## Permission Resolution Optimization

### The Challenge

Permission checking involves multiple lookups:
```
User → Memberships → Entities → Roles → Permissions
```

For users with many memberships, this can result in N+1 query problems.

### Solution 1: Denormalized Permission Cache

#### Redis-Based Permission Cache

```python
import json
from typing import Set, Optional
from datetime import timedelta

class PermissionCacheService:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.cache_ttl = timedelta(minutes=15)  # 15-minute cache
    
    async def get_user_permissions(
        self, 
        user_id: str, 
        context: Optional[str] = None
    ) -> Optional[Set[str]]:
        """Get cached permissions for user"""
        cache_key = f"perms:{user_id}"
        if context:
            cache_key += f":{context}"
        
        cached = await self.redis.get(cache_key)
        if cached:
            return set(json.loads(cached))
        return None
    
    async def set_user_permissions(
        self, 
        user_id: str, 
        permissions: Set[str],
        context: Optional[str] = None
    ):
        """Cache user permissions"""
        cache_key = f"perms:{user_id}"
        if context:
            cache_key += f":{context}"
        
        await self.redis.setex(
            cache_key,
            self.cache_ttl,
            json.dumps(list(permissions))
        )
    
    async def invalidate_user_permissions(self, user_id: str):
        """Clear all cached permissions for a user"""
        pattern = f"perms:{user_id}*"
        async for key in self.redis.scan_iter(match=pattern):
            await self.redis.delete(key)
```

#### Background Permission Calculator

##### Option 1: Simple Async Background Tasks (Phase 1)

```python
import asyncio
from typing import Set
import logging

logger = logging.getLogger(__name__)

class SimpleBackgroundTasks:
    """Lightweight background task runner for initial implementation"""
    
    def __init__(self):
        self.tasks: Set[asyncio.Task] = set()
    
    def create_task(self, coro):
        """Fire-and-forget background task"""
        task = asyncio.create_task(coro)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return task
    
    async def shutdown(self):
        """Gracefully shutdown all tasks"""
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)

# Global instance
background_tasks = SimpleBackgroundTasks()

# Usage in your service
async def on_membership_change(membership_id: str):
    """Triggered when membership changes"""
    # Fire and forget - no waiting
    background_tasks.create_task(
        recalculate_user_permissions(membership_id)
    )

async def recalculate_user_permissions(membership_id: str):
    """Background task to pre-calculate permissions"""
    try:
        membership = await EntityMembershipModel.get(membership_id)
        if not membership:
            return
        
        # Get all user memberships with entities and roles
        memberships = await EntityMembershipModel.find(
            EntityMembershipModel.user.id == membership.user.id
        ).aggregate([
            {
                "$lookup": {
                    "from": "entities",
                    "localField": "entity",
                    "foreignField": "_id",
                    "as": "entity_data"
                }
            },
            {
                "$lookup": {
                    "from": "roles",
                    "localField": "roles",
                    "foreignField": "_id",
                    "as": "role_data"
                }
            }
        ]).to_list()
        
        # Calculate permissions
        permissions = set()
        for membership in memberships:
            for role in membership['role_data']:
                permissions.update(role['permissions'])
        
        # Cache results
        cache_service = PermissionCacheService(redis)
        await cache_service.set_user_permissions(
            str(membership.user.id), 
            permissions
        )
        
        logger.info(f"Updated permissions for user {membership.user.id}")
        
    except Exception as e:
        logger.error(f"Failed to recalculate permissions: {e}")
```

##### Option 2: RabbitMQ Worker (Phase 2)

```python
# worker/permission_worker.py
import asyncio
import json
import aio_pika
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class PermissionWorker:
    """Custom Python worker consuming from RabbitMQ"""
    
    def __init__(self, rabbitmq_url: str):
        self.rabbitmq_url = rabbitmq_url
        self.connection = None
        self.channel = None
        self.queue_name = "permission_calculations"
    
    async def connect(self):
        """Connect to RabbitMQ"""
        self.connection = await aio_pika.connect_robust(self.rabbitmq_url)
        self.channel = await self.connection.channel()
        
        # Declare queue
        self.queue = await self.channel.declare_queue(
            self.queue_name,
            durable=True
        )
        
        # Set QoS
        await self.channel.set_qos(prefetch_count=10)
    
    async def process_message(self, message: aio_pika.IncomingMessage):
        """Process a single message"""
        async with message.process():
            try:
                data = json.loads(message.body)
                task_type = data.get('task_type')
                
                if task_type == 'recalculate_permissions':
                    await self.recalculate_permissions(data['user_id'])
                elif task_type == 'invalidate_cache':
                    await self.invalidate_user_cache(data['user_id'])
                else:
                    logger.warning(f"Unknown task type: {task_type}")
                    
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                # Message will be requeued
                raise
    
    async def recalculate_permissions(self, user_id: str):
        """Recalculate and cache user permissions"""
        # Same logic as above
        logger.info(f"Recalculating permissions for user {user_id}")
        # ... permission calculation logic ...
    
    async def run(self):
        """Start consuming messages"""
        await self.connect()
        logger.info("Permission worker started")
        
        async with self.queue.iterator() as queue_iter:
            async for message in queue_iter:
                await self.process_message(message)

# Publisher side (in your FastAPI app)
class MessagePublisher:
    def __init__(self, rabbitmq_url: str):
        self.rabbitmq_url = rabbitmq_url
        self.connection = None
        self.channel = None
    
    async def connect(self):
        self.connection = await aio_pika.connect_robust(self.rabbitmq_url)
        self.channel = await self.connection.channel()
    
    async def publish_task(self, task_type: str, data: Dict[str, Any]):
        """Publish a task to the queue"""
        if not self.channel:
            await self.connect()
        
        message = aio_pika.Message(
            body=json.dumps({
                'task_type': task_type,
                **data
            }).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT
        )
        
        await self.channel.default_exchange.publish(
            message,
            routing_key="permission_calculations"
        )

# Usage in your service
publisher = MessagePublisher("amqp://guest:guest@localhost/")

async def on_membership_change(membership_id: str):
    membership = await EntityMembershipModel.get(membership_id)
    if membership:
        await publisher.publish_task(
            'recalculate_permissions',
            {'user_id': str(membership.user.id)}
        )
```

##### Option 3: Redis-Based Task Queue (Alternative to Phase 2)

```python
# Simple Redis-based task queue
import json
import asyncio
from typing import Optional
import aioredis

class RedisTaskQueue:
    """Lightweight task queue using Redis lists"""
    
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.redis: Optional[aioredis.Redis] = None
        self.queue_key = "outlabsauth:tasks:permissions"
    
    async def connect(self):
        self.redis = await aioredis.from_url(self.redis_url)
    
    async def enqueue(self, task_type: str, data: dict):
        """Add task to queue"""
        if not self.redis:
            await self.connect()
        
        task = {
            'type': task_type,
            'data': data,
            'created_at': datetime.utcnow().isoformat()
        }
        
        await self.redis.lpush(self.queue_key, json.dumps(task))
    
    async def dequeue(self, timeout: int = 0) -> Optional[dict]:
        """Get task from queue (blocking)"""
        if not self.redis:
            await self.connect()
        
        result = await self.redis.brpop(self.queue_key, timeout)
        if result:
            _, task_json = result
            return json.loads(task_json)
        return None

# Worker
async def permission_worker(queue: RedisTaskQueue):
    """Simple worker processing tasks from Redis"""
    while True:
        task = await queue.dequeue(timeout=5)
        if task:
            try:
                if task['type'] == 'recalculate_permissions':
                    await recalculate_permissions(task['data']['user_id'])
            except Exception as e:
                logger.error(f"Task failed: {e}")
                # Could implement retry logic here
```

### Solution 2: Database Query Optimization

#### Aggregation Pipeline for Permission Resolution

```python
async def get_user_permissions_optimized(user_id: str) -> Set[str]:
    """Single aggregation query to get all permissions"""
    
    pipeline = [
        # Match user's memberships
        {"$match": {"user": ObjectId(user_id), "status": "active"}},
        
        # Lookup entities
        {
            "$lookup": {
                "from": "entities",
                "localField": "entity",
                "foreignField": "_id",
                "as": "entity_data"
            }
        },
        {"$unwind": "$entity_data"},
        
        # Filter active entities only
        {"$match": {"entity_data.status": "active"}},
        
        # Lookup roles
        {
            "$lookup": {
                "from": "roles",
                "localField": "roles",
                "foreignField": "_id",
                "as": "role_data"
            }
        },
        {"$unwind": "$role_data"},
        
        # Get unique permissions
        {"$group": {
            "_id": None,
            "permissions": {"$addToSet": "$role_data.permissions"}
        }},
        
        # Flatten permission arrays
        {"$project": {
            "permissions": {
                "$reduce": {
                    "input": "$permissions",
                    "initialValue": [],
                    "in": {"$setUnion": ["$$value", "$$this"]}
                }
            }
        }}
    ]
    
    result = await EntityMembershipModel.aggregate(pipeline).to_list()
    
    if result:
        return set(result[0].get('permissions', []))
    return set()
```

#### Indexed Queries

```python
# Ensure proper indexes
class EntityMembershipModel(BaseDocument):
    class Settings:
        indexes = [
            # Compound index for user lookups
            IndexModel([("user", 1), ("status", 1)]),
            
            # Index for entity lookups
            IndexModel([("entity", 1), ("status", 1)]),
            
            # Index for role queries
            IndexModel([("roles", 1)]),
            
            # Compound unique constraint
            IndexModel(
                [("user", 1), ("entity", 1)], 
                unique=True,
                name="unique_user_entity"
            )
        ]
```

### Solution 3: Permission Resolution Service

```python
class OptimizedPermissionService:
    def __init__(self, cache_service: PermissionCacheService):
        self.cache = cache_service
    
    async def check_permission(
        self,
        user_id: str,
        permission: str,
        context: Optional[EntityModel] = None
    ) -> bool:
        """Check if user has specific permission with caching"""
        
        # Try cache first
        cache_key = f"{user_id}:{context.id if context else 'global'}"
        permissions = await self.cache.get_user_permissions(user_id, cache_key)
        
        if permissions is None:
            # Cache miss - calculate permissions
            permissions = await self._calculate_permissions(user_id, context)
            
            # Cache for next time
            await self.cache.set_user_permissions(user_id, permissions, cache_key)
        
        # Check hierarchical permissions
        return self._check_hierarchical_permission(permissions, permission)
    
    def _check_hierarchical_permission(
        self, 
        user_permissions: Set[str], 
        required: str
    ) -> bool:
        """Check with hierarchy (manage includes read, etc)"""
        
        # Direct match
        if required in user_permissions:
            return True
        
        # Hierarchical matches
        parts = required.split(':')
        if len(parts) == 2:
            resource, action = parts
            
            # Check for higher-level permissions
            if f"{resource}:manage_all" in user_permissions:
                return True
            
            if action == "read" and f"{resource}:manage" in user_permissions:
                return True
        
        return False
```

## API Response Optimization

### 1. Conditional Includes

```python
@router.get("/v1/users/me/permissions")
async def get_my_permissions(
    include: Optional[str] = Query(None),
    context: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user)
):
    # Base permissions
    permissions = await permission_service.get_user_permissions(
        current_user.id,
        context
    )
    
    response = {"permissions": list(permissions)}
    
    # Only include sources if requested
    if include and "sources" in include.split(","):
        sources = await permission_service.get_permission_sources(
            current_user.id,
            permissions
        )
        response["sources"] = sources
    
    return response
```

### 2. Pagination for Large Results

```python
@router.get("/v1/entities/")
async def list_entities(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    entity_class: Optional[str] = None,
    cursor: Optional[str] = None  # For cursor-based pagination
):
    if cursor:
        # Cursor-based pagination for large datasets
        query = {"_id": {"$gt": ObjectId(cursor)}}
    else:
        query = {}
    
    if entity_class:
        query["entity_class"] = entity_class
    
    entities = await EntityModel.find(query).skip(skip).limit(limit).to_list()
    
    # Include next cursor
    next_cursor = str(entities[-1].id) if entities else None
    
    return {
        "entities": entities,
        "next_cursor": next_cursor,
        "has_more": len(entities) == limit
    }
```

### 3. Field Projection

```python
@router.get("/v1/users/")
async def list_users(
    fields: Optional[str] = Query(None),  # Comma-separated fields
    skip: int = 0,
    limit: int = 50
):
    # Build projection
    projection = {}
    if fields:
        for field in fields.split(","):
            projection[field] = 1
    
    # Always include ID
    projection["_id"] = 1
    
    users = await UserModel.find().project(projection).skip(skip).limit(limit).to_list()
    
    return {"users": users}
```

## Database Connection Pooling

```python
# Motor (MongoDB async driver) configuration
from motor.motor_asyncio import AsyncIOMotorClient

class DatabaseConfig:
    # Connection pool settings
    MONGODB_URL = "mongodb://localhost:27017"
    MAX_POOL_SIZE = 100
    MIN_POOL_SIZE = 10
    MAX_IDLE_TIME_MS = 30000  # 30 seconds
    WAIT_QUEUE_TIMEOUT_MS = 10000  # 10 seconds
    
    @classmethod
    def get_client(cls) -> AsyncIOMotorClient:
        return AsyncIOMotorClient(
            cls.MONGODB_URL,
            maxPoolSize=cls.MAX_POOL_SIZE,
            minPoolSize=cls.MIN_POOL_SIZE,
            maxIdleTimeMS=cls.MAX_IDLE_TIME_MS,
            waitQueueTimeoutMS=cls.WAIT_QUEUE_TIMEOUT_MS,
            serverSelectionTimeoutMS=5000,
            retryWrites=True,
            retryReads=True
        )
```

## Caching Strategy

### Multi-Layer Cache

```python
class CacheLayer:
    def __init__(self):
        # L1: In-memory cache (process-local)
        self.memory_cache = TTLCache(maxsize=1000, ttl=60)  # 1 minute
        
        # L2: Redis cache (shared)
        self.redis = Redis(decode_responses=True)
    
    async def get(self, key: str) -> Optional[Any]:
        # Try L1 first
        if key in self.memory_cache:
            return self.memory_cache[key]
        
        # Try L2
        value = await self.redis.get(key)
        if value:
            # Populate L1
            self.memory_cache[key] = json.loads(value)
            return self.memory_cache[key]
        
        return None
    
    async def set(self, key: str, value: Any, ttl: int = 300):
        # Set in both layers
        self.memory_cache[key] = value
        await self.redis.setex(key, ttl, json.dumps(value))
```

### Cache Warming

```python
@app.on_event("startup")
async def warm_cache():
    """Pre-populate cache with frequently accessed data"""
    
    # Get active platform configurations
    platforms = await PlatformModel.find({"status": "active"}).to_list()
    
    for platform in platforms:
        # Cache platform config
        await cache.set(f"platform:{platform.id}", platform.dict(), ttl=3600)
        
        # Cache top-level entities
        entities = await EntityModel.find({
            "platform_id": str(platform.id),
            "parent_entity": None
        }).to_list()
        
        await cache.set(
            f"platform:{platform.id}:entities",
            [e.dict() for e in entities],
            ttl=1800
        )
```

## Monitoring & Metrics

```python
from prometheus_client import Counter, Histogram, generate_latest

# Metrics
permission_check_counter = Counter(
    'permission_checks_total',
    'Total permission checks',
    ['result', 'cached']
)

permission_check_duration = Histogram(
    'permission_check_duration_seconds',
    'Permission check duration',
    ['cached']
)

# Usage
@permission_check_duration.labels(cached='false').time()
async def check_permission_with_metrics(user_id: str, permission: str):
    result = await permission_service.check_permission(user_id, permission)
    permission_check_counter.labels(
        result='allowed' if result else 'denied',
        cached='false'
    ).inc()
    return result

# Metrics endpoint
@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type="text/plain")
```

## Implementation Phases

### Phase 1: Core Performance (No External Dependencies)
- Implement Redis caching for permissions
- Add database query optimization with indexes
- Use simple async background tasks
- Implement pagination and field projections

### Phase 2: Advanced Background Processing
- Choose between RabbitMQ or Redis-based queues
- Implement dedicated workers for permission calculation
- Add task retry and dead letter handling
- Scale workers based on load

### Phase 3: Full Optimization
- Implement multi-layer caching (L1 + L2)
- Add cache warming strategies
- Implement comprehensive monitoring
- Add predictive pre-calculation

## Best Practices Summary

1. **Cache Aggressively**: Use multi-layer caching for permissions
2. **Batch Operations**: Aggregate multiple permission checks
3. **Use Projections**: Only fetch fields you need
4. **Index Properly**: Create compound indexes for common queries
5. **Monitor Performance**: Track cache hit rates and query times
6. **Invalidate Smartly**: Clear caches only when necessary
7. **Pre-calculate**: Use background jobs for expensive calculations
8. **Paginate**: Always paginate large result sets
9. **Connection Pool**: Tune database connection pool settings
10. **Profile Queries**: Use MongoDB profiler to identify slow queries

## Choosing Background Processing

| Solution | Pros | Cons | When to Use |
|----------|------|------|-------------|
| **Simple Async** | No dependencies, easy setup | Limited scalability, no persistence | Phase 1, < 1000 users |
| **Redis Queue** | Already have Redis, simple | Not designed for queuing | Small to medium scale |
| **RabbitMQ** | Battle-tested, scalable, persistent | Additional infrastructure | Production, high scale |

The key is to start simple and evolve as your needs grow. The architecture supports swapping implementations without changing the core permission logic.