"""
ASGI middleware that resets the per-request memoization cache on entry.

Written as pure ASGI (not ``BaseHTTPMiddleware``) to avoid the extra
async-generator wrapping overhead that BaseHTTPMiddleware imposes.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from outlabs_auth.services import request_cache


ASGIApp = Callable[[dict, Callable[[], Awaitable[dict]], Callable[[dict], Awaitable[None]]], Awaitable[None]]


class RequestCacheMiddleware:
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

        request_cache.reset()
        try:
            await self.app(scope, receive, send)
        finally:
            request_cache.reset()
