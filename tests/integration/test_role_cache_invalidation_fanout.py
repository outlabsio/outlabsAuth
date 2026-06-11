"""
Tier-2 perf regression (docs/PERFORMANCE_AUDIT_2026-06-10.md #8).

A role-definition edit (add/remove/set permissions, update) now invalidates only the
permission caches of users who actually hold that role — instead of flushing the whole
permission cache cluster-wide (which bumps the GLOBAL API-key snapshot version and forces
every worker to rebuild at once). A fail-safe fallback issues a single global invalidation
when the fan-out exceeds the cap, so we never under-invalidate.
"""
import pytest
import pytest_asyncio

from outlabs_auth import SimpleRBAC
from outlabs_auth.observability import ObservabilityConfig

_SECRET = "test-secret-key-do-not-use-in-production-1234567890"


@pytest_asyncio.fixture
async def auth_sr(test_engine):
    # enable_metrics=False so this instance registers nothing to the global Prometheus
    # registry (otherwise a second instance in the same process collides on metric names).
    auth = SimpleRBAC(
        engine=test_engine,
        secret_key=_SECRET,
        enable_token_cleanup=False,
        observability_config=ObservabilityConfig(enabled=False, enable_metrics=False),
    )
    await auth.initialize()
    yield auth
    await auth.shutdown()


class _RecordingCache:
    def __init__(self) -> None:
        self.user_invalidations: list[str] = []
        self.all_invalidations = 0

    async def publish_user_permissions_invalidation(self, user_id: str) -> bool:
        self.user_invalidations.append(str(user_id))
        return True

    async def publish_all_permissions_invalidation(self) -> bool:
        self.all_invalidations += 1
        return True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_role_permission_edit_fans_out_to_role_holders_only(auth_sr):
    auth = auth_sr
    async with auth.get_session() as session:
        await auth.permission_service.create_permission(session, name="report:read", display_name="r")
        await auth.permission_service.create_permission(session, name="report:write", display_name="w")
        role = await auth.role_service.create_role(session, name="reporter", display_name="Reporter")
        await auth.role_service.add_permissions_by_name(session, role.id, ["report:read"])
        holder = await auth.user_service.create_user(
            session=session, email="holder@example.com", password="TestPass123!",
            first_name="H", last_name="older",
        )
        other = await auth.user_service.create_user(
            session=session, email="other@example.com", password="TestPass123!",
            first_name="O", last_name="ther",
        )
        await auth.role_service.assign_role_to_user(session, holder.id, role.id)
        await session.commit()

    recorder = _RecordingCache()
    auth.role_service.cache_service = recorder

    async with auth.get_session() as session:
        await auth.role_service.add_permissions_by_name(session, role.id, ["report:write"])
        await session.commit()

    # Only the role holder is invalidated; no cluster-wide flush.
    assert recorder.all_invalidations == 0
    assert str(holder.id) in recorder.user_invalidations
    assert str(other.id) not in recorder.user_invalidations


@pytest.mark.integration
@pytest.mark.asyncio
async def test_role_permission_edit_falls_back_to_global_over_cap(auth_sr):
    auth = auth_sr
    async with auth.get_session() as session:
        await auth.permission_service.create_permission(session, name="cap:read", display_name="c")
        role = await auth.role_service.create_role(session, name="capped", display_name="Capped")
        user = await auth.user_service.create_user(
            session=session, email="capuser@example.com", password="TestPass123!",
            first_name="C", last_name="apped",
        )
        await auth.role_service.assign_role_to_user(session, user.id, role.id)
        await session.commit()

    recorder = _RecordingCache()
    auth.role_service.cache_service = recorder
    auth.role_service._ROLE_INVALIDATION_FANOUT_LIMIT = 0  # force the fail-safe path

    async with auth.get_session() as session:
        await auth.role_service.add_permissions_by_name(session, role.id, ["cap:read"])
        await session.commit()

    # Over the cap -> a single global invalidation, no per-user fan-out.
    assert recorder.all_invalidations >= 1
    assert recorder.user_invalidations == []
