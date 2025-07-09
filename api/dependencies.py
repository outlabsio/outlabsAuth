"""
Authentication and permission dependencies
"""
from typing import Optional, List, Callable, Any
from functools import wraps
from fastapi import Depends, HTTPException, status, Path
from api.models import UserModel
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
    def permission_dependency(
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
        import asyncio
        
        # Create async wrapper for permission check
        async def check_perms():
            return await permission_service.check_multiple_permissions(
                str(current_user.id),
                permissions,
                entity_id,
                require_all
            )
        
        # Run permission check
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're already in an async context, create a task
            import asyncio
            task = asyncio.create_task(check_perms())
            try:
                results = loop.run_until_complete(task)
            except RuntimeError:
                # Fallback for nested event loops
                import nest_asyncio
                nest_asyncio.apply()
                results = loop.run_until_complete(task)
        else:
            results = loop.run_until_complete(check_perms())
        
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
        def wrapper(
            current_user: UserModel = Depends(get_current_user),
            entity_id: str = Path(..., alias=entity_id_param)
        ) -> UserModel:
            return permission_dependency(current_user, entity_id)
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
    def self_or_permission_dependency(
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
        return permission_check(current_user)
    
    return self_or_permission_dependency


# Common permission dependencies
require_user_read = require_permission("user:read")
require_user_manage = require_permission("user:manage")
require_entity_read = require_entity_access("entity:read")
require_entity_manage = require_entity_access("entity:manage")
require_entity_create = require_permission("entity:create")
require_member_read = require_entity_access("member:read")
require_member_manage = require_entity_access("member:manage")
require_role_read = require_permission("role:read")
require_role_manage = require_permission("role:manage")


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