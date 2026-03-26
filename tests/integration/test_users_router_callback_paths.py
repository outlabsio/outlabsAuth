import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import HTTPException

import outlabs_auth.routers.users as users_router_module
from outlabs_auth import EnterpriseRBAC
from outlabs_auth.models.sql.enums import EntityClass, MembershipStatus, RoleScope, UserStatus
from outlabs_auth.models.sql.user_role_membership import UserRoleMembership
from outlabs_auth.routers import get_users_router
from outlabs_auth.schemas.user import (
    AdminResetPasswordRequest,
    ChangePasswordRequest,
    UserCreateRequest,
    UserStatusUpdateRequest,
    UserUpdateRequest,
)
from outlabs_auth.schemas.user_role_membership import AssignRoleRequest


class DummyObs:
    def __init__(self, user_id: str | None) -> None:
        self.user_id = user_id
        self.events: list[tuple[str, dict]] = []
        self.errors: list[tuple[str, str, dict]] = []

    def log_event(self, event: str, **fields) -> None:
        self.events.append((event, fields))

    def log_500_error(self, exception: Exception, **extra) -> None:
        self.errors.append((type(exception).__name__, str(exception), extra))


class DummyObservability:
    def __init__(self) -> None:
        self.records: list[tuple[str, dict]] = []
        self.logger = SimpleNamespace(info=self._info)

    def _info(self, event: str, **fields) -> None:
        self.records.append((event, fields))

    async def shutdown(self) -> None:
        return None


def _suffix() -> str:
    return uuid.uuid4().hex[:8]


def _http_raiser(status_code: int, detail: str):
    async def _raiser(*args, **kwargs):
        raise HTTPException(status_code=status_code, detail=detail)

    return _raiser


def _runtime_raiser(message: str):
    async def _raiser(*args, **kwargs):
        raise RuntimeError(message)

    return _raiser


async def _return_false(*args, **kwargs):
    return False


def _endpoint(router, path: str, method: str):
    for route in router.routes:
        if route.path == path and method in route.methods:
            return route.endpoint
    raise AssertionError(f"Route not found for {method} {path}")


async def _create_root(auth: EnterpriseRBAC, session, *, label: str):
    slug = f"{label}-{_suffix()}"
    return await auth.entity_service.create_entity(
        session=session,
        name=slug,
        display_name=label.title(),
        slug=slug,
        entity_class=EntityClass.STRUCTURAL,
        entity_type="organization",
    )


async def _create_child(auth: EnterpriseRBAC, session, *, parent_id, label: str):
    slug = f"{label}-{_suffix()}"
    return await auth.entity_service.create_entity(
        session=session,
        name=slug,
        display_name=label.title(),
        slug=slug,
        entity_class=EntityClass.STRUCTURAL,
        entity_type="team",
        parent_id=parent_id,
    )


async def _create_user(
    auth: EnterpriseRBAC,
    session,
    *,
    email_prefix: str,
    password: str = "TestPass123!",
    root_entity_id=None,
    is_superuser: bool = False,
):
    return await auth.user_service.create_user(
        session=session,
        email=f"{email_prefix}-{_suffix()}@example.com",
        password=password,
        first_name="Test",
        last_name="User",
        root_entity_id=root_entity_id,
        is_superuser=is_superuser,
    )


async def _grant_user_read_permission(
    auth: EnterpriseRBAC,
    session,
    *,
    actor_user_id,
    target_user_id,
) -> None:
    existing_permission = await auth.permission_service.get_permission_by_name(session, "user:read")
    if not existing_permission:
        await auth.permission_service.create_permission(
            session,
            name="user:read",
            display_name="User Read",
        )
    role = await auth.role_service.create_role(
        session=session,
        name=f"user_read_role_{_suffix()}",
        display_name="User Read Role",
        permission_names=["user:read"],
        is_global=True,
    )
    await auth.role_service.assign_role_to_user(
        session,
        user_id=target_user_id,
        role_id=role.id,
        assigned_by_id=actor_user_id,
    )


@pytest_asyncio.fixture
async def auth_instance(test_engine) -> EnterpriseRBAC:
    auth = EnterpriseRBAC(
        engine=test_engine,
        secret_key="test-secret-key-do-not-use-in-production-12345678",
        access_token_expire_minutes=60,
        enable_token_cleanup=False,
    )
    await auth.initialize()
    auth.observability = DummyObservability()
    yield auth
    await auth.shutdown()


@pytest_asyncio.fixture
async def users_router(auth_instance: EnterpriseRBAC):
    return get_users_router(auth_instance, prefix="/v1/users")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_users_router_callback_identity_and_cross_root_access_paths(
    auth_instance: EnterpriseRBAC,
    users_router,
):
    list_users = _endpoint(users_router, "/v1/users/", "GET")
    get_user = _endpoint(users_router, "/v1/users/{user_id}", "GET")

    async with auth_instance.get_session() as session:
        root_a = await _create_root(auth_instance, session, label="root-a")
        root_b = await _create_root(auth_instance, session, label="root-b")
        actor = await _create_user(
            auth_instance,
            session,
            email_prefix="actor-a",
            password="ActorPass123!",
            root_entity_id=root_a.id,
        )
        other_root_user = await _create_user(
            auth_instance,
            session,
            email_prefix="root-b-user",
            root_entity_id=root_b.id,
        )

        with pytest.raises(HTTPException) as exc:
            await list_users(
                page=1,
                limit=20,
                search=None,
                user_status=None,
                is_superuser=None,
                root_entity_id=None,
                session=session,
                obs=DummyObs(None),
            )
        assert exc.value.status_code == 401
        assert exc.value.detail == "Not authenticated"

        with pytest.raises(HTTPException) as exc:
            await list_users(
                page=1,
                limit=20,
                search=None,
                user_status=None,
                is_superuser=None,
                root_entity_id=None,
                session=session,
                obs=DummyObs("not-a-uuid"),
            )
        assert exc.value.status_code == 401
        assert exc.value.detail == "Invalid user identity"

        with pytest.raises(HTTPException) as exc:
            await list_users(
                page=1,
                limit=20,
                search=None,
                user_status=None,
                is_superuser=None,
                root_entity_id=None,
                session=session,
                obs=DummyObs(str(uuid.uuid4())),
            )
        assert exc.value.status_code == 401
        assert exc.value.detail == "User not found"

        cross_root = await get_user(
            user_id=other_root_user.id,
            session=session,
            obs=DummyObs(str(actor.id)),
        )
        assert cross_root.id == str(other_root_user.id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_users_router_callback_create_list_and_self_service_paths(
    auth_instance: EnterpriseRBAC,
    users_router,
):
    create_user = _endpoint(users_router, "/v1/users/", "POST")
    list_users = _endpoint(users_router, "/v1/users/", "GET")
    update_me = _endpoint(users_router, "/v1/users/me", "PATCH")
    change_password = _endpoint(users_router, "/v1/users/me/change-password", "POST")

    async with auth_instance.get_session() as session:
        root_a = await _create_root(auth_instance, session, label="team-alpha")
        actor = await _create_user(
            auth_instance,
            session,
            email_prefix="scoped-actor",
            password="ActorPass123!",
            root_entity_id=root_a.id,
        )

        with pytest.raises(HTTPException) as exc:
            await create_user(
                data=UserCreateRequest(
                    email=f"super-{_suffix()}@example.com",
                    password="NewUser123!",
                    first_name="Super",
                    last_name="User",
                    is_superuser=True,
                ),
                session=session,
                obs=DummyObs(str(actor.id)),
            )
        assert exc.value.status_code == 403

        created = await create_user(
            data=UserCreateRequest(
                email=f"created-{_suffix()}@example.com",
                password="Created123!",
                first_name="Created",
                last_name="Person",
                root_entity_id=str(root_a.id),
            ),
            session=session,
            obs=DummyObs(str(actor.id)),
        )
        assert created.root_entity_id == str(root_a.id)
        assert created.root_entity_name == root_a.display_name

        created_db = await auth_instance.user_service.get_user_by_email(session, created.email)
        assert created_db is not None
        assert created_db.root_entity_id == root_a.id

        with pytest.raises(HTTPException) as exc:
            await list_users(
                page=1,
                limit=20,
                search=None,
                user_status="not-a-real-status",
                is_superuser=None,
                root_entity_id=None,
                session=session,
                obs=DummyObs(str(actor.id)),
            )
        assert exc.value.status_code == 400
        assert "Invalid status" in exc.value.detail

        page = await list_users(
            page=1,
            limit=20,
            search=None,
            user_status="active",
            is_superuser=False,
            root_entity_id=root_a.id,
            session=session,
            obs=DummyObs(str(actor.id)),
        )
        assert created.id in {item.id for item in page.items}
        assert all(item.is_superuser is False for item in page.items)

        search_page = await list_users(
            page=1,
            limit=20,
            search="Created",
            user_status="active",
            is_superuser=False,
            root_entity_id=root_a.id,
            session=session,
            obs=DummyObs(str(actor.id)),
        )
        assert [item.id for item in search_page.items] == [created.id]

        obs = DummyObs(str(actor.id))
        updated_me = await update_me(
            data=UserUpdateRequest(first_name="Scoped", last_name="Actor"),
            session=session,
            obs=obs,
        )
        assert updated_me.first_name == "Scoped"
        assert updated_me.last_name == "Actor"
        assert obs.events[0][0] == "user_updated"

        changed = await change_password(
            data=ChangePasswordRequest(
                current_password="ActorPass123!",
                new_password="ActorPass456!",
            ),
            session=session,
            obs=DummyObs(str(actor.id)),
        )
        assert changed is None

        _, tokens = await auth_instance.auth_service.login(
            session,
            email=actor.email,
            password="ActorPass456!",
        )
        assert tokens.access_token
        assert any(event == "user_created" for event, _fields in auth_instance.observability.records)
        assert any(event == "user_password_changed" for event, _fields in auth_instance.observability.records)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_users_router_callback_crud_status_delete_and_invite_paths(
    auth_instance: EnterpriseRBAC,
    users_router,
):
    get_user = _endpoint(users_router, "/v1/users/{user_id}", "GET")
    update_user = _endpoint(users_router, "/v1/users/{user_id}", "PATCH")
    admin_reset_password = _endpoint(users_router, "/v1/users/{user_id}/password", "PATCH")
    update_status = _endpoint(users_router, "/v1/users/{user_id}/status", "PATCH")
    restore_user = _endpoint(users_router, "/v1/users/{user_id}/restore", "POST")
    delete_user = _endpoint(users_router, "/v1/users/{user_id}", "DELETE")
    resend_invite = _endpoint(users_router, "/v1/users/{user_id}/resend-invite", "POST")

    async with auth_instance.get_session() as session:
        root_a = await _create_root(auth_instance, session, label="crud-root")
        actor = await _create_user(
            auth_instance,
            session,
            email_prefix="crud-actor",
            password="ActorPass123!",
            root_entity_id=root_a.id,
        )
        target = await _create_user(
            auth_instance,
            session,
            email_prefix="crud-target",
            password="TargetPass123!",
            root_entity_id=root_a.id,
        )

        fetched = await get_user(
            user_id=target.id,
            session=session,
            obs=DummyObs(str(actor.id)),
        )
        assert fetched.id == str(target.id)

        updated = await update_user(
            user_id=target.id,
            data=UserUpdateRequest(first_name="Updated", last_name="Target"),
            session=session,
            obs=DummyObs(str(actor.id)),
        )
        assert updated.first_name == "Updated"
        assert updated.last_name == "Target"

        reset_response = await admin_reset_password(
            user_id=target.id,
            data=AdminResetPasswordRequest(new_password="ResetPass123!"),
            session=session,
            obs=DummyObs(str(actor.id)),
        )
        assert reset_response is None
        _, tokens = await auth_instance.auth_service.login(
            session,
            email=target.email,
            password="ResetPass123!",
        )
        assert tokens.refresh_token

        suspended_until = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
        status_response = await update_status(
            user_id=target.id,
            data=UserStatusUpdateRequest(
                status="suspended",
                suspended_until=suspended_until,
                reason="maintenance",
            ),
            session=session,
            obs=DummyObs(str(actor.id)),
        )
        assert status_response.status == "suspended"
        assert status_response.suspended_until is not None

        with pytest.raises(HTTPException) as exc:
            await update_status(
                user_id=target.id,
                data=UserStatusUpdateRequest.model_construct(
                    status="nope",
                    suspended_until=None,
                    reason=None,
                ),
                session=session,
                obs=DummyObs(str(actor.id)),
            )
        assert exc.value.status_code == 400
        assert "Invalid status" in exc.value.detail

        with pytest.raises(HTTPException) as exc:
            await update_status(
                user_id=target.id,
                data=UserStatusUpdateRequest.model_construct(
                    status="deleted",
                    suspended_until=None,
                    reason=None,
                ),
                session=session,
                obs=DummyObs(str(actor.id)),
            )
        assert exc.value.status_code == 400
        assert "Cannot set status to 'deleted'" in exc.value.detail

        with pytest.raises(HTTPException) as exc:
            await update_status(
                user_id=target.id,
                data=UserStatusUpdateRequest.model_construct(
                    status="suspended",
                    suspended_until="not-an-iso-datetime",
                    reason=None,
                ),
                session=session,
                obs=DummyObs(str(actor.id)),
            )
        assert exc.value.status_code == 400
        assert "Invalid suspended_until format" in exc.value.detail

        invited, _ = await auth_instance.user_service.invite_user(
            session,
            email=f"invitee-{_suffix()}@example.com",
            first_name="Invited",
            last_name="User",
            invited_by_id=actor.id,
            root_entity_id=root_a.id,
        )
        resent = await resend_invite(
            user_id=invited.id,
            session=session,
            obs=DummyObs(str(actor.id)),
        )
        assert resent.id == str(invited.id)
        assert resent.status == "invited"

        doomed = await _create_user(
            auth_instance,
            session,
            email_prefix="delete-me",
            root_entity_id=root_a.id,
        )
        deleted = await delete_user(
            user_id=doomed.id,
            session=session,
            obs=DummyObs(str(actor.id)),
        )
        assert deleted is None
        retained = await auth_instance.user_service.get_user_by_id(session, doomed.id)
        assert retained is not None
        assert retained.status == UserStatus.DELETED
        assert retained.deleted_at is not None

        with pytest.raises(HTTPException) as exc:
            await update_status(
                user_id=doomed.id,
                data=UserStatusUpdateRequest(status="active"),
                session=session,
                obs=DummyObs(str(actor.id)),
            )
        assert exc.value.status_code == 400
        assert "restore endpoint" in exc.value.detail

        restored = await restore_user(
            user_id=doomed.id,
            session=session,
            obs=DummyObs(str(actor.id)),
        )
        assert restored.id == str(doomed.id)
        assert restored.status == "active"
        assert restored.deleted_at is None

        logged_events = {event for event, _fields in auth_instance.observability.records}
        assert {"admin_password_reset", "user_status_changed", "invite_resent", "user_deleted", "user_restored"} <= logged_events


@pytest.mark.integration
@pytest.mark.asyncio
async def test_users_router_callback_role_and_permission_paths(
    auth_instance: EnterpriseRBAC,
    users_router,
):
    assign_role = _endpoint(users_router, "/v1/users/{user_id}/roles", "POST")
    get_roles = _endpoint(users_router, "/v1/users/{user_id}/roles", "GET")
    get_memberships = _endpoint(users_router, "/v1/users/{user_id}/role-memberships", "GET")
    remove_role = _endpoint(users_router, "/v1/users/{user_id}/roles/{role_id}", "DELETE")
    get_permissions = _endpoint(users_router, "/v1/users/{user_id}/permissions", "GET")

    async with auth_instance.get_session() as session:
        root_a = await _create_root(auth_instance, session, label="roles-root")
        child_a = await _create_child(
            auth_instance,
            session,
            parent_id=root_a.id,
            label="roles-child",
        )
        actor = await _create_user(
            auth_instance,
            session,
            email_prefix="role-actor",
            password="ActorPass123!",
            root_entity_id=root_a.id,
        )
        await _grant_user_read_permission(
            auth_instance,
            session,
            actor_user_id=actor.id,
            target_user_id=actor.id,
        )
        target = await _create_user(
            auth_instance,
            session,
            email_prefix="role-target",
            root_entity_id=root_a.id,
        )

        permission = await auth_instance.permission_service.create_permission(
            session,
            name=f"reports:{_suffix()}",
            display_name="Reports View",
        )
        direct_role = await auth_instance.role_service.create_role(
            session=session,
            name=f"direct_role_{_suffix()}",
            display_name="Direct Role",
            permission_names=[permission.name],
            is_global=True,
        )

        assigned = await assign_role(
            user_id=target.id,
            data=AssignRoleRequest(role_id=str(direct_role.id)),
            session=session,
            obs=DummyObs(str(actor.id)),
        )
        assert assigned.role_id == str(direct_role.id)
        assert assigned.status == MembershipStatus.ACTIVE

        roles = await get_roles(
            user_id=target.id,
            include_inactive=False,
            session=session,
            obs=DummyObs(str(actor.id)),
        )
        assert [role.id for role in roles] == [str(direct_role.id)]

        permission_sources = await get_permissions(
            user_id=target.id,
            session=session,
            obs=DummyObs(str(actor.id)),
        )
        assert len(permission_sources) == 1
        assert permission_sources[0].permission.name == permission.name
        assert permission_sources[0].source_name == direct_role.name

        removed = await remove_role(
            user_id=target.id,
            role_id=direct_role.id,
            session=session,
            obs=DummyObs(str(actor.id)),
        )
        assert removed is None

        inactive_memberships = await get_memberships(
            user_id=target.id,
            include_inactive=True,
            session=session,
            obs=DummyObs(str(actor.id)),
        )
        assert len(inactive_memberships) == 1
        assert inactive_memberships[0].role.id == str(direct_role.id)
        assert inactive_memberships[0].revoked_by_id == str(actor.id)

        entity_role = await auth_instance.role_service.create_role(
            session=session,
            name=f"entity_role_{_suffix()}",
            display_name="Entity Role",
            permission_names=[permission.name],
            is_global=False,
            root_entity_id=root_a.id,
            scope_entity_id=child_a.id,
            scope=RoleScope.ENTITY_ONLY,
        )
        scoped_user = await _create_user(
            auth_instance,
            session,
            email_prefix="scoped-role-user",
            root_entity_id=root_a.id,
        )
        session.add(
            UserRoleMembership(
                user_id=scoped_user.id,
                role_id=entity_role.id,
                assigned_by_id=actor.id,
                status=MembershipStatus.ACTIVE,
            )
        )
        await session.flush()

        scoped_memberships = await get_memberships(
            user_id=scoped_user.id,
            include_inactive=False,
            session=session,
            obs=DummyObs(str(actor.id)),
        )
        assert len(scoped_memberships) == 1
        assert scoped_memberships[0].role.root_entity_name == root_a.display_name
        assert scoped_memberships[0].role.scope_entity_name == child_a.display_name
        assert scoped_memberships[0].role.scope.value == "entity_only"

        membership_permission = await auth_instance.permission_service.create_permission(
            session,
            name=f"membership_reports:{_suffix()}",
            display_name="Membership Reports View",
        )
        membership_role = await auth_instance.role_service.create_role(
            session=session,
            name=f"membership_role_{_suffix()}",
            display_name="Membership Role",
            permission_names=[membership_permission.name],
            is_global=False,
            root_entity_id=root_a.id,
            scope_entity_id=child_a.id,
            scope=RoleScope.ENTITY_ONLY,
        )
        membership_user = await _create_user(
            auth_instance,
            session,
            email_prefix="membership-role-user",
            root_entity_id=root_a.id,
        )
        await auth_instance.membership_service.add_member(
            session,
            entity_id=child_a.id,
            user_id=membership_user.id,
            role_ids=[membership_role.id],
            joined_by_id=actor.id,
        )

        membership_permission_sources = await get_permissions(
            user_id=membership_user.id,
            session=session,
            obs=DummyObs(str(actor.id)),
        )
        assert len(membership_permission_sources) == 1
        assert membership_permission_sources[0].permission.name == membership_permission.name
        assert membership_permission_sources[0].source_name == membership_role.name

        self_permission_sources = await get_permissions(
            user_id=membership_user.id,
            session=session,
            obs=DummyObs(str(membership_user.id)),
        )
        assert len(self_permission_sources) == 1
        assert self_permission_sources[0].permission.name == membership_permission.name
        assert self_permission_sources[0].source_name == membership_role.name

        with pytest.raises(HTTPException) as exc:
            await get_permissions(
                user_id=actor.id,
                session=session,
                obs=DummyObs(str(membership_user.id)),
            )
        assert exc.value.status_code == 403
        assert exc.value.detail == "Not enough permissions"

        logged_events = {event for event, _fields in auth_instance.observability.records}
        assert {"role_assigned", "role_revoked"} <= logged_events


@pytest.mark.integration
@pytest.mark.asyncio
async def test_users_router_callback_remaining_http_error_paths(
    auth_instance: EnterpriseRBAC,
    users_router,
    monkeypatch,
):
    update_me = _endpoint(users_router, "/v1/users/me", "PATCH")
    change_password = _endpoint(users_router, "/v1/users/me/change-password", "POST")
    get_user = _endpoint(users_router, "/v1/users/{user_id}", "GET")
    update_user = _endpoint(users_router, "/v1/users/{user_id}", "PATCH")
    admin_reset_password = _endpoint(users_router, "/v1/users/{user_id}/password", "PATCH")
    delete_user = _endpoint(users_router, "/v1/users/{user_id}", "DELETE")
    resend_invite = _endpoint(users_router, "/v1/users/{user_id}/resend-invite", "POST")
    get_roles = _endpoint(users_router, "/v1/users/{user_id}/roles", "GET")
    get_memberships = _endpoint(users_router, "/v1/users/{user_id}/role-memberships", "GET")
    assign_role = _endpoint(users_router, "/v1/users/{user_id}/roles", "POST")
    remove_role = _endpoint(users_router, "/v1/users/{user_id}/roles/{role_id}", "DELETE")
    get_permissions = _endpoint(users_router, "/v1/users/{user_id}/permissions", "GET")

    async with auth_instance.get_session() as session:
        root = await _create_root(auth_instance, session, label="http-root")
        actor = await _create_user(
            auth_instance,
            session,
            email_prefix="http-actor",
            password="ActorPass123!",
            root_entity_id=root.id,
        )
        target = await _create_user(
            auth_instance,
            session,
            email_prefix="http-target",
            root_entity_id=root.id,
        )

        with monkeypatch.context() as m:
            m.setattr(auth_instance.user_service, "update_user_fields", _http_raiser(409, "email conflict"))
            with pytest.raises(HTTPException) as exc:
                await update_me(
                    data=UserUpdateRequest(first_name="Conflict"),
                    session=session,
                    obs=DummyObs(str(actor.id)),
                )
            assert exc.value.status_code == 409

        with monkeypatch.context() as m:
            m.setattr(
                auth_instance.user_service,
                "change_password_with_current",
                _http_raiser(400, "bad current password"),
            )
            with pytest.raises(HTTPException) as exc:
                await change_password(
                    data=ChangePasswordRequest(
                        current_password="ActorPass123!",
                        new_password="ActorPass456!",
                    ),
                    session=session,
                    obs=DummyObs(str(actor.id)),
                )
            assert exc.value.status_code == 400

        missing_user_id = uuid.uuid4()

        with pytest.raises(HTTPException) as exc:
            await get_user(
                user_id=missing_user_id,
                session=session,
                obs=DummyObs(str(actor.id)),
            )
        assert exc.value.status_code == 404

        with pytest.raises(HTTPException) as exc:
            await update_user(
                user_id=missing_user_id,
                data=UserUpdateRequest(first_name="Missing"),
                session=session,
                obs=DummyObs(str(actor.id)),
            )
        assert exc.value.status_code == 404

        with pytest.raises(HTTPException) as exc:
            await admin_reset_password(
                user_id=missing_user_id,
                data=AdminResetPasswordRequest(new_password="ResetPass123!"),
                session=session,
                obs=DummyObs(str(actor.id)),
            )
        assert exc.value.status_code == 404

        with pytest.raises(HTTPException) as exc:
            await resend_invite(
                user_id=missing_user_id,
                session=session,
                obs=DummyObs(str(actor.id)),
            )
        assert exc.value.status_code == 404

        with pytest.raises(HTTPException) as exc:
            await get_roles(
                user_id=missing_user_id,
                include_inactive=False,
                session=session,
                obs=DummyObs(str(actor.id)),
            )
        assert exc.value.status_code == 404

        with pytest.raises(HTTPException) as exc:
            await get_memberships(
                user_id=missing_user_id,
                include_inactive=False,
                session=session,
                obs=DummyObs(str(actor.id)),
            )
        assert exc.value.status_code == 404

        with pytest.raises(HTTPException) as exc:
            await get_permissions(
                user_id=missing_user_id,
                session=session,
                obs=DummyObs(str(actor.id)),
            )
        assert exc.value.status_code == 404

        missing_role_id = str(uuid.uuid4())
        with pytest.raises(HTTPException) as exc:
            await assign_role(
                user_id=target.id,
                data=AssignRoleRequest(role_id=missing_role_id),
                session=session,
                obs=DummyObs(str(actor.id)),
            )
        assert exc.value.status_code == 404
        assert exc.value.detail == "Role not found"

        with pytest.raises(HTTPException) as exc:
            await remove_role(
                user_id=target.id,
                role_id=uuid.uuid4(),
                session=session,
                obs=DummyObs(str(actor.id)),
            )
        assert exc.value.status_code == 404
        assert exc.value.detail == "User does not have this role assigned"

        doomed = await _create_user(
            auth_instance,
            session,
            email_prefix="http-doomed",
            root_entity_id=root.id,
        )
        with monkeypatch.context() as m:
            m.setattr(auth_instance.user_service, "delete_user", _return_false)
            with pytest.raises(HTTPException) as exc:
                await delete_user(
                    user_id=doomed.id,
                    session=session,
                    obs=DummyObs(str(actor.id)),
                )
            assert exc.value.status_code == 404
            assert exc.value.detail == "User not found"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_users_router_callback_remaining_generic_error_paths(
    auth_instance: EnterpriseRBAC,
    users_router,
    monkeypatch,
):
    create_user = _endpoint(users_router, "/v1/users/", "POST")
    list_users = _endpoint(users_router, "/v1/users/", "GET")
    update_me = _endpoint(users_router, "/v1/users/me", "PATCH")
    change_password = _endpoint(users_router, "/v1/users/me/change-password", "POST")
    get_user = _endpoint(users_router, "/v1/users/{user_id}", "GET")
    update_user = _endpoint(users_router, "/v1/users/{user_id}", "PATCH")
    admin_reset_password = _endpoint(users_router, "/v1/users/{user_id}/password", "PATCH")
    update_status = _endpoint(users_router, "/v1/users/{user_id}/status", "PATCH")
    delete_user = _endpoint(users_router, "/v1/users/{user_id}", "DELETE")
    resend_invite = _endpoint(users_router, "/v1/users/{user_id}/resend-invite", "POST")
    get_roles = _endpoint(users_router, "/v1/users/{user_id}/roles", "GET")
    get_memberships = _endpoint(users_router, "/v1/users/{user_id}/role-memberships", "GET")
    assign_role = _endpoint(users_router, "/v1/users/{user_id}/roles", "POST")
    remove_role = _endpoint(users_router, "/v1/users/{user_id}/roles/{role_id}", "DELETE")
    get_permissions = _endpoint(users_router, "/v1/users/{user_id}/permissions", "GET")

    async with auth_instance.get_session() as session:
        root = await _create_root(auth_instance, session, label="generic-root")
        actor = await _create_user(
            auth_instance,
            session,
            email_prefix="generic-actor",
            password="ActorPass123!",
            root_entity_id=root.id,
        )
        await _grant_user_read_permission(
            auth_instance,
            session,
            actor_user_id=actor.id,
            target_user_id=actor.id,
        )
        target = await _create_user(
            auth_instance,
            session,
            email_prefix="generic-target",
            root_entity_id=root.id,
        )

        permission = await auth_instance.permission_service.create_permission(
            session,
            name=f"generic:{_suffix()}",
            display_name="Generic Permission",
        )
        role = await auth_instance.role_service.create_role(
            session=session,
            name=f"generic_role_{_suffix()}",
            display_name="Generic Role",
            permission_names=[permission.name],
            is_global=True,
        )
        await auth_instance.role_service.assign_role_to_user(
            session,
            user_id=target.id,
            role_id=role.id,
            assigned_by_id=actor.id,
        )

        invited, _ = await auth_instance.user_service.invite_user(
            session,
            email=f"generic-invite-{_suffix()}@example.com",
            invited_by_id=actor.id,
            root_entity_id=root.id,
        )

        obs = DummyObs(str(actor.id))
        with monkeypatch.context() as m:
            m.setattr(auth_instance.user_service, "on_after_register", _runtime_raiser("create exploded"))
            with pytest.raises(RuntimeError):
                await create_user(
                    data=UserCreateRequest(
                        email=f"generic-created-{_suffix()}@example.com",
                        password="Created123!",
                        first_name="Generic",
                        last_name="Created",
                        root_entity_id=str(root.id),
                    ),
                    session=session,
                    obs=obs,
                )
        assert obs.errors[-1][0] == "RuntimeError"

        obs = DummyObs(str(actor.id))
        with monkeypatch.context() as m:
            m.setattr(auth_instance.user_service, "list_users", _runtime_raiser("list exploded"))
            with pytest.raises(RuntimeError):
                await list_users(
                    page=1,
                    limit=20,
                    search=None,
                    user_status=None,
                    is_superuser=None,
                    root_entity_id=None,
                    session=session,
                    obs=obs,
                )
        assert obs.errors[-1][0] == "RuntimeError"

        obs = DummyObs(str(actor.id))
        with monkeypatch.context() as m:
            m.setattr(auth_instance.user_service, "update_user_fields", _runtime_raiser("update me exploded"))
            with pytest.raises(RuntimeError):
                await update_me(
                    data=UserUpdateRequest(first_name="Boom"),
                    session=session,
                    obs=obs,
                )
        assert obs.errors[-1][0] == "RuntimeError"

        obs = DummyObs(str(actor.id))
        with monkeypatch.context() as m:
            m.setattr(
                auth_instance.user_service,
                "change_password_with_current",
                _runtime_raiser("change password exploded"),
            )
            with pytest.raises(RuntimeError):
                await change_password(
                    data=ChangePasswordRequest(
                        current_password="ActorPass123!",
                        new_password="ActorPass456!",
                    ),
                    session=session,
                    obs=obs,
                )
        assert obs.errors[-1][0] == "RuntimeError"

        async def _build_fail(*args, **kwargs):
            raise RuntimeError("build exploded")

        obs = DummyObs(str(actor.id))
        with monkeypatch.context() as m:
            m.setattr(users_router_module, "build_user_response_async", _build_fail)
            with pytest.raises(RuntimeError):
                await get_user(
                    user_id=target.id,
                    session=session,
                    obs=obs,
                )
        assert obs.errors[-1][0] == "RuntimeError"

        obs = DummyObs(str(actor.id))
        with monkeypatch.context() as m:
            m.setattr(auth_instance.user_service, "update_user_fields", _runtime_raiser("update user exploded"))
            with pytest.raises(RuntimeError):
                await update_user(
                    user_id=target.id,
                    data=UserUpdateRequest(first_name="Updated"),
                    session=session,
                    obs=obs,
                )
        assert obs.errors[-1][0] == "RuntimeError"

        obs = DummyObs(str(actor.id))
        with monkeypatch.context() as m:
            m.setattr(auth_instance.user_service, "change_password", _runtime_raiser("admin reset exploded"))
            with pytest.raises(RuntimeError):
                await admin_reset_password(
                    user_id=target.id,
                    data=AdminResetPasswordRequest(new_password="Reset123!"),
                    session=session,
                    obs=obs,
                )
        assert obs.errors[-1][0] == "RuntimeError"

        obs = DummyObs(str(actor.id))
        with monkeypatch.context() as m:
            m.setattr(auth_instance.user_service, "update_user_status", _runtime_raiser("status exploded"))
            with pytest.raises(RuntimeError):
                await update_status(
                    user_id=target.id,
                    data=UserStatusUpdateRequest(status="active"),
                    session=session,
                    obs=obs,
                )
        assert obs.errors[-1][0] == "RuntimeError"

        doomed = await _create_user(
            auth_instance,
            session,
            email_prefix="generic-doomed",
            root_entity_id=root.id,
        )
        obs = DummyObs(str(actor.id))
        with monkeypatch.context() as m:
            m.setattr(auth_instance.user_service, "on_after_delete", _runtime_raiser("delete exploded"))
            with pytest.raises(RuntimeError):
                await delete_user(
                    user_id=doomed.id,
                    session=session,
                    obs=obs,
                )
        assert obs.errors[-1][0] == "RuntimeError"

        obs = DummyObs(str(actor.id))
        with monkeypatch.context() as m:
            m.setattr(auth_instance.user_service, "on_after_invite", _runtime_raiser("resend exploded"))
            with pytest.raises(RuntimeError):
                await resend_invite(
                    user_id=invited.id,
                    session=session,
                    obs=obs,
                )
        assert obs.errors[-1][0] == "RuntimeError"

        obs = DummyObs(str(actor.id))
        with monkeypatch.context() as m:
            m.setattr(auth_instance.role_service, "get_user_roles", _runtime_raiser("roles exploded"))
            with pytest.raises(RuntimeError):
                await get_roles(
                    user_id=target.id,
                    include_inactive=False,
                    session=session,
                    obs=obs,
                )
        assert obs.errors[-1][0] == "RuntimeError"

        obs = DummyObs(str(actor.id))
        with monkeypatch.context() as m:
            m.setattr(
                auth_instance.role_service,
                "get_user_role_memberships",
                _runtime_raiser("memberships exploded"),
            )
            with pytest.raises(RuntimeError):
                await get_memberships(
                    user_id=target.id,
                    include_inactive=False,
                    session=session,
                    obs=obs,
                )
        assert obs.errors[-1][0] == "RuntimeError"

        second_role = await auth_instance.role_service.create_role(
            session=session,
            name=f"second_role_{_suffix()}",
            display_name="Second Role",
            is_global=True,
        )
        obs = DummyObs(str(actor.id))
        with monkeypatch.context() as m:
            m.setattr(auth_instance.role_service, "assign_role_to_user", _runtime_raiser("assign exploded"))
            with pytest.raises(RuntimeError):
                await assign_role(
                    user_id=target.id,
                    data=AssignRoleRequest(role_id=str(second_role.id)),
                    session=session,
                    obs=obs,
                )
        assert obs.errors[-1][0] == "RuntimeError"

        obs = DummyObs(str(actor.id))
        with monkeypatch.context() as m:
            m.setattr(auth_instance.role_service, "revoke_role_from_user", _runtime_raiser("revoke exploded"))
            with pytest.raises(RuntimeError):
                await remove_role(
                    user_id=target.id,
                    role_id=role.id,
                    session=session,
                    obs=obs,
                )
        assert obs.errors[-1][0] == "RuntimeError"

        obs = DummyObs(str(actor.id))
        with monkeypatch.context() as m:
            m.setattr(
                auth_instance.permission_service,
                "get_permissions_for_role",
                _runtime_raiser("permissions exploded"),
            )
            with pytest.raises(RuntimeError):
                await get_permissions(
                    user_id=target.id,
                    session=session,
                    obs=obs,
                )
        assert obs.errors[-1][0] == "RuntimeError"
