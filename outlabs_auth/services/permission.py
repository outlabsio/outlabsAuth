"""
Permission Service

Handles permission checking and management with PostgreSQL/SQLAlchemy:
- BasicPermissionService: Flat permission system (SimpleRBAC)
- EnterprisePermissionService: Hierarchical permissions (EnterpriseRBAC) - Phase 3+
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Set, Tuple
from uuid import UUID

from sqlalchemy import inspect, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import (
    InvalidInputError,
    PermissionDeniedError,
    PermissionNotFoundError,
    UserNotFoundError,
)
from outlabs_auth.models.sql.closure import EntityClosure
from outlabs_auth.models.sql.entity import Entity
from outlabs_auth.models.sql.entity_membership import EntityMembership
from outlabs_auth.models.sql.enums import DefinitionStatus, MembershipStatus, RoleScope
from outlabs_auth.models.sql.permission import (
    Permission,
    PermissionCondition,
    PermissionTag,
    PermissionTagLink,
)
from outlabs_auth.models.sql.role import ConditionGroup as SqlConditionGroup
from outlabs_auth.models.sql.role import Role, RoleEntityTypePermission, RolePermission
from outlabs_auth.models.sql.user import User
from outlabs_auth.models.sql.user_role_membership import UserRoleMembership
from outlabs_auth.services.base import BaseService
from outlabs_auth.services.policy_engine import PolicyEvaluationEngine
from outlabs_auth.schemas.abac import serialize_condition_value
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
        permission_history_service: Optional[Any] = None,
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
        self.permission_history_service = permission_history_service

    @staticmethod
    def _coerce_definition_status(value: DefinitionStatus | str) -> DefinitionStatus:
        if isinstance(value, DefinitionStatus):
            return value
        return DefinitionStatus(str(value))

    def _resolve_permission_status(
        self,
        *,
        current_status: Optional[DefinitionStatus] = None,
        status: Optional[DefinitionStatus | str] = None,
        is_active: Optional[bool] = None,
        allow_archived: bool = False,
    ) -> DefinitionStatus:
        resolved_status = current_status or DefinitionStatus.ACTIVE
        requested_status: Optional[DefinitionStatus] = None

        if status is not None:
            requested_status = self._coerce_definition_status(status)

        if is_active is not None:
            status_from_is_active = (
                DefinitionStatus.ACTIVE if is_active else DefinitionStatus.INACTIVE
            )
            if requested_status is not None and requested_status != status_from_is_active:
                raise InvalidInputError(
                    message="status and is_active cannot conflict",
                    details={
                        "status": requested_status.value,
                        "is_active": is_active,
                    },
                )
            requested_status = status_from_is_active

        if requested_status is None:
            return resolved_status

        if requested_status == DefinitionStatus.ARCHIVED and not allow_archived:
            raise InvalidInputError(
                message="Use delete to archive permissions",
                details={"status": requested_status.value},
            )

        return requested_status

    @staticmethod
    def _role_definition_is_live(role: Optional[Role]) -> bool:
        return bool(role and getattr(role, "status", DefinitionStatus.ACTIVE) == DefinitionStatus.ACTIVE)

    @staticmethod
    def _permission_definition_is_live(permission: Optional[Permission]) -> bool:
        return bool(
            permission
            and getattr(permission, "status", DefinitionStatus.ACTIVE)
            == DefinitionStatus.ACTIVE
        )

    # =========================================================================
    # Permission Checking
    # =========================================================================

    async def check_permission(
        self,
        session: AsyncSession,
        user_id: UUID,
        permission: str,
        entity_id: Optional[UUID] = None,
        resource_context: Optional[Dict[str, Any]] = None,
        env_context: Optional[Dict[str, Any]] = None,
        time_attrs: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Check if user has a specific permission.

        Args:
            session: Database session
            user_id: User UUID
            permission: Permission name (e.g., "user:create")
            entity_id: Optional entity context for EnterpriseRBAC

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

        target_entity_type: Optional[str] = None
        if entity_id is not None and self.config.enable_context_aware_roles:
            target_entity = await session.get(Entity, entity_id)
            if target_entity is not None:
                target_entity_type = target_entity.entity_type

        abac_enabled = bool(getattr(self.config, "enable_abac", False))
        use_permission_cache = self._can_use_permission_cache(
            resource_context=resource_context,
            env_context=env_context,
            time_attrs=time_attrs,
            abac_enabled=abac_enabled,
        )
        if use_permission_cache:
            cached = await self._get_cached_permission_result(
                user_id=user_id,
                permission=permission,
                entity_id=entity_id,
            )
            if cached is not None:
                self._log_permission_check(
                    user_id,
                    permission,
                    "granted" if cached else "denied",
                    start_time,
                    "cache",
                )
                return cached

        # Superusers have all permissions
        if user.is_superuser:
            self._log_permission_check(user_id, permission, "granted", start_time, "superuser")
            return True

        engine: Optional[PolicyEvaluationEngine] = PolicyEvaluationEngine() if abac_enabled else None
        context: Optional[Dict[str, Any]] = None
        if abac_enabled:
            context = engine.create_context(
                user={
                    "id": str(user.id),
                    "email": user.email,
                    "status": getattr(user.status, "value", user.status),
                    "timezone": user.timezone,
                    "locale": user.locale,
                    "is_superuser": user.is_superuser,
                },
                resource=resource_context,
                env=env_context,
                time_attrs=time_attrs,
            )
            if entity_id is not None:
                context.setdefault("resource", {})
                if isinstance(context["resource"], dict):
                    context["resource"].setdefault("entity_id", str(entity_id))

        # DD-054: Permission Scope Enforcement
        # When no entity_id is provided, only global/org-scoped roles should grant permissions.
        # Entity-local roles (scope_entity_id set) are excluded from this check.
        # When entity_id IS provided, we check entity context permissions below.
        if not abac_enabled:
            if entity_id is None:
                # No entity context: keep existing behavior and evaluate the user's
                # aggregate permissions for non-entity checks.
                user_permissions = set(
                    await self.get_user_permissions(
                        session,
                        user_id,
                        include_entity_local=False,
                    )
                )
            else:
                # Entity context: do NOT pre-grant via entity-membership role
                # aggregation, otherwise entity-local permissions can bypass
                # ancestor/descendant checks in _check_permission_in_entity().
                user_permissions = await self._get_user_role_permissions(
                    session=session,
                    user_id=user_id,
                    include_entity_local=True,
                    entity_type=target_entity_type,
                )
            if self._permission_set_allows(permission, user_permissions):
                await self._cache_permission_result(
                    use_cache=use_permission_cache,
                    user_id=user_id,
                    permission=permission,
                    entity_id=entity_id,
                    result=True,
                )
                self._log_permission_check(user_id, permission, "granted", start_time, "global_match")
                return True
        else:
            if await self._check_permission_via_user_roles_with_abac(
                session=session,
                user_id=user_id,
                permission=permission,
                context=context or {},
                engine=engine,
                include_entity_local=(entity_id is not None),
                entity_type=target_entity_type,
            ):
                self._log_permission_check(user_id, permission, "granted", start_time, "global_match_abac")
                return True

        # EnterpriseRBAC check in an entity context
        # This checks permissions via entity memberships (EntityMembership)
        if entity_id is not None:
            if await self._check_permission_in_entity(
                session=session,
                user_id=user_id,
                permission=permission,
                entity_id=entity_id,
                entity_type=target_entity_type,
                context=context,
                engine=engine,
            ):
                await self._cache_permission_result(
                    use_cache=use_permission_cache,
                    user_id=user_id,
                    permission=permission,
                    entity_id=entity_id,
                    result=True,
                )
                self._log_permission_check(user_id, permission, "granted", start_time, "entity_match")
                return True

        # Permission denied
        await self._cache_permission_result(
            use_cache=use_permission_cache,
            user_id=user_id,
            permission=permission,
            entity_id=entity_id,
            result=False,
        )
        self._log_permission_check(user_id, permission, "denied", start_time, "no_permission")
        return False

    # =========================================================================
    # EnterpriseRBAC: entity context + tree permissions
    # =========================================================================

    @staticmethod
    def _parse_permission_name(name: str) -> Tuple[str, str, Optional[str]]:
        """
        Parse `resource:action[_scope]` into (resource, action, scope).

        Scope is the last underscore segment when it's one of: tree, all, own.
        """
        if ":" not in name:
            return name, "*", None

        resource, action_part = name.split(":", 1)
        if "_" not in action_part:
            return resource, action_part, None

        action_base, maybe_scope = action_part.rsplit("_", 1)
        if maybe_scope in ("tree", "all", "own"):
            return resource, action_base, maybe_scope
        return resource, action_part, None

    @classmethod
    def _permission_set_allows(cls, required: str, granted: Set[str]) -> bool:
        """
        Check whether a set of permission *names* grants a required permission name.

        Rules:
        - `*:*` grants everything.
        - Exact match grants.
        - `resource:*` grants all actions/scopes for that resource.
        - `_all` scope is treated as a superset of non-scoped and `_tree`.
        - `_tree` is treated as a superset of non-scoped (within entity hierarchy rules).
        """
        if "*:*" in granted or required in granted:
            return True

        resource, action, scope = cls._parse_permission_name(required)
        if f"{resource}:*" in granted:
            return True

        base = f"{resource}:{action}"
        all_variant = f"{base}_all"

        # `_all` is always a superset
        if all_variant in granted:
            return True

        # `_tree` is a superset of the base (non-scoped) permission
        if scope is None:
            tree_variant = f"{base}_tree"
            if tree_variant in granted:
                return True

        return False

    @classmethod
    def _permission_set_allows_from_ancestor(cls, required: str, granted: Set[str]) -> bool:
        """
        Like `_permission_set_allows`, but for permissions inherited from ancestors.

        Only `_tree`/`_all` (or `*:*`) permissions propagate to descendants.
        """
        if "*:*" in granted:
            return True

        resource, action, scope = cls._parse_permission_name(required)
        base = f"{resource}:{action}"

        if scope == "all":
            return f"{base}_all" in granted

        if scope == "tree":
            return f"{base}_tree" in granted or f"{base}_all" in granted

        # Non-scoped permission required: need `_tree` or `_all` upstream.
        return f"{base}_tree" in granted or f"{base}_all" in granted

    async def _check_permission_in_entity(
        self,
        session: AsyncSession,
        user_id: UUID,
        permission: str,
        entity_id: UUID,
        entity_type: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        engine: Optional[PolicyEvaluationEngine] = None,
    ) -> bool:
        """
        EnterpriseRBAC permission evaluation:
        - permissions granted by membership roles on the target entity
        - inherited tree permissions via membership roles on ancestor entities (closure table)
        - respects entity-local role scope (entity_only vs hierarchy)
        """
        # Resolve ancestors (including self) via closure table.
        ancestors_stmt = select(EntityClosure.ancestor_id, EntityClosure.depth).where(
            EntityClosure.descendant_id == entity_id
        )
        ancestors_result = await session.execute(ancestors_stmt)
        ancestor_rows = ancestors_result.all()
        if not ancestor_rows:
            return False

        depth_by_ancestor: Dict[UUID, int] = {row[0]: row[1] for row in ancestor_rows}
        ancestor_ids = list(depth_by_ancestor.keys())

        # Load memberships in any ancestor entity with roles+permissions.
        memberships_stmt = (
            select(EntityMembership)
            .options(
                selectinload(EntityMembership.roles)
                .selectinload(Role.permissions)
                .selectinload(Permission.conditions),
                selectinload(EntityMembership.roles).selectinload(Role.conditions),
                selectinload(EntityMembership.roles)
                .selectinload(Role.entity_type_permissions)
                .selectinload(RoleEntityTypePermission.permission)
                .selectinload(Permission.conditions),
            )
            .where(
                EntityMembership.user_id == user_id,
                EntityMembership.entity_id.in_(ancestor_ids),
                EntityMembership.status == MembershipStatus.ACTIVE,
            )
        )
        memberships_result = await session.execute(memberships_stmt)
        memberships = memberships_result.scalars().all()

        for membership in memberships:
            if not membership.can_grant_permissions():
                continue

            membership_depth = depth_by_ancestor.get(membership.entity_id)
            if membership_depth is None:
                continue

            # membership_depth == 0 means membership is at target entity (direct)
            # membership_depth > 0 means membership is at an ancestor (inherited)
            is_direct_membership = membership_depth == 0

            for role in membership.roles:
                if not self._role_definition_is_live(role):
                    continue

                # Check if entity-local role scope allows granting at this entity
                if not self._role_can_grant_at_entity(role, membership.entity_id, entity_id, is_direct_membership):
                    continue

                granted = self._get_role_permission_names_for_context(role, entity_type)

                is_match = (
                    self._permission_set_allows(permission, granted)
                    if is_direct_membership
                    else self._permission_set_allows_from_ancestor(permission, granted)
                )
                if not is_match:
                    continue

                if engine and context is not None:
                    if not await self._abac_allows_role_and_permission(
                        session=session,
                        role=role,
                        required_permission=permission,
                        entity_type=entity_type,
                        context=context,
                        engine=engine,
                    ):
                        continue

                return True

        return False

    @staticmethod
    def _role_can_grant_at_entity(
        role: Role,
        membership_entity_id: UUID,
        target_entity_id: UUID,
        is_direct_membership: bool,
    ) -> bool:
        """
        Check if a role can grant permissions at the target entity.

        For entity-local roles:
        - scope=entity_only: Only grants at the scope_entity (membership must be at target)
        - scope=hierarchy: Grants at scope_entity and all descendants

        Non-entity-local roles (scope_entity_id=None) follow normal inheritance.

        Args:
            role: Role to check
            membership_entity_id: Entity where the membership exists
            target_entity_id: Entity where permission is being checked
            is_direct_membership: True if membership is at target entity

        Returns:
            bool: True if role can grant permissions at target entity
        """
        # Non-entity-local roles follow normal inheritance rules
        if role.scope_entity_id is None:
            return True

        # Entity-local role with scope=entity_only only grants at scope_entity
        if role.scope == RoleScope.ENTITY_ONLY:
            # The role only grants permissions at membership_entity_id
            # This is valid only when checking permission at that same entity
            return is_direct_membership and membership_entity_id == target_entity_id

        # Entity-local role with scope=hierarchy grants at scope_entity and descendants
        # Since the membership is in an ancestor of target, and the role's scope_entity
        # is an ancestor (or same) as the membership entity, the permission cascades.
        return True

    async def _check_permission_via_user_roles_with_abac(
        self,
        *,
        session: AsyncSession,
        user_id: UUID,
        permission: str,
        context: Dict[str, Any],
        engine: PolicyEvaluationEngine,
        include_entity_local: bool = True,
        entity_type: Optional[str] = None,
    ) -> bool:
        """
        Check permission via user roles with ABAC evaluation.

        Args:
            session: Database session
            user_id: User UUID
            permission: Permission name to check
            context: ABAC evaluation context
            engine: Policy evaluation engine
            include_entity_local: If False, exclude entity-local roles (DD-054)

        Returns:
            True if permission granted, False otherwise
        """
        stmt = (
            select(UserRoleMembership)
            .options(
                selectinload(UserRoleMembership.role)
                .selectinload(Role.permissions)
                .selectinload(Permission.conditions),
                selectinload(UserRoleMembership.role).selectinload(Role.conditions),
                selectinload(UserRoleMembership.role)
                .selectinload(Role.entity_type_permissions)
                .selectinload(RoleEntityTypePermission.permission)
                .selectinload(Permission.conditions),
            )
            .where(
                UserRoleMembership.user_id == user_id,
                UserRoleMembership.status == MembershipStatus.ACTIVE,
            )
        )
        result = await session.execute(stmt)
        memberships = result.scalars().all()

        for membership in memberships:
            if not membership.can_grant_permissions():
                continue

            role = membership.role
            if not self._role_definition_is_live(role):
                continue

            # DD-054: Filter out entity-local roles when include_entity_local=False
            if not include_entity_local and role.scope_entity_id is not None:
                continue

            granted = self._get_role_permission_names_for_context(role, entity_type)
            if not self._permission_set_allows(permission, granted):
                continue

            if not await self._abac_allows_role_and_permission(
                session=session,
                role=role,
                required_permission=permission,
                entity_type=entity_type,
                context=context,
                engine=engine,
            ):
                continue

            return True

        return False

    async def _abac_allows_role_and_permission(
        self,
        *,
        session: AsyncSession,
        role: Role,
        required_permission: str,
        entity_type: Optional[str],
        context: Dict[str, Any],
        engine: PolicyEvaluationEngine,
    ) -> bool:
        role_conditions = list(role.conditions or []) if self._relationship_is_loaded(role, "conditions") else []
        perms = self._get_role_permissions_for_context(role, entity_type)
        unloaded_permission_ids = [
            permission.id
            for permission in perms
            if permission is not None and not self._relationship_is_loaded(permission, "conditions")
        ]
        if unloaded_permission_ids:
            perm_stmt = (
                select(Permission)
                .options(selectinload(Permission.conditions))
                .where(Permission.id.in_(unloaded_permission_ids))
            )
            perm_result = await session.execute(perm_stmt)
            permission_map = {permission.id: permission for permission in perm_result.scalars().all()}
            perms = [
                permission_map.get(permission.id, permission) if permission is not None else None
                for permission in perms
            ]

        matching_perms = [p for p in perms if p and self._permission_set_allows(required_permission, {p.name})]
        if not matching_perms:
            return False

        group_ids: Set[UUID] = set()
        for cond in role_conditions:
            if getattr(cond, "condition_group_id", None):
                group_ids.add(cond.condition_group_id)
        for p in matching_perms:
            for cond in p.conditions or []:
                if getattr(cond, "condition_group_id", None):
                    group_ids.add(cond.condition_group_id)

        group_ops: Dict[Optional[str], str] = {}
        if group_ids:
            groups_stmt = select(SqlConditionGroup).where(SqlConditionGroup.id.in_(list(group_ids)))
            groups_result = await session.execute(groups_stmt)
            groups = groups_result.scalars().all()
            for g in groups:
                group_ops[str(g.id)] = g.operator

        if not engine.evaluate_sql_conditions(conditions=role_conditions, group_ops=group_ops, context=context):
            return False

        for p in matching_perms:
            if engine.evaluate_sql_conditions(conditions=(p.conditions or []), group_ops=group_ops, context=context):
                return True

        return False

    @staticmethod
    def _relationship_is_loaded(instance: Any, attribute: str) -> bool:
        return attribute not in inspect(instance).unloaded

    async def _get_user_role_permissions(
        self,
        *,
        session: AsyncSession,
        user_id: UUID,
        include_entity_local: bool = True,
        entity_type: Optional[str] = None,
    ) -> Set[str]:
        """
        Collect permission names from active UserRoleMembership links only.

        This excludes EntityMembership role grants by design.
        """
        stmt = (
            select(UserRoleMembership)
            .options(
                selectinload(UserRoleMembership.role)
                .selectinload(Role.permissions)
                .selectinload(Permission.conditions),
                selectinload(UserRoleMembership.role)
                .selectinload(Role.entity_type_permissions)
                .selectinload(RoleEntityTypePermission.permission),
            )
            .where(
                UserRoleMembership.user_id == user_id,
                UserRoleMembership.status == MembershipStatus.ACTIVE,
            )
        )
        result = await session.execute(stmt)
        memberships = result.scalars().all()

        permissions: Set[str] = set()
        for membership in memberships:
            if not membership.is_currently_valid():
                continue
            role = membership.role
            if not self._role_definition_is_live(role):
                continue
            if not include_entity_local and role.scope_entity_id is not None:
                continue
            for perm in self._get_role_permissions_for_context(role, entity_type):
                permissions.add(perm.name)
        return permissions

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
            duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
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
        include_entity_local: bool = True,
        entity_type: Optional[str] = None,
    ) -> List[str]:
        """
        Get all permissions for a user.

        Aggregates permissions from all assigned roles via:
        - UserRoleMembership (SimpleRBAC)
        - EntityMembership roles (EnterpriseRBAC)

        Args:
            session: Database session
            user_id: User UUID
            include_entity_local: If False, exclude permissions from entity-local roles
                (roles where scope_entity_id is set). Defaults to True for backwards
                compatibility. Set to False when checking permissions without entity context.

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
                selectinload(UserRoleMembership.role)
                .selectinload(Role.permissions)
                .selectinload(Permission.conditions),
                selectinload(UserRoleMembership.role)
                .selectinload(Role.entity_type_permissions)
                .selectinload(RoleEntityTypePermission.permission),
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
            if not self._role_definition_is_live(role):
                continue

            # DD-054: Filter out entity-local roles when include_entity_local=False
            # Entity-local roles have scope_entity_id set and should only grant
            # permissions when checked within an entity context.
            if not include_entity_local and role.scope_entity_id is not None:
                continue

            for perm in self._get_role_permissions_for_context(role, entity_type):
                all_permissions.add(perm.name)

        # Get active entity memberships with roles eagerly loaded
        # EnterpriseRBAC stores role assignments via entity membership, so these
        # permissions must be included for effective user permission resolution.
        entity_stmt = (
            select(EntityMembership)
            .options(
                selectinload(EntityMembership.roles)
                .selectinload(Role.permissions)
                .selectinload(Permission.conditions),
                selectinload(EntityMembership.roles)
                .selectinload(Role.entity_type_permissions)
                .selectinload(RoleEntityTypePermission.permission),
            )
            .where(
                EntityMembership.user_id == user_id,
                EntityMembership.status == MembershipStatus.ACTIVE,
            )
        )
        entity_result = await session.execute(entity_stmt)
        entity_memberships = entity_result.scalars().all()

        for membership in entity_memberships:
            if not membership.can_grant_permissions():
                continue

            for role in membership.roles:
                if not self._role_definition_is_live(role):
                    continue

                # DD-054: Filter out entity-local roles when include_entity_local=False
                if not include_entity_local and role.scope_entity_id is not None:
                    continue

                for perm in self._get_role_permissions_for_context(role, entity_type):
                    all_permissions.add(perm.name)

        return list(all_permissions)

    async def _get_global_role_permissions(
        self,
        session: AsyncSession,
        user_id: UUID,
    ) -> Set[str]:
        """
        Get permissions from global and org-scoped roles only.

        This excludes entity-local roles (where scope_entity_id is set).
        Used when checking permissions without an entity context.

        DD-054: Permission Scope Enforcement
        - Global roles (is_global=true): Always included
        - Org-scoped roles (root_entity_id set, scope_entity_id=NULL): Always included
        - Entity-local roles (scope_entity_id set): EXCLUDED

        Args:
            session: Database session
            user_id: User UUID

        Returns:
            Set of permission names from global/org-scoped roles
        """
        # Use the existing method with include_entity_local=False
        permissions = await self.get_user_permissions(session, user_id, include_entity_local=False)
        return set(permissions)

    def _get_role_permissions_for_context(
        self,
        role: Role,
        entity_type: Optional[str] = None,
    ) -> List[Permission]:
        if not self._role_definition_is_live(role):
            return []

        if not self.config.enable_context_aware_roles or not entity_type:
            return [
                permission
                for permission in (role.permissions or [])
                if self._permission_definition_is_live(permission)
            ]

        normalized_entity_type = entity_type.lower()
        matching_overrides = [
            entry.permission
            for entry in (role.entity_type_permissions or [])
            if entry.permission and entry.entity_type.lower() == normalized_entity_type
        ]
        overrides = [
            permission
            for permission in matching_overrides
            if self._permission_definition_is_live(permission)
        ]
        if matching_overrides:
            return overrides
        if overrides:
            return overrides
        return [
            permission
            for permission in (role.permissions or [])
            if self._permission_definition_is_live(permission)
        ]

    def _get_role_permission_names_for_context(
        self,
        role: Role,
        entity_type: Optional[str] = None,
    ) -> Set[str]:
        return {
            permission.name
            for permission in self._get_role_permissions_for_context(role, entity_type)
            if permission and permission.name
        }

    def _can_use_permission_cache(
        self,
        *,
        resource_context: Optional[Dict[str, Any]],
        env_context: Optional[Dict[str, Any]],
        time_attrs: Optional[Dict[str, Any]],
        abac_enabled: bool,
    ) -> bool:
        return bool(
            getattr(self.config, "enable_caching", False)
            and getattr(self, "cache_service", None) is not None
            and not abac_enabled
            and not resource_context
            and not env_context
            and not time_attrs
        )

    async def _get_cached_permission_result(
        self,
        *,
        user_id: UUID,
        permission: str,
        entity_id: Optional[UUID],
    ) -> Optional[bool]:
        cache_service = getattr(self, "cache_service", None)
        if cache_service is None:
            return None
        return await cache_service.get_permission_check(
            str(user_id),
            permission,
            str(entity_id) if entity_id is not None else None,
        )

    async def _cache_permission_result(
        self,
        *,
        use_cache: bool,
        user_id: UUID,
        permission: str,
        entity_id: Optional[UUID],
        result: bool,
    ) -> None:
        if not use_cache:
            return
        cache_service = getattr(self, "cache_service", None)
        if cache_service is None:
            return
        await cache_service.set_permission_check(
            str(user_id),
            permission,
            result,
            str(entity_id) if entity_id is not None else None,
        )

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
        status: Optional[DefinitionStatus | str] = None,
        is_active: Optional[bool] = None,
        tags: Optional[List[str]] = None,
        created_by_id: Optional[UUID] = None,
    ) -> Permission:
        """
        Create a new permission.

        Args:
            session: Database session
            name: Permission name (e.g., "invoice:approve")
            display_name: Human-readable name
            description: Permission description
            is_system: Whether this is a system permission
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

        resolved_status = self._resolve_permission_status(
            status=status,
            is_active=is_active,
        )

        # Create permission (auto-parses resource/action/scope in __init__)
        permission = Permission(
            name=name,
            display_name=display_name,
            description=description,
            is_system=is_system,
            status=resolved_status,
            is_active=resolved_status == DefinitionStatus.ACTIVE,
        )

        await self.create(session, permission)

        if tags:
            await self.set_permission_tags(
                session,
                permission.id,
                tags,
                changed_by_id=created_by_id,
                record_history=False,
            )

        await self._invalidate_all_permissions_cache()
        current_permission = (
            await self.get_permission_by_id(
                session,
                permission.id,
                load_tags=True,
                include_archived=True,
            )
            or permission
        )
        await self._record_permission_definition_history_event(
            session,
            permission=current_permission,
            event_type="created",
            event_source="permission_service.create_permission",
            actor_user_id=created_by_id,
            after=await self._build_permission_definition_snapshot(
                session,
                current_permission,
            ),
        )
        return current_permission

    async def get_permission_by_id(
        self,
        session: AsyncSession,
        permission_id: UUID,
        load_tags: bool = False,
        include_archived: bool = False,
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
        stmt = select(Permission).where(Permission.id == permission_id)
        if not include_archived:
            stmt = stmt.where(Permission.status != DefinitionStatus.ARCHIVED)

        options = []
        if load_tags:
            options.append(selectinload(Permission.tags))
        if options:
            stmt = stmt.options(*options)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_permission_by_name(
        self,
        session: AsyncSession,
        name: str,
        include_archived: bool = True,
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
        filters = [Permission.name == name]
        if not include_archived:
            filters.append(Permission.status != DefinitionStatus.ARCHIVED)
        return await self.get_one(session, *filters)

    async def update_permission(
        self,
        session: AsyncSession,
        permission_id: UUID,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[DefinitionStatus | str] = None,
        is_active: Optional[bool] = None,
        tags: Optional[List[str]] = None,
        changed_by_id: Optional[UUID] = None,
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
        permission = await self.get_permission_by_id(
            session,
            permission_id,
            load_tags=True,
        )
        if not permission:
            raise PermissionNotFoundError(
                message="Permission not found",
                details={"permission_id": str(permission_id)},
            )

        previous_snapshot = await self._build_permission_definition_snapshot(
            session,
            permission,
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

        next_status = self._resolve_permission_status(
            current_status=permission.status,
            status=status,
            is_active=is_active,
        )
        permission.status = next_status
        permission.is_active = next_status == DefinitionStatus.ACTIVE

        await self.update(session, permission)

        if tags is not None:
            await self.set_permission_tags(
                session,
                permission_id,
                tags,
                changed_by_id=changed_by_id,
                record_history=False,
            )

        await self._invalidate_all_permissions_cache()
        current_permission = (
            await self.get_permission_by_id(session, permission_id, load_tags=True)
            or permission
        )
        current_snapshot = await self._build_permission_definition_snapshot(
            session,
            current_permission,
        )
        changed_fields = self._changed_permission_definition_fields(
            previous_snapshot,
            current_snapshot,
        )
        if changed_fields:
            await self._record_permission_definition_history_event(
                session,
                permission=current_permission,
                event_type="updated",
                event_source="permission_service.update_permission",
                actor_user_id=changed_by_id,
                before=previous_snapshot,
                after=current_snapshot,
                metadata={"changed_fields": changed_fields},
            )
        return current_permission

    async def set_permission_tags(
        self,
        session: AsyncSession,
        permission_id: UUID,
        tags: List[str],
        changed_by_id: Optional[UUID] = None,
        record_history: bool = True,
        event_source: str = "permission_service.set_permission_tags",
    ) -> Permission:
        """
        Replace a permission's tag set, creating tags if needed.
        """
        permission = await self.get_permission_by_id(session, permission_id, load_tags=True)
        if not permission:
            raise PermissionNotFoundError(
                message="Permission not found",
                details={"permission_id": str(permission_id)},
            )

        previous_snapshot = await self._build_permission_definition_snapshot(
            session,
            permission,
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
            await self._invalidate_all_permissions_cache()
            current_permission = (
                await self.get_permission_by_id(session, permission_id, load_tags=True)
                or permission
            )
            current_snapshot = await self._build_permission_definition_snapshot(
                session,
                current_permission,
            )
            changed_fields = self._changed_permission_definition_fields(
                previous_snapshot,
                current_snapshot,
            )
            if record_history and changed_fields:
                await self._record_permission_definition_history_event(
                    session,
                    permission=current_permission,
                    event_type="updated",
                    event_source=event_source,
                    actor_user_id=changed_by_id,
                    before=previous_snapshot,
                    after=current_snapshot,
                    metadata={"changed_fields": changed_fields},
                )
            return current_permission

        # Load/create tag models
        stmt = select(PermissionTag).where(PermissionTag.name.in_(normalized))
        result = await session.execute(stmt)
        existing_tags = {t.name: t for t in result.scalars().all()}

        tag_models: List[PermissionTag] = []
        for tag_name in normalized:
            tag_model = existing_tags.get(tag_name)
            if not tag_model:
                tag_model = PermissionTag(name=tag_name)
                session.add(tag_model)
                await session.flush()
            tag_models.append(tag_model)

        permission.tags = tag_models
        await self.update(session, permission)
        await self._invalidate_all_permissions_cache()
        current_permission = (
            await self.get_permission_by_id(session, permission_id, load_tags=True)
            or permission
        )
        current_snapshot = await self._build_permission_definition_snapshot(
            session,
            current_permission,
        )
        changed_fields = self._changed_permission_definition_fields(
            previous_snapshot,
            current_snapshot,
        )
        if record_history and changed_fields:
            await self._record_permission_definition_history_event(
                session,
                permission=current_permission,
                event_type="updated",
                event_source=event_source,
                actor_user_id=changed_by_id,
                before=previous_snapshot,
                after=current_snapshot,
                metadata={"changed_fields": changed_fields},
            )
        return current_permission

    async def delete_permission(
        self,
        session: AsyncSession,
        permission_id: UUID,
        deleted_by_id: Optional[UUID] = None,
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
        permission = await self.get_permission_by_id(
            session,
            permission_id,
            load_tags=True,
            include_archived=True,
        )
        if not permission or permission.status == DefinitionStatus.ARCHIVED:
            return False

        previous_snapshot = await self._build_permission_definition_snapshot(
            session,
            permission,
        )

        if permission.is_system:
            raise InvalidInputError(
                message="Cannot delete system permission",
                details={
                    "permission_id": str(permission_id),
                    "permission_name": permission.name,
                },
            )

        permission.status = DefinitionStatus.ARCHIVED
        permission.is_active = False
        await self.update(session, permission)

        current_permission = (
            await self.get_permission_by_id(
                session,
                permission_id,
                load_tags=True,
                include_archived=True,
            )
            or permission
        )
        current_snapshot = await self._build_permission_definition_snapshot(
            session,
            current_permission,
        )
        await self._record_permission_definition_history_event(
            session,
            permission=current_permission,
            event_type="deleted",
            event_source="permission_service.delete_permission",
            actor_user_id=deleted_by_id,
            before=previous_snapshot,
            after=current_snapshot,
            metadata={"archived": True},
        )
        await self._invalidate_all_permissions_cache()
        return True

    async def create_permission_condition_group(
        self,
        session: AsyncSession,
        permission_id: UUID,
        *,
        operator: str = "AND",
        description: Optional[str] = None,
        changed_by_id: Optional[UUID] = None,
    ) -> SqlConditionGroup:
        permission = await self._get_mutable_permission_for_definition_edit(
            session,
            permission_id,
        )
        previous_snapshot = await self._build_permission_definition_snapshot(
            session,
            permission,
        )

        group = SqlConditionGroup(
            permission_id=permission_id,
            operator=operator,
            description=description,
        )
        session.add(group)
        await session.flush()

        current_snapshot = await self._build_permission_definition_snapshot(
            session,
            permission,
        )
        await self._record_permission_definition_history_event(
            session,
            permission=permission,
            event_type="condition_group_created",
            event_source="permission_service.create_condition_group",
            actor_user_id=changed_by_id,
            before=previous_snapshot,
            after=current_snapshot,
            metadata={
                "condition_group": self._build_condition_group_snapshot(group),
            },
        )
        return group

    async def update_permission_condition_group(
        self,
        session: AsyncSession,
        permission_id: UUID,
        group_id: UUID,
        *,
        fields_set: Set[str],
        operator: Optional[str] = None,
        description: Optional[str] = None,
        changed_by_id: Optional[UUID] = None,
    ) -> Optional[SqlConditionGroup]:
        permission = await self._get_mutable_permission_for_definition_edit(
            session,
            permission_id,
        )
        group = await session.get(SqlConditionGroup, group_id)
        if not group or group.permission_id != permission_id:
            return None

        previous_snapshot = await self._build_permission_definition_snapshot(
            session,
            permission,
        )
        previous_group_snapshot = self._build_condition_group_snapshot(group)

        if "operator" in fields_set and operator is not None:
            group.operator = operator
        if "description" in fields_set:
            group.description = description

        await session.flush()

        current_snapshot = await self._build_permission_definition_snapshot(
            session,
            permission,
        )
        current_group_snapshot = self._build_condition_group_snapshot(group)
        changed_fields = self._changed_snapshot_fields(
            previous_group_snapshot,
            current_group_snapshot,
            ["operator", "description"],
        )
        if changed_fields:
            await self._record_permission_definition_history_event(
                session,
                permission=permission,
                event_type="condition_group_updated",
                event_source="permission_service.update_condition_group",
                actor_user_id=changed_by_id,
                before=previous_snapshot,
                after=current_snapshot,
                metadata={
                    "changed_fields": changed_fields,
                    "before_group": previous_group_snapshot,
                    "after_group": current_group_snapshot,
                },
            )
        return group

    async def delete_permission_condition_group(
        self,
        session: AsyncSession,
        permission_id: UUID,
        group_id: UUID,
        *,
        changed_by_id: Optional[UUID] = None,
    ) -> bool:
        permission = await self._get_mutable_permission_for_definition_edit(
            session,
            permission_id,
        )
        group = await session.get(SqlConditionGroup, group_id)
        if not group or group.permission_id != permission_id:
            return False

        previous_snapshot = await self._build_permission_definition_snapshot(
            session,
            permission,
        )
        deleted_group_snapshot = self._build_condition_group_snapshot(group)

        condition_stmt = select(PermissionCondition).where(
            PermissionCondition.permission_id == permission_id,
            PermissionCondition.condition_group_id == group_id,
        )
        condition_result = await session.execute(condition_stmt)
        deleted_conditions = [
            self._build_permission_condition_snapshot(condition)
            for condition in condition_result.scalars().all()
        ]

        await session.delete(group)
        await session.flush()

        current_snapshot = await self._build_permission_definition_snapshot(
            session,
            permission,
        )
        await self._record_permission_definition_history_event(
            session,
            permission=permission,
            event_type="condition_group_deleted",
            event_source="permission_service.delete_condition_group",
            actor_user_id=changed_by_id,
            before=previous_snapshot,
            after=current_snapshot,
            metadata={
                "deleted_group": deleted_group_snapshot,
                "deleted_conditions": deleted_conditions,
            },
        )
        return True

    async def create_permission_condition(
        self,
        session: AsyncSession,
        permission_id: UUID,
        *,
        attribute: str,
        operator: str,
        value: Optional[Any],
        value_type: str,
        description: Optional[str] = None,
        condition_group_id: Optional[UUID] = None,
        changed_by_id: Optional[UUID] = None,
    ) -> PermissionCondition:
        permission = await self._get_mutable_permission_for_definition_edit(
            session,
            permission_id,
        )
        if condition_group_id is not None:
            group = await session.get(SqlConditionGroup, condition_group_id)
            if not group or group.permission_id != permission_id:
                raise InvalidInputError(
                    message="Invalid condition_group_id",
                    details={
                        "permission_id": str(permission_id),
                        "condition_group_id": str(condition_group_id),
                    },
                )

        previous_snapshot = await self._build_permission_definition_snapshot(
            session,
            permission,
        )

        condition = PermissionCondition(
            permission_id=permission_id,
            condition_group_id=condition_group_id,
            attribute=attribute,
            operator=operator,
            value=serialize_condition_value(value, value_type),
            value_type=value_type,
            description=description,
        )
        session.add(condition)
        await session.flush()

        current_snapshot = await self._build_permission_definition_snapshot(
            session,
            permission,
        )
        await self._record_permission_definition_history_event(
            session,
            permission=permission,
            event_type="condition_created",
            event_source="permission_service.create_condition",
            actor_user_id=changed_by_id,
            before=previous_snapshot,
            after=current_snapshot,
            metadata={
                "condition": self._build_permission_condition_snapshot(condition),
            },
        )
        return condition

    async def update_permission_condition(
        self,
        session: AsyncSession,
        permission_id: UUID,
        condition_id: UUID,
        *,
        fields_set: Set[str],
        condition_group_id: Optional[UUID] = None,
        attribute: Optional[str] = None,
        operator: Optional[str] = None,
        value: Optional[Any] = None,
        value_type: Optional[str] = None,
        description: Optional[str] = None,
        changed_by_id: Optional[UUID] = None,
    ) -> Optional[PermissionCondition]:
        permission = await self._get_mutable_permission_for_definition_edit(
            session,
            permission_id,
        )
        condition = await session.get(PermissionCondition, condition_id)
        if not condition or condition.permission_id != permission_id:
            return None

        if "condition_group_id" in fields_set and condition_group_id is not None:
            group = await session.get(SqlConditionGroup, condition_group_id)
            if not group or group.permission_id != permission_id:
                raise InvalidInputError(
                    message="Invalid condition_group_id",
                    details={
                        "permission_id": str(permission_id),
                        "condition_group_id": str(condition_group_id),
                    },
                )

        previous_snapshot = await self._build_permission_definition_snapshot(
            session,
            permission,
        )
        previous_condition_snapshot = self._build_permission_condition_snapshot(condition)

        if "condition_group_id" in fields_set:
            condition.condition_group_id = condition_group_id
        if "attribute" in fields_set and attribute is not None:
            condition.attribute = attribute
        if "operator" in fields_set and operator is not None:
            condition.operator = operator
        if "value_type" in fields_set and value_type is not None:
            condition.value_type = value_type
        if "value" in fields_set or "value_type" in fields_set:
            condition.value = serialize_condition_value(
                value,
                value_type or condition.value_type,
            )
        if "description" in fields_set:
            condition.description = description

        await session.flush()

        current_snapshot = await self._build_permission_definition_snapshot(
            session,
            permission,
        )
        current_condition_snapshot = self._build_permission_condition_snapshot(condition)
        changed_fields = self._changed_snapshot_fields(
            previous_condition_snapshot,
            current_condition_snapshot,
            [
                "condition_group_id",
                "attribute",
                "operator",
                "value",
                "value_type",
                "description",
            ],
        )
        if changed_fields:
            await self._record_permission_definition_history_event(
                session,
                permission=permission,
                event_type="condition_updated",
                event_source="permission_service.update_condition",
                actor_user_id=changed_by_id,
                before=previous_snapshot,
                after=current_snapshot,
                metadata={
                    "changed_fields": changed_fields,
                    "before_condition": previous_condition_snapshot,
                    "after_condition": current_condition_snapshot,
                },
            )
        return condition

    async def delete_permission_condition(
        self,
        session: AsyncSession,
        permission_id: UUID,
        condition_id: UUID,
        *,
        changed_by_id: Optional[UUID] = None,
    ) -> bool:
        permission = await self._get_mutable_permission_for_definition_edit(
            session,
            permission_id,
        )
        condition = await session.get(PermissionCondition, condition_id)
        if not condition or condition.permission_id != permission_id:
            return False

        previous_snapshot = await self._build_permission_definition_snapshot(
            session,
            permission,
        )
        deleted_condition_snapshot = self._build_permission_condition_snapshot(condition)

        await session.delete(condition)
        await session.flush()

        current_snapshot = await self._build_permission_definition_snapshot(
            session,
            permission,
        )
        await self._record_permission_definition_history_event(
            session,
            permission=permission,
            event_type="condition_deleted",
            event_source="permission_service.delete_condition",
            actor_user_id=changed_by_id,
            before=previous_snapshot,
            after=current_snapshot,
            metadata={
                "deleted_condition": deleted_condition_snapshot,
            },
        )
        return True

    async def list_permissions(
        self,
        session: AsyncSession,
        page: int = 1,
        limit: int = 50,
        resource: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> Tuple[List[Permission], int]:
        """
        List permissions with pagination.

        Args:
            session: Database session
            page: Page number (1-indexed)
            limit: Results per page
            resource: Filter by resource (e.g., "user")
            is_active: Filter by active status
        Returns:
            Tuple of (permissions, total_count)
        """
        filters = [Permission.status != DefinitionStatus.ARCHIVED]
        if resource:
            filters.append(Permission.resource == resource)
        if is_active is not None:
            filters.append(
                Permission.status
                == (DefinitionStatus.ACTIVE if is_active else DefinitionStatus.INACTIVE)
            )

        total_count = await self.count(session, *filters)

        skip = (page - 1) * limit
        permissions = await self.get_many(
            session,
            *filters,
            skip=skip,
            limit=limit,
            order_by=Permission.name,
            options=[selectinload(Permission.tags)],
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
            Permission.status != DefinitionStatus.ARCHIVED,
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
            .where(
                PermissionTag.name == tag_name,
                Permission.status != DefinitionStatus.ARCHIVED,
            )
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
            .where(
                RolePermission.role_id == role_id,
                Permission.status != DefinitionStatus.ARCHIVED,
            )
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
    ) -> List[Permission]:
        """
        Create multiple permissions at once.

        Args:
            session: Database session
            permissions_data: List of dicts with name, display_name, description
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
            )
            session.add(permission)
            created.append(permission)

        await session.flush()

        # Refresh all to get IDs
        for perm in created:
            await session.refresh(perm)

        await self._invalidate_all_permissions_cache()
        return created

    async def _invalidate_all_permissions_cache(self) -> None:
        cache_service = getattr(self, "cache_service", None)
        if cache_service is not None:
            await cache_service.publish_all_permissions_invalidation()

    async def _record_permission_definition_history_event(
        self,
        session: AsyncSession,
        *,
        permission: Permission,
        event_type: str,
        event_source: str,
        actor_user_id: Optional[UUID] = None,
        before: Optional[Dict[str, Any]] = None,
        after: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        occurred_at: Optional[datetime] = None,
    ) -> None:
        if self.permission_history_service is None:
            return

        snapshot = await self._build_permission_definition_snapshot(session, permission)
        await self.permission_history_service.record_event(
            session,
            permission_id=permission.id,
            event_type=event_type,
            event_source=event_source,
            actor_user_id=actor_user_id,
            snapshot=snapshot,
            before=before,
            after=after,
            metadata=metadata,
            occurred_at=occurred_at,
        )

    async def _build_permission_definition_snapshot(
        self,
        session: AsyncSession,
        permission: Permission,
    ) -> Dict[str, Any]:
        current_permission = (
            await self.get_permission_by_id(session, permission.id, load_tags=True)
            or permission
        )
        tags = sorted(
            list(getattr(current_permission, "tags", []) or []),
            key=lambda tag: (tag.name, str(tag.id)),
        )
        group_stmt = select(SqlConditionGroup).where(
            SqlConditionGroup.permission_id == current_permission.id
        )
        group_result = await session.execute(group_stmt)
        groups = sorted(
            list(group_result.scalars().all()),
            key=lambda group: (group.operator, group.description or "", str(group.id)),
        )
        condition_stmt = select(PermissionCondition).where(
            PermissionCondition.permission_id == current_permission.id
        )
        condition_result = await session.execute(condition_stmt)
        conditions = sorted(
            list(condition_result.scalars().all()),
            key=lambda condition: (
                condition.attribute,
                str(condition.condition_group_id or ""),
                str(condition.id),
            ),
        )
        return {
            "permission_name": current_permission.name,
            "permission_display_name": current_permission.display_name,
            "permission_description": current_permission.description,
            "resource": current_permission.resource,
            "action": current_permission.action,
            "scope": current_permission.scope,
            "is_system": current_permission.is_system,
            "status": getattr(current_permission.status, "value", current_permission.status),
            "is_active": current_permission.is_active,
            "tag_names": [tag.name for tag in tags],
            "condition_groups": [
                self._build_condition_group_snapshot(group) for group in groups
            ],
            "conditions": [
                self._build_permission_condition_snapshot(condition)
                for condition in conditions
            ],
        }

    def _changed_permission_definition_fields(
        self,
        previous_snapshot: Dict[str, Any],
        current_snapshot: Dict[str, Any],
    ) -> List[str]:
        field_names = [
            "permission_name",
            "permission_display_name",
            "permission_description",
            "resource",
            "action",
            "scope",
            "is_system",
            "status",
            "is_active",
            "tag_names",
            "condition_groups",
            "conditions",
        ]
        return [
            field_name
            for field_name in field_names
            if previous_snapshot.get(field_name) != current_snapshot.get(field_name)
        ]

    async def _get_mutable_permission_for_definition_edit(
        self,
        session: AsyncSession,
        permission_id: UUID,
    ) -> Permission:
        permission = await self.get_permission_by_id(
            session,
            permission_id,
            load_tags=True,
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
        return permission

    @staticmethod
    def _build_condition_group_snapshot(group: SqlConditionGroup) -> Dict[str, Any]:
        return {
            "id": group.id,
            "operator": group.operator,
            "description": group.description,
        }

    @staticmethod
    def _build_permission_condition_snapshot(
        condition: PermissionCondition,
    ) -> Dict[str, Any]:
        return {
            "id": condition.id,
            "condition_group_id": condition.condition_group_id,
            "attribute": condition.attribute,
            "operator": condition.operator,
            "value": condition.value,
            "value_type": condition.value_type,
            "description": condition.description,
        }

    @staticmethod
    def _changed_snapshot_fields(
        previous_snapshot: Dict[str, Any],
        current_snapshot: Dict[str, Any],
        field_names: List[str],
    ) -> List[str]:
        return [
            field_name
            for field_name in field_names
            if previous_snapshot.get(field_name) != current_snapshot.get(field_name)
        ]
