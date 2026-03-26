"""
API key policy helpers.

Centralizes creation/update/runtime validation so EnterpriseRBAC can tighten
personal keys without duplicating rules across routers and auth backends.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import InvalidInputError
from outlabs_auth.models.sql.api_key import APIKey
from outlabs_auth.models.sql.closure import EntityClosure
from outlabs_auth.models.sql.entity import Entity
from outlabs_auth.models.sql.enums import APIKeyKind, DefinitionStatus
from outlabs_auth.models.sql.permission import Permission
from outlabs_auth.models.sql.user import User

if TYPE_CHECKING:
    from outlabs_auth.services.permission import PermissionService

logger = logging.getLogger(__name__)


class APIKeyPolicyService:
    """Grant-time and runtime policy checks for API keys."""

    def __init__(
        self,
        config: AuthConfig,
        permission_service: Optional["PermissionService"] = None,
    ):
        self.config = config
        self.permission_service = permission_service
        self._personal_allowed_action_prefixes = [
            prefix.lower()
            for prefix in getattr(
                config,
                "api_key_personal_allowed_action_prefixes",
                ["read", "list", "search", "view", "get", "update"],
            )
            if prefix
        ]
        self._personal_excluded_resources = {
            resource.lower()
            for resource in getattr(
                config,
                "api_key_personal_excluded_resources",
                ["api_key", "service_token"],
            )
            if resource
        }

    async def validate_create(
        self,
        session: AsyncSession,
        *,
        actor_user_id: Optional[UUID],
        owner: User,
        key_kind: APIKeyKind,
        scopes: Optional[List[str]],
        entity_id: Optional[UUID],
        inherit_from_tree: bool,
    ) -> None:
        """Validate a new key before it is stored."""
        await self._validate_key_policy(
            session,
            actor_user_id=actor_user_id,
            owner=owner,
            key_kind=key_kind,
            scopes=scopes,
            entity_id=entity_id,
            inherit_from_tree=inherit_from_tree,
        )

    async def validate_update(
        self,
        session: AsyncSession,
        *,
        actor_user_id: Optional[UUID],
        owner: User,
        api_key: APIKey,
        scopes: Optional[List[str]],
        entity_id: Optional[UUID],
        inherit_from_tree: bool,
    ) -> None:
        """Validate the effective state after an update."""
        await self._validate_key_policy(
            session,
            actor_user_id=actor_user_id,
            owner=owner,
            key_kind=api_key.key_kind,
            scopes=scopes,
            entity_id=entity_id,
            inherit_from_tree=inherit_from_tree,
        )

    async def validate_runtime_use(
        self,
        session: AsyncSession,
        *,
        api_key: APIKey,
    ) -> bool:
        """Check whether a stored API key is still usable right now."""
        owner = await session.get(User, api_key.owner_id)
        if owner is None:
            logger.warning("API key %s rejected because owner is missing", api_key.prefix)
            return False
        if not owner.can_authenticate():
            logger.warning("API key %s rejected because owner is inactive", api_key.prefix)
            return False

        if api_key.entity_id is None:
            return True

        entity = await session.get(Entity, api_key.entity_id)
        if entity is None:
            logger.warning("API key %s rejected because anchor entity is missing", api_key.prefix)
            return False
        if not entity.is_active():
            logger.warning("API key %s rejected because anchor entity is inactive", api_key.prefix)
            return False
        return True

    async def validate_runtime_permission(
        self,
        session: AsyncSession,
        *,
        owner_id: UUID,
        required_scope: str,
        entity_id: Optional[UUID],
    ) -> bool:
        """Check the current owner permission side of runtime intersection."""
        if self.permission_service is None:
            return True

        return await self.permission_service.check_permission(
            session,
            user_id=owner_id,
            permission=required_scope,
            entity_id=entity_id,
        )

    def get_allowed_key_kinds(self) -> List[APIKeyKind]:
        """Return the key kinds available in the current implementation slice."""
        return [APIKeyKind.PERSONAL]

    def get_personal_allowed_action_prefixes(self) -> List[str]:
        """Expose the configured action-prefix allowlist for personal keys."""
        return list(self._personal_allowed_action_prefixes)

    async def calculate_owner_grantable_scopes(
        self,
        session: AsyncSession,
        *,
        owner: User,
        key_kind: APIKeyKind,
        entity_id: Optional[UUID],
        inherit_from_tree: bool,
    ) -> List[str]:
        """Calculate scopes the owner may currently delegate for a key."""
        await self._validate_grant_context(
            session,
            actor_user_id=owner.id,
            owner=owner,
            key_kind=key_kind,
            entity_id=entity_id,
            inherit_from_tree=inherit_from_tree,
            allow_cross_owner_for_calculation=True,
        )
        return await self._calculate_user_grantable_scopes(
            session,
            user_id=owner.id,
            key_kind=key_kind,
            entity_id=entity_id,
        )

    async def calculate_actor_grantable_scopes(
        self,
        session: AsyncSession,
        *,
        actor_user_id: UUID,
        owner: User,
        key_kind: APIKeyKind,
        entity_id: Optional[UUID],
        inherit_from_tree: bool,
    ) -> List[str]:
        """Calculate scopes the acting user is currently authorized to grant."""
        await self._validate_grant_context(
            session,
            actor_user_id=actor_user_id,
            owner=owner,
            key_kind=key_kind,
            entity_id=entity_id,
            inherit_from_tree=inherit_from_tree,
            allow_cross_owner_for_calculation=True,
        )
        return await self._calculate_user_grantable_scopes(
            session,
            user_id=actor_user_id,
            key_kind=key_kind,
            entity_id=entity_id,
        )

    async def calculate_grantable_scopes(
        self,
        session: AsyncSession,
        *,
        actor_user_id: UUID,
        owner: User,
        key_kind: APIKeyKind,
        entity_id: Optional[UUID],
        inherit_from_tree: bool,
    ) -> List[str]:
        """Calculate the scopes grantable for an actor/owner/key/entity combination."""
        await self._validate_grant_context(
            session,
            actor_user_id=actor_user_id,
            owner=owner,
            key_kind=key_kind,
            entity_id=entity_id,
            inherit_from_tree=inherit_from_tree,
        )

        owner_scopes = set(
            await self._calculate_user_grantable_scopes(
                session,
                user_id=owner.id,
                key_kind=key_kind,
                entity_id=entity_id,
            )
        )
        actor_scopes = set(
            await self._calculate_user_grantable_scopes(
                session,
                user_id=actor_user_id,
                key_kind=key_kind,
                entity_id=entity_id,
            )
        )
        return sorted(owner_scopes & actor_scopes)

    async def _validate_key_policy(
        self,
        session: AsyncSession,
        *,
        actor_user_id: Optional[UUID],
        owner: User,
        key_kind: APIKeyKind,
        scopes: Optional[List[str]],
        entity_id: Optional[UUID],
        inherit_from_tree: bool,
    ) -> None:
        await self._validate_grant_context(
            session,
            actor_user_id=actor_user_id,
            owner=owner,
            key_kind=key_kind,
            entity_id=entity_id,
            inherit_from_tree=inherit_from_tree,
        )

        if not scopes:
            raise InvalidInputError(
                message="Personal API keys require at least one explicit scope in EnterpriseRBAC",
            )

        actor_id_to_check = actor_user_id or owner.id
        for scope in scopes:
            self._validate_scope_allowlist(scope, key_kind)

            await self._validate_user_has_scope(
                session,
                user_id=owner.id,
                scope=scope,
                entity_id=entity_id,
                error_message="Requested scope exceeds the owner's current permissions",
                details={
                    "owner_id": str(owner.id),
                    "scope": scope,
                    "entity_id": str(entity_id) if entity_id else None,
                },
            )

            if actor_id_to_check != owner.id:
                await self._validate_user_has_scope(
                    session,
                    user_id=actor_id_to_check,
                    scope=scope,
                    entity_id=entity_id,
                    error_message="Requested scope exceeds the actor's current permissions",
                    details={
                        "actor_user_id": str(actor_id_to_check),
                        "scope": scope,
                        "entity_id": str(entity_id) if entity_id else None,
                    },
                )

    async def _validate_grant_context(
        self,
        session: AsyncSession,
        *,
        actor_user_id: Optional[UUID],
        owner: User,
        key_kind: APIKeyKind,
        entity_id: Optional[UUID],
        inherit_from_tree: bool,
        allow_cross_owner_for_calculation: bool = False,
    ) -> None:
        if key_kind != APIKeyKind.PERSONAL:
            raise InvalidInputError(
                message="Only personal API keys are supported in v1",
                details={"key_kind": key_kind.value},
            )

        if inherit_from_tree and not self.config.api_key_personal_allow_inherit_from_tree:
            raise InvalidInputError(
                message="Personal API keys cannot inherit descendant entity access in this configuration",
            )

        if inherit_from_tree and entity_id is None:
            raise InvalidInputError(
                message="inherit_from_tree requires an entity anchor",
            )

        if not self.config.enable_entity_hierarchy:
            return

        if entity_id is None:
            raise InvalidInputError(
                message="Personal API keys require an entity anchor in EnterpriseRBAC",
            )

        entity = await session.get(Entity, entity_id)
        if entity is None:
            raise InvalidInputError(
                message="Entity anchor not found",
                details={"entity_id": str(entity_id)},
            )
        if not entity.is_active():
            raise InvalidInputError(
                message="Entity anchor must be active",
                details={"entity_id": str(entity_id)},
            )

        if actor_user_id is not None and actor_user_id != owner.id and not allow_cross_owner_for_calculation:
            raise InvalidInputError(
                message="Personal API keys can only be managed by their owner in v1",
                details={
                    "actor_user_id": str(actor_user_id),
                    "owner_id": str(owner.id),
                },
            )

        if not owner.can_authenticate():
            raise InvalidInputError(
                message="Personal API key owner must be active",
                details={"owner_id": str(owner.id)},
            )

        if not owner.is_superuser:
            root_entity_id = await self._get_root_entity_id(session, entity_id)
            if owner.root_entity_id is None or owner.root_entity_id != root_entity_id:
                raise InvalidInputError(
                    message="Personal API keys must stay within the owner's root entity",
                    details={
                        "owner_id": str(owner.id),
                        "owner_root_entity_id": (str(owner.root_entity_id) if owner.root_entity_id else None),
                        "entity_root_entity_id": str(root_entity_id),
                    },
                )

    def _validate_scope_allowlist(self, scope: str, key_kind: APIKeyKind) -> None:
        if "*" in scope:
            raise InvalidInputError(
                message="Personal API keys do not allow wildcard scopes in v1",
                details={"scope": scope},
            )

        if key_kind == APIKeyKind.PERSONAL and not self._is_personal_scope_allowed(scope):
            raise InvalidInputError(
                message="Scope is not allowed for personal API keys in v1",
                details={
                    "scope": scope,
                    "allowed_action_prefixes": self.get_personal_allowed_action_prefixes(),
                    "excluded_resources": sorted(self._personal_excluded_resources),
                },
            )

    async def _calculate_user_grantable_scopes(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        key_kind: APIKeyKind,
        entity_id: Optional[UUID],
    ) -> List[str]:
        permission_names = await self._list_active_permission_names(session)
        if self.permission_service is None:
            return sorted(
                permission_name
                for permission_name in permission_names
                if self._is_scope_allowed_for_key_kind(permission_name, key_kind)
            )

        grantable: list[str] = []
        for permission_name in permission_names:
            if not self._is_scope_allowed_for_key_kind(permission_name, key_kind):
                continue
            if await self.permission_service.check_permission(
                session,
                user_id=user_id,
                permission=permission_name,
                entity_id=entity_id,
            ):
                grantable.append(permission_name)
        return sorted(grantable)

    async def _validate_user_has_scope(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        scope: str,
        entity_id: Optional[UUID],
        error_message: str,
        details: dict[str, Optional[str]],
    ) -> None:
        if self.permission_service is None:
            return

        has_permission = await self.permission_service.check_permission(
            session,
            user_id=user_id,
            permission=scope,
            entity_id=entity_id,
        )
        if not has_permission:
            raise InvalidInputError(
                message=error_message,
                details=details,
            )

    async def _list_active_permission_names(
        self,
        session: AsyncSession,
    ) -> List[str]:
        stmt = (
            select(Permission.name).where(Permission.status == DefinitionStatus.ACTIVE).order_by(Permission.name.asc())
        )
        result = await session.execute(stmt)
        return [row[0] for row in result.all()]

    def _is_scope_allowed_for_key_kind(
        self,
        scope: str,
        key_kind: APIKeyKind,
    ) -> bool:
        if key_kind == APIKeyKind.PERSONAL:
            return self._is_personal_scope_allowed(scope)
        return False

    def _is_personal_scope_allowed(self, scope: str) -> bool:
        from outlabs_auth.services.permission import PermissionService

        resource, action, _ = PermissionService._parse_permission_name(scope)
        normalized_resource = resource.lower()
        normalized_action = action.lower()
        if normalized_resource in self._personal_excluded_resources:
            return False
        return any(
            normalized_action == prefix or normalized_action.startswith(f"{prefix}_")
            for prefix in self._personal_allowed_action_prefixes
        )

    async def _get_root_entity_id(
        self,
        session: AsyncSession,
        entity_id: UUID,
    ) -> UUID:
        stmt = (
            select(EntityClosure.ancestor_id)
            .where(EntityClosure.descendant_id == entity_id)
            .order_by(EntityClosure.depth.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        row = result.first()
        return row[0] if row else entity_id
