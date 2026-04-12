import time
import uuid
from dataclasses import dataclass

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import event

from outlabs_auth import EnterpriseRBAC
from outlabs_auth.models.sql.enums import EntityClass
from outlabs_auth.routers import (
    get_entities_router,
    get_memberships_router,
    get_roles_router,
    get_users_router,
)
from outlabs_auth.utils.jwt import create_access_token


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
async def app(auth_instance: EnterpriseRBAC) -> FastAPI:
    application = FastAPI()
    application.include_router(get_users_router(auth_instance, prefix="/v1/users"))
    application.include_router(get_entities_router(auth_instance, prefix="/v1/entities"))
    application.include_router(get_memberships_router(auth_instance, prefix="/v1/memberships"))
    application.include_router(get_roles_router(auth_instance, prefix="/v1/roles"))
    return application


@pytest_asyncio.fixture
async def client(app: FastAPI) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        follow_redirects=True,
        timeout=20.0,
    ) as async_client:
        yield async_client


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
async def seeded_context(auth_instance: EnterpriseRBAC) -> dict[str, str]:
    async with auth_instance.get_session() as session:
        root = await auth_instance.entity_service.create_entity(
            session=session,
            name="diverse-internal",
            display_name="Diverse Internal",
            slug=f"diverse-internal-{uuid.uuid4().hex[:8]}",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        department = await auth_instance.entity_service.create_entity(
            session=session,
            name="dev-ops",
            display_name="Dev Ops",
            slug=f"dev-ops-{uuid.uuid4().hex[:8]}",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="department",
            parent_id=root.id,
        )
        team = await auth_instance.entity_service.create_entity(
            session=session,
            name="platform-team",
            display_name="Platform Team",
            slug=f"platform-team-{uuid.uuid4().hex[:8]}",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=department.id,
        )

        admin = await auth_instance.user_service.create_user(
            session=session,
            email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
            password="TestPass123!",
            first_name="Admin",
            last_name="User",
            is_superuser=True,
            root_entity_id=root.id,
        )

        permissions_target = await auth_instance.user_service.create_user(
            session=session,
            email=f"permissions-target-{uuid.uuid4().hex[:8]}@example.com",
            password="TestPass123!",
            first_name="Permissions",
            last_name="Target",
            root_entity_id=root.id,
        )

        permission_names = [
            "users:bench_read",
            "users:bench_write",
            "users:bench_export",
            "users:bench_manage",
        ]
        created_permissions = []
        for name in permission_names:
            created_permissions.append(
                await auth_instance.permission_service.create_permission(
                    session=session,
                    name=name,
                    display_name=name,
                )
            )

        direct_roles = []
        for idx, permission in enumerate(created_permissions[:2]):
            direct_roles.append(
                await auth_instance.role_service.create_role(
                    session=session,
                    name=f"permissions-direct-{idx}-{uuid.uuid4().hex[:6]}",
                    display_name=f"Permissions Direct {idx}",
                    permission_names=[permission.name],
                    is_global=True,
                )
            )

        membership_roles = []
        for idx, permission in enumerate(created_permissions[2:]):
            membership_roles.append(
                await auth_instance.role_service.create_role(
                    session=session,
                    name=f"permissions-membership-{idx}-{uuid.uuid4().hex[:6]}",
                    display_name=f"Permissions Membership {idx}",
                    permission_names=[permission.name],
                    is_global=False,
                    root_entity_id=root.id,
                )
            )

        for role in direct_roles:
            await auth_instance.role_service.assign_role_to_user(
                session=session,
                user_id=permissions_target.id,
                role_id=role.id,
            )

        await auth_instance.membership_service.add_member(
            session=session,
            entity_id=team.id,
            user_id=permissions_target.id,
            role_ids=[role.id for role in membership_roles],
        )

        for idx in range(25):
            user = await auth_instance.user_service.create_user(
                session=session,
                email=f"user-{idx}-{uuid.uuid4().hex[:6]}@example.com",
                password="TestPass123!",
                first_name=f"User{idx}",
                last_name="Bench",
                root_entity_id=root.id,
            )
            role = await auth_instance.role_service.create_role(
                session=session,
                name=f"role-{idx}-{uuid.uuid4().hex[:6]}",
                display_name=f"Role {idx}",
                root_entity_id=root.id,
                is_global=False,
            )
            await auth_instance.membership_service.add_member(
                session=session,
                entity_id=team.id if idx % 2 else department.id,
                user_id=user.id,
                role_ids=[role.id],
            )

        await session.commit()

    token = create_access_token(
        {"sub": str(admin.id)},
        secret_key=auth_instance.config.secret_key,
        algorithm=auth_instance.config.algorithm,
        audience=auth_instance.config.jwt_audience,
    )

    return {
        "headers": {"Authorization": f"Bearer {token}"},
        "root_id": str(root.id),
        "department_id": str(department.id),
        "permissions_target_user_id": str(permissions_target.id),
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_enterprise_admin_routes_stay_within_query_budgets(
    client: httpx.AsyncClient,
    query_counter: _QueryCounter,
    seeded_context: dict[str, str],
) -> None:
    cases = [
        ("users_me", "/v1/users/me", None, 1),
        ("memberships_me", "/v1/memberships/me", {"include_inactive": "true"}, 3),
        ("entity_get", f"/v1/entities/{seeded_context['root_id']}", None, 2),
        (
            "users_list",
            "/v1/users/",
            {"page": "1", "limit": "100", "root_entity_id": seeded_context["root_id"]},
            4,
        ),
        (
            "users_permissions",
            f"/v1/users/{seeded_context['permissions_target_user_id']}/permissions",
            None,
            8,
        ),
        (
            "entity_members",
            f"/v1/entities/{seeded_context['department_id']}/members",
            {"page": "1", "limit": "100"},
            5,
        ),
        ("entity_descendants", f"/v1/entities/{seeded_context['root_id']}/descendants", None, 3),
        ("entity_path", f"/v1/entities/{seeded_context['department_id']}/path", None, 3),
        (
            "roles_for_entity",
            f"/v1/roles/entity/{seeded_context['root_id']}",
            {"page": "1", "limit": "100"},
            5,
        ),
    ]

    for name, path, params, max_queries in cases:
        query_counter.reset()
        query_counter.enabled = True
        response = await client.get(path, params=params, headers=seeded_context["headers"])
        query_counter.enabled = False

        assert response.status_code == 200, f"{name} failed: {response.text}"
        assert query_counter.count <= max_queries, (
            f"{name} exceeded query budget: {query_counter.count} > {max_queries} " f"(db_ms={query_counter.db_ms:.1f})"
        )
