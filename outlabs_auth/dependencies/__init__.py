"""
FastAPI dependency injection helpers (dynamic signatures).

This module provides `AuthDeps`, which generates FastAPI dependencies with a
signature that includes all configured auth transports so they show up in
OpenAPI/Swagger.
"""

import inspect
from inspect import Parameter, Signature
from typing import Any, Callable, Optional, Sequence, cast
from uuid import UUID

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

    def _permission_set_allows(
        self,
        required_permission: str,
        granted_permissions: Sequence[str],
    ) -> bool:
        permission_service = self.services.get("permission_service")
        normalized = {
            ("*:*" if permission == "*" else permission)
            for permission in granted_permissions
            if permission
        }
        if permission_service and hasattr(permission_service, "_permission_set_allows"):
            return bool(
                permission_service._permission_set_allows(required_permission, normalized)
            )
        return required_permission in normalized or "*:*" in normalized

    async def _auth_result_has_permission(
        self,
        *,
        auth_result: dict,
        session: AsyncSession,
        permission: str,
        entity_id: Optional[UUID],
        resource_context: Optional[dict],
        env_context: Optional[dict],
    ) -> bool:
        source = auth_result.get("source")
        permission_service = self.services.get("permission_service")
        api_key_service = self.api_key_service
        service_token_service = self.services.get("service_token_service")

        if source == "service_token":
            granted_permissions = (auth_result.get("metadata") or {}).get("permissions", [])
            if service_token_service is not None:
                return bool(
                    service_token_service.check_service_permission(
                        auth_result.get("metadata") or {},
                        permission,
                    )
                )
            return self._permission_set_allows(permission, granted_permissions)

        if source == "api_key" and auth_result.get("integration_principal_id"):
            api_key = auth_result.get("api_key")
            api_key_scopes = (auth_result.get("metadata") or {}).get("scopes", [])
            principal_allowed_scopes = (auth_result.get("metadata") or {}).get("principal_allowed_scopes", [])
            if api_key is None or api_key_service is None:
                return False

            if not api_key_service.scopes_allow_permission(api_key_scopes, permission):
                return False
            if not api_key_service.scopes_allow_permission(principal_allowed_scopes, permission):
                return False
            if entity_id is not None:
                has_entity_access = await api_key_service.check_entity_access_with_tree(
                    session,
                    api_key,
                    entity_id,
                )
                if not has_entity_access:
                    return False

            if permission_service is None:
                return True

            if getattr(getattr(permission_service, "config", None), "enable_abac", False):
                if await permission_service.permission_has_conditions(session, permission):
                    return False
            return True

        user_id = auth_result.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User ID not found in auth result",
            )

        try:
            user_id_uuid = user_id if isinstance(user_id, UUID) else UUID(str(user_id))
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user ID in auth result",
            )

        if permission_service is None:
            return False

        try:
            has_permission = await permission_service.check_permission(
                session,
                user_id=user_id_uuid,
                permission=permission,
                entity_id=entity_id,
                resource_context=resource_context,
                env_context=env_context,
                user=auth_result.get("user"),
            )
        except TypeError as exc:
            if "unexpected keyword argument 'user'" not in str(exc):
                raise
            has_permission = await permission_service.check_permission(
                session,
                user_id=user_id_uuid,
                permission=permission,
                entity_id=entity_id,
                resource_context=resource_context,
                env_context=env_context,
            )
        if not has_permission:
            return False

        if source != "api_key":
            return True

        api_key = auth_result.get("api_key")
        api_key_scopes = (auth_result.get("metadata") or {}).get("scopes", [])
        if api_key is None or api_key_service is None:
            return False

        if not api_key_service.scopes_allow_permission(api_key_scopes, permission):
            return False

        if entity_id is not None:
            return bool(
                await api_key_service.check_entity_access_with_tree(
                    session,
                    api_key,
                    entity_id,
                )
            )

        return True

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

        return cast(Callable[..., Any], dependency)

    def require_permission(
        self,
        *permissions: str,
        require_all: bool = False,
        allow_entity_context_header: bool = False,
        resource_context_provider: Optional[
            Callable[[Request, AsyncSession, dict], Any]
        ] = None,
    ) -> Callable:
        signature = self._get_dependency_signature()

        def _parse_uuid(raw: Any, *, detail: str) -> UUID:
            if raw is None or raw == "":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=detail,
                )
            try:
                return raw if isinstance(raw, UUID) else UUID(str(raw))
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=detail,
                )

        def _parse_entity_context_id(request: Request) -> Optional[UUID]:
            raw = (
                request.path_params.get("entity_id")
                or request.query_params.get("entity_id")
            )
            if not raw and allow_entity_context_header:
                raw = request.headers.get("X-Entity-Context")
            if not raw:
                return None
            return _parse_uuid(raw, detail="Invalid entity context ID")

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
            abac_enabled = bool(
                getattr(getattr(permission_service, "config", None), "enable_abac", False)
            )

            if session is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Database session not configured for auth dependencies",
                )

            entity_id = _parse_entity_context_id(request)
            resource_context: Optional[dict] = None
            env_context: Optional[dict] = None
            if abac_enabled:
                request_resource_context = getattr(request.state, "resource_context", None)
                request_resource_context = (
                    request_resource_context
                    if isinstance(request_resource_context, dict)
                    else None
                )

                if resource_context_provider is not None:
                    maybe_context = resource_context_provider(request, session, auth_result)
                    if inspect.isawaitable(maybe_context):
                        maybe_context = await maybe_context
                    if isinstance(maybe_context, dict):
                        resource_context = (
                            {**request_resource_context, **maybe_context}
                            if request_resource_context
                            else maybe_context
                        )
                else:
                    resource_context = request_resource_context

                env_context = {
                    "method": request.method,
                    "path": request.url.path,
                    "client_host": request.client.host if request.client else None,
                    "user_agent": request.headers.get("user-agent"),
                }

            if require_all:
                for perm in permissions:
                    has_perm = await self._auth_result_has_permission(
                        auth_result=auth_result,
                        session=session,
                        permission=perm,
                        entity_id=entity_id,
                        resource_context=resource_context,
                        env_context=env_context,
                    )
                    if not has_perm:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="Insufficient permissions",
                        )
            else:
                has_any = False
                for perm in permissions:
                    if await self._auth_result_has_permission(
                        auth_result=auth_result,
                        session=session,
                        permission=perm,
                        entity_id=entity_id,
                        resource_context=resource_context,
                        env_context=env_context,
                    ):
                        has_any = True
                        break

                if not has_any:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Insufficient permissions",
                    )

            return cast(dict[Any, Any], auth_result)

        return cast(Callable[..., Any], dependency)

    def require_entity_permission(
        self, permission: str, entity_id_param: str = "entity_id"
    ) -> Callable:
        """
        Require a permission in a specific entity context.

        Entity ID is sourced in order from:
        - path param `entity_id_param`
        - query param `entity_id_param`
        - `X-Entity-Context` header (only when `entity_id_param == "entity_id"`)
        """
        signature = self._get_dependency_signature()

        def _parse_uuid(raw: Any, *, detail: str) -> UUID:
            if raw is None or raw == "":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=detail
                )
            try:
                return raw if isinstance(raw, UUID) else UUID(str(raw))
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=detail
                )

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
            abac_enabled = bool(
                getattr(getattr(permission_service, "config", None), "enable_abac", False)
            )

            if session is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Database session not configured for auth dependencies",
                )

            raw_entity_id = request.path_params.get(
                entity_id_param
            ) or request.query_params.get(entity_id_param)
            if raw_entity_id is None and entity_id_param == "entity_id":
                raw_entity_id = request.headers.get("X-Entity-Context")

            entity_id = _parse_uuid(raw_entity_id, detail="Entity ID is required")
            resource_context = None
            env_context = None
            if abac_enabled:
                resource_context = getattr(request.state, "resource_context", None)
                resource_context = (
                    resource_context if isinstance(resource_context, dict) else None
                )
                env_context = {
                    "method": request.method,
                    "path": request.url.path,
                    "client_host": request.client.host if request.client else None,
                    "user_agent": request.headers.get("user-agent"),
                }

            has_perm = await self._auth_result_has_permission(
                auth_result=auth_result,
                session=session,
                permission=permission,
                entity_id=entity_id,
                resource_context=resource_context,
                env_context=env_context,
            )
            if not has_perm:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions",
                )

            return cast(dict[Any, Any], auth_result)

        return cast(Callable[..., Any], dependency)

    def require_tree_permission(
        self,
        permission: str,
        entity_id_field: str,
        *,
        source: str = "path",
    ) -> Callable:
        """
        Require a permission in a *target* entity context, allowing inheritance
        from ancestors via `*_tree` / `*_all` permissions.

        `entity_id_field` indicates where to read the target entity ID from:
        - `source="path"`: `request.path_params[entity_id_field]`
        - `source="query"`: `request.query_params[entity_id_field]`
        - `source="header"`: `request.headers[entity_id_field]`
        - `source="body"`: JSON body field `entity_id_field`

        This helper delegates entity-context permission evaluation to
        `permission_service.check_permission(...)`, which already allows:

        - exact-entity non-scoped permissions at the target entity
        - ancestor `*_tree` / `*_all` permissions across descendants

        If `source="body"` and the field is absent/null, this falls back to a
        global permission check (useful for root-level creates).
        """
        if source not in ("path", "query", "header", "body"):
            raise ValueError("source must be one of: path, query, header, body")

        signature = self._get_dependency_signature()

        def _tree_permission_name(permission_name: str) -> str:
            if permission_name in {"*", "*:*"} or ":" not in permission_name:
                return permission_name

            resource, action = permission_name.split(":", 1)
            if action == "*" or action.endswith("_tree") or action.endswith("_all"):
                return permission_name
            return f"{resource}:{action}_tree"

        def _parse_uuid_optional(raw: Any, *, invalid_detail: str) -> Optional[UUID]:
            if raw is None or raw == "":
                return None
            try:
                return raw if isinstance(raw, UUID) else UUID(str(raw))
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=invalid_detail,
                )

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
            abac_enabled = bool(
                getattr(getattr(permission_service, "config", None), "enable_abac", False)
            )

            if session is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Database session not configured for auth dependencies",
                )

            raw_entity_id: Any = None
            if source == "path":
                raw_entity_id = request.path_params.get(entity_id_field)
            elif source == "query":
                raw_entity_id = request.query_params.get(entity_id_field)
            elif source == "header":
                raw_entity_id = request.headers.get(entity_id_field)
            else:
                body = await request.json()
                if isinstance(body, dict):
                    raw_entity_id = body.get(entity_id_field)

            entity_id = _parse_uuid_optional(
                raw_entity_id, invalid_detail=f"Invalid {entity_id_field}"
            )

            required_permission = (
                _tree_permission_name(permission) if entity_id is not None else permission
            )

            resource_context = None
            env_context = None
            if abac_enabled:
                resource_context = getattr(request.state, "resource_context", None)
                resource_context = (
                    resource_context if isinstance(resource_context, dict) else None
                )
                env_context = {
                    "method": request.method,
                    "path": request.url.path,
                    "client_host": request.client.host if request.client else None,
                    "user_agent": request.headers.get("user-agent"),
                }

            has_perm = await self._auth_result_has_permission(
                auth_result=auth_result,
                session=session,
                permission=required_permission,
                entity_id=entity_id,
                resource_context=resource_context,
                env_context=env_context,
            )
            if not has_perm:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions",
                )

            return cast(dict[Any, Any], auth_result)

        return cast(Callable[..., Any], dependency)

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

            return cast(dict[Any, Any], auth_result)

        return cast(Callable[..., Any], dependency)

    def require_superuser(self) -> Callable:
        """
        Require authentication with superuser privileges.

        This dependency checks that:
        1. The user is authenticated
        2. The user has is_superuser=True

        Returns:
            FastAPI dependency that returns auth_result dict if superuser

        Raises:
            HTTPException 401: If not authenticated
            HTTPException 403: If authenticated but not superuser
        """
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
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Not authenticated",
                )

            # Check if user object exists and is superuser
            user = auth_result.get("user")
            if not user or not getattr(user, "is_superuser", False):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Superuser privileges required",
                )

            return cast(dict[Any, Any], auth_result)

        return cast(Callable[..., Any], dependency)

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
