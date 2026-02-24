"""
Resource context middleware for ABAC.

Allows callers (UI, services) to attach `resource.*` attributes for ABAC evaluation
without forcing each router to manually construct a resource context.
"""

import json
from typing import Any, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class ResourceContextMiddleware(BaseHTTPMiddleware):
    """
    Populate `request.state.resource_context` from an HTTP header.

    Header:
      - `X-Resource-Context`: JSON object (e.g. {"status":"draft","owner_id":"..."})

    Notes:
      - This does not grant permissions. It only provides context for ABAC.
      - Invalid JSON returns 400.
      - Size is capped to avoid abuse.
      - Header parsing is disabled by default; enable with trust_client_header=True.
    """

    def __init__(
        self,
        app,
        *,
        header_name: str = "X-Resource-Context",
        max_bytes: int = 8_192,
        trust_client_header: bool = False,
    ):
        super().__init__(app)
        self.header_name = header_name
        self.max_bytes = max_bytes
        self.trust_client_header = trust_client_header

    async def dispatch(self, request: Request, call_next) -> Response:
        if not self.trust_client_header:
            return await call_next(request)

        raw: Optional[str] = request.headers.get(self.header_name)
        if raw:
            if len(raw.encode("utf-8")) > self.max_bytes:
                return JSONResponse(
                    status_code=413,
                    content={"detail": f"{self.header_name} too large"},
                )
            try:
                parsed: Any = json.loads(raw)
            except Exception:
                return JSONResponse(
                    status_code=400,
                    content={"detail": f"Invalid {self.header_name} JSON"},
                )

            if not isinstance(parsed, dict):
                return JSONResponse(
                    status_code=400,
                    content={"detail": f"{self.header_name} must be a JSON object"},
                )

            request.state.resource_context = parsed

        return await call_next(request)
