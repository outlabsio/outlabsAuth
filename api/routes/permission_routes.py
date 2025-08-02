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


# Effective Permissions schemas
class EffectivePermissionsResponse(BaseModel):
    """Response showing effective permissions for a user at an entity"""
    user_id: str
    user_email: str
    entity_id: str
    entity_name: str
    entity_type: str
    effective_permissions: List[str] = Field(
        ..., description="All permissions the user has at this entity"
    )
    permission_sources: List[Dict[str, Any]] = Field(
        ..., description="Detailed breakdown of where each permission comes from"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "507f1f77bcf86cd799439011",
                "user_email": "john.doe@example.com",
                "entity_id": "507f191e810c19729de860ea",
                "entity_name": "Miami Branch",
                "entity_type": "branch",
                "effective_permissions": ["entity:read", "entity:update", "user:read"],
                "permission_sources": [
                    {
                        "permission": "entity:read",
                        "source": "role:branch_manager",
                        "context": "direct_assignment",
                        "entity": "Miami Branch",
                        "entity_id": "507f191e810c19729de860ea",
                        "role_name": "Branch Manager",
                        "is_context_aware": True,
                        "applied_from_type": "branch"
                    },
                    {
                        "permission": "user:read",
                        "source": "role:regional_manager",
                        "context": "inherited_from_parent",
                        "entity": "Florida Division",
                        "entity_id": "507f191e810c19729de860eb",
                        "role_name": "Regional Manager",
                        "is_context_aware": False
                    }
                ]
            }
        }


@router.get("/users/{user_id}/effective-permissions", response_model=EffectivePermissionsResponse)
async def get_user_effective_permissions(
    user_id: str,
    entity_id: Optional[str] = Query(None, description="Entity context to check permissions for"),
    current_user: UserModel = Depends(get_current_user)
):
    """
    Get effective permissions for a user at a specific entity
    
    This endpoint shows:
    1. All permissions the user has at the entity
    2. Where each permission comes from (role, entity, inheritance)
    3. Whether permissions are from context-aware roles
    
    Useful for:
    - Debugging permission issues
    - Understanding permission inheritance
    - Auditing access rights
    """
    # Check if user can view other users' permissions
    if str(current_user.id) != user_id:
        # Need permission to view others' permissions
        has_permission, _ = await permission_service.check_permission(
            user_id=str(current_user.id),
            permission="user:read",
            entity_id=entity_id
        )
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to view this user's permissions"
            )
    
    # Get the target user
    target_user = await UserModel.get(user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Get the entity if specified
    entity = None
    if entity_id:
        from api.models import EntityModel
        entity = await EntityModel.get(entity_id)
        if not entity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Entity not found"
            )
    
    # Get all user permissions with sources
    user_permissions = await permission_service.resolve_user_permissions(
        user_id=user_id,
        entity_id=entity_id,
        use_cache=False  # Don't use cache for detailed analysis
    )
    
    # Build detailed permission sources
    permission_sources = []
    all_permissions = set()
    
    # Get user memberships for context
    from api.models import EntityMembershipModel
    memberships = await EntityMembershipModel.find(
        EntityMembershipModel.user.id == target_user.id,
        EntityMembershipModel.is_active == True
    ).to_list()
    
    # Process each membership to understand permission sources
    for membership in memberships:
        # Skip if not the entity we're interested in (if specified)
        if entity_id and str(membership.entity.id) != entity_id:
            continue
            
        # Get entity info
        member_entity = await membership.entity.fetch()
        if not member_entity:
            continue
            
        # Process roles in this membership
        for role_link in membership.roles:
            role = await role_link.fetch()
            if not role:
                continue
                
            # Determine which permissions apply based on context
            permissions_to_apply = []
            is_context_aware = False
            applied_from_type = None
            
            # Check if role has context-aware permissions
            if role.entity_type_permissions and member_entity.entity_type in role.entity_type_permissions:
                permissions_to_apply = role.entity_type_permissions[member_entity.entity_type]
                is_context_aware = True
                applied_from_type = member_entity.entity_type
            else:
                permissions_to_apply = role.permissions
                
            # Add each permission with source info
            for perm in permissions_to_apply:
                all_permissions.add(perm)
                permission_sources.append({
                    "permission": perm,
                    "source": f"role:{role.name}",
                    "context": "direct_assignment",
                    "entity": member_entity.display_name,
                    "entity_id": str(member_entity.id),
                    "entity_type": member_entity.entity_type,
                    "role_name": role.display_name,
                    "role_id": str(role.id),
                    "is_context_aware": is_context_aware,
                    "applied_from_type": applied_from_type
                })
    
    # Check for inherited permissions from parent entities
    if entity:
        from api.services.entity_service import EntityService
        entity_path = await EntityService.get_entity_path(str(entity.id))
        
        # Check parent entities for tree permissions
        for i, parent_entity in enumerate(entity_path[:-1]):
            parent_permissions = await permission_service.resolve_user_permissions(
                user_id=user_id,
                entity_id=str(parent_entity.id),
                use_cache=False
            )
            
            # Check for tree permissions that apply to descendants
            for source, perms in parent_permissions.items():
                for perm in perms:
                    if ":" in perm:
                        resource, action = perm.split(":", 1)
                        tree_perm = f"{resource}:{action}_tree"
                        
                        # If parent has tree permission, child gets base permission
                        if tree_perm in perms:
                            base_perm = f"{resource}:{action.replace('_tree', '')}"
                            if base_perm not in all_permissions:
                                all_permissions.add(base_perm)
                                permission_sources.append({
                                    "permission": base_perm,
                                    "source": f"inherited:{source}",
                                    "context": "inherited_from_parent",
                                    "entity": parent_entity.display_name,
                                    "entity_id": str(parent_entity.id),
                                    "entity_type": parent_entity.entity_type,
                                    "parent_permission": tree_perm,
                                    "inheritance_depth": i + 1
                                })
    
    # Add direct entity permissions if any
    if entity and entity.direct_permissions:
        for perm in entity.direct_permissions:
            all_permissions.add(perm)
            permission_sources.append({
                "permission": perm,
                "source": "entity:direct",
                "context": "entity_direct_permission",
                "entity": entity.display_name,
                "entity_id": str(entity.id),
                "entity_type": entity.entity_type
            })
    
    # Sort permissions and sources for readability
    effective_permissions = sorted(list(all_permissions))
    permission_sources.sort(key=lambda x: (x["permission"], x["source"]))
    
    return EffectivePermissionsResponse(
        user_id=user_id,
        user_email=target_user.email,
        entity_id=entity_id or "global",
        entity_name=entity.display_name if entity else "Global Context",
        entity_type=entity.entity_type if entity else "global",
        effective_permissions=effective_permissions,
        permission_sources=permission_sources
    )