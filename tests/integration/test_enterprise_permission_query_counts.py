import time
import uuid
from dataclasses import dataclass
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import event

from outlabs_auth import EnterpriseRBAC
from outlabs_auth.models.sql.enums import EntityClass


@dataclass
class _QueryCounter:
    enabled: bool = False
    count: int = 0
    db_ms: float = 0.0

    def reset(self) -> None:
        self.count = 0
        self.db_ms = 0.0


@pytest_asyncio.fixture
async def auth_instance(test_engine) -> EnterpriseRBAC:
    auth = EnterpriseRBAC(
        engine=test_engine,
        secret_key="test-secret-key-do-not-use-in-production-12345678",
        access_token_expire_minutes=60,
        enable_token_cleanup=False,
    )
    await auth.initialize()
    yield auth
    await auth.shutdown()


@pytest_asyncio.fixture
async def query_counter(auth_instance: EnterpriseRBAC):
    counter = _QueryCounter()
    engine = auth_instance.engine.sync_engine

    @event.listens_for(engine, "before_cursor_execute")
    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        del conn, cursor, statement, parameters, executemany
        if counter.enabled:
            context._bench_start = time.perf_counter()

    @event.listens_for(engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        del conn, cursor, statement, parameters, executemany
        if counter.enabled:
            start = getattr(context, "_bench_start", None)
            if start is not None:
                counter.count += 1
                counter.db_ms += (time.perf_counter() - start) * 1000

    yield counter

    event.remove(engine, "before_cursor_execute", before_cursor_execute)
    event.remove(engine, "after_cursor_execute", after_cursor_execute)


@pytest_asyncio.fixture
async def seeded_permission_context(auth_instance: EnterpriseRBAC) -> dict[str, UUID]:
    async with auth_instance.get_session() as session:
        root = await auth_instance.entity_service.create_entity(
            session=session,
            name="query-bench-root",
            display_name="Query Bench Root",
            slug=f"query-bench-root-{uuid.uuid4().hex[:8]}",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        department = await auth_instance.entity_service.create_entity(
            session=session,
            name="query-bench-department",
            display_name="Query Bench Department",
            slug=f"query-bench-department-{uuid.uuid4().hex[:8]}",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="department",
            parent_id=root.id,
        )
        team = await auth_instance.entity_service.create_entity(
            session=session,
            name="query-bench-team",
            display_name="Query Bench Team",
            slug=f"query-bench-team-{uuid.uuid4().hex[:8]}",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=department.id,
        )

        user = await auth_instance.user_service.create_user(
            session=session,
            email=f"query-bench-{uuid.uuid4().hex[:8]}@example.com",
            password="TestPass123!",
            first_name="Query",
            last_name="Bench",
            root_entity_id=root.id,
        )

        perm_global = await auth_instance.permission_service.create_permission(
            session=session,
            name="report:view",
            display_name="Report View",
        )
        perm_direct = await auth_instance.permission_service.create_permission(
            session=session,
            name="team:manage",
            display_name="Team Manage",
        )
        perm_tree = await auth_instance.permission_service.create_permission(
            session=session,
            name="review:approve_tree",
            display_name="Review Approve Tree",
        )

        global_role = await auth_instance.role_service.create_role(
            session=session,
            name=f"query-bench-global-{uuid.uuid4().hex[:6]}",
            display_name="Query Bench Global",
            permission_names=[perm_global.name],
            is_global=True,
        )
        team_role = await auth_instance.role_service.create_role(
            session=session,
            name=f"query-bench-team-{uuid.uuid4().hex[:6]}",
            display_name="Query Bench Team",
            permission_names=[perm_direct.name],
            is_global=False,
            root_entity_id=root.id,
        )
        department_role = await auth_instance.role_service.create_role(
            session=session,
            name=f"query-bench-dept-{uuid.uuid4().hex[:6]}",
            display_name="Query Bench Department",
            permission_names=[perm_tree.name],
            is_global=False,
            root_entity_id=root.id,
        )

        await auth_instance.role_service.assign_role_to_user(
            session=session,
            user_id=user.id,
            role_id=global_role.id,
        )
        await auth_instance.membership_service.add_member(
            session=session,
            entity_id=team.id,
            user_id=user.id,
            role_ids=[team_role.id],
        )
        await auth_instance.membership_service.add_member(
            session=session,
            entity_id=department.id,
            user_id=user.id,
            role_ids=[department_role.id],
        )
        await session.commit()

    return {
        "user_id": user.id,
        "team_id": team.id,
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_enterprise_permission_checks_stay_within_query_budgets(
    auth_instance: EnterpriseRBAC,
    query_counter: _QueryCounter,
    seeded_permission_context: dict[str, UUID],
) -> None:
    cases = [
        (
            "global_no_entity",
            lambda session: auth_instance.permission_service.check_permission(
                session,
                user_id=seeded_permission_context["user_id"],
                permission="report:view",
            ),
            8,
        ),
        (
            "entity_direct",
            lambda session: auth_instance.permission_service.check_permission(
                session,
                user_id=seeded_permission_context["user_id"],
                permission="team:manage",
                entity_id=seeded_permission_context["team_id"],
            ),
            8,
        ),
        (
            "entity_from_ancestor_tree",
            lambda session: auth_instance.permission_service.check_permission(
                session,
                user_id=seeded_permission_context["user_id"],
                permission="review:approve",
                entity_id=seeded_permission_context["team_id"],
            ),
            8,
        ),
        (
            "get_user_permissions",
            lambda session: auth_instance.permission_service.get_user_permissions(
                session,
                user_id=seeded_permission_context["user_id"],
            ),
            7,
        ),
    ]

    for name, operation, max_queries in cases:
        query_counter.reset()
        async with auth_instance.get_session() as session:
            query_counter.enabled = True
            result = await operation(session)
            query_counter.enabled = False

        assert result, f"{name} returned an unexpected falsy result"
        assert query_counter.count <= max_queries, (
            f"{name} exceeded query budget: {query_counter.count} > {max_queries} " f"(db_ms={query_counter.db_ms:.1f})"
        )
