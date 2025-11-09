"""
Observability service for OutlabsAuth.

Unified service for emitting structured logs and Prometheus metrics.
"""

import asyncio
import socket
from contextvars import ContextVar
from datetime import datetime
from typing import Any, Dict, Optional

import structlog
from prometheus_client import Counter, Gauge, Histogram

from .config import LogsFormat, LogsLevel, ObservabilityConfig, PermissionCheckLogging

# Context variable for correlation ID
correlation_id_var: ContextVar[Optional[str]] = ContextVar(
    "correlation_id", default=None
)


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
            # Add hostname directly to every log
            processors.append(
                lambda _, __, event_dict: {**event_dict, "hostname": self.hostname}
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

        # Error metrics (NEW - for 500 error tracking)
        self.metrics["errors_total"] = Counter(
            "outlabs_auth_errors_total",
            "Total errors by type and location",
            ["error_type", "location"],
        )

        self.metrics["500_errors_total"] = Counter(
            "outlabs_auth_500_errors_total",
            "Total 500 Internal Server Errors",
            ["endpoint", "error_class"],
        )

        self.metrics["router_errors_total"] = Counter(
            "outlabs_auth_router_errors_total",
            "Total router-level errors",
            ["router", "endpoint"],
        )

        self.metrics["service_errors_total"] = Counter(
            "outlabs_auth_service_errors_total",
            "Total service-level errors",
            ["service", "operation"],
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

    def _increment_counter(
        self,
        metric_name: str,
        labels: Optional[Dict[str, str]] = None,
        value: float = 1.0,
    ) -> None:
        """Increment a Prometheus counter."""
        if not self.config.enable_metrics or metric_name not in self.metrics:
            return

        metric = self.metrics[metric_name]
        if labels:
            metric.labels(**labels).inc(value)
        else:
            metric.inc(value)

    def _observe_histogram(
        self, metric_name: str, value: float, labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Observe a value in a Prometheus histogram."""
        if not self.config.enable_metrics or metric_name not in self.metrics:
            return

        metric = self.metrics[metric_name]
        if labels:
            metric.labels(**labels).observe(value)
        else:
            metric.observe(value)

    def _set_gauge(
        self, metric_name: str, value: float, labels: Optional[Dict[str, str]] = None
    ) -> None:
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
        self._increment_counter(
            "login_attempts", {"status": "success", "method": method}
        )
        self._observe_histogram(
            "login_duration", duration_ms / 1000.0, {"method": method}
        )

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
        self._increment_counter(
            "login_attempts", {"status": "failed", "method": method}
        )
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
            or (
                self.config.log_permission_checks
                == PermissionCheckLogging.FAILURES_ONLY
                and result == "denied"
            )
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

        self._increment_counter(
            "permission_checks", {"result": result, "permission": permission}
        )
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

        self._observe_histogram(
            "db_query_duration", duration_ms / 1000.0, {"operation": operation}
        )

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

    # Context managers for timing operations

    def time_login(self, method: str):
        """
        Context manager to time login operations.

        Args:
            method: Authentication method (password, google, api_key, etc.)

        Example:
            >>> with obs.time_login("password"):
            ...     await authenticate_user()
        """
        import time
        from contextlib import contextmanager

        @contextmanager
        def _timer():
            start = time.time()
            try:
                yield
            finally:
                duration = (time.time() - start) * 1000  # Convert to ms
                self._observe_histogram(
                    "login_duration", duration / 1000.0, {"method": method}
                )

        return _timer()

    def time_permission_check(self):
        """
        Context manager to time permission check operations.

        Example:
            >>> with obs.time_permission_check() as timer:
            ...     result = await check_permission()
            ...     timer.set_duration_ms()  # Records duration
        """
        import time
        from contextlib import contextmanager

        @contextmanager
        def _timer():
            start = time.time()
            duration_ms = [0.0]  # Mutable container for duration

            class Timer:
                def set_duration(self):
                    duration_ms[0] = (time.time() - start) * 1000

            timer = Timer()
            try:
                yield timer
            finally:
                if duration_ms[0] == 0:
                    # Auto-record if not manually set
                    duration_ms[0] = (time.time() - start) * 1000
                self._observe_histogram(
                    "permission_check_duration", duration_ms[0] / 1000.0
                )

        return _timer()

    def time_db_query(self, operation: str):
        """
        Context manager to time database query operations.

        Args:
            operation: Database operation type (find, insert, update, delete, etc.)

        Example:
            >>> with obs.time_db_query("find"):
            ...     results = await collection.find(query)
        """
        import time
        from contextlib import contextmanager

        @contextmanager
        def _timer():
            start = time.time()
            try:
                yield
            finally:
                duration = (time.time() - start) * 1000  # Convert to ms
                if self.config.log_db_queries:
                    self.log_db_query(operation=operation, duration_ms=duration)

        return _timer()

    # Public API - Error Logging (NEW - for 500 error tracking)

    def log_error(
        self,
        event: str,
        error_type: str,
        error_message: str,
        location: str,
        endpoint: Optional[str] = None,
        user_id: Optional[str] = None,
        stack_trace: Optional[str] = None,
        **extra: Any,
    ) -> None:
        """
        Log a general error with structured context.

        Args:
            event: Event name (e.g., "router_error", "service_error")
            error_type: Error class name (e.g., "ValueError", "DatabaseError")
            error_message: Error message
            location: Where error occurred (e.g., "users_router.list_users")
            endpoint: Optional API endpoint (e.g., "/v1/users")
            user_id: Optional user ID if available
            stack_trace: Optional stack trace for debugging
            **extra: Additional context fields

        Example:
            >>> obs.log_error(
            ...     event="router_error",
            ...     error_type="ValueError",
            ...     error_message="Invalid user ID format",
            ...     location="users_router.get_user",
            ...     endpoint="/v1/users/{user_id}",
            ...     user_id="invalid_id"
            ... )
        """
        self._emit_log(
            "error",
            event,
            error_type=error_type,
            error_message=error_message,
            location=location,
            endpoint=endpoint,
            user_id=user_id,
            stack_trace=stack_trace if self.config.log_stack_traces else None,
            **extra,
        )
        self._increment_counter(
            "errors_total", {"error_type": error_type, "location": location}
        )

    def log_500_error(
        self,
        endpoint: str,
        error_class: str,
        error_message: str,
        method: Optional[str] = None,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
        stack_trace: Optional[str] = None,
        **extra: Any,
    ) -> None:
        """
        Log a 500 Internal Server Error with full context.

        Args:
            endpoint: API endpoint that failed (e.g., "/v1/users")
            error_class: Exception class name (e.g., "DatabaseError")
            error_message: Error message
            method: HTTP method (GET, POST, etc.)
            user_id: User ID if authenticated
            request_id: Request/correlation ID
            stack_trace: Full stack trace for debugging
            **extra: Additional context fields

        Example:
            >>> obs.log_500_error(
            ...     endpoint="/v1/users",
            ...     error_class="DatabaseConnectionError",
            ...     error_message="Unable to connect to MongoDB",
            ...     method="GET",
            ...     stack_trace=traceback.format_exc()
            ... )
        """
        self._emit_log(
            "error",
            "http_500_internal_server_error",
            endpoint=endpoint,
            error_class=error_class,
            error_message=error_message,
            method=method,
            user_id=user_id,
            request_id=request_id,
            stack_trace=stack_trace if self.config.log_stack_traces else None,
            **extra,
        )
        self._increment_counter(
            "500_errors_total", {"endpoint": endpoint, "error_class": error_class}
        )

    def log_router_error(
        self,
        router: str,
        endpoint: str,
        operation: str,
        error_type: str,
        error_message: str,
        user_id: Optional[str] = None,
        stack_trace: Optional[str] = None,
        **extra: Any,
    ) -> None:
        """
        Log a router-level error (e.g., in FastAPI route handlers).

        Args:
            router: Router name (e.g., "users", "roles", "auth")
            endpoint: Full endpoint path (e.g., "/v1/users/{user_id}")
            operation: Operation being performed (e.g., "list_users", "create_role")
            error_type: Exception class name
            error_message: Error message
            user_id: User ID if available
            stack_trace: Stack trace
            **extra: Additional context

        Example:
            >>> obs.log_router_error(
            ...     router="users",
            ...     endpoint="/v1/users",
            ...     operation="list_users",
            ...     error_type="MongoDBError",
            ...     error_message="Connection timeout",
            ...     stack_trace=traceback.format_exc()
            ... )
        """
        self._emit_log(
            "error",
            "router_error",
            router=router,
            endpoint=endpoint,
            operation=operation,
            error_type=error_type,
            error_message=error_message,
            user_id=user_id,
            stack_trace=stack_trace if self.config.log_stack_traces else None,
            **extra,
        )
        self._increment_counter(
            "router_errors_total", {"router": router, "endpoint": endpoint}
        )
        self._increment_counter(
            "errors_total", {"error_type": error_type, "location": f"{router}_router"}
        )

    def log_service_error(
        self,
        service: str,
        operation: str,
        error_type: str,
        error_message: str,
        user_id: Optional[str] = None,
        stack_trace: Optional[str] = None,
        **extra: Any,
    ) -> None:
        """
        Log a service-level error (e.g., in business logic services).

        Args:
            service: Service name (e.g., "auth", "user", "role", "permission")
            operation: Operation being performed (e.g., "login", "create_user")
            error_type: Exception class name
            error_message: Error message
            user_id: User ID if available
            stack_trace: Stack trace
            **extra: Additional context

        Example:
            >>> obs.log_service_error(
            ...     service="auth",
            ...     operation="login",
            ...     error_type="DatabaseError",
            ...     error_message="Failed to query users collection",
            ...     user_id="507f1f77bcf86cd799439011",
            ...     stack_trace=traceback.format_exc()
            ... )
        """
        self._emit_log(
            "error",
            "service_error",
            service=service,
            operation=operation,
            error_type=error_type,
            error_message=error_message,
            user_id=user_id,
            stack_trace=stack_trace if self.config.log_stack_traces else None,
            **extra,
        )
        self._increment_counter(
            "service_errors_total", {"service": service, "operation": operation}
        )
        self._increment_counter(
            "errors_total", {"error_type": error_type, "location": f"{service}_service"}
        )

    def log_exception(
        self,
        exception: Exception,
        context: str,
        user_id: Optional[str] = None,
        **extra: Any,
    ) -> None:
        """
        Log an exception with automatic stack trace capture.

        Args:
            exception: The exception that occurred
            context: Context where exception occurred (e.g., "users_router.create_user")
            user_id: User ID if available
            **extra: Additional context fields

        Example:
            >>> try:
            ...     await some_operation()
            ... except Exception as e:
            ...     obs.log_exception(e, context="users_router.create_user")
            ...     raise
        """
        import traceback

        error_type = type(exception).__name__
        error_message = str(exception)
        stack_trace = traceback.format_exc() if self.config.log_stack_traces else None

        self._emit_log(
            "error",
            "exception_occurred",
            error_type=error_type,
            error_message=error_message,
            context=context,
            user_id=user_id,
            stack_trace=stack_trace,
            **extra,
        )
        self._increment_counter(
            "errors_total", {"error_type": error_type, "location": context}
        )
