from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL

import pytest

from outlabs_auth.models.sql.enums import DefinitionStatus, MembershipStatus, UserStatus
from outlabs_auth.services.administrative_scope import (
    AdministrativeActor,
    AdministrativeConditionResult,
    AdministrativeDecisionReason,
    AdministrativeGrant,
    AdministrativeRole,
    AdministrativeTarget,
    AdministrativeTargetKind,
    evaluate_administrative_permission,
)
from outlabs_auth.services.permission import PermissionMatcher

pytestmark = pytest.mark.unit

NOW = datetime(2026, 10, 10, 15, tzinfo=timezone.utc)
INTERNAL = uuid5(NAMESPACE_URL, "administrative-test/internal")
STAFF = uuid5(NAMESPACE_URL, "administrative-test/staff")
CUSTOMER_A = uuid5(NAMESPACE_URL, "administrative-test/customer-a")
PRACTICE_A = uuid5(NAMESPACE_URL, "administrative-test/practice-a")
CORPORATE = uuid5(NAMESPACE_URL, "administrative-test/corporate")
REGION = uuid5(NAMESPACE_URL, "administrative-test/corporate-region")
BRANCH_A = uuid5(NAMESPACE_URL, "administrative-test/corporate-branch-a")
BRANCH_B = uuid5(NAMESPACE_URL, "administrative-test/corporate-branch-b")
MANAGED_GROUP = uuid5(NAMESPACE_URL, "administrative-test/managed-group")

ROOTS = {
    INTERNAL: INTERNAL,
    CUSTOMER_A: CUSTOMER_A,
    PRACTICE_A: CUSTOMER_A,
    CORPORATE: CORPORATE,
    REGION: CORPORATE,
    BRANCH_A: CORPORATE,
    BRANCH_B: CORPORATE,
}
DESCENDANTS = {
    INTERNAL: frozenset({INTERNAL}),
    CUSTOMER_A: frozenset({CUSTOMER_A, PRACTICE_A}),
    PRACTICE_A: frozenset({PRACTICE_A}),
    CORPORATE: frozenset({CORPORATE, REGION, BRANCH_A, BRANCH_B}),
    REGION: frozenset({REGION, BRANCH_A}),
    BRANCH_A: frozenset({BRANCH_A}),
    BRANCH_B: frozenset({BRANCH_B}),
}
GROUPS = {MANAGED_GROUP: frozenset({CUSTOMER_A, CORPORATE})}
ACTOR = AdministrativeActor(STAFF, INTERNAL)


def grant(
    target_id: UUID,
    *permissions: str,
    kind: AdministrativeTargetKind = AdministrativeTargetKind.ENTITY,
    requires_conditions: bool = False,
) -> AdministrativeGrant:
    return AdministrativeGrant(
        grant_id=uuid4(),
        user_id=STAFF,
        role=AdministrativeRole(uuid4(), frozenset(permissions), requires_conditions=requires_conditions),
        target_kind=kind,
        target_id=target_id,
    )


def decide(target_id: UUID, grants: tuple[AdministrativeGrant, ...], permission: str = "agent:read", **kwargs):
    arguments = {
        "actor": ACTOR,
        "target": AdministrativeTarget(target_id, ROOTS.get(target_id, CUSTOMER_A)),
        "permission": permission,
        "grants": grants,
        "now": NOW,
        "trusted_internal_root_id": INTERNAL,
        "entity_root_ids": ROOTS,
        "descendants_by_entity": DESCENDANTS,
        "roots_by_group": GROUPS,
    }
    arguments.update(kwargs)
    return evaluate_administrative_permission(**arguments)


def test_standalone_practice_grant_keeps_customer_identity_separate():
    selected = grant(PRACTICE_A, "agent:read")
    result = decide(PRACTICE_A, (selected,))
    assert result.allowed
    assert result.grant_id == selected.grant_id
    assert result.checked_entity_id == PRACTICE_A
    assert ACTOR.root_entity_id == INTERNAL
    assert not hasattr(result, "is_global")
    assert not decide(CUSTOMER_A, (selected,)).allowed
    assert not decide(CORPORATE, (selected,)).allowed


def test_corporate_subtree_explicitly_places_plain_permission_at_selected_descendants():
    selected = grant(REGION, "agent:read", kind=AdministrativeTargetKind.SUBTREE)
    assert decide(REGION, (selected,)).allowed
    assert decide(BRANCH_A, (selected,)).allowed
    assert not decide(BRANCH_B, (selected,)).allowed
    assert not decide(CORPORATE, (selected,)).allowed
    assert not decide(PRACTICE_A, (selected,)).allowed


@pytest.mark.parametrize("target_id", [CUSTOMER_A, PRACTICE_A, CORPORATE, REGION, BRANCH_A, BRANCH_B])
def test_all_managed_group_includes_standalone_and_corporate_customers(target_id):
    selected = grant(MANAGED_GROUP, "agent:read", kind=AdministrativeTargetKind.GROUP)
    assert decide(target_id, (selected,)).allowed


def test_group_never_includes_internal_even_if_group_data_lists_it():
    selected = grant(MANAGED_GROUP, "*:*", kind=AdministrativeTargetKind.GROUP)
    groups = {MANAGED_GROUP: frozenset({CUSTOMER_A, CORPORATE, INTERNAL})}
    assert decide(PRACTICE_A, (selected,), roots_by_group=groups).allowed
    result = decide(INTERNAL, (selected,), roots_by_group=groups)
    assert not result.allowed
    assert result.reason == AdministrativeDecisionReason.INVALID_TARGET


def test_read_a_write_b_cannot_be_stitched_into_write_a():
    read_a = grant(PRACTICE_A, "agent:read")
    write_b = grant(BRANCH_A, "agent:update")
    grants = (read_a, write_b)
    assert decide(PRACTICE_A, grants).allowed
    assert decide(BRANCH_A, grants, "agent:update").allowed
    assert not decide(PRACTICE_A, grants, "agent:update").allowed
    assert not decide(BRANCH_A, grants, "agent:read").allowed


@pytest.mark.parametrize(
    ("granted", "required"),
    [
        ("agent:read", "agent:read"),
        ("agent:*", "agent:update"),
        ("*:*", "membership:delete"),
        ("agent:read_all", "agent:read_tree"),
        ("agent:read_tree", "agent:read"),
        ("agent:read_tree", "agent:read_all"),
        ("agent:read", "agent:update"),
    ],
)
def test_permissions_follow_existing_matcher_without_widening_target(granted, required):
    selected = grant(PRACTICE_A, granted)
    assert decide(PRACTICE_A, (selected,), required).allowed == PermissionMatcher({granted}).allows(required)
    assert not decide(BRANCH_A, (selected,), required).allowed


@pytest.mark.parametrize("status", [MembershipStatus.REVOKED, MembershipStatus.SUSPENDED, MembershipStatus.EXPIRED])
def test_non_active_grants_deny(status):
    assert not decide(PRACTICE_A, (replace(grant(PRACTICE_A, "agent:read"), status=status),)).allowed


@pytest.mark.parametrize("status", [DefinitionStatus.INACTIVE, DefinitionStatus.ARCHIVED])
def test_non_active_role_templates_deny(status):
    selected = grant(PRACTICE_A, "agent:read")
    selected = replace(selected, role=replace(selected.role, status=status))
    assert not decide(PRACTICE_A, (selected,)).allowed


@pytest.mark.parametrize(
    "changes",
    [
        {"valid_until": NOW - timedelta(seconds=1)},
        {"valid_from": NOW + timedelta(seconds=1)},
        {"valid_from": NOW, "valid_until": NOW - timedelta(seconds=1)},
        {"valid_from": NOW.replace(tzinfo=None)},
        {"valid_until": NOW.replace(tzinfo=None)},
    ],
)
def test_invalid_or_outside_time_windows_deny(changes):
    selected = replace(grant(PRACTICE_A, "agent:read"), **changes)
    assert not decide(PRACTICE_A, (selected,)).allowed


def test_time_window_boundaries_are_inclusive_like_existing_memberships():
    selected = replace(grant(PRACTICE_A, "agent:read"), valid_from=NOW, valid_until=NOW)
    assert decide(PRACTICE_A, (selected,)).allowed


def test_naive_evaluation_time_denies():
    result = decide(PRACTICE_A, (grant(PRACTICE_A, "agent:read"),), now=NOW.replace(tzinfo=None))
    assert result.reason == AdministrativeDecisionReason.INVALID_TIME


@pytest.mark.parametrize(
    "actor",
    [
        AdministrativeActor(STAFF, CUSTOMER_A),
        AdministrativeActor(STAFF, None),
        AdministrativeActor(STAFF, INTERNAL, UserStatus.SUSPENDED),
        AdministrativeActor(uuid4(), INTERNAL),
    ],
)
def test_untrusted_inactive_or_wrong_user_cannot_use_staff_grant(actor):
    assert not decide(PRACTICE_A, (grant(PRACTICE_A, "agent:read"),), actor=actor).allowed


def test_missing_trusted_internal_binding_denies():
    assert not decide(PRACTICE_A, (grant(PRACTICE_A, "agent:read"),), trusted_internal_root_id=None).allowed
    roots = {key: value for key, value in ROOTS.items() if key != INTERNAL}
    assert not decide(PRACTICE_A, (grant(PRACTICE_A, "agent:read"),), entity_root_ids=roots).allowed


def test_unknown_target_or_inconsistent_root_denies():
    selected = grant(MANAGED_GROUP, "*:*", kind=AdministrativeTargetKind.GROUP)
    assert not decide(uuid4(), (selected,)).allowed
    assert not decide(PRACTICE_A, (selected,), target=AdministrativeTarget(PRACTICE_A, CORPORATE)).allowed
    roots = {key: value for key, value in ROOTS.items() if key != CUSTOMER_A}
    assert not decide(PRACTICE_A, (selected,), entity_root_ids=roots).allowed


def test_unknown_group_root_or_closure_denies():
    selected = grant(MANAGED_GROUP, "agent:read", kind=AdministrativeTargetKind.GROUP)
    assert not decide(PRACTICE_A, (selected,), roots_by_group={}).allowed
    assert not decide(PRACTICE_A, (selected,), roots_by_group={MANAGED_GROUP: {uuid4(), CUSTOMER_A}}).allowed
    assert not decide(PRACTICE_A, (selected,), descendants_by_entity={}).allowed
    subtree = grant(CUSTOMER_A, "agent:read", kind=AdministrativeTargetKind.SUBTREE)
    assert not decide(CUSTOMER_A, (subtree,), descendants_by_entity={}).allowed


def test_cross_root_closure_edge_cannot_extend_subtree():
    selected = grant(CUSTOMER_A, "*:*", kind=AdministrativeTargetKind.SUBTREE)
    closure = {**DESCENDANTS, CUSTOMER_A: frozenset({CUSTOMER_A, PRACTICE_A, BRANCH_A})}
    assert not decide(BRANCH_A, (selected,), descendants_by_entity=closure).allowed


def test_practice_only_grant_cannot_authorize_customer_account_mutation():
    practice = grant(PRACTICE_A, "user:update")
    root = grant(CUSTOMER_A, "user:update")
    target = AdministrativeTarget(PRACTICE_A, CUSTOMER_A, requires_customer_root=True)
    assert not decide(PRACTICE_A, (practice,), "user:update", target=target).allowed
    result = decide(PRACTICE_A, (root,), "user:update", target=target)
    assert result.allowed
    assert result.checked_entity_id == CUSTOMER_A
    group = grant(MANAGED_GROUP, "user:update", kind=AdministrativeTargetKind.GROUP)
    assert decide(PRACTICE_A, (group,), "user:update", target=target).allowed


def test_personal_api_key_boundary_intersects_selected_target_and_account_root():
    selected = grant(MANAGED_GROUP, "*:*", kind=AdministrativeTargetKind.GROUP)
    assert decide(PRACTICE_A, (selected,), api_key_entity_ids={PRACTICE_A}).allowed
    assert not decide(BRANCH_A, (selected,), api_key_entity_ids={PRACTICE_A}).allowed
    assert not decide(PRACTICE_A, (selected,), api_key_entity_ids=set()).allowed
    target = AdministrativeTarget(PRACTICE_A, CUSTOMER_A, requires_customer_root=True)
    assert not decide(PRACTICE_A, (selected,), target=target, api_key_entity_ids={PRACTICE_A}).allowed
    assert decide(PRACTICE_A, (selected,), target=target, api_key_entity_ids={PRACTICE_A, CUSTOMER_A}).allowed


def condition_result(selected: AdministrativeGrant, **changes) -> AdministrativeConditionResult:
    result = AdministrativeConditionResult(
        STAFF, selected.grant_id, selected.role.role_id, PRACTICE_A, "agent:read", True
    )
    return replace(result, **changes)


def test_abac_conditions_require_one_positive_target_evaluated_result():
    selected = grant(PRACTICE_A, "agent:read", requires_conditions=True)
    outcome = condition_result(selected)
    assert not decide(PRACTICE_A, (selected,)).allowed
    assert decide(PRACTICE_A, (selected,), condition_results=(outcome,)).allowed
    assert not decide(PRACTICE_A, (selected,), condition_results=(replace(outcome, allowed=False),)).allowed
    assert not decide(PRACTICE_A, (selected,), condition_results=(outcome, replace(outcome, allowed=False))).allowed


@pytest.mark.parametrize(
    "changes",
    [
        {"user_id": uuid4()},
        {"grant_id": uuid4()},
        {"role_id": uuid4()},
        {"entity_id": BRANCH_A},
        {"permission": "agent:update"},
    ],
)
def test_condition_result_cannot_be_reused_for_other_actor_grant_role_target_or_action(changes):
    selected = grant(PRACTICE_A, "agent:read", requires_conditions=True)
    outcome = condition_result(selected, **changes)
    assert not decide(PRACTICE_A, (selected,), condition_results=(outcome,)).allowed


def test_target_permission_conditions_also_fail_closed_without_role_conditions():
    selected = grant(PRACTICE_A, "agent:read")
    target = AdministrativeTarget(PRACTICE_A, CUSTOMER_A, requires_conditions=True)
    assert not decide(PRACTICE_A, (selected,), target=target).allowed
    assert decide(PRACTICE_A, (selected,), target=target, condition_results=(condition_result(selected),)).allowed


def test_condition_pass_at_one_child_cannot_authorize_its_sibling_in_same_grant():
    selected = grant(CORPORATE, "agent:read", kind=AdministrativeTargetKind.SUBTREE, requires_conditions=True)
    child_a = condition_result(selected, entity_id=BRANCH_A)
    assert decide(BRANCH_A, (selected,), condition_results=(child_a,)).allowed
    assert not decide(BRANCH_B, (selected,), condition_results=(child_a,)).allowed


def test_customer_root_mutation_requires_root_bound_condition_outcome():
    selected = grant(CUSTOMER_A, "user:update", requires_conditions=True)
    target = AdministrativeTarget(PRACTICE_A, CUSTOMER_A, requires_customer_root=True)
    practice_outcome = condition_result(selected, permission="user:update")
    assert not decide(
        PRACTICE_A, (selected,), "user:update", target=target, condition_results=(practice_outcome,)
    ).allowed
    root_outcome = replace(practice_outcome, entity_id=CUSTOMER_A)
    assert decide(PRACTICE_A, (selected,), "user:update", target=target, condition_results=(root_outcome,)).allowed


def test_customer_root_grant_does_not_authorize_an_unknown_original_practice():
    selected = grant(CUSTOMER_A, "user:update")
    unknown_practice = uuid4()
    target = AdministrativeTarget(unknown_practice, CUSTOMER_A, requires_customer_root=True)
    assert not decide(unknown_practice, (selected,), "user:update", target=target).allowed


def test_unknown_entity_selector_and_empty_permission_deny():
    selected = grant(uuid4(), "*:*", kind=AdministrativeTargetKind.SUBTREE)
    assert not decide(PRACTICE_A, (selected,)).allowed
    assert not decide(PRACTICE_A, (grant(PRACTICE_A, "*:*"),), permission="").allowed


def test_policy_objects_and_permission_collections_are_immutable():
    permissions = {"agent:read"}
    role = AdministrativeRole(uuid4(), permissions)
    permissions.add("agent:update")
    assert role.permissions == frozenset({"agent:read"})
    with pytest.raises(FrozenInstanceError):
        role.status = DefinitionStatus.INACTIVE
    with pytest.raises(FrozenInstanceError):
        ACTOR.root_entity_id = CUSTOMER_A
