"""Real SQL/Redis budgets for conditioned and scheduled-binding cold paths.

Latency samples are local qualification evidence, not a production SLO. Run
with -s to retain numeric measurements. SQL caps are the portable regression gate.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4
import os

import pytest

from outlabs_auth.models.sql.enums import ConditionOperator
from outlabs_auth.models.sql.permission import Permission
from outlabs_auth.models.sql.role import Role, RoleCondition
from outlabs_auth.models.sql.user import User
from outlabs_auth.models.sql.user_role_membership import UserRoleMembership
from outlabs_auth.services import request_cache
from outlabs_auth.services.cache import CacheService
from outlabs_auth.services.permission import PermissionService
from tests.integration.query_budget_support import attach_query_counter, benchmark_operation


@pytest.mark.asyncio
@pytest.mark.parametrize("scheduled_count", [0, 250])
@pytest.mark.parametrize("conditioned", [False, True])
async def test_cold_scheduled_and_conditioned_query_budget(
    test_engine, test_session, redis_client, auth_config, scheduled_count, conditioned
):
    user = User(email=f"budget-{uuid4().hex}@example.test")
    permission = Permission(name="report:read", display_name="Read")
    roles = [
        Role(name=uuid4().hex, display_name="Reader", permissions=[permission]) for _ in range(scheduled_count + 1)
    ]
    test_session.add_all([user, *roles])
    await test_session.flush()
    if conditioned:
        test_session.add(
            RoleCondition(
                role_id=roles[0].id,
                attribute="time.hour",
                operator=ConditionOperator.LESS_THAN,
                value="24",
                value_type="integer",
            )
        )
    for index, role in enumerate(roles):
        test_session.add(
            UserRoleMembership(
                user_id=user.id,
                role_id=role.id,
                valid_from=datetime.now(timezone.utc) + timedelta(days=1) if index else None,
            )
        )
    await test_session.commit()
    config = auth_config.model_copy(update={"enable_caching": True, "enable_abac": conditioned})
    cache = CacheService(redis_client, config)
    service = PermissionService(config)
    service.cache_service = cache
    counter, cleanup = attach_query_counter(test_engine)

    async def check(cold):
        request_cache.reset()
        if cold:
            await cache.bump_global_api_key_auth_snapshot_version()
        async with type(test_session)(test_engine, expire_on_commit=False) as session:
            return await service.check_permission(session, user.id, permission.name, user=user)

    try:
        assert await check(True) is True
        iterations = int(os.getenv("AUTH_BUDGET_ITERATIONS", "25"))
        cold = await benchmark_operation(counter, lambda: check(True), iterations=iterations, warmup=2)
        warm = await benchmark_operation(counter, lambda: check(False), iterations=iterations, warmup=2)
        assert cold.query_count_max <= (8 if conditioned else 3), cold.summary()
        assert warm.query_count_max <= (6 if conditioned else 0), warm.summary()
        print(f"\n[s1-budget] conditions={conditioned} future_bindings={scheduled_count} cold: {cold.summary()}")
        print(f"[s1-budget] conditions={conditioned} future_bindings={scheduled_count} warm: {warm.summary()}")
    finally:
        cleanup()
        request_cache.reset()
