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
  actors only;
* an account is managed only by the tenant holding its root (decision 16), and
  a move that changes an entity's root fails closed while the moved subtree
  carries access, for every actor (decision 17): a member of a moved subtree
  can no longer plant an account in the destination tenant, and revoked rows
  left behind cannot be re-granted across the tenant boundary;
* a member left in another tenant's tree by a move on an earlier release
  creates no accounts there (``POST /users``) and changes no entity-local
  role defined there, and an unrooted legacy administrator creates no
  accounts at all.
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
    from outlabs_auth.middleware import RequestCacheMiddleware

    app = FastAPI()
    # Production apps get the per-request memo reset from instrument_fastapi;
    # without it the in-process test transport would carry ORM instances from
    # a rolled-back request (a refused move) into the next one.
    app.add_middleware(RequestCacheMiddleware)
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


# ---------------------------------------------------------------------------
# Review round 4 (DD-061 decision 16): visibility through a membership never
# hands an account rooted in another tenant to that tenant
# ---------------------------------------------------------------------------


def _account_mutations(
    user_id: Any,
    *,
    grant_role_id: Any,
    held_role_id: Any,
    role_membership_id: Any,
) -> list[tuple[str, str, Any]]:
    """Every users-router mutation of one account (the DD-056 ``for_mutation`` routes)."""
    base = f"/v1/users/{user_id}"
    return [
        ("PATCH", base, {"first_name": "Owned"}),
        ("PATCH", base, {"email": f"owned-{_suffix()}@example.com"}),
        ("PATCH", f"{base}/password", {"new_password": "Hijacked123!x"}),
        ("PATCH", f"{base}/status", {"status": "suspended"}),
        ("POST", f"{base}/restore", None),
        ("POST", f"{base}/resend-invite", None),
        ("POST", f"{base}/roles", {"role_id": str(grant_role_id)}),
        ("DELETE", f"{base}/roles/{held_role_id}", None),
        ("PATCH", f"{base}/role-memberships/{role_membership_id}", {"status": "suspended"}),
        ("DELETE", f"{base}/sessions/{uuid.uuid4()}", None),
        ("DELETE", f"{base}/sessions", None),
        ("DELETE", f"{base}/api-keys/{uuid.uuid4()}", None),
        ("DELETE", base, None),
    ]


async def _assert_account_untouched(client, auth, user, *, password: str = "TestPass123!") -> None:
    hijacked = await client.post("/v1/auth/login", json={"email": user.email, "password": "Hijacked123!x"})
    assert hijacked.status_code == 401, hijacked.text
    original = await client.post("/v1/auth/login", json={"email": user.email, "password": password})
    assert original.status_code == 200, original.text
    async with auth.get_session() as session:
        current = await auth.user_service.get_user_by_id(session, user.id)
        assert current.email == user.email
        assert current.first_name == user.first_name
        assert str(getattr(current.status, "value", current.status)) == "active"
        assert current.deleted_at is None


async def _insert_legacy_membership(session, *, entity_id, user_id, role_ids=()) -> Any:
    """A membership row as a cross-root entity move from an earlier release left it.

    ``MembershipService.add_member`` refuses a holder rooted in another tree,
    and a root-changing move of a subtree with memberships now fails closed
    (DD-061 decision 17), so the row is written directly.
    """
    from outlabs_auth.models.sql.entity_membership import EntityMembership, EntityMembershipRole

    membership = EntityMembership(entity_id=entity_id, user_id=user_id, status=MembershipStatus.ACTIVE)
    session.add(membership)
    await session.flush()
    for role_id in role_ids:
        session.add(EntityMembershipRole(membership_id=membership.id, role_id=role_id))
    await session.flush()
    return membership


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("destination", ["under_another_root", "to_the_root_level"])
async def test_legacy_cross_root_members_are_not_handed_to_the_new_tenant(client, auth_instance, world, destination):
    """Decision 16 stays as defence in depth for subtrees moved before decision 17."""
    auth = auth_instance
    async with auth.get_session() as session:
        # A tenant-A branch ("organization", so it may also become a root),
        # tenant A's second org admin (direct org role) and a plain member.
        branch = await _entity(
            auth, session, label="branch-a", parent_id=world["root_a"].id, entity_type="organization"
        )
        admin_a2 = await _user(auth, session, prefix="admin-a2", root_entity_id=world["root_a"].id)
        a2_grant = await auth.role_service.assign_role_to_user(
            session, user_id=admin_a2.id, role_id=world["scoped_role"].id
        )
        member_a = await _user(auth, session, prefix="member-a", root_entity_id=world["root_a"].id)
        await session.commit()

    super_headers = _headers(auth, world["superuser"].id)
    if destination == "under_another_root":
        new_root_id = world["root_b"].id
        body = {"new_parent_id": str(new_root_id)}
    else:
        new_root_id = branch.id
        body = {"new_parent_id": None}
    # The (empty) move is allowed; tenant A's members are then placed in the
    # moved subtree the way a populated move on an earlier release left them.
    moved = await client.post(f"/v1/entities/{branch.id}/move", headers=super_headers, json=body)
    assert moved.status_code == 200, moved.text
    async with auth.get_session() as session:
        for account in (admin_a2, member_a):
            await _insert_legacy_membership(
                session, entity_id=branch.id, user_id=account.id, role_ids=[world["member_role_a"].id]
            )
        await session.commit()

    # The destination tenant's admin (direct org role at the new root) and one
    # of its own accounts.
    async with auth.get_session() as session:
        new_admin = await _user(auth, session, prefix="new-tenant-admin", root_entity_id=new_root_id)
        new_admin_role = await _role(auth, session, permissions=ADMIN_PERMISSIONS, root_entity_id=new_root_id)
        await auth.role_service.assign_role_to_user(session, user_id=new_admin.id, role_id=new_admin_role.id)
        new_tenant_user = await _user(auth, session, prefix="new-tenant-user", root_entity_id=new_root_id)
        await session.commit()
    new_admin_headers = _headers(auth, new_admin.id)

    # Tenant A's members are now visible to the destination tenant through
    # their memberships in the moved subtree (reads are unchanged) ...
    for member in (admin_a2, member_a):
        read = await client.get(f"/v1/users/{member.id}", headers=new_admin_headers)
        assert read.status_code == 200, read.text
        assert read.json()["root_entity_id"] == str(world["root_a"].id)

    # ... but the destination tenant cannot modify accounts rooted in tenant A.
    for member, grant in ((admin_a2, a2_grant), (member_a, None)):
        for method, path, payload in _account_mutations(
            member.id,
            grant_role_id=new_admin_role.id,
            held_role_id=world["scoped_role"].id,
            role_membership_id=grant.id if grant is not None else uuid.uuid4(),
        ):
            response = await client.request(method, path, headers=new_admin_headers, json=payload)
            assert response.status_code == 403, (destination, member.email, method, path, response.text)
            assert "own tenant" in response.text, response.text
        # Nor pull them into one of its entities.
        pulled = await client.post(
            "/v1/memberships/",
            headers=new_admin_headers,
            json={"entity_id": str(new_root_id), "user_id": str(member.id), "role_ids": []},
        )
        assert pulled.status_code == 403, pulled.text
        await _assert_account_untouched(client, auth, member)
    async with auth.get_session() as session:
        roles = await auth.role_service.get_user_roles(session, admin_a2.id)
        assert world["scoped_role"].id in {role.id for role in roles}
        memberships, _ = await auth.membership_service.get_user_entities(session, user_id=admin_a2.id)
        assert [membership.entity_id for membership in memberships] == [branch.id]

    # The reverse direction: the destination tenant adds one of its own
    # accounts to the moved entity (positive: still allowed) ...
    added = await client.post(
        "/v1/memberships/",
        headers=new_admin_headers,
        json={"entity_id": str(branch.id), "user_id": str(new_tenant_user.id), "role_ids": []},
    )
    assert added.status_code == 201, added.text
    # ... which tenant A's admin, a member of that entity, can now read but not modify.
    a2_headers = _headers(auth, admin_a2.id)
    assert (await client.get(f"/v1/users/{new_tenant_user.id}", headers=a2_headers)).status_code == 200
    reverse = await client.patch(
        f"/v1/users/{new_tenant_user.id}/password", headers=a2_headers, json={"new_password": "Hijacked123!x"}
    )
    assert reverse.status_code == 403, reverse.text
    await _assert_account_untouched(client, auth, new_tenant_user)

    # Positive: the destination tenant still manages its own accounts, and the
    # memberships of tenant A's accounts in its own entities.
    own = await client.patch(
        f"/v1/users/{new_tenant_user.id}/status", headers=new_admin_headers, json={"status": "suspended"}
    )
    assert own.status_code == 200, own.text
    membership = await client.patch(
        f"/v1/memberships/{branch.id}/{member_a.id}", headers=new_admin_headers, json={"status": "suspended"}
    )
    assert membership.status_code == 200, membership.text

    # Positive: tenant A's admin and global actors still manage the moved members.
    scoped = _headers(auth, world["scoped_admin"].id)
    reset = await client.patch(
        f"/v1/users/{admin_a2.id}/password", headers=scoped, json={"new_password": "Rotated123!x"}
    )
    assert reset.status_code == 204, reset.text
    assert (
        await client.post("/v1/auth/login", json={"email": admin_a2.email, "password": "Rotated123!x"})
    ).status_code == 200
    suspended = await client.patch(f"/v1/users/{member_a.id}/status", headers=scoped, json={"status": "suspended"})
    assert suspended.status_code == 200, suspended.text
    for headers, new_status in (
        (_headers(auth, world["global_admin"].id), "active"),
        (super_headers, "suspended"),
    ):
        by_global = await client.patch(f"/v1/users/{member_a.id}/status", headers=headers, json={"status": new_status})
        assert by_global.status_code == 200, by_global.text
        by_global_reset = await client.patch(
            f"/v1/users/{admin_a2.id}/password", headers=headers, json={"new_password": "Global123!x"}
        )
        assert by_global_reset.status_code == 204, by_global_reset.text


async def _assert_no_account(auth: EnterpriseRBAC, email: str) -> None:
    async with auth.get_session() as session:
        assert await auth.user_service.get_user_by_email(session, email) is None, email


def _assert_root_outside_tenant(response: httpx.Response) -> None:
    assert response.status_code == 403, response.text
    assert response.json()["details"]["reason"] == "root_entity_outside_tenant", response.text


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("destination", ["under_another_root", "to_the_root_level"])
async def test_legacy_cross_root_members_cannot_create_accounts_in_the_new_tenant(
    client, auth_instance, world, destination
):
    """Decision 17 for account creation: a member left in another tenant's tree
    by a cross-root move on an earlier release cannot root a new account there.

    Tenant A's org admin holds ``user:create`` flat (its direct tenant-A role)
    and a roleless legacy membership in the moved branch, so the branch is in
    its scope although it holds no permission there. ``POST /users`` used to
    accept any root in that scope: with the branch promoted to a root, the
    admin created an account of the new tenant with a password it knew, which
    the new tenant then read and managed as its own.
    """
    auth = auth_instance
    async with auth.get_session() as session:
        branch = await _entity(
            auth, session, label="branch-create", parent_id=world["root_a"].id, entity_type="organization"
        )
        await session.commit()
    super_headers = _headers(auth, world["superuser"].id)
    if destination == "under_another_root":
        new_root_id = world["root_b"].id
        body = {"new_parent_id": str(new_root_id)}
    else:
        new_root_id = branch.id
        body = {"new_parent_id": None}
    moved = await client.post(f"/v1/entities/{branch.id}/move", headers=super_headers, json=body)
    assert moved.status_code == 200, moved.text
    async with auth.get_session() as session:
        await _insert_legacy_membership(session, entity_id=branch.id, user_id=world["scoped_admin"].id)
        await session.commit()
    new_admin, _ = await _destination_admin(auth, new_root_id, prefix="new-tenant-admin")
    async with auth.get_session() as session:
        branch_role = await _role(auth, session, permissions=["lead:read"], root_entity_id=new_root_id)
        await session.commit()

    scoped = _headers(auth, world["scoped_admin"].id)
    # The branch is in the admin's scope through the membership (403 for the
    # missing entity:read there, not the 404 of an out-of-scope entity) ...
    assert (await client.get(f"/v1/entities/{branch.id}", headers=scoped)).status_code == 403

    # ... but no account is rooted in the other tenant: not at the moved
    # entity (a root after a promotion) ...
    planted_email = f"planted-{_suffix()}@example.com"
    planted = await client.post(
        "/v1/users/",
        headers=scoped,
        json={"email": planted_email, "password": "Planted123!x", "root_entity_id": str(branch.id)},
    )
    _assert_root_outside_tenant(planted)
    await _assert_no_account(auth, planted_email)
    assert (
        await client.post("/v1/auth/login", json={"email": planted_email, "password": "Planted123!x"})
    ).status_code == 401
    # ... nor at the new tenant's root (outside the admin's scope) ...
    at_new_root_email = f"planted-root-{_suffix()}@example.com"
    at_new_root = await client.post(
        "/v1/users/",
        headers=scoped,
        json={"email": at_new_root_email, "password": "Planted123!x", "root_entity_id": str(new_root_id)},
    )
    assert at_new_root.status_code == 403, at_new_root.text
    await _assert_no_account(auth, at_new_root_email)
    # ... nor through an invitation without an entity, whose invitee is
    # rooted where its direct roles are (the new tenant's role is not visible).
    invite_email = f"planted-invite-{_suffix()}@example.com"
    invited = await client.post(
        "/v1/auth/invite",
        headers=scoped,
        json={"email": invite_email, "role_ids": [str(branch_role.id)]},
    )
    assert invited.status_code in (403, 404), invited.text
    await _assert_no_account(auth, invite_email)

    # The same rule holds for the admin's personal API key: it is judged by
    # its owner's root.
    auth.api_key_policy_service._personal_allowed_action_prefixes.append("create")
    async with auth.get_session() as session:
        key_secret, _ = await auth.api_key_service.create_api_key(
            session,
            owner_id=world["scoped_admin"].id,
            name=f"creator-key-{_suffix()}",
            scopes=["user:create"],
            actor_user_id=world["scoped_admin"].id,
        )
        await session.commit()
    key_email = f"planted-key-{_suffix()}@example.com"
    by_key = await client.post(
        "/v1/users/",
        headers={"X-API-Key": key_secret},
        json={"email": key_email, "password": "Planted123!x", "root_entity_id": str(branch.id)},
    )
    _assert_root_outside_tenant(by_key)
    await _assert_no_account(auth, key_email)

    # The new tenant has no account it did not create.
    new_admin_headers = _headers(auth, new_admin.id)
    listed = await client.get("/v1/users/", headers=new_admin_headers, params={"limit": 100})
    assert listed.status_code == 200, listed.text
    listed_emails = {item["email"] for item in listed.json()["items"]}
    assert not {planted_email, at_new_root_email, invite_email, key_email} & listed_emails

    # Positive: tenant A's admin still creates accounts in its own tenant
    # (named or defaulted root, JWT or key) ...
    for headers in (scoped, {"X-API-Key": key_secret}):
        own = await client.post(
            "/v1/users/",
            headers=headers,
            json={
                "email": f"own-{_suffix()}@example.com",
                "password": "TestPass123!",
                "root_entity_id": str(world["root_a"].id),
            },
        )
        assert own.status_code == 201, own.text
    defaulted = await client.post(
        "/v1/users/", headers=scoped, json={"email": f"own-default-{_suffix()}@example.com", "password": "TestPass123!"}
    )
    assert defaulted.status_code == 201, defaulted.text
    assert defaulted.json()["root_entity_id"] == str(world["root_a"].id)
    # ... and the new tenant's admin and global actors create accounts in the new tenant.
    for headers in (new_admin_headers, _headers(auth, world["global_admin"].id), super_headers):
        created = await client.post(
            "/v1/users/",
            headers=headers,
            json={
                "email": f"new-tenant-{_suffix()}@example.com",
                "password": "TestPass123!",
                "root_entity_id": str(new_root_id),
            },
        )
        assert created.status_code == 201, created.text
        assert created.json()["root_entity_id"] == str(new_root_id)


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("destination", ["under_another_root", "to_the_root_level"])
async def test_legacy_cross_root_members_cannot_change_the_new_tenants_roles(client, auth_instance, world, destination):
    """Decision 17 for role definitions: the roles router checks flat
    permissions, so an entity-local role only had to be in the actor's scope.
    A member left in another tenant's tree could create, rename, strip and
    delete that tenant's roles there with a permission from its own tenant."""
    auth = auth_instance
    async with auth.get_session() as session:
        for name in ("role:create", "role:delete"):
            await auth.permission_service.create_permission(session, name=name, display_name=name)
        await auth.role_service.add_permissions_by_name(
            session, role_id=world["scoped_role"].id, permission_names=["role:create", "role:delete"]
        )
        branch = await _entity(
            auth, session, label="branch-roles", parent_id=world["root_a"].id, entity_type="organization"
        )
        await session.commit()
    super_headers = _headers(auth, world["superuser"].id)
    if destination == "under_another_root":
        new_root_id = world["root_b"].id
        body = {"new_parent_id": str(new_root_id)}
    else:
        new_root_id = branch.id
        body = {"new_parent_id": None}
    moved = await client.post(f"/v1/entities/{branch.id}/move", headers=super_headers, json=body)
    assert moved.status_code == 200, moved.text
    async with auth.get_session() as session:
        await _insert_legacy_membership(session, entity_id=branch.id, user_id=world["scoped_admin"].id)
        # Two of the new tenant's entity-local roles, defined at the branch.
        kept = await _role(
            auth, session, permissions=["lead:read"], root_entity_id=new_root_id, scope_entity_id=branch.id
        )
        doomed = await _role(
            auth, session, permissions=["lead:read"], root_entity_id=new_root_id, scope_entity_id=branch.id
        )
        await session.commit()
    new_admin, _ = await _destination_admin(auth, new_root_id, prefix="new-tenant-admin")

    scoped = _headers(auth, world["scoped_admin"].id)
    # The roles are visible to tenant A's admin through its membership ...
    assert (await client.get(f"/v1/roles/{kept.id}", headers=scoped)).status_code == 200
    # ... but every definition write answers 403.
    planted_name = f"planted-{_suffix()}"
    writes = [
        (
            "POST",
            "/v1/roles/",
            {
                "name": planted_name,
                "display_name": "Planted",
                "permissions": [],
                "is_global": False,
                "root_entity_id": str(new_root_id),
                "scope_entity_id": str(branch.id),
            },
        ),
        ("PATCH", f"/v1/roles/{kept.id}", {"display_name": "Owned"}),
        ("PATCH", f"/v1/roles/{kept.id}", {"permissions": []}),
        ("PATCH", f"/v1/roles/{kept.id}", {"status": "inactive"}),
        ("DELETE", f"/v1/roles/{kept.id}/permissions", ["lead:read"]),
        ("POST", f"/v1/roles/{kept.id}/condition-groups", {"operator": "AND"}),
        (
            "POST",
            f"/v1/roles/{kept.id}/conditions",
            {"attribute": "user.department", "operator": "equals", "value": "x", "value_type": "string"},
        ),
        ("DELETE", f"/v1/roles/{doomed.id}", None),
    ]
    for method, path, payload in writes:
        response = await client.request(method, path, headers=scoped, json=payload)
        assert response.status_code == 403, (destination, method, path, response.text)
    async with auth.get_session() as session:
        current = await auth.role_service.get_role_by_id(session, kept.id)
        assert current.display_name == kept.display_name
        assert str(getattr(current.status, "value", current.status)) == "active"
        assert await auth.role_service.get_role_permission_names(session, kept.id) == ["lead:read"]
        assert await auth.role_service.get_role_by_id(session, doomed.id) is not None
        assert await auth.role_service.get_role_by_name(session, planted_name) is None

    # Positive: the new tenant and global actors still change its roles ...
    renamed = await client.patch(
        f"/v1/roles/{kept.id}", headers=_headers(auth, new_admin.id), json={"display_name": "Renamed"}
    )
    assert renamed.status_code == 200, renamed.text
    deleted = await client.delete(f"/v1/roles/{doomed.id}", headers=super_headers)
    assert deleted.status_code == 204, deleted.text
    # ... and tenant A's admin still manages entity-local roles in its own tree.
    own = await client.post(
        "/v1/roles/",
        headers=scoped,
        json={
            "name": f"own-{_suffix()}",
            "display_name": "Own",
            "permissions": ["user:read"],
            "is_global": False,
            "root_entity_id": str(world["root_a"].id),
            "scope_entity_id": str(world["child_a"].id),
        },
    )
    assert own.status_code == 201, own.text
    own_id = own.json()["id"]
    assert (
        await client.patch(f"/v1/roles/{own_id}", headers=scoped, json={"display_name": "Own renamed"})
    ).status_code == 200
    assert (await client.delete(f"/v1/roles/{own_id}", headers=scoped)).status_code == 204


@pytest.mark.integration
@pytest.mark.asyncio
async def test_unrooted_legacy_admins_create_no_accounts(client, auth_instance, world):
    """An unrooted actor has no tenant (decisions 16 and 17), so it roots no
    new account anywhere — not even where a legacy membership in another
    tenant's moved subtree puts a root in its scope."""
    from sqlalchemy import update

    from outlabs_auth.models.sql.user import User

    auth = auth_instance
    async with auth.get_session() as session:
        branch = await _entity(
            auth, session, label="branch-unrooted", parent_id=world["root_a"].id, entity_type="organization"
        )
        # A legacy administrator: tenant A's admin role through a membership
        # at tenant A's root, but rooted nowhere (add_member roots it, so
        # clear the root afterwards).
        legacy_admin = await _user(auth, session, prefix="legacy-admin")
        await auth.membership_service.add_member(
            session, entity_id=world["root_a"].id, user_id=legacy_admin.id, role_ids=[world["scoped_role"].id]
        )
        await session.execute(update(User).where(User.id == legacy_admin.id).values(root_entity_id=None))
        await session.commit()
    promoted = await client.post(
        f"/v1/entities/{branch.id}/move", headers=_headers(auth, world["superuser"].id), json={"new_parent_id": None}
    )
    assert promoted.status_code == 200, promoted.text
    async with auth.get_session() as session:
        await _insert_legacy_membership(session, entity_id=branch.id, user_id=legacy_admin.id)
        await session.commit()

    legacy_headers = _headers(auth, legacy_admin.id)
    for root_id in (branch.id, world["root_a"].id):
        email = f"unrooted-created-{_suffix()}@example.com"
        refused = await client.post(
            "/v1/users/",
            headers=legacy_headers,
            json={"email": email, "password": "TestPass123!", "root_entity_id": str(root_id)},
        )
        _assert_root_outside_tenant(refused)
        await _assert_no_account(auth, email)
    unnamed_email = f"unrooted-unnamed-{_suffix()}@example.com"
    unnamed = await client.post(
        "/v1/users/", headers=legacy_headers, json={"email": unnamed_email, "password": "TestPass123!"}
    )
    assert unnamed.status_code == 403, unnamed.text
    assert unnamed.json()["details"]["reason"] == "root_entity_required", unnamed.text
    await _assert_no_account(auth, unnamed_email)

    # Positive: once a global actor roots it, it creates accounts in its tenant.
    async with auth.get_session() as session:
        await session.execute(update(User).where(User.id == legacy_admin.id).values(root_entity_id=world["root_a"].id))
        await session.commit()
    rooted = await client.post(
        "/v1/users/",
        headers=legacy_headers,
        json={
            "email": f"rooted-created-{_suffix()}@example.com",
            "password": "TestPass123!",
            "root_entity_id": str(world["root_a"].id),
        },
    )
    assert rooted.status_code == 201, rooted.text
    still_refused = await client.post(
        "/v1/users/",
        headers=legacy_headers,
        json={
            "email": f"still-refused-{_suffix()}@example.com",
            "password": "TestPass123!",
            "root_entity_id": str(branch.id),
        },
    )
    _assert_root_outside_tenant(still_refused)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_membership_only_visibility_is_read_only_for_tenant_admins(client, auth_instance, world):
    from sqlalchemy import update

    from outlabs_auth.models.sql.user import User

    auth = auth_instance
    async with auth.get_session() as session:
        # An account that predates the root rule: a member of tenant A's team
        # but rooted nowhere (add_member roots it, so clear the root afterwards).
        legacy = await _user(auth, session, prefix="legacy")
        await auth.membership_service.add_member(session, entity_id=world["child_a"].id, user_id=legacy.id, role_ids=[])
        await session.execute(update(User).where(User.id == legacy.id).values(root_entity_id=None))
        await session.commit()
        legacy = await auth.user_service.get_user_by_id(session, legacy.id)
        assert legacy.root_entity_id is None

    scoped = _headers(auth, world["scoped_admin"].id)
    # Visible through its membership ...
    assert (await client.get(f"/v1/users/{legacy.id}", headers=scoped)).status_code == 200
    # ... but read-only for the tenant admin: no takeover ...
    for method, path, payload in _account_mutations(
        legacy.id,
        grant_role_id=world["member_role_a"].id,
        held_role_id=world["member_role_a"].id,
        role_membership_id=uuid.uuid4(),
    ):
        response = await client.request(method, path, headers=scoped, json=payload)
        assert response.status_code == 403, (method, path, response.text)
    await _assert_account_untouched(client, auth, legacy)
    # ... and no adoption: POST /memberships would root it in tenant A.
    adopt = await client.post(
        "/v1/memberships/",
        headers=scoped,
        json={"entity_id": str(world["root_a"].id), "user_id": str(legacy.id), "role_ids": []},
    )
    assert adopt.status_code == 403, adopt.text
    async with auth.get_session() as session:
        assert (await auth.user_service.get_user_by_id(session, legacy.id)).root_entity_id is None

    # Positive: the account still manages itself.
    self_update = await client.patch("/v1/users/me", headers=_headers(auth, legacy.id), json={"first_name": "Self"})
    assert self_update.status_code == 200, self_update.text

    # Positive: a global actor manages and adopts it.
    global_headers = _headers(auth, world["global_admin"].id)
    by_global = await client.patch(
        f"/v1/users/{legacy.id}/password", headers=global_headers, json={"new_password": "Global123!x"}
    )
    assert by_global.status_code == 204, by_global.text
    adopted = await client.post(
        "/v1/memberships/",
        headers=global_headers,
        json={"entity_id": str(world["root_a"].id), "user_id": str(legacy.id), "role_ids": []},
    )
    assert adopted.status_code == 201, adopted.text
    async with auth.get_session() as session:
        assert (await auth.user_service.get_user_by_id(session, legacy.id)).root_entity_id == world["root_a"].id

    # Once rooted in tenant A, the tenant admin manages it like any other account.
    managed = await client.patch(f"/v1/users/{legacy.id}/status", headers=scoped, json={"status": "suspended"})
    assert managed.status_code == 200, managed.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_anchored_personal_keys_add_members_of_their_owners_tenant_only(client, auth_instance, world):
    from sqlalchemy import update

    from outlabs_auth.models.sql.user import User

    auth = auth_instance
    # A host that lets personal keys create memberships.
    auth.api_key_policy_service._personal_allowed_action_prefixes.append("create")
    async with auth.get_session() as session:
        legacy = await _user(auth, session, prefix="legacy-member")
        await auth.membership_service.add_member(session, entity_id=world["child_a"].id, user_id=legacy.id, role_ids=[])
        await session.execute(update(User).where(User.id == legacy.id).values(root_entity_id=None))
        secret, _ = await auth.api_key_service.create_api_key(
            session,
            owner_id=world["scoped_admin"].id,
            name=f"team-key-{_suffix()}",
            scopes=["membership:create_tree"],
            entity_id=world["child_a"].id,
            actor_user_id=world["scoped_admin"].id,
        )
        await session.commit()
    key = {"X-API-Key": secret}

    # Positive: the anchor narrows where the key acts, not whose accounts its
    # owner's tenant manages, so a tenant-A member of the anchor is accepted
    # although its root lies outside the anchor's subtree.
    own = await client.post(
        "/v1/memberships/",
        headers=key,
        json={"entity_id": str(world["child_a"].id), "user_id": str(world["user_a"].id), "role_ids": []},
    )
    assert own.status_code == 201, own.text

    # Negative: an account seen only through its membership is not adopted.
    adopt = await client.post(
        "/v1/memberships/",
        headers=key,
        json={"entity_id": str(world["child_a"].id), "user_id": str(legacy.id), "role_ids": []},
    )
    assert adopt.status_code == 403, adopt.text
    async with auth.get_session() as session:
        assert (await auth.user_service.get_user_by_id(session, legacy.id)).root_entity_id is None


# ---------------------------------------------------------------------------
# Review round 5 (DD-061 decision 17): a move that changes an entity's root
# fails closed while the moved subtree carries access
# ---------------------------------------------------------------------------


def _assert_move_carries_access(response: httpx.Response, **minimums: int) -> dict[str, int]:
    assert response.status_code == 422, response.text
    from outlabs_auth.services.entity import SUBTREE_ACCESS_CATEGORIES

    body = response.json()
    assert body["error"] == "ENTITY_MOVE_CARRIES_ACCESS", body
    assert body["details"]["reason"] == "cross_root_move_carries_access", body
    access = body["details"]["access"]
    assert set(access) == set(SUBTREE_ACCESS_CATEGORIES), access
    for category, minimum in minimums.items():
        assert access[category] >= minimum, (category, access)
    return access


async def _destination_admin(
    auth: EnterpriseRBAC,
    root_id: Any,
    *,
    prefix: str = "dest-admin",
    permissions: tuple[str, ...] = (*ADMIN_PERMISSIONS, "lead:read"),
):
    """An org admin of the destination tenant (direct org role at its root)."""
    async with auth.get_session() as session:
        admin = await _user(auth, session, prefix=prefix, root_entity_id=root_id)
        role = await _role(auth, session, permissions=permissions, root_entity_id=root_id)
        await auth.role_service.assign_role_to_user(session, user_id=admin.id, role_id=role.id)
        await session.commit()
    return admin, role


async def _root_of(auth: EnterpriseRBAC, entity_id: Any) -> Any:
    async with auth.get_session() as session:
        return await auth.entity_service.get_root_entity_id(session, entity_id)


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("destination", ["under_another_root", "to_the_root_level"])
async def test_populated_cross_root_move_is_refused_for_every_actor(client, auth_instance, world, destination):
    from outlabs_auth.core.exceptions import EntityMoveCarriesAccessError

    auth = auth_instance
    async with auth.get_session() as session:
        branch = await _entity(
            auth, session, label="branch-a", parent_id=world["root_a"].id, entity_type="organization"
        )
        admin_a2 = await _user(auth, session, prefix="admin-a2", root_entity_id=world["root_a"].id)
        await auth.role_service.assign_role_to_user(session, user_id=admin_a2.id, role_id=world["scoped_role"].id)
        member_a = await _user(auth, session, prefix="member-a", root_entity_id=world["root_a"].id)
        for account in (admin_a2, member_a):
            await auth.membership_service.add_member(
                session, entity_id=branch.id, user_id=account.id, role_ids=[world["member_role_a"].id]
            )
        await session.commit()

        # The global admin also gets the tree-create permission a move under
        # a new parent needs, so only decision 17 can refuse it.
        await auth.permission_service.create_permission(
            session, name="entity:create_tree", display_name="entity:create_tree"
        )
        tree_role = await _role(auth, session, permissions=["entity:create_tree"], is_global=True)
        await auth.role_service.assign_role_to_user(session, user_id=world["global_admin"].id, role_id=tree_role.id)
        await session.commit()

    new_parent_id = world["root_b"].id if destination == "under_another_root" else None
    body = {"new_parent_id": str(new_parent_id) if new_parent_id else None}
    for actor in ("superuser", "global_admin"):
        refused = await client.post(
            f"/v1/entities/{branch.id}/move", headers=_headers(auth, world[actor].id), json=body
        )
        access = _assert_move_carries_access(refused, memberships=2)
        assert access["accounts"] == 0 and access["api_keys"] == 0
    # The service refuses it for direct callers too.
    async with auth.get_session() as session:
        with pytest.raises(EntityMoveCarriesAccessError) as excinfo:
            await auth.entity_service.move_entity(session, branch.id, new_parent_id, moved_by_id=world["superuser"].id)
        assert excinfo.value.status_code == 422
        assert excinfo.value.details["access"]["memberships"] == 2
        await session.rollback()

    # Nothing moved: the branch and its members stay in tenant A.
    assert await _root_of(auth, branch.id) == world["root_a"].id
    async with auth.get_session() as session:
        assert (await auth.entity_service.get_entity(session, branch.id)).parent_id == world["root_a"].id

    # The round-3 probe is now impossible: tenant B's admin can neither see
    # nor take over the branch's members ...
    b_admin, _ = await _destination_admin(auth, world["root_b"].id)
    b_headers = _headers(auth, b_admin.id)
    for member in (admin_a2, member_a):
        assert (await client.get(f"/v1/users/{member.id}", headers=b_headers)).status_code == 404
        hijack = await client.patch(
            f"/v1/users/{member.id}/password", headers=b_headers, json={"new_password": "Hijacked123!x"}
        )
        assert hijack.status_code == 404, hijack.text
        await _assert_account_untouched(client, auth, member)
    assert (await client.get(f"/v1/entities/{branch.id}", headers=b_headers)).status_code == 404

    # ... while tenant A still manages them, and moves inside tenant A work.
    scoped = _headers(auth, world["scoped_admin"].id)
    reset = await client.patch(
        f"/v1/users/{admin_a2.id}/password", headers=scoped, json={"new_password": "Rotated123!x"}
    )
    assert reset.status_code == 204, reset.text
    same_root = await client.post(
        f"/v1/entities/{branch.id}/move",
        headers=_headers(auth, world["superuser"].id),
        json={"new_parent_id": str(world["child_a"].id)},
    )
    assert same_root.status_code == 200, same_root.text
    assert await _root_of(auth, branch.id) == world["root_a"].id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_root_demotion_is_refused_while_accounts_are_rooted_there(client, auth_instance, world):
    auth = auth_instance
    super_headers = _headers(auth, world["superuser"].id)
    async with auth.get_session() as session:
        # A small tenant whose only access is an account rooted at it.
        tenant_c = await _entity(auth, session, label="tenant-c")
        team_c = await _entity(auth, session, label="team-c", parent_id=tenant_c.id)
        account_c = await _user(auth, session, prefix="account-c", root_entity_id=tenant_c.id)
        # An empty tenant with an entity-local role definition (no holders).
        tenant_d = await _entity(auth, session, label="tenant-d")
        team_d = await _entity(auth, session, label="team-d", parent_id=tenant_d.id)
        local_role_d = await _role(auth, session, permissions=["lead:read"], scope_entity_id=team_d.id)
        await session.commit()
    assert local_role_d.root_entity_id == tenant_d.id

    # Demoting a root that holds accounts would hand them to the containing
    # tenant (an account belongs to the tenant whose tree holds its root).
    refused = await client.post(
        f"/v1/entities/{tenant_c.id}/move", headers=super_headers, json={"new_parent_id": str(world["root_b"].id)}
    )
    access = _assert_move_carries_access(refused, accounts=1)
    assert access["memberships"] == 0
    b_admin, _ = await _destination_admin(auth, world["root_b"].id)
    assert (await client.get(f"/v1/users/{account_c.id}", headers=_headers(auth, b_admin.id))).status_code == 404

    # The operator path: move the (empty) children instead; the root keeps its accounts.
    moved_child = await client.post(
        f"/v1/entities/{team_c.id}/move", headers=super_headers, json={"new_parent_id": str(world["root_b"].id)}
    )
    assert moved_child.status_code == 200, moved_child.text
    assert await _root_of(auth, team_c.id) == world["root_b"].id
    assert await _root_of(auth, tenant_c.id) == tenant_c.id

    # An empty root can be demoted; its entity-local role definitions follow
    # their scope entity into the destination organization.
    demoted = await client.post(
        f"/v1/entities/{tenant_d.id}/move", headers=super_headers, json={"new_parent_id": str(world["root_b"].id)}
    )
    assert demoted.status_code == 200, demoted.text
    assert await _root_of(auth, team_d.id) == world["root_b"].id
    async with auth.get_session() as session:
        role = await auth.role_service.get_role_by_id(session, local_role_d.id)
        assert role.root_entity_id == world["root_b"].id


async def _grant_access_in_branch(auth: EnterpriseRBAC, client, world, branch, kind: str) -> dict[str, Any]:
    """Give ``branch`` one kind of access; return what the operator revokes."""
    from outlabs_auth.models.sql.enums import IntegrationPrincipalScopeKind
    from outlabs_auth.models.sql.user_role_membership import UserRoleMembership

    scoped = _headers(auth, world["scoped_admin"].id)
    async with auth.get_session() as session:
        holder = await _user(auth, session, prefix=f"holder-{kind}", root_entity_id=world["root_a"].id)
        await session.commit()
    if kind in ("membership", "suspended_membership"):
        async with auth.get_session() as session:
            await auth.membership_service.add_member(
                session,
                entity_id=branch.id,
                user_id=holder.id,
                role_ids=[world["member_role_a"].id],
                status=MembershipStatus.SUSPENDED if kind == "suspended_membership" else MembershipStatus.ACTIVE,
            )
            await session.commit()
        return {"category": "memberships", "membership_user_id": holder.id}
    if kind == "pending_invitation":
        invited = await client.post(
            "/v1/auth/invite",
            headers=scoped,
            json={"email": f"pending-{_suffix()}@example.com", "entity_id": str(branch.id), "role_ids": []},
        )
        assert invited.status_code == 201, invited.text
        assert invited.json()["status"] == "invited"
        return {"category": "pending_invitations", "membership_user_id": invited.json()["id"]}
    if kind == "api_key":
        async with auth.get_session() as session:
            _, api_key = await auth.api_key_service.create_api_key(
                session,
                owner_id=world["scoped_admin"].id,
                name=f"branch-key-{_suffix()}",
                scopes=["user:read"],
                entity_id=branch.id,
                actor_user_id=world["scoped_admin"].id,
            )
            await session.commit()
        return {"category": "api_keys", "api_key_id": api_key.id}
    if kind == "integration_principal":
        async with auth.get_session() as session:
            principal = await auth.integration_principal_service.create_principal(
                session,
                name=f"branch-bot-{_suffix()}",
                description=None,
                scope_kind=IntegrationPrincipalScopeKind.ENTITY,
                anchor_entity_id=branch.id,
                inherit_from_tree=False,
                allowed_scopes=["lead:read"],
                created_by_user_id=world["superuser"].id,
            )
            await session.commit()
        return {"category": "integration_principals", "principal_id": principal.id}
    # Role assignments anchored in the branch: an entity-local role defined
    # there, held by an integration principal anchored elsewhere in tenant A,
    # or (rows from before entity-local direct grants were refused) directly.
    async with auth.get_session() as session:
        local_role = await _role(auth, session, permissions=["lead:read"], scope_entity_id=branch.id)
        if kind == "principal_role":
            principal = await auth.integration_principal_service.create_principal(
                session,
                name=f"tenant-bot-{_suffix()}",
                description=None,
                scope_kind=IntegrationPrincipalScopeKind.ENTITY,
                anchor_entity_id=world["root_a"].id,
                inherit_from_tree=True,
                allowed_scopes=[],
                role_ids=[local_role.id],
                created_by_user_id=world["superuser"].id,
            )
            await session.commit()
            return {"category": "role_assignments", "principal_id": principal.id}
        grant = UserRoleMembership(user_id=holder.id, role_id=local_role.id, status=MembershipStatus.ACTIVE)
        session.add(grant)
        await session.commit()
        return {"category": "role_assignments", "direct_grant": (holder.id, grant.id)}


async def _revoke_access_in_branch(auth: EnterpriseRBAC, client, world, branch, granted: dict[str, Any]) -> None:
    """The documented operator step: revoke or archive the access first."""
    scoped = _headers(auth, world["scoped_admin"].id)
    if "membership_user_id" in granted:
        removed = await client.delete(
            f"/v1/memberships/{branch.id}/{granted['membership_user_id']}",
            headers=_headers(auth, world["superuser"].id),
        )
        assert removed.status_code == 204, removed.text
    elif "api_key_id" in granted:
        revoked = await client.delete(f"/v1/api-keys/{granted['api_key_id']}", headers=scoped)
        assert revoked.status_code == 204, revoked.text
    elif "principal_id" in granted:
        async with auth.get_session() as session:
            assert await auth.integration_principal_service.archive_principal(
                session, granted["principal_id"], actor_user_id=world["superuser"].id
            )
            await session.commit()
    else:
        user_id, grant_id = granted["direct_grant"]
        revoked = await client.patch(
            f"/v1/users/{user_id}/role-memberships/{grant_id}", headers=scoped, json={"status": "revoked"}
        )
        assert revoked.status_code == 200, revoked.text


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind",
    [
        "membership",
        "suspended_membership",
        "pending_invitation",
        "api_key",
        "integration_principal",
        "principal_role",
        "direct_role",
    ],
)
async def test_each_kind_of_access_blocks_a_cross_root_move_until_revoked(client, auth_instance, world, kind):
    auth = auth_instance
    super_headers = _headers(auth, world["superuser"].id)
    async with auth.get_session() as session:
        branch = await _entity(auth, session, label=f"branch-{kind}", parent_id=world["root_a"].id)
        await session.commit()
    granted = await _grant_access_in_branch(auth, client, world, branch, kind)
    body = {"new_parent_id": str(world["root_b"].id)}

    refused = await client.post(f"/v1/entities/{branch.id}/move", headers=super_headers, json=body)
    _assert_move_carries_access(refused, **{granted["category"]: 1})
    async with auth.get_session() as session:
        assert (await auth.entity_service.get_subtree_access(session, branch.id))[granted["category"]] >= 1
    assert await _root_of(auth, branch.id) == world["root_a"].id

    await _revoke_access_in_branch(auth, client, world, branch, granted)
    async with auth.get_session() as session:
        assert not any((await auth.entity_service.get_subtree_access(session, branch.id)).values())
    moved = await client.post(f"/v1/entities/{branch.id}/move", headers=super_headers, json=body)
    assert moved.status_code == 200, moved.text
    assert await _root_of(auth, branch.id) == world["root_b"].id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_empty_subtree_moves_across_roots_and_hands_over_nothing(client, auth_instance, world):
    auth = auth_instance
    super_headers = _headers(auth, world["superuser"].id)
    async with auth.get_session() as session:
        branch = await _entity(auth, session, label="branch-empty", parent_id=world["root_a"].id)
        leaf = await _entity(auth, session, label="leaf-empty", parent_id=branch.id)
        # An auto-assigned entity-local role (a definition, not access).
        auto_role = await _role(
            auth,
            session,
            permissions=["lead:read"],
            scope_entity_id=branch.id,
            scope=RoleScope.HIERARCHY,
            is_auto_assigned=True,
        )
        # A former tenant-A member whose membership was revoked.
        former = await _user(auth, session, prefix="former-a", root_entity_id=world["root_a"].id)
        await auth.membership_service.add_member(
            session, entity_id=leaf.id, user_id=former.id, role_ids=[world["member_role_a"].id]
        )
        await auth.membership_service.remove_member(session, entity_id=leaf.id, user_id=former.id)
        await session.commit()

    moved = await client.post(
        f"/v1/entities/{branch.id}/move", headers=super_headers, json={"new_parent_id": str(world["root_b"].id)}
    )
    assert moved.status_code == 200, moved.text
    assert await _root_of(auth, leaf.id) == world["root_b"].id
    async with auth.get_session() as session:
        role = await auth.role_service.get_role_by_id(session, auto_role.id)
        assert role.root_entity_id == world["root_b"].id
        events, _ = await auth.user_audit_service.list_events(
            session, page=1, limit=10, event_category="entity", entity_id=branch.id
        )
    moved_event = next(event for event in events if event.event_type == "entity.moved")
    assert moved_event.event_metadata["changes_root"] is True
    assert moved_event.event_metadata["previous_root_entity_id"] == str(world["root_a"].id)
    assert moved_event.event_metadata["reanchored_role_ids"] == [str(auto_role.id)]
    assert moved_event.root_entity_id == world["root_b"].id

    # Tenant B now owns the branch: it reads it and adds its own members,
    # and the re-anchored auto-assigned role applies to them.
    b_admin, _ = await _destination_admin(auth, world["root_b"].id)
    b_headers = _headers(auth, b_admin.id)
    assert (await client.get(f"/v1/entities/{leaf.id}", headers=b_headers)).status_code == 200
    added = await client.post(
        "/v1/memberships/",
        headers=b_headers,
        json={"entity_id": str(leaf.id), "user_id": str(world["user_b"].id), "role_ids": []},
    )
    assert added.status_code == 201, added.text
    assert str(auto_role.id) in added.json()["role_ids"]

    # Tenant A lost the branch and nothing in it.
    scoped = _headers(auth, world["scoped_admin"].id)
    assert (await client.get(f"/v1/entities/{branch.id}", headers=scoped)).status_code == 404

    # The revoked tenant-A membership cannot be brought back into tenant B,
    # by the destination admin or a superuser (add_member's root rule).
    for headers in (b_headers, super_headers):
        revived = await client.patch(
            f"/v1/memberships/{leaf.id}/{former.id}", headers=headers, json={"status": "active"}
        )
        assert revived.status_code == 422, revived.text
        assert revived.json()["details"]["reason"] == "membership_root_mismatch"
    assert (await client.get(f"/v1/users/{former.id}", headers=b_headers)).status_code == 404
    async with auth.get_session() as session:
        with pytest.raises(InvalidInputError):
            await auth.membership_service.reactivate_membership(session, leaf.id, former.id)
        await session.rollback()
        membership = await auth.membership_service.get_member(session, leaf.id, former.id)
        assert membership.status == MembershipStatus.REVOKED

    # Promoting an empty organization-type branch to a root is allowed too.
    async with auth.get_session() as session:
        spin_off = await _entity(
            auth, session, label="spin-off", parent_id=world["root_a"].id, entity_type="organization"
        )
        await session.commit()
    promoted = await client.post(
        f"/v1/entities/{spin_off.id}/move", headers=super_headers, json={"new_parent_id": None}
    )
    assert promoted.status_code == 200, promoted.text
    assert await _root_of(auth, spin_off.id) == spin_off.id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_root_changing_moves_need_a_global_actor(client, auth_instance, world):
    """A tenant admin whose scope reaches another tree (a membership left there
    by an earlier release) still cannot re-root a subtree."""
    auth = auth_instance
    async with auth.get_session() as session:
        team = await _entity(auth, session, label="team-to-move", parent_id=world["root_a"].id)
        await _insert_legacy_membership(session, entity_id=world["child_b"].id, user_id=world["scoped_admin"].id)
        # Tenant A's admin may also create below its entities, so only the
        # root rule can refuse the cross-root move.
        await auth.permission_service.create_permission(
            session, name="entity:create_tree", display_name="entity:create_tree"
        )
        tree_role = await _role(auth, session, permissions=["entity:create_tree"], root_entity_id=world["root_a"].id)
        await auth.role_service.assign_role_to_user(session, user_id=world["scoped_admin"].id, role_id=tree_role.id)
        await session.commit()
    scoped = _headers(auth, world["scoped_admin"].id)
    cross = await client.post(
        f"/v1/entities/{team.id}/move", headers=scoped, json={"new_parent_id": str(world["child_b"].id)}
    )
    assert cross.status_code == 403, cross.text
    assert "another root" in cross.text
    assert await _root_of(auth, team.id) == world["root_a"].id

    # Positive: the same actor still moves the team inside its own tenant.
    within = await client.post(
        f"/v1/entities/{team.id}/move", headers=scoped, json={"new_parent_id": str(world["child_a"].id)}
    )
    assert within.status_code == 200, within.text


async def _attempt_invite_takeover(client, auth, *, inviter, entity_id, role_id, victim, captured) -> bool:
    """Round-4 chain: invite an account into ``entity_id`` with ``role_id``,
    accept the invitation and reset ``victim``'s password with it.

    Returns whether the takeover succeeded.
    """
    email = f"planted-{_suffix()}@example.com"
    invited = await client.post(
        "/v1/auth/invite",
        headers=_headers(auth, inviter.id),
        json={"email": email, "entity_id": str(entity_id), "role_ids": [str(role_id)]},
    )
    if invited.status_code != 201:
        async with auth.get_session() as session:
            assert await auth.user_service.get_user_by_email(session, email) is None
        return False
    accepted = await client.post(
        "/v1/auth/accept-invite", json={"token": captured[email], "new_password": "Planted123!x"}
    )
    assert accepted.status_code == 200, accepted.text
    planted = {"Authorization": f"Bearer {accepted.json()['access_token']}"}
    reset = await client.patch(
        f"/v1/users/{victim.id}/password", headers=planted, json={"new_password": "Hijacked123!x"}
    )
    return reset.status_code == 204


@pytest.mark.integration
@pytest.mark.asyncio
async def test_moved_subtree_member_cannot_plant_an_account_in_the_destination(client, auth_instance, world):
    """Round-4 escalation: a member of a moved subtree invites a new account
    into the destination tenant and resets the destination org admin's
    password with it."""
    auth = auth_instance
    captured: dict[str, str] = {}

    async def capture_invite(user, token, request=None):
        captured[user.email] = token

    auth.user_service.on_after_invite = capture_invite
    super_headers = _headers(auth, world["superuser"].id)
    async with auth.get_session() as session:
        branch = await _entity(auth, session, label="branch-r4", parent_id=world["root_a"].id)
        # A tenant-A member holding tenant A's admin role in the branch.
        mover = await _user(auth, session, prefix="mover", root_entity_id=world["root_a"].id)
        await auth.membership_service.add_member(
            session, entity_id=branch.id, user_id=mover.id, role_ids=[world["scoped_role"].id]
        )
        await session.commit()
    # Tenant B's org admin holds the same permission names as tenant A's
    # admin role, so SEC-2 containment alone does not stop the mover from
    # handing out tenant B's role.
    b_admin, b_admin_role = await _destination_admin(
        auth, world["root_b"].id, prefix="b-org-admin", permissions=ADMIN_PERMISSIONS
    )
    body = {"new_parent_id": str(world["root_b"].id)}

    # The move that started the chain is refused ...
    _assert_move_carries_access(
        await client.post(f"/v1/entities/{branch.id}/move", headers=super_headers, json=body), memberships=1
    )
    # ... so the member can only invite into tenant A, where tenant B's role
    # is not available.
    assert not await _attempt_invite_takeover(
        client, auth, inviter=mover, entity_id=branch.id, role_id=b_admin_role.id, victim=b_admin, captured=captured
    )
    assert not await _attempt_invite_takeover(
        client,
        auth,
        inviter=mover,
        entity_id=world["child_b"].id,
        role_id=b_admin_role.id,
        victim=b_admin,
        captured=captured,
    )
    await _assert_account_untouched(client, auth, b_admin)

    # The operator procedure: revoke the branch's access, move it, re-grant
    # in the destination. The former member gains nothing in tenant B.
    assert (await client.delete(f"/v1/memberships/{branch.id}/{mover.id}", headers=super_headers)).status_code == 204
    moved = await client.post(f"/v1/entities/{branch.id}/move", headers=super_headers, json=body)
    assert moved.status_code == 200, moved.text
    assert not await _attempt_invite_takeover(
        client, auth, inviter=mover, entity_id=branch.id, role_id=b_admin_role.id, victim=b_admin, captured=captured
    )
    for headers in (_headers(auth, b_admin.id), super_headers):
        revived = await client.patch(
            f"/v1/memberships/{branch.id}/{mover.id}", headers=headers, json={"status": "active"}
        )
        assert revived.status_code == 422, revived.text
    await _assert_account_untouched(client, auth, b_admin)

    # Positive: tenant B grants access in its new branch to its own accounts.
    regrant = await client.post(
        "/v1/memberships/",
        headers=_headers(auth, b_admin.id),
        json={"entity_id": str(branch.id), "user_id": str(world["user_b"].id), "role_ids": []},
    )
    assert regrant.status_code == 201, regrant.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_legacy_cross_root_members_cannot_grant_access_in_the_destination(client, auth_instance, world):
    """Decision 17 defence in depth for subtrees moved before this release: a
    member left in another tenant's tree cannot invite into it or hand out
    roles there."""
    auth = auth_instance
    captured: dict[str, str] = {}

    async def capture_invite(user, token, request=None):
        captured[user.email] = token

    auth.user_service.on_after_invite = capture_invite
    async with auth.get_session() as session:
        branch = await _entity(auth, session, label="branch-legacy", parent_id=world["root_a"].id)
        mover = await _user(auth, session, prefix="legacy-mover", root_entity_id=world["root_a"].id)
        await session.commit()
    moved = await client.post(
        f"/v1/entities/{branch.id}/move",
        headers=_headers(auth, world["superuser"].id),
        json={"new_parent_id": str(world["root_b"].id)},
    )
    assert moved.status_code == 200, moved.text
    # Tenant B's org admin holds the same permission names as tenant A's
    # admin role, so SEC-2 containment alone does not stop the mover from
    # handing out tenant B's role.
    b_admin, b_admin_role = await _destination_admin(
        auth, world["root_b"].id, prefix="b-org-admin", permissions=ADMIN_PERMISSIONS
    )
    async with auth.get_session() as session:
        await _insert_legacy_membership(
            session, entity_id=branch.id, user_id=mover.id, role_ids=[world["scoped_role"].id]
        )
        await session.commit()
    # Tenant B places one of its own members in the branch.
    b_headers = _headers(auth, b_admin.id)
    assert (
        await client.post(
            "/v1/memberships/",
            headers=b_headers,
            json={"entity_id": str(branch.id), "user_id": str(world["user_b"].id), "role_ids": []},
        )
    ).status_code == 201

    mover_headers = _headers(auth, mover.id)
    planted = await client.post(
        "/v1/auth/invite",
        headers=mover_headers,
        json={
            "email": f"planted-{_suffix()}@example.com",
            "entity_id": str(branch.id),
            "role_ids": [str(b_admin_role.id)],
        },
    )
    assert planted.status_code == 403, planted.text
    assert not await _attempt_invite_takeover(
        client, auth, inviter=mover, entity_id=branch.id, role_id=b_admin_role.id, victim=b_admin, captured=captured
    )
    widened = await client.patch(
        f"/v1/memberships/{branch.id}/{world['user_b'].id}",
        headers=mover_headers,
        json={"role_ids": [str(b_admin_role.id)]},
    )
    assert widened.status_code == 403, widened.text
    added = await client.post(
        "/v1/memberships/",
        headers=mover_headers,
        json={"entity_id": str(branch.id), "user_id": str(world["user_a"].id), "role_ids": []},
    )
    assert added.status_code == 403, added.text
    await _assert_account_untouched(client, auth, b_admin)
    async with auth.get_session() as session:
        membership = await auth.membership_service.get_member(session, branch.id, world["user_b"].id)
        assert b_admin_role.id not in {role.id for role in membership.roles}

    # Narrowing stays possible for incident response.
    suspended = await client.patch(
        f"/v1/memberships/{branch.id}/{world['user_b'].id}", headers=mover_headers, json={"status": "suspended"}
    )
    assert suspended.status_code == 200, suspended.text

    # Positive: tenant B invites into its branch; tenant A invites into its own tree.
    own = await client.post(
        "/v1/auth/invite",
        headers=b_headers,
        json={"email": f"b-invitee-{_suffix()}@example.com", "entity_id": str(branch.id), "role_ids": []},
    )
    assert own.status_code == 201, own.text
    assert own.json()["root_entity_id"] == str(world["root_b"].id)
    a_invite = await client.post(
        "/v1/auth/invite",
        headers=_headers(auth, world["scoped_admin"].id),
        json={"email": f"a-invitee-{_suffix()}@example.com", "entity_id": str(world["child_a"].id), "role_ids": []},
    )
    assert a_invite.status_code == 201, a_invite.text
    assert a_invite.json()["root_entity_id"] == str(world["root_a"].id)
