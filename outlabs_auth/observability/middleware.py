"""
FastAPI middleware for correlation ID tracking.

Automatically extracts or generates correlation IDs for request tracing.
"""

import uuid
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from .service import ObservabilityService


class CorrelationIDMiddleware(BaseHTTPMiddleware):
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
    """

    def __init__(self, app, obs_service: ObservabilityService):
        """
        Initialize correlation ID middleware.

        Args:
            app: FastAPI application
            obs_service: Observability service instance
        """
        super().__init__(app)
        self.obs_service = obs_service
        self.config = obs_service.config

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and inject correlation ID.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/route handler

        Returns:
            HTTP response with correlation ID header
        """
        # Extract correlation ID from header or generate new one
        correlation_id = request.headers.get(self.config.correlation_id_header)

        if not correlation_id and self.config.generate_correlation_id:
            correlation_id = str(uuid.uuid4())

        # Set correlation ID in context
        if correlation_id:
            ObservabilityService.set_correlation_id(correlation_id)

        try:
            # Process request
            response = await call_next(request)

            # Add correlation ID to response headers
            if correlation_id:
                response.headers[self.config.correlation_id_header] = correlation_id

            return response

        finally:
            # Clear correlation ID from context
            ObservabilityService.clear_correlation_id()
