"""
Resource context middleware for ABAC.

Allows callers (UI, services) to attach `resource.*` attributes for ABAC evaluation
without forcing each router to manually construct a resource context.
"""

import json
from typing import Any

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send


class ResourceContextMiddleware:
    """
    Populate `request.state.resource_context` from an HTTP header.

    Header:
      - `X-Resource-Context`: JSON object (e.g. {"status":"draft","owner_id":"..."})

    Notes:
      - This does not grant permissions. It only provides context for ABAC.
      - Invalid JSON returns 400.
      - Size is capped to avoid abuse.
      - Header parsing is disabled by default; enable with trust_client_header=True.

    Implemented as pure ASGI (no BaseHTTPMiddleware wrapping) to avoid the
    extra async-generator overhead per request.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        header_name: str = "X-Resource-Context",
        max_bytes: int = 8_192,
        trust_client_header: bool = False,
    ) -> None:
        self.app = app
        self.header_name = header_name
        self.max_bytes = max_bytes
        self.trust_client_header = trust_client_header

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not self.trust_client_header:
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        raw = headers.get(self.header_name)
        if not raw:
            await self.app(scope, receive, send)
            return

        if len(raw.encode("utf-8")) > self.max_bytes:
            await _send_json_error(
                send,
                status_code=413,
                detail=f"{self.header_name} too large",
            )
            return

        try:
            parsed: Any = json.loads(raw)
        except Exception:
            await _send_json_error(
                send,
                status_code=400,
                detail=f"Invalid {self.header_name} JSON",
            )
            return

        if not isinstance(parsed, dict):
            await _send_json_error(
                send,
                status_code=400,
                detail=f"{self.header_name} must be a JSON object",
            )
            return

        scope.setdefault("state", {})["resource_context"] = parsed
        await self.app(scope, receive, send)


async def _send_json_error(send: Send, *, status_code: int, detail: str) -> None:
    body = json.dumps({"detail": detail}).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status_code,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body, "more_body": False})


__all__ = ["ResourceContextMiddleware"]
