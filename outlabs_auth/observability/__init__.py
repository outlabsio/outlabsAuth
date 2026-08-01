"""
Observability module for OutlabsAuth.

Provides structured logging, Prometheus metrics, and correlation ID tracking
for debugging, performance monitoring, and security analysis.
"""

from .config import ObservabilityConfig, ObservabilityPresets
from .dependencies import (
    ObservabilityContext,
    ObservabilityDeps,
    get_observability_dependency,
    get_observability_with_auth,
)
from .middleware import CorrelationIDMiddleware
from .router import create_metrics_router
from .service import ObservabilityService

__all__ = [
    "ObservabilityConfig",
    "ObservabilityPresets",
    "ObservabilityService",
    "CorrelationIDMiddleware",
    "create_metrics_router",
    "ObservabilityContext",
    "ObservabilityDeps",
    "get_observability_dependency",
    "get_observability_with_auth",
]
