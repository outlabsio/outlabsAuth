"""
Permission Service

Handles permission checking and management with PostgreSQL/SQLAlchemy:
- BasicPermissionService: Flat permission system (SimpleRBAC)
- EnterprisePermissionService: Hierarchical permissions (EnterpriseRBAC) - Phase 3+
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import (
    InvalidInputError,
    PermissionDeniedError,
    PermissionNotFoundError,
    UserNotFoundError,
)
from outlabs_auth.models.sql.enums import MembershipStatus
from outlabs_auth.models.sql.permission import (
    Permission,
    PermissionTag,
    PermissionTagLink,
)
from outlabs_auth.models.sql.role import Role, RolePermission
from outlabs_auth.models.sql.user import User
from outlabs_auth.models.sql.user_role_membership import UserRoleMembership
from outlabs_auth.services.base import BaseService
from outlabs_auth.utils.validation import validate_permission_name


class PermissionService(BaseService[Permission]):
    """
    Permission management and checking service.

    Handles:
    - Permission CRUD operations
    - User permission checking via roles
    - Wildcard permission support
    - Permission aggregation from roles
    """

    def __init__(
        self,
        config: AuthConfig,
        observability: Optional[Any] = None,
    ):
        """
        Initialize PermissionService.

        Args:
            config: Authentication configuration
            observability: Optional observability service for logging/metrics
        """
        super().__init__(Permission)
        self.config = config
        self.observability = observability

    # =========================================================================
    # Permission Checking
    # =========================================================================

    async def check_permission(
        self,
        session: AsyncSession,
        user_id: UUID,
        permission: str,
    ) -> bool:
        """
        Check if user has a specific permission.

        Args:
            session: Database session
            user_id: User UUID
            permission: Permission name (e.g., "user:create")

        Returns:
            True if user has permission, False otherwise

        Raises:
            UserNotFoundError: If user doesn't exist
        """
        start_time = datetime.now(timezone.utc)

        # Get user
        stmt = select(User).where(User.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise UserNotFoundError(
                message="User not found",
                details={"user_id": str(user_id)},
            )

        # Superusers have all permissions
        if user.is_superuser:
            self._log_permission_check(
                user_id, permission, "granted", start_time, "superuser"
            )
            return True

        # Get all user permissions
        user_permissions = await self.get_user_permissions(session, user_id)

        # Check exact match
        if permission in user_permissions:
            self._log_permission_check(
                user_id, permission, "granted", start_time, "exact_match"
            )
            return True

        # Check wildcard permissions
        resource, action = (
            permission.split(":") if ":" in permission else (permission, "*")
        )

        # Check resource wildcard (e.g., "user:*")
        resource_wildcard = f"{resource}:*"
        if resource_wildcard in user_permissions:
            self._log_permission_check(
                user_id, permission, "granted", start_time, "wildcard_match"
            )
            return True

        # Check full wildcard (e.g., "*:*")
        if "*:*" in user_permissions:
            self._log_permission_check(
                user_id, permission, "granted", start_time, "full_wildcard"
            )
            return True

        # Permission denied
        self._log_permission_check(
            user_id, permission, "denied", start_time, "no_permission"
        )
        return False

    def _log_permission_check(
        self,
        user_id: UUID,
        permission: str,
        result: str,
        start_time: datetime,
        reason: str,
    ) -> None:
        """Log permission check for observability."""
        if self.observability:
            duration_ms = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds() * 1000
            self.observability.log_permission_check(
                user_id=str(user_id),
                permission=permission,
                result=result,
                duration_ms=duration_ms,
                reason=reason,
            )

    async def get_user_permissions(
        self,
        session: AsyncSession,
        user_id: UUID,
    ) -> List[str]:
        """
        Get all permissions for a user.

        Aggregates permissions from all assigned roles via UserRoleMembership.

        Args:
            session: Database session
            user_id: User UUID

        Returns:
            List of permission names

        Raises:
            UserNotFoundError: If user doesn't exist
        """
        # Get user
        stmt = select(User).where(User.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise UserNotFoundError(
                message="User not found",
                details={"user_id": str(user_id)},
            )

        # Superusers have all permissions
        if user.is_superuser:
            return ["*:*"]

        all_permissions: Set[str] = set()

        # Get active role memberships with roles eagerly loaded
        stmt = (
            select(UserRoleMembership)
            .options(
                selectinload(UserRoleMembership.role).selectinload(Role.permissions)
            )
            .where(
                UserRoleMembership.user_id == user_id,
                UserRoleMembership.status == MembershipStatus.ACTIVE,
            )
        )
        result = await session.execute(stmt)
        memberships = result.scalars().all()

        for membership in memberships:
            # Check time-based validity
            if not membership.is_currently_valid():
                continue

            role = membership.role
            if role and role.permissions:
                # Extract permission names
                for perm in role.permissions:
                    all_permissions.add(perm.name)

        return list(all_permissions)

    async def require_permission(
        self,
        session: AsyncSession,
        user_id: UUID,
        permission: str,
    ) -> None:
        """
        Require user to have permission (raises exception if not).

        Args:
            session: Database session
            user_id: User UUID
            permission: Permission name

        Raises:
            UserNotFoundError: If user doesn't exist
            PermissionDeniedError: If user lacks permission
        """
        has_permission = await self.check_permission(session, user_id, permission)
        if not has_permission:
            raise PermissionDeniedError(
                message=f"Permission denied: {permission}",
                details={"required_permission": permission},
            )

    async def require_any_permission(
        self,
        session: AsyncSession,
        user_id: UUID,
        permissions: List[str],
    ) -> None:
        """
        Require user to have at least one of the permissions.

        Args:
            session: Database session
            user_id: User UUID
            permissions: List of permission names

        Raises:
            UserNotFoundError: If user doesn't exist
            PermissionDeniedError: If user lacks all permissions
        """
        for permission in permissions:
            if await self.check_permission(session, user_id, permission):
                return

        raise PermissionDeniedError(
            message=f"Permission denied: requires one of {permissions}",
            details={"required_permissions": permissions},
        )

    async def require_all_permissions(
        self,
        session: AsyncSession,
        user_id: UUID,
        permissions: List[str],
    ) -> None:
        """
        Require user to have all of the permissions.

        Args:
            session: Database session
            user_id: User UUID
            permissions: List of permission names

        Raises:
            UserNotFoundError: If user doesn't exist
            PermissionDeniedError: If user lacks any permission
        """
        missing_permissions = []
        for permission in permissions:
            if not await self.check_permission(session, user_id, permission):
                missing_permissions.append(permission)

        if missing_permissions:
            raise PermissionDeniedError(
                message=f"Permission denied: missing {len(missing_permissions)} required permission(s)",
                details={"missing_permissions": missing_permissions},
            )

    # =========================================================================
    # Permission CRUD Operations
    # =========================================================================

    async def create_permission(
        self,
        session: AsyncSession,
        name: str,
        display_name: str,
        description: Optional[str] = None,
        is_system: bool = False,
        is_active: bool = True,
        tags: Optional[List[str]] = None,
        tenant_id: Optional[str] = None,
    ) -> Permission:
        """
        Create a new permission.

        Args:
            session: Database session
            name: Permission name (e.g., "invoice:approve")
            display_name: Human-readable name
            description: Permission description
            is_system: Whether this is a system permission
            tenant_id: Optional tenant ID

        Returns:
            Created permission
        """
        # Validate permission name format
        name = validate_permission_name(name)

        # Check if permission already exists
        existing = await self.get_one(session, Permission.name == name)
        if existing:
            raise InvalidInputError(
                message=f"Permission with name '{name}' already exists",
                details={"name": name},
            )

        # Create permission (auto-parses resource/action/scope in __init__)
        permission = Permission(
            name=name,
            display_name=display_name,
            description=description,
            is_system=is_system,
            is_active=is_active,
            tenant_id=tenant_id,
        )

        await self.create(session, permission)

        if tags:
            await self.set_permission_tags(session, permission.id, tags)

        return permission

    async def get_permission_by_id(
        self,
        session: AsyncSession,
        permission_id: UUID,
        load_tags: bool = False,
    ) -> Optional[Permission]:
        """
        Get permission by ID.

        Args:
            session: Database session
            permission_id: Permission UUID
            load_tags: Whether to eager load tags

        Returns:
            Permission if found, None otherwise
        """
        options = []
        if load_tags:
            options.append(selectinload(Permission.tags))
        return await self.get_by_id(session, permission_id, options=options)

    async def get_permission_by_name(
        self,
        session: AsyncSession,
        name: str,
    ) -> Optional[Permission]:
        """
        Get permission by name.

        Args:
            session: Database session
            name: Permission name

        Returns:
            Permission if found, None otherwise
        """
        name = validate_permission_name(name)
        return await self.get_one(session, Permission.name == name)

    async def update_permission(
        self,
        session: AsyncSession,
        permission_id: UUID,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        is_active: Optional[bool] = None,
        tags: Optional[List[str]] = None,
    ) -> Permission:
        """
        Update permission.

        Args:
            session: Database session
            permission_id: Permission UUID
            display_name: New display name
            description: New description

        Returns:
            Updated permission

        Raises:
            PermissionNotFoundError: If permission doesn't exist
            InvalidInputError: If trying to modify system permission
        """
        permission = await self.get_by_id(session, permission_id)
        if not permission:
            raise PermissionNotFoundError(
                message="Permission not found",
                details={"permission_id": str(permission_id)},
            )

        if permission.is_system:
            raise InvalidInputError(
                message="Cannot modify system permission",
                details={
                    "permission_id": str(permission_id),
                    "permission_name": permission.name,
                },
            )

        if display_name is not None:
            permission.display_name = display_name

        if description is not None:
            permission.description = description

        if is_active is not None:
            permission.is_active = is_active

        await self.update(session, permission)

        if tags is not None:
            await self.set_permission_tags(session, permission_id, tags)

        return permission

    async def set_permission_tags(
        self,
        session: AsyncSession,
        permission_id: UUID,
        tags: List[str],
    ) -> Permission:
        """
        Replace a permission's tag set, creating tags if needed.
        """
        permission = await self.get_permission_by_id(
            session, permission_id, load_tags=True
        )
        if not permission:
            raise PermissionNotFoundError(
                message="Permission not found",
                details={"permission_id": str(permission_id)},
            )

        if permission.is_system:
            raise InvalidInputError(
                message="Cannot modify system permission",
                details={
                    "permission_id": str(permission_id),
                    "permission_name": permission.name,
                },
            )

        normalized = [t.strip() for t in tags if t and t.strip()]
        # De-duplicate, preserve order
        normalized = list(dict.fromkeys(normalized))

        if not normalized:
            permission.tags = []
            await self.update(session, permission)
            return permission

        # Load/create tag models
        stmt = select(PermissionTag).where(
            PermissionTag.name.in_(normalized),
            PermissionTag.tenant_id == permission.tenant_id,
        )
        result = await session.execute(stmt)
        existing_tags = {t.name: t for t in result.scalars().all()}

        tag_models: List[PermissionTag] = []
        for tag_name in normalized:
            tag_model = existing_tags.get(tag_name)
            if not tag_model:
                tag_model = PermissionTag(name=tag_name, tenant_id=permission.tenant_id)
                session.add(tag_model)
                await session.flush()
            tag_models.append(tag_model)

        permission.tags = tag_models
        await self.update(session, permission)
        return permission

    async def delete_permission(
        self,
        session: AsyncSession,
        permission_id: UUID,
    ) -> bool:
        """
        Delete permission.

        Args:
            session: Database session
            permission_id: Permission UUID

        Returns:
            True if deleted, False if not found

        Raises:
            InvalidInputError: If trying to delete system permission
        """
        permission = await self.get_by_id(session, permission_id)
        if not permission:
            return False

        if permission.is_system:
            raise InvalidInputError(
                message="Cannot delete system permission",
                details={
                    "permission_id": str(permission_id),
                    "permission_name": permission.name,
                },
            )

        await self.delete(session, permission)
        return True

    async def list_permissions(
        self,
        session: AsyncSession,
        page: int = 1,
        limit: int = 50,
        resource: Optional[str] = None,
        is_active: Optional[bool] = None,
        tenant_id: Optional[str] = None,
    ) -> Tuple[List[Permission], int]:
        """
        List permissions with pagination.

        Args:
            session: Database session
            page: Page number (1-indexed)
            limit: Results per page
            resource: Filter by resource (e.g., "user")
            is_active: Filter by active status
            tenant_id: Filter by tenant

        Returns:
            Tuple of (permissions, total_count)
        """
        filters = []
        if resource:
            filters.append(Permission.resource == resource)
        if is_active is not None:
            filters.append(Permission.is_active == is_active)
        if tenant_id:
            filters.append(Permission.tenant_id == tenant_id)

        total_count = await self.count(session, *filters)

        skip = (page - 1) * limit
        permissions = await self.get_many(
            session,
            *filters,
            skip=skip,
            limit=limit,
            order_by=Permission.name,
        )

        return permissions, total_count

    async def search_permissions(
        self,
        session: AsyncSession,
        search_term: str,
        limit: int = 20,
    ) -> List[Permission]:
        """
        Search permissions by name or display name.

        Args:
            session: Database session
            search_term: Search term
            limit: Maximum results

        Returns:
            List of matching permissions
        """
        pattern = f"%{search_term}%"
        permissions = await self.get_many(
            session,
            or_(
                Permission.name.ilike(pattern),
                Permission.display_name.ilike(pattern),
            ),
            limit=limit,
        )
        return permissions

    # =========================================================================
    # Tag Management
    # =========================================================================

    async def add_tag_to_permission(
        self,
        session: AsyncSession,
        permission_id: UUID,
        tag_id: UUID,
    ) -> None:
        """
        Add a tag to a permission.

        Args:
            session: Database session
            permission_id: Permission UUID
            tag_id: Tag UUID
        """
        # Check if link already exists
        stmt = select(PermissionTagLink).where(
            PermissionTagLink.permission_id == permission_id,
            PermissionTagLink.tag_id == tag_id,
        )
        result = await session.execute(stmt)
        if result.scalar_one_or_none():
            return  # Already linked

        link = PermissionTagLink(permission_id=permission_id, tag_id=tag_id)
        session.add(link)
        await session.flush()

    async def remove_tag_from_permission(
        self,
        session: AsyncSession,
        permission_id: UUID,
        tag_id: UUID,
    ) -> bool:
        """
        Remove a tag from a permission.

        Args:
            session: Database session
            permission_id: Permission UUID
            tag_id: Tag UUID

        Returns:
            True if removed, False if not found
        """
        stmt = select(PermissionTagLink).where(
            PermissionTagLink.permission_id == permission_id,
            PermissionTagLink.tag_id == tag_id,
        )
        result = await session.execute(stmt)
        link = result.scalar_one_or_none()

        if not link:
            return False

        await session.delete(link)
        await session.flush()
        return True

    async def get_permissions_by_tag(
        self,
        session: AsyncSession,
        tag_name: str,
    ) -> List[Permission]:
        """
        Get all permissions with a specific tag.

        Args:
            session: Database session
            tag_name: Tag name

        Returns:
            List of permissions
        """
        stmt = (
            select(Permission)
            .join(PermissionTagLink)
            .join(PermissionTag)
            .where(PermissionTag.name == tag_name)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    # =========================================================================
    # Utility Methods
    # =========================================================================

    async def get_permissions_for_role(
        self,
        session: AsyncSession,
        role_id: UUID,
    ) -> List[Permission]:
        """
        Get all permissions assigned to a role.

        Args:
            session: Database session
            role_id: Role UUID

        Returns:
            List of Permission objects
        """
        stmt = (
            select(Permission)
            .join(RolePermission)
            .where(RolePermission.role_id == role_id)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def check_permission_exists(
        self,
        session: AsyncSession,
        name: str,
    ) -> bool:
        """
        Check if a permission with the given name exists.

        Args:
            session: Database session
            name: Permission name

        Returns:
            True if exists
        """
        name = validate_permission_name(name)
        return await self.exists(session, Permission.name == name)

    async def bulk_create_permissions(
        self,
        session: AsyncSession,
        permissions_data: List[Dict[str, Any]],
        tenant_id: Optional[str] = None,
    ) -> List[Permission]:
        """
        Create multiple permissions at once.

        Args:
            session: Database session
            permissions_data: List of dicts with name, display_name, description
            tenant_id: Optional tenant ID

        Returns:
            List of created permissions
        """
        created = []
        for data in permissions_data:
            name = validate_permission_name(data["name"])

            # Skip if already exists
            existing = await self.get_one(session, Permission.name == name)
            if existing:
                created.append(existing)
                continue

            permission = Permission(
                name=name,
                display_name=data.get("display_name", name),
                description=data.get("description"),
                is_system=data.get("is_system", False),
                tenant_id=tenant_id,
            )
            session.add(permission)
            created.append(permission)

        await session.flush()

        # Refresh all to get IDs
        for perm in created:
            await session.refresh(perm)

        return created
