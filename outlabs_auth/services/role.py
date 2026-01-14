"""
Role Service

Handles role management operations with PostgreSQL/SQLAlchemy.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import delete as sql_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import (
    InvalidInputError,
    RoleNotFoundError,
    UserNotFoundError,
)
from outlabs_auth.models.sql.enums import MembershipStatus
from outlabs_auth.models.sql.permission import Permission
from outlabs_auth.models.sql.role import Role, RolePermission
from outlabs_auth.models.sql.user import User
from outlabs_auth.models.sql.user_role_membership import UserRoleMembership
from outlabs_auth.services.base import BaseService
from outlabs_auth.utils.validation import validate_name, validate_slug


class RoleService(BaseService[Role]):
    """
    Role management service.

    Handles:
    - Role CRUD operations
    - Permission assignment to roles (via junction table)
    - Role listing and search
    - System role protection
    - User role membership (SimpleRBAC)
    """

    def __init__(self, config: AuthConfig):
        """
        Initialize RoleService.

        Args:
            config: Authentication configuration
        """
        super().__init__(Role)
        self.config = config

    async def create_role(
        self,
        session: AsyncSession,
        name: str,
        display_name: str,
        description: Optional[str] = None,
        permission_names: Optional[List[str]] = None,
        is_global: bool = True,
        is_system_role: bool = False,
        entity_id: Optional[UUID] = None,
        tenant_id: Optional[str] = None,
    ) -> Role:
        """
        Create a new role.

        Args:
            session: Database session
            name: Role name (normalized to lowercase slug)
            display_name: Human-readable role name
            description: Optional role description
            permission_names: List of permission names to assign
            is_global: Whether role can be assigned anywhere
            is_system_role: Whether this is a protected system role
            entity_id: Optional entity ID to scope role (EnterpriseRBAC)
            tenant_id: Optional tenant ID

        Returns:
            Role: Created role

        Raises:
            InvalidInputError: If role name already exists
        """
        # Validate and normalize
        name = validate_slug(name, "name")
        display_name = validate_name(display_name, "display_name")

        # Check if role already exists
        existing = await self.get_one(session, Role.name == name)
        if existing:
            raise InvalidInputError(
                message=f"Role with name '{name}' already exists",
                details={"name": name},
            )

        # Create role
        role = Role(
            name=name,
            display_name=display_name,
            description=description,
            is_global=is_global,
            is_system_role=is_system_role,
            entity_id=entity_id,
            tenant_id=tenant_id,
        )

        await self.create(session, role)

        # Add permissions via junction table
        if permission_names:
            await self._add_permissions_by_name(session, role.id, permission_names)

        return role

    async def get_role_by_id(
        self,
        session: AsyncSession,
        role_id: UUID,
        load_permissions: bool = False,
    ) -> Optional[Role]:
        """
        Get role by ID.

        Args:
            session: Database session
            role_id: Role UUID
            load_permissions: Whether to eager load permissions

        Returns:
            Role if found, None otherwise
        """
        options = []
        if load_permissions:
            options.append(selectinload(Role.permissions))
        return await self.get_by_id(session, role_id, options=options)

    async def get_role_by_name(
        self,
        session: AsyncSession,
        name: str,
    ) -> Optional[Role]:
        """
        Get role by name.

        Args:
            session: Database session
            name: Role name

        Returns:
            Role if found, None otherwise
        """
        name = validate_slug(name, "name")
        return await self.get_one(session, Role.name == name)

    async def update_role(
        self,
        session: AsyncSession,
        role_id: UUID,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        is_global: Optional[bool] = None,
    ) -> Role:
        """
        Update role.

        Args:
            session: Database session
            role_id: Role UUID
            display_name: New display name
            description: New description

        Returns:
            Updated role

        Raises:
            RoleNotFoundError: If role doesn't exist
            InvalidInputError: If trying to modify system role
        """
        role = await self.get_by_id(session, role_id)
        if not role:
            raise RoleNotFoundError(
                message="Role not found",
                details={"role_id": str(role_id)},
            )

        if role.is_system_role:
            raise InvalidInputError(
                message="Cannot modify system role",
                details={"role_id": str(role_id), "role_name": role.name},
            )

        if display_name is not None:
            role.display_name = validate_name(display_name, "display_name")

        if description is not None:
            role.description = description

        if is_global is not None:
            role.is_global = is_global

        await self.update(session, role)
        return role

    async def delete_role(
        self,
        session: AsyncSession,
        role_id: UUID,
    ) -> bool:
        """
        Delete role.

        Args:
            session: Database session
            role_id: Role UUID

        Returns:
            True if deleted, False if not found

        Raises:
            InvalidInputError: If trying to delete system role
        """
        role = await self.get_by_id(session, role_id)
        if not role:
            return False

        if role.is_system_role:
            raise InvalidInputError(
                message="Cannot delete system role",
                details={"role_id": str(role_id), "role_name": role.name},
            )

        await self.delete(session, role)
        return True

    async def list_roles(
        self,
        session: AsyncSession,
        page: int = 1,
        limit: int = 20,
        is_global: Optional[bool] = None,
        tenant_id: Optional[str] = None,
    ) -> Tuple[List[Role], int]:
        """
        List roles with pagination.

        Args:
            session: Database session
            page: Page number (1-indexed)
            limit: Results per page
            is_global: Filter by global flag
            tenant_id: Filter by tenant

        Returns:
            Tuple of (roles, total_count)
        """
        filters = []
        if is_global is not None:
            filters.append(Role.is_global == is_global)
        if tenant_id:
            filters.append(Role.tenant_id == tenant_id)

        total_count = await self.count(session, *filters)

        skip = (page - 1) * limit
        roles = await self.get_many(
            session,
            *filters,
            skip=skip,
            limit=limit,
            order_by=Role.name,
        )

        return roles, total_count

    # =========================================================================
    # Permission Management (by permission name convenience)
    # =========================================================================

    async def set_permissions_by_name(
        self,
        session: AsyncSession,
        role_id: UUID,
        permission_names: List[str],
    ) -> Role:
        """
        Replace a role's permissions using permission names.
        """
        role = await self.get_by_id(session, role_id)
        if not role:
            raise RoleNotFoundError(
                message="Role not found",
                details={"role_id": str(role_id)},
            )
        if role.is_system_role:
            raise InvalidInputError(
                message="Cannot modify system role permissions",
                details={"role_id": str(role_id), "role_name": role.name},
            )

        # Clear existing role_permissions
        await session.execute(
            sql_delete(RolePermission).where(RolePermission.role_id == role_id)
        )
        await session.flush()

        # Add requested permissions
        await self._add_permissions_by_name(session, role_id, permission_names)

        # Reload role with permissions
        return (
            await self.get_role_by_id(session, role_id, load_permissions=True) or role
        )

    async def add_permissions_by_name(
        self,
        session: AsyncSession,
        role_id: UUID,
        permission_names: List[str],
    ) -> Role:
        """
        Add permissions to a role using permission names.
        """
        role = await self.get_by_id(session, role_id)
        if not role:
            raise RoleNotFoundError(
                message="Role not found",
                details={"role_id": str(role_id)},
            )
        if role.is_system_role:
            raise InvalidInputError(
                message="Cannot modify system role permissions",
                details={"role_id": str(role_id), "role_name": role.name},
            )

        await self._add_permissions_by_name(session, role_id, permission_names)
        return (
            await self.get_role_by_id(session, role_id, load_permissions=True) or role
        )

    async def remove_permissions_by_name(
        self,
        session: AsyncSession,
        role_id: UUID,
        permission_names: List[str],
    ) -> Role:
        """
        Remove permissions from a role using permission names.
        """
        role = await self.get_by_id(session, role_id)
        if not role:
            raise RoleNotFoundError(
                message="Role not found",
                details={"role_id": str(role_id)},
            )
        if role.is_system_role:
            raise InvalidInputError(
                message="Cannot modify system role permissions",
                details={"role_id": str(role_id), "role_name": role.name},
            )

        # Resolve permission IDs
        stmt = select(Permission.id).where(Permission.name.in_(permission_names))
        result = await session.execute(stmt)
        perm_ids = [row[0] for row in result.all()]
        if perm_ids:
            await session.execute(
                sql_delete(RolePermission).where(
                    RolePermission.role_id == role_id,
                    RolePermission.permission_id.in_(perm_ids),
                )
            )
            await session.flush()

        return (
            await self.get_role_by_id(session, role_id, load_permissions=True) or role
        )

    # =========================================================================
    # Permission Management (via junction table)
    # =========================================================================

    async def _add_permissions_by_name(
        self,
        session: AsyncSession,
        role_id: UUID,
        permission_names: List[str],
    ) -> None:
        """Add permissions to role by name."""
        for perm_name in permission_names:
            # Find permission by name
            stmt = select(Permission).where(Permission.name == perm_name)
            result = await session.execute(stmt)
            perm = result.scalar_one_or_none()

            if perm:
                # Create junction record
                role_perm = RolePermission(role_id=role_id, permission_id=perm.id)
                session.add(role_perm)

        await session.flush()

    async def add_permissions(
        self,
        session: AsyncSession,
        role_id: UUID,
        permission_ids: List[UUID],
    ) -> Role:
        """
        Add permissions to role.

        Args:
            session: Database session
            role_id: Role UUID
            permission_ids: Permission UUIDs to add

        Returns:
            Updated role

        Raises:
            RoleNotFoundError: If role doesn't exist
            InvalidInputError: If trying to modify system role
        """
        role = await self.get_by_id(session, role_id)
        if not role:
            raise RoleNotFoundError(
                message="Role not found",
                details={"role_id": str(role_id)},
            )

        if role.is_system_role:
            raise InvalidInputError(
                message="Cannot modify system role",
                details={"role_id": str(role_id)},
            )

        # Get existing permission IDs
        stmt = select(RolePermission.permission_id).where(
            RolePermission.role_id == role_id
        )
        result = await session.execute(stmt)
        existing_ids = {row[0] for row in result}

        # Add new permissions
        for perm_id in permission_ids:
            if perm_id not in existing_ids:
                role_perm = RolePermission(role_id=role_id, permission_id=perm_id)
                session.add(role_perm)

        await session.flush()
        return role

    async def remove_permissions(
        self,
        session: AsyncSession,
        role_id: UUID,
        permission_ids: List[UUID],
    ) -> Role:
        """
        Remove permissions from role.

        Args:
            session: Database session
            role_id: Role UUID
            permission_ids: Permission UUIDs to remove

        Returns:
            Updated role

        Raises:
            RoleNotFoundError: If role doesn't exist
            InvalidInputError: If trying to modify system role
        """
        role = await self.get_by_id(session, role_id)
        if not role:
            raise RoleNotFoundError(
                message="Role not found",
                details={"role_id": str(role_id)},
            )

        if role.is_system_role:
            raise InvalidInputError(
                message="Cannot modify system role",
                details={"role_id": str(role_id)},
            )

        # Delete junction records
        for perm_id in permission_ids:
            stmt = select(RolePermission).where(
                RolePermission.role_id == role_id,
                RolePermission.permission_id == perm_id,
            )
            result = await session.execute(stmt)
            role_perm = result.scalar_one_or_none()
            if role_perm:
                await session.delete(role_perm)

        await session.flush()
        return role

    async def get_role_permissions(
        self,
        session: AsyncSession,
        role_id: UUID,
    ) -> List[Permission]:
        """
        Get all permissions for a role.

        Args:
            session: Database session
            role_id: Role UUID

        Returns:
            List of Permission objects

        Raises:
            RoleNotFoundError: If role doesn't exist
        """
        role = await self.get_by_id(
            session,
            role_id,
            options=[selectinload(Role.permissions)],
        )
        if not role:
            raise RoleNotFoundError(
                message="Role not found",
                details={"role_id": str(role_id)},
            )

        return role.permissions

    async def get_role_permission_names(
        self,
        session: AsyncSession,
        role_id: UUID,
    ) -> List[str]:
        """
        Get permission names for a role.

        Args:
            session: Database session
            role_id: Role UUID

        Returns:
            List of permission name strings
        """
        permissions = await self.get_role_permissions(session, role_id)
        return [p.name for p in permissions]

    # =========================================================================
    # User Role Membership (SimpleRBAC)
    # =========================================================================

    async def assign_role_to_user(
        self,
        session: AsyncSession,
        user_id: UUID,
        role_id: UUID,
        assigned_by_id: Optional[UUID] = None,
        valid_from: Optional[datetime] = None,
        valid_until: Optional[datetime] = None,
    ) -> UserRoleMembership:
        """
        Assign role to user (SimpleRBAC).

        Args:
            session: Database session
            user_id: User UUID
            role_id: Role UUID
            assigned_by_id: Optional assigner's user UUID
            valid_from: Optional start of validity
            valid_until: Optional end of validity

        Returns:
            Created membership

        Raises:
            UserNotFoundError: If user doesn't exist
            RoleNotFoundError: If role doesn't exist
            InvalidInputError: If membership already exists
        """
        # Validate user exists
        stmt = select(User).where(User.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            raise UserNotFoundError(
                message="User not found",
                details={"user_id": str(user_id)},
            )

        # Validate role exists
        role = await self.get_by_id(session, role_id)
        if not role:
            raise RoleNotFoundError(
                message="Role not found",
                details={"role_id": str(role_id)},
            )

        # Check for existing active membership
        stmt = select(UserRoleMembership).where(
            UserRoleMembership.user_id == user_id,
            UserRoleMembership.role_id == role_id,
            UserRoleMembership.status == MembershipStatus.ACTIVE,
        )
        result = await session.execute(stmt)
        if result.scalar_one_or_none():
            raise InvalidInputError(
                message="User already has this role assigned",
                details={"user_id": str(user_id), "role_id": str(role_id)},
            )

        # Create membership
        membership = UserRoleMembership(
            user_id=user_id,
            role_id=role_id,
            assigned_by_id=assigned_by_id,
            valid_from=valid_from,
            valid_until=valid_until,
            status=MembershipStatus.ACTIVE,
        )

        session.add(membership)
        await session.flush()
        await session.refresh(membership)
        return membership

    async def revoke_role_from_user(
        self,
        session: AsyncSession,
        user_id: UUID,
        role_id: UUID,
        revoked_by_id: Optional[UUID] = None,
        reason: Optional[str] = None,
    ) -> bool:
        """
        Revoke role from user.

        Args:
            session: Database session
            user_id: User UUID
            role_id: Role UUID
            revoked_by_id: Optional revoker's user UUID
            reason: Optional revocation reason

        Returns:
            True if revoked, False if no active membership found
        """
        stmt = select(UserRoleMembership).where(
            UserRoleMembership.user_id == user_id,
            UserRoleMembership.role_id == role_id,
            UserRoleMembership.status == MembershipStatus.ACTIVE,
        )
        result = await session.execute(stmt)
        membership = result.scalar_one_or_none()

        if not membership:
            return False

        membership.status = MembershipStatus.REVOKED
        membership.revoked_at = datetime.now(timezone.utc)
        membership.revoked_by_id = revoked_by_id
        membership.revocation_reason = reason

        await session.flush()
        return True

    async def get_user_roles(
        self,
        session: AsyncSession,
        user_id: UUID,
        include_inactive: bool = False,
    ) -> List[Role]:
        """
        Get all roles assigned to a user.

        Args:
            session: Database session
            user_id: User UUID
            include_inactive: Include revoked/suspended memberships

        Returns:
            List of Role objects
        """
        filters = [UserRoleMembership.user_id == user_id]
        if not include_inactive:
            filters.append(UserRoleMembership.status == MembershipStatus.ACTIVE)

        stmt = (
            select(UserRoleMembership)
            .options(selectinload(UserRoleMembership.role))
            .where(*filters)
        )
        result = await session.execute(stmt)
        memberships = result.scalars().all()

        # Filter by time-based validity and extract roles
        roles = []
        for m in memberships:
            if m.is_currently_valid():
                roles.append(m.role)

        return roles

    async def get_user_permission_names(
        self,
        session: AsyncSession,
        user_id: UUID,
    ) -> List[str]:
        """
        Get all permission names for a user (aggregated from all roles).

        Args:
            session: Database session
            user_id: User UUID

        Returns:
            List of unique permission names
        """
        roles = await self.get_user_roles(session, user_id)

        all_permissions = set()
        for role in roles:
            # Load permissions for each role
            perms = await self.get_role_permission_names(session, role.id)
            all_permissions.update(perms)

        return list(all_permissions)
