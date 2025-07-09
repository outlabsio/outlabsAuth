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

### Solution 1: Policy Evaluation Cache

With the hybrid authorization model, we can no longer cache just permission lists. We need to cache policy evaluation results:

#### Policy Result Cache

```python
import json
import hashlib
from typing import Optional, Dict, Any
from datetime import timedelta

class PolicyCacheService:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.cache_ttl = timedelta(minutes=5)  # Shorter TTL due to dynamic nature
    
    def _generate_cache_key(
        self,
        user_id: str,
        permission: str,
        entity_id: str,
        resource_attributes: Dict[str, Any]
    ) -> str:
        """Generate unique cache key for policy evaluation"""
        # Create deterministic hash of resource attributes
        attrs_hash = hashlib.md5(
            json.dumps(resource_attributes, sort_keys=True).encode()
        ).hexdigest()
        
        return f"policy:{user_id}:{permission}:{entity_id}:{attrs_hash}"
    
    async def get_policy_result(
        self,
        user_id: str,
        permission: str,
        entity_id: str,
        resource_attributes: Dict[str, Any]
    ) -> Optional[bool]:
        """Get cached policy evaluation result"""
        cache_key = self._generate_cache_key(
            user_id, permission, entity_id, resource_attributes
        )
        
        result = await self.redis.get(cache_key)
        if result is not None:
            return result == "1"
        return None
    
    async def set_policy_result(
        self,
        user_id: str,
        permission: str,
        entity_id: str,
        resource_attributes: Dict[str, Any],
        allowed: bool
    ):
        """Cache policy evaluation result"""
        cache_key = self._generate_cache_key(
            user_id, permission, entity_id, resource_attributes
        )
        
        await self.redis.setex(
            cache_key,
            self.cache_ttl,
            "1" if allowed else "0"
        )
    
    async def invalidate_user_policies(self, user_id: str):
        """Clear all cached policy results for a user"""
        pattern = f"policy:{user_id}:*"
        async for key in self.redis.scan_iter(match=pattern):
            await self.redis.delete(key)
    
    async def invalidate_permission_policies(self, permission: str):
        """Clear all cached results for a specific permission"""
        pattern = f"policy:*:{permission}:*"
        async for key in self.redis.scan_iter(match=pattern):
            await self.redis.delete(key)
```

#### Permission Definition Cache

```python
class PermissionDefinitionCache:
    """Cache permission definitions including conditions"""
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.cache_ttl = timedelta(hours=1)  # Longer TTL for definitions
    
    async def get_permission(self, name: str) -> Optional[Dict[str, Any]]:
        """Get cached permission definition"""
        cached = await self.redis.get(f"perm_def:{name}")
        if cached:
            return json.loads(cached)
        return None
    
    async def set_permission(self, permission: PermissionModel):
        """Cache permission definition"""
        await self.redis.setex(
            f"perm_def:{permission.name}",
            self.cache_ttl,
            json.dumps(permission.dict())
        )
    
    async def invalidate_permission(self, name: str):
        """Invalidate cached permission definition"""
        await self.redis.delete(f"perm_def:{name}")
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
                # Validate each permission against custom permissions
                for perm in role['permissions']:
                    # Check if it's a system permission or valid custom permission
                    if await permission_service.is_valid_permission(perm):
                        permissions.add(perm)
                    else:
                        logger.warning(f"Invalid permission '{perm}' in role {role['name']}")
        
        # Cache validated results
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

### Solution 3: Optimized Policy Evaluation Service

```python
class OptimizedPolicyService:
    def __init__(
        self,
        policy_cache: PolicyCacheService,
        permission_cache: PermissionDefinitionCache
    ):
        self.policy_cache = policy_cache
        self.permission_cache = permission_cache
    
    async def check_permission(
        self,
        user_id: str,
        permission: str,
        entity_id: str,
        resource_attributes: Dict[str, Any] = None
    ) -> PermissionCheckResult:
        """Check permission with policy caching"""
        
        # Normalize resource attributes
        resource_attrs = resource_attributes or {}
        
        # Check policy result cache first
        cached_result = await self.policy_cache.get_policy_result(
            user_id, permission, entity_id, resource_attrs
        )
        
        if cached_result is not None:
            return PermissionCheckResult(
                allowed=cached_result,
                cache_hit=True
            )
        
        # Get permission definition (with caching)
        perm_def = await self._get_permission_definition(permission)
        
        # Perform full policy evaluation
        result = await self._evaluate_policy(
            user_id, permission, entity_id, resource_attrs, perm_def
        )
        
        # Cache the result
        await self.policy_cache.set_policy_result(
            user_id, permission, entity_id, resource_attrs, result.allowed
        )
        
        return result
    
    async def _get_permission_definition(self, permission: str) -> Dict[str, Any]:
        """Get permission definition with caching"""
        # Try cache first
        cached = await self.permission_cache.get_permission(permission)
        if cached:
            return cached
        
        # Fetch from database
        perm_model = await PermissionModel.find_one({"name": permission})
        if perm_model:
            await self.permission_cache.set_permission(perm_model)
            return perm_model.dict()
        
        return None
    
    def _check_hierarchical_permission(
        self, 
        user_permissions: Set[str], 
        required: str
    ) -> bool:
        """Check with hierarchy (manage includes read, etc)"""
        
        # Direct match
        if required in user_permissions:
            return True
        
        # Note: With custom permissions, hierarchical expansion is only
        # applied to SYSTEM permissions. Custom permissions must be
        # explicitly granted and don't auto-expand.
        
        # Check if this is a system permission
        if self._is_system_permission(required):
            # Hierarchical matches for system permissions only
            parts = required.split(':')
            if len(parts) == 2:
                resource, action = parts
                
                # System permission hierarchy
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

## Cache Invalidation Strategies

### When to Invalidate Policy Cache

With conditional permissions, cache invalidation becomes more complex:

```python
class CacheInvalidationService:
    def __init__(self, policy_cache: PolicyCacheService):
        self.policy_cache = policy_cache
    
    async def on_user_role_change(self, user_id: str):
        """Invalidate all cached policies for a user"""
        await self.policy_cache.invalidate_user_policies(user_id)
    
    async def on_permission_update(self, permission: str):
        """Invalidate all cached results for updated permission"""
        await self.policy_cache.invalidate_permission_policies(permission)
    
    async def on_user_attribute_change(self, user_id: str, attribute: str):
        """Invalidate policies that depend on changed attribute"""
        # Find permissions that use this attribute in conditions
        permissions = await PermissionModel.find({
            "conditions.attribute": {"$regex": f"^user.{attribute}"}
        }).to_list()
        
        for perm in permissions:
            pattern = f"policy:{user_id}:{perm.name}:*"
            async for key in redis.scan_iter(match=pattern):
                await redis.delete(key)
    
    async def on_entity_change(self, entity_id: str):
        """Invalidate policies for entity changes"""
        # Clear all cached policies for this entity
        pattern = f"policy:*:*:{entity_id}:*"
        async for key in redis.scan_iter(match=pattern):
            await redis.delete(key)
```

### Smart Cache Warming

Pre-compute common policy evaluations:

```python
async def warm_policy_cache():
    """Pre-compute common permission checks"""
    
    # Get frequently checked permissions
    frequent_permissions = await get_frequent_permissions()
    
    # Get active users
    active_users = await get_recently_active_users()
    
    for user in active_users:
        for permission in frequent_permissions:
            # Pre-evaluate with common resource attributes
            common_scenarios = await get_common_scenarios(permission)
            
            for scenario in common_scenarios:
                result = await policy_service.check_permission(
                    user.id,
                    permission,
                    user.primary_entity_id,
                    scenario.resource_attributes
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
    
    # Cache custom permissions for fast validation
    custom_permissions = await PermissionModel.find(
        {"is_active": True, "is_system": False}
    ).to_list()
    
    await cache.set(
        "permissions:custom:active",
        [p.name for p in custom_permissions],
        ttl=3600  # 1 hour cache
    )
    
    # Cache system permissions
    await cache.set(
        "permissions:system",
        list(SYSTEM_PERMISSIONS),
        ttl=86400  # 24 hour cache
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

### General Optimization
1. **Cache Aggressively**: Cache policy evaluation results, not just permissions
2. **Batch Operations**: Aggregate multiple permission checks when possible
3. **Use Projections**: Only fetch fields you need from database
4. **Index Properly**: Create indexes on condition attributes
5. **Monitor Performance**: Track cache hit rates and policy evaluation times

### Hybrid Model Specific
6. **Optimize Conditions**: Keep conditions simple and fast to evaluate
7. **Limit Condition Depth**: Avoid deeply nested attribute paths
8. **Cache Permission Definitions**: Permission structures change infrequently
9. **Short TTLs for Policies**: Resource attributes change frequently
10. **Pre-evaluate Common Cases**: Warm cache with typical scenarios

### Condition Design Tips
```python
# GOOD: Simple, direct comparisons
{
    "attribute": "resource.value",
    "operator": "LESS_THAN",
    "value": 50000
}

# AVOID: Complex nested paths
{
    "attribute": "resource.metadata.custom_fields.approval_chain[0].limit",
    "operator": "GREATER_THAN",
    "value": 1000
}

# GOOD: Use indexed attributes
{
    "attribute": "user.department",  # Indexed field
    "operator": "EQUALS",
    "value": "finance"
}
```

### Performance Monitoring
```python
# Track policy evaluation metrics
policy_evaluation_histogram = Histogram(
    'policy_evaluation_duration_seconds',
    'Time spent evaluating policies',
    ['permission', 'cached', 'conditions_count']
)

@policy_evaluation_histogram.time()
async def evaluate_policy_with_metrics(
    permission: str,
    conditions_count: int,
    cached: bool
):
    # Policy evaluation logic
    pass
```

## Choosing Background Processing

| Solution | Pros | Cons | When to Use |
|----------|------|------|-------------|
| **Simple Async** | No dependencies, easy setup | Limited scalability, no persistence | Phase 1, < 1000 users |
| **Redis Queue** | Already have Redis, simple | Not designed for queuing | Small to medium scale |
| **RabbitMQ** | Battle-tested, scalable, persistent | Additional infrastructure | Production, high scale |

The key is to start simple and evolve as your needs grow. The architecture supports swapping implementations without changing the core permission logic.