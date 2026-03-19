# OutlabsAuth - Authentication Dependency Patterns

**Version**: 1.4
**Date**: 2025-01-14
**Status**: Core Feature (v1.0)

---

## Table of Contents

1. [Overview](#overview)
2. [AuthContext Architecture](#authcontext-architecture)
3. [AuthDeps - Unified Dependency Injection](#authdeps---unified-dependency-injection)
4. [Multi-Source Authentication](#multi-source-authentication)
5. [API Key System](#api-key-system)
6. [Usage Examples](#usage-examples)
7. [Advanced Patterns](#advanced-patterns)
8. [Rate Limiting](#rate-limiting)
9. [Testing Patterns](#testing-patterns)
10. [Security Best Practices](#security-best-practices)

---

## Overview

This document outlines how to use FastAPI's dependency injection system with the **unified `AuthDeps` class** to create simple, composable authentication and authorization patterns that work across different authentication sources (users, API keys, JWT service tokens, superusers).

### Key Architecture Changes (v1.4)

**Unified Dependency Injection (DD-035)**: Single `AuthDeps` class replaces 5 separate classes (`SimpleDeps`, `MultiSourceDeps`, `GroupDeps`, `EntityDeps`, `RateLimitDeps`). Clear, descriptive method names make it easy to discover and learn.

**Multi-Source Authentication (DD-034)**: Support for:
- **Users**: JWT tokens for human users
- **API Keys**: argon2id-hashed keys for external integrations (DD-028)
- **JWT Service Tokens**: Zero-DB stateless auth for internal microservices
- **Superusers**: Admin override tokens
- **Anonymous**: Public endpoints with optional auth

**Performance Optimizations**:
- **Redis Counters (DD-033)**: API key usage tracking via Redis INCR (99%+ reduction in DB writes)
- **Closure Table (DD-036)**: O(1) tree permission checks (20x faster than recursive queries)
- **Cache Invalidation (DD-037)**: Redis Pub/Sub for <100ms invalidation across instances

### Core Design Principles

1. **Dead Simple for Common Cases**: One-line protection for endpoints
2. **Composable**: Mix and match different auth requirements
3. **Type-Safe**: Full IDE support and type checking
4. **Testable**: Easy to mock and test
5. **Multi-Source**: Support users, API keys, JWT service tokens, and more
6. **Secure by Default**: argon2id hashing, temp locks, Redis counters
7. **Discoverable**: Single class, clear method names, excellent docs

### Why Dependency Injection?

FastAPI's dependency injection system provides:
- **Clear contracts**: Function signatures declare requirements
- **Automatic validation**: FastAPI validates dependencies before calling handlers
- **Easy testing**: Override dependencies in tests
- **Composability**: Combine simple dependencies into complex requirements
- **Reusability**: Define once, use everywhere

---

## AuthContext Architecture

### Universal Authentication Context

The `AuthContext` is a universal authentication abstraction that supports multiple auth sources while providing a consistent API.

```python
# outlabs_auth/auth_context.py
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

class AuthSource(str, Enum):
    """Where the authentication came from"""
    USER = "user"                   # Normal user with JWT
    API_KEY = "api_key"             # Service API key
    SERVICE = "service"             # Internal service account
    SUPERUSER = "superuser"         # Admin override
    IMPERSONATION = "impersonation" # Admin acting as user
    ANONYMOUS = "anonymous"         # No auth provided

class AuthContext(BaseModel):
    """Universal authentication context"""

    # Core identity
    source: AuthSource
    identity: str  # user_id, api_key_id, service_name, etc.

    # Permissions & access
    permissions: List[str] = []
    roles: List[str] = []
    groups: List[str] = []
    entities: Dict[str, List[str]] = {}  # entity_id -> [permissions]

    # Special flags
    is_superuser: bool = False
    is_service_account: bool = False
    is_impersonating: bool = False

    # Metadata
    metadata: Dict[str, Any] = {}

    # Rate limiting info
    rate_limit: Optional[int] = None
    rate_limit_remaining: Optional[int] = None

    # Convenience methods

    def has_permission(self, permission: str) -> bool:
        """Check if context has permission"""
        if self.is_superuser:
            return True
        return permission in self.permissions

    def has_any_permission(self, *permissions: str) -> bool:
        """Check if context has any of the permissions"""
        if self.is_superuser:
            return True
        return any(p in self.permissions for p in permissions)

    def has_all_permissions(self, *permissions: str) -> bool:
        """Check if context has all permissions"""
        if self.is_superuser:
            return True
        return all(p in self.permissions for p in permissions)

    def in_group(self, group: str) -> bool:
        """Check group membership"""
        if self.is_superuser:
            return True
        return group in self.groups

    def has_role(self, role: str) -> bool:
        """Check role assignment"""
        if self.is_superuser:
            return True
        return role in self.roles
```

### Design Benefits

1. **Source Agnostic**: Same API regardless of auth source
2. **Superuser Shortcuts**: Superusers bypass all checks automatically
3. **Rich Metadata**: Carry context-specific information
4. **Type Safe**: Full Pydantic validation
5. **Testable**: Easy to create mock contexts

---

## AuthDeps - Unified Dependency Injection

### The AuthDeps Class

**One class to rule them all.** The `AuthDeps` class provides a unified, discoverable API for all authentication and authorization patterns.

```python
# outlabs_auth/dependencies/auth_deps.py
from fastapi import Depends, HTTPException, Header, Request, Query, Path
from typing import Optional, Callable, List
from outlabs_auth.auth_context import AuthContext, AuthSource

class AuthDeps:
    """
    Unified dependency injection for all auth patterns.

    Design: Single class with clear, descriptive method names.
    See: DESIGN_DECISIONS.md DD-035
    """

    def __init__(self, auth: OutlabsAuth, redis: Optional[Redis] = None):
        self.auth = auth
        self.redis = redis

    # ============================================================
    # AUTHENTICATION (Who are you?)
    # ============================================================

    async def get_context(
        self,
        request: Request,
        # Headers
        authorization: Optional[str] = Header(None),
        x_api_key: Optional[str] = Header(None),
        x_service_token: Optional[str] = Header(None),
        x_superuser_token: Optional[str] = Header(None),
        x_impersonate_user: Optional[str] = Header(None),
        # Query params (for webhooks/callbacks)
        api_key: Optional[str] = Query(None),
        token: Optional[str] = Query(None)
    ) -> AuthContext:
        """
        Extract AuthContext from any source.

        Priority: Superuser > Service > API Key > User > Anonymous
        """
        # [Implementation details in Multi-Source Authentication section]
        pass

    def require_auth(self, allow_anonymous: bool = False) -> Callable:
        """
        Require any authenticated user/service.

        Example:
            @app.get("/protected")
            async def protected(ctx = deps.require_auth()):
                return {"user": ctx.identity}
        """
        async def check(ctx: AuthContext = Depends(self.get_context)):
            if not allow_anonymous and ctx.source == AuthSource.ANONYMOUS:
                raise HTTPException(401, "Authentication required")
            return ctx
        return Depends(check)

    def require_user(self) -> Callable:
        """
        Require authenticated user (not API key/service).

        Example:
            @app.post("/users/profile")
            async def update_profile(ctx = deps.require_user()):
                # Only human users, not API keys
                return {"updated": True}
        """
        async def check(ctx: AuthContext = Depends(self.get_context)):
            if ctx.source != AuthSource.USER:
                raise HTTPException(403, "User authentication required")
            return ctx
        return Depends(check)

    def require_source(self, *allowed_sources: AuthSource) -> Callable:
        """
        Require specific auth source(s).

        Example:
            # Only API keys
            @app.post("/webhook")
            async def webhook(ctx = deps.require_source(AuthSource.API_KEY)):
                return {"received": True}

            # Users or superusers
            @app.post("/admin/action")
            async def action(
                ctx = deps.require_source(AuthSource.USER, AuthSource.SUPERUSER)
            ):
                return {"performed": True}
        """
        async def check(ctx: AuthContext = Depends(self.get_context)):
            if ctx.source not in allowed_sources:
                raise HTTPException(
                    403,
                    f"Auth source {ctx.source} not allowed. Need: {allowed_sources}"
                )
            return ctx
        return Depends(check)

    # ============================================================
    # AUTHORIZATION (What can you do?)
    # ============================================================

    def require_permission(self, *permissions: str, allow_superuser: bool = True) -> Callable:
        """
        Require one or more permissions (any match).

        Example:
            # Need any one permission
            @app.get("/reports")
            async def reports(ctx = deps.require_permission("reports:read", "admin")):
                return {"reports": [...]}
        """
        async def check(ctx: AuthContext = Depends(self.get_context)):
            if ctx.source == AuthSource.ANONYMOUS:
                raise HTTPException(401, "Authentication required")

            if allow_superuser and ctx.is_superuser:
                return ctx

            if not ctx.has_any_permission(*permissions):
                raise HTTPException(403, f"Need one of: {permissions}")

            return ctx
        return Depends(check)

    def require_all_permissions(self, *permissions: str, allow_superuser: bool = True) -> Callable:
        """
        Require ALL specified permissions.

        Example:
            # Need both permissions
            @app.delete("/users/{user_id}")
            async def delete_user(
                user_id: str,
                ctx = deps.require_all_permissions("user:delete", "audit:write")
            ):
                return {"deleted": True}
        """
        async def check(ctx: AuthContext = Depends(self.get_context)):
            if ctx.source == AuthSource.ANONYMOUS:
                raise HTTPException(401, "Authentication required")

            if allow_superuser and ctx.is_superuser:
                return ctx

            if not ctx.has_all_permissions(*permissions):
                missing = [p for p in permissions if p not in ctx.permissions]
                raise HTTPException(403, f"Missing permissions: {missing}")

            return ctx
        return Depends(check)

    def require_role(self, *roles: str) -> Callable:
        """
        Require one or more roles (any match).

        Example:
            @app.post("/system/backup")
            async def backup(ctx = deps.require_role("admin", "superuser")):
                return {"backed_up": True}
        """
        async def check(ctx: AuthContext = Depends(self.get_context)):
            if ctx.source == AuthSource.ANONYMOUS:
                raise HTTPException(401, "Authentication required")

            if ctx.is_superuser:
                return ctx

            if not any(r in ctx.roles for r in roles):
                raise HTTPException(403, f"Need role: {' or '.join(roles)}")

            return ctx
        return Depends(check)

    # ============================================================
    # ENTITY-BASED (Where can you do it?)
    # ============================================================

    def require_entity_access(self, entity_param: str = "entity_id") -> Callable:
        """
        Require membership in the entity.

        Example:
            @app.get("/entities/{entity_id}/members")
            async def get_members(
                entity_id: str,
                ctx = deps.require_entity_access()
            ):
                return {"members": [...]}
        """
        async def check(
            entity_id: str = Path(..., alias=entity_param),
            ctx: AuthContext = Depends(self.require_auth())
        ):
            if ctx.is_superuser:
                ctx.metadata["entity_id"] = entity_id
                return ctx

            # Check if entity is configured for this preset
            if not self.auth.config.enable_entity_hierarchy:
                raise HTTPException(400, "Entity hierarchy not enabled")

            is_member = await self.auth.membership_service.is_member(
                ctx.identity, entity_id
            )
            if not is_member:
                raise HTTPException(403, f"Not a member of entity: {entity_id}")

            ctx.metadata["entity_id"] = entity_id
            return ctx
        return Depends(check)

    def require_entity_permission(
        self,
        permission: str,
        entity_param: str = "entity_id"
    ) -> Callable:
        """
        Require permission within specific entity.

        Example:
            @app.put("/entities/{entity_id}/settings")
            async def update_settings(
                entity_id: str,
                settings: dict,
                ctx = deps.require_entity_permission("entity:update")
            ):
                return {"updated": True}
        """
        async def check(
            entity_id: str = Path(..., alias=entity_param),
            ctx: AuthContext = Depends(self.require_auth())
        ):
            if ctx.is_superuser:
                ctx.metadata["entity_id"] = entity_id
                return ctx

            if not self.auth.config.enable_entity_hierarchy:
                raise HTTPException(400, "Entity hierarchy not enabled")

            has_perm = await self.auth.permission_service.check_permission(
                ctx.identity, permission, entity_id=entity_id
            )
            if not has_perm:
                raise HTTPException(
                    403,
                    f"Missing permission '{permission}' in entity {entity_id}"
                )

            ctx.metadata["entity_id"] = entity_id
            return ctx
        return Depends(check)

    def require_entity_role(
        self,
        role: str,
        entity_param: str = "entity_id"
    ) -> Callable:
        """
        Require specific role in entity.

        Example:
            @app.post("/entities/{entity_id}/invite")
            async def invite_member(
                entity_id: str,
                email: str,
                ctx = deps.require_entity_role("admin")
            ):
                return {"invited": True}
        """
        async def check(
            entity_id: str = Path(..., alias=entity_param),
            ctx: AuthContext = Depends(self.require_auth())
        ):
            if ctx.is_superuser:
                ctx.metadata["entity_id"] = entity_id
                return ctx

            if not self.auth.config.enable_entity_hierarchy:
                raise HTTPException(400, "Entity hierarchy not enabled")

            membership = await self.auth.membership_service.get_membership(
                ctx.identity, entity_id
            )
            if not membership:
                raise HTTPException(403, "Not a member")

            role_names = [r.name for r in membership.roles]
            if role not in role_names:
                raise HTTPException(403, f"Need role '{role}' in entity")

            ctx.metadata["entity_id"] = entity_id
            return ctx
        return Depends(check)

    # ============================================================
    # SPECIAL ACCESS
    # ============================================================

    def require_superuser(self) -> Callable:
        """
        Require superuser access.

        Example:
            @app.post("/system/dangerous")
            async def dangerous_operation(ctx = deps.require_superuser()):
                return {"performed": True}
        """
        async def check(ctx: AuthContext = Depends(self.get_context)):
            if not ctx.is_superuser:
                raise HTTPException(403, "Superuser access required")
            return ctx
        return Depends(check)

    # ============================================================
    # RATE LIMITING
    # ============================================================

    def rate_limit(
        self,
        default_limit: int = 60,
        window: int = 60  # seconds
    ) -> Callable:
        """
        Rate limit by auth source.

        Example:
            @app.post("/api/expensive")
            async def expensive(ctx = deps.rate_limit(10, 60)):
                # 10 requests per minute
                return {"result": "..."}
        """
        async def check(ctx: AuthContext = Depends(self.get_context)):
            # Different limits by source
            limits = {
                AuthSource.ANONYMOUS: 10,
                AuthSource.USER: default_limit,
                AuthSource.API_KEY: ctx.rate_limit or default_limit,
                AuthSource.SERVICE: 1000,
                AuthSource.SUPERUSER: float('inf')
            }

            limit = limits.get(ctx.source, default_limit)

            if limit != float('inf'):
                key = f"rate_limit:{ctx.source}:{ctx.identity}"

                # Try Redis first, fall back to memory
                if self.redis:
                    current = await self.redis.incr(key)
                    if current == 1:
                        await self.redis.expire(key, window)

                    allowed = current <= limit
                    remaining = max(0, limit - current)
                else:
                    # In-memory fallback (for development)
                    allowed, remaining = await self._check_memory_rate_limit(
                        key, limit, window
                    )

                if not allowed:
                    raise HTTPException(429, "Rate limit exceeded")

                ctx.rate_limit_remaining = remaining

            return ctx
        return Depends(check)

    # ============================================================
    # CONVENIENCE SHORTCUTS
    # ============================================================

    @property
    def authenticated(self) -> Callable:
        """Shortcut for require_auth()"""
        return self.require_auth()

    @property
    def user(self) -> Callable:
        """Shortcut for require_user()"""
        return self.require_user()

    @property
    def admin(self) -> Callable:
        """Shortcut for require_role("admin", "superuser")"""
        return self.require_role("admin", "superuser")

    @property
    def superuser(self) -> Callable:
        """Shortcut for require_superuser()"""
        return self.require_superuser()
```

### Key Benefits

1. **Single Import**: `from outlabs_auth import AuthDeps` - that's it
2. **Discoverable**: IDE autocomplete shows all available methods
3. **Clear Names**: Method names explain exactly what they do
4. **Type-Safe**: Full type hints and validation
5. **Consistent**: Same patterns across all auth requirements
6. **Backward Compatible**: Old code can use thin wrapper classes (SimpleDeps, etc.)

---

## Multi-Source Authentication

### get_context Implementation

The `get_context` method in `AuthDeps` resolves authentication from multiple sources with a clear priority chain. This is the core of multi-source auth support.

```python
# outlabs_auth/dependencies/auth_deps.py (continued)

async def get_context(
    self,
    request: Request,
    # Headers
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
    x_service_token: Optional[str] = Header(None),  # JWT service token (DD-034)
    x_superuser_token: Optional[str] = Header(None),
    x_impersonate_user: Optional[str] = Header(None),
    # Query params (for webhooks/callbacks)
    api_key: Optional[str] = Query(None),
    token: Optional[str] = Query(None)
) -> AuthContext:
    """
    Extract AuthContext from any source.

    Priority: Superuser > Service (JWT) > API Key > User > Anonymous

    Design decisions:
    - DD-034: JWT service tokens for internal microservices (zero DB hits)
    - DD-028: API keys with argon2id hashing + temporary locks
    - DD-033: Redis counters for API key usage tracking
    """

    # 1. Superuser token (admin override)
    if x_superuser_token:
        if await self._validate_superuser_token(x_superuser_token):
            # Check for impersonation
            if x_impersonate_user:
                return await self._create_impersonation_context(
                    x_impersonate_user, x_superuser_token
                )

            return AuthContext(
                source=AuthSource.SUPERUSER,
                identity="superuser",
                is_superuser=True,
                metadata={"ip": request.client.host}
            )

    # 2. JWT Service Token (internal microservices) - DD-034
    if x_service_token:
        try:
            # Validate JWT (no database lookup!)
            payload = await self.auth.service_token_service.validate_jwt(
                x_service_token
            )
            return AuthContext(
                source=AuthSource.SERVICE,
                identity=payload["service_name"],
                permissions=payload.get("permissions", []),
                is_service_account=True,
                metadata={
                    "service": payload["service_name"],
                    "issued_at": payload.get("iat")
                }
            )
        except JWTError:
            pass  # Invalid token, continue to next source

    # 3. API key (external integrations) - DD-028 + DD-033
    api_key_value = x_api_key or api_key
    if api_key_value:
        # Check if temporarily locked (DD-028)
        lock_key = f"api_key:lock:{api_key_value[:12]}"
        if self.redis and await self.redis.exists(lock_key):
            raise HTTPException(
                403,
                "API key temporarily locked due to failed attempts. Try again in 30 minutes."
            )

        key = await self.auth.api_key_service.validate(
            api_key_value,
            client_ip=request.client.host
        )
        if key:
            # Check IP restrictions
            if key.allowed_ips and request.client.host not in key.allowed_ips:
                raise HTTPException(403, "IP not allowed for this API key")

            # Track usage with Redis counters (DD-033)
            if self.redis:
                await self.redis.incr(f"api_key:usage:{key.id}")
                await self.redis.incr(f"api_key:usage:{key.id}:hour:{datetime.utcnow().hour}")

            return AuthContext(
                source=AuthSource.API_KEY,
                identity=str(key.id),
                permissions=key.permissions,
                rate_limit=key.rate_limit_per_minute,
                metadata={
                    "key_name": key.name,
                    "key_prefix": key.key_prefix,
                    "service": key.service_name
                }
            )
        else:
            # Track failed attempt (DD-028)
            if self.redis:
                fail_key = f"api_key:fails:{api_key_value[:12]}"
                fails = await self.redis.incr(fail_key)
                await self.redis.expire(fail_key, 600)  # 10 minutes

                # Temporary lock after 10 failures in 10 minutes
                if fails >= 10:
                    await self.redis.setex(lock_key, 1800, "1")  # 30 min lock

    # 4. User JWT token
    token_value = None
    if authorization and authorization.startswith("Bearer "):
        token_value = authorization.replace("Bearer ", "")
    elif token:
        token_value = token

    if token_value:
        try:
            user = await self.auth.get_current_user(token_value)
            perms = await self.auth.permission_service.get_user_permissions(
                user.id
            )
            roles = await self.auth.role_service.get_user_roles(user.id)

            return AuthContext(
                source=AuthSource.USER,
                identity=str(user.id),
                permissions=perms,
                roles=[r.name for r in roles],
                is_superuser=user.is_superuser,
                metadata={"user": user}
            )
        except JWTError:
            pass  # Invalid token, continue to anonymous

    # 5. Anonymous
    return AuthContext(
        source=AuthSource.ANONYMOUS,
        identity="anonymous"
    )

# --- Internal helpers ---

async def _validate_superuser_token(self, token: str) -> bool:
    """Validate superuser override token"""
    # Implementation: Check against secure superuser token
    # Should be cryptographically secure, time-limited JWT
    # Stored in environment or secure config
    return await self.auth.superuser_service.validate_token(token)

async def _create_impersonation_context(
    self,
    user_id: str,
    superuser_token: str
) -> AuthContext:
    """Create context for admin impersonating user"""
    user = await self.auth.user_service.get_by_id(user_id)
    if not user:
        raise HTTPException(404, "User not found")

    perms = await self.auth.permission_service.get_user_permissions(user.id)

    return AuthContext(
        source=AuthSource.IMPERSONATION,
        identity=str(user.id),
        permissions=perms,
        is_impersonating=True,
        metadata={
            "user": user,
            "impersonator": "superuser"
        }
    )
```

### Key Features

1. **JWT Service Tokens (DD-034)**: Zero-DB authentication for internal microservices
   - Stateless JWT validation (no database lookup)
   - ~0.5ms validation time vs ~50-100ms for API keys
   - Perfect for high-frequency internal requests

2. **API Key Security (DD-028)**: Strong security with graceful failures
   - argon2id hashing for key storage
   - Temporary locks after 10 failed attempts (30-minute cooldown)
   - IP whitelisting support
   - Automatic lock recovery (no permanent revocation)

3. **Redis Counters (DD-033)**: High-performance usage tracking
   - Redis INCR for usage counts (99%+ reduction in DB writes)
   - Hourly granularity for analytics
   - Periodic sync to MongoDB (every 5 minutes)

---

## API Key System

### API Key Models

```python
# outlabs_auth/models/api_key.py
from enum import Enum
from typing import List, Optional
from datetime import datetime
from beanie import Document
from pydantic import Field

class APIKeyScope(str, Enum):
    """API key access scopes"""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"

class APIKeyModel(Document):
    """
    API keys for service-to-service authentication.

    Security (DD-028):
    - argon2id hashing for key storage
    - 12-character prefix for identification (increased from 8)
    - Optional expiration (recommended 90 days) with manual rotation API
    - Temporary locks after 10 failures (no permanent auto-revocation)

    Performance (DD-033):
    - Redis counters for usage tracking
    - Periodic sync to MongoDB (every 5 minutes)
    - 99%+ reduction in database writes
    """

    # Identification
    name: str
    description: Optional[str] = None
    key_hash: str  # argon2id hash of the actual key
    key_prefix: str = Field(..., min_length=12, max_length=12)  # First 12 chars (sk_prod_abc1)

    # Access control
    permissions: List[str] = []
    scopes: List[APIKeyScope] = []
    is_superuser: bool = False

    # Restrictions
    allowed_ips: List[str] = []  # Empty = all IPs
    allowed_origins: List[str] = []  # For CORS
    allowed_endpoints: List[str] = []  # Specific endpoints only

    # Rate limiting
    rate_limit_per_minute: Optional[int] = 60
    rate_limit_per_hour: Optional[int] = 1000

    # Metadata
    service_name: Optional[str] = None  # Which service uses this
    environment: str = "production"  # production, staging, development
    created_by: str  # User ID who created it

    # Lifecycle
    last_used_at: Optional[datetime] = None
    last_used_ip: Optional[str] = None
    expires_at: Optional[datetime] = None  # Optional expiration (recommended 90 days)
    revoked_at: Optional[datetime] = None
    revoked_by: Optional[str] = None
    revoked_reason: Optional[str] = None

    # Status
    is_active: bool = True

    # Stats (synced from Redis every 5 minutes - DD-033)
    usage_count: int = 0
    last_synced_at: Optional[datetime] = None  # NEW: When usage_count was last synced

    class Settings:
        name = "api_keys"
        indexes = [
            "key_prefix",  # 12 characters now
            "is_active",
            "service_name",
            "created_by",
            "expires_at"  # For cleanup jobs
        ]
```

### API Key Service

```python
# outlabs_auth/services/api_key_service.py
import secrets
from passlib.hash import argon2
from typing import Tuple, Optional, List
from datetime import datetime, timedelta

class APIKeyService:
    """Manage API keys"""

    KEY_PREFIX_MAP = {
        "production": "sk_prod",
        "staging": "sk_stag",
        "development": "sk_dev",
        "test": "sk_test"
    }

    @staticmethod
    def generate_key(environment: str = "production") -> str:
        """
        Generate a new API key (DD-028).

        Format: {prefix}_{4_random_chars}_{random_32_bytes}
        Example: sk_prod_abc1_x2y3z4... (12-char prefix: sk_prod_abc1)

        The 12-character prefix includes:
        - 7 chars: environment prefix (sk_prod)
        - 1 char: underscore separator
        - 4 chars: random identifier
        """
        env_prefix = APIKeyService.KEY_PREFIX_MAP.get(environment, "sk_prod")
        random_id = secrets.token_urlsafe(3)[:4]  # 4 random chars
        random_part = secrets.token_urlsafe(32)
        return f"{env_prefix}_{random_id}_{random_part}"

    @staticmethod
    def hash_key(key: str) -> str:
        """
        Hash API key for storage using argon2id.

        Security: argon2id with recommended parameters:
        - time_cost=2 (iterations)
        - memory_cost=102400 (100 MB)
        - parallelism=8
        """
        return argon2.using(
            time_cost=2,
            memory_cost=102400,
            parallelism=8
        ).hash(key)

    async def create_api_key(
        self,
        name: str,
        created_by: str,
        permissions: List[str] = None,
        service_name: Optional[str] = None,
        environment: str = "production",
        expires_in_days: Optional[int] = None,
        **kwargs
    ) -> Tuple[str, APIKeyModel]:
        """
        Create new API key.

        Returns: (raw_key, key_model)

        ⚠️ IMPORTANT: The raw key is only returned once!
        Save it securely - it cannot be recovered.
        """
        raw_key = self.generate_key(environment)

        api_key = APIKeyModel(
            name=name,
            key_hash=self.hash_key(raw_key),
            key_prefix=raw_key[:12],  # Store 12-char prefix for identification (DD-028)
            permissions=permissions or [],
            service_name=service_name,
            environment=environment,
            created_by=created_by,
            **kwargs
        )

        if expires_in_days:
            api_key.expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

        await api_key.save()

        # If durable history is needed here, prefer a narrow lifecycle recorder
        # dependency over a generic audit_service facade.

        return raw_key, api_key

    async def validate(
        self,
        key: str,
        required_permissions: List[str] = None,
        client_ip: Optional[str] = None
    ) -> Optional[APIKeyModel]:
        """
        Validate API key and check permissions (DD-028 + DD-033).

        Changes from v1.3:
        - 12-char prefix (was 8)
        - No error_count tracking (temporary locks handled in get_context)
        - No auto-revocation (temporary locks instead)
        - No usage_count writes (Redis counters handle this)
        - Only updates last_used_at (minimal DB write)

        Returns None if invalid, otherwise returns the key model.
        """
        # Extract prefix (first 12 characters - DD-028)
        if not key or len(key) < 12:
            return None

        prefix = key[:12]

        # Find by prefix
        api_key = await APIKeyModel.find_one(
            APIKeyModel.key_prefix == prefix,
            APIKeyModel.is_active == True
        )

        if not api_key:
            return None

        # Verify hash (constant time comparison via argon2)
        if not argon2.verify(key, api_key.key_hash):
            # Failed validation - caller (get_context) handles temp locks
            return None

        # Check expiration (optional)
        if api_key.expires_at and api_key.expires_at < datetime.utcnow():
            return None

        # Check required permissions
        if required_permissions:
            if not api_key.is_superuser:
                missing = set(required_permissions) - set(api_key.permissions)
                if missing:
                    return None

        # Minimal DB write - only update last_used (DD-033)
        # Usage count is tracked via Redis counters and synced periodically
        api_key.last_used_at = datetime.utcnow()
        if client_ip:
            api_key.last_used_ip = client_ip
        await api_key.save()

        return api_key

    async def revoke(
        self,
        key_id: str,
        revoked_by: str,
        reason: str = "Manual revocation"
    ) -> bool:
        """Revoke an API key"""
        api_key = await APIKeyModel.get(key_id)
        if not api_key:
            return False

        api_key.is_active = False
        api_key.revoked_at = datetime.utcnow()
        api_key.revoked_by = revoked_by
        api_key.revoked_reason = reason
        await api_key.save()

        # If durable history is needed here, prefer a narrow lifecycle recorder
        # dependency over a generic audit_service facade.

        return True

    async def rotate(
        self,
        old_key_id: str,
        rotated_by: str
    ) -> Tuple[str, APIKeyModel]:
        """
        Rotate an API key (revoke old, create new).

        Returns: (new_raw_key, new_key_model)
        """
        old_key = await APIKeyModel.get(old_key_id)
        if not old_key:
            raise ValueError("API key not found")

        # Create new key with same permissions
        new_raw_key, new_key = await self.create_api_key(
            name=f"{old_key.name} (rotated)",
            created_by=rotated_by,
            permissions=old_key.permissions,
            service_name=old_key.service_name,
            environment=old_key.environment,
            allowed_ips=old_key.allowed_ips,
            rate_limit_per_minute=old_key.rate_limit_per_minute
        )

        # Revoke old key
        await self.revoke(old_key_id, rotated_by, "Key rotation")

        return new_raw_key, new_key
```

---

## Group & Entity Permissions

### Group-Based Dependencies

```python
# outlabs_auth/dependencies/groups.py
from fastapi import Depends, HTTPException, Path

class GroupDeps:
    """Group-based authorization"""

    def __init__(self, auth: EnterpriseRBAC):
        self.auth = auth

    def in_group(self, *groups: str):
        """Require membership in one of the groups"""
        async def check(user = Depends(self.auth.get_current_user)):
            user_groups = await self.auth.group_service.get_user_groups(user.id)
            group_names = [g.name for g in user_groups]

            if not any(g in group_names for g in groups):
                raise HTTPException(403, f"Must be in group: {groups}")

            return user
        return Depends(check)

    def group_permission(self, group: str, permission: str):
        """Require group membership AND permission"""
        async def check(user = Depends(self.auth.get_current_user)):
            # Check group membership
            is_member = await self.auth.group_service.is_member(user.id, group)
            if not is_member:
                raise HTTPException(403, f"Not in group: {group}")

            # Check permission within group context
            has_perm = await self.auth.permission_service.check_permission(
                user.id, permission, group_id=group
            )
            if not has_perm:
                raise HTTPException(403, f"Missing permission in group: {permission}")

            return user
        return Depends(check)
```

### Entity-Based Dependencies

```python
# outlabs_auth/dependencies/entities.py
from fastapi import Depends, HTTPException, Path

class EntityDeps:
    """Entity-based authorization"""

    def __init__(self, auth: EnterpriseRBAC):
        self.auth = auth

    def in_entity(self, entity_param: str = "entity_id"):
        """Require membership in the entity"""
        async def check(
            entity_id: str = Path(..., alias=entity_param),
            user = Depends(self.auth.get_current_user)
        ):
            is_member = await self.auth.membership_service.is_member(
                user.id, entity_id
            )
            if not is_member:
                raise HTTPException(403, f"Not a member of entity: {entity_id}")

            # Add entity context to user
            user.current_entity_id = entity_id
            return user
        return Depends(check)

    def entity_permission(self, permission: str, entity_param: str = "entity_id"):
        """Require permission within entity"""
        async def check(
            entity_id: str = Path(..., alias=entity_param),
            user = Depends(self.auth.get_current_user)
        ):
            has_perm = await self.auth.permission_service.check_permission(
                user.id, permission, entity_id=entity_id
            )
            if not has_perm:
                raise HTTPException(
                    403,
                    f"Missing permission '{permission}' in entity {entity_id}"
                )

            user.current_entity_id = entity_id
            return user
        return Depends(check)

    def entity_role(self, role: str, entity_param: str = "entity_id"):
        """Require specific role in entity"""
        async def check(
            entity_id: str = Path(..., alias=entity_param),
            user = Depends(self.auth.get_current_user)
        ):
            membership = await self.auth.membership_service.get_membership(
                user.id, entity_id
            )
            if not membership:
                raise HTTPException(403, "Not a member")

            role_names = [r.name for r in membership.roles]
            if role not in role_names:
                raise HTTPException(403, f"Need role '{role}' in entity")

            return user
        return Depends(check)
```

---

## Advanced Patterns

### Combining Multiple Requirements

```python
# Complex authorization requirements
@app.post("/entities/{entity_id}/admin/action")
async def complex_action(
    entity_id: str,
    # Must be in entity
    in_entity = Depends(entity_deps.in_entity()),
    # Must have permission
    has_perm = Depends(entity_deps.entity_permission("admin:write")),
    # Must be in admin group
    in_group = Depends(group_deps.in_group("admins")),
    # Must not be API key
    ctx: AuthContext = Depends(
        multi.source(AuthSource.USER, AuthSource.SUPERUSER)
    )
):
    # All requirements must pass
    return {"performed": True}
```

### Dynamic Permission Resolution

```python
class DynamicDeps:
    """Dynamic permission checking"""

    def __init__(self, auth: OutlabsAuth):
        self.auth = auth

    def owns_resource(self, resource_type: str):
        """Check resource ownership"""
        async def check(
            resource_id: str = Path(...),
            user = Depends(self.auth.get_current_user)
        ):
            # Get resource
            resource = await get_resource(resource_type, resource_id)

            # Check ownership
            if resource.owner_id != str(user.id):
                # Check if user has override permission
                has_override = await self.auth.permission_service.check_permission(
                    user.id, f"{resource_type}:admin"
                )
                if not has_override:
                    raise HTTPException(403, "Not the owner")

            return user, resource
        return Depends(check)

# Usage
dynamic = DynamicDeps(auth)

@app.put("/invoices/{resource_id}")
async def update_invoice(
    invoice_data: InvoiceUpdate,
    auth_result = dynamic.owns_resource("invoice")
):
    user, invoice = auth_result
    # User owns the invoice or has admin permission
    return await update_invoice(invoice, invoice_data)
```

---

## Rate Limiting

### Rate Limiting by Auth Source

```python
# outlabs_auth/dependencies/rate_limit.py
from fastapi import Depends, HTTPException
from typing import Optional
import asyncio
from collections import defaultdict
from datetime import datetime, timedelta

class RateLimiter:
    """In-memory rate limiter (use Redis in production)"""

    def __init__(self):
        self.requests: defaultdict = defaultdict(list)
        self.lock = asyncio.Lock()

    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        window: int = 60
    ) -> tuple[bool, int]:
        """
        Check if request is within rate limit.

        Returns: (allowed, remaining)
        """
        async with self.lock:
            now = datetime.utcnow()
            window_start = now - timedelta(seconds=window)

            # Clean old requests
            self.requests[key] = [
                ts for ts in self.requests[key]
                if ts > window_start
            ]

            current_count = len(self.requests[key])

            if current_count >= limit:
                return False, 0

            # Add current request
            self.requests[key].append(now)

            return True, limit - current_count - 1

class RateLimitDeps:
    """Rate limiting based on auth source"""

    def __init__(
        self,
        auth: OutlabsAuth,
        redis: Optional[Redis] = None
    ):
        self.auth = auth
        self.redis = redis
        self.memory_limiter = RateLimiter()  # Fallback

    def rate_limit(
        self,
        default_limit: int = 60,
        window: int = 60  # seconds
    ):
        async def check(ctx: AuthContext = Depends(multi.get_context)):
            # Different limits by source
            limits = {
                AuthSource.ANONYMOUS: 10,
                AuthSource.USER: default_limit,
                AuthSource.API_KEY: ctx.rate_limit or default_limit,
                AuthSource.SERVICE: 1000,
                AuthSource.SUPERUSER: float('inf')
            }

            limit = limits.get(ctx.source, default_limit)

            if limit != float('inf'):
                key = f"rate_limit:{ctx.source}:{ctx.identity}"

                # Try Redis first, fall back to memory
                if self.redis:
                    current = await self.redis.incr(key)
                    if current == 1:
                        await self.redis.expire(key, window)

                    allowed = current <= limit
                    remaining = max(0, limit - current)
                else:
                    allowed, remaining = await self.memory_limiter.check_rate_limit(
                        key, limit, window
                    )

                if not allowed:
                    raise HTTPException(429, "Rate limit exceeded")

                ctx.rate_limit_remaining = remaining

            return ctx
        return Depends(check)

# Usage
rate_limiter = RateLimitDeps(auth, redis=redis_client)

@app.post("/api/expensive-operation")
async def expensive_operation(
    ctx: AuthContext = rate_limiter.rate_limit(10, 60)
):
    # 10 requests per minute
    return {"result": "...", "rate_limit_remaining": ctx.rate_limit_remaining}
```

---

## Testing Patterns

### Mock Authentication Context

```python
# tests/conftest.py
import pytest
from unittest.mock import AsyncMock

@pytest.fixture
def mock_auth_context():
    """Create mock auth context for testing"""
    def _create_context(
        source: AuthSource = AuthSource.USER,
        permissions: List[str] = None,
        is_superuser: bool = False,
        **kwargs
    ):
        return AuthContext(
            source=source,
            identity="test_user_id",
            permissions=permissions or [],
            is_superuser=is_superuser,
            **kwargs
        )
    return _create_context

@pytest.fixture
def override_auth(mock_auth_context):
    """Override auth dependencies for testing"""
    def _override(
        permissions: List[str] = None,
        source: AuthSource = AuthSource.USER,
        **kwargs
    ):
        context = mock_auth_context(
            source=source,
            permissions=permissions,
            **kwargs
        )

        async def mock_get_context():
            return context

        app.dependency_overrides[multi.get_context] = mock_get_context
        return context

    yield _override

    # Cleanup
    app.dependency_overrides.clear()
```

### Test Examples

```python
def test_endpoint_requires_permission(client, override_auth):
    """Test that endpoint requires specific permission"""

    # Without permission - should fail
    override_auth(permissions=["other:permission"])
    response = client.delete("/users/123")
    assert response.status_code == 403

    # With permission - should succeed
    override_auth(permissions=["user:delete"])
    response = client.delete("/users/123")
    assert response.status_code == 200

def test_api_key_access(client, override_auth):
    """Test API key authentication"""

    override_auth(
        source=AuthSource.API_KEY,
        permissions=["data:read"],
        metadata={"key_name": "test_key"}
    )

    response = client.get("/api/data")
    assert response.status_code == 200
    assert response.json()["auth_source"] == "api_key"

def test_superuser_bypass(client, override_auth):
    """Test superuser can bypass permissions"""

    override_auth(
        permissions=[],  # No permissions
        is_superuser=True  # But is superuser
    )

    response = client.post("/system/reset")
    assert response.status_code == 200

def test_multi_source_priority(client, override_auth):
    """Test auth source priority"""

    # Superuser takes priority
    override_auth(
        source=AuthSource.SUPERUSER,
        is_superuser=True
    )

    response = client.get("/admin/data")
    assert response.status_code == 200
```

### Integration Tests

```python
@pytest.mark.integration
async def test_full_auth_flow(auth_system, test_db):
    """Test complete authentication flow"""

    # Create user
    user = await auth_system.user_service.create_user(
        email="test@example.com",
        password="TestPass123!"
    )

    # Create role with permissions
    role = await auth_system.role_service.create_role(
        name="manager",
        permissions=["user:read", "user:update"]
    )

    # Assign role
    await auth_system.user_service.assign_role(user.id, role.id)

    # Login
    tokens = await auth_system.auth_service.login(
        "test@example.com",
        "TestPass123!"
    )

    # Use token in request
    client.headers = {"Authorization": f"Bearer {tokens.access_token}"}
    response = client.get("/users")

    assert response.status_code == 200

@pytest.mark.integration
async def test_api_key_lifecycle(auth_system, test_user):
    """Test API key creation, usage, rotation, revocation"""

    # Create key
    raw_key, key = await auth_system.api_key_service.create_api_key(
        name="test_key",
        created_by=str(test_user.id),
        permissions=["api:read"],
        expires_in_days=90
    )

    assert raw_key.startswith("sk_prod_")
    assert len(raw_key) > 20

    # Validate key
    validated = await auth_system.api_key_service.validate(raw_key)
    assert validated is not None
    assert validated.usage_count == 1

    # Rotate key
    new_key, new_model = await auth_system.api_key_service.rotate(
        str(key.id),
        str(test_user.id)
    )

    # Old key should be revoked
    old_validated = await auth_system.api_key_service.validate(raw_key)
    assert old_validated is None

    # New key should work
    new_validated = await auth_system.api_key_service.validate(new_key)
    assert new_validated is not None
```

---

## Security Best Practices

### API Key Security

#### 1. Never Log or Store Raw Keys

```python
# ❌ BAD - Never do this
logger.info(f"Created key: {raw_key}")
await db.keys.insert_one({"key": raw_key})

# ✅ GOOD - Only log prefix
logger.info(f"Created key with prefix: {key.key_prefix}")
await db.keys.insert_one({"key_hash": hash_key(raw_key)})
```

#### 2. Use Strong Hashing

```python
# ❌ BAD - SHA256 is too fast
import hashlib
key_hash = hashlib.sha256(key.encode()).hexdigest()

# ✅ GOOD - argon2id with proper parameters
from passlib.hash import argon2
key_hash = argon2.using(
    time_cost=2,
    memory_cost=102400,
    parallelism=8
).hash(key)
```

#### 3. Implement Key Rotation

```python
# Rotate keys periodically (90 days recommended)
@app.post("/api-keys/auto-rotate")
async def auto_rotate_old_keys():
    """Automatically rotate keys older than 90 days"""
    cutoff = datetime.utcnow() - timedelta(days=90)

    old_keys = await APIKeyModel.find(
        APIKeyModel.created_at < cutoff,
        APIKeyModel.is_active == True
    ).to_list()

    results = []
    for key in old_keys:
        try:
            new_key, new_model = await auth.api_key_service.rotate(
                str(key.id),
                "system"
            )
            results.append({
                "old_id": str(key.id),
                "new_id": str(new_model.id),
                "status": "rotated"
            })
        except Exception as e:
            results.append({
                "old_id": str(key.id),
                "status": "failed",
                "error": str(e)
            })

    return {"rotated": len(results), "results": results}
```

#### 4. Rate Limit by Key

```python
# Track usage per key
async def track_api_usage(key_id: str, endpoint: str):
    """Track API usage for monitoring"""
    await redis.hincrby(f"api_usage:{key_id}", endpoint, 1)
    await redis.expire(f"api_usage:{key_id}", 3600)

# Check for abuse
async def check_api_abuse(key_id: str) -> bool:
    """Check if key is being abused"""
    usage = await redis.hgetall(f"api_usage:{key_id}")
    total = sum(int(v) for v in usage.values())

    # Alert if > 10k requests in 1 hour
    if total > 10000:
        await send_alert(f"High API usage for key {key_id}: {total} requests/hour")
        return True

    return False
```

#### 5. Audit All Key Operations

```python
# Log all API key operations
@app.middleware("http")
async def audit_api_keys(request: Request, call_next):
    """Audit all API key usage"""

    if "x-api-key" in request.headers:
        key_prefix = request.headers["x-api-key"][:8]

        # Log the request
        await audit_log.create(
            type="api_key_usage",
            key_prefix=key_prefix,
            endpoint=request.url.path,
            method=request.method,
            ip=request.client.host,
            user_agent=request.headers.get("user-agent"),
            timestamp=datetime.utcnow()
        )

    response = await call_next(request)
    return response
```

#### 6. IP Whitelisting

```python
# Strictly enforce IP restrictions
async def validate_api_key_with_ip(
    key: str,
    client_ip: str
) -> Optional[APIKeyModel]:
    """Validate key and check IP whitelist"""

    key_model = await api_key_service.validate(key)
    if not key_model:
        return None

    # Enforce IP whitelist if configured
    if key_model.allowed_ips:
        if client_ip not in key_model.allowed_ips:
            # Log unauthorized access attempt
            await security_log.create(
                type="unauthorized_ip",
                key_id=str(key_model.id),
                ip=client_ip,
                allowed_ips=key_model.allowed_ips
            )
            return None

    return key_model
```

#### 7. Automatic Revocation

```python
# Auto-revoke on suspicious activity
async def check_and_revoke_if_compromised(key_id: str):
    """Check for signs of compromise"""

    key = await APIKeyModel.get(key_id)
    if not key:
        return

    # Check error rate
    if key.error_count >= 10:
        await api_key_service.revoke(
            key_id,
            "system",
            "Too many failed validation attempts"
        )
        await send_alert(f"API key {key.name} auto-revoked due to high error rate")
        return

    # Check for unusual access patterns
    recent_ips = await get_recent_ips(key_id, hours=1)
    if len(recent_ips) > 10:
        await api_key_service.revoke(
            key_id,
            "system",
            "Suspicious: Too many different IPs"
        )
        await send_alert(f"API key {key.name} auto-revoked due to suspicious activity")
```

### Permission Security

1. **Principle of Least Privilege**: Grant minimum required permissions
2. **Regular Audits**: Review permissions quarterly
3. **Time-Based Permissions**: Expire high-privilege access
4. **Context-Aware**: Scope permissions to entities when possible
5. **Audit All Changes**: Log every permission grant/revoke

### Service Account Security

1. **Separate from Users**: Never use user accounts for services
2. **Token-Based Only**: No password authentication
3. **Short-Lived Tokens**: 1-24 hours maximum
4. **Rotate Regularly**: Automatic rotation policies
5. **Audit Heavily**: Log all service account usage

---

## Summary

### Key Takeaways

1. **AuthContext**: Universal abstraction for all auth sources
2. **Composable Dependencies**: Build complex auth from simple pieces
3. **Multi-Source Support**: Users, API keys, services, superusers
4. **Type-Safe**: Full IDE support and validation
5. **Testable**: Easy to mock and override
6. **Secure by Default**: argon2id, rate limiting, audit logging

### Quick Reference

```python
# Simple auth
require = SimpleDeps(auth)
@app.get("/data")
async def get_data(user = require.requires("data:read")):
    return data

# Multi-source auth
multi = MultiSourceDeps(auth)
@app.get("/api/data")
async def get_api_data(ctx: AuthContext = multi.permission("data:read")):
    return data

# API key
raw_key, key = await auth.api_key_service.create_api_key(
    name="prod_api",
    created_by=user_id,
    permissions=["api:read"]
)

# Test
def test_auth(client, override_auth):
    override_auth(permissions=["data:read"])
    response = client.get("/data")
    assert response.status_code == 200
```

---

**Last Updated**: 2025-01-14 (Unified AuthDeps class, JWT service tokens, Redis counters, temp locks)
**Next Review**: After Phase 2 implementation
**Related Documents**:
- [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md) - DD-028, DD-033, DD-034, DD-035
- [LIBRARY_ARCHITECTURE.md](LIBRARY_ARCHITECTURE.md) - Technical architecture
- [SECURITY.md](SECURITY.md) - Security hardening
- [TESTING_GUIDE.md](TESTING_GUIDE.md) - Testing strategies
- [API_DESIGN.md](API_DESIGN.md) - Usage examples
