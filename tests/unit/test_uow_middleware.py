"""
Unit tests for UnitOfWorkMiddleware.

The contract under test: a request's unit of work is committed (write
methods) or rolled back (reads) BEFORE ``http.response.start`` is forwarded,
so no response byte can reach the client while its writes are still pending.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from outlabs_auth.core.uow import UOW_SCOPE_KEY, UnitOfWorkState
from outlabs_auth.middleware import UnitOfWorkMiddleware


def _make_state() -> UnitOfWorkState:
    return UnitOfWorkState(SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock()))


def _http_scope(method: str) -> dict:
    return {"type": "http", "method": method}


async def test_write_commit_happens_before_response_start_is_forwarded():
    events: list[str] = []
    state = _make_state()
    state.session.commit.side_effect = lambda: events.append("commit")

    async def inner_app(scope, receive, send):
        scope.setdefault(UOW_SCOPE_KEY, []).append(state)
        await send({"type": "http.response.start", "status": 201, "headers": []})
        await send({"type": "http.response.body", "body": b"{}"})

    async def transport_send(message):
        events.append(message["type"])

    await UnitOfWorkMiddleware(inner_app)(_http_scope("POST"), AsyncMock(), transport_send)

    assert events == ["commit", "http.response.start", "http.response.body"]
    assert state.finalized
    state.session.rollback.assert_not_awaited()


async def test_read_method_rolls_back_instead_of_committing():
    state = _make_state()

    async def inner_app(scope, receive, send):
        scope.setdefault(UOW_SCOPE_KEY, []).append(state)
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"{}"})

    await UnitOfWorkMiddleware(inner_app)(_http_scope("GET"), AsyncMock(), AsyncMock())

    assert state.finalized
    state.session.rollback.assert_awaited_once_with()
    state.session.commit.assert_not_awaited()


async def test_already_finalized_state_is_left_alone():
    """Error path: teardown rolled back while the exception unwound, then the
    error response passes through here — it must not trigger a commit."""
    state = _make_state()
    state.finalized = True

    async def inner_app(scope, receive, send):
        scope.setdefault(UOW_SCOPE_KEY, []).append(state)
        await send({"type": "http.response.start", "status": 409, "headers": []})
        await send({"type": "http.response.body", "body": b"{}"})

    await UnitOfWorkMiddleware(inner_app)(_http_scope("POST"), AsyncMock(), AsyncMock())

    state.session.commit.assert_not_awaited()
    state.session.rollback.assert_not_awaited()


async def test_commit_failure_aborts_response_before_start_is_forwarded():
    """A failed commit must surface as an error, never as a success status
    for data that was not persisted."""
    state = _make_state()
    state.session.commit.side_effect = RuntimeError("commit failed")
    forwarded: list[dict] = []

    async def inner_app(scope, receive, send):
        scope.setdefault(UOW_SCOPE_KEY, []).append(state)
        await send({"type": "http.response.start", "status": 201, "headers": []})

    async def transport_send(message):
        forwarded.append(message)

    with pytest.raises(RuntimeError, match="commit failed"):
        await UnitOfWorkMiddleware(inner_app)(_http_scope("POST"), AsyncMock(), transport_send)

    assert forwarded == []
    assert state.finalized


async def test_requests_without_uow_pass_through_untouched():
    messages = [
        {"type": "http.response.start", "status": 200, "headers": []},
        {"type": "http.response.body", "body": b"ok"},
    ]
    forwarded: list[dict] = []

    async def inner_app(scope, receive, send):
        for message in messages:
            await send(message)

    async def transport_send(message):
        forwarded.append(message)

    await UnitOfWorkMiddleware(inner_app)(_http_scope("POST"), AsyncMock(), transport_send)

    assert forwarded == messages


async def test_non_http_scopes_pass_through():
    inner_app = AsyncMock()
    scope = {"type": "lifespan"}
    receive, send = AsyncMock(), AsyncMock()

    await UnitOfWorkMiddleware(inner_app)(scope, receive, send)

    inner_app.assert_awaited_once_with(scope, receive, send)
