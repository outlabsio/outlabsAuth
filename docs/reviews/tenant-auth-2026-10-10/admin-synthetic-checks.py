"""Read-only synthetic probes; uses no database, network or real identities."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import NAMESPACE_URL, uuid5

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.models.sql.enums import ConditionOperator
from outlabs_auth.services.administrative_scope import (
    AdministrativeActor,
    AdministrativeConditionResult,
    AdministrativeGrant,
    AdministrativeRole,
    AdministrativeTarget,
    AdministrativeTargetKind,
    evaluate_administrative_permission,
)
from outlabs_auth.services.cache import CacheService
from outlabs_auth.services.cache_backend import MemoryCacheBackend
from outlabs_auth.services.permission import PermissionService
from outlabs_auth.services.policy_engine import PolicyEvaluationEngine
from outlabs_auth.services import policy_engine, request_cache


def uid(label):
    return uuid5(NAMESPACE_URL, "synthetic-admin-review/" + label)


INTERNAL = uid("internal-one")
OTHER_INTERNAL = uid("internal-two")
ACTOR_ID = uid("staff")
CUSTOMER = uid("customer-b")
PRACTICE = uid("practice-west")
GROUP = uid("managed-group")
NOW = datetime(2026, 10, 10, 11, 59, tzinfo=timezone.utc)


def probe_prototype():
    roots = {
        INTERNAL: INTERNAL,
        OTHER_INTERNAL: OTHER_INTERNAL,
        CUSTOMER: CUSTOMER,
        PRACTICE: CUSTOMER,
    }
    closure = {
        INTERNAL: {INTERNAL},
        OTHER_INTERNAL: {OTHER_INTERNAL},
        CUSTOMER: {CUSTOMER, PRACTICE},
        PRACTICE: {PRACTICE},
    }
    grant = AdministrativeGrant(
        uid("grant"),
        ACTOR_ID,
        AdministrativeRole(uid("template"), frozenset({"*:*"})),
        AdministrativeTargetKind.GROUP,
        GROUP,
    )

    def decide(target, permission, selected=grant, outcomes=()):
        return evaluate_administrative_permission(
            actor=AdministrativeActor(ACTOR_ID, INTERNAL),
            target=target,
            permission=permission,
            grants=(selected,),
            now=NOW,
            trusted_internal_root_id=INTERNAL,
            entity_root_ids=roots,
            descendants_by_entity=closure,
            roots_by_group={GROUP: {CUSTOMER, OTHER_INTERNAL}},
            condition_results=outcomes,
        ).allowed

    other_internal = decide(AdministrativeTarget(OTHER_INTERNAL, OTHER_INTERNAL), "user:read")
    platform_action = decide(AdministrativeTarget(PRACTICE, CUSTOMER), "permission:update")
    conditioned = replace(grant, role=replace(grant.role, requires_conditions=True))
    outcome = AdministrativeConditionResult(
        ACTOR_ID, conditioned.grant_id, conditioned.role.role_id, PRACTICE, "document:update", True
    )
    entity_only_condition = decide(
        AdministrativeTarget(PRACTICE, CUSTOMER), "document:update", conditioned, (outcome,)
    )
    assert other_internal and platform_action and entity_only_condition
    return {
        "prototype_other_internal_root_allowed": other_internal,
        "prototype_platform_catalog_action_at_customer_allowed": platform_action,
        "prototype_positive_condition_has_only_entity_operation_binding": entity_only_condition,
        "qualification": "Caller-side lifecycle/classification/context validation is required; these are integration deltas, not deployed vulnerabilities.",
    }


class FrozenClock(datetime):
    instant = NOW

    @classmethod
    def now(cls, tz=None):
        return cls.instant.astimezone(tz) if tz else cls.instant.replace(tzinfo=None)


async def probe_implicit_time_cache():
    config = AuthConfig(
        secret_key="synthetic-review-secret-for-local-probe-only-0123456789abcdef",
        enable_entity_hierarchy=True,
        enable_abac=True,
        cache_backend="memory",
        redis_key_prefix="synthetic-admin-review",
        cache_permission_ttl=300,
    )
    service = PermissionService(config)
    service.cache_service = CacheService(MemoryCacheBackend(config), config)
    service._resolve_context_entity_type = AsyncMock(return_value="practice")
    service._abac_conditions_exist = AsyncMock(return_value=True)
    service._check_permission_via_user_roles_with_abac = AsyncMock(return_value=False)
    engine = PolicyEvaluationEngine()
    condition = SimpleNamespace(
        attribute="time.hour", operator=ConditionOperator.LESS_THAN,
        value="12", value_type="integer", condition_group_id=None,
    )
    evaluations = []

    async def membership_condition(**kwargs):
        context = kwargs["context"]
        evaluations.append(context["time"]["hour"])
        return engine.evaluate_sql_conditions(conditions=[condition], group_ops={}, context=context)

    service._check_permission_in_entity = membership_condition
    user = SimpleNamespace(
        id=ACTOR_ID, email="staff@example.invalid", status="active",
        timezone="UTC", locale="en", is_superuser=False,
    )
    original_clock = policy_engine.datetime
    policy_engine.datetime = FrozenClock
    try:
        request_cache.reset()
        before = await service.check_permission(
            AsyncMock(), ACTOR_ID, "document:update", entity_id=PRACTICE, user=user
        )
        FrozenClock.instant = datetime(2026, 10, 10, 12, 1, tzinfo=timezone.utc)
        request_cache.reset()
        after_cached = await service.check_permission(
            AsyncMock(), ACTOR_ID, "document:update", entity_id=PRACTICE, user=user
        )
        fresh_context = engine.create_context()
        after_fresh = engine.evaluate_sql_conditions(
            conditions=[condition], group_ops={}, context=fresh_context
        )
        assert before is True and after_cached is True and after_fresh is False
        assert evaluations == [11]
        return {
            "before_noon_authorized": before,
            "after_noon_cached_authorized": after_cached,
            "after_noon_fresh_condition_authorized": after_fresh,
            "membership_condition_evaluations": evaluations,
            "qualification": "Actual PermissionService/CacheService/MemoryCacheBackend/PolicyEvaluationEngine; database loaders are replaced by deterministic synthetic authority/condition suppliers.",
        }
    finally:
        policy_engine.datetime = original_clock
        request_cache.reset()


async def main():
    print(json.dumps({"prototype_probes": probe_prototype(), "implicit_time_cache": await probe_implicit_time_cache()}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
