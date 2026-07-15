"""
ASGI middleware that finalizes the per-request unit of work before the
response starts.

FastAPI (>=0.106) runs dependency teardown AFTER the response has been sent,
so a unit of work that commits in teardown lets a client observe its own 2xx
and issue a dependent request before the data is committed — an immediate
read-after-create can 404 (observed once in CI). ``OutlabsAuth.uow``
registers its session in the ASGI scope; this middleware commits (write
methods) or rolls back (reads) just before forwarding
``http.response.start``, so no response byte reaches the client until its
writes are durable. A commit failure aborts the response: the client gets a
500 instead of a success status for data that was never persisted.

Error responses are untouched: when a handler raises, the dependency's
teardown rolls back and marks the unit of work finalized while the exception
unwinds, before the error response is built and sent through here.

Written as pure ASGI (not ``BaseHTTPMiddleware``) to avoid the extra
async-generator wrapping overhead that BaseHTTPMiddleware imposes.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from outlabs_auth.core.uow import UOW_SCOPE_KEY, WRITE_METHODS


ASGIApp = Callable[[dict, Callable[[], Awaitable[dict]], Callable[[dict], Awaitable[None]]], Awaitable[None]]


class UnitOfWorkMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self,
        scope: dict,
        receive: Callable[[], Awaitable[dict]],
        send: Callable[[dict], Awaitable[None]],
    ) -> Any:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        async def send_after_finalizing_uow(message: dict) -> None:
            if message["type"] == "http.response.start":
                states = scope.get(UOW_SCOPE_KEY)
                if states:
                    commit = scope.get("method") in WRITE_METHODS
                    for state in states:
                        if state.finalized:
                            continue
                        state.finalized = True
                        if commit:
                            await state.session.commit()
                        else:
                            await state.session.rollback()
            await send(message)

        await self.app(scope, receive, send_after_finalizing_uow)
