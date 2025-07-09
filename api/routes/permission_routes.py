"""
Permission Routes
API endpoints for managing custom permissions
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field

from api.models import UserModel, PermissionModel
from api.models.permission_model import Condition
from api.services.permission_management_service import permission_management_service
from api.services.permission_service import permission_service
from api.routes.auth_routes import get_current_user
from api.dependencies import require_permission

router = APIRouter()


# Request/Response schemas
class PermissionCreateRequest(BaseModel):
    """Request to create a new permission"""
    name: str = Field(..., min_length=3, max_length=100, description="Permission identifier (e.g., 'lead:create')")
    display_name: str = Field(..., min_length=3, max_length=200, description="Human-readable name")
    description: Optional[str] = Field(None, max_length=500, description="Permission description")
    entity_id: Optional[str] = Field(None, description="Entity that owns this permission")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")
    conditions: List[Condition] = Field(default_factory=list, description="ABAC conditions for this permission")
    metadata: dict = Field(default_factory=dict, description="Additional metadata")


class PermissionUpdateRequest(BaseModel):
    """Request to update a permission"""
    display_name: Optional[str] = Field(None, min_length=3, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None
    tags: Optional[List[str]] = None
    conditions: Optional[List[Condition]] = None
    metadata: Optional[dict] = None


class PermissionResponse(BaseModel):
    """Permission response"""
    id: Optional[str] = Field(None, description="Permission ID (None for system permissions)")
    name: str
    display_name: str
    description: Optional[str]
    resource: str
    action: str
    scope: Optional[str] = None
    entity_id: Optional[str] = None
    is_system: bool
    is_active: bool
    tags: List[str]
    conditions: List[Condition] = Field(default_factory=list, description="ABAC conditions")
    metadata: dict
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    created_by: Optional[str] = None

    @classmethod
    def from_model(cls, permission: PermissionModel) -> "PermissionResponse":
        """Create response from permission model"""
        return cls(
            id=str(permission.id) if permission.id else None,
            name=permission.name,
            display_name=permission.display_name,
            description=permission.description,
            resource=permission.resource,
            action=permission.action,
            scope=permission.scope,
            entity_id=str(permission.entity_id) if permission.entity_id else None,
            is_system=permission.is_system,
            is_active=permission.is_active,
            tags=permission.tags,
            conditions=permission.conditions,
            metadata=permission.metadata,
            created_at=permission.created_at.isoformat() if permission.created_at else None,
            updated_at=permission.updated_at.isoformat() if permission.updated_at else None,
            created_by=str(permission.created_by) if permission.created_by else None
        )


class PermissionListResponse(BaseModel):
    """List of permissions"""
    permissions: List[PermissionResponse]
    total: int
    system_count: int
    custom_count: int


@router.post("/", response_model=PermissionResponse, dependencies=[Depends(require_permission("permission:create"))])
async def create_permission(
    request: PermissionCreateRequest,
    current_user: UserModel = Depends(get_current_user)
):
    """
    Create a new custom permission
    
    Requires: permission:create
    """
    permission = await permission_management_service.create_permission(
        name=request.name,
        display_name=request.display_name,
        description=request.description,
        entity_id=request.entity_id,
        created_by=current_user,
        tags=request.tags,
        conditions=request.conditions,
        metadata=request.metadata
    )
    
    return PermissionResponse.from_model(permission)


@router.get("/available", response_model=PermissionListResponse)
async def get_available_permissions(
    entity_id: Optional[str] = Query(None, description="Entity context"),
    include_system: bool = Query(True, description="Include system permissions"),
    include_inherited: bool = Query(True, description="Include inherited permissions"),
    active_only: bool = Query(True, description="Only active permissions"),
    current_user: UserModel = Depends(get_current_user)
):
    """
    Get all available permissions for the current context
    
    This endpoint is used by the UI to show available permissions when creating/editing roles.
    """
    permissions = await permission_management_service.get_available_permissions(
        entity_id=entity_id,
        include_system=include_system,
        include_inherited=include_inherited,
        active_only=active_only
    )
    
    # Convert to responses (handle both dict and model objects)
    permission_responses = []
    for p in permissions:
        if isinstance(p, dict):
            # System permission as dict
            permission_responses.append(PermissionResponse(**p))
        else:
            # Custom permission as model
            permission_responses.append(PermissionResponse.from_model(p))
    
    # Count system vs custom
    system_count = sum(1 for p in permissions if (p.get('is_system', False) if isinstance(p, dict) else p.is_system))
    custom_count = len(permissions) - system_count
    
    return PermissionListResponse(
        permissions=permission_responses,
        total=len(permissions),
        system_count=system_count,
        custom_count=custom_count
    )


@router.get("/{permission_id}", response_model=PermissionResponse, dependencies=[Depends(require_permission("permission:read"))])
async def get_permission(
    permission_id: str,
    current_user: UserModel = Depends(get_current_user)
):
    """
    Get permission by ID
    
    Requires: permission:read
    """
    permission = await permission_management_service.get_permission(permission_id)
    return PermissionResponse.from_model(permission)


@router.put("/{permission_id}", response_model=PermissionResponse, dependencies=[Depends(require_permission("permission:update"))])
async def update_permission(
    permission_id: str,
    request: PermissionUpdateRequest,
    current_user: UserModel = Depends(get_current_user)
):
    """
    Update a custom permission
    
    Requires: permission:update
    Note: System permissions cannot be updated
    """
    permission = await permission_management_service.update_permission(
        permission_id=permission_id,
        display_name=request.display_name,
        description=request.description,
        is_active=request.is_active,
        tags=request.tags,
        conditions=request.conditions,
        metadata=request.metadata,
        current_user=current_user
    )
    
    return PermissionResponse.from_model(permission)


@router.delete("/{permission_id}", dependencies=[Depends(require_permission("permission:delete"))])
async def delete_permission(
    permission_id: str,
    current_user: UserModel = Depends(get_current_user)
):
    """
    Delete a custom permission
    
    Requires: permission:delete
    Note: System permissions cannot be deleted
    Note: Permissions in use by roles cannot be deleted
    """
    await permission_management_service.delete_permission(
        permission_id=permission_id,
        current_user=current_user
    )
    
    return {"message": "Permission deleted successfully"}


@router.post("/validate")
async def validate_permissions(
    permissions: List[str],
    entity_id: Optional[str] = Query(None, description="Entity context for validation"),
    current_user: UserModel = Depends(get_current_user)
):
    """
    Validate a list of permission strings
    
    Returns the list if all permissions are valid.
    Raises 400 error if any permission is invalid.
    """
    validated = await permission_management_service.validate_permissions(
        permissions=permissions,
        entity_id=entity_id
    )
    
    return {
        "valid": True,
        "permissions": validated,
        "count": len(validated)
    }


# Permission Check schemas
class PermissionCheckRequest(BaseModel):
    """Request to check a permission with optional resource context"""
    permission: str = Field(..., description="Permission to check (e.g., 'invoice:approve')")
    entity_id: Optional[str] = Field(None, description="Entity context for the check")
    resource_attributes: Optional[Dict[str, Any]] = Field(
        None, 
        description="Attributes of the resource being accessed for ABAC evaluation"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "permission": "invoice:approve",
                "entity_id": "507f1f77bcf86cd799439011",
                "resource_attributes": {
                    "value": 25000,
                    "currency": "USD",
                    "status": "pending_approval",
                    "department": "finance"
                }
            }
        }


class PermissionCheckResponse(BaseModel):
    """Response from permission check"""
    allowed: bool = Field(..., description="Whether permission is granted")
    reason: str = Field(..., description="Human-readable reason for the decision")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional evaluation details")
    
    class Config:
        json_schema_extra = {
            "example": {
                "allowed": True,
                "reason": "All conditions passed",
                "details": {
                    "rbac_check": True,
                    "rbac_source": "role",
                    "evaluations": [
                        {
                            "attribute": "resource.value",
                            "operator": "LESS_THAN_OR_EQUAL",
                            "expected": 50000,
                            "actual": 25000,
                            "passed": True,
                            "reason": "Condition evaluation successful"
                        }
                    ]
                }
            }
        }


@router.post("/check", response_model=PermissionCheckResponse)
async def check_permission(
    request: PermissionCheckRequest,
    current_user: UserModel = Depends(get_current_user)
):
    """
    Check if the current user has a specific permission with optional ABAC conditions
    
    This endpoint performs a comprehensive permission check that includes:
    1. Traditional RBAC (role-based) checks
    2. ReBAC (relationship-based) checks through entity hierarchy
    3. ABAC (attribute-based) condition evaluation if resource_attributes are provided
    
    The permission is granted only if:
    - User has the basic permission through their roles (RBAC)
    - All conditions defined on the permission pass (ABAC)
    """
    result = await permission_service.check_permission_with_context(
        user_id=str(current_user.id),
        permission=request.permission,
        entity_id=request.entity_id,
        resource_attributes=request.resource_attributes,
        use_cache=True
    )
    
    return PermissionCheckResponse(
        allowed=result.allowed,
        reason=result.reason,
        details=result.details
    )