"""
Authentication and permission dependencies
"""
from typing import Optional, List, Callable, Any
from functools import wraps
from fastapi import Depends, HTTPException, status, Path
from api.models import UserModel, EntityModel
from api.routes.auth_routes import get_current_user
from api.services.permission_service import permission_service


def require_permissions(
    permissions: List[str],
    entity_id_param: Optional[str] = None,
    require_all: bool = True
) -> Callable:
    """
    Dependency factory for permission checking
    
    Args:
        permissions: List of required permissions
        entity_id_param: Name of path parameter containing entity ID
        require_all: Whether all permissions are required
    
    Returns:
        Dependency function
    """
    async def permission_dependency(
        current_user: UserModel = Depends(get_current_user),
        entity_id: Optional[str] = None
    ) -> UserModel:
        """
        Check if user has required permissions
        
        Args:
            current_user: Current authenticated user
            entity_id: Entity ID from path parameter
        
        Returns:
            User if authorized
        
        Raises:
            HTTPException: If permission check fails
        """
        # For system users, allow all operations
        if current_user.is_system_user:
            return current_user
        
        # Check permissions
        results = await permission_service.check_multiple_permissions(
            str(current_user.id),
            permissions,
            entity_id,
            require_all
        )
        
        # Check results
        if require_all:
            failed_permissions = [
                perm for perm, (has_perm, _) in results.items() 
                if not has_perm
            ]
            if failed_permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Missing required permissions: {', '.join(failed_permissions)}"
                )
        else:
            # At least one permission required
            if not any(has_perm for has_perm, _ in results.values()):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Missing any of required permissions: {', '.join(permissions)}"
                )
        
        return current_user
    
    # If entity_id_param is specified, inject it
    if entity_id_param:
        async def wrapper(
            current_user: UserModel = Depends(get_current_user),
            entity_id: str = Path(..., alias=entity_id_param)
        ) -> UserModel:
            return await permission_dependency(current_user, entity_id)
        return wrapper
    
    return permission_dependency


def require_permission(permission: str, entity_id_param: Optional[str] = None) -> Callable:
    """
    Dependency factory for single permission checking
    
    Args:
        permission: Required permission
        entity_id_param: Name of path parameter containing entity ID
    
    Returns:
        Dependency function
    """
    return require_permissions([permission], entity_id_param, require_all=True)


def require_any_permission(permissions: List[str], entity_id_param: Optional[str] = None) -> Callable:
    """
    Dependency factory for any permission checking
    
    Args:
        permissions: List of permissions (any one required)
        entity_id_param: Name of path parameter containing entity ID
    
    Returns:
        Dependency function
    """
    return require_permissions(permissions, entity_id_param, require_all=False)


def require_entity_access(permission: str) -> Callable:
    """
    Dependency factory for entity-specific permission checking
    
    Args:
        permission: Required permission
    
    Returns:
        Dependency function that expects entity_id in path
    """
    return require_permission(permission, entity_id_param="entity_id")


def require_self_or_permission(permission: str) -> Callable:
    """
    Dependency factory for self-access or permission checking
    
    Args:
        permission: Required permission for non-self access
    
    Returns:
        Dependency function
    """
    async def self_or_permission_dependency(
        current_user: UserModel = Depends(get_current_user),
        user_id: str = Path(...)
    ) -> UserModel:
        """
        Check if user is accessing their own data or has permission
        
        Args:
            current_user: Current authenticated user
            user_id: User ID from path parameter
        
        Returns:
            User if authorized
        
        Raises:
            HTTPException: If not authorized
        """
        # Allow self-access
        if str(current_user.id) == user_id:
            return current_user
        
        # Check permission for other users
        permission_check = require_permission(permission)
        return await permission_check(current_user)
    
    return self_or_permission_dependency


# Common permission dependencies
require_user_read = require_permission("user:read")
# Removed require_user_manage - routes should check individual permissions
require_entity_read = require_entity_access("entity:read")
require_entity_update = require_entity_access("entity:update")  # Will be replaced below after definition
require_entity_delete = require_entity_access("entity:delete")
require_entity_create = require_permission("entity:create")  # Will be replaced in routes with tree-aware version
require_member_read = require_entity_access("member:read")
# Removed require_member_manage - routes should check individual permissions
require_role_read = require_permission("role:read")
# Removed require_role_manage - routes should check individual permissions


class PermissionChecker:
    """
    Utility class for permission checking in service layer
    """
    
    @staticmethod
    async def check_entity_permission(
        user: UserModel,
        entity_id: str,
        permission: str
    ) -> bool:
        """
        Check if user has permission on entity
        
        Args:
            user: User to check
            entity_id: Entity ID
            permission: Permission to check
        
        Returns:
            True if user has permission
        """
        if user.is_system_user:
            return True
        
        has_perm, _ = await permission_service.check_permission(
            str(user.id),
            permission,
            entity_id
        )
        return has_perm
    
    @staticmethod
    async def check_user_permission(
        user: UserModel,
        permission: str
    ) -> bool:
        """
        Check if user has global permission
        
        Args:
            user: User to check
            permission: Permission to check
        
        Returns:
            True if user has permission
        """
        if user.is_system_user:
            return True
        
        has_perm, _ = await permission_service.check_permission(
            str(user.id),
            permission
        )
        return has_perm
    
    @staticmethod
    async def filter_entities_by_permission(
        user: UserModel,
        entity_ids: List[str],
        permission: str
    ) -> List[str]:
        """
        Filter entity IDs by user permission
        
        Args:
            user: User to check
            entity_ids: List of entity IDs
            permission: Permission to check
        
        Returns:
            Filtered list of entity IDs
        """
        if user.is_system_user:
            return entity_ids
        
        filtered_ids = []
        for entity_id in entity_ids:
            has_perm, _ = await permission_service.check_permission(
                str(user.id),
                permission,
                entity_id
            )
            if has_perm:
                filtered_ids.append(entity_id)
        
        return filtered_ids
    
    @staticmethod
    async def require_entity_permission(
        user: UserModel,
        entity_id: str,
        permission: str
    ) -> None:
        """
        Require entity permission or raise exception
        
        Args:
            user: User to check
            entity_id: Entity ID
            permission: Permission to check
        
        Raises:
            HTTPException: If permission check fails
        """
        if not await PermissionChecker.check_entity_permission(user, entity_id, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {permission}"
            )
    
    @staticmethod
    async def require_user_permission(
        user: UserModel,
        permission: str
    ) -> None:
        """
        Require user permission or raise exception
        
        Args:
            user: User to check
            permission: Permission to check
        
        Raises:
            HTTPException: If permission check fails
        """
        if not await PermissionChecker.check_user_permission(user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {permission}"
            )


# Global permission checker instance
permission_checker = PermissionChecker()


# User permission dependencies
async def require_user_read(current_user: UserModel = Depends(get_current_user)) -> UserModel:
    """Require user:read permission"""
    await PermissionChecker.require_user_permission(current_user, "user:read")
    return current_user


# Removed require_user_manage - use specific permissions instead


async def require_entity_create_with_parent(
    parent_entity_id: Optional[str] = None,
    current_user: UserModel = Depends(get_current_user)
) -> UserModel:
    """
    Check entity:create permission considering parent entity tree permissions.
    
    Allows:
    1. Direct entity:create permission (platform-wide)
    2. entity:create_tree permission in parent entity
    3. entity:create_all permission (system-wide)
    """
    # For system users, allow all operations
    if current_user.is_system_user:
        return current_user
    
    # Check platform-wide entity:create permission first
    has_direct, _ = await permission_service.check_permission(
        str(current_user.id),
        "entity:create"
    )
    
    if has_direct:
        return current_user
    
    # If parent_entity_id is provided, check tree permissions in parent and ancestors
    if parent_entity_id:
        # Get the parent entity's path to check tree permissions in all ancestors
        from api.services.entity_service import EntityService
        try:
            parent_path = await EntityService.get_entity_path(parent_entity_id)
            
            # Check tree permissions in all ancestors (including the parent itself)
            for ancestor in parent_path:
                # Check for entity:create_tree in ancestor
                has_tree_perm, _ = await permission_service.check_permission(
                    str(current_user.id),
                    "entity:create_tree",
                    str(ancestor.id)
                )
                
                if has_tree_perm:
                    return current_user
                
                # No need to check manage_tree since we removed compound permissions
        except Exception as e:
            # If we can't get the parent path, just check the direct parent
            # Check for entity:create_tree in parent
            has_tree_perm, _ = await permission_service.check_permission(
                str(current_user.id),
                "entity:create_tree",
                parent_entity_id
            )
            
            if has_tree_perm:
                return current_user
            
            # No need to check manage_tree since we removed compound permissions
    
    # Check for system-wide permissions
    has_create_all, _ = await permission_service.check_permission(
        str(current_user.id),
        "entity:create_all"
    )
    
    if has_create_all:
        return current_user
    
    # No permission found
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Missing required permission: entity:create or entity:create_tree in parent entity"
    )


def require_entity_update_with_tree(entity_id_param: str = "entity_id") -> Callable:
    """
    Dependency factory for entity update with tree permission checking.
    
    The permission service already handles tree permission checking internally.
    This dependency just needs to check if the user has entity:update permission,
    which will automatically check for entity:update_tree in parent entities.
    """
    async def entity_update_dependency(
        current_user: UserModel = Depends(get_current_user),
        entity_id: str = Path(..., alias=entity_id_param)
    ) -> UserModel:
        # For system users, allow all operations
        if current_user.is_system_user:
            return current_user
        
        # The permission service handles all the logic:
        # 1. Direct entity:update in the entity
        # 2. entity:update_tree in any parent entity  
        # 3. entity:update_all platform-wide
        has_permission, source = await permission_service.check_permission(
            str(current_user.id),
            "entity:update",
            entity_id
        )
        
        # Debug logging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Permission check for entity:update in {entity_id}: {has_permission} (source: {source})")
        
        if has_permission:
            return current_user
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing required permission: entity:update or entity:update_tree in parent entity"
        )
    
    return entity_update_dependency


# Override the common dependency with tree-aware version
require_entity_update = require_entity_update_with_tree()