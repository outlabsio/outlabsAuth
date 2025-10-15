"""
Role Service

Handles role management operations:
- Create roles
- Update roles
- Delete roles
- Assign permissions to roles
- List roles
"""
from typing import Optional, List
from motor.motor_asyncio import AsyncIOMotorDatabase

from outlabs_auth.models.role import RoleModel
from outlabs_auth.models.permission import PermissionModel
from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import (
    RoleNotFoundError,
    InvalidInputError,
)
from outlabs_auth.utils.validation import validate_name, validate_slug


class RoleService:
    """
    Role management service.

    Handles:
    - Role CRUD operations
    - Permission assignment to roles
    - Role listing and search
    - System role protection
    """

    def __init__(
        self,
        database: AsyncIOMotorDatabase,
        config: AuthConfig,
    ):
        """
        Initialize RoleService.

        Args:
            database: MongoDB database instance
            config: Authentication configuration
        """
        self.database = database
        self.config = config

    async def create_role(
        self,
        name: str,
        display_name: str,
        description: Optional[str] = None,
        permissions: Optional[List[str]] = None,
        is_global: bool = True,
        is_system_role: bool = False,
        entity_id: Optional[str] = None,
    ) -> RoleModel:
        """
        Create a new role.

        Args:
            name: Role name (will be used as slug, normalized to lowercase)
            display_name: Human-readable role name
            description: Optional role description
            permissions: List of permission names to assign
            is_global: Whether role can be assigned anywhere (SimpleRBAC default: True)
            is_system_role: Whether this is a system role (cannot be modified)
            entity_id: Optional entity ID to scope role to (EnterpriseRBAC only)

        Returns:
            RoleModel: Created role

        Raises:
            InvalidInputError: If role name already exists or is invalid
            EntityNotFoundError: If entity_id provided but entity not found

        Example:
            >>> role = await role_service.create_role(
            ...     name="admin",
            ...     display_name="Administrator",
            ...     permissions=["user:create", "user:delete"]
            ... )
            >>> role.name
            'admin'
        """
        # Validate and normalize name
        name = validate_slug(name, "name")
        display_name = validate_name(display_name, "display_name")

        # Check if role already exists
        existing_role = await RoleModel.find_one(RoleModel.name == name)
        if existing_role:
            raise InvalidInputError(
                message=f"Role with name '{name}' already exists",
                details={"name": name}
            )

        # Fetch entity if entity_id provided (EnterpriseRBAC)
        entity = None
        if entity_id:
            from outlabs_auth.models.entity import EntityModel
            from outlabs_auth.core.exceptions import EntityNotFoundError

            entity = await EntityModel.get(entity_id)
            if not entity:
                raise EntityNotFoundError(
                    message="Entity not found",
                    details={"entity_id": entity_id}
                )

        # Create role
        role = RoleModel(
            name=name,
            display_name=display_name,
            description=description,
            permissions=permissions or [],
            is_global=is_global,
            is_system_role=is_system_role,
            entity=entity,
        )

        await role.save()
        return role

    async def get_role_by_id(self, role_id: str) -> Optional[RoleModel]:
        """
        Get role by ID.

        Args:
            role_id: Role ID

        Returns:
            Optional[RoleModel]: Role if found, None otherwise

        Example:
            >>> role = await role_service.get_role_by_id("507f1f77bcf86cd799439011")
            >>> role.name if role else None
            'admin'
        """
        return await RoleModel.get(role_id)

    async def get_role_by_name(self, name: str) -> Optional[RoleModel]:
        """
        Get role by name.

        Args:
            name: Role name

        Returns:
            Optional[RoleModel]: Role if found, None otherwise

        Example:
            >>> role = await role_service.get_role_by_name("admin")
            >>> role.display_name if role else None
            'Administrator'
        """
        name = validate_slug(name, "name")
        return await RoleModel.find_one(RoleModel.name == name)

    async def update_role(
        self,
        role_id: str,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        permissions: Optional[List[str]] = None,
    ) -> RoleModel:
        """
        Update role.

        Note: Cannot update system roles.

        Args:
            role_id: Role ID
            display_name: Updated display name
            description: Updated description
            permissions: Updated permission list (replaces existing)

        Returns:
            RoleModel: Updated role

        Raises:
            RoleNotFoundError: If role doesn't exist
            InvalidInputError: If trying to modify system role

        Example:
            >>> role = await role_service.update_role(
            ...     role_id="507f1f77bcf86cd799439011",
            ...     permissions=["user:create", "user:read", "user:update"]
            ... )
            >>> len(role.permissions)
            3
        """
        role = await RoleModel.get(role_id)
        if not role:
            raise RoleNotFoundError(
                message="Role not found",
                details={"role_id": role_id}
            )

        # Protect system roles
        if role.is_system_role:
            raise InvalidInputError(
                message="Cannot modify system role",
                details={"role_id": role_id, "role_name": role.name}
            )

        # Update fields
        if display_name is not None:
            role.display_name = validate_name(display_name, "display_name")

        if description is not None:
            role.description = description

        if permissions is not None:
            role.permissions = permissions

        await role.save()
        return role

    async def add_permissions(
        self,
        role_id: str,
        permissions: List[str],
    ) -> RoleModel:
        """
        Add permissions to role (without removing existing).

        Args:
            role_id: Role ID
            permissions: Permission names to add

        Returns:
            RoleModel: Updated role

        Raises:
            RoleNotFoundError: If role doesn't exist
            InvalidInputError: If trying to modify system role

        Example:
            >>> role = await role_service.add_permissions(
            ...     role_id="507f1f77bcf86cd799439011",
            ...     permissions=["user:delete"]
            ... )
        """
        role = await RoleModel.get(role_id)
        if not role:
            raise RoleNotFoundError(
                message="Role not found",
                details={"role_id": role_id}
            )

        # Protect system roles
        if role.is_system_role:
            raise InvalidInputError(
                message="Cannot modify system role",
                details={"role_id": role_id, "role_name": role.name}
            )

        # Add permissions (avoid duplicates)
        existing_permissions = set(role.permissions)
        for perm in permissions:
            existing_permissions.add(perm)

        role.permissions = list(existing_permissions)
        await role.save()
        return role

    async def remove_permissions(
        self,
        role_id: str,
        permissions: List[str],
    ) -> RoleModel:
        """
        Remove permissions from role.

        Args:
            role_id: Role ID
            permissions: Permission names to remove

        Returns:
            RoleModel: Updated role

        Raises:
            RoleNotFoundError: If role doesn't exist
            InvalidInputError: If trying to modify system role

        Example:
            >>> role = await role_service.remove_permissions(
            ...     role_id="507f1f77bcf86cd799439011",
            ...     permissions=["user:delete"]
            ... )
        """
        role = await RoleModel.get(role_id)
        if not role:
            raise RoleNotFoundError(
                message="Role not found",
                details={"role_id": role_id}
            )

        # Protect system roles
        if role.is_system_role:
            raise InvalidInputError(
                message="Cannot modify system role",
                details={"role_id": role_id, "role_name": role.name}
            )

        # Remove permissions
        permissions_to_remove = set(permissions)
        role.permissions = [p for p in role.permissions if p not in permissions_to_remove]

        await role.save()
        return role

    async def delete_role(self, role_id: str) -> bool:
        """
        Delete role.

        Note: Cannot delete system roles.

        Args:
            role_id: Role ID

        Returns:
            bool: True if deleted, False if not found

        Raises:
            InvalidInputError: If trying to delete system role

        Example:
            >>> deleted = await role_service.delete_role("507f1f77bcf86cd799439011")
            >>> deleted
            True
        """
        role = await RoleModel.get(role_id)
        if not role:
            return False

        # Protect system roles
        if role.is_system_role:
            raise InvalidInputError(
                message="Cannot delete system role",
                details={"role_id": role_id, "role_name": role.name}
            )

        await role.delete()
        return True

    async def list_roles(
        self,
        page: int = 1,
        limit: int = 20,
        is_global: Optional[bool] = None,
    ) -> tuple[List[RoleModel], int]:
        """
        List roles with pagination.

        Args:
            page: Page number (1-indexed)
            limit: Results per page
            is_global: Filter by global flag

        Returns:
            tuple[List[RoleModel], int]: (roles, total_count)

        Example:
            >>> roles, total = await role_service.list_roles(page=1, limit=10)
            >>> len(roles)
            10
            >>> total
            25
        """
        # Build query
        query = {}
        if is_global is not None:
            query["is_global"] = is_global

        # Get total count
        total_count = await RoleModel.find(query).count()

        # Get paginated results
        skip = (page - 1) * limit
        roles = await RoleModel.find(query).skip(skip).limit(limit).to_list()

        return roles, total_count

    async def get_role_permissions(self, role_id: str) -> List[str]:
        """
        Get all permissions for a role.

        Args:
            role_id: Role ID

        Returns:
            List[str]: Permission names

        Raises:
            RoleNotFoundError: If role doesn't exist

        Example:
            >>> permissions = await role_service.get_role_permissions("507f...")
            >>> permissions
            ['user:create', 'user:read', 'user:update']
        """
        role = await RoleModel.get(role_id)
        if not role:
            raise RoleNotFoundError(
                message="Role not found",
                details={"role_id": role_id}
            )

        return role.permissions
