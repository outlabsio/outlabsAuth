"""
0.1.0a35 authorization hardening (DD-056 extension, DD-061).

Every security fix here is pinned with a negative case (the cross-tenant or
escalating request is refused) and a positive case (the legitimate in-scope
or global request still works):

* membership / effective-permission reads apply the DD-056 target scope;
* tenant-scoped admins cannot mint global-scope or cross-tenant accounts;
* reactivating a role/membership re-runs SEC-2 delegation containment;
* clearing ``assignable_at_types`` counts as widening a role;
* orphaned-user listing is tenant-scoped and hides soft-deleted accounts;
* entity routes are tenant-scoped and tenant-creating changes need a global actor;
* self-service email change is disabled by default and needs re-authentication;
* a tenant admin cannot pull an unaffiliated (possibly global) account into its
  tenant, modify an in-tree global administrator, invite into another tenant's
  entity, or reach other tenants' roles through a personal API key;
* direct org-scoped and entity-local roles only grant inside their own tree in
  an entity context (DD-054 matrix);
* a direct grant (assign, invite without entity, reactivation) of another
  tenant's role answers 404, a direct org role only goes to users rooted in its
  tree, and its SEC-2 containment runs at the role's root;
* accounts with a dormant (scheduled, suspended, expired, revoked or
  inactive-definition) system-wide grant are managed by global actors only;
* the shared permission catalog and its ABAC conditions are written by global
  actors only.
"""

from __future__ import annotations

import uuid
from typing import Any

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from outlabs_auth import EnterpriseRBAC
from outlabs_auth.core.exceptions import InvalidInputError
from outlabs_auth.fastapi import register_exception_handlers
from outlabs_auth.models.sql.enums import EntityClass, MembershipStatus, RoleScope, UserStatus
from outlabs_auth.routers import (
    get_api_keys_router,
    get_auth_router,
    get_entities_router,
    get_memberships_router,
    get_permissions_router,
    get_roles_router,
    get_users_router,
)
from outlabs_auth.utils.jwt import create_access_token

SECRET = "test-secret-key-do-not-use-in-production-12345678"

ADMIN_PERMISSIONS = (
    "user:read",
    "user:create",
    "user:update",
    "user:delete",
    "membership:read",
    "membership:create",
    "membership:create_tree",
    "membership:update",
    "membership:update_tree",
    "membership:delete",
    "permission:read",
    "permission:check",
    "role:read",
    "role:update",
    "entity:read",
    "entity:create",
    "entity:update",
    "entity:delete",
)


def _suffix() -> str:
    return uuid.uuid4().hex[:8]


def _headers(auth: EnterpriseRBAC, user_id: Any) -> dict[str, str]:
    token = create_access_token(
        {"sub": str(user_id)},
        secret_key=auth.config.secret_key,
        algorithm=auth.config.algorithm,
        audience=auth.config.jwt_audience,
    )
    return {"Authorization": f"Bearer {token}"}


def _make_app(auth: EnterpriseRBAC) -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app, debug=True)
    app.include_router(get_auth_router(auth, prefix="/v1/auth"))
    app.include_router(get_users_router(auth, prefix="/v1/users"))
    app.include_router(get_memberships_router(auth, prefix="/v1/memberships"))
    app.include_router(get_permissions_router(auth, prefix="/v1/permissions"))
    app.include_router(get_roles_router(auth, prefix="/v1/roles"))
    app.include_router(get_entities_router(auth, prefix="/v1/entities"))
    app.include_router(get_api_keys_router(auth, prefix="/v1/api-keys"))
    return app


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=20.0)


async def _entity(auth, session, *, label: str, parent_id=None, entity_type: str | None = None):
    slug = f"{label}-{_suffix()}"
    return await auth.entity_service.create_entity(
        session=session,
        name=slug,
        display_name=label.title(),
        slug=slug,
        entity_class=EntityClass.STRUCTURAL,
        entity_type=entity_type or ("organization" if parent_id is None else "team"),
        parent_id=parent_id,
    )


async def _user(auth, session, *, prefix: str, root_entity_id=None, is_superuser: bool = False):
    return await auth.user_service.create_user(
        session=session,
        email=f"{prefix}-{_suffix()}@example.com",
        password="TestPass123!",
        first_name=prefix.title(),
        last_name="User",
        root_entity_id=root_entity_id,
        is_superuser=is_superuser,
    )


async def _role(auth, session, *, permissions, root_entity_id=None, is_global=False, **kwargs):
    return await auth.role_service.create_role(
        session=session,
        name=f"role-{_suffix()}",
        display_name="Role",
        permission_names=list(permissions),
        root_entity_id=root_entity_id,
        is_global=is_global,
        **kwargs,
    )


@pytest_asyncio.fixture
async def auth_instance(test_engine) -> EnterpriseRBAC:
    auth = EnterpriseRBAC(
        engine=test_engine,
        secret_key=SECRET,
        access_token_expire_minutes=60,
        enable_token_cleanup=False,
    )
    await auth.initialize()
    yield auth
    await auth.shutdown()


@pytest_asyncio.fixture
async def client(auth_instance: EnterpriseRBAC) -> httpx.AsyncClient:
    async with _client(_make_app(auth_instance)) as http_client:
        yield http_client


@pytest_asyncio.fixture
async def world(auth_instance: EnterpriseRBAC) -> dict[str, Any]:
    """Two tenants, a tenant-scoped admin in A, a global admin and a superuser."""
    auth = auth_instance
    async with auth.get_session() as session:
        for name in ADMIN_PERMISSIONS:
            await auth.permission_service.create_permission(session, name=name, display_name=name)
        for name in ("lead:read", "lead:create", "lead:delete"):
            await auth.permission_service.create_permission(session, name=name, display_name=name)

        root_a = await _entity(auth, session, label="tenant-a")
        child_a = await _entity(auth, session, label="team-a", parent_id=root_a.id)
        root_b = await _entity(auth, session, label="tenant-b")
        child_b = await _entity(auth, session, label="team-b", parent_id=root_b.id)

        scoped_admin = await _user(auth, session, prefix="scoped-admin", root_entity_id=root_a.id)
        scoped_role = await _role(auth, session, permissions=ADMIN_PERMISSIONS, root_entity_id=root_a.id)
        await auth.role_service.assign_role_to_user(session, user_id=scoped_admin.id, role_id=scoped_role.id)

        global_admin = await _user(auth, session, prefix="global-admin", root_entity_id=root_a.id)
        system_admin_role = await _role(auth, session, permissions=ADMIN_PERMISSIONS, is_global=True)
        await auth.role_service.assign_role_to_user(session, user_id=global_admin.id, role_id=system_admin_role.id)

        superuser = await _user(auth, session, prefix="superuser", is_superuser=True)

        member_role_a = await _role(auth, session, permissions=["lead:read"], root_entity_id=root_a.id)
        member_role_b = await _role(auth, session, permissions=["lead:read"], root_entity_id=root_b.id)
        user_a = await _user(auth, session, prefix="user-a", root_entity_id=root_a.id)
        await auth.membership_service.add_member(
            session, entity_id=child_a.id, user_id=user_a.id, role_ids=[member_role_a.id]
        )
        user_b = await _user(auth, session, prefix="user-b", root_entity_id=root_b.id)
        await auth.membership_service.add_member(
            session, entity_id=child_b.id, user_id=user_b.id, role_ids=[member_role_b.id]
        )
        await session.commit()

    return {
        "root_a": root_a,
        "child_a": child_a,
        "root_b": root_b,
        "child_b": child_b,
        "scoped_admin": scoped_admin,
        "scoped_role": scoped_role,
        "global_admin": global_admin,
        "system_admin_role": system_admin_role,
        "superuser": superuser,
        "member_role_a": member_role_a,
        "member_role_b": member_role_b,
        "user_a": user_a,
        "user_b": user_b,
    }


# ---------------------------------------------------------------------------
# F-039: membership / permission reads apply the DD-056 target scope
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_membership_and_permission_reads_apply_target_scope(client, auth_instance, world):
    scoped = _headers(auth_instance, world["scoped_admin"].id)
    user_a, user_b = world["user_a"], world["user_b"]

    # Negative: another tenant's membership graph and permissions are 404.
    cross_memberships = await client.get(f"/v1/memberships/user/{user_b.id}", headers=scoped)
    assert cross_memberships.status_code == 404, cross_memberships.text
    cross_permissions = await client.get(f"/v1/permissions/user/{user_b.id}", headers=scoped)
    assert cross_permissions.status_code == 404, cross_permissions.text
    cross_check = await client.post(
        "/v1/permissions/check",
        headers=scoped,
        json={"user_id": str(user_b.id), "permissions": ["lead:read"]},
    )
    assert cross_check.status_code == 404, cross_check.text

    # Out-of-scope is indistinguishable from nonexistent.
    missing = await client.get(f"/v1/memberships/user/{uuid.uuid4()}", headers=scoped)
    assert missing.status_code == 404
    assert missing.json() == cross_memberships.json()

    # Positive: in-scope targets, self, and global actors still work.
    in_scope = await client.get(f"/v1/memberships/user/{user_a.id}", headers=scoped)
    assert in_scope.status_code == 200, in_scope.text
    assert [row["entity_id"] for row in in_scope.json()] == [str(world["child_a"].id)]
    assert (await client.get(f"/v1/permissions/user/{user_a.id}", headers=scoped)).status_code == 200
    check = await client.post(
        "/v1/permissions/check",
        headers=scoped,
        json={"user_id": str(user_a.id), "permissions": ["lead:read"]},
    )
    assert check.status_code == 200, check.text
    assert check.json()["results"] == {"lead:read": True}

    self_read = await client.get(
        f"/v1/memberships/user/{world['scoped_admin'].id}",
        headers=scoped,
    )
    assert self_read.status_code == 200

    global_headers = _headers(auth_instance, world["global_admin"].id)
    assert (await client.get(f"/v1/memberships/user/{user_b.id}", headers=global_headers)).status_code == 200
    assert (await client.get(f"/v1/permissions/user/{user_b.id}", headers=global_headers)).status_code == 200


# ---------------------------------------------------------------------------
# F-239 / F-056: entity_id is honored by /permissions/user and /permissions/me
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_permission_reads_honor_entity_context(client, auth_instance, world):
    auth = auth_instance
    async with auth.get_session() as session:
        team = await _entity(auth, session, label="ctx-team", parent_id=world["root_a"].id)
        sibling = await _entity(auth, session, label="ctx-sibling", parent_id=world["root_a"].id)
        local_role = await auth.role_service.create_role(
            session=session,
            name=f"local-{_suffix()}",
            display_name="Local",
            permission_names=["lead:delete"],
            root_entity_id=world["root_a"].id,
            scope_entity_id=team.id,
            is_global=False,
        )
        member = await _user(auth, session, prefix="ctx-member", root_entity_id=world["root_a"].id)
        await auth.membership_service.add_member(
            session, entity_id=team.id, user_id=member.id, role_ids=[local_role.id]
        )
        await session.commit()

    scoped = _headers(auth, world["scoped_admin"].id)
    # Without entity_id the historical aggregate (union across contexts) is
    # unchanged for backward compatibility.
    flat = await client.get(f"/v1/permissions/user/{member.id}", headers=scoped)
    assert flat.status_code == 200, flat.text
    assert "lead:delete" in flat.json()

    at_team = await client.get(f"/v1/permissions/user/{member.id}", headers=scoped, params={"entity_id": str(team.id)})
    assert at_team.status_code == 200, at_team.text
    assert "lead:delete" in at_team.json()

    at_sibling = await client.get(
        f"/v1/permissions/user/{member.id}", headers=scoped, params={"entity_id": str(sibling.id)}
    )
    assert at_sibling.status_code == 200
    assert "lead:delete" not in at_sibling.json()

    malformed = await client.get(
        f"/v1/permissions/user/{member.id}", headers=scoped, params={"entity_id": "not-a-uuid"}
    )
    assert malformed.status_code == 400

    me_headers = _headers(auth, member.id)
    me_team = await client.get("/v1/permissions/me", headers=me_headers, params={"entity_id": str(team.id)})
    assert me_team.status_code == 200, me_team.text
    assert "lead:delete" in me_team.json()
    me_sibling = await client.get("/v1/permissions/me", headers=me_headers, params={"entity_id": str(sibling.id)})
    assert me_sibling.status_code == 200, me_sibling.text
    assert "lead:delete" not in me_sibling.json()

    super_headers = _headers(auth, world["superuser"].id)
    super_ctx = await client.get("/v1/permissions/me", headers=super_headers, params={"entity_id": str(team.id)})
    assert super_ctx.json() == ["*:*"]


# ---------------------------------------------------------------------------
# F-040: tenant-scoped admins cannot create global-scope / cross-tenant accounts
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_scoped_admin_cannot_create_users_in_other_tenants(client, auth_instance, world):
    scoped = _headers(auth_instance, world["scoped_admin"].id)

    cross = await client.post(
        "/v1/users/",
        headers=scoped,
        json={
            "email": f"cross-{_suffix()}@example.com",
            "password": "TestPass123!",
            "root_entity_id": str(world["root_b"].id),
        },
    )
    assert cross.status_code == 403, cross.text

    defaulted = await client.post(
        "/v1/users/",
        headers=scoped,
        json={"email": f"defaulted-{_suffix()}@example.com", "password": "TestPass123!"},
    )
    assert defaulted.status_code == 201, defaulted.text
    assert defaulted.json()["root_entity_id"] == str(world["root_a"].id)

    in_scope = await client.post(
        "/v1/users/",
        headers=scoped,
        json={
            "email": f"in-scope-{_suffix()}@example.com",
            "password": "TestPass123!",
            "root_entity_id": str(world["root_a"].id),
        },
    )
    assert in_scope.status_code == 201, in_scope.text

    global_headers = _headers(auth_instance, world["global_admin"].id)
    global_cross = await client.post(
        "/v1/users/",
        headers=global_headers,
        json={
            "email": f"global-cross-{_suffix()}@example.com",
            "password": "TestPass123!",
            "root_entity_id": str(world["root_b"].id),
        },
    )
    assert global_cross.status_code == 201, global_cross.text
    unrooted = await client.post(
        "/v1/users/",
        headers=global_headers,
        json={"email": f"unrooted-{_suffix()}@example.com", "password": "TestPass123!"},
    )
    assert unrooted.status_code == 201
    assert unrooted.json()["root_entity_id"] is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_scoped_inviter_cannot_grant_system_wide_roles(client, auth_instance, world):
    auth = auth_instance
    async with auth.get_session() as session:
        # A system-wide role whose permissions the scoped admin DOES hold, so
        # SEC-2 containment passes and only the global-scope guard can refuse.
        reader_system_role = await _role(auth, session, permissions=["user:read"], is_global=True)
        tenant_role = await _role(auth, session, permissions=["user:read"], root_entity_id=world["root_a"].id)
        await session.commit()

    scoped = _headers(auth, world["scoped_admin"].id)
    refused = await client.post(
        "/v1/auth/invite",
        headers=scoped,
        json={"email": f"esc-{_suffix()}@example.com", "role_ids": [str(reader_system_role.id)]},
    )
    assert refused.status_code == 403, refused.text
    assert refused.json()["details"]["system_wide_role_ids"] == [str(reader_system_role.id)]

    allowed = await client.post(
        "/v1/auth/invite",
        headers=scoped,
        json={"email": f"tenant-invite-{_suffix()}@example.com", "role_ids": [str(tenant_role.id)]},
    )
    assert allowed.status_code == 201, allowed.text
    # The invitee lands in the inviter's tenant instead of outside every tree.
    assert allowed.json()["root_entity_id"] == str(world["root_a"].id)

    with_entity = await client.post(
        "/v1/auth/invite",
        headers=scoped,
        json={
            "email": f"entity-invite-{_suffix()}@example.com",
            "entity_id": str(world["child_a"].id),
            "role_ids": [str(tenant_role.id)],
        },
    )
    assert with_entity.status_code == 201, with_entity.text

    global_headers = _headers(auth, world["global_admin"].id)
    global_invite = await client.post(
        "/v1/auth/invite",
        headers=global_headers,
        json={"email": f"global-invite-{_suffix()}@example.com", "role_ids": [str(reader_system_role.id)]},
    )
    assert global_invite.status_code == 201, global_invite.text

    # Direct assignment through the users router is guarded the same way.
    target = (await client.get("/v1/users/", headers=scoped, params={"search": "tenant-invite"})).json()["items"][0]
    direct = await client.post(
        f"/v1/users/{target['id']}/roles",
        headers=scoped,
        json={"role_id": str(reader_system_role.id)},
    )
    assert direct.status_code == 403, direct.text
    direct_tenant = await client.post(
        f"/v1/users/{target['id']}/roles",
        headers=_headers(auth, world["superuser"].id),
        json={"role_id": str(reader_system_role.id)},
    )
    assert direct_tenant.status_code == 201, direct_tenant.text


# ---------------------------------------------------------------------------
# F-162: reactivation re-runs SEC-2 delegation containment
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_reactivating_direct_role_requires_delegation(client, auth_instance, world):
    auth = auth_instance
    async with auth.get_session() as session:
        powerful = await _role(auth, session, permissions=["lead:delete"], root_entity_id=world["root_a"].id)
        target = await _user(auth, session, prefix="reactivate", root_entity_id=world["root_a"].id)
        membership = await auth.role_service.assign_role_to_user(session, user_id=target.id, role_id=powerful.id)
        await session.commit()

    scoped = _headers(auth, world["scoped_admin"].id)  # holds user:update, not lead:delete
    path = f"/v1/users/{target.id}/role-memberships/{membership.id}"

    # Narrowing (suspending) is always allowed: responders cut access they lack.
    suspended = await client.patch(path, headers=scoped, json={"status": "suspended"})
    assert suspended.status_code == 200, suspended.text
    assert suspended.json()["status"] == "suspended"

    reactivated = await client.patch(path, headers=scoped, json={"status": "active"})
    assert reactivated.status_code == 403, reactivated.text
    assert reactivated.json()["details"]["missing_permissions"] == ["lead:delete"]

    allowed = await client.patch(path, headers=_headers(auth, world["superuser"].id), json={"status": "active"})
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["status"] == "active"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_reactivating_entity_membership_requires_delegation(client, auth_instance, world):
    auth = auth_instance
    async with auth.get_session() as session:
        powerful = await _role(auth, session, permissions=["lead:delete"], root_entity_id=world["root_a"].id)
        target = await _user(auth, session, prefix="member-reactivate", root_entity_id=world["root_a"].id)
        await auth.membership_service.add_member(
            session,
            entity_id=world["child_a"].id,
            user_id=target.id,
            role_ids=[powerful.id],
            status=MembershipStatus.SUSPENDED,
        )
        manager = await _user(auth, session, prefix="member-manager", root_entity_id=world["root_a"].id)
        manager_role = await _role(
            auth,
            session,
            permissions=["membership:update", "membership:update_tree", "membership:read"],
            root_entity_id=world["root_a"].id,
        )
        await auth.membership_service.add_member(
            session, entity_id=world["root_a"].id, user_id=manager.id, role_ids=[manager_role.id]
        )
        await session.commit()

    path = f"/v1/memberships/{world['child_a'].id}/{target.id}"
    refused = await client.patch(path, headers=_headers(auth, manager.id), json={"status": "active"})
    assert refused.status_code == 403, refused.text

    allowed = await client.patch(path, headers=_headers(auth, world["superuser"].id), json={"status": "active"})
    assert allowed.status_code == 200, allowed.text
    suspend_again = await client.patch(path, headers=_headers(auth, manager.id), json={"status": "suspended"})
    assert suspend_again.status_code == 200, suspend_again.text


# ---------------------------------------------------------------------------
# F-238: clearing assignable_at_types widens the role
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_clearing_assignable_at_types_counts_as_widening(client, auth_instance, world):
    auth = auth_instance
    async with auth.get_session() as session:
        restricted = await _role(
            auth,
            session,
            permissions=["lead:delete"],
            root_entity_id=world["root_a"].id,
            assignable_at_types=["office", "team"],
        )
        await session.commit()

    scoped = _headers(auth, world["scoped_admin"].id)  # role:update without lead:delete
    cleared = await client.patch(f"/v1/roles/{restricted.id}", headers=scoped, json={"assignable_at_types": []})
    assert cleared.status_code == 403, cleared.text

    narrowed = await client.patch(f"/v1/roles/{restricted.id}", headers=scoped, json={"assignable_at_types": ["TEAM"]})
    assert narrowed.status_code == 200, narrowed.text

    by_superuser = await client.patch(
        f"/v1/roles/{restricted.id}",
        headers=_headers(auth, world["superuser"].id),
        json={"assignable_at_types": []},
    )
    assert by_superuser.status_code == 200, by_superuser.text
    assert by_superuser.json()["assignable_at_types"] == []


# ---------------------------------------------------------------------------
# F-161 / F-240: orphaned users are tenant-scoped and hide soft-deleted accounts
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_orphaned_users_are_scoped_and_exclude_deleted(client, auth_instance, world):
    auth = auth_instance
    async with auth.get_session() as session:
        orphan_a = await _user(auth, session, prefix="orphan-a", root_entity_id=world["root_a"].id)
        orphan_b = await _user(auth, session, prefix="orphan-b", root_entity_id=world["root_b"].id)
        deleted_orphan = await _user(auth, session, prefix="orphan-deleted", root_entity_id=world["root_a"].id)
        for orphan, entity in (
            (orphan_a, world["child_a"]),
            (orphan_b, world["child_b"]),
            (deleted_orphan, world["child_a"]),
        ):
            await auth.membership_service.add_member(session, entity_id=entity.id, user_id=orphan.id, role_ids=[])
            await auth.membership_service.remove_member(session, entity_id=entity.id, user_id=orphan.id)
        deleted_orphan.status = UserStatus.DELETED
        await session.commit()

    scoped = _headers(auth, world["scoped_admin"].id)
    scoped_page = await client.get("/v1/users/orphaned", headers=scoped)
    assert scoped_page.status_code == 200, scoped_page.text
    scoped_ids = {item["user"]["id"] for item in scoped_page.json()["items"]}
    assert str(orphan_a.id) in scoped_ids
    assert str(orphan_b.id) not in scoped_ids
    assert str(deleted_orphan.id) not in scoped_ids

    deleted_page = await client.get("/v1/users/orphaned", headers=scoped, params={"status": "deleted"})
    assert {item["user"]["id"] for item in deleted_page.json()["items"]} == {str(deleted_orphan.id)}

    bad_status = await client.get("/v1/users/orphaned", headers=scoped, params={"status": "nope"})
    assert bad_status.status_code == 400

    global_page = await client.get("/v1/users/orphaned", headers=_headers(auth, world["global_admin"].id))
    global_ids = {item["user"]["id"] for item in global_page.json()["items"]}
    assert {str(orphan_a.id), str(orphan_b.id)} <= global_ids
    assert str(deleted_orphan.id) not in global_ids


# ---------------------------------------------------------------------------
# F-020 / F-076: entity routes are tenant-scoped (DD-061)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_entity_routes_are_tenant_scoped(client, auth_instance, world):
    scoped = _headers(auth_instance, world["scoped_admin"].id)
    root_b, child_b = world["root_b"], world["child_b"]

    listing = await client.get("/v1/entities/", headers=scoped, params={"limit": 1000})
    assert listing.status_code == 200, listing.text
    listed = {item["id"] for item in listing.json()["items"]}
    assert str(world["root_a"].id) in listed and str(world["child_a"].id) in listed
    assert str(root_b.id) not in listed and str(child_b.id) not in listed

    for path in (
        f"/v1/entities/{root_b.id}",
        f"/v1/entities/{root_b.id}/children",
        f"/v1/entities/{child_b.id}/path",
        f"/v1/entities/{root_b.id}/descendants",
        f"/v1/entities/{root_b.id}/members",
    ):
        response = await client.get(path, headers=scoped)
        assert response.status_code in (403, 404), (path, response.status_code, response.text)
        assert response.status_code != 200

    for path in (f"/v1/entities/{root_b.id}", f"/v1/entities/{child_b.id}/path"):
        assert (await client.get(path, headers=scoped)).status_code == 404

    patch_cross = await client.patch(f"/v1/entities/{child_b.id}", headers=scoped, json={"display_name": "Hijack"})
    assert patch_cross.status_code == 404, patch_cross.text
    delete_cross = await client.delete(f"/v1/entities/{child_b.id}", headers=scoped)
    assert delete_cross.status_code == 404, delete_cross.text

    # In-scope reads and writes keep working.
    assert (await client.get(f"/v1/entities/{world['child_a'].id}", headers=scoped)).status_code == 200
    path_a = await client.get(f"/v1/entities/{world['child_a'].id}/path", headers=scoped)
    assert [row["id"] for row in path_a.json()] == [str(world["root_a"].id), str(world["child_a"].id)]
    patch_own = await client.patch(
        f"/v1/entities/{world['child_a'].id}", headers=scoped, json={"display_name": "Renamed Team"}
    )
    assert patch_own.status_code == 200, patch_own.text

    # Global actors span every tenant.
    global_listing = await client.get(
        "/v1/entities/", headers=_headers(auth_instance, world["global_admin"].id), params={"limit": 1000}
    )
    assert str(root_b.id) in {item["id"] for item in global_listing.json()["items"]}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tenant_creating_entity_changes_need_a_global_actor(client, auth_instance, world):
    auth = auth_instance
    scoped = _headers(auth, world["scoped_admin"].id)
    superuser = _headers(auth, world["superuser"].id)
    async with auth.get_session() as session:
        movable = await _entity(auth, session, label="movable", parent_id=world["root_a"].id)
        await session.commit()

    root_create = await client.post(
        "/v1/entities/",
        headers=scoped,
        json={
            "name": f"rogue_{_suffix()}",
            "display_name": "Rogue Tenant",
            "slug": f"rogue-{_suffix()}",
            "entity_class": "structural",
            "entity_type": "organization",
        },
    )
    assert root_create.status_code == 403, root_create.text

    to_root = await client.post(f"/v1/entities/{movable.id}/move", headers=scoped, json={"new_parent_id": None})
    assert to_root.status_code == 403, to_root.text

    under_other_tenant = await client.post(
        f"/v1/entities/{movable.id}/move",
        headers=scoped,
        json={"new_parent_id": str(world["root_b"].id)},
    )
    assert under_other_tenant.status_code == 404, under_other_tenant.text

    archive_root = await client.delete(f"/v1/entities/{world['root_a'].id}?cascade=true", headers=scoped)
    assert archive_root.status_code == 403, archive_root.text

    # Superusers keep the platform-level operations. "team" is not an allowed
    # root type, so promoting the team is refused by root-type validation.
    invalid_root_type = await client.post(
        f"/v1/entities/{movable.id}/move", headers=superuser, json={"new_parent_id": None}
    )
    assert invalid_root_type.status_code == 422, invalid_root_type.text

    super_root = await client.post(
        "/v1/entities/",
        headers=superuser,
        json={
            "name": f"tenant_c_{_suffix()}",
            "display_name": "Tenant C",
            "slug": f"tenant-c-{_suffix()}",
            "entity_class": "structural",
            "entity_type": "organization",
        },
    )
    assert super_root.status_code == 201, super_root.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_entity_changes_are_audited(client, auth_instance, world):
    superuser = _headers(auth_instance, world["superuser"].id)
    created = await client.post(
        "/v1/entities/",
        headers=superuser,
        json={
            "name": f"audited_{_suffix()}",
            "display_name": "Audited",
            "slug": f"audited-{_suffix()}",
            "entity_class": "structural",
            "entity_type": "team",
            "parent_entity_id": str(world["root_a"].id),
        },
    )
    assert created.status_code == 201, created.text
    entity_id = created.json()["id"]
    assert (
        await client.patch(f"/v1/entities/{entity_id}", headers=superuser, json={"display_name": "Audited 2"})
    ).status_code == 200
    assert (
        await client.post(
            f"/v1/entities/{entity_id}/move",
            headers=superuser,
            json={"new_parent_id": str(world["child_a"].id)},
        )
    ).status_code == 200
    assert (await client.delete(f"/v1/entities/{entity_id}", headers=superuser)).status_code == 204

    async with auth_instance.get_session() as session:
        events, total = await auth_instance.user_audit_service.list_events(
            session, page=1, limit=50, event_category="entity", entity_id=uuid.UUID(entity_id)
        )
    by_type = {event.event_type: event for event in events}
    assert {"entity.created", "entity.updated", "entity.moved", "entity.archived"} <= set(by_type)
    assert by_type["entity.updated"].before == {"display_name": "Audited"}
    assert by_type["entity.updated"].after == {"display_name": "Audited 2"}
    assert by_type["entity.moved"].after["parent_id"] == str(world["child_a"].id)
    assert all(event.root_entity_id == world["root_a"].id for event in events)
    assert all(event.actor_user_id == world["superuser"].id for event in events)


# ---------------------------------------------------------------------------
# F-193: self-service email change
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_self_service_email_change_is_disabled_by_default(client, auth_instance, world):
    user = world["user_a"]
    headers = _headers(auth_instance, user.id)

    refused = await client.patch("/v1/users/me", headers=headers, json={"email": f"new-{_suffix()}@example.com"})
    assert refused.status_code == 403, refused.text
    assert refused.json()["details"]["reason"] == "self_service_email_change_disabled"

    # Whole-object forms that resend the unchanged address keep working.
    unchanged = await client.patch(
        "/v1/users/me", headers=headers, json={"email": user.email.upper(), "first_name": "Still"}
    )
    assert unchanged.status_code == 200, unchanged.text
    assert unchanged.json()["first_name"] == "Still"
    assert unchanged.json()["email"] == user.email

    # Admin edits are unaffected.
    admin_change = await client.patch(
        f"/v1/users/{user.id}",
        headers=_headers(auth_instance, world["superuser"].id),
        json={"email": f"admin-set-{_suffix()}@example.com"},
    )
    assert admin_change.status_code == 200, admin_change.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_self_service_email_change_requires_reauthentication_when_enabled(test_engine):
    auth = EnterpriseRBAC(
        engine=test_engine,
        secret_key=SECRET,
        access_token_expire_minutes=60,
        enable_token_cleanup=False,
        allow_self_service_email_change=True,
    )
    await auth.initialize()
    try:
        async with auth.get_session() as session:
            user = await _user(auth, session, prefix="email-change")
            await session.commit()
        async with _client(_make_app(auth)) as http_client:
            headers = _headers(auth, user.id)
            new_email = f"changed-{_suffix()}@example.com"
            missing = await http_client.patch("/v1/users/me", headers=headers, json={"email": new_email})
            assert missing.status_code == 422, missing.text
            assert missing.json()["details"]["field"] == "current_password"
            wrong = await http_client.patch(
                "/v1/users/me", headers=headers, json={"email": new_email, "current_password": "WrongPass123!"}
            )
            assert wrong.status_code == 401, wrong.text
            ok = await http_client.patch(
                "/v1/users/me", headers=headers, json={"email": new_email, "current_password": "TestPass123!"}
            )
            assert ok.status_code == 200, ok.text
            assert ok.json()["email"] == new_email
            assert ok.json()["email_verified"] is False
    finally:
        await auth.shutdown()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_archived_entities_stay_visible_to_their_own_tenant_only(client, auth_instance, world):
    auth = auth_instance
    async with auth.get_session() as session:
        archived_a = await _entity(auth, session, label="archived-a", parent_id=world["child_a"].id)
        archived_b = await _entity(auth, session, label="archived-b", parent_id=world["child_b"].id)
        for entity in (archived_a, archived_b):
            await auth.entity_service.delete_entity(session, entity.id, deleted_by_id=world["superuser"].id)
        await session.commit()

    scoped = _headers(auth, world["scoped_admin"].id)
    own = await client.get(f"/v1/entities/{archived_a.id}", headers=scoped)
    assert own.status_code == 200, own.text
    assert own.json()["status"] == "archived"
    other = await client.get(f"/v1/entities/{archived_b.id}", headers=scoped)
    assert other.status_code == 404, other.text


# ---------------------------------------------------------------------------
# Review round 2 (DD-061): escalation paths found in the release-candidate review
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_membership_cannot_pull_unaffiliated_or_foreign_accounts(client, auth_instance, world):
    auth = auth_instance
    async with auth.get_session() as session:
        # An unrooted account holding a direct system-wide role: global scope.
        drifter = await _user(auth, session, prefix="drifter")
        await auth.role_service.assign_role_to_user(
            session, user_id=drifter.id, role_id=world["system_admin_role"].id
        )
        plain_unrooted = await _user(auth, session, prefix="unrooted")
        await session.commit()

    scoped = _headers(auth, world["scoped_admin"].id)

    # Negative: the unaffiliated global account is invisible to the tenant
    # admin, so it cannot be pulled into the tenant (404 like a missing user).
    pulled = await client.post(
        "/v1/memberships/",
        headers=scoped,
        json={"entity_id": str(world["child_a"].id), "user_id": str(drifter.id), "role_ids": []},
    )
    assert pulled.status_code == 404, pulled.text
    missing = await client.post(
        "/v1/memberships/",
        headers=scoped,
        json={"entity_id": str(world["child_a"].id), "user_id": str(uuid.uuid4()), "role_ids": []},
    )
    assert missing.status_code == 404
    assert missing.json() == pulled.json()
    plain = await client.post(
        "/v1/memberships/",
        headers=scoped,
        json={"entity_id": str(world["child_a"].id), "user_id": str(plain_unrooted.id), "role_ids": []},
    )
    assert plain.status_code == 404, plain.text

    # ... so the takeover chain stops at the first step.
    reset = await client.patch(
        f"/v1/users/{drifter.id}/password", headers=scoped, json={"new_password": "Hijacked123!"}
    )
    assert reset.status_code == 404, reset.text
    login = await client.post(
        "/v1/auth/login", json={"email": drifter.email, "password": "Hijacked123!"}
    )
    assert login.status_code == 401, login.text
    async with auth.get_session() as session:
        memberships, _ = await auth.membership_service.get_user_entities(
            session, user_id=drifter.id, active_only=False
        )
        assert memberships == []

    # Negative: another tenant's entity answers 404 too (scope guard runs first).
    foreign = await client.post(
        "/v1/memberships/",
        headers=scoped,
        json={"entity_id": str(world["child_b"].id), "user_id": str(world["user_b"].id), "role_ids": []},
    )
    assert foreign.status_code == 404, foreign.text

    # Positive: in-scope users can still be added to in-scope entities.
    own = await client.post(
        "/v1/memberships/",
        headers=scoped,
        json={"entity_id": str(world["root_a"].id), "user_id": str(world["user_a"].id), "role_ids": []},
    )
    assert own.status_code == 201, own.text

    # Positive: a global actor can still adopt the unaffiliated account.
    adopted = await client.post(
        "/v1/memberships/",
        headers=_headers(auth, world["global_admin"].id),
        json={"entity_id": str(world["child_a"].id), "user_id": str(plain_unrooted.id), "role_ids": []},
    )
    assert adopted.status_code == 201, adopted.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_scoped_admin_cannot_modify_in_tree_global_administrator(client, auth_instance, world):
    auth = auth_instance
    scoped = _headers(auth, world["scoped_admin"].id)
    global_admin = world["global_admin"]  # rooted in tenant A, holds a system-wide role

    # Reads of an in-tree global administrator stay allowed (DD-056).
    assert (await client.get(f"/v1/users/{global_admin.id}", headers=scoped)).status_code == 200

    # Negative: every mutation of a global-scope account is refused.
    for method, path, body in (
        ("PATCH", f"/v1/users/{global_admin.id}", {"first_name": "Owned"}),
        ("PATCH", f"/v1/users/{global_admin.id}/password", {"new_password": "Hijacked123!"}),
        ("PATCH", f"/v1/users/{global_admin.id}/status", {"status": "suspended"}),
        ("DELETE", f"/v1/users/{global_admin.id}", None),
    ):
        response = await client.request(method, path, headers=scoped, json=body)
        assert response.status_code == 403, (path, response.status_code, response.text)
    login = await client.post(
        "/v1/auth/login", json={"email": global_admin.email, "password": "Hijacked123!"}
    )
    assert login.status_code == 401, login.text

    # Positive: ordinary in-tree accounts stay manageable by the tenant admin.
    ordinary = await client.patch(
        f"/v1/users/{world['user_a'].id}", headers=scoped, json={"first_name": "Renamed"}
    )
    assert ordinary.status_code == 200, ordinary.text

    # Positive: a global actor can still manage the global administrator.
    by_superuser = await client.patch(
        f"/v1/users/{global_admin.id}",
        headers=_headers(auth, world["superuser"].id),
        json={"first_name": "Updated"},
    )
    assert by_superuser.status_code == 200, by_superuser.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_invite_into_another_tenants_entity_is_refused(client, auth_instance, world):
    auth = auth_instance
    async with auth.get_session() as session:
        # A tenant-B role whose permissions the scoped admin holds, so only the
        # scope rule can refuse the grant.
        tenant_b_admin_role = await _role(
            auth, session, permissions=["user:read", "membership:read"], root_entity_id=world["root_b"].id
        )
        await session.commit()

    scoped = _headers(auth, world["scoped_admin"].id)
    for role_ids in ([], [str(tenant_b_admin_role.id)]):
        email = f"plant-{_suffix()}@example.com"
        refused = await client.post(
            "/v1/auth/invite",
            headers=scoped,
            json={"email": email, "entity_id": str(world["child_b"].id), "role_ids": role_ids},
        )
        assert refused.status_code == 404, refused.text
        async with auth.get_session() as session:
            assert await auth.user_service.get_user_by_email(session, email) is None

    nonexistent = await client.post(
        "/v1/auth/invite",
        headers=scoped,
        json={"email": f"ghost-{_suffix()}@example.com", "entity_id": str(uuid.uuid4()), "role_ids": []},
    )
    assert nonexistent.status_code == 404
    assert nonexistent.json() == refused.json()

    # Positive: inviting into the inviter's own tenant still works.
    own = await client.post(
        "/v1/auth/invite",
        headers=scoped,
        json={"email": f"own-{_suffix()}@example.com", "entity_id": str(world["child_a"].id), "role_ids": []},
    )
    assert own.status_code == 201, own.text
    assert own.json()["root_entity_id"] == str(world["root_a"].id)

    # Positive: a global actor may invite into any tenant.
    global_invite = await client.post(
        "/v1/auth/invite",
        headers=_headers(auth, world["global_admin"].id),
        json={"email": f"global-b-{_suffix()}@example.com", "entity_id": str(world["child_b"].id), "role_ids": []},
    )
    assert global_invite.status_code == 201, global_invite.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_roles_router_scopes_personal_api_keys_to_their_owner(client, auth_instance, world):
    auth = auth_instance
    async with auth.get_session() as session:
        await auth.permission_service.create_permission(session, name="role:create", display_name="role:create")
        role_creator = await _role(auth, session, permissions=["role:create"], root_entity_id=world["root_a"].id)
        await auth.role_service.assign_role_to_user(
            session, user_id=world["scoped_admin"].id, role_id=role_creator.id
        )
        await session.commit()

    scoped = _headers(auth, world["scoped_admin"].id)
    minted = await client.post(
        "/v1/api-keys/",
        headers=scoped,
        json={"name": f"personal-{_suffix()}", "scopes": ["role:read", "role:update"]},
    )
    assert minted.status_code == 201, minted.text
    key_headers = {"X-API-Key": minted.json()["api_key"]}
    role_a, role_b = world["member_role_a"], world["member_role_b"]

    # Negative: an unanchored personal key is not a global credential.
    assert (await client.get(f"/v1/roles/{role_b.id}", headers=key_headers)).status_code == 404
    listing = await client.get("/v1/roles/", headers=key_headers, params={"limit": 100})
    assert listing.status_code == 200, listing.text
    listed = {item["id"] for item in listing.json()["items"]}
    assert str(role_b.id) not in listed and str(role_a.id) in listed
    patched = await client.patch(f"/v1/roles/{role_b.id}", headers=key_headers, json={"display_name": "Hijack"})
    assert patched.status_code == 404, patched.text
    # A host that allows "create" on personal keys still gets no global reach.
    auth.api_key_policy_service._personal_allowed_action_prefixes.append("create")
    async with auth.get_session() as session:
        creator_secret, _ = await auth.api_key_service.create_api_key(
            session,
            owner_id=world["scoped_admin"].id,
            name=f"creator-{_suffix()}",
            scopes=["role:create", "role:read"],
            actor_user_id=world["scoped_admin"].id,
        )
        await session.commit()
    system_wide = await client.post(
        "/v1/roles/",
        headers={"X-API-Key": creator_secret},
        json={"name": f"rogue-{_suffix()}", "display_name": "Rogue", "is_global": True},
    )
    assert system_wide.status_code == 403, system_wide.text
    tenant_role = await client.post(
        "/v1/roles/",
        headers={"X-API-Key": creator_secret},
        json={
            "name": f"tenant-{_suffix()}",
            "display_name": "Tenant",
            "is_global": False,
            "root_entity_id": str(world["root_a"].id),
        },
    )
    assert tenant_role.status_code == 201, tenant_role.text

    # Positive: the key reaches its owner's own tenant roles.
    assert (await client.get(f"/v1/roles/{role_a.id}", headers=key_headers)).status_code == 200

    # Role pickers for another tenant's entity answer 404 (scope guard first).
    picker_b = await client.get(f"/v1/roles/entity/{world['child_b'].id}", headers=scoped)
    assert picker_b.status_code == 404, picker_b.text

    # A key anchored inside the tenant never reaches past its anchor.
    async with auth.get_session() as session:
        anchored_secret, _ = await auth.api_key_service.create_api_key(
            session,
            owner_id=world["scoped_admin"].id,
            name=f"anchored-{_suffix()}",
            scopes=["role:read"],
            entity_id=world["child_a"].id,
            actor_user_id=world["scoped_admin"].id,
        )
        await session.commit()
    anchored = {"X-API-Key": anchored_secret}
    assert (await client.get(f"/v1/roles/{role_b.id}", headers=anchored)).status_code == 404

    # Positive: a global owner's personal key keeps global reach.
    global_key = await client.post(
        "/v1/api-keys/",
        headers=_headers(auth, world["global_admin"].id),
        json={"name": f"global-{_suffix()}", "scopes": ["role:read"]},
    )
    assert global_key.status_code == 201, global_key.text
    global_read = await client.get(
        f"/v1/roles/{role_b.id}", headers={"X-API-Key": global_key.json()["api_key"]}
    )
    assert global_read.status_code == 200, global_read.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_direct_scoped_roles_only_grant_inside_their_own_tree(client, auth_instance, world):
    """DD-054 matrix for direct roles: the root cause behind the cross-tenant writes."""
    auth = auth_instance
    scoped_admin, global_admin = world["scoped_admin"], world["global_admin"]
    async with auth.get_session() as session:
        check = auth.permission_service.check_permission
        # Org-scoped direct role: inside its own tree only.
        assert await check(session, scoped_admin.id, "membership:create_tree", entity_id=world["child_a"].id)
        assert await check(session, scoped_admin.id, "membership:create_tree", entity_id=world["root_a"].id)
        assert not await check(session, scoped_admin.id, "membership:create_tree", entity_id=world["child_b"].id)
        assert not await check(session, scoped_admin.id, "membership:create_tree", entity_id=uuid.uuid4())
        # Without an entity context the flat DD-054 behavior is unchanged.
        assert await check(session, scoped_admin.id, "membership:create_tree")
        # System-wide roles still grant everywhere.
        assert await check(session, global_admin.id, "membership:create_tree", entity_id=world["child_b"].id)

        effective = await auth.permission_service.get_effective_permission_names(
            session, scoped_admin.id, entity_id=world["child_b"].id, candidate_permission_names=["user:read"]
        )
        assert effective == set()
        effective_own = await auth.permission_service.get_effective_permission_names(
            session, scoped_admin.id, entity_id=world["child_a"].id, candidate_permission_names=["user:read"]
        )
        assert effective_own == {"user:read"}

    # Archived entities of the role's own tree stay reachable; another tree's do not.
    async with auth.get_session() as session:
        archived_a = await _entity(auth, session, label="arch-a", parent_id=world["child_a"].id)
        archived_b = await _entity(auth, session, label="arch-b", parent_id=world["child_b"].id)
        for entity in (archived_a, archived_b):
            await auth.entity_service.delete_entity(session, entity.id, deleted_by_id=world["superuser"].id)
        await session.commit()
    async with auth.get_session() as session:
        check = auth.permission_service.check_permission
        assert await check(session, scoped_admin.id, "entity:update", entity_id=archived_a.id)
        assert not await check(session, scoped_admin.id, "entity:update", entity_id=archived_b.id)

    # Over HTTP: tree-permission membership writes and reads on another tenant
    # answer 404 (scope guard), in-tenant ones keep working.
    scoped = _headers(auth, scoped_admin.id)
    cross = f"/v1/memberships/{world['child_b'].id}/{world['user_b'].id}"
    assert (await client.patch(cross, headers=scoped, json={"status": "suspended"})).status_code == 404
    assert (await client.delete(cross, headers=scoped)).status_code == 404
    for path in (
        f"/v1/memberships/entity/{world['child_b'].id}",
        f"/v1/memberships/entity/{world['child_b'].id}/details",
        f"/v1/memberships/entity/{world['child_b'].id}/members",
    ):
        assert (await client.get(path, headers=scoped)).status_code == 404, path
    own = f"/v1/memberships/{world['child_a'].id}/{world['user_a'].id}"
    suspended = await client.patch(own, headers=scoped, json={"status": "suspended"})
    assert suspended.status_code == 200, suspended.text
    async with auth.get_session() as session:
        user_b_memberships, _ = await auth.membership_service.get_user_entities(
            session, user_id=world["user_b"].id, active_only=False
        )
        assert [m.status for m in user_b_memberships] == [MembershipStatus.ACTIVE]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_global_principals_without_a_user_may_grant_system_wide_roles(auth_instance, world):
    from outlabs_auth.core.exceptions import PermissionDeniedError
    from outlabs_auth.routers._scope import require_global_actor_for_system_wide_roles

    auth = auth_instance
    role_ids = [world["system_admin_role"].id]
    async with auth.get_session() as session:
        # Positive: a host-minted service token is a global platform credential.
        await require_global_actor_for_system_wide_roles(
            auth, session, actor_user=None, role_ids=role_ids, auth_result={"source": "service_token"}
        )
        # Negative: no actor at all, or a non-global principal, is refused.
        with pytest.raises(PermissionDeniedError):
            await require_global_actor_for_system_wide_roles(auth, session, actor_user=None, role_ids=role_ids)
        with pytest.raises(PermissionDeniedError):
            await require_global_actor_for_system_wide_roles(
                auth, session, actor_user=None, role_ids=role_ids, auth_result={"source": "unknown"}
            )
        with pytest.raises(PermissionDeniedError):
            await require_global_actor_for_system_wide_roles(
                auth, session, actor_user=world["scoped_admin"], role_ids=role_ids
            )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_enforce_user_scope_false_restores_legacy_direct_role_reach(test_engine, auth_instance, world):
    """The DD-056 transitional escape hatch also restores the unbounded reach."""
    legacy = EnterpriseRBAC(
        engine=test_engine,
        secret_key=SECRET,
        enforce_user_scope=False,
        enable_token_cleanup=False,
    )
    await legacy.initialize()
    try:
        async with legacy.get_session() as session:
            assert await legacy.permission_service.check_permission(
                session, world["scoped_admin"].id, "membership:create_tree", entity_id=world["child_b"].id
            )
    finally:
        await legacy.shutdown()
    async with auth_instance.get_session() as session:
        assert not await auth_instance.permission_service.check_permission(
            session, world["scoped_admin"].id, "membership:create_tree", entity_id=world["child_b"].id
        )


# ---------------------------------------------------------------------------
# Review round 3 (DD-061): direct grants of another tenant's role, dormant
# system-wide grants, and the shared permission catalog
# ---------------------------------------------------------------------------


def _host_app(auth: EnterpriseRBAC) -> FastAPI:
    """The library routers plus host routes guarded by entity-context checks."""
    from fastapi import Depends

    app = _make_app(auth)

    @app.get("/host/tree/{entity_id}")
    async def host_tree(
        entity_id: str,
        _: Any = Depends(auth.require_tree_permission("membership:create_tree", "entity_id")),
    ) -> dict[str, bool]:
        return {"ok": True}

    @app.get("/host/entity/{entity_id}")
    async def host_entity(
        entity_id: str,
        _: Any = Depends(auth.require_entity_permission("user:read", "entity_id")),
    ) -> dict[str, bool]:
        return {"ok": True}

    return app


async def _tenant_b_admin_role(auth: EnterpriseRBAC, world: dict[str, Any]):
    """A tenant-B role whose permission names the tenant-A admin also holds, so
    flat SEC-2 containment alone cannot refuse it."""
    async with auth.get_session() as session:
        role = await _role(
            auth,
            session,
            permissions=["user:read", "membership:read", "membership:create_tree", "entity:read"],
            root_entity_id=world["root_b"].id,
        )
        await session.commit()
    return role


@pytest.mark.integration
@pytest.mark.asyncio
async def test_scoped_admin_cannot_directly_grant_another_tenants_role(auth_instance, world):
    auth = auth_instance
    role_b = await _tenant_b_admin_role(auth, world)
    scoped_admin, user_a = world["scoped_admin"], world["user_a"]
    scoped = _headers(auth, scoped_admin.id)
    child_b = world["child_b"]

    async with _client(_host_app(auth)) as http:
        assert (await http.get(f"/host/tree/{child_b.id}", headers=scoped)).status_code == 403

        # Negative: to itself and to an in-scope user, another tenant's role
        # answers 404 exactly like a nonexistent role.
        to_self = await http.post(
            f"/v1/users/{scoped_admin.id}/roles", headers=scoped, json={"role_id": str(role_b.id)}
        )
        assert to_self.status_code == 404, to_self.text
        to_user = await http.post(f"/v1/users/{user_a.id}/roles", headers=scoped, json={"role_id": str(role_b.id)})
        assert to_user.status_code == 404, to_user.text
        ghost = await http.post(f"/v1/users/{user_a.id}/roles", headers=scoped, json={"role_id": str(uuid.uuid4())})
        assert ghost.status_code == 404
        assert ghost.json() == to_self.json() == to_user.json()

        # Negative: invite without an entity turns role_ids into direct grants.
        email = f"plant-direct-{_suffix()}@example.com"
        invited = await http.post(
            "/v1/auth/invite", headers=scoped, json={"email": email, "role_ids": [str(role_b.id)]}
        )
        assert invited.status_code == 404, invited.text
        async with auth.get_session() as session:
            assert await auth.user_service.get_user_by_email(session, email) is None

        # ... so the host routes and service checks in tenant B stay closed.
        assert (await http.get(f"/host/tree/{child_b.id}", headers=scoped)).status_code == 403
        assert (await http.get(f"/host/entity/{child_b.id}", headers=scoped)).status_code == 403
        async with auth.get_session() as session:
            for user_id in (scoped_admin.id, user_a.id):
                assert not await auth.permission_service.check_permission(
                    session, user_id, "membership:create_tree", entity_id=child_b.id
                )
            roles = await auth.role_service.get_user_roles(session, user_a.id)
            assert role_b.id not in {role.id for role in roles}

        # Positive: the tenant's own role can still be granted directly and
        # reaches the tenant's entities (host routes included).
        async with auth.get_session() as session:
            role_a = await _role(
                auth,
                session,
                permissions=["membership:create_tree", "user:read"],
                root_entity_id=world["root_a"].id,
            )
            await session.commit()
        own = await http.post(f"/v1/users/{user_a.id}/roles", headers=scoped, json={"role_id": str(role_a.id)})
        assert own.status_code == 201, own.text
        user_a_headers = _headers(auth, user_a.id)
        assert (await http.get(f"/host/tree/{world['child_a'].id}", headers=user_a_headers)).status_code == 200
        assert (await http.get(f"/host/tree/{child_b.id}", headers=user_a_headers)).status_code == 403
        own_invite = await http.post(
            "/v1/auth/invite",
            headers=scoped,
            json={"email": f"own-direct-{_suffix()}@example.com", "role_ids": [str(role_a.id)]},
        )
        assert own_invite.status_code == 201, own_invite.text
        assert own_invite.json()["root_entity_id"] == str(world["root_a"].id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_direct_org_roles_only_go_to_users_rooted_in_their_tree(client, auth_instance, world):
    """Service rule for every actor, global ones included (DD-061)."""
    auth = auth_instance
    role_b = await _tenant_b_admin_role(auth, world)
    global_headers = _headers(auth, world["global_admin"].id)
    super_headers = _headers(auth, world["superuser"].id)

    # Negative: a global actor cannot make a tenant-A user a tenant-B role holder.
    for headers in (global_headers, super_headers):
        refused = await client.post(
            f"/v1/users/{world['user_a'].id}/roles", headers=headers, json={"role_id": str(role_b.id)}
        )
        assert refused.status_code == 422, refused.text
        assert refused.json()["details"]["reason"] == "role_root_mismatch"

    async with auth.get_session() as session:
        unrooted = await _user(auth, session, prefix="unrooted-direct")
        await session.commit()
        unrooted_id = unrooted.id
        with pytest.raises(InvalidInputError) as excinfo:
            await auth.role_service.assign_role_to_user(session, user_id=unrooted_id, role_id=role_b.id)
        assert excinfo.value.details["reason"] == "role_root_mismatch"
        await session.rollback()

    # Negative: roles of two organizations cannot be combined on one invitee.
    mixed_email = f"mixed-{_suffix()}@example.com"
    mixed = await client.post(
        "/v1/auth/invite",
        headers=super_headers,
        json={"email": mixed_email, "role_ids": [str(world["member_role_a"].id), str(role_b.id)]},
    )
    assert mixed.status_code == 422, mixed.text
    async with auth.get_session() as session:
        assert await auth.user_service.get_user_by_email(session, mixed_email) is None

    # Positive: a user rooted in the role's tree can hold it; a global
    # inviter's invitee is rooted where its direct roles are; system-wide
    # roles keep going to anyone.
    in_tree = await client.post(
        f"/v1/users/{world['user_b'].id}/roles", headers=global_headers, json={"role_id": str(role_b.id)}
    )
    assert in_tree.status_code == 201, in_tree.text
    invited = await client.post(
        "/v1/auth/invite",
        headers=super_headers,
        json={"email": f"global-direct-{_suffix()}@example.com", "role_ids": [str(role_b.id)]},
    )
    assert invited.status_code == 201, invited.text
    assert invited.json()["root_entity_id"] == str(world["root_b"].id)
    async with auth.get_session() as session:
        await auth.role_service.assign_role_to_user(
            session, user_id=unrooted_id, role_id=world["system_admin_role"].id
        )
        await session.commit()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_reactivating_a_cross_tenant_direct_role_is_refused(client, auth_instance, world):
    """A cross-tree row stored before 0.1.0a35 cannot be granted again."""
    from datetime import datetime, timezone

    from outlabs_auth.models.sql.user_role_membership import UserRoleMembership

    auth = auth_instance
    role_b = await _tenant_b_admin_role(auth, world)
    user_a = world["user_a"]
    async with auth.get_session() as session:
        legacy = UserRoleMembership(
            user_id=user_a.id,
            role_id=role_b.id,
            assigned_at=datetime.now(timezone.utc),
            status=MembershipStatus.ACTIVE,
        )
        session.add(legacy)
        # Permissions the tenant admin holds, so containment passes.
        own_role = await _role(auth, session, permissions=["user:read"], root_entity_id=world["root_a"].id)
        own_membership = await auth.role_service.assign_role_to_user(
            session, user_id=user_a.id, role_id=own_role.id
        )
        await session.commit()

    scoped = _headers(auth, world["scoped_admin"].id)
    path = f"/v1/users/{user_a.id}/role-memberships/{legacy.id}"

    # Positive: cutting access is always allowed, even for a role the tenant
    # admin cannot see.
    suspended = await client.patch(path, headers=scoped, json={"status": "suspended"})
    assert suspended.status_code == 200, suspended.text

    # Negative: re-granting it is refused — 404 for the tenant admin (the role
    # is not visible to it), 422 for a global actor (wrong tree).
    reactivated = await client.patch(path, headers=scoped, json={"status": "active"})
    assert reactivated.status_code == 404, reactivated.text
    by_superuser = await client.patch(path, headers=_headers(auth, world["superuser"].id), json={"status": "active"})
    assert by_superuser.status_code == 422, by_superuser.text
    assert by_superuser.json()["details"]["reason"] == "role_root_mismatch"
    async with auth.get_session() as session:
        assert not await auth.permission_service.check_permission(
            session, user_a.id, "membership:create_tree", entity_id=world["child_b"].id
        )

    # Positive: the tenant's own direct role can still be suspended and
    # reactivated by the tenant admin.
    own_path = f"/v1/users/{user_a.id}/role-memberships/{own_membership.id}"
    assert (await client.patch(own_path, headers=scoped, json={"status": "suspended"})).status_code == 200
    own_again = await client.patch(own_path, headers=scoped, json={"status": "active"})
    assert own_again.status_code == 200, own_again.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_direct_grant_containment_runs_where_the_role_takes_effect(client, auth_instance, world):
    """SEC-2 for a direct org role is evaluated at its root, not flat."""
    auth = auth_instance
    async with auth.get_session() as session:
        # A team-level manager: user:update and lead:read only through a
        # membership at child_a, so flat containment would count lead:read.
        manager = await _user(auth, session, prefix="team-manager", root_entity_id=world["root_a"].id)
        manager_role = await _role(
            auth, session, permissions=["user:read", "user:update", "lead:read"], root_entity_id=world["root_a"].id
        )
        await auth.membership_service.add_member(
            session, entity_id=world["child_a"].id, user_id=manager.id, role_ids=[manager_role.id]
        )
        org_lead_reader = await _role(auth, session, permissions=["lead:read"], root_entity_id=world["root_a"].id)
        await session.commit()

    manager_headers = _headers(auth, manager.id)
    # Negative: the direct role would grant lead:read across the whole tenant,
    # but the manager holds it only at its team.
    refused = await client.post(
        f"/v1/users/{world['user_a'].id}/roles",
        headers=manager_headers,
        json={"role_id": str(org_lead_reader.id)},
    )
    assert refused.status_code == 403, refused.text
    assert refused.json()["details"]["missing_permissions"] == ["lead:read"]

    # Positive: the same role held at the tenant root covers the whole tree,
    # so an org-level manager may grant it.
    async with auth.get_session() as session:
        org_manager = await _user(auth, session, prefix="org-manager", root_entity_id=world["root_a"].id)
        await auth.membership_service.add_member(
            session, entity_id=world["root_a"].id, user_id=org_manager.id, role_ids=[manager_role.id]
        )
        await session.commit()
    allowed = await client.post(
        f"/v1/users/{world['user_a'].id}/roles",
        headers=_headers(auth, org_manager.id),
        json={"role_id": str(org_lead_reader.id)},
    )
    assert allowed.status_code == 201, allowed.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_scoped_admin_cannot_take_over_accounts_with_dormant_system_wide_grants(client, auth_instance, world):
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import update

    from outlabs_auth.models.sql.enums import DefinitionStatus
    from outlabs_auth.models.sql.role import Role
    from outlabs_auth.models.sql.user_role_membership import UserRoleMembership

    auth = auth_instance
    now = datetime.now(timezone.utc)
    accounts: dict[str, Any] = {}
    async with auth.get_session() as session:
        inactive_role = await _role(auth, session, permissions=["user:read"], is_global=True)
        for state in ("scheduled", "suspended", "expired", "revoked", "inactive_definition"):
            account = await _user(auth, session, prefix=f"dormant-{state}", root_entity_id=world["root_a"].id)
            role_id = inactive_role.id if state == "inactive_definition" else world["system_admin_role"].id
            membership = await auth.role_service.assign_role_to_user(
                session,
                user_id=account.id,
                role_id=role_id,
                valid_from=now + timedelta(hours=1) if state == "scheduled" else None,
            )
            if state == "suspended":
                membership.status = MembershipStatus.SUSPENDED
            elif state == "expired":
                membership.valid_from = now - timedelta(days=2)
                membership.valid_until = now - timedelta(days=1)
            elif state == "revoked":
                await auth.role_service.revoke_role_from_user(session, user_id=account.id, role_id=role_id)
            accounts[state] = (account, membership)
        await session.execute(
            update(Role).where(Role.id == inactive_role.id).values(status=DefinitionStatus.INACTIVE)
        )
        await session.commit()

    scoped = _headers(auth, world["scoped_admin"].id)
    for state, (account, _) in accounts.items():
        # None of them is global right now, so the tenant admin can read them ...
        assert (await client.get(f"/v1/users/{account.id}", headers=scoped)).status_code == 200, state
        # ... but every mutation is refused.
        for method, path, body in (
            ("PATCH", f"/v1/users/{account.id}/password", {"new_password": "Takeover123!x"}),
            ("PATCH", f"/v1/users/{account.id}", {"email": f"takeover-{_suffix()}@example.com"}),
            ("PATCH", f"/v1/users/{account.id}/status", {"status": "suspended"}),
        ):
            response = await client.request(method, path, headers=scoped, json=body)
            assert response.status_code == 403, (state, path, response.status_code, response.text)

    # The reviewer's chain: the scheduled grant activates, and the password the
    # tenant admin tried to set never took effect.
    scheduled_account, scheduled_membership = accounts["scheduled"]
    async with auth.get_session() as session:
        await session.execute(
            update(UserRoleMembership)
            .where(UserRoleMembership.id == scheduled_membership.id)
            .values(valid_from=now - timedelta(minutes=1))
        )
        await session.commit()
    login = await client.post("/v1/auth/login", json={"email": scheduled_account.email, "password": "Takeover123!x"})
    assert login.status_code == 401, login.text

    # Positive: ordinary in-tree accounts stay manageable by the tenant admin,
    # and global actors still manage the dormant global accounts.
    ordinary = await client.patch(
        f"/v1/users/{world['user_a'].id}/password", headers=scoped, json={"new_password": "Rotated123!x"}
    )
    assert ordinary.status_code == 204, ordinary.text
    for headers in (_headers(auth, world["global_admin"].id), _headers(auth, world["superuser"].id)):
        by_global = await client.patch(
            f"/v1/users/{accounts['suspended'][0].id}/password", headers=headers, json={"new_password": "Global123!x"}
        )
        assert by_global.status_code == 204, by_global.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_permission_catalog_writes_need_a_global_actor(client, auth_instance, world):
    auth = auth_instance
    catalog_permissions = ("permission:create", "permission:update", "permission:delete")
    async with auth.get_session() as session:
        for name in catalog_permissions:
            await auth.permission_service.create_permission(session, name=name, display_name=name)
        tenant_catalog_role = await _role(
            auth, session, permissions=[*catalog_permissions, "permission:read"], root_entity_id=world["root_a"].id
        )
        await auth.role_service.assign_role_to_user(
            session, user_id=world["scoped_admin"].id, role_id=tenant_catalog_role.id
        )
        catalog_admin = await _user(auth, session, prefix="catalog-admin", root_entity_id=world["root_a"].id)
        global_catalog_role = await _role(
            auth, session, permissions=[*catalog_permissions, "permission:read"], is_global=True
        )
        await auth.role_service.assign_role_to_user(
            session, user_id=catalog_admin.id, role_id=global_catalog_role.id
        )
        lead_read = await auth.permission_service.get_permission_by_name(session, "lead:read")
        lead_delete = await auth.permission_service.get_permission_by_name(session, "lead:delete")
        await session.commit()

    super_headers = _headers(auth, world["superuser"].id)
    condition = await client.post(
        f"/v1/permissions/{lead_read.id}/conditions",
        headers=super_headers,
        json={"attribute": "user.department", "operator": "equals", "value": "sales", "value_type": "string"},
    )
    assert condition.status_code == 201, condition.text
    condition_id = condition.json()["id"]
    group = await client.post(
        f"/v1/permissions/{lead_read.id}/condition-groups", headers=super_headers, json={"operator": "AND"}
    )
    assert group.status_code == 201, group.text
    group_id = group.json()["id"]

    async with auth.get_session() as session:
        tenant_b_before = await auth.permission_service.check_permission(
            session, world["user_b"].id, "lead:read", entity_id=world["child_b"].id
        )

    # Negative: a tenant-scoped holder of permission:* gets 403 on every write
    # to the shared catalog.
    scoped = _headers(auth, world["scoped_admin"].id)
    base = f"/v1/permissions/{lead_read.id}"
    for method, path, body in (
        ("POST", "/v1/permissions/", {"name": f"rogue:{_suffix()}", "display_name": "Rogue"}),
        ("PATCH", base, {"status": "inactive"}),
        ("DELETE", f"/v1/permissions/{lead_delete.id}", None),
        ("POST", f"{base}/conditions", {"attribute": "user.team", "operator": "equals", "value": "y"}),
        ("PATCH", f"{base}/conditions/{condition_id}", {"value": "everyone"}),
        ("DELETE", f"{base}/conditions/{condition_id}", None),
        ("POST", f"{base}/condition-groups", {"operator": "OR"}),
        ("PATCH", f"{base}/condition-groups/{group_id}", {"operator": "OR"}),
        ("DELETE", f"{base}/condition-groups/{group_id}", None),
    ):
        response = await client.request(method, path, headers=scoped, json=body)
        assert response.status_code == 403, (method, path, response.status_code, response.text)

    async with auth.get_session() as session:
        unchanged = await auth.permission_service.get_permission_by_id(session, lead_read.id)
        assert str(getattr(unchanged.status, "value", unchanged.status)) == "active"
        still_there = await auth.permission_service.get_permission_by_id(session, lead_delete.id)
        assert still_there is not None
        assert str(getattr(still_there.status, "value", still_there.status)) == "active"
        assert await auth.permission_service.check_permission(
            session, world["user_b"].id, "lead:read", entity_id=world["child_b"].id
        ) == tenant_b_before
    conditions = await client.get(f"{base}/conditions", headers=scoped)
    assert conditions.status_code == 200, conditions.text  # reads are unchanged
    assert [row["id"] for row in conditions.json()] == [condition_id]
    assert conditions.json()[0]["value"] == "sales"

    # Positive: a global catalog admin (system-wide role) can write.
    catalog = _headers(auth, catalog_admin.id)
    created = await client.post(
        "/v1/permissions/", headers=catalog, json={"name": f"report:{_suffix()}", "display_name": "Report"}
    )
    assert created.status_code == 201, created.text
    updated = await client.patch(
        f"/v1/permissions/{created.json()['id']}", headers=catalog, json={"display_name": "Reports"}
    )
    assert updated.status_code == 200, updated.text
    cond_patch = await client.patch(f"{base}/conditions/{condition_id}", headers=catalog, json={"value": "support"})
    assert cond_patch.status_code == 200, cond_patch.text
    assert (await client.delete(f"{base}/condition-groups/{group_id}", headers=catalog)).status_code == 204
    assert (await client.delete(f"{base}/conditions/{condition_id}", headers=catalog)).status_code == 204
    assert (await client.delete(f"/v1/permissions/{created.json()['id']}", headers=catalog)).status_code == 204
