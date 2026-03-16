"""
Role Service

Handles role management operations with PostgreSQL/SQLAlchemy.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy import delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import (
    EntityNotFoundError,
    InvalidInputError,
    RoleNotFoundError,
    UserNotFoundError,
)
from outlabs_auth.models.sql.closure import EntityClosure
from outlabs_auth.models.sql.entity import Entity
from outlabs_auth.models.sql.enums import MembershipStatus, RoleScope
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
        root_entity_id: Optional[UUID] = None,
        scope_entity_id: Optional[UUID] = None,
        scope: RoleScope = RoleScope.HIERARCHY,
        is_auto_assigned: bool = False,
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
            is_global: Whether role can be assigned anywhere in hierarchy
            is_system_role: Whether this is a protected system role
            root_entity_id: Optional root entity ID that owns this role (EnterpriseRBAC).
                           If set, role is only available within that organization's hierarchy.
                           Must be a root entity (parent_id is NULL).
            scope_entity_id: Optional entity where this role is defined (entity-local roles).
                            If set, role is local to this entity (and descendants if scope=hierarchy).
            scope: How this role's permissions apply (entity_only or hierarchy).
                   Also controls auto-assignment scope.
            is_auto_assigned: If true, automatically assigned to members within scope.
            tenant_id: Optional tenant ID

        Returns:
            Role: Created role

        Raises:
            InvalidInputError: If role name already exists or validation fails
            EntityNotFoundError: If root_entity_id or scope_entity_id doesn't exist
        """
        # Validate and normalize
        name = validate_slug(name, "name")
        display_name = validate_name(display_name, "display_name")

        # Check role name uniqueness within scope_entity_id
        # (Different entities can have roles with the same name)
        if scope_entity_id:
            existing = await self.get_one(
                session,
                Role.name == name,
                Role.scope_entity_id == scope_entity_id,
            )
        else:
            # For non-entity-local roles, check global uniqueness
            existing = await self.get_one(
                session,
                Role.name == name,
                Role.scope_entity_id.is_(None),
            )
        if existing:
            raise InvalidInputError(
                message=f"Role with name '{name}' already exists in this scope",
                details={
                    "name": name,
                    "scope_entity_id": str(scope_entity_id)
                    if scope_entity_id
                    else None,
                },
            )

        # Validate root_entity_id if provided
        if root_entity_id:
            entity = await session.get(Entity, root_entity_id)
            if not entity:
                raise EntityNotFoundError(
                    message="Root entity not found",
                    details={"root_entity_id": str(root_entity_id)},
                )
            if entity.parent_id is not None:
                raise InvalidInputError(
                    message="Role can only be scoped to root entities (entities with no parent)",
                    details={
                        "root_entity_id": str(root_entity_id),
                        "entity_name": entity.name,
                        "parent_id": str(entity.parent_id),
                    },
                )

        # Validate scope_entity_id if provided
        if scope_entity_id:
            scope_entity = await session.get(Entity, scope_entity_id)
            if not scope_entity:
                raise EntityNotFoundError(
                    message="Scope entity not found",
                    details={"scope_entity_id": str(scope_entity_id)},
                )
            # If scope_entity is set, root_entity_id should also be set (or auto-derived)
            if not root_entity_id:
                # Auto-derive root_entity_id from scope_entity
                root_id = await self._get_root_entity_id(session, scope_entity_id)
                root_entity_id = root_id
            else:
                # Validate scope_entity is within the root_entity's hierarchy
                is_valid = await self._is_entity_in_hierarchy(
                    session, scope_entity_id, root_entity_id
                )
                if not is_valid:
                    raise InvalidInputError(
                        message="Scope entity must be within the root entity's hierarchy",
                        details={
                            "scope_entity_id": str(scope_entity_id),
                            "root_entity_id": str(root_entity_id),
                        },
                    )

        # Create role
        role = Role(
            name=name,
            display_name=display_name,
            description=description,
            is_global=is_global,
            is_system_role=is_system_role,
            root_entity_id=root_entity_id,
            scope_entity_id=scope_entity_id,
            scope=scope,
            is_auto_assigned=is_auto_assigned,
            tenant_id=tenant_id,
        )

        await self.create(session, role)

        # Add permissions via junction table
        if permission_names:
            await self._add_permissions_by_name(session, role.id, permission_names)

        return role

    async def _get_root_entity_id(
        self,
        session: AsyncSession,
        entity_id: UUID,
    ) -> UUID:
        """Get the root entity ID for any entity using closure table."""
        stmt = (
            select(EntityClosure.ancestor_id)
            .where(EntityClosure.descendant_id == entity_id)
            .order_by(EntityClosure.depth.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        row = result.first()
        return row[0] if row else entity_id

    async def _is_entity_in_hierarchy(
        self,
        session: AsyncSession,
        entity_id: UUID,
        root_entity_id: UUID,
    ) -> bool:
        """Check if entity is within root_entity's hierarchy using closure table."""
        stmt = select(EntityClosure).where(
            EntityClosure.ancestor_id == root_entity_id,
            EntityClosure.descendant_id == entity_id,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None

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
        scope: Optional[RoleScope] = None,
        is_auto_assigned: Optional[bool] = None,
    ) -> Role:
        """
        Update role.

        Args:
            session: Database session
            role_id: Role UUID
            display_name: New display name
            description: New description
            is_global: Whether role is global
            scope: Role scope (entity_only or hierarchy)
            is_auto_assigned: Whether to auto-assign to members

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

        if scope is not None:
            role.scope = scope

        if is_auto_assigned is not None:
            role.is_auto_assigned = is_auto_assigned

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
        search: Optional[str] = None,
        is_global: Optional[bool] = None,
        root_entity_id: Optional[UUID] = None,
        tenant_id: Optional[str] = None,
    ) -> Tuple[List[Role], int]:
        """
        List roles with pagination.

        Args:
            session: Database session
            page: Page number (1-indexed)
            limit: Results per page
            search: Optional search term for name, display name, or description
            is_global: Filter by global flag
            root_entity_id: Filter by root entity that owns the role
            tenant_id: Filter by tenant

        Returns:
            Tuple of (roles, total_count)
        """
        filters = []
        if search:
            pattern = f"%{search}%"
            filters.append(
                or_(
                    Role.name.ilike(pattern),
                    Role.display_name.ilike(pattern),
                    Role.description.ilike(pattern),
                )
            )
        if is_global is not None:
            filters.append(Role.is_global == is_global)
        if root_entity_id is not None:
            filters.append(Role.root_entity_id == root_entity_id)
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

    async def get_roles_for_entity(
        self,
        session: AsyncSession,
        entity_id: UUID,
        page: int = 1,
        limit: int = 50,
        include_global: bool = True,
        include_auto_assigned_only: bool = False,
    ) -> Tuple[List[Role], int]:
        """
        Get roles available for a specific entity.

        Returns roles that can be assigned within this entity's context:
        1. Global system-wide roles (is_global=True and root_entity_id=NULL)
        2. Org-scoped roles (root_entity_id matches and scope_entity_id=NULL)
        3. Entity-local roles with scope=hierarchy from any ancestor
        4. Entity-local roles with scope=entity_only from THIS entity only

        Args:
            session: Database session
            entity_id: Entity to find available roles for
            page: Page number (1-indexed)
            limit: Results per page
            include_global: Whether to include system-wide global roles
            include_auto_assigned_only: If True, only return auto-assigned roles

        Returns:
            Tuple of (roles, total_count)
        """
        # Step 1: Get all ancestors (including self) using closure table
        ancestors_stmt = select(EntityClosure.ancestor_id, EntityClosure.depth).where(
            EntityClosure.descendant_id == entity_id
        )
        ancestors_result = await session.execute(ancestors_stmt)
        ancestor_rows = ancestors_result.all()

        if not ancestor_rows:
            return [], 0

        ancestor_ids = [row[0] for row in ancestor_rows]
        # Root is the one with highest depth
        root_id = max(ancestor_rows, key=lambda x: x[1])[0]

        # Step 2: Build filter for available roles
        # A role is available at entity X if:
        # 1. System-wide global: is_global=True AND root_entity_id IS NULL AND scope_entity_id IS NULL
        # 2. Org-scoped: root_entity_id matches AND scope_entity_id IS NULL
        # 3. Entity-local (hierarchy): scope_entity_id is X or an ancestor AND scope=hierarchy
        # 4. Entity-local (entity_only): scope_entity_id = X AND scope=entity_only

        conditions = []

        if include_global:
            # 1. System-wide global roles
            conditions.append(
                and_(
                    Role.is_global == True,
                    Role.root_entity_id.is_(None),
                    Role.scope_entity_id.is_(None),
                )
            )

        # 2. Org-scoped roles (within our root, not entity-local)
        conditions.append(
            and_(
                Role.root_entity_id == root_id,
                Role.scope_entity_id.is_(None),
            )
        )

        # 3. Entity-local roles with hierarchy scope from any ancestor
        conditions.append(
            and_(
                Role.scope_entity_id.in_(ancestor_ids),
                Role.scope == RoleScope.HIERARCHY,
            )
        )

        # 4. Entity-local roles with entity_only scope from THIS entity only
        conditions.append(
            and_(
                Role.scope_entity_id == entity_id,
                Role.scope == RoleScope.ENTITY_ONLY,
            )
        )

        role_filter = or_(*conditions)

        # Add auto-assigned filter if requested
        if include_auto_assigned_only:
            role_filter = and_(role_filter, Role.is_auto_assigned == True)

        # Step 3: Count and fetch
        count_stmt = select(Role).where(role_filter)
        count_result = await session.execute(count_stmt)
        total_count = len(count_result.all())

        skip = (page - 1) * limit
        stmt = (
            select(Role)
            .where(role_filter)
            .order_by(Role.name)
            .offset(skip)
            .limit(limit)
        )
        result = await session.execute(stmt)
        roles = list(result.scalars().all())

        return roles, total_count

    async def get_auto_assigned_roles_for_entity(
        self,
        session: AsyncSession,
        entity_id: UUID,
    ) -> List[Role]:
        """
        Get roles that should be auto-assigned to members of an entity.

        Returns auto-assigned roles where:
        - scope_entity_id matches entity_id AND scope=entity_only
        - OR scope_entity_id is an ancestor AND scope=hierarchy

        Args:
            session: Database session
            entity_id: Entity to get auto-assigned roles for

        Returns:
            List of Role objects that should be auto-assigned
        """
        # Get all ancestors (including self)
        ancestors_stmt = select(EntityClosure.ancestor_id).where(
            EntityClosure.descendant_id == entity_id
        )
        ancestors_result = await session.execute(ancestors_stmt)
        ancestor_ids = [row[0] for row in ancestors_result.all()]

        if not ancestor_ids:
            return []

        # Find auto-assigned roles:
        # 1. Entity-only roles defined at THIS entity
        # 2. Hierarchy roles defined at any ancestor (including self)
        role_filter = and_(
            Role.is_auto_assigned == True,
            or_(
                # Entity-only auto-assigned for this specific entity
                and_(
                    Role.scope_entity_id == entity_id,
                    Role.scope == RoleScope.ENTITY_ONLY,
                ),
                # Hierarchy auto-assigned from any ancestor
                and_(
                    Role.scope_entity_id.in_(ancestor_ids),
                    Role.scope == RoleScope.HIERARCHY,
                ),
            ),
        )

        stmt = select(Role).where(role_filter).order_by(Role.name)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def is_role_available_for_entity(
        self,
        session: AsyncSession,
        role: Role,
        entity_id: UUID,
    ) -> bool:
        """
        Check if a role can be assigned within an entity's context.

        A role is available at entity X if:
        1. System-wide global: is_global=True AND root_entity_id=NULL AND scope_entity_id=NULL
        2. Org-scoped: root_entity_id matches X's root AND scope_entity_id=NULL
        3. Entity-local (hierarchy): scope_entity_id is X or an ancestor AND scope=hierarchy
        4. Entity-local (entity_only): scope_entity_id = X AND scope=entity_only

        Args:
            session: Database session
            role: Role to check
            entity_id: Entity where role would be assigned

        Returns:
            bool: True if role can be used in this entity's context
        """
        # 1. Global system-wide roles are available everywhere
        if (
            role.is_global
            and role.root_entity_id is None
            and role.scope_entity_id is None
        ):
            return True

        # Get entity's ancestors for hierarchy checks
        ancestors_stmt = select(EntityClosure.ancestor_id, EntityClosure.depth).where(
            EntityClosure.descendant_id == entity_id
        )
        ancestors_result = await session.execute(ancestors_stmt)
        ancestor_rows = ancestors_result.all()

        if not ancestor_rows:
            return False

        ancestor_ids = {row[0] for row in ancestor_rows}
        root_id = max(ancestor_rows, key=lambda x: x[1])[0]

        # 2. Org-scoped roles (not entity-local)
        if role.root_entity_id and role.scope_entity_id is None:
            return role.root_entity_id == root_id

        # 3 & 4. Entity-local roles
        if role.scope_entity_id:
            if role.scope == RoleScope.HIERARCHY:
                # Hierarchy scope: available if scope_entity is this entity or an ancestor
                return role.scope_entity_id in ancestor_ids
            else:
                # Entity-only scope: available only at the exact scope entity
                return role.scope_entity_id == entity_id

        # Role with no root_entity_id and is_global=False is orphaned/unusable
        return False

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

        if role.scope_entity_id is not None:
            raise InvalidInputError(
                message="Entity-local roles cannot be assigned via SimpleRBAC",
                details={
                    "role_id": str(role_id),
                    "scope_entity_id": str(role.scope_entity_id),
                },
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

    async def get_user_role_memberships(
        self,
        session: AsyncSession,
        user_id: UUID,
        include_inactive: bool = False,
    ) -> List[UserRoleMembership]:
        """
        Get direct role membership records for a user.

        Args:
            session: Database session
            user_id: User UUID
            include_inactive: Include revoked/suspended memberships

        Returns:
            List of UserRoleMembership records with roles loaded
        """
        filters = [UserRoleMembership.user_id == user_id]
        if not include_inactive:
            filters.append(UserRoleMembership.status == MembershipStatus.ACTIVE)

        stmt = (
            select(UserRoleMembership)
            .options(selectinload(UserRoleMembership.role).selectinload(Role.permissions))
            .where(*filters)
            .order_by(UserRoleMembership.assigned_at.desc())
        )
        result = await session.execute(stmt)
        return result.scalars().all()

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
