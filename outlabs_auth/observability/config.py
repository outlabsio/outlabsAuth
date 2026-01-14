"""
Observability configuration for OutlabsAuth.

Configures structured logging, Prometheus metrics, and correlation ID tracking.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class LogsFormat(str, Enum):
    """Log output format."""

    JSON = "json"
    TEXT = "text"


class LogsLevel(str, Enum):
    """Log verbosity level."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class PermissionCheckLogging(str, Enum):
    """Permission check logging mode."""

    ALL = "all"
    FAILURES_ONLY = "failures_only"
    NONE = "none"


class ObservabilityConfig(BaseModel):
    """
    Configuration for observability features.

    Controls structured logging, Prometheus metrics, and correlation IDs.

    Examples:
        Development configuration:
        >>> config = ObservabilityConfig(
        ...     logs_format="text",
        ...     logs_level="DEBUG",
        ...     enable_metrics=False,
        ...     log_permission_checks="all"
        ... )

        Production configuration:
        >>> config = ObservabilityConfig(
        ...     logs_format="json",
        ...     logs_level="INFO",
        ...     enable_metrics=True,
        ...     metrics_path="/metrics",
        ...     log_permission_checks="failures_only",
        ...     log_api_key_hits=False
        ... )
    """

    # Logging Configuration
    logs_format: LogsFormat = Field(
        default=LogsFormat.JSON, description="Log output format (json or text)"
    )

    logs_level: LogsLevel = Field(
        default=LogsLevel.INFO, description="Minimum log level to output"
    )

    logs_include_timestamps: bool = Field(
        default=True, description="Include timestamps in log output"
    )

    logs_include_correlation_id: bool = Field(
        default=True, description="Include correlation ID in log output"
    )

    # Metrics Configuration
    enable_metrics: bool = Field(
        default=True, description="Enable Prometheus metrics collection"
    )

    metrics_path: str = Field(
        default="/metrics", description="HTTP path for Prometheus metrics endpoint"
    )

    metrics_include_hostname: bool = Field(
        default=True, description="Include hostname in metric labels"
    )

    # Detailed Logging Controls
    log_permission_checks: PermissionCheckLogging = Field(
        default=PermissionCheckLogging.FAILURES_ONLY,
        description="Permission check logging mode",
    )

    log_api_key_hits: bool = Field(
        default=False, description="Log every API key validation (can be noisy)"
    )

    log_cache_hits: bool = Field(
        default=False, description="Log cache hits/misses (can be noisy)"
    )

    log_db_queries: bool = Field(
        default=False, description="Log database queries with timing (can be noisy)"
    )

    log_jwt_validations: bool = Field(
        default=False, description="Log every JWT validation (can be noisy)"
    )

    # Performance Configuration
    async_logging: bool = Field(
        default=True, description="Use async logging to avoid blocking requests"
    )

    max_log_queue_size: int = Field(
        default=10000, description="Maximum async log queue size before dropping"
    )

    # Correlation ID Configuration
    correlation_id_header: str = Field(
        default="X-Correlation-ID", description="HTTP header name for correlation ID"
    )

    generate_correlation_id: bool = Field(
        default=True, description="Auto-generate correlation ID if not provided"
    )

    # Security Configuration
    log_ip_addresses: bool = Field(
        default=True, description="Include IP addresses in security logs"
    )

    log_user_agents: bool = Field(
        default=True, description="Include user agents in security logs"
    )

    redact_sensitive_data: bool = Field(
        default=True, description="Redact passwords, tokens, etc. from logs"
    )

    log_stack_traces: bool = Field(
        default=True,
        description="Include stack traces in error logs (disable in production for cleaner logs)",
    )

    model_config = ConfigDict(use_enum_values=True)


# Preset configurations for common environments
class ObservabilityPresets:
    """
    Preset observability configurations for common environments.

    Examples:
        >>> config = ObservabilityPresets.development()
        >>> config = ObservabilityPresets.production()
    """

    @staticmethod
    def development() -> ObservabilityConfig:
        """
        Development environment configuration.

        - Text logs (easier to read)
        - DEBUG level (verbose)
        - Metrics disabled (not needed locally)
        - All permission checks logged
        - All detailed logging enabled
        """
        return ObservabilityConfig(
            logs_format=LogsFormat.TEXT,
            logs_level=LogsLevel.DEBUG,
            enable_metrics=False,
            log_permission_checks=PermissionCheckLogging.ALL,
            log_api_key_hits=True,
            log_cache_hits=True,
            log_db_queries=True,
            log_jwt_validations=True,
        )

    @staticmethod
    def staging() -> ObservabilityConfig:
        """
        Staging environment configuration.

        - JSON logs (structured)
        - INFO level (moderate verbosity)
        - Metrics enabled
        - Only permission failures logged
        - Some detailed logging enabled
        """
        return ObservabilityConfig(
            logs_format=LogsFormat.JSON,
            logs_level=LogsLevel.INFO,
            enable_metrics=True,
            log_permission_checks=PermissionCheckLogging.FAILURES_ONLY,
            log_api_key_hits=False,
            log_cache_hits=False,
            log_db_queries=True,
            log_jwt_validations=False,
        )

    @staticmethod
    def production() -> ObservabilityConfig:
        """
        Production environment configuration.

        - JSON logs (structured for aggregation)
        - INFO level (errors + important events)
        - Metrics enabled
        - Only permission failures logged
        - Minimal detailed logging
        """
        return ObservabilityConfig(
            logs_format=LogsFormat.JSON,
            logs_level=LogsLevel.INFO,
            enable_metrics=True,
            log_permission_checks=PermissionCheckLogging.FAILURES_ONLY,
            log_api_key_hits=False,
            log_cache_hits=False,
            log_db_queries=False,
            log_jwt_validations=False,
        )

    @staticmethod
    def disabled() -> ObservabilityConfig:
        """
        Minimal observability configuration.

        - JSON logs
        - ERROR level only
        - No metrics
        - Minimal logging
        """
        return ObservabilityConfig(
            logs_format=LogsFormat.JSON,
            logs_level=LogsLevel.ERROR,
            enable_metrics=False,
            log_permission_checks=PermissionCheckLogging.NONE,
            log_api_key_hits=False,
            log_cache_hits=False,
            log_db_queries=False,
            log_jwt_validations=False,
        )
