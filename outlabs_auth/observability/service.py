"""
Observability service for OutlabsAuth.

Unified service for emitting structured logs and Prometheus metrics.
"""

import asyncio
import socket
import structlog
from contextvars import ContextVar
from datetime import datetime
from typing import Any, Dict, Optional
from prometheus_client import Counter, Histogram, Gauge

from .config import ObservabilityConfig, LogsFormat, LogsLevel, PermissionCheckLogging


# Context variable for correlation ID
correlation_id_var: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


class ObservabilityService:
    """
    Unified observability service for structured logging and metrics.

    Provides a single emission point for both logs and metrics to ensure
    consistency and simplify instrumentation.

    Examples:
        >>> obs = ObservabilityService(config)
        >>> await obs.initialize()
        >>>
        >>> # Emit login success (logs + metrics)
        >>> obs.log_and_count(
        ...     event="user_login_success",
        ...     level="info",
        ...     user_id="123",
        ...     method="password"
        ... )
        >>>
        >>> # Time an operation
        >>> with obs.time_operation("login", method="password"):
        ...     await authenticate_user()
    """

    def __init__(self, config: ObservabilityConfig):
        """
        Initialize observability service.

        Args:
            config: Observability configuration
        """
        self.config = config
        self.hostname = socket.gethostname()
        self.logger: Optional[structlog.BoundLogger] = None
        self._log_queue: Optional[asyncio.Queue] = None
        self._log_worker_task: Optional[asyncio.Task] = None

        # Prometheus metrics (will be initialized in initialize())
        self.metrics: Dict[str, Any] = {}

    async def initialize(self) -> None:
        """
        Initialize observability service.

        Sets up structured logging with structlog and defines Prometheus metrics.
        """
        # Configure structlog
        self._configure_structlog()

        # Initialize Prometheus metrics if enabled
        if self.config.enable_metrics:
            self._initialize_metrics()

        # Start async log worker if enabled
        if self.config.async_logging:
            self._log_queue = asyncio.Queue(maxsize=self.config.max_log_queue_size)
            self._log_worker_task = asyncio.create_task(self._log_worker())

        self.logger.info(
            "observability_initialized",
            logs_format=self.config.logs_format,
            logs_level=self.config.logs_level,
            metrics_enabled=self.config.enable_metrics,
            async_logging=self.config.async_logging,
        )

    async def shutdown(self) -> None:
        """Shutdown observability service gracefully."""
        if self._log_worker_task:
            # Wait for queue to drain
            await self._log_queue.join()
            self._log_worker_task.cancel()
            try:
                await self._log_worker_task
            except asyncio.CancelledError:
                pass

        self.logger.info("observability_shutdown")

    def _configure_structlog(self) -> None:
        """Configure structlog for structured logging."""
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
        ]

        # Add correlation ID processor if enabled
        if self.config.logs_include_correlation_id:
            processors.append(self._add_correlation_id)

        # Add hostname if enabled
        if self.config.metrics_include_hostname:
            processors.append(
                structlog.processors.CallsiteParameter(
                    parameters=[structlog.processors.CallsiteParameterAdder.hostname]
                )
            )

        # Choose output format
        if self.config.logs_format == LogsFormat.JSON:
            processors.append(structlog.processors.JSONRenderer())
        else:
            processors.append(structlog.dev.ConsoleRenderer())

        structlog.configure(
            processors=processors,
            wrapper_class=structlog.make_filtering_bound_logger(
                self._get_log_level_int()
            ),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )

        self.logger = structlog.get_logger()

    def _add_correlation_id(
        self, logger: Any, method_name: str, event_dict: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Add correlation ID to log event."""
        correlation_id = correlation_id_var.get()
        if correlation_id:
            event_dict["correlation_id"] = correlation_id
        return event_dict

    def _get_log_level_int(self) -> int:
        """Convert log level string to int."""
        levels = {
            LogsLevel.DEBUG: 10,
            LogsLevel.INFO: 20,
            LogsLevel.WARNING: 30,
            LogsLevel.ERROR: 40,
        }
        return levels.get(self.config.logs_level, 20)

    def _initialize_metrics(self) -> None:
        """Initialize Prometheus metrics."""
        # Authentication metrics
        self.metrics["login_attempts"] = Counter(
            "outlabs_auth_login_attempts_total",
            "Total login attempts",
            ["status", "method"],
        )

        self.metrics["login_duration"] = Histogram(
            "outlabs_auth_login_duration_seconds",
            "Login duration in seconds",
            ["method"],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
        )

        self.metrics["account_locked"] = Counter(
            "outlabs_auth_account_locked_total",
            "Total account lockouts",
        )

        self.metrics["password_reset_requests"] = Counter(
            "outlabs_auth_password_reset_requests_total",
            "Total password reset requests",
        )

        self.metrics["email_verifications"] = Counter(
            "outlabs_auth_email_verifications_total",
            "Total email verifications",
            ["status"],
        )

        # Authorization metrics
        self.metrics["permission_checks"] = Counter(
            "outlabs_auth_permission_checks_total",
            "Total permission checks",
            ["result", "permission"],
        )

        self.metrics["permission_check_duration"] = Histogram(
            "outlabs_auth_permission_check_duration_seconds",
            "Permission check duration in seconds",
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5],
        )

        self.metrics["role_assignments"] = Counter(
            "outlabs_auth_role_assignments_total",
            "Total role assignments",
            ["operation"],
        )

        # Session metrics
        self.metrics["active_sessions"] = Gauge(
            "outlabs_auth_active_sessions",
            "Number of active sessions",
        )

        self.metrics["session_duration"] = Histogram(
            "outlabs_auth_session_duration_seconds",
            "Session duration in seconds",
            buckets=[60, 300, 900, 1800, 3600, 7200, 14400, 28800],
        )

        self.metrics["token_refreshes"] = Counter(
            "outlabs_auth_token_refreshes_total",
            "Total token refresh operations",
            ["status"],
        )

        self.metrics["token_blacklist_checks"] = Counter(
            "outlabs_auth_token_blacklist_checks_total",
            "Total token blacklist checks",
            ["result"],
        )

        # API Key metrics
        self.metrics["api_key_validations"] = Counter(
            "outlabs_auth_api_key_validations_total",
            "Total API key validations",
            ["status"],
        )

        self.metrics["api_key_rate_limit_hits"] = Counter(
            "outlabs_auth_api_key_rate_limit_hits_total",
            "Total API key rate limit hits",
        )

        self.metrics["api_key_usage"] = Counter(
            "outlabs_auth_api_key_usage_total",
            "Total API key usage",
            ["prefix"],
        )

        # Security metrics
        self.metrics["suspicious_activity"] = Counter(
            "outlabs_auth_suspicious_activity_total",
            "Suspicious activity detected",
            ["type"],
        )

        self.metrics["failed_login_attempts"] = Counter(
            "outlabs_auth_failed_login_attempts_total",
            "Failed login attempts",
            ["reason"],
        )

        # Performance metrics
        self.metrics["cache_hits"] = Counter(
            "outlabs_auth_cache_hits_total",
            "Cache hits",
            ["cache_type"],
        )

        self.metrics["cache_misses"] = Counter(
            "outlabs_auth_cache_misses_total",
            "Cache misses",
            ["cache_type"],
        )

        self.metrics["db_query_duration"] = Histogram(
            "outlabs_auth_db_query_duration_seconds",
            "Database query duration in seconds",
            ["operation"],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5],
        )

    async def _log_worker(self) -> None:
        """Background worker for async logging."""
        while True:
            try:
                log_func, args, kwargs = await self._log_queue.get()
                log_func(*args, **kwargs)
                self._log_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                # Can't log errors in the logger itself, print to stderr
                print(f"Error in log worker: {e}", file=__import__("sys").stderr)

    def _emit_log(self, level: str, event: str, **kwargs: Any) -> None:
        """Emit a structured log event."""
        if not self.logger:
            return

        log_method = getattr(self.logger, level, self.logger.info)

        if self.config.async_logging and self._log_queue:
            try:
                self._log_queue.put_nowait((log_method, (event,), kwargs))
            except asyncio.QueueFull:
                # Drop log if queue is full (prevents memory issues)
                pass
        else:
            log_method(event, **kwargs)

    def _increment_counter(self, metric_name: str, labels: Optional[Dict[str, str]] = None, value: float = 1.0) -> None:
        """Increment a Prometheus counter."""
        if not self.config.enable_metrics or metric_name not in self.metrics:
            return

        metric = self.metrics[metric_name]
        if labels:
            metric.labels(**labels).inc(value)
        else:
            metric.inc(value)

    def _observe_histogram(self, metric_name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Observe a value in a Prometheus histogram."""
        if not self.config.enable_metrics or metric_name not in self.metrics:
            return

        metric = self.metrics[metric_name]
        if labels:
            metric.labels(**labels).observe(value)
        else:
            metric.observe(value)

    def _set_gauge(self, metric_name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Set a Prometheus gauge value."""
        if not self.config.enable_metrics or metric_name not in self.metrics:
            return

        metric = self.metrics[metric_name]
        if labels:
            metric.labels(**labels).set(value)
        else:
            metric.set(value)

    # Public API - Authentication Events

    def log_login_success(
        self,
        user_id: str,
        email: str,
        method: str,
        duration_ms: float,
        ip_address: Optional[str] = None,
        **extra: Any,
    ) -> None:
        """Log successful login and increment metrics."""
        self._emit_log(
            "info",
            "user_login_success",
            user_id=user_id,
            email=email,
            method=method,
            duration_ms=duration_ms,
            ip_address=ip_address if self.config.log_ip_addresses else None,
            **extra,
        )
        self._increment_counter("login_attempts", {"status": "success", "method": method})
        self._observe_histogram("login_duration", duration_ms / 1000.0, {"method": method})

    def log_login_failed(
        self,
        email: str,
        reason: str,
        method: str,
        failed_attempts: int,
        ip_address: Optional[str] = None,
        **extra: Any,
    ) -> None:
        """Log failed login and increment metrics."""
        self._emit_log(
            "warning",
            "user_login_failed",
            email=email,
            reason=reason,
            method=method,
            failed_attempts=failed_attempts,
            ip_address=ip_address if self.config.log_ip_addresses else None,
            **extra,
        )
        self._increment_counter("login_attempts", {"status": "failed", "method": method})
        self._increment_counter("failed_login_attempts", {"reason": reason})

    def log_account_locked(
        self,
        user_id: str,
        email: str,
        reason: str,
        ip_address: Optional[str] = None,
        **extra: Any,
    ) -> None:
        """Log account lockout and increment metrics."""
        self._emit_log(
            "warning",
            "account_locked",
            user_id=user_id,
            email=email,
            reason=reason,
            ip_address=ip_address if self.config.log_ip_addresses else None,
            **extra,
        )
        self._increment_counter("account_locked")

    def log_logout(
        self,
        user_id: str,
        session_duration_seconds: float,
        revoke_all_tokens: bool = False,
        **extra: Any,
    ) -> None:
        """Log logout and observe session duration."""
        self._emit_log(
            "info",
            "user_logout",
            user_id=user_id,
            session_duration_seconds=session_duration_seconds,
            revoke_all_tokens=revoke_all_tokens,
            **extra,
        )
        self._observe_histogram("session_duration", session_duration_seconds)

    # Public API - Authorization Events

    def log_permission_check(
        self,
        user_id: str,
        permission: str,
        result: str,  # "granted" or "denied"
        duration_ms: float,
        reason: Optional[str] = None,
        **extra: Any,
    ) -> None:
        """Log permission check and increment metrics."""
        # Respect log_permission_checks config
        should_log = (
            self.config.log_permission_checks == PermissionCheckLogging.ALL
            or (self.config.log_permission_checks == PermissionCheckLogging.FAILURES_ONLY and result == "denied")
        )

        if should_log:
            level = "info" if result == "granted" else "warning"
            self._emit_log(
                level,
                f"permission_check_{result}",
                user_id=user_id,
                permission=permission,
                result=result,
                duration_ms=duration_ms,
                reason=reason,
                **extra,
            )

        self._increment_counter("permission_checks", {"result": result, "permission": permission})
        self._observe_histogram("permission_check_duration", duration_ms / 1000.0)

    def log_role_assigned(
        self,
        user_id: str,
        role_id: str,
        entity_id: Optional[str] = None,
        **extra: Any,
    ) -> None:
        """Log role assignment."""
        self._emit_log(
            "info",
            "role_assigned",
            user_id=user_id,
            role_id=role_id,
            entity_id=entity_id,
            **extra,
        )
        self._increment_counter("role_assignments", {"operation": "assign"})

    def log_role_revoked(
        self,
        user_id: str,
        role_id: str,
        entity_id: Optional[str] = None,
        **extra: Any,
    ) -> None:
        """Log role revocation."""
        self._emit_log(
            "info",
            "role_revoked",
            user_id=user_id,
            role_id=role_id,
            entity_id=entity_id,
            **extra,
        )
        self._increment_counter("role_assignments", {"operation": "revoke"})

    # Public API - API Key Events

    def log_api_key_validated(
        self,
        prefix: str,
        status: str,  # "valid" or "invalid"
        reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        **extra: Any,
    ) -> None:
        """Log API key validation."""
        if self.config.log_api_key_hits:
            level = "info" if status == "valid" else "warning"
            self._emit_log(
                level,
                f"api_key_{status}",
                prefix=prefix,
                status=status,
                reason=reason,
                ip_address=ip_address if self.config.log_ip_addresses else None,
                **extra,
            )

        self._increment_counter("api_key_validations", {"status": status})
        if status == "valid":
            self._increment_counter("api_key_usage", {"prefix": prefix})

    def log_api_key_rate_limited(
        self,
        prefix: str,
        current_count: int,
        limit: int,
        **extra: Any,
    ) -> None:
        """Log API key rate limit hit."""
        self._emit_log(
            "warning",
            "api_key_rate_limited",
            prefix=prefix,
            current_count=current_count,
            limit=limit,
            **extra,
        )
        self._increment_counter("api_key_rate_limit_hits")

    # Public API - Security Events

    def log_suspicious_activity(
        self,
        activity_type: str,
        severity: str,
        details: Dict[str, Any],
        ip_address: Optional[str] = None,
        **extra: Any,
    ) -> None:
        """Log suspicious activity detection."""
        self._emit_log(
            "error",
            "suspicious_activity_detected",
            type=activity_type,
            severity=severity,
            details=details,
            ip_address=ip_address if self.config.log_ip_addresses else None,
            **extra,
        )
        self._increment_counter("suspicious_activity", {"type": activity_type})

    # Public API - Performance Events

    def log_cache_event(
        self,
        cache_type: str,
        result: str,  # "hit" or "miss"
        key: Optional[str] = None,
        **extra: Any,
    ) -> None:
        """Log cache hit/miss."""
        if self.config.log_cache_hits:
            self._emit_log(
                "debug",
                f"cache_{result}",
                cache_type=cache_type,
                result=result,
                key=key,
                **extra,
            )

        if result == "hit":
            self._increment_counter("cache_hits", {"cache_type": cache_type})
        else:
            self._increment_counter("cache_misses", {"cache_type": cache_type})

    def log_db_query(
        self,
        operation: str,
        duration_ms: float,
        collection: Optional[str] = None,
        **extra: Any,
    ) -> None:
        """Log database query."""
        if self.config.log_db_queries:
            self._emit_log(
                "debug",
                "db_query",
                operation=operation,
                duration_ms=duration_ms,
                collection=collection,
                **extra,
            )

        self._observe_histogram("db_query_duration", duration_ms / 1000.0, {"operation": operation})

    # Public API - Session Management

    def set_active_sessions(self, count: int) -> None:
        """Update active sessions gauge."""
        self._set_gauge("active_sessions", count)

    def log_token_refreshed(
        self,
        user_id: str,
        status: str,  # "success" or "failed"
        reason: Optional[str] = None,
        **extra: Any,
    ) -> None:
        """Log token refresh attempt."""
        level = "info" if status == "success" else "warning"
        self._emit_log(
            level,
            f"token_refresh_{status}",
            user_id=user_id,
            status=status,
            reason=reason,
            **extra,
        )
        self._increment_counter("token_refreshes", {"status": status})

    def log_token_blacklist_check(
        self,
        token_jti: str,
        result: str,  # "blacklisted" or "valid"
        **extra: Any,
    ) -> None:
        """Log token blacklist check."""
        if self.config.log_jwt_validations:
            self._emit_log(
                "debug",
                "token_blacklist_check",
                token_jti=token_jti,
                result=result,
                **extra,
            )

        self._increment_counter("token_blacklist_checks", {"result": result})

    # Utility methods

    @staticmethod
    def set_correlation_id(correlation_id: str) -> None:
        """Set correlation ID for current context."""
        correlation_id_var.set(correlation_id)

    @staticmethod
    def get_correlation_id() -> Optional[str]:
        """Get correlation ID from current context."""
        return correlation_id_var.get()

    @staticmethod
    def clear_correlation_id() -> None:
        """Clear correlation ID from current context."""
        correlation_id_var.set(None)
