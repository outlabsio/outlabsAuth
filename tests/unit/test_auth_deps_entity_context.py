import json
from uuid import UUID, uuid4

import pytest
from starlette.requests import Request

from outlabs_auth.authentication.backend import AuthBackend
from outlabs_auth.authentication.transport import HeaderTransport
from outlabs_auth.dependencies import AuthDeps


class _TestStrategy:
    async def authenticate(self, credentials: str, **kwargs):
        return {"user_id": credentials, "source": "test"}


class _PermissionServiceStub:
    def __init__(self, result: bool):
        self.result = result
        self.calls = []

    async def check_permission(self, session, *, user_id, permission, entity_id=None):
        self.calls.append(
            {"user_id": user_id, "permission": permission, "entity_id": entity_id}
        )
        return self.result


def _make_request(
    method: str, path: str, body: dict, headers: dict[str, str] | None = None
) -> Request:
    raw_body = json.dumps(body).encode("utf-8")

    async def receive():
        return {"type": "http.request", "body": raw_body, "more_body": False}

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"",
        "headers": [
            (b"content-type", b"application/json"),
            *(
                [
                    (k.lower().encode("utf-8"), v.encode("utf-8"))
                    for k, v in (headers or {}).items()
                ]
            ),
        ],
        "client": ("testclient", 123),
        "server": ("testserver", 80),
        "scheme": "http",
    }
    return Request(scope, receive)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_require_tree_permission_reads_entity_id_from_body(test_session):
    user_id = uuid4()
    entity_id = uuid4()

    backend = AuthBackend(
        name="test",
        transport=HeaderTransport(header_name="X-Test-User"),
        strategy=_TestStrategy(),
    )

    permission_service = _PermissionServiceStub(result=True)
    deps = AuthDeps(
        backends=[backend],
        permission_service=permission_service,
        get_session=lambda: None,
    )

    dep = deps.require_tree_permission(
        "entity:create", "parent_entity_id", source="body"
    )
    request = _make_request(
        "POST",
        "/entities",
        {"parent_entity_id": str(entity_id)},
        headers={"X-Test-User": str(user_id)},
    )

    auth_result = await dep(request=request, session=test_session)
    assert auth_result["user_id"] == str(user_id)
    assert permission_service.calls == [
        {
            "user_id": UUID(str(user_id)),
            "permission": "entity:create",
            "entity_id": UUID(str(entity_id)),
        }
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_require_tree_permission_allows_missing_body_field(test_session):
    user_id = uuid4()

    backend = AuthBackend(
        name="test",
        transport=HeaderTransport(header_name="X-Test-User"),
        strategy=_TestStrategy(),
    )

    permission_service = _PermissionServiceStub(result=True)
    deps = AuthDeps(
        backends=[backend],
        permission_service=permission_service,
        get_session=lambda: None,
    )

    dep = deps.require_tree_permission(
        "entity:create", "parent_entity_id", source="body"
    )
    request = _make_request(
        "POST", "/entities", {}, headers={"X-Test-User": str(user_id)}
    )

    await dep(request=request, session=test_session)
    assert permission_service.calls == [
        {
            "user_id": UUID(str(user_id)),
            "permission": "entity:create",
            "entity_id": None,
        }
    ]
