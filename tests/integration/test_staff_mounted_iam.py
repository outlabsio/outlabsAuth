"""Mounted opt-in workflow and ordinary-route escape-path qualification."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select, text

from outlabs_auth.core.exceptions import InvalidInputError
from outlabs_auth.models.sql.api_key import APIKey
from outlabs_auth.routers import get_api_keys_router, get_staff_router
from outlabs_auth.services.permission import PermissionService
from tests.integration.test_administrative_grant_foundation import grant, world as foundation_world
from tests.integration.test_staff_credential_target_lists import context, request, world

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def mounted(w):
    permission = PermissionService(w.auth.config)
    await permission.create_permission(w.session, name="entity:read", display_name="Entity read")
    template = await w.svc.create_template(
        w.session, actor_id=w.platform.id, template_key=uuid4().hex, revision=1, actions=["entity:read"]
    )
    await grant(w, template, w.a)
    await grant(w, w.read, w.a)
    await w.session.commit()
    app = FastAPI()
    w.auth.instrument_fastapi(app)
    app.include_router(get_staff_router(w.facade))
    app.include_router(get_api_keys_router(w.auth, prefix="/ordinary-keys"))
    return app


async def test_mounted_staff_keys_commit_before_response_and_deny_alternate_route(world):
    w = world
    app = await mounted(w)
    headers = dict(request(w).headers)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
        page = await client.get("/staff/entities", headers=headers)
        assert page.status_code == 200, page.text
        assert {row["id"] for row in page.json()["items"]} == {str(w.a.id)}
        created = await client.post(
            "/staff/keys", headers=headers, json={"name": "Mounted", "entity_id": str(w.a.id), "scopes": ["case:read"]}
        )
        assert created.status_code == 201, created.text
        key_id = created.json()["key"]["id"]
        async with w.factory() as reader:
            key = (await reader.execute(select(APIKey).where(APIKey.id == key_id))).scalar_one()
            assert key.staff_managed
        for payload in [
            {"expires_at": (datetime.now(timezone.utc) + timedelta(days=60)).isoformat()},
            {"status": "active"},
            {"name": "alternate"},
        ]:
            denied = await client.patch(f"/ordinary-keys/{key_id}", headers=headers, json=payload)
            assert denied.status_code in {400, 422}, denied.text
            assert "staff lifecycle workflow" in denied.text
        denied = await client.post(f"/ordinary-keys/{key_id}/rotate", headers=headers)
        assert denied.status_code in {400, 422}, denied.text
        assert "staff lifecycle workflow" in denied.text
        narrowed = await client.patch(f"/staff/keys/{key_id}", headers=headers, json={"scopes": ["case:read"]})
        assert narrowed.status_code == 200, narrowed.text
        rotated = await client.post(f"/staff/keys/{key_id}/rotate", headers=headers)
        assert rotated.status_code == 200, rotated.text
        assert rotated.json()["key"]["expires_at"] == created.json()["key"]["expires_at"]
        assert (await client.delete(f"/staff/keys/{rotated.json()['key']['id']}", headers=headers)).status_code == 204
        listed = await client.get("/staff/keys", headers=headers)
        assert listed.json()["total"] == 2
        assert all("secret" not in row and "key_hash" not in row for row in listed.json()["items"])


async def test_mounted_staff_refuses_customer_key_source_ambiguous_and_extra_fields(world):
    w = world
    app = await mounted(w)
    headers = dict(request(w).headers)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
        assert (
            await client.get("/staff/entities", headers=dict(request(w, user=w.outsider).headers))
        ).status_code == 403
        issued = await client.post(
            "/staff/keys",
            headers=headers,
            json={"name": "Synthetic", "entity_id": str(w.a.id), "scopes": ["case:read"]},
        )
        secret = issued.json()["secret"]
        key_headers = {"X-API-Key": secret}
        for method, path, payload in [
            ("get", "/staff/keys", None),
            ("post", "/staff/keys", {}),
            ("post", f"/staff/keys/{issued.json()['key']['id']}/rotate", None),
        ]:
            result = await client.request(method, path, headers=key_headers, json=payload)
            assert result.status_code in {403, 422}, result.text
        ambiguous = await client.get("/staff/entities", headers={**headers, **key_headers})
        assert ambiguous.status_code == 401
        result = await client.patch(
            f"/staff/keys/{issued.json()['key']['id']}",
            headers=headers,
            json={"scopes": ["case:read"], "status": "active"},
        )
        assert result.status_code == 422


@pytest.mark.parametrize(
    "field,value",
    [
        ("staff_managed", "false"),
        ("expires_at", "NULL"),
        ("expires_at", "clock_timestamp()+interval '60 days'"),
        ("entity_id", "NULL"),
        ("inherit_from_tree", "true"),
    ],
)
async def test_staff_key_database_lifecycle_cannot_expand(world, field, value):
    w = world
    await grant(w, w.read, w.a)
    await w.session.commit()
    ctx = await context(w)
    _, key = await w.facade.create_personal_key(w.session, ctx, name="Frozen", entity_id=w.a.id, scopes=["case:read"])
    key_id = key.id
    await w.session.commit()
    with pytest.raises(Exception, match="staff credential lifecycle cannot expand"):
        await w.session.execute(text(f"UPDATE api_keys SET {field}={value} WHERE id=:id"), {"id": key_id})
    await w.session.rollback()


async def test_native_sdk_cannot_update_staff_key_without_approval(world):
    w = world
    await grant(w, w.read, w.a)
    await w.session.commit()
    ctx = await context(w)
    _, key = await w.facade.create_personal_key(w.session, ctx, name="Frozen", entity_id=w.a.id, scopes=["case:read"])
    for updates in [{"expires_at": None}, {"status": "active"}, {"scopes": ["case:update"]}]:
        with pytest.raises(InvalidInputError, match="staff lifecycle workflow"):
            await w.auth.api_key_service.update_api_key(w.session, key.id, **updates)
    with pytest.raises(InvalidInputError, match="staff lifecycle workflow"):
        await w.auth.api_key_service.rotate_api_key(w.session, key.id)
