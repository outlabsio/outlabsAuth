"""Mounted auth-surface discovery and the minimal capabilities router."""

from enum import Enum
from typing import Any, Iterable, Optional

from fastapi import APIRouter, Request
from fastapi.routing import APIRoute

from outlabs_auth._version import __version__
from outlabs_auth.schemas.auth import AuthConfigResponse

AUTH_SURFACE_OPENAPI_EXTENSION = "x-outlabs-auth-surface"


def mark_auth_surface(router: APIRouter, surface: str) -> APIRouter:
    """Mark every API route in a factory with its stable auth surface name."""
    for route in router.routes:
        if not isinstance(route, APIRoute):
            continue
        extra = dict(route.openapi_extra or {})
        raw_surfaces = extra.get(AUTH_SURFACE_OPENAPI_EXTENSION, [])
        surfaces = [raw_surfaces] if isinstance(raw_surfaces, str) else list(raw_surfaces)
        if surface not in surfaces:
            surfaces.append(surface)
        extra[AUTH_SURFACE_OPENAPI_EXTENSION] = sorted(surfaces)
        route.openapi_extra = extra
    return router


def discover_mounted_auth_surfaces(app: Any) -> list[str]:
    """Return auth surfaces actually included in a FastAPI application."""
    surfaces: set[str] = set()
    visited: set[int] = set()

    def visit_routes(routes: Iterable[Any]) -> None:
        for route in routes:
            if id(route) in visited:
                continue
            visited.add(id(route))
            if isinstance(route, APIRoute):
                raw_surfaces = (route.openapi_extra or {}).get(AUTH_SURFACE_OPENAPI_EXTENSION, [])
                if isinstance(raw_surfaces, str):
                    surfaces.add(raw_surfaces)
                else:
                    surfaces.update(str(surface) for surface in raw_surfaces)
            original_router = getattr(route, "original_router", None)
            if original_router is not None:
                visit_routes(getattr(original_router, "routes", []))

    visit_routes(getattr(app, "routes", []))
    return sorted(surfaces)


def missing_auth_surfaces(app: Any, required: Iterable[str]) -> list[str]:
    """Return required surface names that are not mounted on the application."""
    mounted = set(discover_mounted_auth_surfaces(app))
    return sorted(set(required) - mounted)


def assert_auth_surfaces(app: Any, required: Iterable[str]) -> None:
    """Fail a host contract test when required auth surfaces are not mounted."""
    missing = missing_auth_surfaces(app, required)
    if missing:
        raise AssertionError(f"Missing OutlabsAuth router surfaces: {', '.join(missing)}")


def build_auth_config_response(auth: Any, request: Request) -> AuthConfigResponse:
    """Build public capabilities from runtime config and actually mounted routes."""
    features = {
        "entity_hierarchy": auth.config.enable_entity_hierarchy,
        "context_aware_roles": auth.config.enable_context_aware_roles,
        "abac": auth.config.enable_abac,
        "tree_permissions": auth.config.enable_entity_hierarchy,
        "api_keys": True,
        "system_api_keys": True,
        "user_status": True,
        "activity_tracking": True,
        "invitations": auth.config.enable_invitations,
        "magic_links": auth.config.enable_magic_links,
        "access_codes": auth.config.enable_access_codes,
    }
    auth_methods = {
        "password": True,
        "magic_link": auth.config.enable_magic_links,
        "access_code": auth.config.enable_access_codes,
    }
    return AuthConfigResponse(
        library_version=__version__,
        preset=auth.__class__.__name__,
        features=features,
        auth_methods=auth_methods,
        mounted_surfaces=discover_mounted_auth_surfaces(request.app),
    )


def get_capabilities_router(
    auth: Any,
    prefix: str = "",
    tags: Optional[list[str | Enum]] = None,
) -> APIRouter:
    """Expose public capability discovery without mounting login/register flows."""
    router = APIRouter(prefix=prefix, tags=tags or ["auth-capabilities"])

    @router.get(
        "/config",
        response_model=AuthConfigResponse,
        summary="Get auth configuration",
        description="Returns enabled features and the auth surfaces mounted by this host.",
    )
    async def get_config(request: Request) -> AuthConfigResponse:
        return build_auth_config_response(auth, request)

    return mark_auth_surface(router, "capabilities")
