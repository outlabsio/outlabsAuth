"""Opt-in human staff facade. Existing IAM/ordinary authorization stays separate.

Contexts are issued only by this facade's configured authentication dependencies
and bound to one session/transaction. They are not serializable authority. SQL
lists retain each grant's action/selector relationship. Hosts must derive entity
ownership from their stored resource, then authorize in the write transaction.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, cast
from uuid import UUID

from fastapi import HTTPException, Request
from sqlalchemy import Text, and_, func, literal, or_, select, union_all
from sqlalchemy import cast as sql_cast
from sqlalchemy.dialects.postgresql import array
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from outlabs_auth.core.session_security import proof_is_current
from outlabs_auth.models.sql.administrative_grant import (
    AdministrativeAdmission,
    AdministrativeGrantRecord,
    AdministrativeGroup,
    AdministrativeTemplateRevision,
)
from outlabs_auth.models.sql.api_key import APIKey, APIKeyScope
from outlabs_auth.models.sql.entity_membership import EntityMembership, EntityMembershipRole
from outlabs_auth.models.sql.entity import Entity
from outlabs_auth.models.sql.closure import EntityClosure
from outlabs_auth.models.sql.enums import APIKeyKind, APIKeyStatus, EntityClass, UserStatus
from outlabs_auth.models.sql.permission import Permission, PermissionCondition
from outlabs_auth.models.sql.role import Role
from outlabs_auth.models.sql.user import User
from outlabs_auth.models.sql.user_role_membership import UserRoleMembership
from outlabs_auth.services.administrative_grants import AdministrativeGrantService, _hash
from outlabs_auth.services.administrative_scope import AdministrativeDecision, AdministrativeDecisionReason


@dataclass(frozen=True)
class StaffContext:
    user_id: UUID
    source: str
    key_id: UUID | None
    _claims: dict[str, Any] = field(repr=False)
    _seal: object = field(repr=False)
    _session: AsyncSession = field(repr=False)
    _transaction: object = field(repr=False)


@dataclass(frozen=True)
class StaffEntityView:
    id: UUID
    customer_root_id: UUID
    display_name: str


@dataclass(frozen=True)
class StaffEntityPage:
    items: tuple[StaffEntityView, ...]
    total: int
    next_cursor: str | None


@dataclass(frozen=True)
class StaffKeyView:
    id: UUID
    name: str
    status: APIKeyStatus
    entity_id: UUID | None
    expires_at: datetime | None


@dataclass(frozen=True)
class StaffKeyPage:
    items: tuple[StaffKeyView, ...]
    total: int
    next_after: UUID | None


def _deny(
    reason: AdministrativeDecisionReason = AdministrativeDecisionReason.UNTRUSTED_ACTOR,
) -> AdministrativeDecision:
    return AdministrativeDecision(False, reason)


def _active_entity(row: Any, now: Any) -> Any:
    return and_(
        row.entity_class == EntityClass.STRUCTURAL,
        row.status == "active",
        or_(row.valid_from.is_(None), row.valid_from <= now),
        or_(row.valid_until.is_(None), row.valid_until > now),
    )


class AdministrativeAuthorization:
    """Explicit opt-in for qualified host operations, never a global-scope union.

    First policy supports exact unconditional actions, 64 active actor grants,
    bounded tree depth and pages up to 100. Unanchored personal keys require an
    explicit host disposition. Existing mounted IAM routes are not broadened.
    C5 root-column/indexed scale admission remains a separate release gate.
    """

    def __init__(
        self, auth: Any, grants: AdministrativeGrantService, *, allow_unanchored_personal_keys: bool = False
    ) -> None:
        self.auth = auth
        self.grants = grants
        self.allow_unanchored_personal_keys = allow_unanchored_personal_keys
        self._seal = object()
        self._cursor_secret = secrets.token_bytes(32)

    async def authenticate(self, session: AsyncSession, request: Request) -> StaffContext:
        # Refuse ambiguous credential transport rather than falling back from a
        # restricted/bad key to a different, wider credential on the same call.
        if request.headers.get("X-API-Key") and request.headers.get("Authorization"):
            raise HTTPException(401, "Ambiguous staff credentials")
        result = await self.auth.deps._authenticate_request(
            request, session, active=True, verified=False, optional=False
        )
        if not result or result.get("source") not in {"jwt", "api_key"} or result.get("integration_principal_id"):
            raise HTTPException(403, "Human staff credentials required")
        try:
            user_id = UUID(str(result["user_id"]))
            key = result.get("api_key")
            key_id = key.id if result["source"] == "api_key" and key is not None else None
            if result["source"] == "api_key" and key_id is None:
                raise ValueError("Missing verified personal key")
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(401, "Invalid staff credentials") from exc
        bind = session.bind
        engine = bind.engine if isinstance(bind, AsyncConnection) else bind
        if engine is not self.auth._engine:
            raise HTTPException(403, "Staff context belongs to another installation")
        context = StaffContext(
            user_id,
            result["source"],
            key_id,
            dict(result.get("metadata") or {}),
            self._seal,
            session,
            session.sync_session.get_transaction(),
        )
        if await self._actor(session, context) is None:
            raise HTTPException(403, "Staff control-domain admission refused")
        return context

    async def _actor(self, session: AsyncSession, context: StaffContext) -> User | None:
        if (
            not isinstance(context, StaffContext)
            or context._seal is not self._seal
            or context._session is not session
            or context._transaction is not session.sync_session.get_transaction()
            or context._transaction is None
        ):
            return None
        user = (
            await session.execute(
                select(User).where(cast(Any, User.id) == context.user_id).execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        if user is None or user.status != UserStatus.ACTIVE or user.root_entity_id != self.grants.trusted_root:
            return None
        if context.source == "jwt":
            expires = context._claims.get("exp")
            if (
                not proof_is_current(context._claims, user)
                or not isinstance(expires, (int, float))
                or isinstance(expires, bool)
                or not expires > datetime.now(timezone.utc).timestamp()
            ):
                return None
        return user

    async def _key(self, session: AsyncSession, context: StaffContext, *, lock: bool = False) -> APIKey | None:
        statement = (
            select(APIKey).where(cast(Any, APIKey.id) == context.key_id).execution_options(populate_existing=True)
        )
        if lock:
            statement = statement.with_for_update(read=True)
        key = (await session.execute(statement)).scalar_one_or_none()
        now = datetime.now(timezone.utc)
        if (
            key is None
            or key.owner_id != context.user_id
            or key.integration_principal_id is not None
            or key.key_kind != APIKeyKind.PERSONAL
            or key.status != APIKeyStatus.ACTIVE
            or (key.expires_at is not None and now >= key.expires_at)
            or (key.entity_id is None and not self.allow_unanchored_personal_keys)
        ):
            return None
        return key

    async def authorize(
        self,
        session: AsyncSession,
        context: StaffContext,
        *,
        action: str,
        entity_id: UUID,
        account_root_required: bool = False,
        protected_write: bool = False,
        customer_catalog: bool = False,
    ) -> AdministrativeDecision:
        if await self._actor(session, context) is None:
            return _deny()
        key = None
        if context.source == "api_key":
            key = await self._key(session, context, lock=protected_write)
            if key is None:
                return _deny(AdministrativeDecisionReason.OUTSIDE_KEY_BOUNDARY)
            statement = select(APIKeyScope).where(cast(Any, APIKeyScope.api_key_id) == key.id)
            # The parent key fence covers every child writer, including an
            # empty-set INSERT. Avoid child lock upgrades/inverted lock order.
            scopes = [row.scope for row in (await session.execute(statement)).scalars()]
            if not self.auth.api_key_service.scopes_allow_permission(scopes, action):
                return _deny(AdministrativeDecisionReason.OUTSIDE_KEY_BOUNDARY)
            try:
                path = await self.grants._path(session, entity_id, datetime.now(timezone.utc))
            except Exception as exc:
                from outlabs_auth.core.exceptions import InvalidInputError

                if not isinstance(exc, InvalidInputError):
                    raise
                return _deny(AdministrativeDecisionReason.INVALID_TARGET)
            targets = {entity_id, path[-1].id} if account_root_required else {entity_id}
            if key.entity_id is not None:
                for target in targets:
                    target_path = await self.grants._path(
                        session, target, datetime.now(timezone.utc), lock=protected_write
                    )
                    if target != key.entity_id and (
                        not key.inherit_from_tree or key.entity_id not in {e.id for e in target_path}
                    ):
                        return _deny(AdministrativeDecisionReason.OUTSIDE_KEY_BOUNDARY)
        decision = await self.grants.check_target(
            session,
            user_id=context.user_id,
            action=action,
            entity_id=entity_id,
            customer_catalog=customer_catalog,
            account_root_required=account_root_required,
        )
        if not decision.allowed or not protected_write:
            return decision
        # Only the qualifying grant is locked. A concurrent withdrawal that won
        # before lock acquisition must deny; it cannot silently switch grants.
        decision = await self.grants.check_target(
            session,
            user_id=context.user_id,
            action=action,
            entity_id=entity_id,
            customer_catalog=customer_catalog,
            account_root_required=account_root_required,
            protected_write=True,
            qualifying_grant_id=decision.grant_id,
        )
        if not decision.allowed:
            return decision
        # Waiting on a policy/target lock cannot preserve an earlier clock/window.
        if await self._actor(session, context) is None:
            return _deny()
        if context.source == "api_key" and await self._key(session, context) is None:
            return _deny(AdministrativeDecisionReason.OUTSIDE_KEY_BOUNDARY)
        return await self.grants.check_target(
            session,
            user_id=context.user_id,
            action=action,
            entity_id=entity_id,
            customer_catalog=customer_catalog,
            account_root_required=account_root_required,
            qualifying_grant_id=decision.grant_id,
        )

    async def create_personal_key(
        self,
        session: AsyncSession,
        context: StaffContext,
        *,
        name: str,
        entity_id: UUID,
        scopes: list[str],
        inherit_from_tree: bool = False,
        expires_in_days: int = 7,
    ) -> tuple[str, APIKey]:
        """JWT-authenticated self-service; mint only exact currently held actions.

        Opaque approval is transaction/owner/anchor/action bound. Ordinary SDK
        and mounted key routes retain their original tenant-root policy.
        """
        from outlabs_auth.services.api_key_policy import _StaffKeyApproval

        actor = await self._actor(session, context)
        if (
            actor is None
            or context.source != "jwt"
            or not scopes
            or len(set(scopes)) > 64
            or not 1 <= expires_in_days <= 30
        ):
            raise HTTPException(403, "Staff key issuance requires current human JWT and bounded exact scopes")
        if any("*" in scope for scope in scopes):
            raise HTTPException(403, "Staff key scopes must be exact actions")
        for scope in sorted(set(scopes)):
            decision = await self.authorize(session, context, action=scope, entity_id=entity_id, protected_write=True)
            if not decision.allowed:
                raise HTTPException(403, "Staff key scope is outside current administrative authority")
        policy = self.auth.api_key_service.policy_service
        if policy is None:
            raise HTTPException(503, "Staff key policy is unavailable")
        approval = _StaffKeyApproval(
            policy._staff_approval_issuer,
            session,
            session.sync_session.get_transaction(),
            actor.id,
            int(actor.session_security_epoch or 0),
            entity_id,
            tuple(sorted(set(scopes))),
            inherit_from_tree,
        )
        result = await self.auth.api_key_service.create_api_key(
            session,
            owner_id=actor.id,
            actor_user_id=actor.id,
            name=name,
            entity_id=entity_id,
            scopes=sorted(set(scopes)),
            inherit_from_tree=inherit_from_tree,
            expires_in_days=expires_in_days,
            _staff_approval=approval,
            event_source="staff_authorization.create_personal_key",
        )
        return cast(tuple[str, APIKey], result)

    async def _owned_personal_key(
        self, session: AsyncSession, context: StaffContext, key_id: UUID, *, active: bool
    ) -> APIKey:
        if context.source != "jwt" or await self._actor(session, context) is None:
            raise HTTPException(403, "Key management requires a current human JWT")
        key = (
            await session.execute(
                select(APIKey)
                .where(
                    cast(Any, APIKey.id) == key_id,
                    cast(Any, APIKey.owner_id) == context.user_id,
                    cast(Any, APIKey.key_kind) == APIKeyKind.PERSONAL,
                    cast(Any, APIKey.integration_principal_id).is_(None),
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        # Recheck after waiting on the key. Lock ownership, not the login row.
        if key is None or await self._actor(session, context) is None:
            raise HTTPException(403, "Personal key ownership refused")
        if active and (
            key.status != APIKeyStatus.ACTIVE
            or key.entity_id is None
            or key.expires_at is None
            or key.expires_at <= datetime.now(timezone.utc)
        ):
            raise HTTPException(403, "Only active anchored expiring keys can be updated or rotated")
        return key

    async def _key_approval(self, session: AsyncSession, context: StaffContext, key: APIKey, scopes: list[str]) -> Any:
        from outlabs_auth.services.api_key_policy import _StaffKeyApproval

        if not scopes or len(set(scopes)) > 64 or any("*" in scope for scope in scopes):
            raise HTTPException(403, "Staff key scopes must be bounded exact actions")
        if key.entity_id is None:
            raise HTTPException(403, "Staff key anchor is required")
        for scope in sorted(set(scopes)):
            if not (
                await self.authorize(session, context, action=scope, entity_id=key.entity_id, protected_write=True)
            ).allowed:
                raise HTTPException(403, "Staff key scope is outside current administrative authority")
        actor = await self._actor(session, context)
        policy = self.auth.api_key_service.policy_service
        if actor is None or policy is None or key.expires_at is None or key.expires_at <= datetime.now(timezone.utc):
            raise HTTPException(403, "Staff key policy admission refused")
        return _StaffKeyApproval(
            policy._staff_approval_issuer,
            session,
            session.sync_session.get_transaction(),
            actor.id,
            int(actor.session_security_epoch or 0),
            key.entity_id,
            tuple(sorted(set(scopes))),
            key.inherit_from_tree,
            key.id,
        )

    async def update_personal_key(
        self,
        session: AsyncSession,
        context: StaffContext,
        *,
        key_id: UUID,
        scopes: list[str],
        expires_at: datetime | None = None,
    ) -> APIKey:
        """Narrow an owned key; anchor, inheritance, owner and status cannot change."""
        key = await self._owned_personal_key(session, context, key_id, active=True)
        previous = await self.auth.api_key_service.get_api_key_scopes(session, key_id)
        if not set(scopes).issubset(previous):
            raise HTTPException(403, "Staff key updates cannot expand scopes")
        if expires_at is not None and (
            expires_at.tzinfo is None
            or key.expires_at is None
            or not datetime.now(timezone.utc) < expires_at <= key.expires_at
        ):
            raise HTTPException(403, "Staff key updates can only shorten a future expiry")
        approval = await self._key_approval(session, context, key, scopes)
        if expires_at is not None and expires_at <= datetime.now(timezone.utc):
            raise HTTPException(403, "Staff key deadline passed while waiting on authority")
        updates: dict[str, Any] = {"scopes": sorted(set(scopes))}
        if expires_at is not None:
            updates["expires_at"] = expires_at
        result = await self.auth.api_key_service.update_api_key(
            session,
            key_id,
            actor_user_id=context.user_id,
            event_source="staff_authorization.update_personal_key",
            _staff_approval=approval,
            **updates,
        )
        return cast(APIKey, result)

    async def rotate_personal_key(
        self, session: AsyncSession, context: StaffContext, *, key_id: UUID
    ) -> tuple[str, APIKey]:
        """Retain exact restrictions/deadline; issue and revoke in one transaction."""
        key = await self._owned_personal_key(session, context, key_id, active=True)
        scopes = await self.auth.api_key_service.get_api_key_scopes(session, key_id)
        approval = await self._key_approval(session, context, key, scopes)
        result = await self.auth.api_key_service.rotate_api_key(
            session,
            key_id,
            actor_user_id=context.user_id,
            event_source="staff_authorization.rotate_personal_key",
            _staff_approval=approval,
        )
        return cast(tuple[str, APIKey], result)

    async def revoke_personal_key(self, session: AsyncSession, context: StaffContext, *, key_id: UUID) -> bool:
        """Self-revocation remains available after administrative grants end."""
        await self._owned_personal_key(session, context, key_id, active=False)
        return bool(
            await self.auth.api_key_service.revoke_api_key(
                session, key_id, actor_user_id=context.user_id, event_source="staff_authorization.revoke_personal_key"
            )
        )

    async def personal_key_page(
        self, session: AsyncSession, context: StaffContext, *, limit: int = 50, after: UUID | None = None
    ) -> StaffKeyPage:
        """Own credential metadata only; SQL filters before count and keyset limit."""
        actor = await self._actor(session, context)
        if context.source != "jwt" or actor is None:
            raise HTTPException(403, "Key inventory requires a current human JWT")
        if not 1 <= limit <= 100:
            raise HTTPException(422, "Staff page size must be 1..100")
        active_actor = (
            select(cast(Any, User.id))
            .where(
                cast(Any, User.id) == actor.id,
                cast(Any, User.status) == UserStatus.ACTIVE,
                cast(Any, User.root_entity_id) == self.grants.trusted_root,
                func.coalesce(cast(Any, User.session_security_epoch), 0) == int(actor.session_security_epoch or 0),
            )
            .exists()
        )
        k = cast(Any, APIKey).__table__
        allowed = (
            select(k.c.id, k.c.name, k.c.status, k.c.entity_id, k.c.expires_at)
            .where(
                k.c.owner_id == actor.id,
                k.c.key_kind == APIKeyKind.PERSONAL,
                k.c.integration_principal_id.is_(None),
                active_actor,
            )
            .cte("staff_owned_keys")
        )
        count = select(func.count().label("total")).select_from(allowed).cte("staff_key_count")
        page = (
            select(allowed)
            .where(allowed.c.id > after if after else literal(True))
            .order_by(allowed.c.id)
            .limit(limit + 1)
            .cte("staff_key_page")
        )
        rows = (
            await session.execute(
                select(page, count.c.total).select_from(count.outerjoin(page, literal(True))).order_by(page.c.id)
            )
        ).all()
        views = [StaffKeyView(r.id, r.name, r.status, r.entity_id, r.expires_at) for r in rows if r.id is not None]
        return StaffKeyPage(
            tuple(views[:limit]), int(rows[0].total), views[limit - 1].id if len(views) > limit else None
        )

    async def authorize_account(
        self, session: AsyncSession, context: StaffContext, *, action: str, user_id: UUID, protected_write: bool = False
    ) -> AdministrativeDecision:
        if await self._actor(session, context) is None:
            return _deny()
        if user_id == context.user_id:
            return _deny(AdministrativeDecisionReason.INVALID_TARGET)
        statement = (
            select(User)
            .where(cast(Any, User.id) == user_id, cast(Any, User.root_entity_id) != self.grants.trusted_root)
            .execution_options(populate_existing=True)
        )
        if protected_write:
            statement = statement.with_for_update()
        target = (await session.execute(statement)).scalar_one_or_none()
        if target is None or target.root_entity_id is None or target.is_superuser or target.platform_protected:
            return _deny(AdministrativeDecisionReason.INVALID_TARGET)
        if not await self._unprotected_subject(session, target, lock=protected_write):
            return _deny(AdministrativeDecisionReason.INVALID_TARGET)
        return await self.authorize(
            session,
            context,
            action=action,
            entity_id=target.root_entity_id,
            account_root_required=True,
            protected_write=protected_write,
        )

    async def _unprotected_subject(self, session: AsyncSession, target: User, *, lock: bool) -> bool:
        """Reject retained platform classification and every assigned global role."""
        if (
            target.root_entity_id is None
            or target.root_entity_id == self.grants.trusted_root
            or target.is_superuser
            or target.platform_protected
        ):
            return False
        direct = select(cast(Any, UserRoleMembership.role_id)).where(cast(Any, UserRoleMembership.user_id) == target.id)
        member = (
            select(cast(Any, EntityMembershipRole.role_id))
            .join(EntityMembership, cast(Any, EntityMembership.id) == cast(Any, EntityMembershipRole.membership_id))
            .where(cast(Any, EntityMembership.user_id) == target.id)
        )
        statement = (
            select(Role)
            .where(cast(Any, Role.id).in_(union_all(direct, member)))
            .execution_options(populate_existing=True)
        )
        if lock:
            statement = statement.with_for_update(read=True, of=Role)
        roles = (await session.execute(statement)).scalars().all()
        if any(r.is_global and r.root_entity_id is None and r.scope_entity_id is None for r in roles):
            return False
        administrative = (
            select(cast(Any, AdministrativeGrantRecord.id))
            .where(cast(Any, AdministrativeGrantRecord.user_id) == target.id)
            .exists()
        )
        return not (await session.execute(select(administrative))).scalar()

    def _customer_filter(self, root_id: UUID) -> Any:
        direct = (
            select(cast(Any, UserRoleMembership.role_id))
            .where(cast(Any, UserRoleMembership.user_id) == User.id)
            .correlate(User)
        )
        member = (
            select(cast(Any, EntityMembershipRole.role_id))
            .join(EntityMembership, cast(Any, EntityMembership.id) == EntityMembershipRole.membership_id)
            .where(cast(Any, EntityMembership.user_id) == User.id)
            .correlate(User)
        )
        protected = (
            select(cast(Any, Role.id))
            .where(
                cast(Any, Role.id).in_(union_all(direct, member)),
                cast(Any, Role.is_global).is_(True),
                cast(Any, Role.root_entity_id).is_(None),
                cast(Any, Role.scope_entity_id).is_(None),
            )
            .exists()
        )
        staff = (
            select(cast(Any, AdministrativeGrantRecord.id))
            .where(cast(Any, AdministrativeGrantRecord.user_id) == User.id)
            .exists()
        )
        return and_(
            cast(Any, User.root_entity_id) == root_id,
            cast(Any, User.is_superuser).is_(False),
            cast(Any, User.platform_protected).is_not(True),
            ~protected,
            ~staff,
        )

    async def customer_users(
        self,
        session: AsyncSession,
        context: StaffContext,
        *,
        customer_root_id: UUID,
        limit: int = 50,
        after: UUID | None = None,
    ) -> tuple[list[User], int]:
        path = await self.grants._path(session, customer_root_id, datetime.now(timezone.utc))
        if (
            len(path) != 1
            or customer_root_id == self.grants.trusted_root
            or not 1 <= limit <= 100
            or not (
                await self.authorize(
                    session, context, action="user:read", entity_id=customer_root_id, account_root_required=True
                )
            ).allowed
        ):
            raise HTTPException(403, "Customer account list admission refused")
        predicate = self._customer_filter(customer_root_id)
        total = int((await session.execute(select(func.count()).select_from(User).where(predicate))).scalar_one())
        statement = select(User).where(predicate).order_by(cast(Any, User.id)).limit(limit)
        if after is not None:
            statement = statement.where(cast(Any, User.id) > after)
        return list((await session.execute(statement)).scalars()), total

    async def member_admission(
        self,
        session: AsyncSession,
        context: StaffContext,
        *,
        action: str,
        entity_id: UUID,
        user_id: UUID,
        role_ids: list[UUID] | None = None,
        write: bool = False,
    ) -> User:
        """Derive customer ownership and hold subject/roles before final approval."""
        if await self._actor(session, context) is None:
            raise HTTPException(403, "Staff admission refused")
        target_stmt = select(User).where(cast(Any, User.id) == user_id).execution_options(populate_existing=True)
        if write:
            target_stmt = target_stmt.with_for_update()
        user = (await session.execute(target_stmt)).scalar_one_or_none()
        if user is None or not await self._unprotected_subject(session, user, lock=write):
            raise HTTPException(403, "Protected or absent customer subject")
        path = await self.grants._path(session, entity_id, datetime.now(timezone.utc), lock=write)
        if path[-1].id != user.root_entity_id or user.status == UserStatus.DELETED:
            raise HTTPException(403, "Membership subject belongs to another customer or is deleted")
        if role_ids is not None:
            if len(role_ids) > 64 or len(set(role_ids)) != len(role_ids):
                raise HTTPException(422, "Exact bounded role IDs required")
            stmt = (
                select(Role)
                .where(cast(Any, Role.id).in_(role_ids))
                .order_by(cast(Any, Role.id))
                .execution_options(populate_existing=True)
            )
            if write:
                stmt = stmt.with_for_update(read=True)
            roles = (await session.execute(stmt)).scalars().all()
            if len(roles) != len(role_ids) or any(
                r.is_global
                or r.root_entity_id != user.root_entity_id
                or str(getattr(r.status, "value", r.status)) != "active"
                for r in roles
            ):
                raise HTTPException(403, "Only active customer-owned roles may be assigned")
        decision = await self.authorize(session, context, action=action, entity_id=entity_id, protected_write=write)
        if not decision.allowed:
            raise HTTPException(403, "Action and target admission refused")
        return user

    async def entity_page(
        self,
        session: AsyncSession,
        context: StaffContext,
        *,
        action: str,
        limit: int = 50,
        cursor: str | None = None,
        customer_root_id: UUID | None = None,
    ) -> StaffEntityPage:
        if not 1 <= limit <= 100:
            raise HTTPException(422, "Staff page size must be 1..100")
        actor = await self._actor(session, context)
        if actor is None:
            raise HTTPException(403, "Invalid staff context")
        now = datetime.now(timezone.utc)
        await self.grants._trusted(session, now)
        eligible = (
            await session.execute(
                select(AdministrativeGrantRecord, AdministrativeTemplateRevision)
                .join(
                    AdministrativeTemplateRevision,
                    cast(Any, AdministrativeTemplateRevision.id)
                    == cast(Any, AdministrativeGrantRecord.template_revision_id),
                )
                .where(
                    cast(Any, AdministrativeGrantRecord.user_id) == actor.id,
                    cast(Any, AdministrativeGrantRecord.holder_security_epoch)
                    == int(actor.session_security_epoch or 0),
                    cast(Any, AdministrativeGrantRecord.revoked_at).is_(None),
                )
                .order_by(cast(Any, AdministrativeGrantRecord.id))
                .limit(65)
                .execution_options(populate_existing=True)
            )
        ).all()
        if len(eligible) > 64:
            raise HTTPException(403, "Administrative actor grant budget exceeded")
        refs = []
        for grant, template in eligible:
            if (
                template.active
                and template.policy_hash == _hash(template.policy)
                and template.policy.get("matching") == "exact"
            ):
                ref = next((p for p in template.policy["permissions"] if p["name"] == action), None)
                if ref:
                    refs.append((grant, template, UUID(ref["id"])))
        key = await self._key(session, context) if context.source == "api_key" else None
        if context.source == "api_key" and key is None:
            raise HTTPException(403, "Staff key refused")
        scopes = await self.auth.api_key_service.get_api_key_scopes(session, key.id) if key else []
        if key and not self.auth.api_key_service.scopes_allow_permission(scopes, action):
            refs = []
        binding = {
            "actor": str(actor.id),
            "epoch": int(actor.session_security_epoch or 0),
            "source": context.source,
            "key": str(context.key_id),
            "action": action,
            "customer": str(customer_root_id),
            "key_policy": [str(key.entity_id), key.inherit_from_tree, sorted(scopes)] if key else None,
            "grants": [(str(g.id), t.policy_hash, str(g.updated_at), str(t.updated_at)) for g, t, _ in refs],
        }
        contract = _hash(binding)
        after = None
        if cursor:
            try:
                raw, sig = cursor.split(".")
                assert hmac.compare_digest(hmac.new(self._cursor_secret, raw.encode(), hashlib.sha256).hexdigest(), sig)
                value = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
                assert value["contract"] == contract and value["expires"] > datetime.now(timezone.utc).timestamp()
                after = UUID(value["after"])
            except Exception as exc:
                raise HTTPException(422, "Staff cursor is stale or belongs to another query") from exc
        # A set-based parent traversal establishes customer boundaries, independent
        # of potentially stale closure rows. Only active structural paths qualify.
        query_now = func.statement_timestamp()
        e = cast(Any, Entity).__table__
        anchors = [grant.entity_id for grant, _, _ in refs if grant.selector_kind in {"entity", "subtree"}]
        parent_paths = (
            select(e.c.id, e.c.parent_id, literal(0).label("depth"))
            .where(e.c.id.in_(anchors), _active_entity(e.c, query_now))
            .cte("staff_selector_parents", recursive=True)
        )
        parent_paths = parent_paths.union_all(
            select(e.c.id, e.c.parent_id, parent_paths.c.depth + 1)
            .join(parent_paths, e.c.id == parent_paths.c.parent_id)
            .where(parent_paths.c.depth < self.grants.max_depth, _active_entity(e.c, query_now))
        )
        roots = [select(parent_paths.c.id).where(parent_paths.c.parent_id.is_(None))]
        a = cast(Any, AdministrativeAdmission).__table__
        for grant, _, _ in refs:
            if grant.selector_kind == "group":
                # Restrict the forest before traversing it; admission pins are
                # checked again against the live grant in the final predicate.
                roots.append(
                    select(a.c.customer_root_id).where(
                        a.c.group_id == grant.group_id,
                        a.c.closed_at.is_(None),
                        a.c.id.in_([UUID(value) for value in grant.admission_ids]),
                    )
                )
        selected_roots = union_all(*roots).cte("staff_selector_roots")
        tree = (
            select(e.c.id, e.c.id.label("root_id"), literal(0).label("depth"), array([e.c.id]).label("path"))
            .where(
                e.c.parent_id.is_(None),
                e.c.id != self.grants.trusted_root,
                e.c.id.in_(select(selected_roots.c.id)),
                _active_entity(e.c, query_now),
            )
            .cte("staff_tree", recursive=True)
        )
        child = e.alias("staff_child")
        tree = tree.union_all(
            select(child.c.id, tree.c.root_id, tree.c.depth + 1, tree.c.path + array([child.c.id]))
            .join(tree, child.c.parent_id == tree.c.id)
            .where(tree.c.depth < self.grants.max_depth, _active_entity(child.c, query_now))
        )
        clauses = []
        for grant, template, permission_id in refs:
            g = cast(Any, aliased(AdministrativeGrantRecord))
            t = cast(Any, aliased(AdministrativeTemplateRevision))
            p = cast(Any, aliased(Permission))
            selector = tree.c.id == grant.entity_id
            if grant.selector_kind == "subtree":
                selector = tree.c.path.any(grant.entity_id)
            if grant.selector_kind == "group":
                selector = (
                    select(cast(Any, AdministrativeAdmission.id))
                    .join(
                        AdministrativeGroup,
                        cast(Any, AdministrativeGroup.id) == cast(Any, AdministrativeAdmission.group_id),
                    )
                    .where(
                        cast(Any, AdministrativeAdmission.group_id) == grant.group_id,
                        cast(Any, AdministrativeGroup.active).is_(True),
                        cast(Any, AdministrativeAdmission.customer_root_id) == tree.c.root_id,
                        cast(Any, AdministrativeAdmission.closed_at).is_(None),
                        g.admission_ids.op("@>")(
                            func.jsonb_build_array(sql_cast(cast(Any, AdministrativeAdmission.id), Text))
                        ),
                    )
                    .correlate(g, tree)
                    .exists()
                )
            types = template.policy.get("entity_types", [])
            clauses.append(
                select(g.id)
                .join(t, t.id == g.template_revision_id)
                .join(p, p.id == permission_id)
                .where(
                    g.id == grant.id,
                    g.revoked_at.is_(None),
                    t.active.is_(True),
                    p.is_active.is_(True),
                    p.status == "active",
                    p.name == action,
                    ~select(cast(Any, PermissionCondition.id))
                    .where(cast(Any, PermissionCondition.permission_id) == p.id)
                    .exists(),
                    or_(g.valid_from.is_(None), g.valid_from <= query_now),
                    or_(g.valid_until.is_(None), g.valid_until > query_now),
                    selector,
                    e.c.entity_type.in_(types) if types else literal(True),
                )
                .exists()
            )
        active_actor = (
            select(cast(Any, User.id))
            .where(
                cast(Any, User.id) == actor.id,
                cast(Any, User.status) == UserStatus.ACTIVE,
                cast(Any, User.root_entity_id) == self.grants.trusted_root,
                func.coalesce(cast(Any, User.session_security_epoch), 0) == int(actor.session_security_epoch or 0),
            )
            .exists()
        )
        control = cast(Any, aliased(Entity))
        active_control = (
            select(control.id)
            .where(
                control.id == self.grants.trusted_root, control.parent_id.is_(None), _active_entity(control, query_now)
            )
            .exists()
        )
        closure = cast(Any, EntityClosure).__table__
        closure_count = (
            select(func.count())
            .select_from(closure)
            .where(closure.c.descendant_id == tree.c.id)
            .correlate(tree)
            .scalar_subquery()
        )
        bad_closure = (
            select(closure.c.ancestor_id)
            .where(
                closure.c.descendant_id == tree.c.id,
                or_(
                    ~tree.c.path.any(closure.c.ancestor_id),
                    closure.c.depth != tree.c.depth + 1 - func.array_position(tree.c.path, closure.c.ancestor_id),
                ),
            )
            .correlate(tree)
            .exists()
        )
        predicates = [
            or_(*clauses) if clauses else literal(False),
            active_actor,
            active_control,
            closure_count == tree.c.depth + 1,
            ~bad_closure,
        ]
        if customer_root_id:
            predicates.append(tree.c.root_id == customer_root_id)
        if key:
            key_scopes = [s for s in scopes if self.auth.api_key_service.scopes_allow_permission([s], action)]
            predicates.append(
                select(cast(Any, APIKey.id))
                .where(
                    cast(Any, APIKey.id) == key.id,
                    cast(Any, APIKey.status) == APIKeyStatus.ACTIVE,
                    cast(Any, APIKey.owner_id) == actor.id,
                    cast(Any, APIKey.integration_principal_id).is_(None),
                    (
                        cast(Any, APIKey.entity_id) == key.entity_id
                        if key.entity_id
                        else cast(Any, APIKey.entity_id).is_(None)
                    ),
                    cast(Any, APIKey.inherit_from_tree) == key.inherit_from_tree,
                    or_(cast(Any, APIKey.expires_at).is_(None), cast(Any, APIKey.expires_at) > query_now),
                )
                .exists()
            )
            predicates.append(
                or_(
                    ~select(cast(Any, APIKeyScope.api_key_id))
                    .where(cast(Any, APIKeyScope.api_key_id) == key.id)
                    .exists(),
                    select(cast(Any, APIKeyScope.api_key_id))
                    .where(cast(Any, APIKeyScope.api_key_id) == key.id, cast(Any, APIKeyScope.scope).in_(key_scopes))
                    .exists(),
                )
            )
            if key.entity_id:
                predicates.append(
                    tree.c.path.any(key.entity_id) if key.inherit_from_tree else tree.c.id == key.entity_id
                )
        allowed = (
            select(e.c.id, e.c.display_name, tree.c.root_id)
            .join(tree, tree.c.id == e.c.id)
            .where(*predicates)
            .cte("staff_allowed")
        )
        count = select(func.count().label("total")).select_from(allowed).cte("staff_count")
        page = (
            select(allowed)
            .where(allowed.c.id > after if after else literal(True))
            .order_by(allowed.c.id)
            .limit(limit + 1)
            .cte("staff_page")
        )
        rows = (
            await session.execute(
                select(page, count.c.total).select_from(count.outerjoin(page, literal(True))).order_by(page.c.id)
            )
        ).all()
        total = int(rows[0].total)
        views = [StaffEntityView(r.id, r.root_id, r.display_name) for r in rows if r.id is not None]
        next_cursor = None
        if len(views) > limit:
            value = {
                "contract": contract,
                "after": str(views[limit - 1].id),
                "expires": int(datetime.now(timezone.utc).timestamp()) + 300,
            }
            raw = base64.urlsafe_b64encode(json.dumps(value, sort_keys=True).encode()).decode().rstrip("=")
            next_cursor = raw + "." + hmac.new(self._cursor_secret, raw.encode(), hashlib.sha256).hexdigest()
        return StaffEntityPage(tuple(views[:limit]), total, next_cursor)
