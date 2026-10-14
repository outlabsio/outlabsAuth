"""Persistent S2 foundation, deliberately absent from runtime admission.

The caller supplies a transaction and server-authenticated principal UUID.
Nothing commits, caches a decision, assigns an ordinary role or creates global
scope. HTTP, list-SQL, credential and account-mutation integration are separate
qualification gates; this service alone must not activate staff administration.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select, literal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from outlabs_auth.core.exceptions import InvalidInputError, PermissionDeniedError
from outlabs_auth.models.sql.administrative_grant import (
    AdministrativeAdmission,
    AdministrativeAudit,
    AdministrativeGrantRecord,
    AdministrativeGroup,
    AdministrativeTemplateRevision,
)
from outlabs_auth.models.sql.closure import EntityClosure
from outlabs_auth.models.sql.entity import Entity
from outlabs_auth.models.sql.enums import DefinitionStatus, EntityClass, UserStatus
from outlabs_auth.models.sql.permission import Permission
from outlabs_auth.models.sql.user import User
from outlabs_auth.services.administrative_scope import AdministrativeDecision, AdministrativeDecisionReason


def _hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _fresh(statement: Any, lock: bool = False) -> Any:
    statement = statement.execution_options(populate_existing=True)
    return statement.with_for_update(read=True) if lock else statement


def _time(value: datetime | None) -> str | None:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        raise InvalidInputError(message="Administrative validity requires aware UTC times")
    return value.astimezone(timezone.utc).isoformat() if value else None


class AdministrativeGrantService:
    """One protected control domain identified by a configured root UUID.

    Exact actions and pinned admissions are the initial supported policy. Any
    wildcard, mutable condition or platform-control resource is refused. Broader
    policy support must add immutable conditions and the full S2 integration.
    """

    def __init__(self, *, trusted_internal_root_id: UUID, max_depth: int = 10) -> None:
        if not isinstance(trusted_internal_root_id, UUID) or not 1 <= max_depth <= 100:
            raise ValueError("A trusted root UUID and bounded depth are required")
        self.trusted_root = trusted_internal_root_id
        self.max_depth = max_depth

    async def _platform(self, session: AsyncSession, actor_id: UUID) -> User:
        actor = (
            await session.execute(
                select(User)
                .where(cast(Any, User.id) == actor_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        if actor is None or actor.status != UserStatus.ACTIVE or not actor.is_superuser:
            raise PermissionDeniedError(message="Administrative management is platform-only")
        return actor

    async def _path(self, session: AsyncSession, target_id: UUID, now: datetime, *, lock: bool = False) -> list[Entity]:
        # Walk only this target's parents in one bounded statement. Reconstruct
        # from fresh, locked rows for writes: a move between discovery and lock
        # acquisition must fail closed rather than authorizing stale ancestry.
        e = cast(Any, Entity).__table__
        ancestry = (
            select(e.c.id, e.c.parent_id, literal(0).label("depth"))
            .where(e.c.id == target_id)
            .cte("staff_target_ancestry", recursive=True)
        )
        ancestry = ancestry.union_all(
            select(e.c.id, e.c.parent_id, (ancestry.c.depth + 1).label("depth"))
            .join(ancestry, e.c.id == ancestry.c.parent_id)
            .where(ancestry.c.depth < self.max_depth + 1)
        )
        statement = select(Entity).where(cast(Any, Entity.id).in_(select(ancestry.c.id)))
        if lock:
            # PostgreSQL cannot lock recursive CTE results directly. Lock the
            # base rows in UUID order and validate their current parent links.
            statement = statement.order_by(cast(Any, Entity.id)).with_for_update(read=True)
        rows = (await session.execute(statement.execution_options(populate_existing=True))).scalars().all()
        by_id = {entity.id: entity for entity in rows}
        path: list[Entity] = []
        seen: set[UUID] = set()
        cursor: UUID | None = target_id
        while cursor is not None:
            if cursor in seen or len(path) > self.max_depth:
                raise InvalidInputError(message="Invalid administrative target ancestry")
            seen.add(cursor)
            entity = by_id.get(cursor)
            if entity is None or entity.entity_class != EntityClass.STRUCTURAL or entity.status != "active":
                raise InvalidInputError(message="Administrative target is not active and structural")
            if (entity.valid_from is not None and now < entity.valid_from) or (
                entity.valid_until is not None and now >= entity.valid_until
            ):
                raise InvalidInputError(message="Administrative target is outside its validity window")
            path.append(entity)
            cursor = entity.parent_id
        # Closure corruption must not expand reach. Parent links establish the
        # bounded path; closure must agree exactly, including depth and self.
        closure = (
            await session.execute(
                select(cast(Any, EntityClosure.ancestor_id), cast(Any, EntityClosure.depth)).where(
                    cast(Any, EntityClosure.descendant_id) == target_id
                )
            )
        ).all()
        if {(row[0], row[1]) for row in closure} != {(entity.id, depth) for depth, entity in enumerate(path)}:
            raise InvalidInputError(message="Administrative target closure disagrees with ancestry")
        return path

    async def _trusted(self, session: AsyncSession, now: datetime, *, lock: bool = False) -> None:
        path = await self._path(session, self.trusted_root, now, lock=lock)
        if len(path) != 1:
            raise InvalidInputError(message="Administrative control root is not independent")

    async def _customer(self, session: AsyncSession, target_id: UUID, now: datetime) -> list[Entity]:
        await self._trusted(session, now)
        path = await self._path(session, target_id, now)
        if path[-1].id == self.trusted_root:
            raise InvalidInputError(message="Customer selectors cannot include the Internal control domain")
        return path

    async def _audit(
        self, session: AsyncSession, actor_id: UUID, subject_id: UUID, event: str, evidence: dict[str, Any]
    ) -> None:
        session.add(AdministrativeAudit(actor_id=actor_id, subject_id=subject_id, event_type=event, evidence=evidence))
        await session.flush()

    async def create_template(
        self,
        session: AsyncSession,
        *,
        actor_id: UUID,
        template_key: str,
        revision: int,
        actions: list[str],
        entity_types: list[str] | None = None,
        customer_catalog: bool = False,
    ) -> AdministrativeTemplateRevision:
        await self._platform(session, actor_id)
        if not template_key or len(template_key) > 100 or revision < 1 or not actions:
            raise InvalidInputError(message="A named positive revision and nonempty policy are required")
        control = {
            "permission",
            "role",
            "config",
            "system",
            "bootstrap",
            "administrative_grant",
            "integration_principal",
        }
        snapshots: list[dict[str, str]] = []
        for action in sorted(set(actions)):
            is_catalog = customer_catalog is True and action in {
                "role:create",
                "role:read",
                "role:update",
                "role:delete",
            }
            if "*" in action or (action.split(":")[0] in control and not is_catalog):
                raise InvalidInputError(message="Wildcard and control-plane administrative actions are unsupported")
            permission = (
                await session.execute(
                    select(Permission)
                    .where(cast(Any, Permission.name) == action)
                    .options(selectinload(cast(Any, Permission.conditions)))
                )
            ).scalar_one_or_none()
            if (
                permission is None
                or permission.status != DefinitionStatus.ACTIVE
                or not permission.is_active
                or permission.conditions
            ):
                raise InvalidInputError(message="Administrative policy requires active unconditional exact permissions")
            snapshots.append({"id": str(permission.id), "name": permission.name})
        policy: dict[str, Any] = {
            "permissions": snapshots,
            "entity_types": sorted(set(entity_types or [])),
            "matching": "exact",
        }
        if customer_catalog is True:
            policy["customer_catalog"] = "bounded-customer-role-v1"
        template = AdministrativeTemplateRevision(
            template_key=template_key, revision=revision, policy=policy, policy_hash=_hash(policy)
        )
        session.add(template)
        await session.flush()
        await self._audit(
            session,
            actor_id,
            template.id,
            "template.created",
            {"policy_hash": template.policy_hash, "revision": revision},
        )
        return template

    async def set_template_active(
        self, session: AsyncSession, *, actor_id: UUID, template_id: UUID, active: bool
    ) -> None:
        await self._platform(session, actor_id)
        row = (
            await session.execute(
                select(AdministrativeTemplateRevision)
                .where(cast(Any, AdministrativeTemplateRevision.id) == template_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one()
        row.active = active
        await self._audit(session, actor_id, row.id, "template.lifecycle", {"active": active})

    async def create_group(self, session: AsyncSession, *, actor_id: UUID, group_key: str) -> AdministrativeGroup:
        await self._platform(session, actor_id)
        if not group_key or len(group_key) > 100:
            raise InvalidInputError(message="A bounded administrative group key is required")
        group = AdministrativeGroup(group_key=group_key)
        session.add(group)
        await session.flush()
        await self._audit(session, actor_id, group.id, "group.created", {"group_key": group_key})
        return group

    async def admit_customer(
        self, session: AsyncSession, *, actor_id: UUID, group_id: UUID, customer_root_id: UUID
    ) -> AdministrativeAdmission:
        await self._platform(session, actor_id)
        now = datetime.now(timezone.utc)
        if len(await self._customer(session, customer_root_id, now)) != 1:
            raise InvalidInputError(message="Only independent customer roots can be admitted")
        group = (
            await session.execute(
                select(AdministrativeGroup)
                .where(cast(Any, AdministrativeGroup.id) == group_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one()
        if not group.active:
            raise InvalidInputError(message="Administrative group is retired")
        existing = (
            await session.execute(
                select(AdministrativeAdmission).where(
                    cast(Any, AdministrativeAdmission.group_id) == group_id,
                    cast(Any, AdministrativeAdmission.customer_root_id) == customer_root_id,
                    cast(Any, AdministrativeAdmission.closed_at).is_(None),
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        row = AdministrativeAdmission(group_id=group_id, customer_root_id=customer_root_id)
        session.add(row)
        await session.flush()
        await self._audit(
            session,
            actor_id,
            row.id,
            "customer.admitted",
            {"group_id": str(group_id), "root_id": str(customer_root_id)},
        )
        return row

    async def remove_customer(self, session: AsyncSession, *, actor_id: UUID, admission_id: UUID) -> None:
        await self._platform(session, actor_id)
        admission = (
            await session.execute(
                select(AdministrativeAdmission)
                .where(cast(Any, AdministrativeAdmission.id) == admission_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one()
        if admission.closed_at is None:
            admission.closed_at = datetime.now(timezone.utc)
            await self._audit(
                session,
                actor_id,
                admission.id,
                "customer.removed",
                {"group_id": str(admission.group_id), "root_id": str(admission.customer_root_id)},
            )

    async def issue_grant(
        self,
        session: AsyncSession,
        *,
        actor_id: UUID,
        user_id: UUID,
        template_id: UUID,
        selector_kind: str,
        target_id: UUID,
        request_key: str,
        reason: str,
        valid_from: datetime | None = None,
        valid_until: datetime | None = None,
    ) -> AdministrativeGrantRecord:
        await self._platform(session, actor_id)
        payload = {
            "user_id": str(user_id),
            "template_id": str(template_id),
            "selector": selector_kind,
            "target_id": str(target_id),
            "reason": reason,
            "valid_from": _time(valid_from),
            "valid_until": _time(valid_until),
        }
        if (
            selector_kind not in {"entity", "subtree", "group"}
            or not request_key
            or len(request_key) > 100
            or not reason
            or len(reason) > 500
        ):
            raise InvalidInputError(message="A supported selector, request key and reason are required")
        if valid_from is not None and valid_until is not None and valid_from >= valid_until:
            raise InvalidInputError(message="Administrative validity window is empty")
        prior = (
            await session.execute(
                select(AdministrativeGrantRecord)
                .where(cast(Any, AdministrativeGrantRecord.request_key) == request_key)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        if prior is not None:
            if prior.request_hash != _hash(payload):
                raise InvalidInputError(message="Administrative request key has conflicting content")
            return prior  # Revoked retries remain revoked; regrant needs a new key.
        now = datetime.now(timezone.utc)
        await self._trusted(session, now)
        holder = (
            await session.execute(
                select(User)
                .where(cast(Any, User.id) == user_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        if holder is None or holder.status != UserStatus.ACTIVE or holder.root_entity_id != self.trusted_root:
            raise InvalidInputError(message="Grant holder is not an active Internal-domain human")
        template = (
            await session.execute(
                select(AdministrativeTemplateRevision)
                .where(cast(Any, AdministrativeTemplateRevision.id) == template_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one()
        if not template.active or template.policy_hash != _hash(template.policy):
            raise InvalidInputError(message="Administrative template is not an approved active revision")
        pins: list[str] = []
        if selector_kind == "group":
            group = (
                await session.execute(
                    select(AdministrativeGroup)
                    .where(cast(Any, AdministrativeGroup.id) == target_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            ).scalar_one()
            if not group.active:
                raise InvalidInputError(message="Administrative group is retired")
            admissions = (
                (
                    await session.execute(
                        select(AdministrativeAdmission).where(
                            cast(Any, AdministrativeAdmission.group_id) == target_id,
                            cast(Any, AdministrativeAdmission.closed_at).is_(None),
                        )
                    )
                )
                .scalars()
                .all()
            )
            for admission in admissions:
                if len(await self._customer(session, admission.customer_root_id, now)) != 1:
                    raise InvalidInputError(message="Administrative admission is not an independent customer")
            pins = sorted(str(admission.id) for admission in admissions)
            if not pins:
                raise InvalidInputError(message="Administrative group has no active admissions")
        else:
            await self._customer(session, target_id, now)
        grant = AdministrativeGrantRecord(
            user_id=user_id,
            template_revision_id=template_id,
            selector_kind=selector_kind,
            entity_id=target_id if selector_kind != "group" else None,
            group_id=target_id if selector_kind == "group" else None,
            admission_ids=pins,
            request_key=request_key,
            request_hash=_hash(payload),
            reason=reason,
            grantor_id=actor_id,
            holder_security_epoch=int(holder.session_security_epoch or 0),
            valid_from=valid_from,
            valid_until=valid_until,
        )
        session.add(grant)
        await session.flush()
        await self._audit(
            session,
            actor_id,
            grant.id,
            "grant.issued",
            {
                **payload,
                "admission_ids": pins,
                "holder_security_epoch": grant.holder_security_epoch,
            },
        )
        return grant

    async def revoke_grant(self, session: AsyncSession, *, actor_id: UUID, grant_id: UUID) -> None:
        await self._platform(session, actor_id)
        row = (
            await session.execute(
                select(AdministrativeGrantRecord)
                .where(cast(Any, AdministrativeGrantRecord.id) == grant_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one()
        if row.revoked_at is None:
            row.revoked_at = datetime.now(timezone.utc)
            await self._audit(session, actor_id, row.id, "grant.revoked", {})

    async def check_target(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        action: str,
        entity_id: UUID,
        account_root_required: bool = False,
        key_actions: set[str] | None = None,
        key_entity_ids: set[UUID] | None = None,
        protected_write: bool = False,
        qualifying_grant_id: UUID | None = None,
        customer_catalog: bool = False,
    ) -> AdministrativeDecision:
        """Fresh database evaluation; never infer authentication from this result.

        A host must pass credential ceilings from its verified authentication
        context. This foundation is not wired to the existing permission API.
        """
        catalog_action = action.split(":")[0] == "role"
        if catalog_action and (
            not customer_catalog or action not in {"role:create", "role:read", "role:update", "role:delete"}
        ):
            return AdministrativeDecision(False, AdministrativeDecisionReason.NO_MATCHING_GRANT)
        now = datetime.now(timezone.utc)
        try:
            await self._trusted(session, now, lock=protected_write)
            path = await self._path(session, entity_id, now, lock=protected_write)
            if path[-1].id == self.trusted_root:
                raise InvalidInputError(message="Internal cannot be a customer target")
        except InvalidInputError:
            return AdministrativeDecision(False, AdministrativeDecisionReason.INVALID_TARGET)
        holder = (
            await session.execute(
                select(User).where(cast(Any, User.id) == user_id).execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        if holder is None or holder.status != UserStatus.ACTIVE or holder.root_entity_id != self.trusted_root:
            return AdministrativeDecision(False, AdministrativeDecisionReason.UNTRUSTED_ACTOR)
        checked = path[-1].id if account_root_required else entity_id
        if (key_actions is not None and action not in key_actions) or (
            key_entity_ids is not None and not {entity_id, checked}.issubset(key_entity_ids)
        ):
            return AdministrativeDecision(False, AdministrativeDecisionReason.OUTSIDE_KEY_BOUNDARY, checked)
        if protected_write and qualifying_grant_id is None:
            raise InvalidInputError(message="A protected write must pin one qualifying grant")
        statement = select(AdministrativeGrantRecord).where(
            cast(Any, AdministrativeGrantRecord.user_id) == user_id,
            cast(Any, AdministrativeGrantRecord.holder_security_epoch) == int(holder.session_security_epoch or 0),
            cast(Any, AdministrativeGrantRecord.revoked_at).is_(None),
        )
        if qualifying_grant_id is not None:
            statement = statement.where(cast(Any, AdministrativeGrantRecord.id) == qualifying_grant_id)
        grants = (await session.execute(_fresh(statement.limit(65), protected_write))).scalars().all()
        if len(grants) > 64:
            return AdministrativeDecision(False, AdministrativeDecisionReason.NO_MATCHING_GRANT, checked)
        for grant in grants:
            if (grant.valid_from is not None and now < grant.valid_from) or (
                grant.valid_until is not None and now >= grant.valid_until
            ):
                continue
            template = (
                await session.execute(
                    _fresh(
                        select(AdministrativeTemplateRevision).where(
                            cast(Any, AdministrativeTemplateRevision.id) == grant.template_revision_id
                        ),
                        protected_write,
                    )
                )
            ).scalar_one()
            if (
                (catalog_action and template.policy.get("customer_catalog") != "bounded-customer-role-v1")
                or not template.active
                or template.policy_hash != _hash(template.policy)
                or template.policy.get("matching") != "exact"
            ):
                continue
            checked_entity = path[-1] if account_root_required else path[0]
            types = template.policy.get("entity_types", [])
            if types and checked_entity.entity_type not in types:
                continue
            permission_ref = next((item for item in template.policy["permissions"] if item["name"] == action), None)
            if permission_ref is None:
                continue
            permission = (
                await session.execute(
                    _fresh(
                        select(Permission)
                        .where(cast(Any, Permission.id) == UUID(permission_ref["id"]))
                        .options(selectinload(cast(Any, Permission.conditions))),
                        protected_write,
                    )
                )
            ).scalar_one_or_none()
            if (
                permission is None
                or permission.name != action
                or permission.status != DefinitionStatus.ACTIVE
                or not permission.is_active
                or permission.conditions
            ):
                continue
            selected = grant.entity_id == checked if grant.selector_kind == "entity" else False
            if grant.selector_kind == "subtree":
                selected = grant.entity_id in {entity.id for entity in (path[-1:] if account_root_required else path)}
            if grant.selector_kind == "group":
                group = (
                    await session.execute(
                        _fresh(
                            select(AdministrativeGroup).where(cast(Any, AdministrativeGroup.id) == grant.group_id),
                            protected_write,
                        )
                    )
                ).scalar_one()
                admission = (
                    await session.execute(
                        _fresh(
                            select(cast(Any, AdministrativeAdmission.id)).where(
                                cast(Any, AdministrativeAdmission.group_id) == grant.group_id,
                                cast(Any, AdministrativeAdmission.customer_root_id) == path[-1].id,
                                cast(Any, AdministrativeAdmission.closed_at).is_(None),
                            ),
                            protected_write,
                        )
                    )
                ).scalar_one_or_none()
                selected = group.active and admission is not None and str(admission) in grant.admission_ids
            if selected:
                return AdministrativeDecision(True, AdministrativeDecisionReason.ALLOWED, checked, grant.id)
        return AdministrativeDecision(False, AdministrativeDecisionReason.NO_MATCHING_GRANT, checked)
