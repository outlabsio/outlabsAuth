"""
API key policy helpers.

Centralizes creation/update/runtime validation so EnterpriseRBAC can tighten
personal keys without duplicating rules across routers and auth backends.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import TYPE_CHECKING, Any, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import InvalidInputError
from outlabs_auth.models.sql.api_key import APIKey, APIKeyScope
from outlabs_auth.models.sql.closure import EntityClosure
from outlabs_auth.models.sql.entity import Entity
from outlabs_auth.models.sql.enums import APIKeyKind, APIKeyStatus, DefinitionStatus
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
        try:
            await self._validate_key_policy(
                session,
                actor_user_id=actor_user_id,
                owner=owner,
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
                owner_id=str(owner.id),
                entity_id=str(entity_id) if entity_id else None,
            )
            raise

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
        try:
            await self._validate_key_policy(
                session,
                actor_user_id=actor_user_id,
                owner=owner,
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
                owner_id=str(owner.id),
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
        owner = await session.get(User, api_key.owner_id)
        if owner is None:
            logger.warning("API key %s rejected because owner is missing", api_key.prefix)
            self._log_policy_decision(
                surface="runtime_use",
                outcome="denied",
                reason="owner_missing",
                key_kind=api_key.key_kind,
                prefix=api_key.prefix,
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
                owner_id=str(api_key.owner_id),
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
                owner_id=str(api_key.owner_id),
                entity_id=str(api_key.entity_id),
            )
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

    async def evaluate_effectiveness(
        self,
        session: AsyncSession,
        *,
        api_key: APIKey,
        scopes: Optional[List[str]] = None,
    ) -> APIKeyEffectivenessResult:
        """Return derived runtime effectiveness and the reasons when a key is ineffective."""
        reasons: list[str] = []

        if api_key.status == APIKeyStatus.SUSPENDED:
            reasons.append("key_suspended")
        elif api_key.status == APIKeyStatus.REVOKED:
            reasons.append("key_revoked")
        elif api_key.status == APIKeyStatus.EXPIRED:
            reasons.append("key_expired")
        elif api_key.expires_at and datetime.now(timezone.utc) > api_key.expires_at:
            reasons.append("key_expired")

        owner = await session.get(User, api_key.owner_id)
        if owner is None:
            reasons.append("owner_missing")
        elif not owner.can_authenticate():
            reasons.append("owner_inactive")

        if api_key.entity_id is not None:
            entity = await session.get(Entity, api_key.entity_id)
            if entity is None:
                reasons.append("anchor_missing")
            elif not entity.is_active():
                reasons.append("anchor_inactive")

        if reasons:
            return APIKeyEffectivenessResult(
                is_currently_effective=False,
                ineffective_reasons=reasons,
            )

        if not self.config.enable_entity_hierarchy:
            return APIKeyEffectivenessResult(
                is_currently_effective=True,
                ineffective_reasons=[],
            )

        stored_scopes = scopes
        if stored_scopes is None:
            stmt = select(APIKeyScope.scope).where(APIKeyScope.api_key_id == api_key.id)
            result = await session.execute(stmt)
            stored_scopes = [row[0] for row in result.all()]

        try:
            owner_grantable_scopes = await self.calculate_owner_grantable_scopes(
                session,
                owner=owner,
                key_kind=api_key.key_kind,
                entity_id=api_key.entity_id,
                inherit_from_tree=api_key.inherit_from_tree,
            )
        except InvalidInputError:
            reasons.append("policy_invalid")
            return APIKeyEffectivenessResult(
                is_currently_effective=False,
                ineffective_reasons=reasons,
            )

        from outlabs_auth.services.api_key import APIKeyService

        has_effective_scope = any(
            APIKeyService.scopes_allow_permission(stored_scopes, permission_name)
            for permission_name in owner_grantable_scopes
        )
        if not has_effective_scope:
            reasons.append("no_effective_scopes")

        return APIKeyEffectivenessResult(
            is_currently_effective=not reasons,
            ineffective_reasons=reasons,
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
        try:
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
        except InvalidInputError as exc:
            self._log_policy_decision(
                surface="grantable_scopes",
                outcome="denied",
                reason=self._get_policy_reason(exc),
                key_kind=key_kind,
                actor_user_id=str(actor_user_id),
                owner_id=str(owner.id),
                entity_id=str(entity_id) if entity_id else None,
            )
            raise

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

        if not self.config.enable_entity_hierarchy:
            return

        if not scopes:
            raise self._policy_error(
                "explicit_scopes_required",
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
        owner: User,
        key_kind: APIKeyKind,
        entity_id: Optional[UUID],
        inherit_from_tree: bool,
        allow_cross_owner_for_calculation: bool = False,
    ) -> None:
        if key_kind != APIKeyKind.PERSONAL:
            raise self._policy_error(
                "unsupported_key_kind",
                message="Only personal API keys are supported in v1",
                details={"key_kind": key_kind.value},
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
            raise self._policy_error(
                "entity_anchor_required",
                message="Personal API keys require an entity anchor in EnterpriseRBAC",
            )

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

    def _validate_scope_allowlist(self, scope: str, key_kind: APIKeyKind) -> None:
        if "*" in scope:
            raise self._policy_error(
                "wildcard_scope_disallowed",
                message="Personal API keys do not allow wildcard scopes in v1",
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
            select(Permission.name).where(Permission.status == DefinitionStatus.ACTIVE).order_by(Permission.name.asc())
        )
        result = await session.execute(stmt)
        return [row[0] for row in result.all()]

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
