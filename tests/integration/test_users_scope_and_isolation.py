"""
DD-056 — tenant isolation on user-management routes.

Mirrors test_roles_scope_and_contract.py::test_scoped_admin_role_management_is_limited_to_access_scope
for the users router: scoped admins only reach users inside their own trees,
out-of-scope targets are hidden as 404, system-wide roles grant explicit
global scope, and the enforce_user_scope flag / SimpleRBAC restore the
unscoped behavior.
"""

import uuid

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from outlabs_auth import EnterpriseRBAC, SimpleRBAC
from outlabs_auth.fastapi import register_exception_handlers
from outlabs_auth.models.sql.enums import EntityClass
from outlabs_auth.routers import get_users_router
from outlabs_auth.utils.jwt import create_access_token

USER_PERMISSIONS = ("user:read", "user:update", "user:delete")


def _suffix() -> str:
    return uuid.uuid4().hex[:8]


def _make_app(auth) -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app, debug=True)
    app.include_router(get_users_router(auth, prefix="/v1/users"))
    return app


def _client_for(app: FastAPI) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        follow_redirects=True,
        timeout=20.0,
    )


def _token_for(auth, user_id) -> dict[str, str]:
    token = create_access_token(
        {"sub": str(user_id)},
        secret_key=auth.config.secret_key,
        algorithm=auth.config.algorithm,
    )
    return {"Authorization": f"Bearer {token}"}


async def _create_root(auth, session, *, label: str):
    slug = f"{label}-{_suffix()}"
    return await auth.entity_service.create_entity(
        session=session,
        name=slug,
        display_name=label.title(),
        slug=slug,
        entity_class=EntityClass.STRUCTURAL,
        entity_type="organization",
    )


async def _create_child(auth, session, *, parent_id, label: str):
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


async def _create_user(auth, session, *, email_prefix: str, root_entity_id=None, is_superuser=False):
    return await auth.user_service.create_user(
        session=session,
        email=f"{email_prefix}-{_suffix()}@example.com",
        password="TestPass123!",
        first_name=email_prefix.title(),
        last_name="User",
        root_entity_id=root_entity_id,
        is_superuser=is_superuser,
    )


async def _create_user_permissions(auth, session) -> None:
    for permission_name in USER_PERMISSIONS:
        await auth.permission_service.create_permission(
            session,
            name=permission_name,
            display_name=permission_name,
        )


async def _grant_role(auth, session, *, user_id, permission_names, root_entity_id=None, is_global=False):
    role = await auth.role_service.create_role(
        session=session,
        name=f"granted-{_suffix()}",
        display_name="Granted Role",
        permission_names=list(permission_names),
        root_entity_id=root_entity_id,
        is_global=is_global,
    )
    await auth.role_service.assign_role_to_user(
        session,
        user_id=user_id,
        role_id=role.id,
    )
    return role


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
async def client(auth_instance: EnterpriseRBAC) -> httpx.AsyncClient:
    async with _client_for(_make_app(auth_instance)) as client:
        yield client


@pytest.mark.integration
@pytest.mark.asyncio
async def test_scoped_admin_user_management_is_limited_to_access_scope(
    client: httpx.AsyncClient,
    auth_instance: EnterpriseRBAC,
):
    async with auth_instance.get_session() as session:
        root_a = await _create_root(auth_instance, session, label="root-a")
        child_a = await _create_child(auth_instance, session, parent_id=root_a.id, label="child-a")
        root_b = await _create_root(auth_instance, session, label="root-b")

        await _create_user_permissions(auth_instance, session)

        scoped_admin = await _create_user(auth_instance, session, email_prefix="scoped-admin", root_entity_id=root_a.id)
        await _grant_role(
            auth_instance,
            session,
            user_id=scoped_admin.id,
            permission_names=USER_PERMISSIONS,
            root_entity_id=root_a.id,
        )

        # Root-assigned with NO membership rows — the basis edge case (DD-056 Q5).
        root_only_target = await _create_user(
            auth_instance, session, email_prefix="root-only", root_entity_id=root_a.id
        )
        # No root, but an active membership inside the actor's tree.
        member_role = await auth_instance.role_service.create_role(
            session=session,
            name=f"member-role-{_suffix()}",
            display_name="Member Role",
            root_entity_id=root_a.id,
            is_global=False,
        )
        membership_target = await _create_user(auth_instance, session, email_prefix="member-only")
        await auth_instance.membership_service.add_member(
            session,
            entity_id=child_a.id,
            user_id=membership_target.id,
            role_ids=[member_role.id],
            joined_by_id=scoped_admin.id,
        )
        other_root_target = await _create_user(
            auth_instance, session, email_prefix="other-root", root_entity_id=root_b.id
        )
        in_tree_superuser = await _create_user(
            auth_instance,
            session,
            email_prefix="tree-superuser",
            root_entity_id=root_a.id,
            is_superuser=True,
        )
        orphan_user = await _create_user(auth_instance, session, email_prefix="orphan")
        await session.commit()

    headers = _token_for(auth_instance, scoped_admin.id)

    # List is silently filtered to the actor's trees.
    list_response = await client.get("/v1/users/", headers=headers)
    assert list_response.status_code == 200, list_response.text
    listed_ids = {item["id"] for item in list_response.json()["items"]}
    assert str(root_only_target.id) in listed_ids
    assert str(membership_target.id) in listed_ids
    assert str(in_tree_superuser.id) in listed_ids
    assert str(other_root_target.id) not in listed_ids
    assert str(orphan_user.id) not in listed_ids

    # Search cannot reach across trees either.
    search_response = await client.get(
        "/v1/users/",
        headers=headers,
        params={"search": other_root_target.email},
    )
    assert search_response.status_code == 200, search_response.text
    assert search_response.json()["items"] == []

    # The root_entity_id param narrows within scope, never widens it.
    widen_response = await client.get(
        "/v1/users/",
        headers=headers,
        params={"root_entity_id": str(root_b.id)},
    )
    assert widen_response.status_code == 200, widen_response.text
    assert widen_response.json()["items"] == []

    # In-scope targets are reachable on both bases (root and membership).
    assert (await client.get(f"/v1/users/{root_only_target.id}", headers=headers)).status_code == 200
    assert (await client.get(f"/v1/users/{membership_target.id}", headers=headers)).status_code == 200
    update_response = await client.patch(
        f"/v1/users/{root_only_target.id}",
        headers=headers,
        json={"first_name": "Renamed"},
    )
    assert update_response.status_code == 200, update_response.text

    # Out-of-scope targets are hidden as 404 (anti-enumeration), reads and writes alike.
    get_cross = await client.get(f"/v1/users/{other_root_target.id}", headers=headers)
    assert get_cross.status_code == 404, get_cross.text
    assert get_cross.json()["message"] == "User not found"
    assert (
        await client.patch(
            f"/v1/users/{other_root_target.id}",
            headers=headers,
            json={"first_name": "Nope"},
        )
    ).status_code == 404
    assert (
        await client.patch(
            f"/v1/users/{other_root_target.id}/status",
            headers=headers,
            json={"status": "suspended", "reason": "cross-tree attempt"},
        )
    ).status_code == 404
    assert (
        await client.post(
            f"/v1/users/{other_root_target.id}/roles",
            headers=headers,
            json={"role_id": str(uuid.uuid4())},
        )
    ).status_code == 404
    assert (await client.delete(f"/v1/users/{other_root_target.id}", headers=headers)).status_code == 404
    assert (await client.get(f"/v1/users/{other_root_target.id}/roles", headers=headers)).status_code == 404
    assert (await client.get(f"/v1/users/{other_root_target.id}/audit-events", headers=headers)).status_code == 404

    # In-tree superusers are visible but not mutable by non-global actors.
    assert (await client.get(f"/v1/users/{in_tree_superuser.id}", headers=headers)).status_code == 200
    superuser_patch = await client.patch(
        f"/v1/users/{in_tree_superuser.id}",
        headers=headers,
        json={"first_name": "Hijack"},
    )
    assert superuser_patch.status_code == 403, superuser_patch.text
    assert "superuser" in superuser_patch.json()["message"].lower()

    # Orphaned users match only global scopes.
    orphaned_response = await client.get("/v1/users/orphaned", headers=headers)
    assert orphaned_response.status_code == 200, orphaned_response.text
    assert orphaned_response.json()["total"] == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_system_wide_role_grants_global_user_scope(
    client: httpx.AsyncClient,
    auth_instance: EnterpriseRBAC,
):
    async with auth_instance.get_session() as session:
        root_a = await _create_root(auth_instance, session, label="root-a")
        root_b = await _create_root(auth_instance, session, label="root-b")

        await _create_user_permissions(auth_instance, session)

        global_admin = await _create_user(auth_instance, session, email_prefix="global-admin", root_entity_id=root_a.id)
        # System-wide role: is_global with no root/scope entity (DD-056).
        await _grant_role(
            auth_instance,
            session,
            user_id=global_admin.id,
            permission_names=USER_PERMISSIONS,
            is_global=True,
        )

        other_root_target = await _create_user(
            auth_instance, session, email_prefix="other-root", root_entity_id=root_b.id
        )
        other_root_superuser = await _create_user(
            auth_instance,
            session,
            email_prefix="other-superuser",
            root_entity_id=root_b.id,
            is_superuser=True,
        )
        await session.commit()

    headers = _token_for(auth_instance, global_admin.id)

    list_response = await client.get("/v1/users/", headers=headers)
    assert list_response.status_code == 200, list_response.text
    listed_ids = {item["id"] for item in list_response.json()["items"]}
    assert str(other_root_target.id) in listed_ids

    assert (await client.get(f"/v1/users/{other_root_target.id}", headers=headers)).status_code == 200
    cross_patch = await client.patch(
        f"/v1/users/{other_root_target.id}",
        headers=headers,
        json={"first_name": "Managed"},
    )
    assert cross_patch.status_code == 200, cross_patch.text

    # Global scope also clears the superuser-target guard.
    superuser_patch = await client.patch(
        f"/v1/users/{other_root_superuser.id}",
        headers=headers,
        json={"first_name": "Allowed"},
    )
    assert superuser_patch.status_code == 200, superuser_patch.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_enforce_user_scope_flag_restores_legacy_behavior(test_engine):
    auth = EnterpriseRBAC(
        engine=test_engine,
        secret_key="test-secret-key-do-not-use-in-production-12345678",
        access_token_expire_minutes=60,
        enable_token_cleanup=False,
        enforce_user_scope=False,
    )
    await auth.initialize()
    try:
        async with auth.get_session() as session:
            root_a = await _create_root(auth, session, label="root-a")
            root_b = await _create_root(auth, session, label="root-b")
            await _create_user_permissions(auth, session)
            scoped_admin = await _create_user(auth, session, email_prefix="legacy-admin", root_entity_id=root_a.id)
            await _grant_role(
                auth,
                session,
                user_id=scoped_admin.id,
                permission_names=USER_PERMISSIONS,
                root_entity_id=root_a.id,
            )
            other_root_target = await _create_user(auth, session, email_prefix="other-root", root_entity_id=root_b.id)
            await session.commit()

        async with _client_for(_make_app(auth)) as client:
            headers = _token_for(auth, scoped_admin.id)
            cross_get = await client.get(f"/v1/users/{other_root_target.id}", headers=headers)
            assert cross_get.status_code == 200, cross_get.text

            list_response = await client.get("/v1/users/", headers=headers)
            assert list_response.status_code == 200, list_response.text
            listed_ids = {item["id"] for item in list_response.json()["items"]}
            assert str(other_root_target.id) in listed_ids
    finally:
        await auth.shutdown()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_simple_rbac_user_routes_are_unscoped(test_engine):
    auth = SimpleRBAC(
        engine=test_engine,
        secret_key="test-secret-key-do-not-use-in-production-12345678",
        access_token_expire_minutes=60,
        enable_token_cleanup=False,
    )
    await auth.initialize()
    try:
        async with auth.get_session() as session:
            await _create_user_permissions(auth, session)
            actor = await _create_user(auth, session, email_prefix="simple-actor")
            # SimpleRBAC has no entities, so every role is system-wide by construction.
            await _grant_role(
                auth,
                session,
                user_id=actor.id,
                permission_names=USER_PERMISSIONS,
                is_global=True,
            )
            target = await _create_user(auth, session, email_prefix="simple-target")
            await session.commit()

        async with _client_for(_make_app(auth)) as client:
            headers = _token_for(auth, actor.id)
            get_response = await client.get(f"/v1/users/{target.id}", headers=headers)
            assert get_response.status_code == 200, get_response.text

            list_response = await client.get("/v1/users/", headers=headers)
            assert list_response.status_code == 200, list_response.text
            listed_ids = {item["id"] for item in list_response.json()["items"]}
            assert str(target.id) in listed_ids
    finally:
        await auth.shutdown()
