"""
Entity routes
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from api.models import UserModel
from api.schemas.entity_schema import (
    EntityCreate,
    EntityUpdate,
    EntityResponse,
    EntityTreeResponse,
    EntityListResponse,
    EntitySearchParams,
    EntityMemberAdd,
    EntityMemberUpdate,
    EntityMemberResponse,
    EntityPermissionCheck,
    EntityPermissionResponse
)
from api.services.entity_service import EntityService
from api.services.entity_membership_service import EntityMembershipService
from api.dependencies import (
    require_entity_create,
    require_entity_read,
    require_entity_manage,
    require_member_read,
    require_member_manage,
    require_self_or_permission,
    get_current_user
)

router = APIRouter()


# Entity CRUD Operations

@router.post("/", response_model=EntityResponse)
async def create_entity(
    entity_data: EntityCreate,
    current_user: UserModel = Depends(require_entity_create)
):
    """
    Create a new entity
    
    Requires: entity:create permission
    """
    
    entity = await EntityService.create_entity(entity_data, current_user)
    
    return EntityResponse(
        id=str(entity.id),
        name=entity.name,
        display_name=entity.name,  # Use name as display_name
        description=entity.description,
        entity_class=entity.entity_class.value.upper(),  # Convert to uppercase
        entity_type=entity.entity_type,
        parent_entity_id=str(entity.parent_entity.ref.id) if entity.parent_entity else None,
        platform_id=str(entity.platform_id) if entity.platform_id else None,
        status=entity.status,
        direct_permissions=entity.direct_permissions,
        config=entity.metadata,  # Use metadata as config
        valid_from=entity.valid_from,
        valid_until=entity.valid_until,
        created_at=entity.created_at,
        updated_at=entity.updated_at
    )


@router.get("/{entity_id}", response_model=EntityResponse)
async def get_entity(
    entity_id: str,
    current_user: UserModel = Depends(require_entity_read)
):
    """
    Get entity by ID
    
    Requires: entity:read permission or membership in entity
    """
    entity = await EntityService.get_entity(entity_id)
    
    return EntityResponse(
        id=str(entity.id),
        name=entity.name,
        display_name=entity.name,  # Use name as display_name
        description=entity.description,
        entity_class=entity.entity_class.value.upper(),  # Convert to uppercase
        entity_type=entity.entity_type,
        parent_entity_id=str(entity.parent_entity.ref.id) if entity.parent_entity else None,
        platform_id=str(entity.platform_id) if entity.platform_id else None,
        status=entity.status,
        direct_permissions=entity.direct_permissions,
        config=entity.metadata,  # Use metadata as config
        valid_from=entity.valid_from,
        valid_until=entity.valid_until,
        created_at=entity.created_at,
        updated_at=entity.updated_at
    )


@router.put("/{entity_id}", response_model=EntityResponse)
async def update_entity(
    entity_id: str,
    update_data: EntityUpdate,
    current_user: UserModel = Depends(require_entity_manage)
):
    """
    Update an entity
    
    Requires: entity:manage permission in entity
    """
    
    entity = await EntityService.update_entity(entity_id, update_data, current_user)
    
    return EntityResponse(
        id=str(entity.id),
        name=entity.name,
        display_name=entity.name,  # Use name as display_name
        description=entity.description,
        entity_class=entity.entity_class.value.upper(),  # Convert to uppercase
        entity_type=entity.entity_type,
        parent_entity_id=str(entity.parent_entity.ref.id) if entity.parent_entity else None,
        platform_id=str(entity.platform_id) if entity.platform_id else None,
        status=entity.status,
        direct_permissions=entity.direct_permissions,
        config=entity.metadata,  # Use metadata as config
        valid_from=entity.valid_from,
        valid_until=entity.valid_until,
        created_at=entity.created_at,
        updated_at=entity.updated_at
    )


@router.delete("/{entity_id}")
async def delete_entity(
    entity_id: str,
    cascade: bool = Query(False, description="Delete all child entities"),
    current_user: UserModel = Depends(require_entity_manage)
):
    """
    Delete an entity (soft delete by default)
    
    Requires: entity:manage permission in entity
    """
    
    success = await EntityService.delete_entity(entity_id, current_user, cascade)
    
    return {"message": "Entity deleted successfully", "cascade": cascade}


@router.get("/", response_model=EntityListResponse)
async def search_entities(
    query: Optional[str] = Query(None, description="Search in name, display_name, description"),
    entity_class: Optional[str] = Query(None, description="Filter by entity class"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    parent_entity_id: Optional[str] = Query(None, description="Filter by parent entity"),
    platform_id: Optional[str] = Query(None, description="Filter by platform"),
    include_children: bool = Query(False, description="Include child entities"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: UserModel = Depends(get_current_user)
):
    """
    Search entities with filtering and pagination
    
    Requires: Authenticated user (results filtered by permissions)
    """
    # Build search params
    search_params = EntitySearchParams(
        query=query,
        entity_class=entity_class,
        entity_type=entity_type,
        status=status,
        parent_entity_id=parent_entity_id,
        platform_id=platform_id,
        include_children=include_children,
        page=page,
        page_size=page_size
    )
    
    entities, total = await EntityService.search_entities(search_params, current_user)
    
    # Convert to response models
    items = []
    for entity in entities:
        items.append(EntityResponse(
            id=str(entity.id),
            name=entity.name,
            display_name=entity.name,  # Use name as display_name
            description=entity.description,
            entity_class=entity.entity_class.value.upper(),  # Convert to uppercase
            entity_type=entity.entity_type,
            parent_entity_id=str(entity.parent_entity.ref.id) if entity.parent_entity else None,
            platform_id=str(entity.platform_id) if entity.platform_id else None,
            status=entity.status,
            direct_permissions=entity.direct_permissions,
            config=entity.metadata,  # Use metadata as config
            valid_from=entity.valid_from,
            valid_until=entity.valid_until,
            created_at=entity.created_at,
            updated_at=entity.updated_at
        ))
    
    total_pages = (total + page_size - 1) // page_size
    
    return EntityListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get("/{entity_id}/tree", response_model=dict)
async def get_entity_tree(
    entity_id: str,
    max_depth: int = Query(10, ge=1, le=20),
    current_user: UserModel = Depends(get_current_user)
):
    """
    Get entity with all its children as a tree
    
    Requires: entity:read permission
    """
    # TODO: Check read permissions
    
    tree = await EntityService.get_entity_tree(entity_id, max_depth)
    return tree


@router.get("/{entity_id}/path", response_model=List[EntityResponse])
async def get_entity_path(
    entity_id: str,
    current_user: UserModel = Depends(get_current_user)
):
    """
    Get full path from root to entity
    
    Requires: entity:read permission
    """
    # TODO: Check read permissions
    
    path = await EntityService.get_entity_path(entity_id)
    
    # Convert to response models
    response_path = []
    for entity in path:
        response_path.append(EntityResponse(
            id=str(entity.id),
            name=entity.name,
            display_name=entity.name,  # Use name as display_name
            description=entity.description,
            entity_class=entity.entity_class.value.upper(),  # Convert to uppercase
            entity_type=entity.entity_type,
            parent_entity_id=str(entity.parent_entity.ref.id) if entity.parent_entity else None,
            platform_id=str(entity.platform_id) if entity.platform_id else None,
            status=entity.status,
            direct_permissions=entity.direct_permissions,
            config=entity.metadata,  # Use metadata as config
            valid_from=entity.valid_from,
            valid_until=entity.valid_until,
            created_at=entity.created_at,
            updated_at=entity.updated_at
        ))
    
    return response_path


# Entity Membership Operations

@router.post("/{entity_id}/members", response_model=EntityMemberResponse)
async def add_entity_member(
    entity_id: str,
    member_data: EntityMemberAdd,
    current_user: UserModel = Depends(require_member_manage)
):
    """
    Add a member to an entity
    
    Requires: member:manage permission in entity
    """
    
    membership = await EntityMembershipService.add_member(entity_id, member_data, current_user)
    
    # Fetch related data
    user = await membership.user.fetch()
    entity = await membership.entity.fetch()
    role = await membership.role.fetch()
    
    return EntityMemberResponse(
        id=str(membership.id),
        user_id=str(user.id),
        user_email=user.email,
        user_name=f"{user.profile.first_name} {user.profile.last_name}" if user.profile else user.email,
        entity_id=str(entity.id),
        entity_name=entity.name,
        role_id=str(role.id),
        role_name=role.name,
        permissions=role.permissions,
        status=membership.status,
        valid_from=membership.valid_from,
        valid_until=membership.valid_until,
        created_at=membership.created_at,
        updated_at=membership.updated_at
    )


@router.get("/{entity_id}/members", response_model=dict)
async def list_entity_members(
    entity_id: str,
    include_inactive: bool = Query(False, description="Include inactive members"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: UserModel = Depends(require_member_read)
):
    """
    List all members of an entity
    
    Requires: member:read permission in entity
    """
    
    members, total = await EntityMembershipService.list_entity_members(
        entity_id,
        include_inactive,
        page,
        page_size
    )
    
    total_pages = (total + page_size - 1) // page_size
    
    return {
        "items": members,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }


@router.put("/{entity_id}/members/{user_id}", response_model=EntityMemberResponse)
async def update_entity_member(
    entity_id: str,
    user_id: str,
    update_data: EntityMemberUpdate,
    current_user: UserModel = Depends(require_member_manage)
):
    """
    Update a member's role or status in an entity
    
    Requires: member:manage permission in entity
    """
    
    membership = await EntityMembershipService.update_member(
        entity_id,
        user_id,
        update_data,
        current_user
    )
    
    # Fetch related data
    user = await membership.user.fetch()
    entity = await membership.entity.fetch()
    role = await membership.role.fetch()
    
    return EntityMemberResponse(
        id=str(membership.id),
        user_id=str(user.id),
        user_email=user.email,
        user_name=f"{user.profile.first_name} {user.profile.last_name}" if user.profile else user.email,
        entity_id=str(entity.id),
        entity_name=entity.name,
        role_id=str(role.id),
        role_name=role.name,
        permissions=role.permissions,
        status=membership.status,
        valid_from=membership.valid_from,
        valid_until=membership.valid_until,
        created_at=membership.created_at,
        updated_at=membership.updated_at
    )


@router.delete("/{entity_id}/members/{user_id}")
async def remove_entity_member(
    entity_id: str,
    user_id: str,
    hard_delete: bool = Query(False, description="Permanently delete membership"),
    current_user: UserModel = Depends(require_member_manage)
):
    """
    Remove a member from an entity
    
    Requires: member:manage permission in entity
    """
    
    success = await EntityMembershipService.remove_member(
        entity_id,
        user_id,
        current_user,
        hard_delete
    )
    
    return {"message": "Member removed successfully", "hard_delete": hard_delete}


# User Membership Operations

@router.get("/users/{user_id}/memberships", response_model=dict)
async def list_user_memberships(
    user_id: str,
    include_inactive: bool = Query(False, description="Include inactive memberships"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: UserModel = Depends(require_self_or_permission("user:read"))
):
    """
    List all entity memberships for a user
    
    Requires: user:read permission or self
    """
    
    memberships, total = await EntityMembershipService.list_user_memberships(
        user_id,
        include_inactive,
        page,
        page_size
    )
    
    total_pages = (total + page_size - 1) // page_size
    
    return {
        "items": memberships,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }


# Permission Check

@router.post("/{entity_id}/check-permissions", response_model=EntityPermissionResponse)
async def check_entity_permissions(
    entity_id: str,
    permission_check: EntityPermissionCheck,
    current_user: UserModel = Depends(get_current_user)
):
    """
    Check if current user has specific permissions on entity
    """
    # TODO: Implement with permission service
    # For now, return mock response
    
    permissions_result = {}
    source = {}
    
    for permission in permission_check.permissions:
        # Mock check - user has permission if they're a member
        has_permission = await EntityService.validate_entity_access(
            entity_id,
            current_user,
            permission
        )
        permissions_result[permission] = has_permission
        source[permission] = "membership" if has_permission else "none"
    
    return EntityPermissionResponse(
        entity_id=entity_id,
        permissions=permissions_result,
        source=source
    )