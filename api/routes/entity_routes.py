"""
Entity routes
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from api.models import UserModel, RoleModel
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
    require_entity_update,
    require_entity_delete,
    require_member_read,
    require_entity_access,
    require_self_or_permission,
    get_current_user,
    require_entity_create_with_parent
)

router = APIRouter()


# Entity Type Suggestions

@router.get("/entity-types", response_model=dict)
async def get_entity_types(
    platform_id: Optional[str] = Query(None, description="Filter by platform"),
    entity_class: Optional[str] = Query(None, description="Filter by entity class"),
    current_user: UserModel = Depends(get_current_user)
):
    """
    Get distinct entity types with usage counts
    
    Returns list of entity types that have been used in the system,
    sorted by usage frequency and recency.
    
    Requires: Authenticated user
    """
    # For non-system users, always filter by their platform
    if not current_user.is_system_user and platform_id is None:
        # Get user's primary platform from their memberships
        # For now, we'll require platform_id to be specified
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="platform_id is required for non-system users"
        )
    
    entity_types = await EntityService.get_distinct_entity_types(
        platform_id=platform_id,
        entity_class=entity_class
    )
    
    # Add predefined suggestions based on entity class
    predefined_suggestions = []
    if not entity_class or entity_class.upper() == "STRUCTURAL":
        predefined_suggestions = [
            {"entity_type": "platform", "count": 0, "is_predefined": True},
            {"entity_type": "organization", "count": 0, "is_predefined": True},
            {"entity_type": "division", "count": 0, "is_predefined": True},
            {"entity_type": "department", "count": 0, "is_predefined": True},
            {"entity_type": "branch", "count": 0, "is_predefined": True},
            {"entity_type": "team", "count": 0, "is_predefined": True},
            {"entity_type": "region", "count": 0, "is_predefined": True},
            {"entity_type": "sector", "count": 0, "is_predefined": True},
            {"entity_type": "office", "count": 0, "is_predefined": True},
            {"entity_type": "unit", "count": 0, "is_predefined": True}
        ]
    elif entity_class and entity_class.upper() == "ACCESS_GROUP":
        predefined_suggestions = [
            {"entity_type": "functional_group", "count": 0, "is_predefined": True},
            {"entity_type": "permission_group", "count": 0, "is_predefined": True},
            {"entity_type": "project_group", "count": 0, "is_predefined": True},
            {"entity_type": "role_group", "count": 0, "is_predefined": True},
            {"entity_type": "access_group", "count": 0, "is_predefined": True},
            {"entity_type": "workgroup", "count": 0, "is_predefined": True},
            {"entity_type": "committee", "count": 0, "is_predefined": True},
            {"entity_type": "task_force", "count": 0, "is_predefined": True}
        ]
    
    # Merge predefined with actual usage, keeping actual counts where they exist
    existing_types = {et["entity_type"]: et for et in entity_types}
    merged_suggestions = []
    
    # Add predefined suggestions with actual counts if they exist
    for suggestion in predefined_suggestions:
        if suggestion["entity_type"] in existing_types:
            merged_suggestions.append(existing_types[suggestion["entity_type"]])
        else:
            merged_suggestions.append(suggestion)
    
    # Add any custom types that aren't in predefined
    predefined_names = {s["entity_type"] for s in predefined_suggestions}
    for entity_type in entity_types:
        if entity_type["entity_type"] not in predefined_names:
            merged_suggestions.append(entity_type)
    
    return {
        "suggestions": merged_suggestions,
        "total": len(merged_suggestions)
    }


# Entity CRUD Operations

@router.post("/", response_model=EntityResponse)
async def create_entity(
    entity_data: EntityCreate,
    current_user: UserModel = Depends(get_current_user)
):
    """
    Create a new entity
    
    Requires one of:
    - entity:create permission (platform-wide)
    - entity:create_tree permission in parent entity
    - entity:create_all permission (system-wide)
    """
    # Check permissions with parent entity context
    await require_entity_create_with_parent(
        parent_entity_id=entity_data.parent_entity_id,
        current_user=current_user
    )
    
    entity = await EntityService.create_entity(entity_data, current_user)
    
    return EntityResponse(
        id=str(entity.id),
        name=entity.name,
        display_name=entity.display_name,
        description=entity.description,
        entity_class=entity.entity_class.upper(),  # Convert to uppercase
        entity_type=entity.entity_type,
        parent_entity_id=str(entity.parent_entity.id) if entity.parent_entity else None,
        platform_id=str(entity.platform_id) if entity.platform_id else None,
        status=entity.status,
        direct_permissions=entity.direct_permissions,
        config=entity.metadata,  # Use metadata as config
        valid_from=entity.valid_from,
        valid_until=entity.valid_until,
        created_at=entity.created_at,
        updated_at=entity.updated_at
    )


@router.get("/top-level-organizations", response_model=EntityListResponse)
async def get_top_level_organizations(
    status: Optional[str] = Query("active", description="Filter by status"),
    current_user: UserModel = Depends(get_current_user)
):
    """
    Get all top-level organizations (root entities with type ORGANIZATION or PLATFORM)
    
    This is specifically for the context selector dropdown.
    Returns organizations where the current user has membership or all if platform admin.
    
    Requires: Authenticated user
    """
    # For top-level entities, we want both platforms and organizations with no parent
    # Don't filter by entity_type - we'll filter after
    search_params = EntitySearchParams(
        parent_entity_id="null",  # Special value to search for entities with no parent
        status=status,
        include_children=False,
        page=1,
        page_size=100  # Assuming max 100 top-level orgs
    )
    
    entities, total = await EntityService.search_entities(search_params)
    
    # Convert to response models
    items = []
    for entity in entities:
        # Filter to only organizations and platforms
        if entity.entity_type not in ["organization", "platform"]:
            continue
            
        # Check if user should see this entity
        # System users (platform admins) see all top-level entities
        if current_user.is_system_user:
            include_entity = True
        else:
            # Regular users only see entities they have membership in
            membership = await EntityMembershipService.get_user_membership_in_entity(
                str(current_user.id),
                str(entity.id)
            )
            include_entity = bool(membership)
        
        if include_entity:
            items.append(EntityResponse(
                id=str(entity.id),
                name=entity.name,
                display_name=entity.display_name,
                description=entity.description,
                entity_class=entity.entity_class.upper(),  # Convert to uppercase string
                entity_type=entity.entity_type,
                platform_id=str(entity.platform_id) if entity.platform_id else None,
                parent_entity_id=str(entity.parent_entity.id) if entity.parent_entity and hasattr(entity.parent_entity, 'id') else None,
                status=entity.status,
                direct_permissions=entity.direct_permissions,
                config=entity.metadata,  # Use metadata as config
                valid_from=entity.valid_from,
                valid_until=entity.valid_until,
                created_at=entity.created_at,
                updated_at=entity.updated_at
            ))
    
    return EntityListResponse(
        items=items,
        total=len(items),
        page=1,
        page_size=100,
        total_pages=1
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
        display_name=entity.display_name,
        description=entity.description,
        entity_class=entity.entity_class.upper(),  # Convert to uppercase
        entity_type=entity.entity_type,
        parent_entity_id=str(entity.parent_entity.id) if entity.parent_entity else None,
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
    current_user: UserModel = Depends(require_entity_update)
):
    """
    Update an entity
    
    Requires: entity:update permission in entity
    """
    
    entity = await EntityService.update_entity(entity_id, update_data, current_user)
    
    return EntityResponse(
        id=str(entity.id),
        name=entity.name,
        display_name=entity.display_name,
        description=entity.description,
        entity_class=entity.entity_class.upper(),  # Convert to uppercase
        entity_type=entity.entity_type,
        parent_entity_id=str(entity.parent_entity.id) if entity.parent_entity else None,
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
    current_user: UserModel = Depends(require_entity_delete)
):
    """
    Delete an entity (soft delete by default)
    
    Requires: entity:delete permission in entity
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
    
    entities, total = await EntityService.search_entities(search_params)
    
    # Filter entities based on user permissions
    # System users see all entities
    if not current_user.is_system_user:
        try:
            # Get entities user can see (includes tree permissions)
            visible_entity_ids = await EntityService.get_user_visible_entities(
                str(current_user.id),
                include_tree_permissions=True
            )
            
            # Filter entities to only those the user can access
            filtered_entities = []
            for entity in entities:
                if entity.id in visible_entity_ids:
                    filtered_entities.append(entity)
            
            # If we need to include all visible entities (not just from search results)
            # we should query them separately
            if not search_params.query and not filtered_entities:
                # Get all visible entities for the user
                visible_entities = await EntityModel.find(
                    {"_id": {"$in": list(visible_entity_ids)}}
                ).to_list()
                filtered_entities = visible_entities
            
            entities = filtered_entities
            # Update total count after filtering
            total = len(entities)
            
            # Apply pagination to filtered results
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            entities = entities[start_idx:end_idx]
        except Exception as e:
            # Log the error and raise a proper HTTP exception
            import traceback
            error_detail = f"Error in entity filtering: {str(e)}\n{traceback.format_exc()}"
            print(error_detail)
            # Re-raise to see the actual error
            raise
    
    # Convert to response models
    items = []
    for entity in entities:
        items.append(EntityResponse(
            id=str(entity.id),
            name=entity.name,
            display_name=entity.display_name,
            description=entity.description,
            entity_class=entity.entity_class.upper(),  # Convert to uppercase
            entity_type=entity.entity_type,
            parent_entity_id=str(entity.parent_entity.id) if entity.parent_entity and hasattr(entity.parent_entity, 'id') else None,
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
            display_name=entity.display_name,
            description=entity.description,
            entity_class=entity.entity_class.upper(),  # Convert to uppercase
            entity_type=entity.entity_type,
            parent_entity_id=str(entity.parent_entity.id) if entity.parent_entity and hasattr(entity.parent_entity, 'id') else None,
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


# Entity Roles Operations

@router.get("/{entity_id}/roles", response_model=dict)
async def list_entity_roles(
    entity_id: str,
    current_user: UserModel = Depends(require_entity_read)
):
    """
    List all roles available for an entity
    
    Requires: entity:read permission
    """
    # For now, return default roles that can be assigned
    # In a full implementation, this would fetch entity-specific roles
    roles = await RoleModel.find(
        RoleModel.entity.id == entity_id,
        fetch_links=True
    ).to_list()
    
    # If no entity-specific roles, return some default roles
    if not roles:
        # Create default role structures
        default_roles = [
            {
                "id": "default-admin",
                "name": "Admin",
                "description": "Full administrative access to this entity",
                "permissions": ["*:manage"]
            },
            {
                "id": "default-member",
                "name": "Member",
                "description": "Standard member access",
                "permissions": ["*:read"]
            },
            {
                "id": "default-viewer",
                "name": "Viewer",
                "description": "Read-only access",
                "permissions": ["*:read"]
            }
        ]
        return {"items": default_roles}
    
    # Convert to response format
    items = []
    for role in roles:
        items.append({
            "id": str(role.id),
            "name": role.name,
            "description": role.description,
            "permissions": role.permissions
        })
    
    return {"items": items}


# Entity Membership Operations

@router.post("/{entity_id}/members", response_model=EntityMemberResponse)
async def add_entity_member(
    entity_id: str,
    member_data: EntityMemberAdd,
    current_user: UserModel = Depends(require_entity_access("member:create"))
):
    """
    Add a member to an entity
    
    Requires: member:create permission in entity
    """
    
    membership = await EntityMembershipService.add_member(entity_id, member_data, current_user)
    
    # Fetch related data if needed
    if hasattr(membership.user, 'fetch'):
        user = await membership.user.fetch()
    else:
        user = membership.user
        
    if hasattr(membership.entity, 'fetch'):
        entity = await membership.entity.fetch()
    else:
        entity = membership.entity
    
    # Get first role for now (TODO: support multiple roles in response)
    roles = []
    for role_link in membership.roles:
        if hasattr(role_link, 'fetch'):
            role = await role_link.fetch()
        else:
            role = role_link
        roles.append(role)
    
    first_role = roles[0] if roles else None
    
    return EntityMemberResponse(
        id=str(membership.id),
        user_id=str(user.id),
        user_email=user.email,
        user_name=f"{user.profile.first_name} {user.profile.last_name}" if user.profile else user.email,
        entity_id=str(entity.id),
        entity_name=entity.display_name,
        entity_system_name=entity.name,
        role_id=str(first_role.id) if first_role else "",
        role_name=first_role.name if first_role else "No Role",
        permissions=first_role.permissions if first_role else [],
        is_active=membership.is_active,
        status="active" if membership.is_active else "inactive",
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
    current_user: UserModel = Depends(require_entity_access("member:update"))
):
    """
    Update a member's role or status in an entity
    
    Requires: member:update permission in entity
    """
    
    membership = await EntityMembershipService.update_member(
        entity_id,
        user_id,
        update_data,
        current_user
    )
    
    # Fetch related data if needed
    if hasattr(membership.user, 'fetch'):
        user = await membership.user.fetch()
    else:
        user = membership.user
        
    if hasattr(membership.entity, 'fetch'):
        entity = await membership.entity.fetch()
    else:
        entity = membership.entity
    
    # Get first role for now (TODO: support multiple roles in response)
    roles = []
    for role_link in membership.roles:
        if hasattr(role_link, 'fetch'):
            role = await role_link.fetch()
        else:
            role = role_link
        roles.append(role)
    
    first_role = roles[0] if roles else None
    
    return EntityMemberResponse(
        id=str(membership.id),
        user_id=str(user.id),
        user_email=user.email,
        user_name=f"{user.profile.first_name} {user.profile.last_name}" if user.profile else user.email,
        entity_id=str(entity.id),
        entity_name=entity.display_name,
        entity_system_name=entity.name,
        role_id=str(first_role.id) if first_role else "",
        role_name=first_role.name if first_role else "No Role",
        permissions=first_role.permissions if first_role else [],
        is_active=membership.is_active,
        status="active" if membership.is_active else "inactive",
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
    current_user: UserModel = Depends(require_entity_access("member:delete"))
):
    """
    Remove a member from an entity
    
    Requires: member:delete permission in entity
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