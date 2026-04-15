"""
Integration principal service.

Manages non-human principals that own durable system integration API keys.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, List, Optional, cast
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import InvalidInputError, UserNotFoundError
from outlabs_auth.models.sql.entity import Entity
from outlabs_auth.models.sql.enums import (
    DefinitionStatus,
    IntegrationPrincipalScopeKind,
    IntegrationPrincipalStatus,
)
from outlabs_auth.models.sql.integration_principal import IntegrationPrincipal
from outlabs_auth.models.sql.role import Role
from outlabs_auth.models.sql.user import User
from outlabs_auth.services.base import BaseService

if TYPE_CHECKING:
    from outlabs_auth.observability.service import ObservabilityService
    from outlabs_auth.services.api_key import APIKeyService
    from outlabs_auth.services.api_key_policy import APIKeyPolicyService


class IntegrationPrincipalService(BaseService[IntegrationPrincipal]):
    """CRUD and lifecycle management for integration principals."""

    def __init__(
        self,
        config: AuthConfig,
        *,
        policy_service: Optional["APIKeyPolicyService"] = None,
        api_key_service: Optional["APIKeyService"] = None,
        observability: Optional["ObservabilityService"] = None,
    ) -> None:
        super().__init__(IntegrationPrincipal)
        self.config = config
        self.policy_service = policy_service
        self.api_key_service = api_key_service
        self.observability = observability

    @staticmethod
    def _principal_loader_options() -> list[Any]:
        return [
            selectinload(cast(Any, IntegrationPrincipal.roles)).selectinload(cast(Any, Role.permissions)),
        ]

    async def get_principal(
        self,
        session: AsyncSession,
        principal_id: UUID,
    ) -> Optional[IntegrationPrincipal]:
        """Get one integration principal by ID."""
        return await self.get_by_id(
            session,
            principal_id,
            options=self._principal_loader_options(),
        )

    async def list_principals(
        self,
        session: AsyncSession,
        *,
        scope_kind: Optional[IntegrationPrincipalScopeKind] = None,
        anchor_entity_id: Optional[UUID] = None,
        status: Optional[IntegrationPrincipalStatus] = None,
        search: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[List[IntegrationPrincipal], int]:
        """List principals with simple pagination and filtering."""
        scope_kind_col = cast(Any, IntegrationPrincipal.scope_kind)
        anchor_entity_id_col = cast(Any, IntegrationPrincipal.anchor_entity_id)
        status_col = cast(Any, IntegrationPrincipal.status)
        name_col = cast(Any, IntegrationPrincipal.name)
        description_col = cast(Any, IntegrationPrincipal.description)
        created_at_col = cast(Any, IntegrationPrincipal.created_at)
        filters: list[Any] = []
        if scope_kind is not None:
            filters.append(scope_kind_col == scope_kind)
        if anchor_entity_id is not None:
            filters.append(anchor_entity_id_col == anchor_entity_id)
        if status is not None:
            filters.append(status_col == status)
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(
                or_(
                    name_col.ilike(pattern),
                    description_col.ilike(pattern),
                )
            )

        total = await self.count(session, *filters)
        principals = await self.get_many(
            session,
            *filters,
            skip=(page - 1) * limit,
            limit=limit,
            order_by=created_at_col.desc(),
            options=self._principal_loader_options(),
        )
        return principals, total

    async def create_principal(
        self,
        session: AsyncSession,
        *,
        name: str,
        description: Optional[str],
        scope_kind: IntegrationPrincipalScopeKind,
        anchor_entity_id: Optional[UUID],
        inherit_from_tree: bool,
        allowed_scopes: List[str],
        role_ids: Optional[List[UUID]] = None,
        created_by_user_id: Optional[UUID],
    ) -> IntegrationPrincipal:
        """Create a new principal after validating scope and grant rules."""
        actor = await self._load_actor(session, created_by_user_id)
        normalized_scopes = self._normalize_scopes(allowed_scopes, allow_empty=True)
        normalized_role_ids = self._normalize_role_ids(role_ids)
        await self._validate_scope_context(
            session,
            scope_kind=scope_kind,
            anchor_entity_id=anchor_entity_id,
            inherit_from_tree=inherit_from_tree,
        )
        roles = await self._load_roles(session, normalized_role_ids)
        self._validate_role_assignments(
            roles,
            scope_kind=scope_kind,
            anchor_entity_id=anchor_entity_id,
        )
        effective_scopes = await self._resolve_effective_scopes(
            session,
            roles=roles,
            legacy_allowed_scopes=normalized_scopes,
        )

        if self.policy_service is not None and created_by_user_id is not None:
            effective_scopes = await self.policy_service.validate_integration_principal_allowed_scopes(
                session,
                actor_user_id=created_by_user_id,
                allowed_scopes=effective_scopes,
                anchor_entity_id=anchor_entity_id,
                scope_kind=scope_kind,
                allow_empty=True,
            )

        principal = IntegrationPrincipal(
            name=name,
            description=description,
            status=IntegrationPrincipalStatus.ACTIVE,
            scope_kind=scope_kind,
            anchor_entity_id=anchor_entity_id,
            inherit_from_tree=inherit_from_tree,
            allowed_scopes=normalized_scopes,
            created_by_user_id=created_by_user_id,
        )
        principal.roles = roles
        session.add(principal)
        await session.flush()
        await session.refresh(principal)
        principal = cast(IntegrationPrincipal, await self.get_principal(session, principal.id))

        if self.observability is not None:
            self.observability.log_api_key_lifecycle(
                operation="integration_principal_created",
                key_kind="system_integration",
                status=principal.status_enum.value,
                prefix=None,
                owner_id=str(principal.id),
                owner_type="integration_principal",
                actor_user_id=str(created_by_user_id) if created_by_user_id else None,
                entity_id=str(principal.anchor_entity_id) if principal.anchor_entity_id else None,
                entity_scoped=bool(principal.anchor_entity_id),
                event_source="integration_principal_service.create_principal",
                scope_kind=principal.scope_kind_enum.value,
                allowed_scopes=effective_scopes,
                actor_superuser=actor.is_superuser if actor is not None else None,
            )

        return principal

    async def update_principal(
        self,
        session: AsyncSession,
        principal_id: UUID,
        *,
        actor_user_id: Optional[UUID] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[IntegrationPrincipalStatus] = None,
        allowed_scopes: Optional[List[str]] = None,
        role_ids: Optional[List[UUID]] = None,
        inherit_from_tree: Optional[bool] = None,
    ) -> Optional[IntegrationPrincipal]:
        """Update mutable principal fields and enforce lifecycle side effects."""
        principal = await self.get_principal(session, principal_id)
        if principal is None:
            return None

        await self._load_actor(session, actor_user_id)

        if name is not None:
            principal.name = name
        if description is not None:
            principal.description = description

        if inherit_from_tree is not None:
            if principal.scope_kind_enum == IntegrationPrincipalScopeKind.PLATFORM_GLOBAL and inherit_from_tree:
                raise InvalidInputError(
                    message="Platform-global principals cannot inherit from entity trees",
                    details={"principal_id": str(principal.id)},
                )
            principal.inherit_from_tree = inherit_from_tree

        normalized_scopes = (
            self._normalize_scopes(allowed_scopes, allow_empty=True)
            if allowed_scopes is not None
            else list(principal.allowed_scopes or [])
        )
        roles = (
            await self._load_roles(session, self._normalize_role_ids(role_ids))
            if role_ids is not None
            else list(principal.roles or [])
        )
        self._validate_role_assignments(
            roles,
            scope_kind=principal.scope_kind_enum,
            anchor_entity_id=principal.anchor_entity_id,
        )
        effective_scopes = await self._resolve_effective_scopes(
            session,
            roles=roles,
            legacy_allowed_scopes=normalized_scopes,
        )
        if self.policy_service is not None and actor_user_id is not None:
            effective_scopes = await self.policy_service.validate_integration_principal_allowed_scopes(
                session,
                actor_user_id=actor_user_id,
                allowed_scopes=effective_scopes,
                anchor_entity_id=principal.anchor_entity_id,
                scope_kind=principal.scope_kind_enum,
                allow_empty=True,
            )
        if allowed_scopes is not None:
            principal.allowed_scopes = normalized_scopes
        if role_ids is not None:
            principal.roles = roles

        current_status = principal.status_enum
        status_changed = status is not None and status != current_status
        if status is not None:
            principal.status = status

        await session.flush()
        await session.refresh(principal)
        principal = cast(IntegrationPrincipal, await self.get_principal(session, principal.id))

        if status_changed and principal.status_enum != IntegrationPrincipalStatus.ACTIVE and self.api_key_service is not None:
            await self.api_key_service.revoke_integration_principal_api_keys(
                session,
                principal.id,
                revoked_by_id=actor_user_id,
                reason=f"Integration principal status changed to {principal.status_enum.value}",
                event_source="integration_principal_service.update_principal",
            )

        return principal

    async def archive_principal(
        self,
        session: AsyncSession,
        principal_id: UUID,
        *,
        actor_user_id: Optional[UUID] = None,
        reason: Optional[str] = None,
    ) -> bool:
        """Archive a principal and revoke all owned keys."""
        principal = await self.get_principal(session, principal_id)
        if principal is None:
            return False

        principal.status = IntegrationPrincipalStatus.ARCHIVED
        await session.flush()

        if self.api_key_service is not None:
            await self.api_key_service.revoke_integration_principal_api_keys(
                session,
                principal.id,
                revoked_by_id=actor_user_id,
                reason=reason or "Integration principal archived",
                event_source="integration_principal_service.archive_principal",
            )

        return True

    async def archive_entity_principals(
        self,
        session: AsyncSession,
        entity_id: UUID,
        *,
        archived_by_id: Optional[UUID] = None,
        reason: Optional[str] = None,
    ) -> int:
        """Archive every principal anchored to an entity."""
        principals = await self.get_many(
            session,
            IntegrationPrincipal.anchor_entity_id == entity_id,
            IntegrationPrincipal.status != IntegrationPrincipalStatus.ARCHIVED,
            limit=10_000,
        )
        if not principals:
            return 0

        for principal in principals:
            await self.archive_principal(
                session,
                principal.id,
                actor_user_id=archived_by_id,
                reason=reason or "Anchor entity archived",
            )

        return len(principals)

    async def _validate_scope_context(
        self,
        session: AsyncSession,
        *,
        scope_kind: IntegrationPrincipalScopeKind,
        anchor_entity_id: Optional[UUID],
        inherit_from_tree: bool,
    ) -> None:
        if scope_kind == IntegrationPrincipalScopeKind.PLATFORM_GLOBAL:
            if anchor_entity_id is not None:
                raise InvalidInputError(
                    message="Platform-global principals cannot have an anchor entity",
                    details={"anchor_entity_id": str(anchor_entity_id)},
                )
            if inherit_from_tree:
                raise InvalidInputError(
                    message="Platform-global principals cannot inherit from entity trees",
                    details={"scope_kind": scope_kind.value},
                )
            return

        if not self.config.enable_entity_hierarchy:
            raise InvalidInputError(
                message="Entity-scoped integration principals require EnterpriseRBAC",
                details={"scope_kind": scope_kind.value},
            )

        if scope_kind == IntegrationPrincipalScopeKind.ENTITY:
            if anchor_entity_id is None:
                raise InvalidInputError(
                    message="Entity-scoped principals require an anchor entity",
                    details={"scope_kind": scope_kind.value},
                )
            entity = await session.get(Entity, anchor_entity_id)
            if entity is None:
                raise InvalidInputError(
                    message="Anchor entity not found",
                    details={"anchor_entity_id": str(anchor_entity_id)},
                )
            if not entity.is_active():
                raise InvalidInputError(
                    message="Anchor entity must be active",
                    details={"anchor_entity_id": str(anchor_entity_id)},
                )
            return

    async def _load_actor(
        self,
        session: AsyncSession,
        actor_user_id: Optional[UUID],
    ) -> Optional[User]:
        if actor_user_id is None:
            return None
        actor = await session.get(User, actor_user_id)
        if actor is None:
            raise UserNotFoundError(message="User not found", details={"user_id": str(actor_user_id)})
        return actor

    @staticmethod
    def _normalize_scopes(scopes: List[str], *, allow_empty: bool = False) -> List[str]:
        normalized = sorted({scope.strip() for scope in scopes if scope and scope.strip()})
        if not normalized:
            if allow_empty:
                return []
            raise InvalidInputError(
                message="Integration principals require at least one allowed scope",
                details={"allowed_scopes": []},
            )
        return normalized

    @staticmethod
    def _normalize_role_ids(role_ids: Optional[List[UUID]]) -> List[UUID]:
        return list(dict.fromkeys(role_ids or []))

    async def _load_roles(
        self,
        session: AsyncSession,
        role_ids: List[UUID],
    ) -> List[Role]:
        if not role_ids:
            return []

        stmt = (
            select(Role)
            .where(
                cast(Any, Role.id).in_(role_ids),
                cast(Any, Role.status) == DefinitionStatus.ACTIVE,
            )
            .options(selectinload(cast(Any, Role.permissions)))
        )
        result = await session.execute(stmt)
        roles = list(result.scalars().all())
        roles_by_id = {role.id: role for role in roles}
        missing_role_ids = [role_id for role_id in role_ids if role_id not in roles_by_id]
        if missing_role_ids:
            raise InvalidInputError(
                message="One or more roles were not found or are not active",
                details={"role_ids": [str(role_id) for role_id in missing_role_ids]},
            )
        return [roles_by_id[role_id] for role_id in role_ids]

    @staticmethod
    def _validate_role_assignments(
        roles: List[Role],
        *,
        scope_kind: IntegrationPrincipalScopeKind,
        anchor_entity_id: Optional[UUID],
    ) -> None:
        if not roles:
            return

        if scope_kind == IntegrationPrincipalScopeKind.PLATFORM_GLOBAL:
            invalid_roles = [role.name for role in roles if not role.is_global]
            if invalid_roles:
                raise InvalidInputError(
                    message="Platform-global integration principals may only use global roles",
                    details={"role_names": invalid_roles},
                )
            return

        if scope_kind == IntegrationPrincipalScopeKind.ENTITY and anchor_entity_id is None:
            raise InvalidInputError(
                message="Entity-scoped integration principals require an anchor entity",
                details={"scope_kind": scope_kind.value},
            )

    async def _resolve_effective_scopes(
        self,
        session: AsyncSession,
        *,
        roles: List[Role],
        legacy_allowed_scopes: List[str],
    ) -> List[str]:
        role_ids = [role.id for role in roles]
        if self.policy_service is not None:
            effective_scopes = await self.policy_service.resolve_effective_scopes_for_assignments(
                session,
                role_ids=role_ids,
                legacy_allowed_scopes=legacy_allowed_scopes,
            )
        else:
            effective_scopes_set = set(legacy_allowed_scopes)
            for role in roles:
                for permission in getattr(role, "permissions", []):
                    if getattr(permission, "name", None):
                        effective_scopes_set.add(permission.name)
            effective_scopes = sorted(effective_scopes_set)

        if not effective_scopes:
            raise InvalidInputError(
                message="Integration principals require at least one role or allowed scope",
                details={"allowed_scopes": legacy_allowed_scopes, "role_ids": [str(role_id) for role_id in role_ids]},
            )

        return list(effective_scopes)
