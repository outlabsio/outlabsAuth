"""
Permission Service

Handles permission checking and management:
- BasicPermissionService: Flat permission system (SimpleRBAC)
- EnterprisePermissionService: Hierarchical permissions (EnterpriseRBAC) - Phase 3
- ABAC Support: Attribute-Based Access Control (Phase 4.2)
"""
from typing import List, Optional, Set, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from outlabs_auth.models.user import UserModel
from outlabs_auth.models.role import RoleModel
from outlabs_auth.models.permission import PermissionModel
from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import UserNotFoundError, PermissionDeniedError
from outlabs_auth.utils.validation import validate_permission_name
from outlabs_auth.services.policy_engine import PolicyEvaluationEngine

# Import observability (v1.5)
from outlabs_auth.observability import ObservabilityService


class BasicPermissionService:
    """
    Basic permission service for flat (non-hierarchical) RBAC.

    Used by SimpleRBAC preset.

    Features:
    - User permission checking via roles
    - Permission management (CRUD)
    - Wildcard permission support
    """

    def __init__(
        self,
        database: AsyncIOMotorDatabase,
        config: AuthConfig,
        observability: Optional[ObservabilityService] = None,
    ):
        """
        Initialize BasicPermissionService.

        Args:
            database: MongoDB database instance
            config: Authentication configuration
            observability: Optional observability service for logging/metrics
        """
        self.database = database
        self.config = config
        self.observability = observability

    async def check_permission(
        self,
        user_id: str,
        permission: str,
    ) -> bool:
        """
        Check if user has a specific permission.

        Args:
            user_id: User ID
            permission: Permission name (e.g., "user:create")

        Returns:
            bool: True if user has permission, False otherwise

        Raises:
            UserNotFoundError: If user doesn't exist

        Example:
            >>> has_perm = await perm_service.check_permission(
            ...     user_id="507f1f77bcf86cd799439011",
            ...     permission="user:create"
            ... )
            >>> has_perm
            True
        """
        # Start timing for observability
        from datetime import datetime, timezone
        start_time = datetime.now(timezone.utc)

        # Get user
        user = await UserModel.get(user_id)
        if not user:
            raise UserNotFoundError(
                message="User not found",
                details={"user_id": user_id}
            )

        # Superusers have all permissions
        if user.is_superuser:
            # Log permission check (observability)
            if self.observability:
                duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                self.observability.log_permission_check(
                    user_id=user_id,
                    permission=permission,
                    result="granted",
                    duration_ms=duration_ms,
                    reason="superuser",
                )
            return True

        # Get all user permissions
        user_permissions = await self.get_user_permissions(user_id)

        # Check exact match
        if permission in user_permissions:
            # Log permission check (observability)
            if self.observability:
                duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                self.observability.log_permission_check(
                    user_id=user_id,
                    permission=permission,
                    result="granted",
                    duration_ms=duration_ms,
                    reason="exact_match",
                )
            return True

        # Check wildcard permissions
        # For example: "user:*" matches "user:create"
        resource, action = permission.split(":") if ":" in permission else (permission, "*")

        # Check resource wildcard (e.g., "user:*")
        resource_wildcard = f"{resource}:*"
        if resource_wildcard in user_permissions:
            # Log permission check (observability)
            if self.observability:
                duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                self.observability.log_permission_check(
                    user_id=user_id,
                    permission=permission,
                    result="granted",
                    duration_ms=duration_ms,
                    reason="wildcard_match",
                )
            return True

        # Check full wildcard (e.g., "*:*")
        if "*:*" in user_permissions:
            # Log permission check (observability)
            if self.observability:
                duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                self.observability.log_permission_check(
                    user_id=user_id,
                    permission=permission,
                    result="granted",
                    duration_ms=duration_ms,
                    reason="full_wildcard",
                )
            return True

        # Permission denied - log (observability)
        if self.observability:
            duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            self.observability.log_permission_check(
                user_id=user_id,
                permission=permission,
                result="denied",
                duration_ms=duration_ms,
                reason="no_permission",
            )

        return False

    async def get_user_permissions(self, user_id: str) -> List[str]:
        """
        Get all permissions for a user.

        Aggregates permissions from all assigned roles.

        Args:
            user_id: User ID

        Returns:
            List[str]: List of permission names

        Raises:
            UserNotFoundError: If user doesn't exist

        Example:
            >>> permissions = await perm_service.get_user_permissions("507f...")
            >>> permissions
            ['user:create', 'user:read', 'user:update', 'role:read']
        """
        # Get user
        user = await UserModel.get(user_id)
        if not user:
            raise UserNotFoundError(
                message="User not found",
                details={"user_id": user_id}
            )

        # Superusers have all permissions (represented as wildcard)
        if user.is_superuser:
            return ["*:*"]

        # In SimpleRBAC, user roles are assigned via UserRoleMembership table
        # This provides audit trail and time-based role assignments
        from outlabs_auth.models.user_role_membership import UserRoleMembership
        from outlabs_auth.models.membership_status import MembershipStatus

        # Find all active role memberships for user
        # Convert user_id to ObjectId for Beanie Link query
        user_oid = ObjectId(user_id)
        memberships = await UserRoleMembership.find(
            {"user.$id": user_oid, "status": MembershipStatus.ACTIVE.value}
        ).fetch_links().to_list()

        # Aggregate permissions from all valid roles
        all_permissions: Set[str] = set()
        for membership in memberships:
            # Check if membership can grant permissions (status + time validity)
            if membership.can_grant_permissions():
                # Fetch the role and add its permissions
                role = await membership.role.fetch()
                if role:
                    all_permissions.update(role.permissions)

        return list(all_permissions)

    async def require_permission(
        self,
        user_id: str,
        permission: str,
    ) -> None:
        """
        Require user to have permission (raises exception if not).

        Args:
            user_id: User ID
            permission: Permission name

        Raises:
            UserNotFoundError: If user doesn't exist
            PermissionDeniedError: If user lacks permission

        Example:
            >>> await perm_service.require_permission(
            ...     user_id="507f...",
            ...     permission="user:delete"
            ... )
            # Raises PermissionDeniedError if user lacks permission
        """
        has_permission = await self.check_permission(user_id, permission)
        if not has_permission:
            raise PermissionDeniedError(
                message=f"Permission denied: {permission}",
                details={"required_permission": permission}
            )

    async def require_any_permission(
        self,
        user_id: str,
        permissions: List[str],
    ) -> None:
        """
        Require user to have at least one of the permissions.

        Args:
            user_id: User ID
            permissions: List of permission names

        Raises:
            UserNotFoundError: If user doesn't exist
            PermissionDeniedError: If user lacks all permissions

        Example:
            >>> await perm_service.require_any_permission(
            ...     user_id="507f...",
            ...     permissions=["user:delete", "user:update"]
            ... )
        """
        for permission in permissions:
            if await self.check_permission(user_id, permission):
                return  # User has at least one permission

        raise PermissionDeniedError(
            message=f"Permission denied: requires one of {permissions}",
            details={"required_permissions": permissions}
        )

    async def require_all_permissions(
        self,
        user_id: str,
        permissions: List[str],
    ) -> None:
        """
        Require user to have all of the permissions.

        Args:
            user_id: User ID
            permissions: List of permission names

        Raises:
            UserNotFoundError: If user doesn't exist
            PermissionDeniedError: If user lacks any permission

        Example:
            >>> await perm_service.require_all_permissions(
            ...     user_id="507f...",
            ...     permissions=["user:create", "user:update", "user:delete"]
            ... )
        """
        missing_permissions = []
        for permission in permissions:
            if not await self.check_permission(user_id, permission):
                missing_permissions.append(permission)

        if missing_permissions:
            raise PermissionDeniedError(
                message=f"Permission denied: missing {len(missing_permissions)} required permission(s)",
                details={"missing_permissions": missing_permissions}
            )

    # Permission CRUD operations

    async def create_permission(
        self,
        name: str,
        display_name: str,
        description: str,
        is_system: bool = False,
    ) -> PermissionModel:
        """
        Create a new permission.

        Args:
            name: Permission name (e.g., "invoice:approve")
            display_name: Human-readable name
            description: Permission description
            is_system: Whether this is a system permission

        Returns:
            PermissionModel: Created permission

        Example:
            >>> perm = await perm_service.create_permission(
            ...     name="invoice:approve",
            ...     display_name="Approve Invoices",
            ...     description="Can approve invoices up to $10,000"
            ... )
        """
        # Validate permission name format
        name = validate_permission_name(name)

        # Create permission
        permission = PermissionModel(
            name=name,
            display_name=display_name,
            description=description,
            is_system=is_system,
        )

        await permission.save()
        return permission

    async def get_permission_by_name(self, name: str) -> Optional[PermissionModel]:
        """
        Get permission by name.

        Args:
            name: Permission name

        Returns:
            Optional[PermissionModel]: Permission if found

        Example:
            >>> perm = await perm_service.get_permission_by_name("user:create")
            >>> perm.display_name if perm else None
            'Create Users'
        """
        name = validate_permission_name(name)
        return await PermissionModel.find_one(PermissionModel.name == name)

    async def list_permissions(
        self,
        page: int = 1,
        limit: int = 50,
        resource: Optional[str] = None,
    ) -> tuple[List[PermissionModel], int]:
        """
        List permissions with pagination.

        Args:
            page: Page number (1-indexed)
            limit: Results per page
            resource: Filter by resource (e.g., "user")

        Returns:
            tuple[List[PermissionModel], int]: (permissions, total_count)

        Example:
            >>> perms, total = await perm_service.list_permissions(
            ...     page=1,
            ...     limit=20,
            ...     resource="user"
            ... )
            >>> [p.name for p in perms]
            ['user:create', 'user:read', 'user:update', 'user:delete']
        """
        # Build query
        query = {}
        if resource:
            query["resource"] = resource

        # Get total count
        total_count = await PermissionModel.find(query).count()

        # Get paginated results
        skip = (page - 1) * limit
        permissions = await PermissionModel.find(query).skip(skip).limit(limit).to_list()

        return permissions, total_count

    async def delete_permission(self, permission_id: str) -> bool:
        """
        Delete permission.

        Note: Cannot delete system permissions.

        Args:
            permission_id: Permission ID

        Returns:
            bool: True if deleted, False if not found

        Example:
            >>> deleted = await perm_service.delete_permission("507f...")
            >>> deleted
            True
        """
        permission = await PermissionModel.get(permission_id)
        if not permission:
            return False

        # Protect system permissions
        if permission.is_system:
            from outlabs_auth.core.exceptions import InvalidInputError
            raise InvalidInputError(
                message="Cannot delete system permission",
                details={"permission_id": permission_id, "permission_name": permission.name}
            )

        await permission.delete()
        return True


class EnterprisePermissionService(BasicPermissionService):
    """
    Enterprise permission service with entity hierarchy and tree permissions.

    Used by EnterpriseRBAC preset.

    Features:
    - All BasicPermissionService features
    - Entity-scoped permission checking
    - Tree permissions (`resource:action_tree`)
    - Permission inheritance via closure table (O(1) queries)
    - Multiple roles per entity membership
    - Redis caching for permission lookups (optional)

    Example:
        >>> # Check if user can update entity
        >>> has_perm, source = await perm_service.check_permission(
        ...     user_id,
        ...     "entity:update",
        ...     entity_id
        ... )
        >>>
        >>> # Check if user can update all descendants
        >>> has_tree_perm = await perm_service.check_tree_permission(
        ...     user_id,
        ...     "entity:update_tree",
        ...     target_entity_id
        ... )
    """

    def __init__(
        self,
        database: AsyncIOMotorDatabase,
        config: AuthConfig,
        redis_client: Optional["RedisClient"] = None,
    ):
        """
        Initialize EnterprisePermissionService.

        Args:
            database: MongoDB database instance
            config: Authentication configuration
            redis_client: Optional Redis client for caching
        """
        super().__init__(database, config)
        self.redis_client = redis_client
        self.policy_engine = PolicyEvaluationEngine()  # For ABAC condition evaluation

    async def check_permission(
        self,
        user_id: str,
        permission: str,
        entity_id: Optional[str] = None,
    ) -> tuple[bool, str]:
        """
        Check if user has permission with optional entity context.

        Permission Resolution Algorithm:
        1. Check Redis cache (if enabled)
        2. Check direct permission in target entity
        3. Check tree permission (_tree suffix) in ancestors (via closure table)
        4. Check platform-wide permission (_all suffix)
        5. Cache result in Redis (if enabled)

        Args:
            user_id: User ID
            permission: Permission name (e.g., "entity:update")
            entity_id: Optional entity ID for scoped check

        Returns:
            tuple[bool, str]: (has_permission, source)
                source: "direct", "tree", "all", or "superuser"

        Raises:
            UserNotFoundError: If user doesn't exist

        Example:
            >>> has_perm, source = await perm_service.check_permission(
            ...     user_id,
            ...     "entity:update",
            ...     entity_id
            ... )
            >>> print(f"Permission granted via: {source}")
        """
        from outlabs_auth.models.entity import EntityModel
        from outlabs_auth.models.membership import EntityMembershipModel
        from outlabs_auth.models.closure import EntityClosureModel

        # Try Redis cache first (if enabled)
        if self.redis_client and self.redis_client.is_available:
            cache_key = self.redis_client.make_key(
                "auth", "perm", user_id, permission, entity_id or "global"
            )
            cached = await self.redis_client.get(cache_key)
            if cached is not None:
                return cached.get("has_permission", False), cached.get("source", "cached")

        # Get user
        user = await UserModel.get(user_id)
        if not user:
            raise UserNotFoundError(
                message="User not found",
                details={"user_id": user_id}
            )

        # Superusers have all permissions
        if user.is_superuser:
            result = (True, "superuser")
            await self._cache_permission_result(user_id, permission, entity_id, result)
            return result

        # If no entity context, fallback to basic checking
        if not entity_id:
            has_basic = await super().check_permission(user_id, permission)
            return has_basic, "basic"

        # Parse permission
        if ":" not in permission:
            permission = f"{permission}:*"

        resource, action = permission.split(":", 1)

        # Get target entity to determine its type
        target_entity = await EntityModel.get(entity_id)
        target_entity_type = target_entity.entity_type if target_entity else None

        # Get all user memberships
        # TODO: Update to use status field when EntityMembershipModel is created
        # Should be: {"user.$id": user.id, "status": MembershipStatus.ACTIVE.value}
        memberships = await EntityMembershipModel.find(
            EntityMembershipModel.user.id == user.id,
            EntityMembershipModel.is_active == True
        ).to_list()

        # Extract permission names:
        # - Direct permissions: only from TARGET entity (context-aware)
        # - Platform-wide permissions (_all): from ANY membership
        # - Tree permissions: handled separately below via ancestors
        user_permissions: Set[str] = set()
        platform_wide_permissions: Set[str] = set()
        direct_entity_ids = set()
        entity_type_map = {}  # Map entity_id -> entity_type

        for membership in memberships:
            # Skip if not currently valid
            if not membership.is_currently_valid():
                continue

            # Fetch entity
            entity = await membership.entity.fetch() if hasattr(membership.entity, 'fetch') else membership.entity
            if entity:
                entity_id_str = str(entity.id)
                direct_entity_ids.add(entity_id_str)
                entity_type_map[entity_id_str] = entity.entity_type

                # Fetch and check permissions from roles
                for role_link in membership.roles:
                    role = await role_link.fetch() if hasattr(role_link, 'fetch') else role_link
                    if role and isinstance(role, RoleModel):
                        # Get permissions for this membership's entity type
                        membership_entity_type = entity.entity_type
                        context_permissions = role.get_permissions_for_entity_type(membership_entity_type)

                        # If this is the target entity, add to user_permissions
                        if entity_id_str == entity_id:
                            user_permissions.update(context_permissions)

                        # Always collect platform-wide permissions (_all suffix) from any membership
                        for perm in context_permissions:
                            if perm.endswith("_all") or perm == "*:*":
                                platform_wide_permissions.add(perm)

        # 1. Check direct permission in target entity
        if entity_id in direct_entity_ids:
            # User is a direct member of the target entity
            if permission in user_permissions:
                result = (True, "direct")
                await self._cache_permission_result(user_id, permission, entity_id, result)
                return result

            # Check wildcard permissions
            if f"{resource}:*" in user_permissions:
                result = (True, "direct")
                await self._cache_permission_result(user_id, permission, entity_id, result)
                return result

            if "*:*" in user_permissions:
                result = (True, "direct")
                await self._cache_permission_result(user_id, permission, entity_id, result)
                return result

        # 2. Check tree permission in ancestors
        # Get all ancestors of target entity using closure table
        ancestor_closures = await EntityClosureModel.find(
            EntityClosureModel.descendant_id == entity_id,
            EntityClosureModel.depth > 0  # Exclude self
        ).to_list()

        ancestor_ids = {closure.ancestor_id for closure in ancestor_closures}

        # Check if user has membership in any ancestor
        for ancestor_id in ancestor_ids:
            if ancestor_id in direct_entity_ids:
                # User is a member of an ancestor
                # Get permissions for THIS ancestor's entity type (context-aware)
                ancestor_entity_type = entity_type_map.get(ancestor_id)

                # Re-evaluate permissions for this specific ancestor context
                ancestor_permissions: Set[str] = set()
                for membership in memberships:
                    entity = await membership.entity.fetch() if hasattr(membership.entity, 'fetch') else membership.entity
                    if entity and str(entity.id) == ancestor_id:
                        # This is the membership in the ancestor entity
                        for role_link in membership.roles:
                            role = await role_link.fetch() if hasattr(role_link, 'fetch') else role_link
                            if role and isinstance(role, RoleModel):
                                # Use context-aware permissions for this ancestor entity type
                                context_perms = role.get_permissions_for_entity_type(ancestor_entity_type)
                                ancestor_permissions.update(context_perms)

                # Check for tree permission
                tree_permission = f"{resource}:{action}_tree"

                if tree_permission in ancestor_permissions:
                    result = (True, "tree")
                    await self._cache_permission_result(user_id, permission, entity_id, result)
                    return result

                # Check tree wildcard
                if f"{resource}:*_tree" in ancestor_permissions:
                    result = (True, "tree")
                    await self._cache_permission_result(user_id, permission, entity_id, result)
                    return result

        # 3. Check platform-wide permission (_all suffix) from any membership
        all_permission = f"{resource}:{action}_all"
        if all_permission in platform_wide_permissions:
            result = (True, "all")
            await self._cache_permission_result(user_id, permission, entity_id, result)
            return result

        # Check all wildcard
        if f"{resource}:*_all" in platform_wide_permissions:
            result = (True, "all")
            await self._cache_permission_result(user_id, permission, entity_id, result)
            return result

        if "*:*" in platform_wide_permissions:
            result = (True, "all")
            await self._cache_permission_result(user_id, permission, entity_id, result)
            return result

        # No permission found
        result = (False, "none")
        await self._cache_permission_result(user_id, permission, entity_id, result)
        return result

    async def check_tree_permission(
        self,
        user_id: str,
        permission: str,
        target_entity_id: str,
    ) -> bool:
        """
        Check if user has tree permission for target entity.

        This checks if user has the tree permission in any ancestor of target entity.

        Args:
            user_id: User ID
            permission: Tree permission name (e.g., "entity:update_tree")
            target_entity_id: Target entity ID

        Returns:
            bool: True if user has tree permission

        Example:
            >>> # Check if user can update all descendants of target
            >>> can_update_tree = await perm_service.check_tree_permission(
            ...     user_id,
            ...     "entity:update_tree",
            ...     target_entity_id
            ... )
        """
        # Use check_permission which already handles tree logic
        has_perm, source = await self.check_permission(
            user_id,
            permission.replace("_tree", ""),
            target_entity_id
        )

        return has_perm and source in ["tree", "all", "superuser"]

    async def has_permission(
        self,
        user_id: str,
        permission: str,
        entity_id: Optional[str] = None,
    ) -> bool:
        """
        Convenience method to check if user has permission (returns only bool).

        This is a wrapper around check_permission() that only returns the boolean result.

        Args:
            user_id: User ID
            permission: Permission name (e.g., "entity:update")
            entity_id: Optional entity ID for scoped check

        Returns:
            bool: True if user has permission

        Raises:
            UserNotFoundError: If user doesn't exist

        Example:
            >>> has_perm = await perm_service.has_permission(
            ...     user_id,
            ...     "entity:update",
            ...     entity_id
            ... )
        """
        has_perm, _ = await self.check_permission(user_id, permission, entity_id)
        return has_perm

    async def get_user_permissions_in_entity(
        self,
        user_id: str,
        entity_id: str
    ) -> List[str]:
        """
        Get all permissions user has in specific entity.

        Args:
            user_id: User ID
            entity_id: Entity ID

        Returns:
            List[str]: List of permission names

        Raises:
            UserNotFoundError: If user doesn't exist

        Example:
            >>> permissions = await perm_service.get_user_permissions_in_entity(
            ...     user_id,
            ...     entity_id
            ... )
        """
        from outlabs_auth.models.membership import EntityMembershipModel

        # Get user
        user = await UserModel.get(user_id)
        if not user:
            raise UserNotFoundError(
                message="User not found",
                details={"user_id": user_id}
            )

        # Superusers have all permissions
        if user.is_superuser:
            return ["*:*"]

        # Get entity to determine its type
        from outlabs_auth.models.entity import EntityModel
        from bson import ObjectId

        target_entity = await EntityModel.get(entity_id)
        target_entity_type = target_entity.entity_type if target_entity else None

        # Get membership in entity (convert entity_id to ObjectId for comparison)
        try:
            entity_oid = ObjectId(entity_id) if isinstance(entity_id, str) else entity_id
        except Exception:
            return []

        # TODO: Update to use status field when EntityMembershipModel is created
        # Should use: {"user.$id": user.id, "entity.$id": entity_oid, "status": MembershipStatus.ACTIVE.value}
        # and membership.can_grant_permissions() instead of is_active + is_currently_valid()
        membership = await EntityMembershipModel.find_one(
            EntityMembershipModel.user.id == user.id,
            EntityMembershipModel.entity.id == entity_oid,
            EntityMembershipModel.is_active == True
        )

        if not membership or not membership.is_currently_valid():
            return []

        # Aggregate permissions from roles (use context-aware permissions)
        all_permissions: Set[str] = set()
        for role_link in membership.roles:
            role = await role_link.fetch() if hasattr(role_link, 'fetch') else role_link
            if role and isinstance(role, RoleModel):
                # Use context-aware permissions for this entity type
                context_perms = role.get_permissions_for_entity_type(target_entity_type)
                all_permissions.update(context_perms)

        return list(all_permissions)

    # Cache Management Methods

    async def _cache_permission_result(
        self,
        user_id: str,
        permission: str,
        entity_id: Optional[str],
        result: tuple[bool, str],
    ) -> None:
        """
        Cache permission check result in Redis.

        Args:
            user_id: User ID
            permission: Permission name
            entity_id: Optional entity ID
            result: (has_permission, source) tuple
        """
        if not self.redis_client or not self.redis_client.is_available:
            return

        cache_key = self.redis_client.make_key(
            "auth", "perm", user_id, permission, entity_id or "global"
        )

        cache_value = {
            "has_permission": result[0],
            "source": result[1],
        }

        await self.redis_client.set(
            cache_key,
            cache_value,
            ttl=self.config.cache_permission_ttl
        )

    async def invalidate_user_permissions(self, user_id: str) -> int:
        """
        Invalidate all permission cache entries for a user.

        Call this when:
        - User's roles change
        - User's entity memberships change
        - User is deleted

        Args:
            user_id: User ID

        Returns:
            int: Number of cache keys deleted

        Example:
            >>> deleted = await perm_service.invalidate_user_permissions(user_id)
            >>> print(f"Invalidated {deleted} cache entries")
        """
        if not self.redis_client or not self.redis_client.is_available:
            return 0

        pattern = self.redis_client.make_key("auth", "perm", user_id, "*")
        deleted = await self.redis_client.delete_pattern(pattern)

        # Publish invalidation event for other instances
        if deleted > 0:
            await self.redis_client.publish(
                self.config.redis_invalidation_channel,
                f"user:{user_id}:permissions"
            )

        return deleted

    async def invalidate_entity_permissions(self, entity_id: str) -> int:
        """
        Invalidate all permission cache entries for an entity.

        Call this when:
        - Entity permissions change
        - Entity roles change
        - Entity is deleted

        Args:
            entity_id: Entity ID

        Returns:
            int: Number of cache keys deleted

        Example:
            >>> deleted = await perm_service.invalidate_entity_permissions(entity_id)
        """
        if not self.redis_client or not self.redis_client.is_available:
            return 0

        pattern = self.redis_client.make_key("auth", "perm", "*", "*", entity_id)
        deleted = await self.redis_client.delete_pattern(pattern)

        # Publish invalidation event
        if deleted > 0:
            await self.redis_client.publish(
                self.config.redis_invalidation_channel,
                f"entity:{entity_id}:permissions"
            )

        return deleted

    async def invalidate_all_permissions(self) -> int:
        """
        Invalidate all permission cache entries.

        Call this when:
        - System-wide permission changes
        - Role definitions change globally

        Returns:
            int: Number of cache keys deleted

        Example:
            >>> deleted = await perm_service.invalidate_all_permissions()
        """
        if not self.redis_client or not self.redis_client.is_available:
            return 0

        pattern = self.redis_client.make_key("auth", "perm", "*")
        deleted = await self.redis_client.delete_pattern(pattern)

        # Publish invalidation event
        if deleted > 0:
            await self.redis_client.publish(
                self.config.redis_invalidation_channel,
                "all:permissions"
            )

        return deleted

    # ABAC (Attribute-Based Access Control) Methods - Phase 4.2

    async def check_permission_with_context(
        self,
        user_id: str,
        permission: str,
        entity_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> tuple[bool, str]:
        """
        Check permission with ABAC context evaluation.

        This method extends check_permission() to evaluate ABAC conditions.
        If roles have conditions, they must be satisfied for permissions to apply.

        Args:
            user_id: User ID
            permission: Permission name (e.g., "entity:update")
            entity_id: Optional entity ID for scoped check
            context: ABAC context (user, resource, env, time attributes)
                    If None, context will be built from database models

        Returns:
            tuple[bool, str]: (has_permission, source)
                source: "direct", "tree", "all", "superuser", or "abac_denied"

        Example:
            >>> context = {
            ...     "user": {"department": "engineering"},
            ...     "resource": {"department": "engineering", "budget": 50000}
            ... }
            >>> has_perm, source = await perm_service.check_permission_with_context(
            ...     user_id,
            ...     "entity:update",
            ...     entity_id,
            ...     context
            ... )
        """
        from outlabs_auth.models.entity import EntityModel
        from outlabs_auth.models.membership import EntityMembershipModel

        # First check basic RBAC permission
        has_rbac_perm, source = await self.check_permission(user_id, permission, entity_id)

        # If no RBAC permission, no need to check ABAC
        if not has_rbac_perm:
            return False, source

        # If user is superuser, skip ABAC checks
        user = await UserModel.get(user_id)
        if user and user.is_superuser:
            return True, "superuser"

        # Build context if not provided
        if context is None:
            context = await self.build_context_from_models(user_id, entity_id)

        # If no entity context, can't apply role conditions
        if not entity_id:
            return has_rbac_perm, source

        # Get memberships to check role conditions
        # TODO: Update to use status field when EntityMembershipModel is created
        # Should be: {"user.$id": user.id, "status": MembershipStatus.ACTIVE.value}
        memberships = await EntityMembershipModel.find(
            EntityMembershipModel.user.id == user.id,
            EntityMembershipModel.is_active == True
        ).to_list()

        # Check conditions for each applicable role
        # If ANY role that grants this permission has conditions, ALL must pass
        roles_with_permission = []
        roles_with_conditions = []

        for membership in memberships:
            if not membership.is_currently_valid():
                continue

            entity = await membership.entity.fetch() if hasattr(membership.entity, 'fetch') else membership.entity
            if not entity:
                continue

            for role_link in membership.roles:
                role = await role_link.fetch() if hasattr(role_link, 'fetch') else role_link
                if not role or not isinstance(role, RoleModel):
                    continue

                # Get permissions for this entity type (context-aware)
                entity_type = entity.entity_type
                role_permissions = role.get_permissions_for_entity_type(entity_type)

                # Check if this role grants the permission
                if permission in role_permissions or "*:*" in role_permissions:
                    roles_with_permission.append(role)

                    # If role has conditions, track it
                    if role.conditions or role.condition_groups:
                        roles_with_conditions.append(role)

        # If no roles have conditions, RBAC permission is sufficient
        if not roles_with_conditions:
            return has_rbac_perm, source

        # Evaluate conditions for all roles with conditions
        all_conditions_pass = True
        for role in roles_with_conditions:
            role_conditions_pass = await self.evaluate_role_conditions(role, context)
            if not role_conditions_pass:
                all_conditions_pass = False
                break

        if all_conditions_pass:
            return True, f"{source}_abac"
        else:
            return False, "abac_denied"

    async def build_context_from_models(
        self,
        user_id: str,
        entity_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Build ABAC context from database models.

        Args:
            user_id: User ID
            entity_id: Optional entity ID

        Returns:
            Dict[str, Any]: ABAC context with user, resource, env, time

        Example:
            >>> context = await perm_service.build_context_from_models(
            ...     user_id="507f...",
            ...     entity_id="507f..."
            ... )
            >>> context["user"]["email"]
            'user@example.com'
        """
        from outlabs_auth.models.entity import EntityModel

        # Get user model
        user = await UserModel.get(user_id)
        user_attrs = {}
        if user:
            user_attrs = {
                "id": str(user.id),
                "email": user.email,
                "is_superuser": user.is_superuser,
                "status": user.status,
                # Add metadata attributes for ABAC
                **user.metadata  # User metadata as attributes
            }

        # Get entity/resource model
        resource_attrs = {}
        if entity_id:
            entity = await EntityModel.get(entity_id)
            if entity:
                resource_attrs = {
                    "id": str(entity.id),
                    "type": entity.entity_type,
                    "name": entity.name,
                    "display_name": entity.display_name,
                    "entity_class": entity.entity_class,
                    # Add metadata as attributes
                    **entity.metadata
                }

        # Create context using policy engine
        context = self.policy_engine.create_context(
            user=user_attrs,
            resource=resource_attrs
        )

        return context

    async def evaluate_role_conditions(
        self,
        role: RoleModel,
        context: Dict[str, Any]
    ) -> bool:
        """
        Evaluate all conditions for a role.

        Args:
            role: Role model with conditions
            context: ABAC context

        Returns:
            bool: True if all conditions pass, False otherwise

        Example:
            >>> role = await RoleModel.get(role_id)
            >>> context = {"user": {"department": "engineering"}}
            >>> passes = await perm_service.evaluate_role_conditions(role, context)
        """
        # If role has condition groups, evaluate them
        if role.condition_groups:
            for group in role.condition_groups:
                if not self.policy_engine.evaluate_condition_group(group, context):
                    return False
            return True

        # Otherwise evaluate simple conditions (AND logic)
        if role.conditions:
            return self.policy_engine.evaluate_conditions(role.conditions, context)

        # No conditions means pass
        return True
