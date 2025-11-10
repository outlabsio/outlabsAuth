"""
Dynamic dependency injection with makefun for perfect OpenAPI schema.

Implements dynamic dependency pattern from FastAPI-Users (DD-039).
"""

from inspect import Parameter, Signature
from typing import Any, Callable, Optional, Sequence

from fastapi import Depends, HTTPException, Request, status
from makefun import with_signature

from outlabs_auth.authentication.backend import AuthBackend


class AuthDeps:
    """
    Dynamic dependency injection for multiple authentication backends.

    Uses makefun to generate FastAPI dependencies with correct signatures,
    ensuring all auth backends appear correctly in the OpenAPI/Swagger schema.

    Example:
        ```python
        # Define backends
        jwt_backend = AuthBackend(name="jwt", ...)
        api_key_backend = AuthBackend(name="api_key", ...)

        # Initialize dependencies
        deps = AuthDeps(
            backends=[jwt_backend, api_key_backend],
            user_service=user_service,
            api_key_service=api_key_service
        )

        # Use in routes - ALL backends appear in Swagger UI!
        @app.get("/protected")
        async def protected_route(user = Depends(deps.require_auth())):
            return {"user": user}
        ```
    """

    def __init__(
        self,
        backends: Sequence[AuthBackend],
        user_service: Any = None,
        api_key_service: Any = None,
        activity_tracker: Any = None,
        **services: Any,
    ):
        """
        Initialize dynamic dependencies.

        Args:
            backends: List of authentication backends
            user_service: UserService instance (for JWT, etc.)
            api_key_service: ApiKeyService instance (for API keys)
            activity_tracker: ActivityTracker instance (for DAU/MAU tracking)
            **services: Additional services for strategies
        """
        self.backends = backends
        self.user_service = user_service
        self.api_key_service = api_key_service
        self.activity_tracker = activity_tracker
        self.services = services

    def require_auth(
        self, active: bool = True, verified: bool = False, optional: bool = False
    ) -> Callable:
        """
        Generate dependency that requires authentication from any backend.

        Args:
            active: Require user to be active (default: True)
            verified: Require user to be verified (default: False)
            optional: Return None if not authenticated (default: False, raises 401)

        Returns:
            FastAPI dependency function with dynamic signature

        Example:
            ```python
            # Any valid auth method works
            @app.get("/me")
            async def get_me(auth_result = Depends(deps.require_auth())):
                return auth_result

            # Require verified users only
            @app.get("/verified-only")
            async def verified_route(
                auth_result = Depends(deps.require_auth(verified=True))
            ):
                return auth_result
            ```
        """
        # Generate dynamic signature for this dependency
        signature = self._get_dependency_signature()

        @with_signature(signature)
        async def dependency(
            request: Request, *args: Any, **kwargs: Any
        ) -> Optional[dict]:
            """Try all backends in order until one authenticates."""
            # request is now a direct parameter, not from kwargs

            # Try each backend
            for backend in self.backends:
                try:
                    # Authenticate using this backend
                    result = await backend.authenticate(
                        request,
                        user_service=self.user_service,
                        api_key_service=self.api_key_service,
                        **self.services,
                    )

                    if result:
                        # Check active status
                        if active and result.get("user"):
                            if not result["user"].can_authenticate():
                                continue  # Try next backend

                        # Check verified status
                        if verified and result.get("user"):
                            if not result["user"].email_verified:
                                continue  # Try next backend

                        # Track activity (fire-and-forget, non-blocking)
                        if self.activity_tracker and result.get("user"):
                            import asyncio

                            user_id = str(result["user"].id)
                            asyncio.create_task(
                                self.activity_tracker.track_activity(user_id)
                            )

                        # Authentication successful
                        return result

                except Exception:
                    # Backend failed, try next one
                    continue

            # No backend authenticated
            if optional:
                return None

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
            )

        return dependency

    def require_permission(
        self, *permissions: str, require_all: bool = False
    ) -> Callable:
        """
        Generate dependency that requires specific permissions.

        Args:
            *permissions: Permission strings to check
            require_all: Require ALL permissions (default: False, requires ANY)

        Returns:
            FastAPI dependency function

        Example:
            ```python
            # Require any permission
            @app.delete("/users/{id}")
            async def delete_user(
                auth = Depends(deps.require_permission("user:delete", "admin:all"))
            ):
                return {"deleted": True}

            # Require all permissions
            @app.post("/admin/critical")
            async def critical_action(
                auth = Depends(deps.require_permission(
                    "admin:all", "system:critical", require_all=True
                ))
            ):
                return {"success": True}
            ```
        """
        signature = self._get_dependency_signature()

        @with_signature(signature)
        async def dependency(*args: Any, **kwargs: Any) -> dict:
            """Authenticate and check permissions."""
            # First, authenticate
            auth_result = await self.require_auth()(*args, **kwargs)

            if not auth_result:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

            # Fetch user's permissions from database
            permission_service = self.services.get("permission_service")
            if not permission_service:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Permission service not configured",
                )

            user_id = auth_result.get("user_id")
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User ID not found in auth result",
                )

            # Check permissions using permission service (handles wildcards properly)
            if require_all:
                # Require ALL permissions
                for perm in permissions:
                    has_perm = await permission_service.check_permission(
                        user_id=user_id, permission=perm
                    )
                    if not has_perm:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="Insufficient permissions",
                        )
            else:
                # Require ANY permission
                has_any = False
                for perm in permissions:
                    if await permission_service.check_permission(
                        user_id=user_id, permission=perm
                    ):
                        has_any = True
                        break

                if not has_any:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Insufficient permissions",
                    )

            return auth_result

        return dependency

    def require_source(self, source: str) -> Callable:
        """
        Generate dependency that requires specific auth source.

        Args:
            source: Required authentication source (e.g., "api_key", "service_token")

        Returns:
            FastAPI dependency function

        Example:
            ```python
            # API keys only
            @app.get("/api-only")
            async def api_only(auth = Depends(deps.require_source("api_key"))):
                return {"key": auth["metadata"]["key_prefix"]}

            # Service tokens only (microservices)
            @app.post("/internal")
            async def internal(auth = Depends(deps.require_source("service_token"))):
                return {"service": auth["service_name"]}
            ```
        """
        signature = self._get_dependency_signature()

        @with_signature(signature)
        async def dependency(*args: Any, **kwargs: Any) -> dict:
            """Authenticate and check source."""
            auth_result = await self.require_auth()(*args, **kwargs)

            if not auth_result or auth_result.get("source") != source:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Authentication via {source} required",
                )

            return auth_result

        return dependency

    def _get_dependency_signature(self) -> Signature:
        """
        Generate dynamic signature for dependency functions.

        This is the "magic" that makes all auth backends appear in OpenAPI schema.
        Uses makefun to generate a function signature with parameters for each backend.

        Returns:
            Signature object for use with @with_signature decorator
        """
        parameters = [
            # Always include request
            Parameter(
                name="request", kind=Parameter.POSITIONAL_OR_KEYWORD, annotation=Request
            )
        ]

        # Add parameters for each backend's transport
        # This makes them appear in OpenAPI schema
        for backend in self.backends:
            # Each backend gets its own parameter
            # FastAPI will call the transport to get credentials
            parameters.append(
                Parameter(
                    name=f"{backend.name}_credentials",
                    kind=Parameter.POSITIONAL_OR_KEYWORD,
                    default=Depends(backend.transport.get_credentials),
                    annotation=Optional[str],
                )
            )

        return Signature(parameters)


def create_auth_deps(backends: Sequence[AuthBackend], **services: Any) -> AuthDeps:
    """
    Factory function to create AuthDeps instance.

    Args:
        backends: List of authentication backends
        **services: Service instances (user_service, api_key_service, etc.)

    Returns:
        AuthDeps instance

    Example:
        ```python
        deps = create_auth_deps(
            backends=[jwt_backend, api_key_backend],
            user_service=user_service,
            api_key_service=api_key_service
        )
        ```
    """
    return AuthDeps(backends=backends, **services)
