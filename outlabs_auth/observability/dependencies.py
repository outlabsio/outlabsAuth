"""
Observability dependencies for FastAPI routes.

Provides automatic request context capture and error logging utilities.
"""

import traceback
from contextvars import ContextVar
from typing import Any, Optional

from fastapi import Request

from .service import ObservabilityService

# Context variable for current request
current_request_var: ContextVar[Optional[Request]] = ContextVar(
    "current_request", default=None
)


class ObservabilityContext:
    """
    Observability context with request information and logging helpers.

    Automatically injected into FastAPI routes via dependency injection,
    providing easy access to structured logging with full request context.

    Example:
        ```python
        @router.get("/users")
        async def list_users(obs: ObservabilityContext = Depends(get_observability)):
            try:
                users = await get_users()
                return users
            except Exception as e:
                # Automatically logs with endpoint, method, correlation_id, etc.
                obs.log_500_error(e)
                raise HTTPException(500, detail=str(e))
        ```
    """

    def __init__(
        self,
        request: Request,
        observability: Optional[ObservabilityService],
        user_id: Optional[str] = None,
    ):
        """
        Initialize observability context.

        Args:
            request: FastAPI request object
            observability: ObservabilityService instance
            user_id: Authenticated user ID (if available)
        """
        self.request = request
        self.observability = observability
        self.user_id = user_id

        # Extract request context
        self.endpoint = request.url.path
        self.method = request.method
        self.correlation_id = (
            observability.get_correlation_id() if observability else None
        )

        # Store request in context var for global access
        current_request_var.set(request)

    def log_500_error(
        self,
        exception: Exception,
        include_stack_trace: bool = True,
        **extra: Any,
    ) -> None:
        """
        Log a 500 error with full request context.

        Automatically captures endpoint, method, correlation_id, user_id.

        Args:
            exception: The exception that occurred
            include_stack_trace: Include full stack trace (default: True)
            **extra: Additional context fields

        Example:
            ```python
            try:
                await some_operation()
            except Exception as e:
                obs.log_500_error(e)
                raise HTTPException(500, detail=str(e))
            ```
        """
        if not self.observability:
            return

        self.observability.log_500_error(
            endpoint=self.endpoint,
            error_class=type(exception).__name__,
            error_message=str(exception),
            method=self.method,
            user_id=self.user_id,
            request_id=self.correlation_id,
            stack_trace=traceback.format_exc() if include_stack_trace else None,
            **extra,
        )

    def log_router_error(
        self,
        router: str,
        operation: str,
        exception: Exception,
        **extra: Any,
    ) -> None:
        """
        Log a router-level error with full context.

        Args:
            router: Router name (e.g., "users", "roles")
            operation: Operation name (e.g., "list_users", "create_role")
            exception: The exception that occurred
            **extra: Additional context fields

        Example:
            ```python
            try:
                role = await create_role(data)
            except Exception as e:
                obs.log_router_error("roles", "create_role", e)
                raise
            ```
        """
        if not self.observability:
            return

        self.observability.log_router_error(
            router=router,
            endpoint=self.endpoint,
            operation=operation,
            error_type=type(exception).__name__,
            error_message=str(exception),
            user_id=self.user_id,
            stack_trace=traceback.format_exc(),
            **extra,
        )

    def log_error(
        self,
        event: str,
        error_message: str,
        **extra: Any,
    ) -> None:
        """
        Log a custom error event with request context.

        Args:
            event: Event name
            error_message: Error message
            **extra: Additional context fields
        """
        if not self.observability:
            return

        self.observability.log_error(
            event=event,
            error_type="CustomError",
            error_message=error_message,
            location=self.endpoint,
            endpoint=self.endpoint,
            user_id=self.user_id,
            **extra,
        )

    def log_exception(
        self,
        exception: Exception,
        context: str,
        **extra: Any,
    ) -> None:
        """
        Log any exception with automatic stack trace.

        Args:
            exception: The exception to log
            context: Additional context (e.g., "database query failed")
            **extra: Additional fields
        """
        if not self.observability:
            return

        self.observability.log_exception(
            exception=exception,
            context=f"{self.endpoint}.{context}",
            user_id=self.user_id,
            endpoint=self.endpoint,
            method=self.method,
            **extra,
        )

    def log_event(self, event: str, **fields: Any) -> None:
        """
        Log a structured event with request context.

        Safe no-op when observability is disabled.
        """
        if not self.observability or not self.observability.logger:
            return

        payload = {
            "endpoint": self.endpoint,
            "method": self.method,
            "request_id": self.correlation_id,
        }

        if self.user_id is not None and "user_id" not in fields:
            payload["user_id"] = self.user_id

        payload.update(fields)

        self.observability.logger.info(event, **payload)


def get_observability_dependency(observability_service: Optional[ObservabilityService]):
    """
    Create a FastAPI dependency that provides ObservabilityContext.

    Args:
        observability_service: The ObservabilityService instance

    Returns:
        FastAPI dependency function

    Usage:
        ```python
        # In your main.py
        auth = SimpleRBAC(database=db)
        await auth.initialize()

        # Create the dependency
        get_observability = get_observability_dependency(auth.observability)

        # Use in routes
        @app.get("/users")
        async def list_users(
            obs: ObservabilityContext = Depends(get_observability)
        ):
            try:
                users = await get_users()
                return users
            except Exception as e:
                obs.log_500_error(e)
                raise HTTPException(500, detail=str(e))
        ```
    """

    async def _get_observability(request: Request) -> ObservabilityContext:
        """Dependency that provides observability context."""
        # Try to extract user_id from request state (set by auth middleware)
        user_id = getattr(request.state, "user_id", None)

        return ObservabilityContext(
            request=request,
            observability=observability_service,
            user_id=user_id,
        )

    return _get_observability


def get_observability_with_auth(
    observability_service: Optional[ObservabilityService],
    auth_dependency: Any,
):
    """
    Create a FastAPI dependency that provides ObservabilityContext with auth.

    Combines authentication and observability, automatically extracting user_id
    from the auth result.

    Args:
        observability_service: The ObservabilityService instance
        auth_dependency: The authentication dependency (e.g., deps.require_auth())

    Returns:
        FastAPI dependency function

    Usage:
        ```python
        # In your router factory
        def get_users_router(auth):
            get_obs = get_observability_with_auth(
                auth.observability,
                auth.deps.require_auth()
            )

            @router.get("/")
            async def list_users(obs: ObservabilityContext = Depends(get_obs)):
                try:
                    users = await get_users()
                    return users
                except Exception as e:
                    obs.log_500_error(e)  # Already has user_id from auth!
                    raise HTTPException(500, detail=str(e))
        ```
    """
    from fastapi import Depends

    async def _get_observability_with_auth(
        request: Request,
        auth_result: Any = Depends(auth_dependency),
    ) -> ObservabilityContext:
        """Dependency that provides observability with authenticated user context."""
        # Extract user_id from auth_result
        user_id = auth_result.get("user_id") if isinstance(auth_result, dict) else None

        return ObservabilityContext(
            request=request,
            observability=observability_service,
            user_id=user_id,
        )

    return _get_observability_with_auth


class ObservabilityDeps:
    """
    Dependency factory for observability contexts.

    Similar to AuthDeps, provides clean API for creating observability dependencies.

    Example:
        ```python
        auth = SimpleRBAC(database=db)
        obs_deps = ObservabilityDeps(auth.observability, auth.deps)

        @router.get("/users")
        async def list_users(
            obs = Depends(obs_deps.with_auth())
        ):
            try:
                users = await get_users()
                return users
            except Exception as e:
                obs.log_500_error(e)
                raise HTTPException(500, detail=str(e))
        ```
    """

    def __init__(
        self,
        observability: Optional[ObservabilityService],
        auth_deps: Optional[Any] = None,
    ):
        """
        Initialize observability dependencies.

        Args:
            observability: ObservabilityService instance
            auth_deps: Optional AuthDeps instance for authenticated contexts
        """
        self.observability = observability
        self.auth_deps = auth_deps

    def get_context(self):
        """
        Get observability context without authentication.

        Returns:
            FastAPI dependency for ObservabilityContext
        """
        return get_observability_dependency(self.observability)

    def with_auth(self, **auth_kwargs):
        """
        Get observability context with authentication.

        Args:
            **auth_kwargs: Arguments to pass to auth_deps.require_auth()

        Returns:
            FastAPI dependency for ObservabilityContext with auth
        """
        if not self.auth_deps:
            raise ValueError("auth_deps is required for with_auth()")

        auth_dependency = self.auth_deps.require_auth(**auth_kwargs)

        return get_observability_with_auth(
            self.observability,
            auth_dependency,
        )

    def with_permission(self, permission: str):
        """
        Get observability context with permission check.

        Args:
            permission: Required permission (e.g., "user:read")

        Returns:
            FastAPI dependency for ObservabilityContext with permission
        """
        if not self.auth_deps:
            raise ValueError("auth_deps is required for with_permission()")

        auth_dependency = self.auth_deps.require_permission(permission)

        return get_observability_with_auth(
            self.observability,
            auth_dependency,
        )
