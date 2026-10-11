"""Real credential, SQL paging and PostgreSQL race acceptance for the opt-in facade."""

import asyncio
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI, HTTPException, Request
from sqlalchemy import delete, select, text, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from outlabs_auth import EnterpriseRBAC
from outlabs_auth.cli import run_migrations
from outlabs_auth.models.sql.api_key import APIKeyScope
from outlabs_auth.models.sql.closure import EntityClosure
from outlabs_auth.models.sql.enums import ConditionOperator, MembershipStatus
from outlabs_auth.models.sql.permission import Permission, PermissionCondition
from outlabs_auth.models.sql.role import Role, RolePermission
from outlabs_auth.models.sql.user_role_membership import UserRoleMembership
from outlabs_auth.core.exceptions import InvalidInputError
from outlabs_auth.services.administrative_authorization import AdministrativeAuthorization
from outlabs_auth.utils.jwt import create_access_token
from tests.integration.test_administrative_grant_foundation import grant, world as foundation_world

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture
async def world(foundation_world):
    w = foundation_world
    schema = (await w.session.execute(text("SELECT current_schema()"))).scalar_one()
    await w.session.commit()
    await run_migrations(os.environ["TEST_DATABASE_URL"], schema=schema)
    w.auth = EnterpriseRBAC(
        engine=w.session.bind,
        database_schema=schema,
        secret_key="synthetic-qualified-staff-context-20261011",
        enable_caching=False,
    )
    await w.auth.initialize()
    w.facade = w.auth.host_query_service.staff_administration(w.auth, trusted_internal_root_id=w.internal.id)
    w.factory = async_sessionmaker(w.session.bind, expire_on_commit=False)
    await w.session.execute(text("CREATE TABLE staff_effects (entity_id uuid PRIMARY KEY, value integer NOT NULL)"))
    await w.session.execute(text("INSERT INTO staff_effects VALUES (:id, 0)"), {"id": w.a.id})
    await w.session.commit()
    yield w
    await w.auth.shutdown()


def request(w, user=None, key=None):
    token = create_access_token(
        {"sub": str((user or w.staff).id), "security_epoch": int((user or w.staff).session_security_epoch or 0)},
        w.auth.config.secret_key,
        audience=w.auth.config.jwt_audience,
    )
    headers = [(b"x-api-key", key.encode())] if key else [(b"authorization", ("Bearer " + token).encode())]
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/staff",
            "headers": headers,
            "client": ("127.0.0.1", 5000),
            "query_string": b"",
            "server": ("localhost", 80),
            "scheme": "http",
        }
    )


async def context(w, session=None, **kwargs):
    return await w.facade.authenticate(session or w.session, request(w, **kwargs))


async def test_real_jwt_source_target_and_transaction_binding(world):
    w = world
    await grant(w, w.read, w.a)
    await grant(w, w.update, w.b)
    await w.session.commit()
    ctx = await context(w)
    assert (await w.facade.authorize(w.session, ctx, action="case:read", entity_id=w.a.id)).allowed
    assert not (await w.facade.authorize(w.session, ctx, action="case:update", entity_id=w.a.id)).allowed
    assert not (await w.facade.authorize(w.session, ctx, action="case:read", entity_id=w.internal.id)).allowed
    assert not (
        await w.facade.authorize(w.session, {"user_id": str(w.staff.id)}, action="case:read", entity_id=w.a.id)
    ).allowed
    async with w.factory() as another:
        assert not (await w.facade.authorize(another, ctx, action="case:read", entity_id=w.a.id)).allowed
    await w.session.commit()
    assert not (await w.facade.authorize(w.session, ctx, action="case:read", entity_id=w.a.id)).allowed
    with pytest.raises(HTTPException):
        await context(w, user=w.outsider)


async def test_sql_count_cursor_filter_and_same_grant_action(world):
    w = world
    await grant(w, w.read, w.a, "subtree")
    await grant(w, w.update, w.b)
    await w.session.commit()
    ctx = await context(w)
    first = await w.facade.entity_page(w.session, ctx, action="case:read", limit=1)
    assert first.total == 2 and len(first.items) == 1 and first.next_cursor
    second = await w.facade.entity_page(w.session, ctx, action="case:read", limit=1, cursor=first.next_cursor)
    assert second.total == 2 and {i.id for i in first.items + second.items} == {w.a.id, w.child.id}
    assert second.next_cursor is None
    assert (await w.facade.entity_page(w.session, ctx, action="case:update")).total == 1
    assert (await w.facade.entity_page(w.session, ctx, action="case:read", customer_root_id=w.b.id)).total == 0
    with pytest.raises(HTTPException, match="belongs to another"):
        await w.facade.entity_page(w.session, ctx, action="case:update", cursor=first.next_cursor)
    with pytest.raises(HTTPException):
        await w.facade.entity_page(w.session, ctx, action="case:read", cursor=first.next_cursor + "tampered")


async def test_group_list_pins_and_corrupt_closure_fail_closed(world):
    w = world
    group = await w.svc.create_group(w.session, actor_id=w.platform.id, group_key=uuid4().hex)
    admission = await w.svc.admit_customer(
        w.session, actor_id=w.platform.id, group_id=group.id, customer_root_id=w.a.id
    )
    await grant(w, w.read, group, "group")
    await w.svc.admit_customer(w.session, actor_id=w.platform.id, group_id=group.id, customer_root_id=w.b.id)
    await w.session.commit()
    ctx = await context(w)
    assert (await w.facade.entity_page(w.session, ctx, action="case:read")).total == 2
    await w.session.execute(
        update(EntityClosure)
        .where(EntityClosure.descendant_id == w.child.id, EntityClosure.ancestor_id == w.a.id)
        .values(depth=10)
    )
    assert {i.id for i in (await w.facade.entity_page(w.session, ctx, action="case:read")).items} == {w.a.id}
    await w.svc.remove_customer(w.session, actor_id=w.platform.id, admission_id=admission.id)
    assert (await w.facade.entity_page(w.session, ctx, action="case:read")).total == 0


async def test_personal_key_ceilings_quota_once_and_account_root(world):
    w = world
    await grant(w, w.update, w.a, "subtree")
    mint = await context(w)
    full, key = await w.facade.create_personal_key(
        w.session, mint, name="bounded", entity_id=w.child.id, scopes=["case:update", "user:update"]
    )
    await w.session.commit()
    ctx = await context(w, key=full)
    assert (await w.facade.authorize(w.session, ctx, action="case:update", entity_id=w.child.id)).allowed
    assert not (await w.facade.authorize(w.session, ctx, action="case:update", entity_id=w.a.id)).allowed
    assert not (
        await w.facade.authorize(w.session, ctx, action="user:update", entity_id=w.child.id, account_root_required=True)
    ).allowed
    assert (await w.facade.entity_page(w.session, ctx, action="case:update")).total == 1
    assert (await w.facade.entity_page(w.session, ctx, action="case:read")).total == 0
    usage = (
        await w.session.execute(text("SELECT usage_count FROM api_keys WHERE id=:id"), {"id": key.id})
    ).scalar_one()
    assert usage == 1
    mixed = request(w, key=full)
    mixed.scope["headers"].append((b"authorization", b"Bearer invalid"))
    with pytest.raises(HTTPException, match="Ambiguous"):
        await w.facade.authenticate(w.session, mixed)


async def test_unanchored_key_requires_disposition_and_revoked_key_denies(world):
    w = world
    await grant(w, w.read, w.a)
    permission = (await w.session.execute(select(Permission).where(Permission.name == "case:read"))).scalar_one()
    native_role = Role(name=uuid4().hex, display_name="Internal native read", root_entity_id=w.internal.id)
    w.session.add(native_role)
    await w.session.flush()
    w.session.add(RolePermission(role_id=native_role.id, permission_id=permission.id))
    w.session.add(UserRoleMembership(user_id=w.staff.id, role_id=native_role.id))
    await w.session.flush()
    full, key = await w.auth.api_key_service.create_api_key(
        w.session, owner_id=w.staff.id, name="unanchored", scopes=["case:read"], record_audit=False
    )
    await w.session.commit()
    ctx = await context(w, key=full)
    assert not (await w.facade.authorize(w.session, ctx, action="case:read", entity_id=w.a.id)).allowed
    approved = AdministrativeAuthorization(w.auth, w.svc, allow_unanchored_personal_keys=True)
    ctx = await approved.authenticate(w.session, request(w, key=full))
    assert (await approved.authorize(w.session, ctx, action="case:read", entity_id=w.a.id)).allowed
    await w.auth.api_key_service.revoke_api_key(w.session, key.id)
    assert not (await approved.authorize(w.session, ctx, action="case:read", entity_id=w.a.id)).allowed


async def test_account_grant_and_dormant_platform_protection(world):
    w = world
    await grant(w, w.update, w.child, "subtree")
    await w.session.commit()
    ctx = await context(w)
    assert not (await w.facade.authorize_account(w.session, ctx, action="user:update", user_id=w.outsider.id)).allowed
    await grant(w, w.update, w.a, "subtree")
    assert (await w.facade.authorize_account(w.session, ctx, action="user:update", user_id=w.outsider.id)).allowed
    role = Role(name=uuid4().hex, display_name="Dormant platform", is_global=True)
    w.session.add(role)
    await w.session.flush()
    w.session.add(
        UserRoleMembership(
            user_id=w.outsider.id,
            role_id=role.id,
            status=MembershipStatus.SUSPENDED,
            valid_from=datetime.now(timezone.utc) + timedelta(days=30),
        )
    )
    await w.session.flush()
    assert not (
        await w.facade.authorize_account(
            w.session, ctx, action="user:update", user_id=w.outsider.id, protected_write=True
        )
    ).allowed


async def test_http_host_boundary_uses_actual_backends_and_sql_projection(world):
    w = world
    await grant(w, w.read, w.a, "subtree")
    await w.session.commit()
    app = FastAPI()

    @app.get("/staff/entities")
    async def entities(req: Request):
        async with w.factory() as session:
            ctx = await w.facade.authenticate(session, req)
            page = await w.facade.entity_page(session, ctx, action="case:read")
            return {"total": page.total, "items": [{"id": str(i.id), "name": i.display_name} for i in page.items]}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
        valid = request(w)
        assert (await client.get("/staff/entities")).status_code == 401
        assert (await client.get("/staff/entities", headers={"Authorization": "Bearer forged"})).status_code == 401
        outsider = request(w, user=w.outsider)
        assert (
            await client.get("/staff/entities", headers=dict(outsider.headers), params={"user_id": str(w.staff.id)})
        ).status_code == 403
        response = await client.get("/staff/entities", headers=dict(valid.headers))
        assert response.status_code == 200 and response.json()["total"] == 2
        assert {i["id"] for i in response.json()["items"]} == {str(w.a.id), str(w.child.id)}
        # Administrative policy has not been injected into ordinary permissions.
        assert "case:read" not in await w.auth.permission_service.get_user_permissions(w.session, w.staff.id)


async def waiting_on_lock(w, name):
    async with w.factory() as observer:
        for _ in range(200):
            await observer.execute(text("SELECT pg_stat_clear_snapshot()"))
            if (
                await observer.execute(
                    text(
                        "SELECT count(*) FROM pg_stat_activity WHERE application_name=:name AND wait_event_type='Lock'"
                    ),
                    {"name": name},
                )
            ).scalar_one():
                return
            await asyncio.sleep(0.01)
    raise AssertionError("Competing writer never reached the expected PostgreSQL row-lock wait")


@pytest.mark.parametrize(
    "withdrawal", ["grant", "template", "admission", "security", "empty_key_scope", "permission_condition", "archive"]
)
async def test_sensitive_write_holds_qualifying_rows_until_commit(world, withdrawal):
    w = world
    group = await w.svc.create_group(w.session, actor_id=w.platform.id, group_key=uuid4().hex)
    admission = await w.svc.admit_customer(
        w.session, actor_id=w.platform.id, group_id=group.id, customer_root_id=w.a.id
    )
    g = await grant(w, w.update, group, "group")
    full = None
    if withdrawal == "empty_key_scope":
        mint = await context(w)
        full, key = await w.facade.create_personal_key(
            w.session, mint, name="initially empty", entity_id=w.a.id, scopes=["case:update"]
        )
        # Model an existing/repair writer clearing the child set. The fence must
        # cover a later narrowing INSERT even when no old scope row exists.
        await w.session.execute(delete(APIKeyScope).where(APIKeyScope.api_key_id == key.id))
    permission = (await w.session.execute(select(Permission).where(Permission.name == "case:update"))).scalar_one()
    await w.session.commit()
    name = "staff_race_" + uuid4().hex
    async with w.factory() as writer:
        ctx = await context(w, writer, key=full)
        assert (
            await w.facade.authorize(writer, ctx, action="case:update", entity_id=w.a.id, protected_write=True)
        ).allowed

        async def change():
            async with w.factory() as other:
                await other.execute(text("SELECT set_config('application_name',:name,true)"), {"name": name})
                if withdrawal == "grant":
                    await w.svc.revoke_grant(other, actor_id=w.platform.id, grant_id=g.id)
                elif withdrawal == "template":
                    await w.svc.set_template_active(
                        other, actor_id=w.platform.id, template_id=w.update.id, active=False
                    )
                elif withdrawal == "admission":
                    await w.svc.remove_customer(other, actor_id=w.platform.id, admission_id=admission.id)
                elif withdrawal == "security":
                    await w.auth.user_service.change_password(other, w.staff.id, "SyntheticChangedBoundary456!")
                elif withdrawal == "empty_key_scope":
                    other.add(APIKeyScope(api_key_id=key.id, scope="case:read"))
                elif withdrawal == "permission_condition":
                    other.add(
                        PermissionCondition(
                            permission_id=permission.id,
                            attribute="resource.safe",
                            operator=ConditionOperator.EQUALS,
                            value="true",
                        )
                    )
                else:
                    await w.entities.delete_entity(other, w.a.id, cascade=True)
                await other.commit()

        pending = asyncio.create_task(change())
        try:
            await waiting_on_lock(w, name)
            assert not pending.done()
            await writer.execute(text("UPDATE staff_effects SET value=value+1 WHERE entity_id=:id"), {"id": w.a.id})
            await writer.commit()
            await asyncio.wait_for(pending, 10)
        finally:
            if not pending.done():
                pending.cancel()
            await asyncio.gather(pending, return_exceptions=True)
    async with w.factory() as later:
        if withdrawal == "security":
            with pytest.raises(HTTPException):
                await context(w, later)
            fresh = await w.auth.user_service.get_user_by_id(later, w.staff.id, populate_existing=True)
            ctx = await context(w, later, user=fresh)
        else:
            ctx = await context(w, later, key=full)
        assert not (
            await w.facade.authorize(later, ctx, action="case:update", entity_id=w.a.id, protected_write=True)
        ).allowed
        assert (
            await later.execute(text("SELECT value FROM staff_effects WHERE entity_id=:id"), {"id": w.a.id})
        ).scalar_one() == 1


async def test_staff_key_issuance_refuses_untrusted_approval_and_wider_actions(world):
    w = world
    await grant(w, w.read, w.a)
    await w.session.commit()
    ctx = await context(w)
    with pytest.raises(InvalidInputError, match="owner.*root entity"):
        await w.auth.api_key_service.create_api_key(
            w.session, owner_id=w.staff.id, name="legacy", entity_id=w.a.id, scopes=["case:read"]
        )
    with pytest.raises(InvalidInputError, match="Invalid staff credential"):
        await w.auth.api_key_service.create_api_key(
            w.session,
            owner_id=w.staff.id,
            name="forged",
            entity_id=w.a.id,
            scopes=["case:read"],
            _staff_approval={"approved": True},
        )
    for scopes in [["case:update"], ["case:*"], []]:
        with pytest.raises(HTTPException):
            await w.facade.create_personal_key(w.session, ctx, name="wider", entity_id=w.a.id, scopes=scopes)
    assert (await w.session.execute(text("SELECT count(*) FROM api_keys"))).scalar_one() == 0


async def test_valid_machine_service_credential_cannot_borrow_human_grants(world):
    w = world
    token = w.auth.service_token_service.create_service_token("synthetic-machine", "Machine", ["case:read"])
    req = request(w)
    req.scope["headers"] = [(b"authorization", ("Bearer " + token).encode())]
    result = await w.auth.deps._authenticate_request(req, w.session, active=True, verified=False, optional=False)
    assert result["source"] == "service_token"
    with pytest.raises(HTTPException, match="Human staff"):
        await w.facade.authenticate(w.session, req)


async def test_protected_account_write_serializes_future_platform_classification(world):
    w = world
    await grant(w, w.update, w.a, "subtree")
    role = Role(name=uuid4().hex, display_name="Initially ordinary")
    w.session.add(role)
    await w.session.flush()
    w.session.add(UserRoleMembership(user_id=w.outsider.id, role_id=role.id, status=MembershipStatus.SUSPENDED))
    await w.session.commit()
    name = "staff_account_" + uuid4().hex
    async with w.factory() as writer:
        ctx = await context(w, writer)
        assert (
            await w.facade.authorize_account(
                writer, ctx, action="user:update", user_id=w.outsider.id, protected_write=True
            )
        ).allowed

        async def elevate():
            async with w.factory() as other:
                await other.execute(text("SELECT set_config('application_name',:name,true)"), {"name": name})
                await other.execute(update(Role).where(Role.id == role.id).values(is_global=True))
                await other.commit()

        pending = asyncio.create_task(elevate())
        try:
            await waiting_on_lock(w, name)
            await writer.commit()
            await asyncio.wait_for(pending, 10)
        finally:
            if not pending.done():
                pending.cancel()
            await asyncio.gather(pending, return_exceptions=True)
    ctx = await context(w)
    assert not (await w.facade.authorize_account(w.session, ctx, action="user:update", user_id=w.outsider.id)).allowed
