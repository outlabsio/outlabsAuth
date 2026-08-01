"""
Regression tests: a write request's commit must complete before the response
reaches the client.

FastAPI (>=0.106) runs dependency teardown only after the response has been
sent, so a unit of work that commits in teardown lets a client receive its
201 and issue a dependent request before the data is committed. Observed in
CI (Release Readiness run 27383495356): POST /roles/{id}/conditions -> 404
for a role created by the immediately preceding request. The fix:
``UnitOfWorkMiddleware`` (installed by ``instrument_fastapi``) finalizes the
unit of work just before ``http.response.start`` is forwarded.
"""

import json
import uuid
from typing import Any

import httpx
import pytest_asyncio
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from outlabs_auth import SimpleRBAC
from outlabs_auth.models.sql.permission import Permission


@pytest_asyncio.fixture
async def simple_auth(test_engine) -> SimpleRBAC:
    auth = SimpleRBAC(
        engine=test_engine,
        secret_key="test-secret-key-do-not-use-in-production-12345678",
        enable_token_cleanup=False,
    )
    await auth.initialize()
    yield auth
    await auth.shutdown()


def _build_app(auth: SimpleRBAC, *, instrument: bool) -> FastAPI:
    """Minimal host app exercising ``auth.uow`` the way library routers do."""
    app = FastAPI()

    @app.post("/things", status_code=201)
    async def create_thing(session: AsyncSession = Depends(auth.uow)):
        permission = Permission(
            name=f"thing:{uuid.uuid4().hex[:12]}",
            display_name="UoW regression fixture",
        )
        session.add(permission)
        await session.flush()
        return {"name": permission.name}

    @app.post("/things-conflict", status_code=201)
    async def create_thing_then_fail(session: AsyncSession = Depends(auth.uow)):
        permission = Permission(
            name=f"conflict:{uuid.uuid4().hex[:12]}",
            display_name="UoW regression fixture",
        )
        session.add(permission)
        await session.flush()
        raise HTTPException(status_code=409, detail=permission.name)

    @app.get("/peek", status_code=200)
    async def write_on_a_read_method(session: AsyncSession = Depends(auth.uow)):
        permission = Permission(
            name=f"peek:{uuid.uuid4().hex[:12]}",
            display_name="UoW regression fixture",
        )
        session.add(permission)
        await session.flush()
        return {"name": permission.name}

    if instrument:
        auth.instrument_fastapi(app)
    return app


async def _visible_from_second_connection(test_engine, name: str) -> bool:
    """Query from a fresh session (separate pooled connection): only committed
    rows are visible here."""
    other_connections = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with other_connections() as session:
        row = (
            await session.execute(select(Permission).where(Permission.name == name))
        ).scalar_one_or_none()
    return row is not None


async def _drive_post_and_check_visibility(app: FastAPI, test_engine) -> dict[str, Any]:
    """Drive the ASGI app by hand: the ``send`` callable runs while the request
    is still inside the routing layer — dependency teardown has NOT run yet,
    which is exactly when a fast client can already be issuing its next
    request. Records whether the created row was visible from a second
    connection at the moment the client had the complete response."""
    body = bytearray()
    seen: dict[str, Any] = {}

    async def receive() -> dict:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict) -> None:
        if message["type"] == "http.response.start":
            seen["status"] = message["status"]
        elif message["type"] == "http.response.body":
            body.extend(message.get("body", b""))
            if not message.get("more_body"):
                # The client now has the complete response.
                name = json.loads(bytes(body))["name"]
                seen["name"] = name
                seen["visible"] = await _visible_from_second_connection(test_engine, name)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/things",
        "raw_path": b"/things",
        "query_string": b"",
        "root_path": "",
        "headers": [(b"host", b"testserver")],
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
    }

    await app(scope, receive, send)
    return seen


async def test_write_is_committed_before_response_reaches_client(test_engine, simple_auth):
    app = _build_app(simple_auth, instrument=True)

    seen = await _drive_post_and_check_visibility(app, test_engine)

    assert seen["status"] == 201
    assert seen["visible"] is True, (
        f"{seen['name']} was not visible from a second connection at the moment the "
        "client finished receiving the 201 — the commit is racing the response again"
    )


async def test_manual_drive_detects_the_race_when_middleware_is_absent(test_engine, simple_auth):
    """Experimental control for the test above: without UnitOfWorkMiddleware,
    the legacy teardown commit runs after the response, so the row must NOT
    be visible yet when the client has the 201 — proving the apparatus
    actually detects the race rather than passing vacuously. If FastAPI ever
    moves dependency teardown before the response, this fails and the
    fallback (and this control) can be retired."""
    app = _build_app(simple_auth, instrument=False)

    seen = await _drive_post_and_check_visibility(app, test_engine)

    assert seen["status"] == 201
    assert seen["visible"] is False
    # Teardown has run by now: the legacy path still commits, just late.
    assert await _visible_from_second_connection(test_engine, seen["name"])


async def test_uow_still_commits_in_teardown_without_middleware(test_engine, simple_auth):
    """Apps that never call instrument_fastapi keep the legacy behavior:
    teardown commits (after the response, but it does commit)."""
    app = _build_app(simple_auth, instrument=False)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/things")

    assert response.status_code == 201
    assert await _visible_from_second_connection(test_engine, response.json()["name"])


async def test_read_method_write_is_rolled_back_through_middleware(test_engine, simple_auth):
    app = _build_app(simple_auth, instrument=True)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/peek")

    assert response.status_code == 200
    assert not await _visible_from_second_connection(test_engine, response.json()["name"])


async def test_handler_exception_rolls_back_and_middleware_does_not_commit(test_engine, simple_auth):
    app = _build_app(simple_auth, instrument=True)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/things-conflict")

    assert response.status_code == 409
    name = response.json()["detail"]
    assert not await _visible_from_second_connection(test_engine, name)
