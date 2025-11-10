"""
Role Service

Handles role management operations:
- Create roles
- Update roles
- Delete roles
- Assign permissions to roles
- List roles
- Assign roles to users (SimpleRBAC via UserRoleMembership)
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import (
    InvalidInputError,
    RoleNotFoundError,
)
from outlabs_auth.models.permission import PermissionModel
from outlabs_auth.models.role import RoleModel
from outlabs_auth.utils.validation import validate_name, validate_slug

if TYPE_CHECKING:
    from outlabs_auth.models.user_role_membership import UserRoleMembership


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
                details={"name": name},
            )

        # Fetch entity if entity_id provided (EnterpriseRBAC)
        entity = None
        if entity_id:
            from outlabs_auth.core.exceptions import EntityNotFoundError
            from outlabs_auth.models.entity import EntityModel

            entity = await EntityModel.get(entity_id)
            if not entity:
                raise EntityNotFoundError(
                    message="Entity not found", details={"entity_id": entity_id}
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

    async def update_role(self, role_id: str, update_dict: Dict[str, Any]) -> RoleModel:
        """
        Update role with fields from update_dict.

        Note: Cannot update system roles.

        Args:
            role_id: Role ID
            update_dict: Dictionary of fields to update (supports display_name, description, permissions)

        Returns:
            RoleModel: Updated role

        Raises:
            RoleNotFoundError: If role doesn't exist
            InvalidInputError: If trying to modify system role

        Example:
            >>> role = await role_service.update_role(
            ...     role_id="507f1f77bcf86cd799439011",
            ...     update_dict={"permissions": ["user:create", "user:read", "user:update"]}
            ... )
            >>> len(role.permissions)
            3
        """
        role = await RoleModel.get(role_id)
        if not role:
            raise RoleNotFoundError(
                message="Role not found", details={"role_id": role_id}
            )

        # Protect system roles
        if role.is_system_role:
            raise InvalidInputError(
                message="Cannot modify system role",
                details={"role_id": role_id, "role_name": role.name},
            )

        # Update fields from dict (only supported fields for SimpleRBAC)
        if "display_name" in update_dict:
            role.display_name = validate_name(
                update_dict["display_name"], "display_name"
            )

        if "description" in update_dict:
            role.description = update_dict["description"]

        if "permissions" in update_dict:
            role.permissions = update_dict["permissions"]

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
                message="Role not found", details={"role_id": role_id}
            )

        # Protect system roles
        if role.is_system_role:
            raise InvalidInputError(
                message="Cannot modify system role",
                details={"role_id": role_id, "role_name": role.name},
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
                message="Role not found", details={"role_id": role_id}
            )

        # Protect system roles
        if role.is_system_role:
            raise InvalidInputError(
                message="Cannot modify system role",
                details={"role_id": role_id, "role_name": role.name},
            )

        # Remove permissions
        permissions_to_remove = set(permissions)
        role.permissions = [
            p for p in role.permissions if p not in permissions_to_remove
        ]

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
                details={"role_id": role_id, "role_name": role.name},
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
                message="Role not found", details={"role_id": role_id}
            )

        return role.permissions

    # -------------------------------------------------------------------------
    # UserRoleMembership Methods (SimpleRBAC)
    # -------------------------------------------------------------------------

    async def assign_role_to_user(
        self,
        user_id: str,
        role_id: str,
        assigned_by: Optional[str] = None,
        valid_from: Optional["datetime"] = None,
        valid_until: Optional["datetime"] = None,
    ) -> "UserRoleMembership":
        """
        Assign role to user (SimpleRBAC only).

        Creates a UserRoleMembership record linking user to role with full audit trail.

        Args:
            user_id: User ID to assign role to
            role_id: Role ID to assign
            assigned_by: Optional user ID who performed the assignment (for audit)
            valid_from: Optional start date for role validity
            valid_until: Optional end date for role validity (e.g., 90-day contractor)

        Returns:
            UserRoleMembership: Created membership record

        Raises:
            UserNotFoundError: If user doesn't exist
            RoleNotFoundError: If role doesn't exist
            InvalidInputError: If membership already exists

        Example:
            >>> membership = await role_service.assign_role_to_user(
            ...     user_id="507f...",
            ...     role_id="507f...",
            ...     assigned_by=admin_user.id,
            ...     valid_until=datetime.now(timezone.utc) + timedelta(days=90)
            ... )
            >>> membership.status
            MembershipStatus.ACTIVE
        """
        from outlabs_auth.core.exceptions import UserNotFoundError
        from outlabs_auth.models.user import UserModel
        from outlabs_auth.models.user_role_membership import UserRoleMembership

        # Validate user exists
        user = await UserModel.get(user_id)
        if not user:
            raise UserNotFoundError(
                message="User not found", details={"user_id": user_id}
            )

        # Validate role exists
        role = await RoleModel.get(role_id)
        if not role:
            raise RoleNotFoundError(
                message="Role not found", details={"role_id": role_id}
            )

        # Check if membership already exists
        from outlabs_auth.models.membership_status import MembershipStatus as MStatus

        existing_membership = await UserRoleMembership.find_one(
            {"user.$id": user_id, "role.$id": role_id, "status": MStatus.ACTIVE.value}
        )
        if existing_membership:
            raise InvalidInputError(
                message="User already has this role assigned",
                details={"user_id": user_id, "role_id": role_id},
            )

        # Create membership
        assigned_by_user = None
        if assigned_by:
            assigned_by_user = await UserModel.get(assigned_by)

        membership = UserRoleMembership(
            user=user,
            role=role,
            assigned_by=assigned_by_user,
            valid_from=valid_from,
            valid_until=valid_until,
            status=MStatus.ACTIVE,
        )

        await membership.save()
        return membership

    async def revoke_role_from_user(
        self,
        user_id: str,
        role_id: str,
        revoked_by: Optional[str] = None,
    ) -> bool:
        """
        Revoke role from user (SimpleRBAC only).

        Changes membership status to REVOKED (soft delete for audit trail).

        Args:
            user_id: User ID to revoke role from
            role_id: Role ID to revoke
            revoked_by: Optional user ID who performed the revocation (for audit)

        Returns:
            bool: True if role was revoked, False if no active membership found

        Example:
            >>> revoked = await role_service.revoke_role_from_user(
            ...     user_id="507f...",
            ...     role_id="507f...",
            ...     revoked_by=admin_user.id
            ... )
            >>> revoked
            True
        """
        from datetime import datetime, timezone

        from beanie import PydanticObjectId

        from outlabs_auth.models.membership_status import MembershipStatus as MStatus
        from outlabs_auth.models.user import UserModel
        from outlabs_auth.models.user_role_membership import UserRoleMembership

        # Find active membership (convert string IDs to ObjectId for Link query)
        user_obj_id = PydanticObjectId(user_id)
        role_obj_id = PydanticObjectId(role_id)
        membership = await UserRoleMembership.find_one(
            {
                "user.$id": user_obj_id,
                "role.$id": role_obj_id,
                "status": MStatus.ACTIVE.value,
            }
        )

        if not membership:
            return False

        # Update to revoked status with audit trail
        membership.status = MStatus.REVOKED
        membership.revoked_at = datetime.now(timezone.utc)

        if revoked_by:
            revoked_by_user = await UserModel.get(revoked_by)
            if revoked_by_user:
                membership.revoked_by = revoked_by_user

        await membership.save()
        return True

    async def get_user_roles(
        self,
        user_id: str,
        include_inactive: bool = False,
    ) -> List[RoleModel]:
        """
        Get all roles assigned to a user (SimpleRBAC only).

        Queries UserRoleMembership to find all roles assigned to the user.

        Args:
            user_id: User ID
            include_inactive: Whether to include inactive memberships (default: False)

        Returns:
            List[RoleModel]: List of roles assigned to user (empty if none)

        Example:
            >>> roles = await role_service.get_user_roles("507f...")
            >>> [role.name for role in roles]
            ['admin', 'editor']
        """
        from beanie import PydanticObjectId

        from outlabs_auth.models.membership_status import MembershipStatus as MStatus
        from outlabs_auth.models.user_role_membership import UserRoleMembership

        # Build query (convert user_id string to PydanticObjectId for Link query)
        user_obj_id = PydanticObjectId(user_id)
        if include_inactive:
            query = {"user.$id": user_obj_id}
        else:
            query = {"user.$id": user_obj_id, "status": MStatus.ACTIVE.value}

        # Find all memberships
        memberships = await UserRoleMembership.find(query).to_list()

        # Extract roles (with validity check)
        roles = []
        for membership in memberships:
            # Check time-based validity
            if membership.is_currently_valid():
                role = await membership.role.fetch()
                if role:
                    roles.append(role)

        return roles

    async def get_user_memberships(
        self,
        user_id: str,
        include_inactive: bool = False,
    ) -> List["UserRoleMembership"]:
        """
        Get all role memberships for a user (SimpleRBAC only).

        Returns full membership records with audit trail.

        Args:
            user_id: User ID
            include_inactive: Whether to include inactive memberships (default: False)

        Returns:
            List[UserRoleMembership]: List of membership records

        Example:
            >>> memberships = await role_service.get_user_memberships("507f...")
            >>> for m in memberships:
            ...     print(f"Role: {m.role.name}, Assigned: {m.assigned_at}")
        """
        from outlabs_auth.models.membership_status import MembershipStatus as MStatus
        from outlabs_auth.models.user_role_membership import UserRoleMembership

        # Build query
        if include_inactive:
            query = {"user.$id": user_id}
        else:
            query = {"user.$id": user_id, "status": MStatus.ACTIVE.value}

        # Find all memberships
        memberships = await UserRoleMembership.find(query).to_list()
        return memberships
