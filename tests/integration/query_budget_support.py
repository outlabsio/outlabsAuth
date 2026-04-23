from __future__ import annotations

import statistics
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import event

from outlabs_auth import EnterpriseRBAC, SimpleRBAC
from outlabs_auth.models.sql.enums import APIKeyKind, EntityClass, IntegrationPrincipalScopeKind
from outlabs_auth.utils.jwt import create_access_token


@dataclass
class QueryCounter:
    enabled: bool = False
    count: int = 0
    db_ms: float = 0.0

    def reset(self) -> None:
        self.count = 0
        self.db_ms = 0.0


def attach_query_counter(engine) -> tuple[QueryCounter, Callable[[], None]]:
    counter = QueryCounter()
    sync_engine = getattr(engine, "sync_engine", engine)

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        del conn, cursor, statement, parameters, executemany
        if counter.enabled:
            context._bench_start = time.perf_counter()

    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        del conn, cursor, statement, parameters, executemany
        if counter.enabled:
            start = getattr(context, "_bench_start", None)
            if start is not None:
                counter.count += 1
                counter.db_ms += (time.perf_counter() - start) * 1000

    event.listen(sync_engine, "before_cursor_execute", before_cursor_execute)
    event.listen(sync_engine, "after_cursor_execute", after_cursor_execute)

    def cleanup() -> None:
        event.remove(sync_engine, "before_cursor_execute", before_cursor_execute)
        event.remove(sync_engine, "after_cursor_execute", after_cursor_execute)

    return counter, cleanup


@dataclass
class LatencyStats:
    """Summary statistics for a benchmarked operation."""

    iterations: int
    db_ms_samples: list[float] = field(default_factory=list)
    wall_ms_samples: list[float] = field(default_factory=list)
    query_count_samples: list[int] = field(default_factory=list)

    @staticmethod
    def _percentile(values: list[float], p: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        if len(ordered) == 1:
            return ordered[0]
        # nearest-rank percentile, 0 <= p <= 100
        k = max(1, min(len(ordered), int(round(p / 100.0 * len(ordered)))))
        return ordered[k - 1]

    @property
    def db_ms_p50(self) -> float:
        return self._percentile(self.db_ms_samples, 50)

    @property
    def db_ms_p95(self) -> float:
        return self._percentile(self.db_ms_samples, 95)

    @property
    def db_ms_p99(self) -> float:
        return self._percentile(self.db_ms_samples, 99)

    @property
    def wall_ms_p50(self) -> float:
        return self._percentile(self.wall_ms_samples, 50)

    @property
    def wall_ms_p95(self) -> float:
        return self._percentile(self.wall_ms_samples, 95)

    @property
    def wall_ms_p99(self) -> float:
        return self._percentile(self.wall_ms_samples, 99)

    @property
    def db_ms_mean(self) -> float:
        return statistics.fmean(self.db_ms_samples) if self.db_ms_samples else 0.0

    @property
    def wall_ms_mean(self) -> float:
        return statistics.fmean(self.wall_ms_samples) if self.wall_ms_samples else 0.0

    @property
    def query_count_max(self) -> int:
        return max(self.query_count_samples) if self.query_count_samples else 0

    @property
    def query_count_min(self) -> int:
        return min(self.query_count_samples) if self.query_count_samples else 0

    def summary(self) -> str:
        return (
            f"iterations={self.iterations} "
            f"queries[min/max]={self.query_count_min}/{self.query_count_max} "
            f"db_ms[p50/p95/p99]={self.db_ms_p50:.2f}/{self.db_ms_p95:.2f}/{self.db_ms_p99:.2f} "
            f"wall_ms[p50/p95/p99]={self.wall_ms_p50:.2f}/{self.wall_ms_p95:.2f}/{self.wall_ms_p99:.2f}"
        )


async def benchmark_operation(
    counter: QueryCounter,
    operation: Callable[[], Awaitable[Any]],
    *,
    iterations: int = 50,
    warmup: int = 5,
) -> LatencyStats:
    """
    Run an async operation N times with the counter attached and return stats.

    - Warmup iterations are executed first but excluded from samples (lets
      connection pools / prepared statements / caches reach steady state).
    - Each sampled iteration is timed end-to-end (wall clock) alongside the
      DB time and query count captured by the counter.

    The caller is responsible for ensuring `operation` is idempotent and does
    not accumulate state (e.g., rollback writes, or read-only benchmarks).
    """
    for _ in range(max(0, warmup)):
        counter.reset()
        counter.enabled = True
        try:
            await operation()
        finally:
            counter.enabled = False

    stats = LatencyStats(iterations=iterations)
    for _ in range(iterations):
        counter.reset()
        counter.enabled = True
        start = time.perf_counter()
        try:
            await operation()
        finally:
            counter.enabled = False
            wall_ms = (time.perf_counter() - start) * 1000
        stats.db_ms_samples.append(counter.db_ms)
        stats.wall_ms_samples.append(wall_ms)
        stats.query_count_samples.append(counter.count)

    return stats


@dataclass(frozen=True, slots=True)
class EnterpriseQueryBudgetContext:
    root_id: UUID
    department_id: UUID
    team_id: UUID
    admin_user_id: UUID
    benchmark_user_id: UUID
    permissions_target_user_id: UUID
    permission_global_name: str
    permission_entity_name: str
    permission_tree_check_name: str
    api_key_global_scope: str
    api_key_entity_scope: str
    api_key_denied_scope: str
    unanchored_api_key: str
    anchored_api_key: str
    admin_token: str
    benchmark_user_token: str

    @property
    def admin_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.admin_token}"}

    @property
    def benchmark_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.benchmark_user_token}"}


@dataclass(frozen=True, slots=True)
class PersonalApiKeySelfServiceQueryContext:
    department_id: UUID
    user_id: UUID
    global_permission_name: str
    entity_permission_name: str
    token: str
    key_count: int

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}


@dataclass(frozen=True, slots=True)
class EnterpriseAdminApiKeyQueryContext:
    root_id: UUID
    department_id: UUID
    team_id: UUID
    superuser_id: UUID
    entity_admin_id: UUID
    entity_principal_id: UUID
    system_principal_id: UUID
    entity_system_api_key: str
    system_global_api_key: str
    entity_system_scope_tree_name: str
    entity_system_scope_check_name: str
    system_global_scope: str
    entity_admin_token: str
    superuser_token: str

    @property
    def entity_admin_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.entity_admin_token}"}

    @property
    def superuser_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.superuser_token}"}


@dataclass(frozen=True, slots=True)
class ApiKeyMutationQueryContext:
    root_id: UUID
    department_id: UUID
    team_id: UUID
    admin_user_id: UUID
    permission_removed_role_id: UUID
    membership_role_id: UUID
    direct_user_role_id: UUID
    permission_removed_owner_id: UUID
    membership_owner_id: UUID
    direct_role_owner_id: UUID
    permission_removed_key: str
    membership_key: str
    direct_role_key: str
    permission_removed_scope_check_name: str
    membership_scope_check_name: str
    direct_role_scope_name: str


async def seed_enterprise_query_budget_context(
    auth_instance: EnterpriseRBAC,
) -> EnterpriseQueryBudgetContext:
    unique = uuid.uuid4().hex[:8]

    permission_global_name = f"report{unique}:view"
    permission_entity_name = f"team{unique}:manage"
    permission_tree_name = f"review{unique}:approve_tree"
    permission_tree_check_name = permission_tree_name.removesuffix("_tree")
    api_key_global_scope = f"dashboard{unique}:read"
    api_key_entity_scope = f"pipeline{unique}:read_tree"
    api_key_denied_scope = f"secrets{unique}:read"
    role_read_permission_name = "role:read"
    user_permission_names = [
        f"users{unique}:bench_read",
        f"users{unique}:bench_write",
        f"users{unique}:bench_export",
        f"users{unique}:bench_manage",
    ]

    async with auth_instance.get_session() as session:
        root = await auth_instance.entity_service.create_entity(
            session=session,
            name=f"query-bench-root-{unique}",
            display_name="Query Bench Root",
            slug=f"query-bench-root-{unique}",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        department = await auth_instance.entity_service.create_entity(
            session=session,
            name=f"query-bench-department-{unique}",
            display_name="Query Bench Department",
            slug=f"query-bench-department-{unique}",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="department",
            parent_id=root.id,
        )
        team = await auth_instance.entity_service.create_entity(
            session=session,
            name=f"query-bench-team-{unique}",
            display_name="Query Bench Team",
            slug=f"query-bench-team-{unique}",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=department.id,
        )

        admin = await auth_instance.user_service.create_user(
            session=session,
            email=f"query-bench-admin-{unique}@example.com",
            password="TestPass123!",
            first_name="Query",
            last_name="Admin",
            is_superuser=True,
            root_entity_id=root.id,
        )
        benchmark_user = await auth_instance.user_service.create_user(
            session=session,
            email=f"query-bench-user-{unique}@example.com",
            password="TestPass123!",
            first_name="Query",
            last_name="Bench",
            root_entity_id=root.id,
        )

        permission_names = [
            permission_global_name,
            permission_entity_name,
            permission_tree_name,
            api_key_global_scope,
            api_key_entity_scope,
            role_read_permission_name,
            *user_permission_names,
        ]
        for name in permission_names:
            await auth_instance.permission_service.create_permission(
                session=session,
                name=name,
                display_name=name,
            )

        global_role = await auth_instance.role_service.create_role(
            session=session,
            name=f"query-bench-global-{unique}",
            display_name="Query Bench Global",
            permission_names=[permission_global_name],
            is_global=True,
        )
        team_role = await auth_instance.role_service.create_role(
            session=session,
            name=f"query-bench-team-{unique}",
            display_name="Query Bench Team",
            permission_names=[permission_entity_name],
            is_global=False,
            root_entity_id=root.id,
        )
        department_role = await auth_instance.role_service.create_role(
            session=session,
            name=f"query-bench-department-{unique}",
            display_name="Query Bench Department",
            permission_names=[permission_tree_name],
            is_global=False,
            root_entity_id=root.id,
        )
        api_key_global_role = await auth_instance.role_service.create_role(
            session=session,
            name=f"query-bench-api-key-global-{unique}",
            display_name="Query Bench API Key Global",
            permission_names=[api_key_global_scope],
            is_global=True,
        )
        api_key_entity_role = await auth_instance.role_service.create_role(
            session=session,
            name=f"query-bench-api-key-entity-{unique}",
            display_name="Query Bench API Key Entity",
            permission_names=[api_key_entity_scope],
            is_global=False,
            root_entity_id=root.id,
        )

        direct_roles = []
        for index, permission_name in enumerate(user_permission_names[:2]):
            direct_roles.append(
                await auth_instance.role_service.create_role(
                    session=session,
                    name=f"query-bench-direct-{index}-{unique}",
                    display_name=f"Query Bench Direct {index}",
                    permission_names=[permission_name],
                    is_global=True,
                )
            )

        direct_roles.append(
            await auth_instance.role_service.create_role(
                session=session,
                name=f"query-bench-role-read-{unique}",
                display_name="Query Bench Role Read",
                permission_names=[role_read_permission_name],
                is_global=True,
            )
        )

        membership_roles = []
        for index, permission_name in enumerate(user_permission_names[2:]):
            membership_roles.append(
                await auth_instance.role_service.create_role(
                    session=session,
                    name=f"query-bench-membership-{index}-{unique}",
                    display_name=f"Query Bench Membership {index}",
                    permission_names=[permission_name],
                    is_global=False,
                    root_entity_id=root.id,
                )
            )

        for role in [global_role, api_key_global_role, *direct_roles]:
            await auth_instance.role_service.assign_role_to_user(
                session=session,
                user_id=benchmark_user.id,
                role_id=role.id,
            )

        await auth_instance.membership_service.add_member(
            session=session,
            entity_id=team.id,
            user_id=benchmark_user.id,
            role_ids=[team_role.id, *(role.id for role in membership_roles)],
        )
        await auth_instance.membership_service.add_member(
            session=session,
            entity_id=department.id,
            user_id=benchmark_user.id,
            role_ids=[department_role.id, api_key_entity_role.id],
        )

        for index in range(25):
            user = await auth_instance.user_service.create_user(
                session=session,
                email=f"query-bench-extra-{index}-{unique}@example.com",
                password="TestPass123!",
                first_name=f"User{index}",
                last_name="Bench",
                root_entity_id=root.id,
            )
            role = await auth_instance.role_service.create_role(
                session=session,
                name=f"query-bench-extra-role-{index}-{unique}",
                display_name=f"Query Bench Extra Role {index}",
                root_entity_id=root.id,
                is_global=False,
            )
            await auth_instance.membership_service.add_member(
                session=session,
                entity_id=team.id if index % 2 else department.id,
                user_id=user.id,
                role_ids=[role.id],
            )

        unanchored_api_key, _ = await auth_instance.api_key_service.create_api_key(
            session=session,
            owner_id=benchmark_user.id,
            name="Query Bench Unanchored Key",
            scopes=[api_key_global_scope],
            actor_user_id=benchmark_user.id,
        )
        anchored_api_key, _ = await auth_instance.api_key_service.create_api_key(
            session=session,
            owner_id=benchmark_user.id,
            name="Query Bench Anchored Key",
            scopes=[api_key_entity_scope],
            entity_id=department.id,
            inherit_from_tree=True,
            actor_user_id=benchmark_user.id,
        )

        await session.commit()

    admin_token = create_access_token(
        {"sub": str(admin.id)},
        secret_key=auth_instance.config.secret_key,
        algorithm=auth_instance.config.algorithm,
        audience=auth_instance.config.jwt_audience,
    )
    benchmark_user_token = create_access_token(
        {"sub": str(benchmark_user.id)},
        secret_key=auth_instance.config.secret_key,
        algorithm=auth_instance.config.algorithm,
        audience=auth_instance.config.jwt_audience,
    )

    return EnterpriseQueryBudgetContext(
        root_id=root.id,
        department_id=department.id,
        team_id=team.id,
        admin_user_id=admin.id,
        benchmark_user_id=benchmark_user.id,
        permissions_target_user_id=benchmark_user.id,
        permission_global_name=permission_global_name,
        permission_entity_name=permission_entity_name,
        permission_tree_check_name=permission_tree_check_name,
        api_key_global_scope=api_key_global_scope,
        api_key_entity_scope=api_key_entity_scope,
        api_key_denied_scope=api_key_denied_scope,
        unanchored_api_key=unanchored_api_key,
        anchored_api_key=anchored_api_key,
        admin_token=admin_token,
        benchmark_user_token=benchmark_user_token,
    )


async def seed_personal_api_key_self_service_query_context(
    auth_instance: EnterpriseRBAC,
) -> PersonalApiKeySelfServiceQueryContext:
    unique = uuid.uuid4().hex[:8]
    global_permission_name = f"dashboard{unique}:read"
    entity_permission_name = f"pipeline{unique}:read_tree"

    async with auth_instance.get_session() as session:
        root = await auth_instance.entity_service.create_entity(
            session=session,
            name=f"self-service-root-{unique}",
            display_name="Self Service Root",
            slug=f"self-service-root-{unique}",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        department = await auth_instance.entity_service.create_entity(
            session=session,
            name=f"self-service-department-{unique}",
            display_name="Self Service Department",
            slug=f"self-service-department-{unique}",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="department",
            parent_id=root.id,
        )
        user = await auth_instance.user_service.create_user(
            session=session,
            email=f"self-service-{unique}@example.com",
            password="TestPass123!",
            first_name="Self",
            last_name="Service",
            root_entity_id=root.id,
        )

        global_permission = await auth_instance.permission_service.create_permission(
            session,
            name=global_permission_name,
            display_name=global_permission_name,
            description="global self-service permission",
        )
        entity_permission = await auth_instance.permission_service.create_permission(
            session,
            name=entity_permission_name,
            display_name=entity_permission_name,
            description="entity self-service permission",
        )

        global_role = await auth_instance.role_service.create_role(
            session=session,
            name=f"self-service-global-role-{unique}",
            display_name="Self Service Global Role",
            is_global=True,
        )
        entity_role = await auth_instance.role_service.create_role(
            session=session,
            name=f"self-service-entity-role-{unique}",
            display_name="Self Service Entity Role",
            is_global=False,
            root_entity_id=root.id,
        )
        await auth_instance.role_service.add_permissions(session, global_role.id, [global_permission.id])
        await auth_instance.role_service.add_permissions(session, entity_role.id, [entity_permission.id])
        await auth_instance.role_service.assign_role_to_user(
            session=session,
            user_id=user.id,
            role_id=global_role.id,
            assigned_by_id=user.id,
        )
        await auth_instance.membership_service.add_member(
            session=session,
            entity_id=department.id,
            user_id=user.id,
            role_ids=[entity_role.id],
            joined_by_id=user.id,
        )

        await auth_instance.api_key_service.create_api_key(
            session=session,
            owner_id=user.id,
            name="Self Service Unanchored Key",
            scopes=[global_permission_name],
            actor_user_id=user.id,
        )
        await auth_instance.api_key_service.create_api_key(
            session=session,
            owner_id=user.id,
            name="Self Service Anchored Key",
            scopes=[entity_permission_name],
            entity_id=department.id,
            inherit_from_tree=True,
            actor_user_id=user.id,
        )
        await session.commit()

    token = create_access_token(
        {"sub": str(user.id)},
        secret_key=auth_instance.config.secret_key,
        algorithm=auth_instance.config.algorithm,
        audience=auth_instance.config.jwt_audience,
    )

    return PersonalApiKeySelfServiceQueryContext(
        department_id=department.id,
        user_id=user.id,
        global_permission_name=global_permission_name,
        entity_permission_name=entity_permission_name,
        token=token,
        key_count=2,
    )


async def seed_enterprise_admin_api_key_query_context(
    auth_instance: EnterpriseRBAC,
) -> EnterpriseAdminApiKeyQueryContext:
    unique = uuid.uuid4().hex[:8]
    entity_scope_tree_name = f"contacts{unique}:read_tree"
    entity_scope_check_name = entity_scope_tree_name.removesuffix("_tree")
    system_global_scope = f"jobs{unique}:run"
    api_key_admin_permissions = [
        "api_key:create_tree",
        "api_key:read_tree",
        "api_key:update_tree",
        "api_key:delete_tree",
    ]

    async with auth_instance.get_session() as session:
        root = await auth_instance.entity_service.create_entity(
            session=session,
            name=f"admin-bench-root-{unique}",
            display_name="Admin Bench Root",
            slug=f"admin-bench-root-{unique}",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        department = await auth_instance.entity_service.create_entity(
            session=session,
            name=f"admin-bench-department-{unique}",
            display_name="Admin Bench Department",
            slug=f"admin-bench-department-{unique}",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="department",
            parent_id=root.id,
        )
        team = await auth_instance.entity_service.create_entity(
            session=session,
            name=f"admin-bench-team-{unique}",
            display_name="Admin Bench Team",
            slug=f"admin-bench-team-{unique}",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=department.id,
        )

        superuser = await auth_instance.user_service.create_user(
            session=session,
            email=f"admin-bench-superuser-{unique}@example.com",
            password="TestPass123!",
            first_name="Platform",
            last_name="Admin",
            is_superuser=True,
            root_entity_id=root.id,
        )
        entity_admin = await auth_instance.user_service.create_user(
            session=session,
            email=f"admin-bench-entity-admin-{unique}@example.com",
            password="TestPass123!",
            first_name="Entity",
            last_name="Admin",
            root_entity_id=root.id,
        )

        permission_names = [entity_scope_tree_name, system_global_scope, *api_key_admin_permissions]
        permission_ids = []
        for permission_name in permission_names:
            permission = await auth_instance.permission_service.create_permission(
                session,
                name=permission_name,
                display_name=permission_name,
            )
            permission_ids.append(permission.id)

        entity_admin_role = await auth_instance.role_service.create_role(
            session=session,
            name=f"admin-bench-role-{unique}",
            display_name="Admin Bench Role",
            is_global=False,
            root_entity_id=root.id,
        )
        await auth_instance.role_service.add_permissions(session, entity_admin_role.id, permission_ids)
        await auth_instance.membership_service.add_member(
            session=session,
            entity_id=department.id,
            user_id=entity_admin.id,
            role_ids=[entity_admin_role.id],
            joined_by_id=superuser.id,
        )

        entity_principal = await auth_instance.integration_principal_service.create_principal(
            session,
            name="Entity Worker Principal",
            description="Entity scoped benchmark principal",
            scope_kind=IntegrationPrincipalScopeKind.ENTITY,
            anchor_entity_id=department.id,
            inherit_from_tree=True,
            allowed_scopes=[entity_scope_tree_name],
            created_by_user_id=entity_admin.id,
        )
        entity_system_api_key, _ = await auth_instance.api_key_service.create_api_key(
            session=session,
            integration_principal_id=entity_principal.id,
            name="Entity System Key",
            scopes=[entity_scope_tree_name],
            key_kind=APIKeyKind.SYSTEM_INTEGRATION,
            actor_user_id=entity_admin.id,
        )

        system_principal = await auth_instance.integration_principal_service.create_principal(
            session,
            name="Platform Worker Principal",
            description="Platform global benchmark principal",
            scope_kind=IntegrationPrincipalScopeKind.PLATFORM_GLOBAL,
            anchor_entity_id=None,
            inherit_from_tree=False,
            allowed_scopes=[system_global_scope],
            created_by_user_id=superuser.id,
        )
        system_global_api_key, _ = await auth_instance.api_key_service.create_api_key(
            session=session,
            integration_principal_id=system_principal.id,
            name="Platform System Key",
            scopes=[system_global_scope],
            key_kind=APIKeyKind.SYSTEM_INTEGRATION,
            actor_user_id=superuser.id,
        )
        await session.commit()

    return EnterpriseAdminApiKeyQueryContext(
        root_id=root.id,
        department_id=department.id,
        team_id=team.id,
        superuser_id=superuser.id,
        entity_admin_id=entity_admin.id,
        entity_principal_id=entity_principal.id,
        system_principal_id=system_principal.id,
        entity_system_api_key=entity_system_api_key,
        system_global_api_key=system_global_api_key,
        entity_system_scope_tree_name=entity_scope_tree_name,
        entity_system_scope_check_name=entity_scope_check_name,
        system_global_scope=system_global_scope,
        entity_admin_token=create_access_token(
            {"sub": str(entity_admin.id)},
            secret_key=auth_instance.config.secret_key,
            algorithm=auth_instance.config.algorithm,
            audience=auth_instance.config.jwt_audience,
        ),
        superuser_token=create_access_token(
            {"sub": str(superuser.id)},
            secret_key=auth_instance.config.secret_key,
            algorithm=auth_instance.config.algorithm,
            audience=auth_instance.config.jwt_audience,
        ),
    )


async def seed_api_key_mutation_query_context(
    auth_instance: EnterpriseRBAC,
) -> ApiKeyMutationQueryContext:
    unique = uuid.uuid4().hex[:8]
    permission_removed_scope_tree_name = f"contacts{unique}:read_tree"
    membership_scope_tree_name = f"orders{unique}:read_tree"
    direct_role_scope_name = f"billing{unique}:read"

    async with auth_instance.get_session() as session:
        root = await auth_instance.entity_service.create_entity(
            session=session,
            name=f"mutation-bench-root-{unique}",
            display_name="Mutation Bench Root",
            slug=f"mutation-bench-root-{unique}",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        department = await auth_instance.entity_service.create_entity(
            session=session,
            name=f"mutation-bench-department-{unique}",
            display_name="Mutation Bench Department",
            slug=f"mutation-bench-department-{unique}",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="department",
            parent_id=root.id,
        )
        team = await auth_instance.entity_service.create_entity(
            session=session,
            name=f"mutation-bench-team-{unique}",
            display_name="Mutation Bench Team",
            slug=f"mutation-bench-team-{unique}",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=department.id,
        )

        admin = await auth_instance.user_service.create_user(
            session=session,
            email=f"mutation-admin-{unique}@example.com",
            password="TestPass123!",
            first_name="Mutation",
            last_name="Admin",
            is_superuser=True,
            root_entity_id=root.id,
        )
        permission_removed_owner = await auth_instance.user_service.create_user(
            session=session,
            email=f"mutation-owner-permission-{unique}@example.com",
            password="TestPass123!",
            first_name="Permission",
            last_name="Owner",
            root_entity_id=root.id,
        )
        membership_owner = await auth_instance.user_service.create_user(
            session=session,
            email=f"mutation-owner-membership-{unique}@example.com",
            password="TestPass123!",
            first_name="Membership",
            last_name="Owner",
            root_entity_id=root.id,
        )
        direct_role_owner = await auth_instance.user_service.create_user(
            session=session,
            email=f"mutation-owner-direct-{unique}@example.com",
            password="TestPass123!",
            first_name="Direct",
            last_name="Owner",
            root_entity_id=root.id,
        )

        permission_removed_permission = await auth_instance.permission_service.create_permission(
            session,
            name=permission_removed_scope_tree_name,
            display_name=permission_removed_scope_tree_name,
        )
        membership_permission = await auth_instance.permission_service.create_permission(
            session,
            name=membership_scope_tree_name,
            display_name=membership_scope_tree_name,
        )
        direct_role_permission = await auth_instance.permission_service.create_permission(
            session,
            name=direct_role_scope_name,
            display_name=direct_role_scope_name,
        )

        permission_removed_role = await auth_instance.role_service.create_role(
            session=session,
            name=f"mutation-permission-role-{unique}",
            display_name="Mutation Permission Role",
            is_global=False,
            root_entity_id=root.id,
        )
        membership_role = await auth_instance.role_service.create_role(
            session=session,
            name=f"mutation-membership-role-{unique}",
            display_name="Mutation Membership Role",
            is_global=False,
            root_entity_id=root.id,
        )
        direct_user_role = await auth_instance.role_service.create_role(
            session=session,
            name=f"mutation-direct-role-{unique}",
            display_name="Mutation Direct Role",
            is_global=True,
        )

        await auth_instance.role_service.add_permissions(
            session,
            permission_removed_role.id,
            [permission_removed_permission.id],
        )
        await auth_instance.role_service.add_permissions(
            session,
            membership_role.id,
            [membership_permission.id],
        )
        await auth_instance.role_service.add_permissions(
            session,
            direct_user_role.id,
            [direct_role_permission.id],
        )

        await auth_instance.membership_service.add_member(
            session=session,
            entity_id=department.id,
            user_id=permission_removed_owner.id,
            role_ids=[permission_removed_role.id],
            joined_by_id=admin.id,
        )
        await auth_instance.membership_service.add_member(
            session=session,
            entity_id=department.id,
            user_id=membership_owner.id,
            role_ids=[membership_role.id],
            joined_by_id=admin.id,
        )
        await auth_instance.role_service.assign_role_to_user(
            session=session,
            user_id=direct_role_owner.id,
            role_id=direct_user_role.id,
            assigned_by_id=admin.id,
        )

        permission_removed_key, _ = await auth_instance.api_key_service.create_api_key(
            session=session,
            owner_id=permission_removed_owner.id,
            name="Permission Removed Key",
            scopes=[permission_removed_scope_tree_name],
            entity_id=department.id,
            inherit_from_tree=True,
            actor_user_id=permission_removed_owner.id,
        )
        membership_key, _ = await auth_instance.api_key_service.create_api_key(
            session=session,
            owner_id=membership_owner.id,
            name="Membership Removed Key",
            scopes=[membership_scope_tree_name],
            entity_id=department.id,
            inherit_from_tree=True,
            actor_user_id=membership_owner.id,
        )
        direct_role_key, _ = await auth_instance.api_key_service.create_api_key(
            session=session,
            owner_id=direct_role_owner.id,
            name="Direct Role Key",
            scopes=[direct_role_scope_name],
            entity_id=root.id,
            inherit_from_tree=True,
            actor_user_id=direct_role_owner.id,
        )
        await session.commit()

    return ApiKeyMutationQueryContext(
        root_id=root.id,
        department_id=department.id,
        team_id=team.id,
        admin_user_id=admin.id,
        permission_removed_role_id=permission_removed_role.id,
        membership_role_id=membership_role.id,
        direct_user_role_id=direct_user_role.id,
        permission_removed_owner_id=permission_removed_owner.id,
        membership_owner_id=membership_owner.id,
        direct_role_owner_id=direct_role_owner.id,
        permission_removed_key=permission_removed_key,
        membership_key=membership_key,
        direct_role_key=direct_role_key,
        permission_removed_scope_check_name=permission_removed_scope_tree_name.removesuffix("_tree"),
        membership_scope_check_name=membership_scope_tree_name.removesuffix("_tree"),
        direct_role_scope_name=direct_role_scope_name,
    )


@dataclass(frozen=True, slots=True)
class SimpleQueryBudgetContext:
    """
    Seeded SimpleRBAC context for query-count benchmarks.

    Mirrors EnterpriseQueryBudgetContext but without entity hierarchy —
    exercises the flat user -> role -> permission path that SimpleRBAC uses.
    """

    benchmark_user_id: UUID
    admin_user_id: UUID
    role_count: int
    permission_granted_name: str
    permission_missing_name: str
    benchmark_user_token: str
    admin_token: str

    @property
    def admin_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.admin_token}"}

    @property
    def benchmark_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.benchmark_user_token}"}


async def seed_simple_query_budget_context(
    auth_instance: SimpleRBAC,
    *,
    role_count: int = 3,
    extra_permissions_per_role: int = 4,
) -> SimpleQueryBudgetContext:
    """
    Seed a realistic SimpleRBAC dataset for query-count benchmarking.

    Creates:
    - One admin (superuser) and one benchmark user.
    - `role_count` roles, each holding `1 + extra_permissions_per_role` permissions.
    - The benchmark user is assigned every role so `get_user_permissions` has
      to fold together several memberships and permission sets.
    - A `permission_missing_name` the user is not granted, for deny-path checks.
    """
    unique = uuid.uuid4().hex[:8]
    permission_granted_name = f"report{unique}:view"
    permission_missing_name = f"admin{unique}:destroy"

    async with auth_instance.get_session() as session:
        admin = await auth_instance.user_service.create_user(
            session=session,
            email=f"simple-bench-admin-{unique}@example.com",
            password="TestPass123!",
            first_name="Simple",
            last_name="Admin",
            is_superuser=True,
        )
        benchmark_user = await auth_instance.user_service.create_user(
            session=session,
            email=f"simple-bench-user-{unique}@example.com",
            password="TestPass123!",
            first_name="Simple",
            last_name="Bench",
        )

        # Permission that the user WILL have (via role 0)
        await auth_instance.permission_service.create_permission(
            session=session,
            name=permission_granted_name,
            display_name=permission_granted_name,
        )
        # Permission that the user WILL NOT have (deny-path)
        await auth_instance.permission_service.create_permission(
            session=session,
            name=permission_missing_name,
            display_name=permission_missing_name,
        )

        role_ids: list[UUID] = []
        for role_index in range(role_count):
            role_permission_names: list[str] = []
            for perm_index in range(extra_permissions_per_role):
                perm_name = f"mod{role_index}{unique}:act{perm_index}"
                await auth_instance.permission_service.create_permission(
                    session=session,
                    name=perm_name,
                    display_name=perm_name,
                )
                role_permission_names.append(perm_name)
            if role_index == 0:
                role_permission_names.append(permission_granted_name)

            role = await auth_instance.role_service.create_role(
                session=session,
                name=f"simple-bench-role-{role_index}-{unique}",
                display_name=f"Simple Bench Role {role_index}",
                permission_names=role_permission_names,
                is_global=True,
            )
            await auth_instance.role_service.assign_role_to_user(
                session=session,
                user_id=benchmark_user.id,
                role_id=role.id,
            )
            role_ids.append(role.id)

        await session.commit()

    benchmark_token = create_access_token(
        data={"sub": str(benchmark_user.id)},
        secret_key=auth_instance.config.secret_key,
        algorithm=auth_instance.config.algorithm,
    )
    admin_token = create_access_token(
        data={"sub": str(admin.id)},
        secret_key=auth_instance.config.secret_key,
        algorithm=auth_instance.config.algorithm,
    )

    return SimpleQueryBudgetContext(
        benchmark_user_id=benchmark_user.id,
        admin_user_id=admin.id,
        role_count=len(role_ids),
        permission_granted_name=permission_granted_name,
        permission_missing_name=permission_missing_name,
        benchmark_user_token=benchmark_token,
        admin_token=admin_token,
    )
