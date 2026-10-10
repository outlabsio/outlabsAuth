"""Experimental, target-bound administrative authorization primitive.

This module is not wired into authentication, routers, persistence or principal
scope resolution. It grants no runtime access and is not a release-ready staff
administration feature. Callers must supply current, server-verified actors,
roles, grants and validated entity/root, closure and administrative-group maps.
Grant creation, delegation containment, SQL list filtering, cache invalidation
and account-mutation guards remain separate integration requirements.

An administrative selector explicitly places its role at every selected target.
Consequently a plain permission applies throughout an explicit subtree selector,
using the existing PermissionMatcher.allows semantics. This differs from an
EntityMembership role inherited from an ancestor, which needs _tree/_all.
Neither a reusable role template nor this decision produces global scope.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Set
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID

from outlabs_auth.models.sql.enums import DefinitionStatus, MembershipStatus, UserStatus
from outlabs_auth.services.permission import PermissionMatcher


class AdministrativeTargetKind(str, Enum):
    ENTITY = "entity"
    SUBTREE = "subtree"
    GROUP = "group"


class AdministrativeDecisionReason(str, Enum):
    ALLOWED = "allowed"
    UNTRUSTED_ACTOR = "untrusted_actor"
    INVALID_TARGET = "invalid_target"
    INVALID_TIME = "invalid_time"
    OUTSIDE_KEY_BOUNDARY = "outside_key_boundary"
    NO_MATCHING_GRANT = "no_matching_grant"


@dataclass(frozen=True)
class AdministrativeActor:
    user_id: UUID
    root_entity_id: UUID | None
    status: UserStatus = UserStatus.ACTIVE


@dataclass(frozen=True)
class AdministrativeRole:
    """Current reusable role policy, without implicit global-user authority."""

    role_id: UUID
    permissions: frozenset[str]
    status: DefinitionStatus = DefinitionStatus.ACTIVE
    requires_conditions: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "permissions", frozenset(self.permissions))


@dataclass(frozen=True)
class AdministrativeGrant:
    grant_id: UUID
    user_id: UUID
    role: AdministrativeRole
    target_kind: AdministrativeTargetKind
    target_id: UUID
    status: MembershipStatus = MembershipStatus.ACTIVE
    valid_from: datetime | None = None
    valid_until: datetime | None = None


@dataclass(frozen=True)
class AdministrativeTarget:
    entity_id: UUID
    root_entity_id: UUID
    # Credentials and other tenant-wide account mutations must authorize the
    # owning customer root, not merely a practice where the user is a member.
    requires_customer_root: bool = False
    requires_conditions: bool = False


@dataclass(frozen=True)
class AdministrativeConditionResult:
    """Trusted caller's condition outcome bound to this exact operation.

    This is not a client-supplied assertion or an ABAC evaluator. The eventual
    integration must evaluate every applicable role/permission/resource
    condition at this actor, grant and target before constructing the result.
    """

    user_id: UUID
    grant_id: UUID
    role_id: UUID
    entity_id: UUID
    permission: str
    allowed: bool


@dataclass(frozen=True)
class AdministrativeDecision:
    allowed: bool
    reason: AdministrativeDecisionReason
    checked_entity_id: UUID | None = None
    grant_id: UUID | None = None


def _aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def _grant_is_current(grant: AdministrativeGrant, now: datetime) -> bool:
    if grant.status != MembershipStatus.ACTIVE or grant.role.status != DefinitionStatus.ACTIVE:
        return False
    if any(value is not None and not _aware(value) for value in (grant.valid_from, grant.valid_until)):
        return False
    if grant.valid_from is not None and grant.valid_until is not None and grant.valid_until < grant.valid_from:
        return False
    return (grant.valid_from is None or grant.valid_from <= now) and (
        grant.valid_until is None or now <= grant.valid_until
    )


def _selector_holds_entity(
    grant: AdministrativeGrant,
    entity_id: UUID,
    root_entity_id: UUID,
    *,
    trusted_internal_root_id: UUID,
    entity_root_ids: Mapping[UUID, UUID],
    descendants_by_entity: Mapping[UUID, Set[UUID]],
    roots_by_group: Mapping[UUID, Set[UUID]],
) -> bool:
    if grant.target_kind == AdministrativeTargetKind.GROUP:
        group_roots = roots_by_group.get(grant.target_id)
        if group_roots is None:
            return False
        # An accidental Internal entry can never delegate Internal authority.
        customer_roots = set(group_roots) - {trusted_internal_root_id}
        if any(entity_root_ids.get(root_id) != root_id for root_id in customer_roots):
            return False
        if root_entity_id not in customer_roots:
            return False
        if entity_id == root_entity_id:
            return True
        descendants = descendants_by_entity.get(root_entity_id)
        return descendants is not None and entity_id in descendants

    anchor_root = entity_root_ids.get(grant.target_id)
    if anchor_root is None or anchor_root == trusted_internal_root_id or anchor_root != root_entity_id:
        return False
    if grant.target_kind == AdministrativeTargetKind.ENTITY:
        return grant.target_id == entity_id
    if grant.target_kind == AdministrativeTargetKind.SUBTREE:
        descendants = descendants_by_entity.get(grant.target_id)
        return descendants is not None and grant.target_id in descendants and entity_id in descendants
    return False


def evaluate_administrative_permission(
    *,
    actor: AdministrativeActor,
    target: AdministrativeTarget,
    permission: str,
    grants: Iterable[AdministrativeGrant],
    now: datetime,
    trusted_internal_root_id: UUID | None,
    entity_root_ids: Mapping[UUID, UUID],
    descendants_by_entity: Mapping[UUID, Set[UUID]],
    roots_by_group: Mapping[UUID, Set[UUID]],
    condition_results: Iterable[AdministrativeConditionResult] = (),
    api_key_entity_ids: Set[UUID] | None = None,
) -> AdministrativeDecision:
    """Evaluate action and target from the same current administrative grant.

    Root-required operations still validate the original entity and intersect
    both that entity and its owning root with an optional personal API-key
    boundary. ``None`` means no additional key boundary; an empty set denies.
    Missing maps, untrusted actors, naive times and unevaluated conditions deny.
    This does not replace ordinary tenant authorization or grant-management
    policy, and callers must never accept these inputs from a request body.
    """
    if (
        trusted_internal_root_id is None
        or actor.root_entity_id != trusted_internal_root_id
        or actor.status != UserStatus.ACTIVE
        or entity_root_ids.get(trusted_internal_root_id) != trusted_internal_root_id
    ):
        return AdministrativeDecision(False, AdministrativeDecisionReason.UNTRUSTED_ACTOR)
    if not _aware(now):
        return AdministrativeDecision(False, AdministrativeDecisionReason.INVALID_TIME)
    if (
        not permission
        or entity_root_ids.get(target.entity_id) != target.root_entity_id
        or entity_root_ids.get(target.root_entity_id) != target.root_entity_id
        or target.root_entity_id == trusted_internal_root_id
    ):
        return AdministrativeDecision(False, AdministrativeDecisionReason.INVALID_TARGET)

    checked_entity_id = target.root_entity_id if target.requires_customer_root else target.entity_id
    if api_key_entity_ids is not None and (
        target.entity_id not in api_key_entity_ids or checked_entity_id not in api_key_entity_ids
    ):
        return AdministrativeDecision(False, AdministrativeDecisionReason.OUTSIDE_KEY_BOUNDARY, checked_entity_id)

    outcomes = tuple(condition_results)
    for grant in grants:
        if grant.user_id != actor.user_id or not _grant_is_current(grant, now):
            continue
        if not _selector_holds_entity(
            grant,
            checked_entity_id,
            target.root_entity_id,
            trusted_internal_root_id=trusted_internal_root_id,
            entity_root_ids=entity_root_ids,
            descendants_by_entity=descendants_by_entity,
            roots_by_group=roots_by_group,
        ):
            continue
        if not PermissionMatcher(grant.role.permissions).allows(permission):
            continue
        if grant.role.requires_conditions or target.requires_conditions:
            matches = tuple(
                result
                for result in outcomes
                if result.user_id == actor.user_id
                and result.grant_id == grant.grant_id
                and result.role_id == grant.role.role_id
                and result.entity_id == checked_entity_id
                and result.permission == permission
            )
            # Reject absent or contradictory outcomes; a caller supplies one
            # fully evaluated result per exact operation, never permission union.
            if len(matches) != 1 or not matches[0].allowed:
                continue
        return AdministrativeDecision(True, AdministrativeDecisionReason.ALLOWED, checked_entity_id, grant.grant_id)
    return AdministrativeDecision(False, AdministrativeDecisionReason.NO_MATCHING_GRANT, checked_entity_id)
