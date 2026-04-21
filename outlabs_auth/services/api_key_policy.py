"""
API key policy helpers.

Centralizes creation/update/runtime validation so EnterpriseRBAC can tighten
personal keys without duplicating rules across routers and auth backends.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Mapping, Optional, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import InvalidInputError
from outlabs_auth.models.sql.api_key import APIKey, APIKeyScope
from outlabs_auth.models.sql.closure import EntityClosure
from outlabs_auth.models.sql.entity import Entity
from outlabs_auth.models.sql.enums import (
    APIKeyKind,
    APIKeyStatus,
    DefinitionStatus,
    IntegrationPrincipalScopeKind,
)
from outlabs_auth.models.sql.integration_principal import IntegrationPrincipal, IntegrationPrincipalRole
from outlabs_auth.models.sql.permission import Permission
from outlabs_auth.models.sql.user import User

if TYPE_CHECKING:
    from outlabs_auth.observability.service import ObservabilityService
    from outlabs_auth.services.permission import PermissionService

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class APIKeyEffectivenessResult:
    """Derived runtime effectiveness for a stored API key."""

    is_currently_effective: bool
    ineffective_reasons: list[str] = field(default_factory=list)


class APIKeyPolicyService:
    """Grant-time and runtime policy checks for API keys."""

    def __init__(
        self,
        config: AuthConfig,
        permission_service: Optional["PermissionService"] = None,
        observability: Optional["ObservabilityService"] = None,
    ):
        self.config = config
        self.permission_service = permission_service
        self.observability = observability
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
        self._system_allowed_action_prefixes = [
            prefix.lower()
            for prefix in getattr(
                config,
                "api_key_system_allowed_action_prefixes",
                [
                    "create",
                    "read",
                    "list",
                    "search",
                    "view",
                    "get",
                    "update",
                    "delete",
                    "write",
                    "run",
                    "execute",
                    "trigger",
                    "control",
                    "sync",
                    "import",
                    "export",
                    "generate",
                    "manage",
                ],
            )
            if prefix
        ]
        self._system_excluded_resources = {
            resource.lower()
            for resource in getattr(
                config,
                "api_key_system_excluded_resources",
                ["api_key", "service_token", "integration_principal"],
            )
            if resource
        }

    async def validate_create(
        self,
        session: AsyncSession,
        *,
        actor_user_id: Optional[UUID],
        owner: Optional[User] = None,
        integration_principal: Optional[IntegrationPrincipal] = None,
        key_kind: APIKeyKind,
        scopes: Optional[List[str]],
        entity_id: Optional[UUID],
        inherit_from_tree: bool,
    ) -> None:
        """Validate a new key before it is stored."""
        try:
            await self._validate_key_policy(
                session,
                actor_user_id=actor_user_id,
                owner=owner,
                integration_principal=integration_principal,
                key_kind=key_kind,
                scopes=scopes,
                entity_id=entity_id,
                inherit_from_tree=inherit_from_tree,
            )
        except InvalidInputError as exc:
            self._log_policy_decision(
                surface="grant_create",
                outcome="denied",
                reason=self._get_policy_reason(exc),
                key_kind=key_kind,
                actor_user_id=str(actor_user_id) if actor_user_id else None,
                owner_id=str(self._resolve_owner_id(owner=owner, integration_principal=integration_principal)),
                owner_type=self._resolve_owner_type(owner=owner, integration_principal=integration_principal),
                entity_id=str(entity_id) if entity_id else None,
            )
            raise

    async def validate_update(
        self,
        session: AsyncSession,
        *,
        actor_user_id: Optional[UUID],
        owner: Optional[User] = None,
        integration_principal: Optional[IntegrationPrincipal] = None,
        api_key: APIKey,
        scopes: Optional[List[str]],
        entity_id: Optional[UUID],
        inherit_from_tree: bool,
    ) -> None:
        """Validate the effective state after an update."""
        try:
            await self._validate_key_policy(
                session,
                actor_user_id=actor_user_id,
                owner=owner,
                integration_principal=integration_principal,
                key_kind=api_key.key_kind,
                scopes=scopes,
                entity_id=entity_id,
                inherit_from_tree=inherit_from_tree,
            )
        except InvalidInputError as exc:
            self._log_policy_decision(
                surface="grant_update",
                outcome="denied",
                reason=self._get_policy_reason(exc),
                key_kind=api_key.key_kind,
                actor_user_id=str(actor_user_id) if actor_user_id else None,
                owner_id=str(self._resolve_owner_id(owner=owner, integration_principal=integration_principal)),
                owner_type=self._resolve_owner_type(owner=owner, integration_principal=integration_principal),
                entity_id=str(entity_id) if entity_id else None,
                prefix=api_key.prefix,
            )
            raise

    async def validate_runtime_use(
        self,
        session: AsyncSession,
        *,
        api_key: APIKey,
    ) -> bool:
        """Check whether a stored API key is still usable right now."""
        if api_key.integration_principal_id is not None:
            principal = await session.get(IntegrationPrincipal, api_key.integration_principal_id)
            if principal is None:
                logger.warning("API key %s rejected because principal is missing", api_key.prefix)
                self._log_policy_decision(
                    surface="runtime_use",
                    outcome="denied",
                    reason="integration_principal_missing",
                    key_kind=api_key.key_kind,
                    prefix=api_key.prefix,
                    owner_type="integration_principal",
                )
                return False
            if not principal.is_active():
                logger.warning("API key %s rejected because principal is inactive", api_key.prefix)
                self._log_policy_decision(
                    surface="runtime_use",
                    outcome="denied",
                    reason="integration_principal_inactive",
                    key_kind=api_key.key_kind,
                    prefix=api_key.prefix,
                    owner_id=str(principal.id),
                    owner_type="integration_principal",
                )
                return False
        else:
            owner = await session.get(User, api_key.owner_id)
            if owner is None:
                logger.warning("API key %s rejected because owner is missing", api_key.prefix)
                self._log_policy_decision(
                    surface="runtime_use",
                    outcome="denied",
                    reason="owner_missing",
                    key_kind=api_key.key_kind,
                    prefix=api_key.prefix,
                    owner_type="user",
                )
                return False
            if not owner.can_authenticate():
                logger.warning("API key %s rejected because owner is inactive", api_key.prefix)
                self._log_policy_decision(
                    surface="runtime_use",
                    outcome="denied",
                    reason="owner_inactive",
                    key_kind=api_key.key_kind,
                    prefix=api_key.prefix,
                    owner_id=str(owner.id),
                    owner_type="user",
                )
                return False

        if api_key.entity_id is None:
            return True

        entity = await session.get(Entity, api_key.entity_id)
        if entity is None:
            logger.warning("API key %s rejected because anchor entity is missing", api_key.prefix)
            self._log_policy_decision(
                surface="runtime_use",
                outcome="denied",
                reason="anchor_missing",
                key_kind=api_key.key_kind,
                prefix=api_key.prefix,
                owner_id=str(api_key.resolved_owner_id) if api_key.resolved_owner_id else None,
                owner_type=api_key.owner_type,
            )
            return False
        if not entity.is_active():
            logger.warning("API key %s rejected because anchor entity is inactive", api_key.prefix)
            self._log_policy_decision(
                surface="runtime_use",
                outcome="denied",
                reason="anchor_inactive",
                key_kind=api_key.key_kind,
                prefix=api_key.prefix,
                owner_id=str(api_key.resolved_owner_id) if api_key.resolved_owner_id else None,
                owner_type=api_key.owner_type,
                entity_id=str(api_key.entity_id),
            )
            return False
        return True

    async def validate_runtime_permission(
        self,
        session: AsyncSession,
        *,
        api_key: APIKey,
        required_scope: str,
        entity_id: Optional[UUID],
    ) -> bool:
        """Check the current owner permission side of runtime intersection."""
        if api_key.integration_principal_id is not None:
            principal = await session.get(IntegrationPrincipal, api_key.integration_principal_id)
            if principal is None or not principal.is_active():
                return False
            from outlabs_auth.services.api_key import APIKeyService

            principal_allowed_scopes = await self.resolve_integration_principal_effective_scopes(
                session,
                principal,
            )
            return APIKeyService.scopes_allow_permission(principal_allowed_scopes, required_scope)

        if self.permission_service is None or api_key.owner_id is None:
            return True

        return await self.permission_service.check_permission(
            session,
            user_id=api_key.owner_id,
            permission=required_scope,
            entity_id=entity_id,
        )

    async def evaluate_effectiveness(
        self,
        session: AsyncSession,
        *,
        api_key: APIKey,
        scopes: Optional[List[str]] = None,
    ) -> APIKeyEffectivenessResult:
        """Return derived runtime effectiveness and the reasons when a key is ineffective."""
        return (
            await self.evaluate_effectiveness_map(
                session,
                api_keys=[api_key],
                scopes_by_key_id={api_key.id: scopes} if scopes is not None else None,
            )
        )[api_key.id]

    async def evaluate_effectiveness_map(
        self,
        session: AsyncSession,
        *,
        api_keys: List[APIKey],
        scopes_by_key_id: Optional[Mapping[UUID, Optional[List[str]]]] = None,
    ) -> Dict[UUID, APIKeyEffectivenessResult]:
        """Batch runtime effectiveness evaluation for one or more API keys."""
        if not api_keys:
            return {}

        key_ids = [api_key.id for api_key in api_keys]
        resolved_scopes_by_key_id: Dict[UUID, List[str]] = {
            key_id: list(scopes) for key_id, scopes in (scopes_by_key_id or {}).items() if scopes is not None
        }
        missing_scope_key_ids = [key_id for key_id in key_ids if key_id not in resolved_scopes_by_key_id]
        if missing_scope_key_ids:
            stmt = (
                select(
                    cast(Any, APIKeyScope.api_key_id),
                    cast(Any, APIKeyScope.scope),
                )
                .where(cast(Any, APIKeyScope.api_key_id).in_(missing_scope_key_ids))
                .order_by(cast(Any, APIKeyScope.api_key_id), cast(Any, APIKeyScope.scope))
            )
            result = await session.execute(stmt)
            for key_id in missing_scope_key_ids:
                resolved_scopes_by_key_id.setdefault(key_id, [])
            for key_id, scope in result.all():
                resolved_scopes_by_key_id.setdefault(cast(UUID, key_id), []).append(cast(str, scope))

        owner_ids = list({api_key.owner_id for api_key in api_keys if api_key.owner_id is not None})
        principal_ids = list(
            {api_key.integration_principal_id for api_key in api_keys if api_key.integration_principal_id is not None}
        )
        entity_ids = list({api_key.entity_id for api_key in api_keys if api_key.entity_id is not None})

        owners_by_id: Dict[UUID, User] = {}
        principals_by_id: Dict[UUID, IntegrationPrincipal] = {}
        entities_by_id: Dict[UUID, Entity] = {}

        if owner_ids:
            owners_result = await session.execute(select(User).where(cast(Any, User.id).in_(owner_ids)))
            owners_by_id = {owner.id: owner for owner in owners_result.scalars().all()}
        if principal_ids:
            principals_result = await session.execute(
                select(IntegrationPrincipal).where(cast(Any, IntegrationPrincipal.id).in_(principal_ids))
            )
            principals_by_id = {principal.id: principal for principal in principals_result.scalars().all()}
        if entity_ids:
            entities_result = await session.execute(select(Entity).where(cast(Any, Entity.id).in_(entity_ids)))
            entities_by_id = {entity.id: entity for entity in entities_result.scalars().all()}

        from outlabs_auth.services.api_key import APIKeyService

        owner_grantable_scope_cache: Dict[tuple[UUID, APIKeyKind, Optional[UUID], bool], List[str]] = {}
        principal_effective_scopes_by_id = (
            await self.resolve_integration_principals_effective_scopes_map(
                session,
                principals_by_id.values(),
            )
            if principals_by_id
            else {}
        )
        results: Dict[UUID, APIKeyEffectivenessResult] = {}

        for api_key in api_keys:
            reasons: list[str] = []

            if api_key.status == APIKeyStatus.SUSPENDED:
                reasons.append("key_suspended")
            elif api_key.status == APIKeyStatus.REVOKED:
                reasons.append("key_revoked")
            elif api_key.status == APIKeyStatus.EXPIRED:
                reasons.append("key_expired")
            elif api_key.expires_at and datetime.now(timezone.utc) > api_key.expires_at:
                reasons.append("key_expired")

            principal = None
            owner = None
            if api_key.integration_principal_id is not None:
                principal = principals_by_id.get(api_key.integration_principal_id)
                if principal is None:
                    reasons.append("integration_principal_missing")
                elif not principal.is_active():
                    reasons.append("integration_principal_inactive")
            else:
                owner = owners_by_id.get(api_key.owner_id) if api_key.owner_id is not None else None
                if owner is None:
                    reasons.append("owner_missing")
                elif not owner.can_authenticate():
                    reasons.append("owner_inactive")

            if api_key.entity_id is not None:
                entity = entities_by_id.get(api_key.entity_id)
                if entity is None:
                    reasons.append("anchor_missing")
                elif not entity.is_active():
                    reasons.append("anchor_inactive")

            if reasons:
                results[api_key.id] = APIKeyEffectivenessResult(
                    is_currently_effective=False,
                    ineffective_reasons=reasons,
                )
                continue

            if not self.config.enable_entity_hierarchy:
                results[api_key.id] = APIKeyEffectivenessResult(
                    is_currently_effective=True,
                    ineffective_reasons=[],
                )
                continue

            stored_scopes = resolved_scopes_by_key_id.get(api_key.id, [])

            if principal is not None:
                owner_grantable_scopes = list(principal_effective_scopes_by_id.get(principal.id, []))
            else:
                if owner is None:
                    results[api_key.id] = APIKeyEffectivenessResult(
                        is_currently_effective=False,
                        ineffective_reasons=["owner_missing"],
                    )
                    continue
                cache_key = (owner.id, api_key.key_kind, api_key.entity_id, api_key.inherit_from_tree)
                if cache_key not in owner_grantable_scope_cache:
                    try:
                        owner_grantable_scope_cache[cache_key] = await self.calculate_owner_grantable_scopes(
                            session,
                            owner=owner,
                            key_kind=api_key.key_kind,
                            entity_id=api_key.entity_id,
                            inherit_from_tree=api_key.inherit_from_tree,
                        )
                    except InvalidInputError:
                        results[api_key.id] = APIKeyEffectivenessResult(
                            is_currently_effective=False,
                            ineffective_reasons=["policy_invalid"],
                        )
                        continue
                owner_grantable_scopes = owner_grantable_scope_cache[cache_key]

            has_effective_scope = any(
                APIKeyService.scopes_allow_permission(stored_scopes, permission_name)
                for permission_name in owner_grantable_scopes
            )
            if not has_effective_scope:
                reasons.append("no_effective_scopes")

            results[api_key.id] = APIKeyEffectivenessResult(
                is_currently_effective=not reasons,
                ineffective_reasons=reasons,
            )

        return results

    async def load_integration_principal_role_ids_map(
        self,
        session: AsyncSession,
        principal_ids: Iterable[UUID],
    ) -> Dict[UUID, List[UUID]]:
        """Load assigned role IDs for one or more integration principals."""
        unique_principal_ids = list(dict.fromkeys(principal_ids))
        if not unique_principal_ids:
            return {}

        stmt = (
            select(
                cast(Any, IntegrationPrincipalRole.integration_principal_id),
                cast(Any, IntegrationPrincipalRole.role_id),
            )
            .where(cast(Any, IntegrationPrincipalRole.integration_principal_id).in_(unique_principal_ids))
            .order_by(
                cast(Any, IntegrationPrincipalRole.integration_principal_id),
                cast(Any, IntegrationPrincipalRole.role_id),
            )
        )
        result = await session.execute(stmt)

        role_ids_by_principal_id: Dict[UUID, List[UUID]] = {principal_id: [] for principal_id in unique_principal_ids}
        for principal_id, role_id in result.all():
            role_ids_by_principal_id.setdefault(cast(UUID, principal_id), []).append(cast(UUID, role_id))

        return role_ids_by_principal_id

    async def resolve_effective_scopes_for_assignments(
        self,
        session: AsyncSession,
        *,
        role_ids: List[UUID],
        legacy_allowed_scopes: List[str],
    ) -> List[str]:
        """Resolve effective system scopes from assigned roles plus compatibility scopes."""
        normalized_legacy_scopes = sorted({scope for scope in legacy_allowed_scopes if scope})
        unique_role_ids = list(dict.fromkeys(role_ids))
        if not unique_role_ids or self.permission_service is None:
            return normalized_legacy_scopes

        permissions_by_role_id = await self.permission_service.get_permissions_for_roles(
            session,
            unique_role_ids,
        )

        effective_scopes = set(normalized_legacy_scopes)
        for permissions in permissions_by_role_id.values():
            for permission in permissions:
                if permission.name:
                    effective_scopes.add(permission.name)

        return sorted(effective_scopes)

    async def resolve_integration_principals_effective_scopes_map(
        self,
        session: AsyncSession,
        principals: Iterable[IntegrationPrincipal],
    ) -> Dict[UUID, List[str]]:
        """Resolve effective scopes for multiple principals in one pass."""
        principal_list = list(principals)
        if not principal_list:
            return {}

        role_ids_by_principal_id = await self.load_integration_principal_role_ids_map(
            session,
            [principal.id for principal in principal_list],
        )
        all_role_ids = list(
            dict.fromkeys(role_id for role_ids in role_ids_by_principal_id.values() for role_id in role_ids)
        )
        permissions_by_role_id = (
            await self.permission_service.get_permissions_for_roles(session, all_role_ids)
            if all_role_ids and self.permission_service is not None
            else {}
        )

        scopes_by_principal_id: Dict[UUID, List[str]] = {}
        for principal in principal_list:
            effective_scopes = set(scope for scope in (principal.allowed_scopes or []) if scope)
            for role_id in role_ids_by_principal_id.get(principal.id, []):
                for permission in permissions_by_role_id.get(role_id, []):
                    if permission.name:
                        effective_scopes.add(permission.name)
            scopes_by_principal_id[principal.id] = sorted(effective_scopes)

        return scopes_by_principal_id

    async def resolve_integration_principal_effective_scopes(
        self,
        session: AsyncSession,
        principal: IntegrationPrincipal,
    ) -> List[str]:
        """Resolve the effective scope envelope for a single integration principal."""
        return (
            await self.resolve_integration_principals_effective_scopes_map(
                session,
                [principal],
            )
        ).get(principal.id, [])

    def get_allowed_key_kinds(self) -> List[APIKeyKind]:
        """Return the key kinds available in the current implementation slice."""
        return [APIKeyKind.PERSONAL, APIKeyKind.SYSTEM_INTEGRATION]

    def get_personal_allowed_action_prefixes(self) -> List[str]:
        """Expose the configured action-prefix allowlist for personal keys."""
        return list(self._personal_allowed_action_prefixes)

    def get_system_allowed_action_prefixes(self) -> List[str]:
        """Expose the configured action-prefix allowlist for system integration keys."""
        return list(self._system_allowed_action_prefixes)

    async def calculate_owner_grantable_scopes(
        self,
        session: AsyncSession,
        *,
        owner: Optional[User] = None,
        integration_principal: Optional[IntegrationPrincipal] = None,
        key_kind: APIKeyKind,
        entity_id: Optional[UUID],
        inherit_from_tree: bool,
    ) -> List[str]:
        """Calculate scopes the owner may currently delegate for a key."""
        if owner is None:
            raise self._policy_error(
                "owner_required",
                message="Personal grantable-scope calculation requires a user owner",
            )
        await self._validate_grant_context(
            session,
            actor_user_id=owner.id,
            owner=owner,
            integration_principal=integration_principal,
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
            user=owner,
        )

    async def calculate_actor_grantable_scopes(
        self,
        session: AsyncSession,
        *,
        actor_user_id: UUID,
        owner: Optional[User] = None,
        integration_principal: Optional[IntegrationPrincipal] = None,
        key_kind: APIKeyKind,
        entity_id: Optional[UUID],
        inherit_from_tree: bool,
    ) -> List[str]:
        """Calculate scopes the acting user is currently authorized to grant."""
        await self._validate_grant_context(
            session,
            actor_user_id=actor_user_id,
            owner=owner,
            integration_principal=integration_principal,
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
        owner: Optional[User] = None,
        integration_principal: Optional[IntegrationPrincipal] = None,
        key_kind: APIKeyKind,
        entity_id: Optional[UUID],
        inherit_from_tree: bool,
    ) -> List[str]:
        """Calculate the scopes grantable for an actor/owner/key/entity combination."""
        if owner is None:
            raise self._policy_error(
                "owner_required",
                message="Personal grantable-scope calculation requires a user owner",
            )
        try:
            await self._validate_grant_context(
                session,
                actor_user_id=actor_user_id,
                owner=owner,
                integration_principal=integration_principal,
                key_kind=key_kind,
                entity_id=entity_id,
                inherit_from_tree=inherit_from_tree,
            )
            permission_names = await self._list_active_permission_names(session)
            owner_scopes = set(
                await self._calculate_user_grantable_scopes(
                    session,
                    user_id=owner.id,
                    key_kind=key_kind,
                    entity_id=entity_id,
                    candidate_permission_names=permission_names,
                    user=owner,
                )
            )
            if actor_user_id == owner.id:
                return sorted(owner_scopes)
            actor_scopes = set(
                await self._calculate_user_grantable_scopes(
                    session,
                    user_id=actor_user_id,
                    key_kind=key_kind,
                    entity_id=entity_id,
                    candidate_permission_names=permission_names,
                )
            )
            return sorted(owner_scopes & actor_scopes)
        except InvalidInputError as exc:
            self._log_policy_decision(
                surface="grantable_scopes",
                outcome="denied",
                reason=self._get_policy_reason(exc),
                key_kind=key_kind,
                actor_user_id=str(actor_user_id),
                owner_id=str(self._resolve_owner_id(owner=owner, integration_principal=integration_principal)),
                owner_type=self._resolve_owner_type(owner=owner, integration_principal=integration_principal),
                entity_id=str(entity_id) if entity_id else None,
            )
            raise

    async def calculate_system_integration_grantable_scopes(
        self,
        session: AsyncSession,
        *,
        actor_user_id: UUID,
        anchor_entity_id: Optional[UUID],
        scope_kind: IntegrationPrincipalScopeKind,
    ) -> List[str]:
        """List system-integration scopes an actor may currently grant."""
        actor = await self._load_actor_user(session, actor_user_id)
        if not actor.can_authenticate():
            raise self._policy_error(
                "actor_inactive",
                message="Only active users may manage system integration credentials",
                details={"actor_user_id": str(actor_user_id)},
            )

        permission_names = await self._list_active_permission_names(session)
        allowed_names = self._filter_allowed_permission_names(
            permission_names,
            APIKeyKind.SYSTEM_INTEGRATION,
        )

        if scope_kind == IntegrationPrincipalScopeKind.PLATFORM_GLOBAL:
            if actor.is_superuser:
                return sorted(allowed_names)
            if self.config.enable_entity_hierarchy:
                raise self._policy_error(
                    "superuser_required",
                    message="Platform-global integration principals require a superuser actor",
                    details={"actor_user_id": str(actor_user_id)},
                )
            if self.permission_service is None:
                return []
            return sorted(
                await self.permission_service.get_effective_permission_names(
                    session,
                    user_id=actor_user_id,
                    candidate_permission_names=allowed_names,
                    user=actor,
                )
            )

        if anchor_entity_id is None:
            raise self._policy_error(
                "entity_anchor_required",
                message="Entity-scoped integration principals require an anchor entity",
            )

        entity = await session.get(Entity, anchor_entity_id)
        if entity is None or not entity.is_active():
            raise self._policy_error(
                "entity_anchor_invalid",
                message="Entity anchor must exist and be active",
                details={"entity_id": str(anchor_entity_id)},
            )

        root_entity_id = await self._get_root_entity_id(session, anchor_entity_id)
        if not actor.is_superuser and actor.root_entity_id != root_entity_id:
            raise self._policy_error(
                "root_entity_mismatch",
                message="Entity-scoped integration principals must stay within the actor's root entity",
                details={
                    "actor_user_id": str(actor_user_id),
                    "actor_root_entity_id": str(actor.root_entity_id) if actor.root_entity_id else None,
                    "entity_root_entity_id": str(root_entity_id),
                },
            )

        if self.permission_service is None or actor.is_superuser:
            return sorted(allowed_names)

        if not getattr(self.permission_service.config, "enable_abac", False):
            return sorted(
                await self.permission_service.get_effective_permission_names(
                    session,
                    user_id=actor_user_id,
                    entity_id=anchor_entity_id,
                    candidate_permission_names=allowed_names,
                    user=actor,
                )
            )

        grantable: list[str] = []
        for permission_name in allowed_names:
            if await self.permission_service.check_permission(
                session,
                user_id=actor_user_id,
                permission=permission_name,
                entity_id=anchor_entity_id,
                user=actor,
            ):
                grantable.append(permission_name)
        return sorted(grantable)

    async def validate_integration_principal_allowed_scopes(
        self,
        session: AsyncSession,
        *,
        actor_user_id: UUID,
        allowed_scopes: List[str],
        anchor_entity_id: Optional[UUID],
        scope_kind: IntegrationPrincipalScopeKind,
        allow_empty: bool = False,
    ) -> List[str]:
        """Validate a principal scope envelope against actor authority and allowlists."""
        normalized_scopes = sorted({scope for scope in allowed_scopes if scope})
        if not normalized_scopes:
            if allow_empty:
                return []
            raise self._policy_error(
                "explicit_scopes_required",
                message="Integration principals require at least one explicit scope",
            )

        grantable_scopes = set(
            await self.calculate_system_integration_grantable_scopes(
                session,
                actor_user_id=actor_user_id,
                anchor_entity_id=anchor_entity_id,
                scope_kind=scope_kind,
            )
        )
        for scope in normalized_scopes:
            self._validate_scope_allowlist(scope, APIKeyKind.SYSTEM_INTEGRATION)
            if scope not in grantable_scopes:
                raise self._policy_error(
                    "actor_scope_exceeded",
                    message="Requested scope exceeds the actor's current grantable system scopes",
                    details={
                        "actor_user_id": str(actor_user_id),
                        "scope": scope,
                        "anchor_entity_id": str(anchor_entity_id) if anchor_entity_id else None,
                        "scope_kind": scope_kind.value,
                    },
                )
        return normalized_scopes

    async def _validate_key_policy(
        self,
        session: AsyncSession,
        *,
        actor_user_id: Optional[UUID],
        owner: Optional[User] = None,
        integration_principal: Optional[IntegrationPrincipal] = None,
        key_kind: APIKeyKind,
        scopes: Optional[List[str]],
        entity_id: Optional[UUID],
        inherit_from_tree: bool,
    ) -> None:
        await self._validate_grant_context(
            session,
            actor_user_id=actor_user_id,
            owner=owner,
            integration_principal=integration_principal,
            key_kind=key_kind,
            entity_id=entity_id,
            inherit_from_tree=inherit_from_tree,
        )

        if key_kind == APIKeyKind.SYSTEM_INTEGRATION:
            if integration_principal is None:
                raise self._policy_error(
                    "integration_principal_required",
                    message="System integration API keys require an integration principal owner",
                )
            if actor_user_id is None:
                raise self._policy_error(
                    "actor_required",
                    message="System integration API keys require an acting user",
                )

            principal_allowed_scopes = await self.resolve_integration_principal_effective_scopes(
                session,
                integration_principal,
            )
            requested_scopes = list(scopes) if scopes else principal_allowed_scopes
            if not requested_scopes:
                raise self._policy_error(
                    "principal_has_no_effective_scopes",
                    message="System integration principals must have at least one effective permission before minting keys",
                    details={"integration_principal_id": str(integration_principal.id)},
                )

            normalized_scopes = await self.validate_integration_principal_allowed_scopes(
                session,
                actor_user_id=actor_user_id,
                allowed_scopes=requested_scopes,
                anchor_entity_id=integration_principal.anchor_entity_id,
                scope_kind=integration_principal.scope_kind,
            )
            from outlabs_auth.services.api_key import APIKeyService

            for scope in normalized_scopes:
                if not APIKeyService.scopes_allow_permission(principal_allowed_scopes, scope):
                    raise self._policy_error(
                        "principal_scope_exceeded",
                        message="Requested scope exceeds the integration principal's allowed scopes",
                        details={
                            "integration_principal_id": str(integration_principal.id),
                            "scope": scope,
                        },
                    )
            return

        if not self.config.enable_entity_hierarchy:
            return

        if not scopes:
            raise self._policy_error(
                "explicit_scopes_required",
                message="Personal API keys require at least one explicit scope in EnterpriseRBAC",
            )

        if owner is None:
            raise self._policy_error(
                "owner_required",
                message="Personal API keys require a user owner",
            )

        actor_id_to_check = actor_user_id or owner.id
        for scope in scopes:
            self._validate_scope_allowlist(scope, key_kind)

            await self._validate_user_has_scope(
                session,
                user_id=owner.id,
                scope=scope,
                entity_id=entity_id,
                policy_reason="owner_scope_exceeded",
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
                    policy_reason="actor_scope_exceeded",
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
        owner: Optional[User] = None,
        integration_principal: Optional[IntegrationPrincipal] = None,
        key_kind: APIKeyKind,
        entity_id: Optional[UUID],
        inherit_from_tree: bool,
        allow_cross_owner_for_calculation: bool = False,
    ) -> None:
        if (owner is None) == (integration_principal is None):
            raise self._policy_error(
                "invalid_owner_context",
                message="Exactly one API key owner type must be provided",
                details={"key_kind": key_kind.value},
            )

        if key_kind == APIKeyKind.PERSONAL:
            if owner is None:
                raise self._policy_error(
                    "owner_required",
                    message="Personal API keys require a user owner",
                )
            if integration_principal is not None:
                raise self._policy_error(
                    "invalid_owner_context",
                    message="Personal API keys cannot be owned by integration principals",
                )
            if inherit_from_tree and not self.config.api_key_personal_allow_inherit_from_tree:
                raise self._policy_error(
                    "inherit_from_tree_disallowed",
                    message="Personal API keys cannot inherit descendant entity access in this configuration",
                )

            if inherit_from_tree and entity_id is None:
                raise self._policy_error(
                    "inherit_from_tree_requires_anchor",
                    message="inherit_from_tree requires an entity anchor",
                )

            if entity_id is not None and not self.config.enable_entity_hierarchy:
                raise self._policy_error(
                    "entity_anchor_unsupported",
                    message="Entity anchors are not supported when entity hierarchy is disabled",
                    details={"entity_id": str(entity_id)},
                )

            if not self.config.enable_entity_hierarchy:
                return

            if entity_id is None:
                if not owner.can_authenticate():
                    raise self._policy_error(
                        "owner_inactive",
                        message="Personal API key owner must be active",
                        details={"owner_id": str(owner.id)},
                    )

                if actor_user_id is not None and actor_user_id != owner.id and not allow_cross_owner_for_calculation:
                    raise self._policy_error(
                        "cross_owner_personal_key_forbidden",
                        message="Personal API keys can only be managed by their owner in v1",
                        details={
                            "actor_user_id": str(actor_user_id),
                            "owner_id": str(owner.id),
                        },
                    )
                return

            entity = await session.get(Entity, entity_id)
            if entity is None:
                raise self._policy_error(
                    "entity_anchor_not_found",
                    message="Entity anchor not found",
                    details={"entity_id": str(entity_id)},
                )
            if not entity.is_active():
                raise self._policy_error(
                    "entity_anchor_inactive",
                    message="Entity anchor must be active",
                    details={"entity_id": str(entity_id)},
                )

            if actor_user_id is not None and actor_user_id != owner.id and not allow_cross_owner_for_calculation:
                raise self._policy_error(
                    "cross_owner_personal_key_forbidden",
                    message="Personal API keys can only be managed by their owner in v1",
                    details={
                        "actor_user_id": str(actor_user_id),
                        "owner_id": str(owner.id),
                    },
                )

            if not owner.can_authenticate():
                raise self._policy_error(
                    "owner_inactive",
                    message="Personal API key owner must be active",
                    details={"owner_id": str(owner.id)},
                )

            if not owner.is_superuser:
                root_entity_id = await self._get_root_entity_id(session, entity_id)
                if owner.root_entity_id is None or owner.root_entity_id != root_entity_id:
                    raise self._policy_error(
                        "root_entity_mismatch",
                        message="Personal API keys must stay within the owner's root entity",
                        details={
                            "owner_id": str(owner.id),
                            "owner_root_entity_id": (str(owner.root_entity_id) if owner.root_entity_id else None),
                            "entity_root_entity_id": str(root_entity_id),
                        },
                    )
            return

        if key_kind != APIKeyKind.SYSTEM_INTEGRATION:
            raise self._policy_error(
                "unsupported_key_kind",
                message="Unsupported API key kind",
                details={"key_kind": key_kind.value},
            )

        if owner is not None:
            raise self._policy_error(
                "invalid_owner_context",
                message="System integration API keys cannot be owned by human users",
            )
        if integration_principal is None:
            raise self._policy_error(
                "integration_principal_required",
                message="System integration API keys require an integration principal owner",
            )
        if actor_user_id is None:
            raise self._policy_error(
                "actor_required",
                message="System integration API keys require an acting user",
            )

        actor = await self._load_actor_user(session, actor_user_id)
        if not actor.can_authenticate():
            raise self._policy_error(
                "actor_inactive",
                message="Only active users may manage system integration credentials",
                details={"actor_user_id": str(actor_user_id)},
            )
        if not integration_principal.is_active():
            raise self._policy_error(
                "integration_principal_inactive",
                message="Integration principal must be active",
                details={"integration_principal_id": str(integration_principal.id)},
            )

        if integration_principal.scope_kind == IntegrationPrincipalScopeKind.PLATFORM_GLOBAL:
            if entity_id is not None:
                raise self._policy_error(
                    "entity_anchor_unsupported",
                    message="Platform-global integration principals cannot issue entity-anchored keys",
                    details={"entity_id": str(entity_id)},
                )
            if inherit_from_tree:
                raise self._policy_error(
                    "inherit_from_tree_disallowed",
                    message="Platform-global integration principals cannot inherit tree scope",
                )
            if not actor.is_superuser and self.config.enable_entity_hierarchy:
                raise self._policy_error(
                    "superuser_required",
                    message="Platform-global integration principals require a superuser actor",
                    details={"actor_user_id": str(actor_user_id)},
                )
            return

        if not self.config.enable_entity_hierarchy:
            raise self._policy_error(
                "entity_scoped_system_key_unsupported",
                message="Entity-scoped system integration API keys require EnterpriseRBAC",
                details={
                    "key_kind": key_kind.value,
                    "integration_principal_id": str(integration_principal.id),
                },
            )

        if integration_principal.anchor_entity_id is None:
            raise self._policy_error(
                "entity_anchor_required",
                message="Entity-scoped integration principals require an anchor entity",
                details={"integration_principal_id": str(integration_principal.id)},
            )
        if entity_id != integration_principal.anchor_entity_id:
            raise self._policy_error(
                "entity_anchor_mismatch",
                message="System integration API keys must use the principal's anchor entity",
                details={
                    "integration_principal_id": str(integration_principal.id),
                    "entity_id": str(entity_id) if entity_id else None,
                    "expected_entity_id": str(integration_principal.anchor_entity_id),
                },
            )
        if inherit_from_tree != integration_principal.inherit_from_tree:
            raise self._policy_error(
                "inherit_from_tree_mismatch",
                message="System integration API keys must mirror the principal tree-scope setting",
                details={"integration_principal_id": str(integration_principal.id)},
            )

        entity = await session.get(Entity, integration_principal.anchor_entity_id)
        if entity is None:
            raise self._policy_error(
                "entity_anchor_not_found",
                message="Entity anchor not found",
                details={"entity_id": str(integration_principal.anchor_entity_id)},
            )
        if not entity.is_active():
            raise self._policy_error(
                "entity_anchor_inactive",
                message="Entity anchor must be active",
                details={"entity_id": str(integration_principal.anchor_entity_id)},
            )

        if not actor.is_superuser:
            root_entity_id = await self._get_root_entity_id(session, integration_principal.anchor_entity_id)
            if actor.root_entity_id is None or actor.root_entity_id != root_entity_id:
                raise self._policy_error(
                    "root_entity_mismatch",
                    message="Entity-scoped integration principals must stay within the actor's root entity",
                    details={
                        "actor_user_id": str(actor.id),
                        "actor_root_entity_id": str(actor.root_entity_id) if actor.root_entity_id else None,
                        "entity_root_entity_id": str(root_entity_id),
                    },
                )

    def _validate_scope_allowlist(self, scope: str, key_kind: APIKeyKind) -> None:
        if "*" in scope:
            raise self._policy_error(
                "wildcard_scope_disallowed",
                message="API keys do not allow wildcard scopes in this implementation slice",
                details={"scope": scope},
            )

        if key_kind == APIKeyKind.PERSONAL and not self._is_personal_scope_allowed(scope):
            raise self._policy_error(
                "scope_not_allowed_for_personal",
                message="Scope is not allowed for personal API keys in v1",
                details={
                    "scope": scope,
                    "allowed_action_prefixes": self.get_personal_allowed_action_prefixes(),
                    "excluded_resources": sorted(self._personal_excluded_resources),
                },
            )
        if key_kind == APIKeyKind.SYSTEM_INTEGRATION and not self._is_system_scope_allowed(scope):
            raise self._policy_error(
                "scope_not_allowed_for_system_integration",
                message="Scope is not allowed for system integration API keys in this slice",
                details={
                    "scope": scope,
                    "allowed_action_prefixes": self.get_system_allowed_action_prefixes(),
                    "excluded_resources": sorted(self._system_excluded_resources),
                },
            )

    async def _calculate_user_grantable_scopes(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        key_kind: APIKeyKind,
        entity_id: Optional[UUID],
        candidate_permission_names: Optional[Iterable[str]] = None,
        user: Optional[User] = None,
    ) -> List[str]:
        permission_names = list(
            candidate_permission_names
            if candidate_permission_names is not None
            else await self._list_active_permission_names(session)
        )
        allowed_names = self._filter_allowed_permission_names(permission_names, key_kind)
        if not allowed_names:
            return []

        if self.permission_service is None:
            return sorted(allowed_names)

        if not getattr(self.permission_service.config, "enable_abac", False):
            return sorted(
                await self.permission_service.get_effective_permission_names(
                    session,
                    user_id=user_id,
                    entity_id=entity_id,
                    candidate_permission_names=allowed_names,
                    user=user,
                )
            )

        grantable: list[str] = []
        for permission_name in allowed_names:
            if await self.permission_service.check_permission(
                session,
                user_id=user_id,
                permission=permission_name,
                entity_id=entity_id,
                user=user,
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
        policy_reason: str,
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
            raise self._policy_error(
                policy_reason,
                message=error_message,
                details=details,
            )

    async def _list_active_permission_names(
        self,
        session: AsyncSession,
    ) -> List[str]:
        stmt = (
            select(cast(Any, Permission.name))
            .where(cast(Any, Permission.status) == DefinitionStatus.ACTIVE)
            .order_by(cast(Any, Permission.name).asc())
        )
        result = await session.execute(stmt)
        return [row[0] for row in result.all()]

    def _filter_allowed_permission_names(
        self,
        permission_names: Iterable[str],
        key_kind: APIKeyKind,
    ) -> List[str]:
        return [
            permission_name
            for permission_name in permission_names
            if self._is_scope_allowed_for_key_kind(permission_name, key_kind)
        ]

    def _policy_error(
        self,
        reason: str,
        *,
        message: str,
        details: Optional[dict[str, Any]] = None,
    ) -> InvalidInputError:
        payload = dict(details or {})
        payload.setdefault("policy_reason", reason)
        return InvalidInputError(message=message, details=payload)

    @staticmethod
    def _get_policy_reason(exc: InvalidInputError) -> str:
        reason = exc.details.get("policy_reason")
        return str(reason) if reason else "invalid_input"

    def _log_policy_decision(
        self,
        *,
        surface: str,
        outcome: str,
        reason: str,
        key_kind: Optional[APIKeyKind],
        **extra: Any,
    ) -> None:
        if self.observability is None:
            return
        normalized_key_kind = None
        if key_kind is not None:
            normalized_key_kind = key_kind.value if hasattr(key_kind, "value") else str(key_kind)
        self.observability.log_api_key_policy_decision(
            surface=surface,
            outcome=outcome,
            reason=reason,
            key_kind=normalized_key_kind,
            **extra,
        )

    def _is_scope_allowed_for_key_kind(
        self,
        scope: str,
        key_kind: APIKeyKind,
    ) -> bool:
        if key_kind == APIKeyKind.PERSONAL:
            return self._is_personal_scope_allowed(scope)
        if key_kind == APIKeyKind.SYSTEM_INTEGRATION:
            return self._is_system_scope_allowed(scope)
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

    def _is_system_scope_allowed(self, scope: str) -> bool:
        from outlabs_auth.services.permission import PermissionService

        resource, action, _ = PermissionService._parse_permission_name(scope)
        normalized_resource = resource.lower()
        normalized_action = action.lower()
        if normalized_resource in self._system_excluded_resources:
            return False
        return any(
            normalized_action == prefix or normalized_action.startswith(f"{prefix}_")
            for prefix in self._system_allowed_action_prefixes
        )

    @staticmethod
    def _resolve_owner_id(
        *,
        owner: Optional[User],
        integration_principal: Optional[IntegrationPrincipal],
    ) -> Optional[UUID]:
        if integration_principal is not None:
            return integration_principal.id
        if owner is not None:
            return owner.id
        return None

    @staticmethod
    def _resolve_owner_type(
        *,
        owner: Optional[User],
        integration_principal: Optional[IntegrationPrincipal],
    ) -> Optional[str]:
        if integration_principal is not None:
            return "integration_principal"
        if owner is not None:
            return "user"
        return None

    async def _load_actor_user(
        self,
        session: AsyncSession,
        actor_user_id: UUID,
    ) -> User:
        actor = await session.get(User, actor_user_id)
        if actor is None:
            raise self._policy_error(
                "actor_not_found",
                message="Actor user not found",
                details={"actor_user_id": str(actor_user_id)},
            )
        return actor

    async def _get_root_entity_id(
        self,
        session: AsyncSession,
        entity_id: UUID,
    ) -> UUID:
        stmt = (
            select(cast(Any, EntityClosure.ancestor_id))
            .where(cast(Any, EntityClosure.descendant_id) == entity_id)
            .order_by(cast(Any, EntityClosure.depth).desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        row = result.first()
        return row[0] if row else entity_id
