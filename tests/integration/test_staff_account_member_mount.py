"""Actual opt-in account/member HTTP effects and target/credential isolation."""

from uuid import uuid4
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text

from outlabs_auth.models.sql.role import Role
from outlabs_auth.routers import get_staff_router, get_entities_router
from tests.integration.test_administrative_grant_foundation import grant, world as foundation_world
from tests.integration.test_staff_credential_target_lists import request, world as staff_world

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture
async def mounted_world(staff_world):
    w = staff_world
    actions = [
        "user:read",
        "user:update",
        "user:delete",
        "membership:read",
        "membership:create",
        "membership:update",
        "membership:delete",
    ]
    for name in actions:
        if name != "user:update":
            await w.auth.permission_service.create_permission(w.session, name=name, display_name=name)
    t = await w.svc.create_template(
        w.session, actor_id=w.platform.id, template_key=uuid4().hex, revision=1, actions=actions
    )
    w.all_grant = await grant(w, t, w.a, "subtree")
    w.customer_role = await w.auth.role_service.create_role(
        w.session,
        name=uuid4().hex,
        display_name="Customer member",
        is_global=False,
        root_entity_id=w.a.id,
        permission_names=["case:read"],
    )
    await w.session.commit()
    app = FastAPI()
    w.auth.instrument_fastapi(app)
    app.include_router(get_staff_router(w.facade))
    app.include_router(get_entities_router(w.auth, prefix="/ordinary"))
    w.app = app
    yield w


async def test_profile_native_roles_membership_and_soft_restore_commit_before_response(mounted_world):
    w = mounted_world
    headers = dict(request(w).headers)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=w.app), base_url="http://localhost") as c:
        r = await c.get("/staff/users/" + str(w.outsider.id), headers=headers)
        assert r.status_code == 200, r.text
        assert not {"hashed_password", "invite_token", "session_security_epoch"} & r.json().keys()
        r = await c.patch("/staff/users/" + str(w.outsider.id), headers=headers, json={"first_name": "Native"})
        assert r.status_code == 200, r.text
        async with w.factory() as s:
            assert (
                await s.execute(text("SELECT first_name FROM users WHERE id=:id"), {"id": w.outsider.id})
            ).scalar_one() == "Native"
        path = f"/staff/entities/{w.child.id}/members/{w.outsider.id}"
        r = await c.put(path, headers=headers, json={"role_ids": [str(w.customer_role.id)]})
        assert r.status_code == 200, r.text
        assert r.json()["role_ids"] == [str(w.customer_role.id)]
        assert (await c.get(path, headers=headers)).status_code == 200
        assert (await c.delete(path, headers=headers)).status_code == 204
        r = await c.post(path + "/reactivate", headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "active"
        assert (await c.delete("/staff/users/" + str(w.outsider.id), headers=headers)).status_code == 204
        r = await c.post("/staff/users/" + str(w.outsider.id) + "/restore", headers=headers)
        assert r.status_code == 200, r.text
        async with w.factory() as s:
            assert (
                await s.execute(
                    text("SELECT status FROM entity_memberships WHERE user_id=:id AND entity_id=:entity"),
                    {"id": w.outsider.id, "entity": w.child.id},
                )
            ).scalar_one() == "revoked"


@pytest.mark.parametrize("escape", ["root_transfer", "superuser", "password", "email"])
async def test_account_profile_rejects_security_and_identity_fields(mounted_world, escape):
    w = mounted_world
    payload = {
        "root_transfer": {"root_entity_id": str(w.b.id)},
        "superuser": {"is_superuser": True},
        "password": {"password": "SyntheticOther123!"},
        "email": {"email": "other@example.com"},
    }[escape]
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=w.app), base_url="http://localhost") as c:
        r = await c.patch("/staff/users/" + str(w.outsider.id), headers=dict(request(w).headers), json=payload)
        assert r.status_code == 422, r.text


async def test_leaf_grant_cannot_manage_whole_customer_account(mounted_world):
    w = mounted_world
    await w.svc.revoke_grant(w.session, actor_id=w.platform.id, grant_id=w.all_grant.id)
    t = await w.svc.create_template(
        w.session,
        actor_id=w.platform.id,
        template_key=uuid4().hex,
        revision=1,
        actions=["user:update", "membership:update", "membership:create"],
    )
    await grant(w, t, w.child)
    await w.session.commit()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=w.app), base_url="http://localhost") as c:
        assert (
            await c.patch(
                "/staff/users/" + str(w.outsider.id), headers=dict(request(w).headers), json={"first_name": "Denied"}
            )
        ).status_code == 403
        r = await c.put(
            f"/staff/entities/{w.child.id}/members/{w.outsider.id}",
            headers=dict(request(w).headers),
            json={"role_ids": [str(w.customer_role.id)]},
        )
        assert r.status_code == 200, r.text


@pytest.mark.parametrize("target", ["internal", "other_customer", "platform", "retained_platform", "global_membership"])
async def test_customer_mutation_refuses_protected_and_cross_root_targets(mounted_world, target):
    w = mounted_world
    user = w.outsider.id
    entity = w.child.id
    if target == "internal":
        user = w.staff.id
        entity = w.internal.id
    elif target == "other_customer":
        entity = w.b.id
    elif target == "platform":
        user = w.platform.id
    elif target == "retained_platform":
        await w.session.execute(text("UPDATE users SET platform_protected=true WHERE id=:id"), {"id": user})
        await w.session.commit()
    else:
        role = await w.auth.role_service.create_role(
            w.session, name=uuid4().hex, display_name="Protected", is_global=True
        )
        await w.auth.membership_service.add_member(w.session, w.a.id, user, role_ids=[role.id])
        await w.session.commit()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=w.app), base_url="http://localhost") as c:
        r = await c.put(
            f"/staff/entities/{entity}/members/{user}",
            headers=dict(request(w).headers),
            json={"role_ids": [str(w.customer_role.id)]},
        )
        assert r.status_code == 403, r.text


async def test_customer_and_personal_key_cannot_escape_staff_boundaries(mounted_world):
    w = mounted_world
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=w.app), base_url="http://localhost") as c:
        r = await c.patch(
            "/staff/users/" + str(w.outsider.id),
            headers=dict(request(w, user=w.outsider).headers),
            json={"first_name": "Denied"},
        )
        assert r.status_code == 403
        ctx = await w.facade.authenticate(w.session, request(w))
        secret, _ = await w.facade.create_personal_key(
            w.session, ctx, name="Narrow", entity_id=w.child.id, scopes=["membership:read"]
        )
        await w.session.commit()
        headers = {"X-API-Key": secret}
        assert (
            await c.patch("/staff/users/" + str(w.outsider.id), headers=headers, json={"first_name": "Denied"})
        ).status_code == 403
        assert (
            await c.put(f"/staff/entities/{w.child.id}/members/{w.outsider.id}", headers=headers, json={"role_ids": []})
        ).status_code == 403
        assert "/ordinary/{entity_id}" in w.app.openapi()["paths"]
        assert (await c.get("/ordinary/" + str(w.a.id), headers=dict(request(w).headers))).status_code in (403, 404)


async def test_staff_native_assignment_preserves_source_and_repeated_remove_fences_return(mounted_world):
    w = mounted_world
    claim_id = uuid4()
    await w.auth.membership_service.set_source_membership(
        w.session, source_id=claim_id, entity_id=w.child.id, user_id=w.outsider.id, role_ids=(w.customer_role.id,)
    )
    await w.session.commit()
    path = f"/staff/entities/{w.child.id}/members/{w.outsider.id}"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=w.app), base_url="http://localhost") as c:
        r = await c.put(path, headers=dict(request(w).headers), json={"role_ids": [str(w.customer_role.id)]})
        assert r.status_code == 200, r.text
    await w.auth.membership_service.set_source_membership(
        w.session, source_id=claim_id, entity_id=w.child.id, user_id=w.outsider.id, role_ids=None
    )
    await w.session.commit()
    async with w.factory() as s:
        assert (
            await s.execute(
                text("SELECT status,native_owned FROM entity_memberships WHERE user_id=:id AND entity_id=:entity"),
                {"id": w.outsider.id, "entity": w.child.id},
            )
        ).one() == ("active", True)


async def test_account_list_filters_protected_subjects_before_count_and_refuses_sibling(mounted_world):
    w = mounted_world
    private = await w.auth.user_service.create_user(
        w.session, email=uuid4().hex + "@example.com", password="SyntheticOther123!", root_entity_id=w.a.id
    )
    private.platform_protected = True
    await w.session.commit()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=w.app), base_url="http://localhost") as c:
        r = await c.get(
            "/staff/users", headers=dict(request(w).headers), params={"customer_root_id": str(w.a.id), "limit": 1}
        )
        assert r.status_code == 200, r.text
        assert r.json()["total"] == 1 and r.json()["items"][0]["id"] == str(w.outsider.id)
        assert (
            await c.get("/staff/users", headers=dict(request(w).headers), params={"customer_root_id": str(w.b.id)})
        ).status_code == 403
