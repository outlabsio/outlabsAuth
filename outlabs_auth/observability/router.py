"""
FastAPI router for Prometheus metrics endpoint.

Provides /metrics endpoint for Prometheus scraping.
"""

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from .service import ObservabilityService


def create_metrics_router(
    obs_service: ObservabilityService,
    path: str = "/metrics",
    tags: list = None,
) -> APIRouter:
    """
    Create FastAPI router for Prometheus metrics endpoint.

    Args:
        obs_service: Observability service instance
        path: HTTP path for metrics endpoint (default: /metrics)
        tags: Optional FastAPI tags for the endpoint

    Returns:
        FastAPI router with metrics endpoint

    Examples:
        >>> from fastapi import FastAPI
        >>> from outlabs_auth.observability import ObservabilityService, create_metrics_router
        >>>
        >>> app = FastAPI()
        >>> obs_service = ObservabilityService(config)
        >>> await obs_service.initialize()
        >>>
        >>> # Add metrics endpoint
        >>> app.include_router(create_metrics_router(obs_service))
        >>>
        >>> # Metrics now available at http://localhost:8000/metrics
    """
    if not obs_service.config.enable_metrics:
        # Return empty router if metrics disabled
        return APIRouter()

    router = APIRouter(tags=tags or ["Observability"])

    @router.get(path, include_in_schema=False)
    async def metrics():
        """
        Prometheus metrics endpoint.

        Returns metrics in Prometheus text format for scraping.

        Example metrics:
            outlabs_auth_login_attempts_total{method="password",status="success"} 42
            outlabs_auth_permission_checks_total{permission="user:read",result="granted"} 1234
            outlabs_auth_active_sessions 156
        """
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST,
        )

    return router
