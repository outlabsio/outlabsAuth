from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from outlabs_auth.models.sql.user import User
from outlabs_auth.routers.config import get_config_router
from outlabs_auth.schemas.config import (
    AllowedRootTypes,
    DefaultChildTypes,
    EntityTypeConfigResponse,
    EntityTypeConfigUpdateRequest,
)


def _build_auth_stub(observability=None):
    class _Deps:
        def require_superuser(self):
            async def _dep():
                return {"user_id": str(uuid4())}

            return _dep

    class _AuthStub:
        def __init__(self):
            self.deps = _Deps()
            self.observability = observability

        async def uow(self):
            raise AssertionError("uow dependency should not execute in direct endpoint tests")

    return _AuthStub()


def _get_route_endpoint(router, path: str, method: str):
    for route in router.routes:
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
            return route.endpoint
    raise AssertionError(f"route {method} {path} not found")


async def _create_actor(test_session) -> User:
    actor = User(email=f"router-config-{uuid4().hex[:8]}@example.com")
    test_session.add(actor)
    await test_session.flush()
    return actor


@pytest.mark.unit
@pytest.mark.asyncio
async def test_config_router_get_and_update_handlers_cover_merge_logging_and_guard(test_session):
    logger = MagicMock()
    auth = _build_auth_stub(observability=SimpleNamespace(logger=logger))
    router = get_config_router(auth, prefix="/v1/config")
    get_endpoint = _get_route_endpoint(router, "/v1/config/entity-types", "GET")
    put_endpoint = _get_route_endpoint(router, "/v1/config/entity-types", "PUT")
    actor = await _create_actor(test_session)

    get_response = await get_endpoint(session=test_session)

    assert isinstance(get_response, EntityTypeConfigResponse)
    assert get_response.allowed_root_types.structural == ["organization"]

    update_payload = EntityTypeConfigUpdateRequest.model_construct(
        allowed_root_types=None,
        default_child_types=DefaultChildTypes(
            structural=["department", "team", "division"],
            access_group=["admin_group"],
        ),
    )

    update_response = await put_endpoint(
        data=update_payload,
        session=test_session,
        auth_result={"user_id": str(actor.id)},
    )

    assert update_response.allowed_root_types.structural == ["organization"]
    assert update_response.default_child_types.structural == [
        "department",
        "team",
        "division",
    ]
    logger.info.assert_called_once_with(
        "entity_type_config_updated",
        allowed_root_types={
            "structural": ["organization"],
            "access_group": get_response.allowed_root_types.access_group,
        },
        updated_by=str(actor.id),
    )

    invalid_payload = EntityTypeConfigUpdateRequest.model_construct(
        allowed_root_types=AllowedRootTypes(structural=[], access_group=[]),
        default_child_types=None,
    )

    with pytest.raises(HTTPException) as exc_info:
        await put_endpoint(
            data=invalid_payload,
            session=test_session,
            auth_result=None,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "At least one root entity type must be configured"
