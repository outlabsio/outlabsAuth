import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from fastapi import HTTPException

from outlabs_auth import SimpleRBAC
from outlabs_auth.models.sql.entity import Entity
from outlabs_auth.models.sql.enums import APIKeyStatus, EntityClass
from outlabs_auth.routers import get_api_keys_router
from outlabs_auth.schemas.api_key import ApiKeyCreateRequest, ApiKeyUpdateRequest


def _endpoint(router, path: str, method: str):
    for route in router.routes:
        if route.path == path and method in route.methods:
            return route.endpoint
    raise AssertionError(f"Route not found for {method} {path}")


def _suffix() -> str:
    return uuid.uuid4().hex[:8]


def _entity(*, name: str, slug: str) -> Entity:
    return Entity(
        name=name,
        display_name=name.title(),
        slug=slug,
        entity_class=EntityClass.STRUCTURAL,
        entity_type="organization",
        path=f"/{slug}/",
        depth=0,
    )


@pytest_asyncio.fixture
async def auth_instance(test_engine) -> SimpleRBAC:
    auth = SimpleRBAC(
        engine=test_engine,
        secret_key="test-secret-key-do-not-use-in-production-12345678",
        access_token_expire_minutes=60,
        enable_token_cleanup=False,
    )
    await auth.initialize()
    yield auth
    await auth.shutdown()


@pytest_asyncio.fixture
async def api_keys_router(auth_instance: SimpleRBAC):
    return get_api_keys_router(auth_instance, prefix="/v1/api-keys")


async def _create_user(auth: SimpleRBAC, session, *, email_prefix: str):
    return await auth.user_service.create_user(
        session=session,
        email=f"{email_prefix}-{_suffix()}@example.com",
        password="TestPass123!",
        first_name="Api",
        last_name="Owner",
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_api_keys_router_callback_validation_and_visibility_paths(
    auth_instance: SimpleRBAC,
    api_keys_router,
):
    list_api_keys = _endpoint(api_keys_router, "/v1/api-keys/", "GET")
    create_api_key = _endpoint(api_keys_router, "/v1/api-keys/", "POST")
    get_api_key = _endpoint(api_keys_router, "/v1/api-keys/{key_id}", "GET")
    update_api_key = _endpoint(api_keys_router, "/v1/api-keys/{key_id}", "PATCH")
    delete_api_key = _endpoint(api_keys_router, "/v1/api-keys/{key_id}", "DELETE")

    async with auth_instance.get_session() as session:
        owner = await _create_user(auth_instance, session, email_prefix="api-owner")
        other_user = await _create_user(auth_instance, session, email_prefix="api-other")
        entity = _entity(name=f"entity-{_suffix()}", slug=f"entity-{_suffix()}")
        session.add(entity)
        await session.flush()

        _, key = await auth_instance.api_key_service.create_api_key(
            session,
            owner_id=owner.id,
            name="Owned Key",
            scopes=["user:read"],
            ip_whitelist=["10.0.0.1"],
        )
        await session.commit()

        listed = await list_api_keys(
            session=session,
            auth_result={"user_id": str(owner.id)},
        )
        assert len(listed) == 1
        assert listed[0].id == str(key.id)
        assert listed[0].scopes == ["user:read"]
        assert listed[0].ip_whitelist == ["10.0.0.1"]

        with pytest.raises(HTTPException) as exc:
            await create_api_key(
                data=ApiKeyCreateRequest(
                    name="bad-entities",
                    entity_ids=[str(entity.id), str(uuid.uuid4())],
                ),
                session=session,
                auth_result={"user_id": str(owner.id)},
            )
        assert exc.value.status_code == 400

        with pytest.raises(HTTPException) as exc:
            await create_api_key(
                data=ApiKeyCreateRequest(
                    name="bad-uuid",
                    entity_ids=["not-a-uuid"],
                ),
                session=session,
                auth_result={"user_id": str(owner.id)},
            )
        assert exc.value.status_code == 422

        with pytest.raises(HTTPException) as exc:
            await get_api_key(
                key_id=uuid.uuid4(),
                session=session,
                auth_result={"user_id": str(owner.id)},
            )
        assert exc.value.status_code == 404

        with pytest.raises(HTTPException) as exc:
            await get_api_key(
                key_id=key.id,
                session=session,
                auth_result={"user_id": str(other_user.id)},
            )
        assert exc.value.status_code == 403

        with pytest.raises(HTTPException) as exc:
            await update_api_key(
                key_id=key.id,
                data=ApiKeyUpdateRequest(name="forbidden"),
                session=session,
                auth_result={"user_id": str(other_user.id)},
            )
        assert exc.value.status_code == 404

        with pytest.raises(HTTPException) as exc:
            await update_api_key(
                key_id=key.id,
                data=ApiKeyUpdateRequest(entity_ids=[str(entity.id), str(uuid.uuid4())]),
                session=session,
                auth_result={"user_id": str(owner.id)},
            )
        assert exc.value.status_code == 400

        updated = await update_api_key(
            key_id=key.id,
            data=ApiKeyUpdateRequest(
                name="Updated Key",
                description="updated",
                status=APIKeyStatus.REVOKED,
                scopes=["role:read"],
                ip_whitelist=["192.168.0.10"],
                entity_ids=[],
            ),
            session=session,
            auth_result={"user_id": str(owner.id)},
        )
        assert updated.name == "Updated Key"
        assert updated.description == "updated"
        assert updated.status == APIKeyStatus.REVOKED
        assert updated.scopes == ["role:read"]
        assert updated.ip_whitelist == ["192.168.0.10"]
        assert updated.entity_ids is None

        with pytest.raises(HTTPException) as exc:
            await delete_api_key(
                key_id=key.id,
                session=session,
                auth_result={"user_id": str(other_user.id)},
            )
        assert exc.value.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
async def test_api_keys_router_callback_rotate_paths(
    auth_instance: SimpleRBAC,
    api_keys_router,
):
    rotate_api_key = _endpoint(api_keys_router, "/v1/api-keys/{key_id}/rotate", "POST")

    async with auth_instance.get_session() as session:
        owner = await _create_user(auth_instance, session, email_prefix="api-rotate")
        other_user = await _create_user(auth_instance, session, email_prefix="api-rotate-other")

        _, original = await auth_instance.api_key_service.create_api_key(
            session,
            owner_id=owner.id,
            name="Rotate Me",
            scopes=["user:read"],
            prefix_type="sk_test",
            ip_whitelist=["10.0.0.8"],
            expires_in_days=2,
            description="rotate original",
        )
        original.expires_at = datetime.now(timezone.utc) + timedelta(days=2, hours=6)
        await session.flush()

        with pytest.raises(HTTPException) as exc:
            await rotate_api_key(
                key_id=original.id,
                session=session,
                auth_result={"user_id": str(other_user.id)},
            )
        assert exc.value.status_code == 404

        rotated = await rotate_api_key(
            key_id=original.id,
            session=session,
            auth_result={"user_id": str(owner.id)},
        )
        assert rotated.name == "Rotate Me"
        assert rotated.api_key.startswith(rotated.prefix)
        assert rotated.scopes == ["user:read"]
        assert rotated.ip_whitelist == ["10.0.0.8"]

        old_key = await auth_instance.api_key_service.get_api_key(session, original.id)
        assert old_key is not None
        assert old_key.status == APIKeyStatus.REVOKED
