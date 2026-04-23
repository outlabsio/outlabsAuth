"""
FastAPI middleware for correlation ID tracking.

Automatically extracts or generates correlation IDs for request tracing.
"""

import uuid

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .service import ObservabilityService


class CorrelationIDMiddleware:
    """
    Middleware to extract or generate correlation IDs for request tracing.

    Reads correlation ID from request header (default: X-Correlation-ID).
    If not present and auto-generation is enabled, generates a new UUID.
    Sets correlation ID in context for all logs during the request.

    Examples:
        >>> from fastapi import FastAPI
        >>> from outlabs_auth.observability import CorrelationIDMiddleware, ObservabilityService
        >>>
        >>> app = FastAPI()
        >>> obs_service = ObservabilityService(config)
        >>> app.add_middleware(CorrelationIDMiddleware, obs_service=obs_service)

    Implemented as pure ASGI (no BaseHTTPMiddleware wrapping) to avoid the
    extra async-generator overhead per request.
    """

    def __init__(self, app: ASGIApp, obs_service: ObservabilityService) -> None:
        self.app = app
        self.obs_service = obs_service
        self.config = obs_service.config

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        header_name = self.config.correlation_id_header
        incoming = Headers(scope=scope).get(header_name)

        correlation_id = incoming
        if not correlation_id and self.config.generate_correlation_id:
            correlation_id = str(uuid.uuid4())

        if correlation_id:
            ObservabilityService.set_correlation_id(correlation_id)

        async def send_with_header(message: Message) -> None:
            if correlation_id and message["type"] == "http.response.start":
                MutableHeaders(scope=message)[header_name] = correlation_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_header)
        finally:
            ObservabilityService.clear_correlation_id()
