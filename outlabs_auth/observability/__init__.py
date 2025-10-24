"""
Observability module for OutlabsAuth.

Provides structured logging, Prometheus metrics, and correlation ID tracking
for debugging, performance monitoring, and security analysis.
"""

from .config import ObservabilityConfig, ObservabilityPresets
from .service import ObservabilityService
from .middleware import CorrelationIDMiddleware

__all__ = [
    "ObservabilityConfig",
    "ObservabilityPresets",
    "ObservabilityService",
    "CorrelationIDMiddleware",
]
