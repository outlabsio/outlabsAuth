"""
FastAPI dependency injection helpers (dynamic signatures).

This module provides `AuthDeps`, which generates FastAPI dependencies with a
signature that includes all configured auth transports so they show up in
OpenAPI/Swagger.
"""

from inspect import Parameter, Signature
from typing import Any, Callable, Optional, Sequence

from fastapi import Depends, HTTPException, Request, status
from makefun import with_signature
from sqlalchemy.ext.asyncio import AsyncSession

from outlabs_auth.authentication.backend import AuthBackend


class AuthDeps:
    """
    Dynamic dependency injection for multiple authentication backends.

    Uses makefun to generate FastAPI dependencies with correct signatures,
    ensuring all auth backends appear correctly in the OpenAPI/Swagger schema.
    """

    def __init__(
        self,
        backends: Sequence[AuthBackend],
        user_service: Any = None,
        api_key_service: Any = None,
        activity_tracker: Any = None,
        get_session: Optional[Callable[..., Any]] = None,
        **services: Any,
    ):
        self.backends = backends
        self.user_service = user_service
        self.api_key_service = api_key_service
        self.activity_tracker = activity_tracker
        self.get_session = get_session
        self.services = services

    def require_auth(
        self, active: bool = True, verified: bool = False, optional: bool = False
    ) -> Callable:
        signature = self._get_dependency_signature()

        @with_signature(signature)
        async def dependency(
            request: Request,
            session: Optional[AsyncSession] = None,
            *args: Any,
            **kwargs: Any,
        ) -> Optional[dict]:
            return await _authenticate_with_session(request, session)

        async def _authenticate_with_session(
            request: Request, session: Optional[AsyncSession]
        ) -> Optional[dict]:
            for backend in self.backends:
                try:
                    result = await backend.authenticate(
                        request,
                        session=session,
                        user_service=self.user_service,
                        api_key_service=self.api_key_service,
                        **self.services,
                    )

                    if result:
                        if active and result.get("user"):
                            if not result["user"].can_authenticate():
                                continue

                        if verified and result.get("user"):
                            if not result["user"].email_verified:
                                continue

                        if self.activity_tracker and result.get("user"):
                            import asyncio

                            user_id = str(result["user"].id)
                            asyncio.create_task(
                                self.activity_tracker.track_activity(user_id)
                            )

                        return result

                except Exception:
                    continue

            if optional:
                return None

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
            )

        return dependency

    def require_permission(
        self, *permissions: str, require_all: bool = False
    ) -> Callable:
        signature = self._get_dependency_signature()

        @with_signature(signature)
        async def dependency(
            request: Request,
            session: Optional[AsyncSession] = None,
            *args: Any,
            **kwargs: Any,
        ) -> dict:
            auth_result = await self.require_auth()(
                request=request, session=session, *args, **kwargs
            )

            if not auth_result:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

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

            if session is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Database session not configured for auth dependencies",
                )

            if require_all:
                for perm in permissions:
                    has_perm = await permission_service.check_permission(
                        session, user_id=user_id, permission=perm
                    )
                    if not has_perm:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="Insufficient permissions",
                        )
            else:
                has_any = False
                for perm in permissions:
                    if await permission_service.check_permission(
                        session, user_id=user_id, permission=perm
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
        signature = self._get_dependency_signature()

        @with_signature(signature)
        async def dependency(
            request: Request,
            session: Optional[AsyncSession] = None,
            *args: Any,
            **kwargs: Any,
        ) -> dict:
            auth_result = await self.require_auth()(
                request=request, session=session, *args, **kwargs
            )

            if not auth_result or auth_result.get("source") != source:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Authentication via {source} required",
                )

            return auth_result

        return dependency

    def _get_dependency_signature(self) -> Signature:
        parameters = [
            Parameter(
                name="request", kind=Parameter.POSITIONAL_OR_KEYWORD, annotation=Request
            )
        ]

        if self.get_session:
            parameters.append(
                Parameter(
                    name="session",
                    kind=Parameter.POSITIONAL_OR_KEYWORD,
                    default=Depends(self.get_session),
                    annotation=AsyncSession,
                )
            )

        for backend in self.backends:
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
    return AuthDeps(backends=backends, **services)


__all__ = ["AuthDeps", "create_auth_deps"]
