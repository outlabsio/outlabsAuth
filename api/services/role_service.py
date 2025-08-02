"""
Role Service
Handles role CRUD operations and permission management
"""
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Tuple
from beanie import PydanticObjectId
from beanie.operators import In, And, Or
from fastapi import HTTPException, status

from api.models import RoleModel, EntityModel, UserModel, EntityMembershipModel, EntityClass
from api.services.permission_service import permission_service


class RoleService:
    """Service for role operations"""
    
    # Predefined permission templates
    PERMISSION_TEMPLATES = {
        "admin": [
            "entity:manage",
            "user:manage",
            "role:manage",
            "member:manage"
        ],
        "manager": [
            "entity:read",
            "entity:update",
            "user:read",
            "user:update",
            "member:manage"
        ],
        "member": [
            "entity:read",
            "user:read",
            "member:read"
        ],
        "viewer": [
            "entity:read",
            "user:read"
        ]
    }
    
    @staticmethod
    async def create_role(
        name: str,
        display_name: str,
        description: Optional[str],
        permissions: List[str],
        entity_id: Optional[str] = None,
        assignable_at_types: Optional[List[str]] = None,
        is_system_role: bool = False,
        is_global: bool = False,
        created_by: Optional[UserModel] = None
    ) -> RoleModel:
        """
        Create a new role
        
        Args:
            name: Role name (unique within entity)
            display_name: Human-readable name
            description: Role description
            permissions: List of permissions
            entity_id: Entity that owns this role
            assignable_at_types: Entity types where role can be assigned
            is_system_role: Whether this is a system role
            is_global: Whether this is a global role
            created_by: User creating the role
        
        Returns:
            Created role
        
        Raises:
            HTTPException: If validation fails
        """
        # Validate entity if provided
        entity = None
        if entity_id:
            entity = await EntityModel.get(entity_id)
            if not entity:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Entity not found"
                )
        
        # Check for duplicate role name within entity
        existing_query = RoleModel.find(RoleModel.name == name)
        if entity:
            existing_query = existing_query.find(RoleModel.entity.id == entity.id)
        else:
            existing_query = existing_query.find(RoleModel.entity == None)
        
        existing_role = await existing_query.first_or_none()
        if existing_role:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Role '{name}' already exists in this scope"
            )
        
        # Validate permissions
        validated_permissions = await RoleService._validate_permissions(permissions, entity_id)
        
        # Create role
        role = RoleModel(
            name=name,
            display_name=display_name,
            description=description,
            permissions=validated_permissions,
            entity=entity,
            assignable_at_types=assignable_at_types or [],
            is_system_role=is_system_role,
            is_global=is_global
        )
        
        await role.save()
        
        # Invalidate permission cache for affected users
        if entity:
            await permission_service.invalidate_entity_cache(str(entity.id))
        
        return role
    
    @staticmethod
    async def get_role(role_id: str) -> RoleModel:
        """
        Get role by ID
        
        Args:
            role_id: Role ID
        
        Returns:
            Role model
        
        Raises:
            HTTPException: If role not found
        """
        role = await RoleModel.get(role_id, fetch_links=True)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found"
            )
        return role
    
    @staticmethod
    async def update_role(
        role_id: str,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        permissions: Optional[List[str]] = None,
        assignable_at_types: Optional[List[str]] = None,
        updated_by: Optional[UserModel] = None
    ) -> RoleModel:
        """
        Update a role
        
        Args:
            role_id: Role ID
            display_name: New display name
            description: New description
            permissions: New permissions
            assignable_at_types: New assignable types
            updated_by: User updating the role
        
        Returns:
            Updated role
        
        Raises:
            HTTPException: If role not found or validation fails
        """
        role = await RoleService.get_role(role_id)
        
        # Prevent modification of system roles
        if role.is_system_role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot modify system roles"
            )
        
        # Update fields
        if display_name is not None:
            role.display_name = display_name
        
        if description is not None:
            role.description = description
        
        if permissions is not None:
            # For global roles, entity_id should be None
            entity_id = None
            if not role.is_global and role.entity:
                if hasattr(role.entity, 'id'):
                    # It's a populated document
                    entity_id = str(role.entity.id)
                elif hasattr(role.entity, 'ref'):
                    # It's a Link object
                    entity_id = str(role.entity.ref.id) if role.entity.ref else None
                else:
                    # It's an ObjectId
                    entity_id = str(role.entity)
            
            validated_permissions = await RoleService._validate_permissions(permissions, entity_id)
            role.permissions = validated_permissions
        
        if assignable_at_types is not None:
            role.assignable_at_types = assignable_at_types
        
        role.updated_at = datetime.now(timezone.utc)
        await role.save()
        
        # Invalidate permission cache for affected users
        if role.entity:
            # Handle Link object properly
            if hasattr(role.entity, 'id'):
                # It's a populated document
                await permission_service.invalidate_entity_cache(str(role.entity.id))
            elif hasattr(role.entity, 'ref'):
                # It's a Link object
                if role.entity.ref:
                    await permission_service.invalidate_entity_cache(str(role.entity.ref.id))
            else:
                # It's an ObjectId
                await permission_service.invalidate_entity_cache(str(role.entity))
        
        return role
    
    @staticmethod
    async def delete_role(role_id: str, deleted_by: Optional[UserModel] = None) -> bool:
        """
        Delete a role
        
        Args:
            role_id: Role ID
            deleted_by: User deleting the role
        
        Returns:
            Success status
        
        Raises:
            HTTPException: If role not found or cannot be deleted
        """
        role = await RoleService.get_role(role_id)
        
        # Prevent deletion of system roles
        if role.is_system_role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete system roles"
            )
        
        # Check if role is in use
        # Since roles is a list of Links, we need to fetch and check manually
        all_memberships = await EntityMembershipModel.find(
            EntityMembershipModel.is_active == True
        ).to_list()
        
        memberships_count = 0
        for membership in all_memberships:
            for member_role in membership.roles:
                # Handle Link object
                if hasattr(member_role, 'ref') and member_role.ref:
                    if str(member_role.ref.id) == str(role.id):
                        memberships_count += 1
                        break
                elif hasattr(member_role, 'id'):
                    if str(member_role.id) == str(role.id):
                        memberships_count += 1
                        break
        
        if memberships_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete role: {memberships_count} active memberships exist"
            )
        
        # Delete role
        await role.delete()
        
        # Invalidate permission cache
        if role.entity:
            # Handle Link object properly
            if hasattr(role.entity, 'id'):
                # It's a populated document
                await permission_service.invalidate_entity_cache(str(role.entity.id))
            elif hasattr(role.entity, 'ref'):
                # It's a Link object
                if role.entity.ref:
                    await permission_service.invalidate_entity_cache(str(role.entity.ref.id))
            else:
                # It's an ObjectId
                await permission_service.invalidate_entity_cache(str(role.entity))
        
        return True
    
    @staticmethod
    async def search_roles(
        entity_id: Optional[str] = None,
        query: Optional[str] = None,
        is_global: Optional[bool] = None,
        assignable_at_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[RoleModel], int]:
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[RoleService] search_roles called with:")
        logger.info(f"  - entity_id: {entity_id}")
        logger.info(f"  - query: {query}")
        logger.info(f"  - is_global: {is_global}")
        logger.info(f"  - assignable_at_type: {assignable_at_type}")
        """
        Search roles with filtering
        
        Args:
            entity_id: Filter by entity
            query: Search in name and description
            is_global: Filter by global status
            assignable_at_type: Filter by assignable type
            page: Page number
            page_size: Items per page
        
        Returns:
            Tuple of (roles, total_count)
        """
        # Build query
        query_conditions = []
        
        if entity_id:
            # When filtering by entity, include:
            # 1. Roles specific to this entity
            # 2. Global roles (always available)
            # 3. TODO: Roles from parent entities (if implementing inheritance)
            entity_conditions = [
                RoleModel.entity.id == PydanticObjectId(entity_id),
                RoleModel.is_global == True
            ]
            
            # TODO: Add parent entity roles if needed
            # For now, just include the current entity and global roles
            
            query_conditions.append(Or(*entity_conditions))
        
        if query:
            query_conditions.append(
                Or(
                    RoleModel.name.regex(f".*{query}.*", "i"),
                    RoleModel.display_name.regex(f".*{query}.*", "i"),
                    RoleModel.description.regex(f".*{query}.*", "i")
                )
            )
        
        if is_global is not None:
            query_conditions.append(RoleModel.is_global == is_global)
        
        if assignable_at_type:
            query_conditions.append(
                In(assignable_at_type, RoleModel.assignable_at_types)
            )
        
        # Execute query
        if query_conditions:
            roles_query = RoleModel.find(And(*query_conditions), fetch_links=True)
        else:
            roles_query = RoleModel.find_all(fetch_links=True)
        
        # Get total count
        total = await roles_query.count()
        
        # Apply pagination
        skip = (page - 1) * page_size
        roles = await roles_query.skip(skip).limit(page_size).to_list()
        
        logger.info(f"[RoleService] Found {len(roles)} roles (total: {total})")
        for role in roles:
            # Handle Link object properly
            entity_id_str = None
            if role.entity:
                if hasattr(role.entity, 'id'):
                    # It's a populated document
                    entity_id_str = str(role.entity.id)
                elif hasattr(role.entity, 'ref'):
                    # It's a Link object
                    if role.entity.ref:
                        entity_id_str = str(role.entity.ref.id)
                else:
                    # It's an ObjectId
                    entity_id_str = str(role.entity)
            logger.info(f"  - {role.name} (entity_id: {entity_id_str}, is_global: {role.is_global})")
        
        return roles, total
    
    @staticmethod
    async def get_assignable_roles(
        entity_id: str,
        entity_type: str
    ) -> List[RoleModel]:
        """
        Get roles that can be assigned at a specific entity type
        
        Args:
            entity_id: Entity ID
            entity_type: Entity type
        
        Returns:
            List of assignable roles
        """
        # Get entity
        entity = await EntityModel.get(entity_id)
        if not entity:
            return []
        
        # Get roles from entity hierarchy
        assignable_roles = []
        
        # Get roles from current entity and parents
        current_entity = entity
        while current_entity:
            # Get roles from current entity
            entity_roles = await RoleModel.find(
                RoleModel.entity.id == current_entity.id,
                Or(
                    RoleModel.assignable_at_types == [],
                    In(entity_type, RoleModel.assignable_at_types)
                )
            ).to_list()
            
            assignable_roles.extend(entity_roles)
            
            # Move to parent entity
            if current_entity.parent_entity:
                current_entity = await current_entity.parent_entity.fetch()
            else:
                break
        
        # Get global roles
        global_roles = await RoleModel.find(
            RoleModel.is_global == True,
            Or(
                RoleModel.assignable_at_types == [],
                In(entity_type, RoleModel.assignable_at_types)
            )
        ).to_list()
        
        assignable_roles.extend(global_roles)
        
        return assignable_roles
    
    @staticmethod
    async def create_default_roles(entity_id: str) -> List[RoleModel]:
        """
        Create default roles for an entity
        
        Args:
            entity_id: Entity ID
        
        Returns:
            List of created roles
        """
        entity = await EntityModel.get(entity_id)
        if not entity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Entity not found"
            )
        
        created_roles = []
        
        # Create roles based on entity class and metadata
        # For structural entities, create standard admin/manager/member roles
        # For access groups, create simplified roles
        
        if entity.entity_class == EntityClass.STRUCTURAL:
            # Use entity's display name for role naming
            entity_label = entity.display_name or entity.name
            roles_to_create = [
                (f"{entity.name}_admin", f"{entity_label} Admin", RoleService.PERMISSION_TEMPLATES["admin"]),
                (f"{entity.name}_manager", f"{entity_label} Manager", RoleService.PERMISSION_TEMPLATES["manager"]),
                (f"{entity.name}_member", f"{entity_label} Member", RoleService.PERMISSION_TEMPLATES["member"])
            ]
        else:  # ACCESS_GROUP
            # Access groups typically have simpler role structures
            entity_label = entity.display_name or entity.name
            roles_to_create = [
                (f"{entity.name}_lead", f"{entity_label} Lead", RoleService.PERMISSION_TEMPLATES["manager"]),
                (f"{entity.name}_member", f"{entity_label} Member", RoleService.PERMISSION_TEMPLATES["member"])
            ]
        
        for name, display_name, permissions in roles_to_create:
            try:
                role = await RoleService.create_role(
                    name=name,
                    display_name=display_name,
                    description=f"Default {display_name} role",
                    permissions=permissions,
                    entity_id=entity_id
                )
                created_roles.append(role)
            except HTTPException:
                # Role might already exist
                pass
        
        return created_roles
    
    @staticmethod
    async def _validate_permissions(permissions: List[str], entity_id: Optional[str] = None) -> List[str]:
        """
        Validate and normalize permissions
        
        Args:
            permissions: List of permission strings
            entity_id: Entity context for validation
        
        Returns:
            Validated permissions
        
        Raises:
            HTTPException: If permissions are invalid
        """
        # Use the new permission management service for validation
        from api.services.permission_management_service import permission_management_service
        
        try:
            validated = await permission_management_service.validate_permissions(
                permissions=permissions,
                entity_id=entity_id
            )
            return validated
        except HTTPException:
            # Re-raise with original error
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Permission validation failed: {str(e)}"
            )