"""
FastAPI router for Prometheus metrics endpoint.

Provides /metrics endpoint for Prometheus scraping.
"""

from fastapi import APIRouter, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST


def create_metrics_router(path: str = "/metrics") -> APIRouter:
    """
    Create FastAPI router for Prometheus metrics endpoint.

    Args:
        path: URL path for metrics endpoint (default: /metrics)

    Returns:
        FastAPI router with metrics endpoint

    Examples:
        >>> from fastapi import FastAPI
        >>> from outlabs_auth.observability import create_metrics_router
        >>>
        >>> app = FastAPI()
        >>> app.include_router(create_metrics_router())
    """
    router = APIRouter(tags=["observability"])

    @router.get(path)
    async def metrics() -> Response:
        """
        Prometheus metrics endpoint.

        Returns metrics in Prometheus exposition format.
        """
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST,
        )

    return router
