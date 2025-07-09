"""
Role routes
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from api.models import UserModel
from api.schemas.role_schema import (
    RoleCreate,
    RoleUpdate,
    RoleResponse,
    RoleListResponse,
    RoleSearchParams,
    RoleTemplateResponse,
    RolePermissionTemplate,
    RoleUsageStatsResponse,
    RoleUsageStats
)
from api.services.role_service import RoleService
from api.dependencies import (
    require_role_read,
    require_role_manage,
    get_current_user
)

router = APIRouter()


@router.post("/", response_model=RoleResponse, dependencies=[Depends(require_role_manage)])
async def create_role(
    role_data: RoleCreate,
    current_user: UserModel = Depends(get_current_user)
):
    """
    Create a new role
    
    Requires: role:manage permission
    """
    role = await RoleService.create_role(
        name=role_data.name,
        display_name=role_data.display_name,
        description=role_data.description,
        permissions=role_data.permissions,
        entity_id=role_data.entity_id,
        assignable_at_types=role_data.assignable_at_types,
        is_global=role_data.is_global,
        created_by=current_user
    )
    
    # Get entity name if applicable
    entity_name = None
    if role.entity_id:
        from api.models import EntityModel
        entity = await EntityModel.get(role.entity_id)
        if entity:
            entity_name = entity.display_name
    
    return RoleResponse(
        id=str(role.id),
        name=role.name,
        display_name=role.display_name,
        description=role.description,
        permissions=role.permissions,
        entity_id=str(role.entity_id) if role.entity_id else None,
        entity_name=entity_name,
        assignable_at_types=role.assignable_at_types,
        is_system_role=role.is_system_role,
        is_global=role.is_global,
        created_at=role.created_at,
        updated_at=role.updated_at
    )


@router.get("/{role_id}", response_model=RoleResponse, dependencies=[Depends(require_role_read)])
async def get_role(role_id: str):
    """
    Get role by ID
    
    Requires: role:read permission
    """
    role = await RoleService.get_role(role_id)
    
    # Get entity name if applicable
    entity_name = None
    if role.entity_id:
        from api.models import EntityModel
        entity = await EntityModel.get(role.entity_id)
        if entity:
            entity_name = entity.display_name
    
    return RoleResponse(
        id=str(role.id),
        name=role.name,
        display_name=role.display_name,
        description=role.description,
        permissions=role.permissions,
        entity_id=str(role.entity_id) if role.entity_id else None,
        entity_name=entity_name,
        assignable_at_types=role.assignable_at_types,
        is_system_role=role.is_system_role,
        is_global=role.is_global,
        created_at=role.created_at,
        updated_at=role.updated_at
    )


@router.put("/{role_id}", response_model=RoleResponse, dependencies=[Depends(require_role_manage)])
async def update_role(
    role_id: str,
    update_data: RoleUpdate,
    current_user: UserModel = Depends(get_current_user)
):
    """
    Update a role
    
    Requires: role:manage permission
    """
    role = await RoleService.update_role(
        role_id=role_id,
        display_name=update_data.display_name,
        description=update_data.description,
        permissions=update_data.permissions,
        assignable_at_types=update_data.assignable_at_types,
        updated_by=current_user
    )
    
    # Get entity name if applicable
    entity_name = None
    if role.entity_id:
        from api.models import EntityModel
        entity = await EntityModel.get(role.entity_id)
        if entity:
            entity_name = entity.display_name
    
    return RoleResponse(
        id=str(role.id),
        name=role.name,
        display_name=role.display_name,
        description=role.description,
        permissions=role.permissions,
        entity_id=str(role.entity_id) if role.entity_id else None,
        entity_name=entity_name,
        assignable_at_types=role.assignable_at_types,
        is_system_role=role.is_system_role,
        is_global=role.is_global,
        created_at=role.created_at,
        updated_at=role.updated_at
    )


@router.delete("/{role_id}", dependencies=[Depends(require_role_manage)])
async def delete_role(
    role_id: str,
    current_user: UserModel = Depends(get_current_user)
):
    """
    Delete a role
    
    Requires: role:manage permission
    """
    await RoleService.delete_role(role_id, current_user)
    return {"message": "Role deleted successfully"}


@router.get("/", response_model=RoleListResponse, dependencies=[Depends(require_role_read)])
async def search_roles(
    entity_id: Optional[str] = Query(None, description="Filter by entity"),
    query: Optional[str] = Query(None, description="Search in name and description"),
    is_global: Optional[bool] = Query(None, description="Filter by global status"),
    assignable_at_type: Optional[str] = Query(None, description="Filter by assignable type"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    """
    Search roles with filtering and pagination
    
    Requires: role:read permission
    """
    roles, total = await RoleService.search_roles(
        entity_id=entity_id,
        query=query,
        is_global=is_global,
        assignable_at_type=assignable_at_type,
        page=page,
        page_size=page_size
    )
    
    # Convert to response models
    items = []
    for role in roles:
        # Get entity name if applicable
        entity_name = None
        if role.entity_id:
            from api.models import EntityModel
            entity = await EntityModel.get(role.entity_id)
            if entity:
                entity_name = entity.display_name
        
        items.append(RoleResponse(
            id=str(role.id),
            name=role.name,
            display_name=role.display_name,
            description=role.description,
            permissions=role.permissions,
            entity_id=str(role.entity_id) if role.entity_id else None,
            entity_name=entity_name,
            assignable_at_types=role.assignable_at_types,
            is_system_role=role.is_system_role,
            is_global=role.is_global,
            created_at=role.created_at,
            updated_at=role.updated_at
        ))
    
    total_pages = (total + page_size - 1) // page_size
    
    return RoleListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get("/entity/{entity_id}/assignable", response_model=List[RoleResponse])
async def get_assignable_roles(
    entity_id: str,
    current_user: UserModel = Depends(get_current_user)
):
    """
    Get roles that can be assigned at a specific entity
    
    Requires: Authentication
    """
    # Get entity to determine type
    from api.models import EntityModel
    entity = await EntityModel.get(entity_id)
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found"
        )
    
    # Get assignable roles
    roles = await RoleService.get_assignable_roles(entity_id, entity.entity_type)
    
    # Convert to response models
    response_roles = []
    for role in roles:
        # Get entity name if applicable
        entity_name = None
        if role.entity_id:
            role_entity = await EntityModel.get(role.entity_id)
            if role_entity:
                entity_name = role_entity.display_name
        
        response_roles.append(RoleResponse(
            id=str(role.id),
            name=role.name,
            display_name=role.display_name,
            description=role.description,
            permissions=role.permissions,
            entity_id=str(role.entity_id) if role.entity_id else None,
            entity_name=entity_name,
            assignable_at_types=role.assignable_at_types,
            is_system_role=role.is_system_role,
            is_global=role.is_global,
            created_at=role.created_at,
            updated_at=role.updated_at
        ))
    
    return response_roles


@router.post("/entity/{entity_id}/defaults", response_model=List[RoleResponse])
async def create_default_roles(
    entity_id: str,
    current_user: UserModel = Depends(require_role_manage)
):
    """
    Create default roles for an entity
    
    Requires: role:manage permission
    """
    roles = await RoleService.create_default_roles(entity_id)
    
    # Convert to response models
    response_roles = []
    for role in roles:
        # Get entity name
        from api.models import EntityModel
        entity = await EntityModel.get(role.entity_id)
        entity_name = entity.display_name if entity else None
        
        response_roles.append(RoleResponse(
            id=str(role.id),
            name=role.name,
            display_name=role.display_name,
            description=role.description,
            permissions=role.permissions,
            entity_id=str(role.entity_id) if role.entity_id else None,
            entity_name=entity_name,
            assignable_at_types=role.assignable_at_types,
            is_system_role=role.is_system_role,
            is_global=role.is_global,
            created_at=role.created_at,
            updated_at=role.updated_at
        ))
    
    return response_roles


@router.get("/templates", response_model=RoleTemplateResponse)
async def get_role_templates():
    """
    Get role permission templates
    
    Requires: Authentication
    """
    templates = {}
    
    for template_name, permissions in RoleService.PERMISSION_TEMPLATES.items():
        templates[template_name] = RolePermissionTemplate(
            name=template_name,
            display_name=template_name.title(),
            description=f"Standard {template_name} role with appropriate permissions",
            permissions=permissions,
            suitable_for=["platform", "organization", "team"]  # Most templates work for these
        )
    
    return RoleTemplateResponse(templates=templates)


@router.get("/{role_id}/usage", response_model=RoleUsageStatsResponse)
async def get_role_usage_stats(
    role_id: str,
    current_user: UserModel = Depends(require_role_read)
):
    """
    Get usage statistics for a role
    
    Requires: role:read permission
    """
    # Get role
    role = await RoleService.get_role(role_id)
    
    # Get usage statistics
    from api.models import EntityMembershipModel
    
    # Count active assignments
    active_assignments = await EntityMembershipModel.find(
        EntityMembershipModel.role.id == role.id,
        EntityMembershipModel.status == "active"
    ).count()
    
    # Count total assignments
    total_assignments = await EntityMembershipModel.find(
        EntityMembershipModel.role.id == role.id
    ).count()
    
    # Count entities used in
    memberships = await EntityMembershipModel.find(
        EntityMembershipModel.role.id == role.id
    ).to_list()
    
    unique_entities = set()
    last_assigned = None
    
    for membership in memberships:
        unique_entities.add(str(membership.entity.id))
        if not last_assigned or membership.created_at > last_assigned:
            last_assigned = membership.created_at
    
    stats = RoleUsageStats(
        role_id=str(role.id),
        role_name=role.display_name,
        active_assignments=active_assignments,
        total_assignments=total_assignments,
        entities_used_in=len(unique_entities),
        last_assigned=last_assigned
    )
    
    return RoleUsageStatsResponse(stats=[stats])