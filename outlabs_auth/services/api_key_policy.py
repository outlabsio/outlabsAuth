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
from outlabs_auth.models.sql.enums import APIKeyKind
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
        if key_kind != APIKeyKind.PERSONAL:
            raise InvalidInputError(
                message="Only personal API keys are supported in v1",
                details={"key_kind": key_kind.value},
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
        if not scopes:
            raise InvalidInputError(
                message="Personal API keys require at least one explicit scope in EnterpriseRBAC",
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

        if actor_user_id is not None and actor_user_id != owner.id:
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

        if any("*" in scope for scope in scopes):
            raise InvalidInputError(
                message="Personal API keys do not allow wildcard scopes in v1",
                details={"scopes": scopes},
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

        if self.permission_service is None:
            return

        for scope in scopes:
            has_permission = await self.permission_service.check_permission(
                session,
                user_id=owner.id,
                permission=scope,
                entity_id=entity_id,
            )
            if not has_permission:
                raise InvalidInputError(
                    message="Requested scope exceeds the owner's current permissions",
                    details={
                        "owner_id": str(owner.id),
                        "scope": scope,
                        "entity_id": str(entity_id),
                    },
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
