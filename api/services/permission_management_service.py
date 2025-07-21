"""
Permission Management Service
Handles CRUD operations for custom permissions
"""
from typing import List, Optional, Dict, Set
from datetime import datetime, timezone
from beanie import PydanticObjectId
from beanie.operators import And, Or, In
from fastapi import HTTPException, status
import logging

from api.models import PermissionModel, EntityModel, UserModel
from api.models.permission_model import Condition
from api.services.entity_service import EntityService
from api.services.permission_service import permission_service

logger = logging.getLogger(__name__)


class PermissionManagementService:
    """Service for managing custom permissions"""
    
    # System permissions that cannot be modified or deleted
    SYSTEM_PERMISSIONS = {
        # System level
        "system:manage_all", "system:read_all",
        
        # Platform level
        "platform:manage", "platform:manage_platform", "platform:read_platform",
        
        # Entity management - with hierarchical scoping
        "entity:manage_all", "entity:read_all",
        "entity:read", "entity:read_tree",
        "entity:create", "entity:create_tree",
        "entity:update", "entity:update_tree", 
        "entity:delete", "entity:delete_tree",
        
        # User management - with hierarchical scoping
        "user:manage", "user:manage_tree", "user:manage_all",
        "user:manage_client", "user:read", "user:read_tree", "user:read_all",
        "user:create", "user:create_tree", "user:update", "user:update_tree",
        "user:delete", "user:delete_tree", "user:invite", "user:invite_tree",
        
        # Role management - with hierarchical scoping
        "role:manage", "role:manage_tree", "role:manage_all",
        "role:read", "role:read_tree", "role:read_all",
        "role:create", "role:create_tree", "role:update", "role:update_tree",
        "role:delete", "role:delete_tree", "role:assign", "role:assign_tree",
        
        # Member management - with hierarchical scoping
        "member:manage", "member:manage_tree",
        "member:read", "member:read_tree",
        "member:add", "member:add_tree",
        "member:update", "member:update_tree",
        "member:remove", "member:remove_tree",
        
        # Permission management
        "permission:manage", "permission:read", "permission:create", "permission:update", "permission:delete",
        
        # Wildcard permissions
        "*:manage_all", "*:read_all", "*"
    }
    
    @staticmethod
    async def create_permission(
        name: str,
        display_name: str,
        description: Optional[str],
        entity_id: Optional[str],
        created_by: UserModel,
        tags: List[str] = None,
        conditions: List[Condition] = None,
        metadata: Dict = None
    ) -> PermissionModel:
        """
        Create a new custom permission
        
        Args:
            name: Permission identifier (e.g., "lead:create")
            display_name: Human-readable name
            description: Permission description
            entity_id: Entity that owns this permission (None for global)
            created_by: User creating the permission
            tags: Optional tags for categorization
            metadata: Optional metadata
            
        Returns:
            Created permission
            
        Raises:
            HTTPException: If permission already exists or is invalid
        """
        # Check if trying to create a system permission
        if name.lower() in PermissionManagementService.SYSTEM_PERMISSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot create system permission: {name}"
            )
        
        # Check if permission already exists
        existing = await PermissionModel.find_one(
            And(
                PermissionModel.name == name.lower(),
                Or(
                    PermissionModel.entity_id == entity_id,
                    PermissionModel.entity_id == None  # Global permission
                )
            )
        )
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Permission '{name}' already exists"
            )
        
        # Validate entity if provided
        if entity_id:
            entity = await EntityModel.get(entity_id)
            if not entity:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Entity not found"
                )
            
            # Check if user has permission to create permissions in this entity
            can_manage = await permission_service.check_permission(
                str(created_by.id),
                "permission:create",
                entity_id
            )
            if not can_manage[0] and not created_by.is_system_user:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No permission to create permissions in this entity"
                )
        
        # Create permission
        permission = PermissionModel(
            name=name.lower(),
            display_name=display_name,
            description=description,
            entity_id=entity_id,
            created_by=created_by.id,
            tags=tags or [],
            conditions=conditions or [],
            metadata=metadata or {},
            is_system=False
        )
        
        await permission.save()
        logger.info(f"Created permission: {permission.name} by {created_by.email}")
        
        return permission
    
    @staticmethod
    async def get_permission(permission_id: str) -> PermissionModel:
        """
        Get permission by ID
        
        Args:
            permission_id: Permission ID
            
        Returns:
            Permission model
            
        Raises:
            HTTPException: If not found
        """
        permission = await PermissionModel.get(permission_id)
        if not permission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Permission not found"
            )
        return permission
    
    @staticmethod
    async def get_available_permissions(
        entity_id: Optional[str] = None,
        include_system: bool = True,
        include_inherited: bool = True,
        active_only: bool = True
    ) -> List[any]:
        print(f"[PermissionService] get_available_permissions called with:")
        print(f"  - entity_id: {entity_id}")
        print(f"  - include_system: {include_system}")
        print(f"  - include_inherited: {include_inherited}")
        print(f"  - active_only: {active_only}")
        """
        Get all available permissions for an entity
        
        Args:
            entity_id: Entity to get permissions for
            include_system: Include system permissions
            include_inherited: Include permissions from parent entities
            active_only: Only return active permissions
            
        Returns:
            List of available permissions
        """
        permissions = []
        
        # Get system permissions (as virtual PermissionModel objects)
        if include_system:
            for perm_name in PermissionManagementService.SYSTEM_PERMISSIONS:
                # Skip wildcards for regular listings
                if perm_name == "*":
                    continue
                    
                parts = perm_name.split(":")
                resource = parts[0] if parts[0] != "*" else "all"
                action = parts[1] if len(parts) > 1 else "all"
                
                # Create virtual permission object without saving
                # We'll create a dict and convert to response later
                system_perm = {
                    'id': None,
                    'name': perm_name,
                    'display_name': f"{resource.title()} - {action.replace('_', ' ').title()}",
                    'description': f"System permission for {perm_name}",
                    'resource': resource,
                    'action': action,
                    'scope': None,
                    'entity_id': None,
                    'is_system': True,
                    'is_active': True,
                    'tags': [],
                    'conditions': [],
                    'metadata': {},
                    'created_at': None,
                    'updated_at': None,
                    'created_by': None
                }
                permissions.append(system_perm)
        
        # Build query for custom permissions
        query_conditions = []
        
        if active_only:
            query_conditions.append(PermissionModel.is_active == True)
        
        # Get entity and its parents if needed
        entity_ids = []
        if entity_id:
            from bson import ObjectId
            # Convert string ID to ObjectId for query
            try:
                entity_obj_id = ObjectId(entity_id)
                entity_ids.append(entity_obj_id)
            except:
                print(f"[PermissionService] Invalid entity_id format: {entity_id}")
                entity_ids.append(entity_id)  # Fallback to string
            
            if include_inherited:
                # Get parent entities
                entity = await EntityModel.get(entity_id)
                if entity:
                    parent_entities = await EntityService.get_entity_path(entity_id)
                    # Convert parent IDs to ObjectId too
                    for parent in parent_entities:
                        try:
                            entity_ids.append(ObjectId(str(parent.id)))
                        except:
                            entity_ids.append(str(parent.id))
                    print(f"[PermissionService] Entity path for {entity_id}: {[str(e.id) for e in parent_entities]}")
        
        print(f"[PermissionService] Entity IDs to query: {entity_ids}")
        
        # Query for custom permissions
        if entity_ids:
            # When in entity context, only show permissions for that entity (and parents if inherited)
            query_conditions.append(In(PermissionModel.entity_id, entity_ids))
            print(f"[PermissionService] Querying for permissions with entity_id in: {entity_ids}")
        else:
            print(f"[PermissionService] No entity filter - returning all permissions")
        
        if query_conditions:
            custom_permissions = await PermissionModel.find(
                And(*query_conditions)
            ).to_list()
            print(f"[PermissionService] Found {len(custom_permissions)} custom permissions")
            for perm in custom_permissions:
                print(f"  - {perm.name} (entity_id: {perm.entity_id})")
            permissions.extend(custom_permissions)
        
        print(f"[PermissionService] Total permissions to return: {len(permissions)} (system: {len([p for p in permissions if isinstance(p, dict) or p.is_system])}, custom: {len([p for p in permissions if not isinstance(p, dict) and not p.is_system])})")
        
        # Sort by resource and action (handle both dict and model)
        permissions.sort(key=lambda p: (
            p.get('resource', '') if isinstance(p, dict) else p.resource,
            p.get('action', '') if isinstance(p, dict) else p.action
        ))
        
        return permissions
    
    @staticmethod
    async def update_permission(
        permission_id: str,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        is_active: Optional[bool] = None,
        tags: Optional[List[str]] = None,
        conditions: Optional[List[Condition]] = None,
        metadata: Optional[Dict] = None,
        current_user: UserModel = None
    ) -> PermissionModel:
        """
        Update a custom permission
        
        Args:
            permission_id: Permission ID
            display_name: New display name
            description: New description
            is_active: Active status
            tags: New tags
            metadata: New metadata
            current_user: User making the update
            
        Returns:
            Updated permission
            
        Raises:
            HTTPException: If permission not found or is system permission
        """
        permission = await PermissionModel.get(permission_id)
        if not permission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Permission not found"
            )
        
        if permission.is_system:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot modify system permissions"
            )
        
        # Check authorization
        if permission.entity_id and current_user and not current_user.is_system_user:
            can_manage = await permission_service.check_permission(
                str(current_user.id),
                "permission:update",
                str(permission.entity_id)
            )
            if not can_manage[0]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No permission to update permissions in this entity"
                )
        
        # Update fields
        if display_name is not None:
            permission.display_name = display_name
        if description is not None:
            permission.description = description
        if is_active is not None:
            permission.is_active = is_active
        if tags is not None:
            permission.tags = tags
        if conditions is not None:
            permission.conditions = conditions
        if metadata is not None:
            permission.metadata = metadata
        
        permission.updated_at = datetime.now(timezone.utc)
        await permission.save()
        
        logger.info(f"Updated permission: {permission.name}")
        
        return permission
    
    @staticmethod
    async def delete_permission(
        permission_id: str,
        current_user: UserModel
    ) -> bool:
        """
        Delete a custom permission
        
        Args:
            permission_id: Permission ID
            current_user: User performing deletion
            
        Returns:
            True if deleted
            
        Raises:
            HTTPException: If permission not found, is system, or in use
        """
        permission = await PermissionModel.get(permission_id)
        if not permission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Permission not found"
            )
        
        if permission.is_system:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete system permissions"
            )
        
        # Check authorization
        if permission.entity_id and not current_user.is_system_user:
            can_delete = await permission_service.check_permission(
                str(current_user.id),
                "permission:delete",
                str(permission.entity_id)
            )
            if not can_delete[0]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No permission to delete permissions in this entity"
                )
        
        # Check if permission is in use by any roles
        from api.models import RoleModel
        roles_using = await RoleModel.find(
            RoleModel.permissions == permission.name
        ).count()
        
        if roles_using > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete permission. It is used by {roles_using} role(s)"
            )
        
        # Delete permission
        await permission.delete()
        logger.info(f"Deleted permission: {permission.name} by {current_user.email}")
        
        return True
    
    @staticmethod
    async def validate_permissions(
        permissions: List[str],
        entity_id: Optional[str] = None
    ) -> List[str]:
        """
        Validate a list of permission strings
        
        Args:
            permissions: List of permission names to validate
            entity_id: Entity context for validation
            
        Returns:
            List of valid permissions
            
        Raises:
            HTTPException: If any permission is invalid
        """
        # Get all available permissions for the entity
        available = await PermissionManagementService.get_available_permissions(
            entity_id=entity_id,
            include_system=True,
            include_inherited=True,
            active_only=True
        )
        
        available_names = {p['name'] if isinstance(p, dict) else p.name for p in available}
        
        # Add wildcard patterns
        available_names.add("*")
        available_names.update([f"{r}:*" for r in ["user", "entity", "role", "member", "permission"]])
        available_names.update([f"*:{a}" for a in ["read", "create", "update", "delete", "manage"]])
        
        # Validate each permission
        validated = []
        for perm in permissions:
            if perm in available_names:
                validated.append(perm)
            elif ":" in perm and (perm.startswith("*:") or perm.endswith(":*")):
                # Wildcard patterns
                validated.append(perm)
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid permission: {perm}. Permission does not exist or is not available in this context."
                )
        
        return validated


# Global instance
permission_management_service = PermissionManagementService()