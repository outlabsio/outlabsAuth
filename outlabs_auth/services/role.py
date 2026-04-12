"""
Role Service

Handles role management operations with PostgreSQL/SQLAlchemy.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple, cast
from uuid import UUID

from sqlalchemy import and_, false, or_, select
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
from outlabs_auth.models.sql.enums import DefinitionStatus, MembershipStatus, RoleScope
from outlabs_auth.models.sql.permission import Permission
from outlabs_auth.models.sql.role import (
    ConditionGroup as SqlConditionGroup,
    Role,
    RoleCondition,
    RoleEntityTypePermission,
    RolePermission,
)
from outlabs_auth.models.sql.user import User
from outlabs_auth.models.sql.user_role_membership import UserRoleMembership
from outlabs_auth.schemas.abac import serialize_condition_value
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

    def __init__(
        self,
        config: AuthConfig,
        role_history_service: Optional[Any] = None,
        user_audit_service: Optional[Any] = None,
    ):
        """
        Initialize RoleService.

        Args:
            config: Authentication configuration
        """
        super().__init__(Role)
        self.config = config
        self.role_history_service = role_history_service
        self.user_audit_service = user_audit_service

    @staticmethod
    def _role_permission_options() -> list[Any]:
        return [
            selectinload(cast(Any, Role.permissions)),
            selectinload(cast(Any, Role.entity_type_permissions)).selectinload(
                cast(Any, RoleEntityTypePermission.permission)
            ),
        ]

    @staticmethod
    def _user_role_membership_role_options() -> list[Any]:
        return [
            selectinload(cast(Any, UserRoleMembership.role)).selectinload(
                cast(Any, Role.permissions)
            ),
            selectinload(cast(Any, UserRoleMembership.role))
            .selectinload(cast(Any, Role.entity_type_permissions))
            .selectinload(cast(Any, RoleEntityTypePermission.permission)),
        ]

    @staticmethod
    def _coerce_definition_status(value: DefinitionStatus | str) -> DefinitionStatus:
        if isinstance(value, DefinitionStatus):
            return value
        return DefinitionStatus(str(value))

    def _resolve_role_status(
        self,
        *,
        current_status: Optional[DefinitionStatus] = None,
        status: Optional[DefinitionStatus | str] = None,
        allow_archived: bool = False,
    ) -> DefinitionStatus:
        resolved_status = current_status or DefinitionStatus.ACTIVE
        if status is None:
            return resolved_status

        requested_status = self._coerce_definition_status(status)
        if requested_status == DefinitionStatus.ARCHIVED and not allow_archived:
            raise InvalidInputError(
                message="Use delete to archive roles",
                details={"status": requested_status.value},
            )
        return requested_status

    @staticmethod
    def _role_definition_is_active(role: Optional[Role]) -> bool:
        return bool(role and getattr(role, "status", DefinitionStatus.ACTIVE) == DefinitionStatus.ACTIVE)

    @staticmethod
    def _role_definition_is_visible(role: Optional[Role]) -> bool:
        return bool(role and getattr(role, "status", DefinitionStatus.ACTIVE) != DefinitionStatus.ARCHIVED)

    @staticmethod
    def _permission_definition_is_assignable(permission: Optional[Permission]) -> bool:
        return bool(
            permission
            and getattr(permission, "status", DefinitionStatus.ACTIVE)
            == DefinitionStatus.ACTIVE
        )

    async def create_role(
        self,
        session: AsyncSession,
        name: str,
        display_name: str,
        description: Optional[str] = None,
        permission_names: Optional[List[str]] = None,
        is_global: bool = True,
        is_system_role: bool = False,
        status: Optional[DefinitionStatus | str] = None,
        root_entity_id: Optional[UUID] = None,
        scope_entity_id: Optional[UUID] = None,
        scope: RoleScope = RoleScope.HIERARCHY,
        is_auto_assigned: bool = False,
        assignable_at_types: Optional[List[str]] = None,
        entity_type_permissions: Optional[Dict[str, List[str]]] = None,
        created_by_id: Optional[UUID] = None,
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
            assignable_at_types: Entity types where this role can be assigned.
        Returns:
            Role: Created role

        Raises:
            InvalidInputError: If role name already exists or validation fails
            EntityNotFoundError: If root_entity_id or scope_entity_id doesn't exist
        """
        # Validate and normalize
        name = validate_slug(name, "name")
        display_name = validate_name(display_name, "display_name")
        assignable_at_types = self._normalize_assignable_at_types(assignable_at_types)

        if is_global and (root_entity_id is not None or scope_entity_id is not None):
            raise InvalidInputError(
                message="System-wide roles cannot set root_entity_id or scope_entity_id",
                details={
                    "name": name,
                    "root_entity_id": str(root_entity_id) if root_entity_id else None,
                    "scope_entity_id": str(scope_entity_id) if scope_entity_id else None,
                },
            )

        if not is_global and root_entity_id is None and scope_entity_id is None:
            raise InvalidInputError(
                message="Scoped roles must define root_entity_id or scope_entity_id",
                details={"name": name},
            )

        # Check role name uniqueness within scope_entity_id
        # (Different entities and different root scopes can have roles with the same name)
        if scope_entity_id:
            existing = await self.get_one(
                session,
                cast(Any, Role.name) == name,
                cast(Any, Role.scope_entity_id) == scope_entity_id,
            )
        elif root_entity_id:
            existing = await self.get_one(
                session,
                cast(Any, Role.name) == name,
                cast(Any, Role.root_entity_id) == root_entity_id,
                cast(Any, Role.scope_entity_id).is_(None),
            )
        else:
            # System-wide roles must remain globally unique
            existing = await self.get_one(
                session,
                cast(Any, Role.name) == name,
                cast(Any, Role.root_entity_id).is_(None),
                cast(Any, Role.scope_entity_id).is_(None),
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
        if is_auto_assigned and not scope_entity_id:
            raise InvalidInputError(
                message="Auto-assigned roles must have a scope_entity_id",
                details={"name": name},
            )

        resolved_status = self._resolve_role_status(status=status)
        if is_auto_assigned and resolved_status != DefinitionStatus.ACTIVE:
            raise InvalidInputError(
                message="Only active roles can be auto-assigned",
                details={"name": name, "status": resolved_status.value},
            )

        role = Role(
            name=name,
            display_name=display_name,
            description=description,
            is_global=is_global,
            is_system_role=is_system_role,
            status=resolved_status,
            root_entity_id=root_entity_id,
            scope_entity_id=scope_entity_id,
            scope=scope,
            is_auto_assigned=is_auto_assigned,
            assignable_at_types=assignable_at_types,
        )

        await self.create(session, role)
        role_id = role.id

        # Add permissions via junction table
        if permission_names:
            await self._add_permissions_by_name(session, role_id, permission_names)

        if entity_type_permissions is not None:
            await self.set_entity_type_permissions(
                session,
                role_id,
                entity_type_permissions,
                changed_by_id=created_by_id,
                record_history=False,
            )

        await session.refresh(role, attribute_names=["permissions", "entity_type_permissions"])
        await self._invalidate_all_permissions_cache()
        current_role = (
            await self.get_role_by_id(
                session,
                role_id,
                load_permissions=True,
                load_entity_type_permissions=True,
            )
            or role
        )
        await self._record_role_definition_history_event(
            session,
            role=current_role,
            event_type="created",
            event_source="role_service.create_role",
            actor_user_id=created_by_id,
            after=await self._build_role_definition_snapshot(session, current_role),
        )
        return current_role

    @staticmethod
    def _normalize_assignable_at_types(
        assignable_at_types: Optional[List[str]],
    ) -> List[str]:
        if not assignable_at_types:
            return []

        normalized: List[str] = []
        seen = set()
        for entity_type in assignable_at_types:
            if not entity_type:
                continue
            next_value = entity_type.strip().lower()
            if not next_value or next_value in seen:
                continue
            seen.add(next_value)
            normalized.append(next_value)
        return normalized

    @staticmethod
    def _allows_entity_type(role: Role, entity_type: Optional[str]) -> bool:
        if not role.assignable_at_types:
            return True

        if not entity_type:
            return False

        return entity_type.lower() in {
            role_entity_type.lower() for role_entity_type in role.assignable_at_types
        }

    async def _get_root_entity_id(
        self,
        session: AsyncSession,
        entity_id: UUID,
    ) -> UUID:
        """Get the root entity ID for any entity using closure table."""
        stmt = (
            select(cast(Any, EntityClosure.ancestor_id))
            .where(cast(Any, EntityClosure.descendant_id) == entity_id)
            .order_by(cast(Any, EntityClosure.depth).desc())
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
            cast(Any, EntityClosure.ancestor_id) == root_entity_id,
            cast(Any, EntityClosure.descendant_id) == entity_id,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def get_role_by_id(
        self,
        session: AsyncSession,
        role_id: UUID,
        load_permissions: bool = False,
        load_entity_type_permissions: bool = False,
        include_archived: bool = False,
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
        stmt = select(Role).where(cast(Any, Role.id) == role_id)
        if not include_archived:
            stmt = stmt.where(cast(Any, Role.status) != DefinitionStatus.ARCHIVED)

        options: list[Any] = []
        if load_permissions:
            options.append(selectinload(cast(Any, Role.permissions)))
        if load_entity_type_permissions:
            options.append(
                selectinload(cast(Any, Role.entity_type_permissions)).selectinload(
                    cast(Any, RoleEntityTypePermission.permission)
                )
            )
        if options:
            stmt = stmt.options(*options)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

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
        status: Optional[DefinitionStatus | str] = None,
        scope: Optional[RoleScope] = None,
        is_auto_assigned: Optional[bool] = None,
        assignable_at_types: Optional[List[str]] = None,
        permission_names: Optional[List[str]] = None,
        update_permissions: bool = False,
        changed_by_id: Optional[UUID] = None,
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
            assignable_at_types: Entity types where this role can be assigned

        Returns:
            Updated role

        Raises:
            RoleNotFoundError: If role doesn't exist
            InvalidInputError: If trying to modify system role
        """
        role = await self.get_role_by_id(
            session,
            role_id,
            load_permissions=True,
            load_entity_type_permissions=True,
        )
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

        previous_snapshot = await self._build_role_definition_snapshot(session, role)

        if display_name is not None:
            role.display_name = validate_name(display_name, "display_name")

        if description is not None:
            role.description = description

        if status is not None:
            role.status = self._resolve_role_status(
                current_status=role.status,
                status=status,
            )

        if is_global is not None:
            if is_global and (role.root_entity_id is not None or role.scope_entity_id is not None):
                raise InvalidInputError(
                    message="Scoped roles cannot be converted to system-wide roles",
                    details={"role_id": str(role_id), "role_name": role.name},
                )
            if not is_global and role.root_entity_id is None and role.scope_entity_id is None:
                raise InvalidInputError(
                    message="System-wide roles cannot be made non-global without a scope",
                    details={"role_id": str(role_id), "role_name": role.name},
                )
            role.is_global = is_global

        if scope is not None:
            role.scope = scope

        if is_auto_assigned is not None:
            if is_auto_assigned and role.scope_entity_id is None:
                raise InvalidInputError(
                    message="Auto-assigned roles must have a scope_entity_id",
                    details={"role_id": str(role_id), "role_name": role.name},
                )
            if is_auto_assigned and role.status != DefinitionStatus.ACTIVE:
                raise InvalidInputError(
                    message="Only active roles can be auto-assigned",
                    details={
                        "role_id": str(role_id),
                        "status": getattr(role.status, "value", role.status),
                    },
                )
            role.is_auto_assigned = is_auto_assigned

        if assignable_at_types is not None:
            role.assignable_at_types = self._normalize_assignable_at_types(
                assignable_at_types
            )

        await self.update(session, role)

        if update_permissions:
            await self.set_permissions_by_name(
                session,
                role_id,
                permission_names or [],
                changed_by_id=changed_by_id,
                event_source="role_service.update_role",
            )

        current_role = (
            await self.get_role_by_id(
                session,
                role_id,
                load_permissions=True,
                load_entity_type_permissions=True,
            )
            or role
        )
        current_snapshot = await self._build_role_definition_snapshot(session, current_role)
        changed_fields = self._changed_role_definition_fields(previous_snapshot, current_snapshot)
        if changed_fields:
            await self._record_role_definition_history_event(
                session,
                role=current_role,
                event_type="updated",
                event_source="role_service.update_role",
                actor_user_id=changed_by_id,
                before=previous_snapshot,
                after=current_snapshot,
                metadata={"changed_fields": changed_fields},
            )
        await self._invalidate_all_permissions_cache()
        return current_role

    async def delete_role(
        self,
        session: AsyncSession,
        role_id: UUID,
        deleted_by_id: Optional[UUID] = None,
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
        role = await self.get_role_by_id(
            session,
            role_id,
            load_permissions=True,
            load_entity_type_permissions=True,
            include_archived=True,
        )
        if not role or role.status == DefinitionStatus.ARCHIVED:
            return False

        if role.is_system_role:
            raise InvalidInputError(
                message="Cannot delete system role",
                details={"role_id": str(role_id), "role_name": role.name},
            )

        previous_snapshot = await self._build_role_definition_snapshot(session, role)
        deleted_at = datetime.now(timezone.utc)
        role.status = DefinitionStatus.ARCHIVED
        await self.update(session, role)
        current_snapshot = await self._build_role_definition_snapshot(session, role)
        await self._record_role_definition_history_event(
            session,
            role=role,
            event_type="deleted",
            event_source="role_service.delete_role",
            actor_user_id=deleted_by_id,
            before=previous_snapshot,
            after=current_snapshot,
            occurred_at=deleted_at,
            metadata={"archived": True},
        )
        await self._invalidate_all_permissions_cache()
        return True

    async def create_role_condition_group(
        self,
        session: AsyncSession,
        role_id: UUID,
        *,
        operator: str = "AND",
        description: Optional[str] = None,
        changed_by_id: Optional[UUID] = None,
    ) -> SqlConditionGroup:
        role = await self._get_mutable_role_for_definition_edit(session, role_id)
        previous_snapshot = await self._build_role_definition_snapshot(session, role)

        group = SqlConditionGroup(
            role_id=role_id,
            operator=operator,
            description=description,
        )
        session.add(group)
        await session.flush()

        current_snapshot = await self._build_role_definition_snapshot(session, role)
        await self._record_role_definition_history_event(
            session,
            role=role,
            event_type="condition_group_created",
            event_source="role_service.create_condition_group",
            actor_user_id=changed_by_id,
            before=previous_snapshot,
            after=current_snapshot,
            metadata={"condition_group": self._build_condition_group_snapshot(group)},
        )
        return group

    async def update_role_condition_group(
        self,
        session: AsyncSession,
        role_id: UUID,
        group_id: UUID,
        *,
        fields_set: Set[str],
        operator: Optional[str] = None,
        description: Optional[str] = None,
        changed_by_id: Optional[UUID] = None,
    ) -> Optional[SqlConditionGroup]:
        role = await self._get_mutable_role_for_definition_edit(session, role_id)
        group = await session.get(SqlConditionGroup, group_id)
        if not group or group.role_id != role_id:
            return None

        previous_snapshot = await self._build_role_definition_snapshot(session, role)
        previous_group_snapshot = self._build_condition_group_snapshot(group)

        if "operator" in fields_set and operator is not None:
            group.operator = operator
        if "description" in fields_set:
            group.description = description

        await session.flush()

        current_snapshot = await self._build_role_definition_snapshot(session, role)
        current_group_snapshot = self._build_condition_group_snapshot(group)
        changed_fields = self._changed_snapshot_fields(
            previous_group_snapshot,
            current_group_snapshot,
            ["operator", "description"],
        )
        if changed_fields:
            await self._record_role_definition_history_event(
                session,
                role=role,
                event_type="condition_group_updated",
                event_source="role_service.update_condition_group",
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

    async def delete_role_condition_group(
        self,
        session: AsyncSession,
        role_id: UUID,
        group_id: UUID,
        *,
        changed_by_id: Optional[UUID] = None,
    ) -> bool:
        role = await self._get_mutable_role_for_definition_edit(session, role_id)
        group = await session.get(SqlConditionGroup, group_id)
        if not group or group.role_id != role_id:
            return False

        previous_snapshot = await self._build_role_definition_snapshot(session, role)
        deleted_group_snapshot = self._build_condition_group_snapshot(group)

        condition_stmt = select(RoleCondition).where(
            cast(Any, RoleCondition.role_id) == role_id,
            cast(Any, RoleCondition.condition_group_id) == group_id,
        )
        condition_result = await session.execute(condition_stmt)
        deleted_conditions = [
            self._build_role_condition_snapshot(condition)
            for condition in condition_result.scalars().all()
        ]

        await session.delete(group)
        await session.flush()

        current_snapshot = await self._build_role_definition_snapshot(session, role)
        await self._record_role_definition_history_event(
            session,
            role=role,
            event_type="condition_group_deleted",
            event_source="role_service.delete_condition_group",
            actor_user_id=changed_by_id,
            before=previous_snapshot,
            after=current_snapshot,
            metadata={
                "deleted_group": deleted_group_snapshot,
                "deleted_conditions": deleted_conditions,
            },
        )
        return True

    async def create_role_condition(
        self,
        session: AsyncSession,
        role_id: UUID,
        *,
        attribute: str,
        operator: str,
        value: Optional[Any],
        value_type: str,
        description: Optional[str] = None,
        condition_group_id: Optional[UUID] = None,
        changed_by_id: Optional[UUID] = None,
    ) -> RoleCondition:
        role = await self._get_mutable_role_for_definition_edit(session, role_id)
        if condition_group_id is not None:
            group = await session.get(SqlConditionGroup, condition_group_id)
            if not group or group.role_id != role_id:
                raise InvalidInputError(
                    message="Invalid condition_group_id",
                    details={
                        "role_id": str(role_id),
                        "condition_group_id": str(condition_group_id),
                    },
                )

        previous_snapshot = await self._build_role_definition_snapshot(session, role)

        condition = RoleCondition(
            role_id=role_id,
            condition_group_id=condition_group_id,
            attribute=attribute,
            operator=operator,
            value=serialize_condition_value(value, value_type),
            value_type=value_type,
            description=description,
        )
        session.add(condition)
        await session.flush()

        current_snapshot = await self._build_role_definition_snapshot(session, role)
        await self._record_role_definition_history_event(
            session,
            role=role,
            event_type="condition_created",
            event_source="role_service.create_condition",
            actor_user_id=changed_by_id,
            before=previous_snapshot,
            after=current_snapshot,
            metadata={"condition": self._build_role_condition_snapshot(condition)},
        )
        return condition

    async def update_role_condition(
        self,
        session: AsyncSession,
        role_id: UUID,
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
    ) -> Optional[RoleCondition]:
        role = await self._get_mutable_role_for_definition_edit(session, role_id)
        condition = await session.get(RoleCondition, condition_id)
        if not condition or condition.role_id != role_id:
            return None

        if "condition_group_id" in fields_set and condition_group_id is not None:
            group = await session.get(SqlConditionGroup, condition_group_id)
            if not group or group.role_id != role_id:
                raise InvalidInputError(
                    message="Invalid condition_group_id",
                    details={
                        "role_id": str(role_id),
                        "condition_group_id": str(condition_group_id),
                    },
                )

        previous_snapshot = await self._build_role_definition_snapshot(session, role)
        previous_condition_snapshot = self._build_role_condition_snapshot(condition)

        if "condition_group_id" in fields_set:
            condition.condition_group_id = condition_group_id
        if "attribute" in fields_set and attribute is not None:
            condition.attribute = attribute
        if "operator" in fields_set and operator is not None:
            condition.operator = cast(Any, operator)
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

        current_snapshot = await self._build_role_definition_snapshot(session, role)
        current_condition_snapshot = self._build_role_condition_snapshot(condition)
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
            await self._record_role_definition_history_event(
                session,
                role=role,
                event_type="condition_updated",
                event_source="role_service.update_condition",
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

    async def delete_role_condition(
        self,
        session: AsyncSession,
        role_id: UUID,
        condition_id: UUID,
        *,
        changed_by_id: Optional[UUID] = None,
    ) -> bool:
        role = await self._get_mutable_role_for_definition_edit(session, role_id)
        condition = await session.get(RoleCondition, condition_id)
        if not condition or condition.role_id != role_id:
            return False

        previous_snapshot = await self._build_role_definition_snapshot(session, role)
        deleted_condition_snapshot = self._build_role_condition_snapshot(condition)

        await session.delete(condition)
        await session.flush()

        current_snapshot = await self._build_role_definition_snapshot(session, role)
        await self._record_role_definition_history_event(
            session,
            role=role,
            event_type="condition_deleted",
            event_source="role_service.delete_condition",
            actor_user_id=changed_by_id,
            before=previous_snapshot,
            after=current_snapshot,
            metadata={"deleted_condition": deleted_condition_snapshot},
        )
        return True

    async def list_roles(
        self,
        session: AsyncSession,
        page: int = 1,
        limit: int = 20,
        search: Optional[str] = None,
        is_global: Optional[bool] = None,
        root_entity_id: Optional[UUID] = None,
        manageable_root_entity_ids: Optional[List[UUID]] = None,
        manageable_entity_ids: Optional[List[UUID]] = None,
        include_system_global: bool = True,
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
            manageable_root_entity_ids: Optional root scopes visible to the actor
            manageable_entity_ids: Optional entity scopes visible to the actor
            include_system_global: Whether to include system-wide global roles
        Returns:
            Tuple of (roles, total_count)
        """
        filters: list[Any] = [cast(Any, Role.status) != DefinitionStatus.ARCHIVED]
        if search:
            pattern = f"%{search}%"
            filters.append(
                or_(
                    cast(Any, Role.name).ilike(pattern),
                    cast(Any, Role.display_name).ilike(pattern),
                    cast(Any, Role.description).ilike(pattern),
                )
            )
        if is_global is not None:
            filters.append(cast(Any, Role.is_global) == is_global)
        if root_entity_id is not None:
            filters.append(cast(Any, Role.root_entity_id) == root_entity_id)

        scope_filters: list[Any] = []
        if include_system_global:
            scope_filters.append(
                and_(
                    cast(Any, Role.is_global) == True,
                    cast(Any, Role.root_entity_id).is_(None),
                    cast(Any, Role.scope_entity_id).is_(None),
                )
            )
        if manageable_root_entity_ids:
            scope_filters.append(
                and_(
                    cast(Any, Role.root_entity_id).in_(manageable_root_entity_ids),
                    cast(Any, Role.scope_entity_id).is_(None),
                )
            )
        if manageable_entity_ids:
            scope_filters.append(
                cast(Any, Role.scope_entity_id).in_(manageable_entity_ids)
            )

        if (
            manageable_root_entity_ids is not None
            or manageable_entity_ids is not None
            or not include_system_global
        ):
            filters.append(or_(*scope_filters) if scope_filters else false())

        total_count = await self.count(session, *filters)

        skip = (page - 1) * limit
        roles = await self.get_many(
            session,
            *filters,
            skip=skip,
            limit=limit,
            order_by=cast(Any, Role.name),
            options=[
                selectinload(cast(Any, Role.permissions)),
                selectinload(cast(Any, Role.root_entity)),
                selectinload(cast(Any, Role.scope_entity)),
            ],
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
        # Resolve target entity type and ancestor chain in one round trip.
        ancestors_stmt = (
            select(
                cast(Any, Entity.entity_type),
                cast(Any, EntityClosure.ancestor_id),
                cast(Any, EntityClosure.depth),
            )
            .join(
                EntityClosure,
                cast(Any, EntityClosure.descendant_id) == cast(Any, Entity.id),
            )
            .where(cast(Any, Entity.id) == entity_id)
        )
        ancestors_result = await session.execute(ancestors_stmt)
        ancestor_rows = ancestors_result.all()

        if not ancestor_rows:
            return [], 0

        entity_type = cast(str, ancestor_rows[0][0])
        ancestor_depth_rows = [(row[1], row[2]) for row in ancestor_rows]
        ancestor_ids = [ancestor_id for ancestor_id, _depth in ancestor_depth_rows]
        # Root is the one with highest depth
        root_id = max(ancestor_depth_rows, key=lambda row: row[1])[0]

        # Step 2: Build filter for available roles
        # A role is available at entity X if:
        # 1. System-wide global: is_global=True AND root_entity_id IS NULL AND scope_entity_id IS NULL
        # 2. Org-scoped: root_entity_id matches AND scope_entity_id IS NULL
        # 3. Entity-local (hierarchy): scope_entity_id is X or an ancestor AND scope=hierarchy
        # 4. Entity-local (entity_only): scope_entity_id = X AND scope=entity_only

        conditions: list[Any] = []

        if include_global:
            # 1. System-wide global roles
            conditions.append(
                and_(
                    cast(Any, Role.status) == DefinitionStatus.ACTIVE,
                    cast(Any, Role.is_global) == True,
                    cast(Any, Role.root_entity_id).is_(None),
                    cast(Any, Role.scope_entity_id).is_(None),
                )
            )

        # 2. Org-scoped roles (within our root, not entity-local)
        conditions.append(
            and_(
                cast(Any, Role.status) == DefinitionStatus.ACTIVE,
                cast(Any, Role.root_entity_id) == root_id,
                cast(Any, Role.scope_entity_id).is_(None),
            )
        )

        # 3. Entity-local roles with hierarchy scope from any ancestor
        conditions.append(
            and_(
                cast(Any, Role.status) == DefinitionStatus.ACTIVE,
                cast(Any, Role.scope_entity_id).in_(ancestor_ids),
                cast(Any, Role.scope) == RoleScope.HIERARCHY,
            )
        )

        # 4. Entity-local roles with entity_only scope from THIS entity only
        conditions.append(
            and_(
                cast(Any, Role.status) == DefinitionStatus.ACTIVE,
                cast(Any, Role.scope_entity_id) == entity_id,
                cast(Any, Role.scope) == RoleScope.ENTITY_ONLY,
            )
        )

        role_filter = or_(*conditions)

        # Add auto-assigned filter if requested
        if include_auto_assigned_only:
            role_filter = and_(role_filter, cast(Any, Role.is_auto_assigned) == True)

        stmt = (
            select(Role)
            .where(role_filter)
            .options(
                selectinload(cast(Any, Role.permissions)),
                selectinload(cast(Any, Role.root_entity)),
                selectinload(cast(Any, Role.scope_entity)),
            )
            .order_by(cast(Any, Role.name))
        )
        result = await session.execute(stmt)
        roles = [
            role
            for role in result.scalars().all()
            if self._allows_entity_type(role, entity_type)
        ]

        total_count = len(roles)
        skip = (page - 1) * limit
        return roles[skip : skip + limit], total_count

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
        ancestors_stmt = select(cast(Any, EntityClosure.ancestor_id)).where(
            cast(Any, EntityClosure.descendant_id) == entity_id
        )
        ancestors_result = await session.execute(ancestors_stmt)
        ancestor_ids = [row[0] for row in ancestors_result.all()]

        if not ancestor_ids:
            return []

        # Find auto-assigned roles:
        # 1. Entity-only roles defined at THIS entity
        # 2. Hierarchy roles defined at any ancestor (including self)
        role_filter = and_(
            cast(Any, Role.status) == DefinitionStatus.ACTIVE,
            cast(Any, Role.is_auto_assigned).is_(True),
            or_(
                # Entity-only auto-assigned for this specific entity
                and_(
                    cast(Any, Role.scope_entity_id) == entity_id,
                    cast(Any, Role.scope) == RoleScope.ENTITY_ONLY,
                ),
                # Hierarchy auto-assigned from any ancestor
                and_(
                    cast(Any, Role.scope_entity_id).in_(ancestor_ids),
                    cast(Any, Role.scope) == RoleScope.HIERARCHY,
                ),
            ),
        )

        stmt = select(Role).where(role_filter).order_by(cast(Any, Role.name))
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
        entity = await session.get(Entity, entity_id)
        if not entity:
            return False

        if not self._allows_entity_type(role, entity.entity_type):
            return False

        if not self._role_definition_is_active(role):
            return False

        # 1. Global system-wide roles are available everywhere
        if (
            role.is_global
            and role.root_entity_id is None
            and role.scope_entity_id is None
        ):
            return True

        # Get entity's ancestors for hierarchy checks
        ancestors_stmt = select(
            cast(Any, EntityClosure.ancestor_id),
            cast(Any, EntityClosure.depth),
        ).where(cast(Any, EntityClosure.descendant_id) == entity_id)
        ancestors_result = await session.execute(ancestors_stmt)
        ancestor_rows: list[tuple[UUID, int]] = [
            (cast(UUID, row[0]), cast(int, row[1]))
            for row in ancestors_result.all()
        ]

        if not ancestor_rows:
            return False

        ancestor_ids = {row[0] for row in ancestor_rows}
        root_id = cast(UUID, max(ancestor_rows, key=lambda x: x[1])[0])

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
        changed_by_id: Optional[UUID] = None,
        event_source: str = "role_service.set_permissions_by_name",
    ) -> Role:
        """
        Replace a role's permissions using permission names.
        """
        role = await self.get_role_by_id(
            session,
            role_id,
            load_permissions=True,
            load_entity_type_permissions=True,
        )
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

        previous_snapshot = await self._build_role_definition_snapshot(session, role)

        # Clear existing role_permissions
        await self._replace_permissions_by_name(session, role_id, permission_names)
        await session.refresh(role, attribute_names=["permissions", "entity_type_permissions"])
        await self._invalidate_all_permissions_cache()

        current_role = (
            await self.get_role_by_id(
                session,
                role_id,
                load_permissions=True,
                load_entity_type_permissions=True,
            )
            or role
        )
        current_snapshot = await self._build_role_definition_snapshot(session, current_role)
        added_permission_names, removed_permission_names = self._permission_name_delta(
            previous_snapshot,
            current_snapshot,
        )
        if added_permission_names or removed_permission_names:
            await self._record_role_definition_history_event(
                session,
                role=current_role,
                event_type="permissions_replaced",
                event_source=event_source,
                actor_user_id=changed_by_id,
                before=previous_snapshot,
                after=current_snapshot,
                metadata={
                    "added_permission_names": added_permission_names,
                    "removed_permission_names": removed_permission_names,
                },
            )
        return current_role

    async def add_permissions_by_name(
        self,
        session: AsyncSession,
        role_id: UUID,
        permission_names: List[str],
        changed_by_id: Optional[UUID] = None,
        event_source: str = "role_service.add_permissions_by_name",
    ) -> Role:
        """
        Add permissions to a role using permission names.
        """
        role = await self.get_role_by_id(
            session,
            role_id,
            load_permissions=True,
            load_entity_type_permissions=True,
        )
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

        previous_snapshot = await self._build_role_definition_snapshot(session, role)

        await self._add_permissions_by_name(session, role_id, permission_names)
        await session.refresh(role, attribute_names=["permissions", "entity_type_permissions"])
        await self._invalidate_all_permissions_cache()
        current_role = (
            await self.get_role_by_id(
                session,
                role_id,
                load_permissions=True,
                load_entity_type_permissions=True,
            )
            or role
        )
        current_snapshot = await self._build_role_definition_snapshot(session, current_role)
        added_permission_names, _ = self._permission_name_delta(previous_snapshot, current_snapshot)
        if added_permission_names:
            await self._record_role_definition_history_event(
                session,
                role=current_role,
                event_type="permissions_added",
                event_source=event_source,
                actor_user_id=changed_by_id,
                before=previous_snapshot,
                after=current_snapshot,
                metadata={"added_permission_names": added_permission_names},
            )
        return current_role

    async def remove_permissions_by_name(
        self,
        session: AsyncSession,
        role_id: UUID,
        permission_names: List[str],
        changed_by_id: Optional[UUID] = None,
        event_source: str = "role_service.remove_permissions_by_name",
    ) -> Role:
        """
        Remove permissions from a role using permission names.
        """
        role = await self.get_role_by_id(
            session,
            role_id,
            load_permissions=True,
            load_entity_type_permissions=True,
        )
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

        previous_snapshot = await self._build_role_definition_snapshot(session, role)

        # Resolve permission IDs
        stmt = select(cast(Any, Permission.id)).where(
            cast(Any, Permission.name).in_(permission_names)
        )
        result = await session.execute(stmt)
        perm_ids = [row[0] for row in result.all()]
        if perm_ids:
            await session.execute(
                sql_delete(RolePermission).where(
                    cast(Any, RolePermission.role_id) == role_id,
                    cast(Any, RolePermission.permission_id).in_(perm_ids),
                )
            )
            await session.flush()

        await session.refresh(role, attribute_names=["permissions", "entity_type_permissions"])
        await self._invalidate_all_permissions_cache()

        current_role = (
            await self.get_role_by_id(
                session,
                role_id,
                load_permissions=True,
                load_entity_type_permissions=True,
            )
            or role
        )
        current_snapshot = await self._build_role_definition_snapshot(session, current_role)
        _, removed_permission_names = self._permission_name_delta(previous_snapshot, current_snapshot)
        if removed_permission_names:
            await self._record_role_definition_history_event(
                session,
                role=current_role,
                event_type="permissions_removed",
                event_source=event_source,
                actor_user_id=changed_by_id,
                before=previous_snapshot,
                after=current_snapshot,
                metadata={"removed_permission_names": removed_permission_names},
            )
        return current_role

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
        permissions = await self._resolve_permissions_by_name(session, permission_names)
        for permission in permissions:
            role_perm = RolePermission(role_id=role_id, permission_id=permission.id)
            session.add(role_perm)

        await session.flush()

    async def _resolve_permissions_by_name(
        self,
        session: AsyncSession,
        permission_names: List[str],
    ) -> List[Permission]:
        normalized_names = list(dict.fromkeys(permission_names))
        if not normalized_names:
            return []

        stmt = select(Permission).where(cast(Any, Permission.name).in_(normalized_names))
        result = await session.execute(stmt)
        permissions_by_name = {permission.name: permission for permission in result.scalars().all()}
        missing_names = [name for name in normalized_names if name not in permissions_by_name]
        inactive_names = sorted(
            name
            for name, permission in permissions_by_name.items()
            if not self._permission_definition_is_assignable(permission)
        )
        if inactive_names:
            raise InvalidInputError(
                message="One or more permissions are not active",
                details={"inactive_permissions": inactive_names},
            )
        if missing_names:
            raise InvalidInputError(
                message="One or more permissions do not exist",
                details={"missing_permissions": missing_names},
            )
        return [
            permissions_by_name[name]
            for name in normalized_names
        ]

    async def set_entity_type_permissions(
        self,
        session: AsyncSession,
        role_id: UUID,
        entity_type_permissions: Optional[Dict[str, List[str]]],
        changed_by_id: Optional[UUID] = None,
        record_history: bool = True,
        event_source: str = "role_service.set_entity_type_permissions",
    ) -> Role:
        """Replace a role's context-aware permission overrides."""
        role = await self.get_role_by_id(
            session,
            role_id,
            load_permissions=True,
            load_entity_type_permissions=True,
        )
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

        previous_snapshot = await self._build_role_definition_snapshot(session, role)

        await session.execute(
            sql_delete(RoleEntityTypePermission).where(
                cast(Any, RoleEntityTypePermission.role_id) == role_id
            )
        )
        await session.flush()

        for entity_type, permission_names in (entity_type_permissions or {}).items():
            permissions = await self._resolve_permissions_by_name(session, permission_names)
            for permission in permissions:
                session.add(
                    RoleEntityTypePermission(
                        role_id=role_id,
                        entity_type=entity_type.lower(),
                        permission_id=permission.id,
                    )
                )

        await session.flush()
        await session.refresh(role, attribute_names=["permissions", "entity_type_permissions"])
        await self._invalidate_all_permissions_cache()
        current_role = (
            await self.get_role_by_id(
                session,
                role_id,
                load_permissions=True,
                load_entity_type_permissions=True,
            )
            or role
        )
        current_snapshot = await self._build_role_definition_snapshot(session, current_role)
        if (
            record_history
            and previous_snapshot.get("entity_type_permissions") != current_snapshot.get("entity_type_permissions")
        ):
            await self._record_role_definition_history_event(
                session,
                role=current_role,
                event_type="entity_type_permissions_replaced",
                event_source=event_source,
                actor_user_id=changed_by_id,
                before=previous_snapshot,
                after=current_snapshot,
            )
        return current_role

    async def add_permissions(
        self,
        session: AsyncSession,
        role_id: UUID,
        permission_ids: List[UUID],
        changed_by_id: Optional[UUID] = None,
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
        permission_names = await self._resolve_permission_names_by_ids(session, permission_ids)
        return await self.add_permissions_by_name(
            session,
            role_id,
            permission_names,
            changed_by_id=changed_by_id,
            event_source="role_service.add_permissions",
        )

    async def remove_permissions(
        self,
        session: AsyncSession,
        role_id: UUID,
        permission_ids: List[UUID],
        changed_by_id: Optional[UUID] = None,
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
        permission_names = await self._resolve_permission_names_by_ids(session, permission_ids)
        return await self.remove_permissions_by_name(
            session,
            role_id,
            permission_names,
            changed_by_id=changed_by_id,
            event_source="role_service.remove_permissions",
        )

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
        role = await self.get_role_by_id(
            session,
            role_id,
            load_permissions=True,
        )
        if not role:
            raise RoleNotFoundError(
                message="Role not found",
                details={"role_id": str(role_id)},
            )

        return [
            permission
            for permission in role.permissions
            if getattr(permission, "status", DefinitionStatus.ACTIVE)
            != DefinitionStatus.ARCHIVED
        ]

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

    async def get_role_entity_type_permission_names(
        self,
        session: AsyncSession,
        role_id: UUID,
    ) -> Dict[str, List[str]]:
        """Get context-aware permission overrides for a role."""
        role = await self.get_role_by_id(
            session,
            role_id,
            load_entity_type_permissions=True,
        )
        if not role:
            raise RoleNotFoundError(
                message="Role not found",
                details={"role_id": str(role_id)},
            )

        overrides: Dict[str, List[str]] = {}
        for entry in role.entity_type_permissions or []:
            if not entry.permission:
                continue
            overrides.setdefault(entry.entity_type, []).append(entry.permission.name)
        return overrides

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
        user_stmt = select(User).where(cast(Any, User.id) == user_id)
        user_result = await session.execute(user_stmt)
        user = cast(Optional[User], user_result.scalar_one_or_none())
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

        if not self._role_definition_is_active(role):
            raise InvalidInputError(
                message="Only active roles can be assigned",
                details={
                    "role_id": str(role_id),
                    "status": getattr(role.status, "value", role.status),
                },
            )

        if role.scope_entity_id is not None:
            raise InvalidInputError(
                message="Entity-local roles cannot be assigned via SimpleRBAC",
                details={
                    "role_id": str(role_id),
                    "scope_entity_id": str(role.scope_entity_id),
                },
            )

        # Keep one current-state row per (user, role) and reactivate it in place.
        membership_stmt = select(UserRoleMembership).where(
            cast(Any, UserRoleMembership.user_id) == user_id,
            cast(Any, UserRoleMembership.role_id) == role_id,
        )
        membership_result = await session.execute(membership_stmt)
        existing_membership = cast(
            Optional[UserRoleMembership], membership_result.scalar_one_or_none()
        )
        if existing_membership and existing_membership.status == MembershipStatus.ACTIVE:
            raise InvalidInputError(
                message="User already has this role assigned",
                details={"user_id": str(user_id), "role_id": str(role_id)},
            )

        if existing_membership:
            previous_snapshot = await self._build_user_role_audit_snapshot(
                session,
                existing_membership,
                role=role,
            )
            event_at = datetime.now(timezone.utc)
            existing_membership.assigned_at = event_at
            existing_membership.assigned_by_id = assigned_by_id
            existing_membership.valid_from = valid_from
            existing_membership.valid_until = valid_until
            existing_membership.status = MembershipStatus.ACTIVE
            existing_membership.revoked_at = None
            existing_membership.revoked_by_id = None
            existing_membership.revocation_reason = None

            await session.flush()
            await session.refresh(existing_membership)
            await self._record_user_role_audit_event(
                session,
                user=user,
                role=role,
                membership=existing_membership,
                event_type="user.role_assigned",
                event_source="role_service.assign_role_to_user",
                actor_user_id=assigned_by_id,
                previous_snapshot=previous_snapshot,
                occurred_at=event_at,
                metadata={"reactivated_existing_membership": True},
            )
            await self._invalidate_user_permissions_cache(user_id)
            return existing_membership

        # Create membership
        event_at = datetime.now(timezone.utc)
        membership = UserRoleMembership(
            user_id=user_id,
            role_id=role_id,
            assigned_at=event_at,
            assigned_by_id=assigned_by_id,
            valid_from=valid_from,
            valid_until=valid_until,
            status=MembershipStatus.ACTIVE,
        )

        session.add(membership)
        await session.flush()
        await session.refresh(membership)
        await self._record_user_role_audit_event(
            session,
            user=user,
            role=role,
            membership=membership,
            event_type="user.role_assigned",
            event_source="role_service.assign_role_to_user",
            actor_user_id=assigned_by_id,
            occurred_at=event_at,
            metadata={"reactivated_existing_membership": False},
        )
        await self._invalidate_user_permissions_cache(user_id)
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
            cast(Any, UserRoleMembership.user_id) == user_id,
            cast(Any, UserRoleMembership.role_id) == role_id,
            cast(Any, UserRoleMembership.status) == MembershipStatus.ACTIVE,
        )
        result = await session.execute(stmt)
        membership = result.scalar_one_or_none()

        if not membership:
            return False

        user = await session.get(User, user_id)
        role = await session.get(Role, role_id)
        previous_snapshot = None
        if role is not None:
            previous_snapshot = await self._build_user_role_audit_snapshot(
                session,
                membership,
                role=role,
            )

        event_at = datetime.now(timezone.utc)
        membership.status = MembershipStatus.REVOKED
        membership.revoked_at = event_at
        membership.revoked_by_id = revoked_by_id
        membership.revocation_reason = reason

        await session.flush()
        if user is not None and role is not None:
            await self._record_user_role_audit_event(
                session,
                user=user,
                role=role,
                membership=membership,
                event_type="user.role_revoked",
                event_source="role_service.revoke_role_from_user",
                actor_user_id=revoked_by_id,
                reason=reason,
                previous_snapshot=previous_snapshot,
                occurred_at=event_at,
            )
        await self._invalidate_user_permissions_cache(user_id)
        return True

    async def revoke_all_roles_for_user(
        self,
        session: AsyncSession,
        user_id: UUID,
        *,
        revoked_by_id: Optional[UUID] = None,
        reason: Optional[str] = None,
    ) -> int:
        """Revoke all non-revoked direct role memberships for a user."""
        stmt = select(UserRoleMembership).where(
            cast(Any, UserRoleMembership.user_id) == user_id,
            cast(Any, UserRoleMembership.status) != MembershipStatus.REVOKED,
        )
        result = await session.execute(stmt)
        memberships = list(result.scalars().all())
        if not memberships:
            return 0

        event_at = datetime.now(timezone.utc)
        for membership in memberships:
            role = await session.get(Role, membership.role_id)
            user = await session.get(User, membership.user_id)
            previous_snapshot = None
            if role is not None:
                previous_snapshot = await self._build_user_role_audit_snapshot(
                    session,
                    membership,
                    role=role,
                )
            membership.status = MembershipStatus.REVOKED
            membership.revoked_at = event_at
            membership.revoked_by_id = revoked_by_id
            membership.revocation_reason = reason
            if user is not None and role is not None:
                await self._record_user_role_audit_event(
                    session,
                    user=user,
                    role=role,
                    membership=membership,
                    event_type="user.role_revoked",
                    event_source="role_service.revoke_all_roles_for_user",
                    actor_user_id=revoked_by_id,
                    reason=reason,
                    previous_snapshot=previous_snapshot,
                    occurred_at=event_at,
                )

        await session.flush()
        await self._invalidate_user_permissions_cache(user_id)
        return len(memberships)

    async def revoke_memberships_for_archived_entities(
        self,
        session: AsyncSession,
        entity_ids: List[UUID],
        *,
        revoked_by_id: Optional[UUID] = None,
        reason: Optional[str] = None,
    ) -> int:
        """
        Revoke direct role memberships tied to archived entities.

        A direct role assignment must no longer grant permissions if the role is
        rooted or scoped to an entity that has just been archived.
        """
        if not entity_ids:
            return 0

        stmt = (
            select(UserRoleMembership)
            .join(Role, cast(Any, UserRoleMembership.role_id) == Role.id)
            .where(
                cast(Any, UserRoleMembership.status) != MembershipStatus.REVOKED,
                or_(
                    cast(Any, Role.root_entity_id).in_(entity_ids),
                    cast(Any, Role.scope_entity_id).in_(entity_ids),
                ),
            )
        )
        result = await session.execute(stmt)
        memberships = list(result.scalars().all())
        if not memberships:
            return 0

        affected_user_ids: set[UUID] = set()
        event_at = datetime.now(timezone.utc)

        for membership in memberships:
            role = await session.get(Role, membership.role_id)
            user = await session.get(User, membership.user_id)
            previous_snapshot = None
            if role is not None:
                previous_snapshot = await self._build_user_role_audit_snapshot(
                    session,
                    membership,
                    role=role,
                )
            membership.status = MembershipStatus.REVOKED
            membership.revoked_at = event_at
            membership.revoked_by_id = revoked_by_id
            membership.revocation_reason = reason
            affected_user_ids.add(membership.user_id)
            if user is not None and role is not None:
                await self._record_user_role_audit_event(
                    session,
                    user=user,
                    role=role,
                    membership=membership,
                    event_type="user.role_revoked",
                    event_source="role_service.revoke_memberships_for_archived_entities",
                    actor_user_id=revoked_by_id,
                    reason=reason,
                    previous_snapshot=previous_snapshot,
                    occurred_at=event_at,
                )

        await session.flush()

        for user_id in affected_user_ids:
            await self._invalidate_user_permissions_cache(user_id)

        return len(memberships)

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
        filters: list[Any] = [cast(Any, UserRoleMembership.user_id) == user_id]
        if not include_inactive:
            filters.append(cast(Any, UserRoleMembership.status) == MembershipStatus.ACTIVE)

        stmt = (
            select(UserRoleMembership)
            .options(*self._user_role_membership_role_options())
            .where(*filters)
        )
        result = await session.execute(stmt)
        memberships: list[UserRoleMembership] = list(result.scalars().all())

        # Filter by time-based validity and extract roles
        roles = []
        for m in memberships:
            if m.is_currently_valid() and self._role_definition_is_visible(m.role):
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
        filters: list[Any] = [cast(Any, UserRoleMembership.user_id) == user_id]
        if not include_inactive:
            filters.append(cast(Any, UserRoleMembership.status) == MembershipStatus.ACTIVE)

        stmt = (
            select(UserRoleMembership)
            .options(*self._user_role_membership_role_options())
            .where(*filters)
            .order_by(cast(Any, UserRoleMembership.assigned_at).desc())
        )
        result = await session.execute(stmt)
        memberships: list[UserRoleMembership] = list(result.scalars().all())
        return [
            membership
            for membership in memberships
            if self._role_definition_is_visible(membership.role)
        ]

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

    async def _replace_permissions_by_name(
        self,
        session: AsyncSession,
        role_id: UUID,
        permission_names: List[str],
    ) -> None:
        """Replace the direct permission set for a role."""
        await session.execute(
            sql_delete(RolePermission).where(cast(Any, RolePermission.role_id) == role_id)
        )
        await session.flush()
        await self._add_permissions_by_name(session, role_id, permission_names)

    async def _resolve_permission_names_by_ids(
        self,
        session: AsyncSession,
        permission_ids: List[UUID],
    ) -> List[str]:
        """Resolve permission IDs into stable names for history-aware updates."""
        if not permission_ids:
            return []

        stmt = select(Permission).where(cast(Any, Permission.id).in_(permission_ids))
        result = await session.execute(stmt)
        permissions_by_id = {permission.id: permission for permission in result.scalars().all()}
        missing_ids = [str(permission_id) for permission_id in permission_ids if permission_id not in permissions_by_id]
        inactive_ids = sorted(
            str(permission.id)
            for permission in permissions_by_id.values()
            if not self._permission_definition_is_assignable(permission)
        )
        if inactive_ids:
            raise InvalidInputError(
                message="One or more permissions are not active",
                details={"inactive_permission_ids": inactive_ids},
            )
        if missing_ids:
            raise InvalidInputError(
                message="One or more permissions do not exist",
                details={"missing_permission_ids": missing_ids},
            )
        return [permissions_by_id[permission_id].name for permission_id in permission_ids]

    async def _record_role_definition_history_event(
        self,
        session: AsyncSession,
        *,
        role: Role,
        event_type: str,
        event_source: str,
        actor_user_id: Optional[UUID] = None,
        before: Optional[Dict[str, Any]] = None,
        after: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        occurred_at: Optional[datetime] = None,
    ) -> None:
        if self.role_history_service is None:
            return

        snapshot = await self._build_role_definition_snapshot(session, role)
        await self.role_history_service.record_event(
            session,
            role_id=role.id,
            event_type=event_type,
            event_source=event_source,
            actor_user_id=actor_user_id,
            snapshot=snapshot,
            before=before,
            after=after,
            metadata=metadata,
            occurred_at=occurred_at,
        )

    async def _build_role_definition_snapshot(
        self,
        session: AsyncSession,
        role: Role,
    ) -> Dict[str, Any]:
        current_role = (
            await self.get_role_by_id(
                session,
                role.id,
                load_permissions=True,
                load_entity_type_permissions=True,
                include_archived=True,
            )
            or role
        )
        permissions = sorted(
            list(getattr(current_role, "permissions", []) or []),
            key=lambda permission: (permission.name, str(permission.id)),
        )
        entity_type_permissions = sorted(
            list(getattr(current_role, "entity_type_permissions", []) or []),
            key=lambda item: (item.entity_type, str(item.permission_id)),
        )
        condition_group_stmt = select(SqlConditionGroup).where(
            cast(Any, SqlConditionGroup.role_id) == current_role.id
        )
        condition_group_result = await session.execute(condition_group_stmt)
        condition_groups = sorted(
            list(condition_group_result.scalars().all()),
            key=lambda group: (group.operator, group.description or "", str(group.id)),
        )
        condition_stmt = select(RoleCondition).where(
            cast(Any, RoleCondition.role_id) == current_role.id
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
        root_entity = await session.get(Entity, current_role.root_entity_id) if current_role.root_entity_id else None
        scope_entity = await session.get(Entity, current_role.scope_entity_id) if current_role.scope_entity_id else None

        entity_type_permission_snapshot: Dict[str, Dict[str, List[Any]]] = {}
        for item in entity_type_permissions:
            permission_name = item.permission.name if getattr(item, "permission", None) else None
            bucket = entity_type_permission_snapshot.setdefault(
                item.entity_type,
                {"permission_ids": [], "permission_names": []},
            )
            bucket["permission_ids"].append(item.permission_id)
            if permission_name:
                bucket["permission_names"].append(permission_name)

        return {
            "role_name": current_role.name,
            "role_display_name": current_role.display_name,
            "role_description": current_role.description,
            "is_system_role": current_role.is_system_role,
            "is_global": current_role.is_global,
            "status": getattr(current_role.status, "value", current_role.status),
            "root_entity_id": current_role.root_entity_id,
            "root_entity_name": root_entity.display_name if root_entity else None,
            "scope_entity_id": current_role.scope_entity_id,
            "scope_entity_name": scope_entity.display_name if scope_entity else None,
            "scope": getattr(current_role.scope, "value", current_role.scope),
            "is_auto_assigned": current_role.is_auto_assigned,
            "assignable_at_types": list(current_role.assignable_at_types or []),
            "permission_ids": [permission.id for permission in permissions],
            "permission_names": [permission.name for permission in permissions],
            "entity_type_permissions": entity_type_permission_snapshot,
            "condition_groups": [
                self._build_condition_group_snapshot(group)
                for group in condition_groups
            ],
            "conditions": [
                self._build_role_condition_snapshot(condition)
                for condition in conditions
            ],
        }

    def _changed_role_definition_fields(
        self,
        previous_snapshot: Dict[str, Any],
        current_snapshot: Dict[str, Any],
    ) -> List[str]:
        """Return changed role-definition fields excluding permission-set deltas."""
        field_names = [
            "role_name",
            "role_display_name",
            "role_description",
            "is_system_role",
            "is_global",
            "status",
            "root_entity_id",
            "root_entity_name",
            "scope_entity_id",
            "scope_entity_name",
            "scope",
            "is_auto_assigned",
            "assignable_at_types",
        ]
        return [
            field_name
            for field_name in field_names
            if previous_snapshot.get(field_name) != current_snapshot.get(field_name)
        ]

    def _permission_name_delta(
        self,
        previous_snapshot: Dict[str, Any],
        current_snapshot: Dict[str, Any],
    ) -> Tuple[List[str], List[str]]:
        """Return deterministic permission-name add/remove deltas."""
        previous_names = set(previous_snapshot.get("permission_names") or [])
        current_names = set(current_snapshot.get("permission_names") or [])
        added_names = sorted(current_names - previous_names)
        removed_names = sorted(previous_names - current_names)
        return added_names, removed_names

    async def _invalidate_all_permissions_cache(self) -> None:
        cache_service = getattr(self, "cache_service", None)
        if cache_service is not None:
            await cache_service.publish_all_permissions_invalidation()

    async def _get_mutable_role_for_definition_edit(
        self,
        session: AsyncSession,
        role_id: UUID,
    ) -> Role:
        role = await self.get_role_by_id(
            session,
            role_id,
            load_permissions=True,
            load_entity_type_permissions=True,
        )
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
        return role

    @staticmethod
    def _build_condition_group_snapshot(group: SqlConditionGroup) -> Dict[str, Any]:
        return {
            "id": group.id,
            "operator": group.operator,
            "description": group.description,
        }

    @staticmethod
    def _build_role_condition_snapshot(condition: RoleCondition) -> Dict[str, Any]:
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

    async def _record_user_role_audit_event(
        self,
        session: AsyncSession,
        *,
        user: User,
        role: Role,
        membership: UserRoleMembership,
        event_type: str,
        event_source: str,
        actor_user_id: Optional[UUID] = None,
        reason: Optional[str] = None,
        previous_snapshot: Optional[Dict[str, Any]] = None,
        occurred_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        if self.user_audit_service is None:
            return

        payload = {
            "role_name": role.name,
            "role_display_name": role.display_name,
            "role_is_global": role.is_global,
            "role_root_entity_id": role.root_entity_id,
            "role_scope_entity_id": role.scope_entity_id,
        }
        if metadata:
            payload.update(metadata)

        await self.user_audit_service.record_event(
            session,
            event_category="role",
            event_type=event_type,
            event_source=event_source,
            actor_user_id=actor_user_id,
            subject_user_id=user.id,
            subject_email_snapshot=user.email,
            root_entity_id=role.root_entity_id or user.root_entity_id,
            entity_id=role.scope_entity_id,
            role_id=role.id,
            reason=reason,
            before=previous_snapshot,
            after=await self._build_user_role_audit_snapshot(session, membership, role=role),
            metadata=payload,
            occurred_at=occurred_at,
        )

    async def _build_user_role_audit_snapshot(
        self,
        session: AsyncSession,
        membership: UserRoleMembership,
        *,
        role: Optional[Role] = None,
    ) -> Dict[str, Any]:
        current_role = role or getattr(membership, "role", None) or await session.get(Role, membership.role_id)
        return {
            "status": membership.status,
            "assigned_at": membership.assigned_at,
            "assigned_by_id": membership.assigned_by_id,
            "valid_from": membership.valid_from,
            "valid_until": membership.valid_until,
            "revoked_at": membership.revoked_at,
            "revoked_by_id": membership.revoked_by_id,
            "revocation_reason": membership.revocation_reason,
            "role_id": membership.role_id,
            "role_name": current_role.name if current_role else None,
            "role_display_name": current_role.display_name if current_role else None,
            "role_root_entity_id": current_role.root_entity_id if current_role else None,
            "role_scope_entity_id": current_role.scope_entity_id if current_role else None,
        }

    async def _invalidate_user_permissions_cache(self, user_id: UUID) -> None:
        cache_service = getattr(self, "cache_service", None)
        if cache_service is not None:
            await cache_service.publish_user_permissions_invalidation(str(user_id))
