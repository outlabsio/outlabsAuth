# Consistency Fixes - January 26, 2025

## Summary

This document details all consistency fixes applied to the OutlabsAuth codebase to align implementation with design decisions and ensure consistency across models, services, schemas, and routers.

## Overview

**Total Files Modified**: 6
**Total Issues Fixed**: 25+
**Categories**: Model field usage, API schemas, router integration, service method naming

---

## 1. Duplicate File Deletion

### Issue
Two API key service files existed with conflicting implementations:
- `outlabs_auth/services/api_key.py` (full implementation)
- `outlabs_auth/services/api_key_service.py` (only empty lifecycle hooks)

### Fix
**DELETED**: `outlabs_auth/services/api_key_service.py`
**KEPT**: `outlabs_auth/services/api_key.py` (complete implementation)

**Rationale**: The duplicate file had no actual service logic, only empty hook methods that weren't being used.

---

## 2. Service Method Naming Consistency

### File: `outlabs_auth/services/api_key.py`

#### Issue
Inconsistent method naming - used `validate_api_key()` instead of standard `verify_*` pattern.

#### Fix
```python
# BEFORE
async def validate_api_key(...) -> tuple[Optional[APIKeyModel], int]:

# AFTER
async def verify_api_key(...) -> tuple[Optional[APIKeyModel], int]:
```

#### Docstring Fix
```python
# BEFORE
"""
Validate API key and track usage with Redis counter.
...
"""

# AFTER
"""
Verify API key and track usage with Redis counter.
...
"""
```

**Rationale**: Aligns with naming convention used elsewhere (`verify_password`, `verify_token`).

---

## 3. EntityMembershipModel.is_active → status Migration

### Background
The `EntityMembershipModel` was redesigned to use a `MembershipStatus` enum instead of a boolean `is_active` field, providing richer status tracking (ACTIVE, SUSPENDED, REVOKED, EXPIRED, PENDING, REJECTED).

### Files Modified
1. `outlabs_auth/services/membership.py` (7 fixes)
2. `outlabs_auth/services/permission.py` (3 fixes + import)

---

### 3.1 Membership Service Fixes

**File**: `outlabs_auth/services/membership.py`

#### Import Added
```python
from outlabs_auth.models.membership_status import MembershipStatus
```

#### Fix 1: Line 134 - Reactivate Existing Membership
```python
# BEFORE
existing.is_active = True

# AFTER
existing.status = MembershipStatus.ACTIVE
```

#### Fix 2: Lines 165-208 - Remove Member (Soft Delete)
```python
# BEFORE
async def remove_member(self, entity_id: str, user_id: str) -> bool:
    """Remove user from entity (hard delete)."""
    # ... hard delete logic ...

# AFTER
async def remove_member(self, entity_id: str, user_id: str, revoked_by: Optional[str] = None) -> bool:
    """Remove user from entity (soft delete by setting status=REVOKED)."""
    
    # Soft delete - set status to REVOKED with audit trail
    membership.status = MembershipStatus.REVOKED
    membership.revoked_at = datetime.now(timezone.utc)
    if revoked_by:
        revoked_by_user = await UserModel.get(revoked_by)
        if revoked_by_user:
            membership.revoked_by = revoked_by_user
    membership.updated_at = datetime.now(timezone.utc)
    await membership.save()
```

#### Fixes 3-6: Lines 321, 359, 398, 490 - Query Conditions
```python
# BEFORE (4 locations)
EntityMembershipModel.is_active == True

# AFTER (4 locations)
EntityMembershipModel.status == MembershipStatus.ACTIVE
```

**Affected Methods**:
- `get_entity_members()` - Line 321
- `get_user_entities()` - Line 359
- `get_user_roles_in_entity()` - Line 398
- `is_member()` - Line 490

---

### 3.2 Permission Service Fixes

**File**: `outlabs_auth/services/permission.py`

#### Import Added
```python
from outlabs_auth.models.membership_status import MembershipStatus
```

#### Fix 1: Line 603 - Check Permission (Enterprise)
```python
# BEFORE
# TODO: Update to use status field when EntityMembershipModel is created
# Should be: {"user.$id": user.id, "status": MembershipStatus.ACTIVE.value}
memberships = await EntityMembershipModel.find(
    EntityMembershipModel.user.id == user.id,
    EntityMembershipModel.is_active == True,
).to_list()

# AFTER
# Get all user memberships
memberships = await EntityMembershipModel.find(
    EntityMembershipModel.user.id == user.id,
    EntityMembershipModel.status == MembershipStatus.ACTIVE,
).to_list()
```

#### Fix 2: Line 878 - Get User Permissions in Entity
```python
# BEFORE
# TODO: Update to use status field when EntityMembershipModel is created
# Should use: {"user.$id": user.id, "entity.$id": entity_oid, "status": MembershipStatus.ACTIVE.value}
# and membership.can_grant_permissions() instead of is_active + is_currently_valid()
membership = await EntityMembershipModel.find_one(
    EntityMembershipModel.user.id == user.id,
    EntityMembershipModel.entity.id == entity_oid,
    EntityMembershipModel.is_active == True,
)

# AFTER
# Get membership in entity
membership = await EntityMembershipModel.find_one(
    EntityMembershipModel.user.id == user.id,
    EntityMembershipModel.entity.id == entity_oid,
    EntityMembershipModel.status == MembershipStatus.ACTIVE,
)
```

#### Fix 3: Line 1091 - Check Permission with Context (ABAC)
```python
# BEFORE
# TODO: Update to use status field when EntityMembershipModel is created
# Should be: {"user.$id": user.id, "status": MembershipStatus.ACTIVE.value}
memberships = await EntityMembershipModel.find(
    EntityMembershipModel.user.id == user.id,
    EntityMembershipModel.is_active == True,
).to_list()

# AFTER
# Get memberships to check role conditions
memberships = await EntityMembershipModel.find(
    EntityMembershipModel.user.id == user.id,
    EntityMembershipModel.status == MembershipStatus.ACTIVE,
).to_list()
```

---

## 4. API Key Schemas Alignment

### File: `outlabs_auth/schemas/api_key.py`

#### Background
API key schemas had field name mismatches with the actual `APIKeyModel`:
- Model uses `scopes` (not `permissions`)
- Model uses `prefix` (not `key_prefix`)
- Model uses `status: APIKeyStatus` enum (not `is_active: bool`)
- Model uses `prefix_type` parameter (not `environment`)
- Model uses `ip_whitelist` (not `allowed_ips`)
- Model uses `owner` Link (not `created_by` or `user_id`)

---

### 4.1 ApiKeyCreateRequest Schema

```python
# BEFORE
class ApiKeyCreateRequest(BaseModel):
    """API key creation request schema."""
    name: str = Field(..., description="Friendly name for the API key")
    permissions: List[str] = Field(default_factory=list, description="List of allowed permissions")
    environment: str = Field(default="production", description="Environment: production, staging, development, test")
    allowed_ips: Optional[List[str]] = Field(default=None, description="IP whitelist (optional)")
    rate_limit_per_minute: int = Field(default=60, description="Rate limit per minute")
    expires_at: Optional[datetime] = Field(default=None, description="Optional expiration date")

# AFTER
from outlabs_auth.models.api_key import APIKeyStatus

class ApiKeyCreateRequest(BaseModel):
    """API key creation request schema."""
    name: str = Field(..., description="Friendly name for the API key")
    scopes: List[str] = Field(default_factory=list, description="List of allowed permissions/scopes")
    prefix_type: str = Field(default="sk_live", description="Key prefix type: sk_live, sk_test, etc.")
    ip_whitelist: Optional[List[str]] = Field(default=None, description="IP whitelist (optional)")
    rate_limit_per_minute: int = Field(default=60, description="Rate limit per minute")
    expires_at: Optional[datetime] = Field(default=None, description="Optional expiration date")
    description: Optional[str] = Field(default=None, description="Optional key description")
    entity_ids: Optional[List[str]] = Field(default=None, description="Restrict to specific entities (None = all)")
```

**Changes**:
- `permissions` → `scopes`
- `environment` → `prefix_type`
- `allowed_ips` → `ip_whitelist`
- Added `description` field
- Added `entity_ids` field

---

### 4.2 ApiKeyResponse Schema

```python
# BEFORE
class ApiKeyResponse(BaseModel):
    """API key response schema."""
    id: str
    key_prefix: str  # First 12 chars only
    name: str
    permissions: List[str]
    environment: str
    allowed_ips: Optional[List[str]] = None
    rate_limit_per_minute: int
    is_active: bool
    usage_count: int
    created_at: datetime
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# AFTER
class ApiKeyResponse(BaseModel):
    """API key response schema."""
    id: str
    prefix: str  # First 12 chars only
    name: str
    scopes: List[str]
    ip_whitelist: Optional[List[str]] = None
    rate_limit_per_minute: int
    status: APIKeyStatus
    usage_count: int
    created_at: datetime
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    description: Optional[str] = None
    entity_ids: Optional[List[str]] = None
    owner_id: Optional[str] = None  # String representation of owner ID

    class Config:
        from_attributes = True
```

**Changes**:
- `key_prefix` → `prefix`
- `permissions` → `scopes`
- `environment` → removed
- `allowed_ips` → `ip_whitelist`
- `is_active: bool` → `status: APIKeyStatus`
- Added `description` field
- Added `entity_ids` field
- Added `owner_id` field

---

### 4.3 ApiKeyUpdateRequest Schema

```python
# BEFORE
class ApiKeyUpdateRequest(BaseModel):
    """API key update request schema."""
    name: Optional[str] = None
    permissions: Optional[List[str]] = None
    allowed_ips: Optional[List[str]] = None
    rate_limit_per_minute: Optional[int] = None
    is_active: Optional[bool] = None

# AFTER
class ApiKeyUpdateRequest(BaseModel):
    """API key update request schema."""
    name: Optional[str] = None
    scopes: Optional[List[str]] = None
    ip_whitelist: Optional[List[str]] = None
    rate_limit_per_minute: Optional[int] = None
    status: Optional[APIKeyStatus] = None
    description: Optional[str] = None
    entity_ids: Optional[List[str]] = None
```

**Changes**:
- `permissions` → `scopes`
- `allowed_ips` → `ip_whitelist`
- `is_active: bool` → `status: APIKeyStatus`
- Added `description` field
- Added `entity_ids` field

---

## 5. API Key Router Integration Fixes

### File: `outlabs_auth/routers/api_keys.py`

#### Background
The router had multiple issues:
1. Using wrong field names when calling service methods
2. Using wrong service method names
3. Incorrectly accessing `api_key.user_id` instead of `api_key.owner`
4. Not converting Beanie models to response schemas properly
5. Service method `create_api_key` returns tuple, not dict

---

### 5.1 List API Keys Endpoint

```python
# BEFORE
async def list_api_keys(auth_result=Depends(auth.deps.require_auth())):
    """List all API keys for the current user."""
    try:
        api_keys = await auth.api_key_service.list_api_keys(  # ❌ Wrong method name
            user_id=auth_result["user_id"]
        )
        return api_keys  # ❌ Returns Beanie models directly

# AFTER
async def list_api_keys(auth_result=Depends(auth.deps.require_auth())):
    """List all API keys for the current user."""
    try:
        api_keys = await auth.api_key_service.list_user_api_keys(  # ✅ Correct method
            user_id=auth_result["user_id"]
        )
        
        # Convert to response format
        response_list = []
        for api_key in api_keys:
            response_data = api_key.model_dump()
            response_data["id"] = str(api_key.id)
            response_data["owner_id"] = str(api_key.owner.ref.id) if api_key.owner else None
            response_list.append(ApiKeyResponse(**response_data))
        
        return response_list
```

---

### 5.2 Create API Key Endpoint

```python
# BEFORE
async def create_api_key(data: ApiKeyCreateRequest, auth_result=Depends(auth.deps.require_auth())):
    try:
        result = await auth.api_key_service.create_api_key(
            user_id=auth_result["user_id"],           # ❌ Wrong param: owner_id
            name=data.name,
            permissions=data.permissions,             # ❌ Wrong field: scopes
            environment=data.environment,             # ❌ Wrong field: prefix_type
            allowed_ips=data.allowed_ips,             # ❌ Wrong field: ip_whitelist
            rate_limit_per_minute=data.rate_limit_per_minute,
            expires_at=data.expires_at
        )
        
        # ❌ Assumes dict return, actually returns tuple
        return ApiKeyCreateResponse(
            api_key=result["api_key"],
            **result["key_object"].model_dump()
        )

# AFTER
async def create_api_key(data: ApiKeyCreateRequest, auth_result=Depends(auth.deps.require_auth())):
    try:
        # create_api_key returns tuple: (full_key, api_key_model)
        full_key, api_key_model = await auth.api_key_service.create_api_key(
            owner_id=auth_result["user_id"],          # ✅ Correct param
            name=data.name,
            scopes=data.scopes,                       # ✅ Correct field
            prefix_type=data.prefix_type,             # ✅ Correct field
            ip_whitelist=data.ip_whitelist,           # ✅ Correct field
            rate_limit_per_minute=data.rate_limit_per_minute,
            expires_at=data.expires_at,
            description=data.description,
            entity_ids=data.entity_ids
        )
        
        # Convert model to response with full key
        response_data = api_key_model.model_dump()
        response_data["id"] = str(api_key_model.id)
        response_data["owner_id"] = str(api_key_model.owner.ref.id) if api_key_model.owner else None
        response_data["api_key"] = full_key  # Full key (ONLY time it's shown!)
        
        return ApiKeyCreateResponse(**response_data)
```

---

### 5.3 Get API Key Endpoint

```python
# BEFORE
async def get_api_key(key_id: str, auth_result=Depends(auth.deps.require_auth())):
    try:
        api_key = await auth.api_key_service.get_api_key(key_id)
        
        if not api_key:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
        
        # Verify ownership
        if str(api_key.user_id) != auth_result["user_id"]:  # ❌ Wrong field: owner
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        
        return api_key  # ❌ Returns Beanie model directly

# AFTER
async def get_api_key(key_id: str, auth_result=Depends(auth.deps.require_auth())):
    try:
        api_key = await auth.api_key_service.get_api_key(key_id)
        
        if not api_key:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
        
        # Verify ownership
        owner_id = str(api_key.owner.ref.id) if api_key.owner else None  # ✅ Correct field
        if owner_id != auth_result["user_id"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        
        # Convert to response format
        response_data = api_key.model_dump()
        response_data["id"] = str(api_key.id)
        response_data["owner_id"] = owner_id
        return ApiKeyResponse(**response_data)
```

---

### 5.4 Update API Key Endpoint

```python
# BEFORE
async def update_api_key(key_id: str, data: ApiKeyUpdateRequest, auth_result=Depends(auth.deps.require_auth())):
    try:
        api_key = await auth.api_key_service.get_api_key(key_id)
        if not api_key or str(api_key.user_id) != auth_result["user_id"]:  # ❌ Wrong field
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
        
        updated_key = await auth.api_key_service.update_api_key(
            key_id=key_id,
            update_dict=data.model_dump(exclude_unset=True)  # ❌ Wrong param format
        )
        
        return updated_key  # ❌ Returns Beanie model directly

# AFTER
async def update_api_key(key_id: str, data: ApiKeyUpdateRequest, auth_result=Depends(auth.deps.require_auth())):
    try:
        api_key = await auth.api_key_service.get_api_key(key_id)
        owner_id = str(api_key.owner.ref.id) if api_key and api_key.owner else None
        if not api_key or owner_id != auth_result["user_id"]:  # ✅ Correct field
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
        
        updated_key = await auth.api_key_service.update_api_key(
            key_id=key_id,
            **data.model_dump(exclude_unset=True)  # ✅ Correct param format
        )
        
        # Convert to response format
        response_data = updated_key.model_dump()
        response_data["id"] = str(updated_key.id)
        response_data["owner_id"] = str(updated_key.owner.ref.id) if updated_key.owner else None
        return ApiKeyResponse(**response_data)
```

---

### 5.5 Delete API Key Endpoint

```python
# BEFORE
async def delete_api_key(key_id: str, auth_result=Depends(auth.deps.require_auth())):
    try:
        api_key = await auth.api_key_service.get_api_key(key_id)
        if not api_key or str(api_key.user_id) != auth_result["user_id"]:  # ❌ Wrong field
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
        
        await auth.api_key_service.delete_api_key(key_id)  # ❌ Wrong method name

# AFTER
async def delete_api_key(key_id: str, auth_result=Depends(auth.deps.require_auth())):
    try:
        api_key = await auth.api_key_service.get_api_key(key_id)
        owner_id = str(api_key.owner.ref.id) if api_key and api_key.owner else None
        if not api_key or owner_id != auth_result["user_id"]:  # ✅ Correct field
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
        
        await auth.api_key_service.revoke_api_key(key_id)  # ✅ Correct method name
```

---

### 5.6 Rotate API Key Endpoint

```python
# BEFORE
async def rotate_api_key(key_id: str, auth_result=Depends(auth.deps.require_auth())):
    try:
        api_key = await auth.api_key_service.get_api_key(key_id)
        if not api_key or str(api_key.user_id) != auth_result["user_id"]:  # ❌ Wrong field
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
        
        result = await auth.api_key_service.rotate_api_key(key_id)  # ❌ Method doesn't exist
        # ...

# AFTER
async def rotate_api_key(key_id: str, auth_result=Depends(auth.deps.require_auth())):
    try:
        api_key = await auth.api_key_service.get_api_key(key_id)
        owner_id = str(api_key.owner.ref.id) if api_key and api_key.owner else None
        if not api_key or owner_id != auth_result["user_id"]:  # ✅ Correct field
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
        
        # TODO: Implement rotate_api_key in service
        # For now, manually rotate: create new with same settings, revoke old
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="API key rotation not yet implemented"
        )
```

---

## Impact Summary

### Files Changed
1. ✅ `outlabs_auth/services/api_key_service.py` - DELETED (duplicate)
2. ✅ `outlabs_auth/services/api_key.py` - Method renamed (validate → verify)
3. ✅ `outlabs_auth/services/membership.py` - 7 fixes (is_active → status)
4. ✅ `outlabs_auth/services/permission.py` - 3 fixes + import (is_active → status)
5. ✅ `outlabs_auth/schemas/api_key.py` - Complete schema overhaul (field renames)
6. ✅ `outlabs_auth/routers/api_keys.py` - 6 endpoint fixes (params, ownership, responses)

### Breaking Changes
⚠️ **API Schema Breaking Changes** - API consumers will need to update:
- `permissions` → `scopes`
- `environment` → `prefix_type`
- `allowed_ips` → `ip_whitelist`
- `key_prefix` → `prefix`
- `is_active` → `status` (enum)

### Non-Breaking Internal Changes
✅ **Internal consistency improvements**:
- Membership status queries now use enum
- Service method naming consistency
- Proper Beanie Link field access
- Correct response schema conversion

### Future Work
- [ ] Implement `rotate_api_key()` in service (currently returns 501)
- [ ] Update API documentation to reflect new field names
- [ ] Consider migration script for existing API consumers

---

## Verification Checklist

- [x] All `is_active` references replaced with `status` checks
- [x] All API key field names aligned with model
- [x] All router endpoints convert Beanie models to schemas
- [x] All ownership checks use `api_key.owner.ref.id`
- [x] Service method names follow `verify_*` convention
- [x] No duplicate service files
- [x] All imports added where needed

---

**Status**: ✅ All consistency fixes completed
**Date**: January 26, 2025
**Files Modified**: 6 (1 deleted, 5 updated)
**Issues Fixed**: 25+
