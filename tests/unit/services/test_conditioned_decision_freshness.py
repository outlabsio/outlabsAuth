"""F-admin-01: implicit server time must be evaluated on every conditioned decision."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.models.sql.enums import ConditionOperator
from outlabs_auth.services import policy_engine, request_cache
from outlabs_auth.services.cache import CacheService
from outlabs_auth.services.cache_backend import MemoryCacheBackend
from outlabs_auth.services.permission import PermissionService
from outlabs_auth.services.policy_engine import PolicyEvaluationEngine


class Clock(datetime):
    instant = datetime(2026, 1, 1, 11, 0, tzinfo=timezone.utc)

    @classmethod
    def now(cls, tz=None):
        return cls.instant.astimezone(tz) if tz else cls.instant.replace(tzinfo=None)


async def assert_time_transitions(backend, monkeypatch, *, start_hour: int, projection: bool) -> None:
    config = AuthConfig(
        secret_key="condition-cache-regression-local-secret-0123456789",
        enable_entity_hierarchy=True,
        enable_abac=True,
        cache_backend="memory",
        redis_key_prefix=f"condition-regression-{uuid4().hex}",
        cache_permission_ttl=300,
    )
    service = PermissionService(config)
    service.cache_service = CacheService(backend or MemoryCacheBackend(config), config)
    service._resolve_context_entity_type = AsyncMock(return_value="practice")
    service._abac_conditions_exist = AsyncMock(return_value=True)
    service._check_permission_via_user_roles_with_abac = AsyncMock(return_value=False)
    engine = PolicyEvaluationEngine()
    target = uuid4()
    targets = {resource: uuid4() for resource in ["morning", "afternoon"]}
    user = SimpleNamespace(
        id=uuid4(), email="member@example.test", status="active", timezone="UTC", locale="en", is_superuser=False
    )
    before_noon = SimpleNamespace(
        attribute="time.hour",
        operator=ConditionOperator.LESS_THAN,
        value="12",
        value_type="integer",
        condition_group_id=None,
    )
    after_noon = SimpleNamespace(
        attribute="time.hour",
        operator=ConditionOperator.GREATER_THAN_OR_EQUAL,
        value="12",
        value_type="integer",
        condition_group_id=None,
    )
    evaluations = []

    async def evaluate(**kwargs):
        resource = kwargs["context"]["resource"].get("id")
        if resource is None:
            resource = "morning" if kwargs["entity_id"] == targets["morning"] else "afternoon"
        conditions = [before_noon if resource == "morning" else after_noon]
        evaluations.append(kwargs["context"]["time"]["hour"])
        return engine.evaluate_sql_conditions(conditions=conditions, group_ops={}, context=kwargs["context"])

    service._check_permission_in_entity = evaluate
    monkeypatch.setattr(policy_engine, "datetime", Clock)
    try:
        for hour in [start_hour, 13 if start_hour == 11 else 11]:
            Clock.instant = datetime(2026, 1, 1, hour, 0, tzinfo=timezone.utc)
            request_cache.reset()
            for resource in ["morning", "afternoon"]:
                if projection:
                    granted = await service.get_effective_permission_names(
                        AsyncMock(),
                        user.id,
                        entity_id=targets[resource],
                        user=user,
                        candidate_permission_names={"document:update"},
                    )
                    allowed = "document:update" in granted
                else:
                    allowed = await service.check_permission(
                        AsyncMock(),
                        user.id,
                        "document:update",
                        entity_id=target,
                        user=user,
                        resource_context={"id": resource},
                    )
                assert allowed is ((hour < 12) if resource == "morning" else (hour >= 12))
        assert len(evaluations) == 4
    finally:
        request_cache.reset()


@pytest.mark.asyncio
@pytest.mark.parametrize("start_hour", [11, 13])
@pytest.mark.parametrize("projection", [False, True], ids=["detail", "permission-list"])
async def test_memory_conditioned_allow_and_deny_crossings(monkeypatch, start_hour, projection):
    await assert_time_transitions(None, monkeypatch, start_hour=start_hour, projection=projection)


@pytest.mark.asyncio
@pytest.mark.parametrize("start_hour", [11, 13])
@pytest.mark.parametrize("projection", [False, True], ids=["detail", "permission-list"])
async def test_redis_conditioned_allow_and_deny_crossings(redis_client, monkeypatch, start_hour, projection):
    await assert_time_transitions(redis_client, monkeypatch, start_hour=start_hour, projection=projection)


@pytest.mark.asyncio
@pytest.mark.parametrize("enable_abac", [False, True])
async def test_unconditioned_rbac_retains_decision_cache(enable_abac):
    config = AuthConfig(
        secret_key="condition-cache-regression-local-secret-0123456789", cache_backend="memory", enable_abac=enable_abac
    )
    service = PermissionService(config)
    service.cache_service = CacheService(MemoryCacheBackend(config), config)
    service._resolve_context_entity_type = AsyncMock(return_value=None)
    service._abac_conditions_exist = AsyncMock(return_value=False)
    service.get_user_permissions = AsyncMock(return_value=["document:read"])
    user = SimpleNamespace(id=uuid4(), is_superuser=False)
    try:
        for _ in range(2):
            request_cache.reset()
            assert await service.check_permission(AsyncMock(info={}), user.id, "document:read", user=user)
        service.get_user_permissions.assert_awaited_once()
    finally:
        request_cache.reset()
