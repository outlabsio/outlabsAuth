# OutlabsAuth - Authentication Dependency Patterns

**Version**: 1.0
**Date**: 2025-01-14
**Status**: Core Feature (v1.0)

---

## Table of Contents

1. [Overview](#overview)
2. [AuthContext Architecture](#authcontext-architecture)
3. [Simple Dependency Patterns](#simple-dependency-patterns)
4. [Multi-Source Authentication](#multi-source-authentication)
5. [API Key System](#api-key-system)
6. [Group & Entity Permissions](#group--entity-permissions)
7. [Advanced Patterns](#advanced-patterns)
8. [Rate Limiting](#rate-limiting)
9. [Testing Patterns](#testing-patterns)
10. [Security Best Practices](#security-best-practices)

---

## Overview

This document outlines how to use FastAPI's dependency injection system to create simple, composable authentication and authorization patterns that work across different authentication sources (users, API keys, service accounts, superusers).

### Core Design Principles

1. **Dead Simple for Common Cases**: One-line protection for endpoints
2. **Composable**: Mix and match different auth requirements
3. **Type-Safe**: Full IDE support and type checking
4. **Testable**: Easy to mock and test
5. **Multi-Source**: Support users, API keys, services, and more
6. **Secure by Default**: Industry best practices built-in

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

## Simple Dependency Patterns

### SimpleDeps - Basic Authentication

For most use cases, the `SimpleDeps` class provides dead-simple auth protection.

```python
# outlabs_auth/dependencies/simple.py
from fastapi import Depends, HTTPException, Header
from typing import Optional

class SimpleDeps:
    """Simple authentication dependencies"""

    def __init__(self, auth: OutlabsAuth):
        self.auth = auth

    # --- Basic Authentication ---

    def authenticated(self):
        """Just require any authentication"""
        async def get_user(
            authorization: Optional[str] = Header(None)
        ):
            if not authorization:
                raise HTTPException(401, "Not authenticated")

            token = authorization.replace("Bearer ", "")
            user = await self.auth.get_current_user(token)
            return user

        return Depends(get_user)

    # --- Permission-Based ---

    def requires(self, *permissions: str):
        """Require all listed permissions"""
        async def check(user = Depends(self.authenticated())):
            for permission in permissions:
                has_perm = await self.auth.permission_service.check_permission(
                    user.id, permission
                )
                if not has_perm:
                    raise HTTPException(403, f"Missing permission: {permission}")
            return user

        return Depends(check)

    def requires_any(self, *permissions: str):
        """Require at least one permission"""
        async def check(user = Depends(self.authenticated())):
            for permission in permissions:
                has_perm = await self.auth.permission_service.check_permission(
                    user.id, permission
                )
                if has_perm:
                    return user

            raise HTTPException(403, f"Need one of: {permissions}")

        return Depends(check)

    # --- Role-Based ---

    def role(self, *roles: str):
        """Require one of the listed roles"""
        async def check(user = Depends(self.authenticated())):
            user_roles = await self.auth.role_service.get_user_roles(user.id)
            role_names = [r.name for r in user_roles]

            if not any(r in role_names for r in roles):
                raise HTTPException(403, f"Need role: {' or '.join(roles)}")

            return user

        return Depends(check)

    # --- Shortcuts ---

    @property
    def admin(self):
        """Shortcut for admin access"""
        return self.role("admin", "superuser")

    @property
    def user(self):
        """Shortcut for authenticated user"""
        return self.authenticated()
```

### Usage Examples

```python
from fastapi import FastAPI
from outlabs_auth import SimpleRBAC

app = FastAPI()
auth = SimpleRBAC(database=db)

# Create dependency factory
require = SimpleDeps(auth)

# --- Dead Simple Usage ---

# Just need authentication
@app.get("/profile")
async def get_profile(user = require.user):
    return user.profile

# Need specific permission
@app.delete("/users/{user_id}")
async def delete_user(user_id: str, user = require.requires("user:delete")):
    await user_service.delete(user_id)
    return {"deleted": True}

# Need one of several permissions
@app.get("/reports")
async def view_reports(user = require.requires_any("reports:read", "admin")):
    return await report_service.get_all()

# Need admin role
@app.post("/system/reset")
async def system_reset(user = require.admin):
    await system.reset()
    return {"status": "reset"}

# Combine multiple requirements
@app.post("/sensitive/action")
async def sensitive_action(
    user = require.requires("sensitive:write"),
    is_admin = require.role("admin", "manager")
):
    # User must have permission AND be admin/manager
    return {"performed": True}
```

---

## Multi-Source Authentication

### MultiSourceDeps - Handle All Auth Sources

The `MultiSourceDeps` class resolves authentication from multiple sources with a clear priority chain.

```python
# outlabs_auth/dependencies/multi_source.py
from fastapi import Header, Query, Request, HTTPException
from typing import Optional

class MultiSourceDeps:
    """Handle authentication from multiple sources"""

    def __init__(self, auth: OutlabsAuth):
        self.auth = auth

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
        Extract auth from any source.

        Priority: Superuser > Service > API Key > User > Anonymous
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

        # 2. Service account (internal services)
        if x_service_token:
            service = await self.auth.service_account_service.validate_token(
                x_service_token
            )
            if service:
                return AuthContext(
                    source=AuthSource.SERVICE,
                    identity=service.name,
                    permissions=service.permissions,
                    is_service_account=True,
                    metadata={"service": service.name}
                )

        # 3. API key (external integrations)
        api_key_value = x_api_key or api_key
        if api_key_value:
            key = await self.auth.api_key_service.validate(api_key_value)
            if key:
                # Check IP restrictions
                if key.allowed_ips and request.client.host not in key.allowed_ips:
                    raise HTTPException(403, "IP not allowed for this API key")

                return AuthContext(
                    source=AuthSource.API_KEY,
                    identity=str(key.id),
                    permissions=key.permissions,
                    rate_limit=key.rate_limit_per_minute,
                    metadata={
                        "key_name": key.name,
                        "service": key.service_name
                    }
                )

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
                groups = await self.auth.group_service.get_user_groups(user.id)

                return AuthContext(
                    source=AuthSource.USER,
                    identity=str(user.id),
                    permissions=perms,
                    roles=[r.name for r in roles],
                    groups=[g.name for g in groups],
                    is_superuser=user.is_superuser,
                    metadata={"user": user}
                )
            except Exception:
                pass  # Invalid token, continue to anonymous

        # 5. Anonymous
        return AuthContext(
            source=AuthSource.ANONYMOUS,
            identity="anonymous"
        )

    # --- Dependency Factories ---

    def authenticated(self, allow_anonymous: bool = False):
        """Require some form of authentication"""
        async def check(ctx: AuthContext = Depends(self.get_context)):
            if not allow_anonymous and ctx.source == AuthSource.ANONYMOUS:
                raise HTTPException(401, "Authentication required")
            return ctx
        return Depends(check)

    def permission(self, *perms: str, allow_superuser: bool = True):
        """Require permissions"""
        async def check(ctx: AuthContext = Depends(self.get_context)):
            if ctx.source == AuthSource.ANONYMOUS:
                raise HTTPException(401, "Authentication required")

            if allow_superuser and ctx.is_superuser:
                return ctx

            if not ctx.has_all_permissions(*perms):
                missing = [p for p in perms if p not in ctx.permissions]
                raise HTTPException(403, f"Missing permissions: {missing}")

            return ctx
        return Depends(check)

    def source(self, *allowed_sources: AuthSource):
        """Restrict to specific auth sources"""
        async def check(ctx: AuthContext = Depends(self.get_context)):
            if ctx.source not in allowed_sources:
                raise HTTPException(
                    403,
                    f"Auth source {ctx.source} not allowed. Need: {allowed_sources}"
                )
            return ctx
        return Depends(check)

    # --- Internal helpers ---

    async def _validate_superuser_token(self, token: str) -> bool:
        """Validate superuser override token"""
        # Implementation: Check against secure superuser token
        # Should be cryptographically secure, time-limited token
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

### Multi-Source Usage Examples

```python
# Create multi-source dependencies
multi = MultiSourceDeps(auth)

# Allow both users and API keys
@app.get("/api/data")
async def get_data(
    ctx: AuthContext = multi.permission("data:read")
):
    if ctx.source == AuthSource.API_KEY:
        # Log API key usage
        await log_api_usage(ctx.metadata["key_name"])

    return {"data": "...", "auth_source": ctx.source}

# API keys only (for webhooks/integrations)
@app.post("/webhook/github")
async def github_webhook(
    payload: dict,
    ctx: AuthContext = multi.source(AuthSource.API_KEY)
):
    # Only API keys can call webhooks
    return {"received": True}

# Service accounts only (internal microservices)
@app.post("/internal/sync")
async def internal_sync(
    ctx: AuthContext = multi.source(AuthSource.SERVICE)
):
    service_name = ctx.metadata["service"]
    await sync_service.run(service_name)
    return {"synced": True}

# Public endpoint with optional auth
@app.get("/public/content")
async def public_content(
    ctx: AuthContext = multi.authenticated(allow_anonymous=True)
):
    if ctx.source != AuthSource.ANONYMOUS:
        # Authenticated users see more
        return {"content": "...", "premium": "..."}
    return {"content": "..."}
```

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
    """API keys for service-to-service authentication"""

    # Identification
    name: str
    description: Optional[str] = None
    key_hash: str  # argon2id hash of the actual key
    key_prefix: str = Field(..., min_length=8, max_length=8)  # First 8 chars (sk_prod_)

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
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    revoked_by: Optional[str] = None
    revoked_reason: Optional[str] = None

    # Status
    is_active: bool = True

    # Stats
    usage_count: int = 0
    error_count: int = 0

    class Settings:
        name = "api_keys"
        indexes = [
            "key_prefix",
            "is_active",
            "service_name",
            "created_by"
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
        Generate a new API key.

        Format: {prefix}_{random_32_bytes}
        Example: sk_prod_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
        """
        prefix = APIKeyService.KEY_PREFIX_MAP.get(environment, "sk_prod")
        random_part = secrets.token_urlsafe(32)
        return f"{prefix}_{random_part}"

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
            key_prefix=raw_key[:8],  # Store prefix for identification
            permissions=permissions or [],
            service_name=service_name,
            environment=environment,
            created_by=created_by,
            **kwargs
        )

        if expires_in_days:
            api_key.expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

        await api_key.save()

        # Log key creation
        await self.audit_service.log(
            action="api_key.created",
            actor=created_by,
            target=str(api_key.id),
            metadata={"name": name, "service": service_name}
        )

        return raw_key, api_key

    async def validate(
        self,
        key: str,
        required_permissions: List[str] = None
    ) -> Optional[APIKeyModel]:
        """
        Validate API key and check permissions.

        Returns None if invalid, otherwise returns the key model.
        """
        # Extract prefix (first 8 characters)
        if not key or len(key) < 8:
            return None

        prefix = key[:8]

        # Find by prefix
        api_key = await APIKeyModel.find_one(
            APIKeyModel.key_prefix == prefix,
            APIKeyModel.is_active == True
        )

        if not api_key:
            return None

        # Verify hash (constant time comparison via argon2)
        if not argon2.verify(key, api_key.key_hash):
            # Log failed attempt
            api_key.error_count += 1
            await api_key.save()

            # Auto-revoke after 10 failed attempts
            if api_key.error_count >= 10:
                await self.revoke(
                    str(api_key.id),
                    "system",
                    "Too many failed validation attempts"
                )

            return None

        # Check expiration
        if api_key.expires_at and api_key.expires_at < datetime.utcnow():
            return None

        # Check required permissions
        if required_permissions:
            if not api_key.is_superuser:
                missing = set(required_permissions) - set(api_key.permissions)
                if missing:
                    return None

        # Update usage stats
        api_key.last_used_at = datetime.utcnow()
        api_key.usage_count += 1
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

        # Log revocation
        await self.audit_service.log(
            action="api_key.revoked",
            actor=revoked_by,
            target=key_id,
            metadata={"reason": reason}
        )

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

**Last Updated**: 2025-01-14
**Next Review**: After Phase 2 implementation
**Related Documents**:
- [LIBRARY_ARCHITECTURE.md](LIBRARY_ARCHITECTURE.md) - Technical architecture
- [SECURITY.md](SECURITY.md) - Security hardening
- [TESTING_GUIDE.md](TESTING_GUIDE.md) - Testing strategies
- [API_DESIGN.md](API_DESIGN.md) - Usage examples
