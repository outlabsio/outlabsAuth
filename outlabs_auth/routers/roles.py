"""
Roles router factory.

Provides ready-to-use role management routes (DD-041).
"""

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from outlabs_auth.observability import ObservabilityContext, get_observability_with_auth
from outlabs_auth.schemas.common import PaginatedResponse
from outlabs_auth.schemas.role import (
    RoleCreateRequest,
    RoleResponse,
    RoleUpdateRequest,
)


def get_roles_router(
    auth: Any, prefix: str = "", tags: Optional[list[str]] = None
) -> APIRouter:
    """
    Generate role management router.

    Args:
        auth: OutlabsAuth instance (SimpleRBAC or EnterpriseRBAC)
        prefix: Router prefix (default: "")
        tags: OpenAPI tags (default: ["roles"])

    Returns:
        APIRouter with role management endpoints

    Routes:
        GET / - List all roles
        POST / - Create new role
        GET /{role_id} - Get role details
        PATCH /{role_id} - Update role
        DELETE /{role_id} - Delete role
        POST /{role_id}/permissions - Add permissions to role
        DELETE /{role_id}/permissions - Remove permissions from role

    Example:
        ```python
        from outlabs_auth import SimpleRBAC
        from outlabs_auth.routers import get_roles_router

        auth = SimpleRBAC(database=db)
        app.include_router(get_roles_router(auth, prefix="/roles"))
        ```
    """
    router = APIRouter(prefix=prefix, tags=tags or ["roles"])

    @router.get(
        "/",
        response_model=PaginatedResponse[RoleResponse],
        summary="List roles",
        description="List all roles with pagination (requires role:read permission)",
    )
    async def list_roles(
        page: int = Query(1, ge=1, description="Page number (1-indexed)"),
        limit: int = Query(20, ge=1, le=100, description="Results per page"),
        is_global: Optional[bool] = Query(
            None, description="Filter by global/non-global roles"
        ),
        obs: ObservabilityContext = Depends(
            get_observability_with_auth(
                auth.observability,
                auth.deps.require_permission("role:read"),
            )
        ),
    ):
        """List all roles with pagination and optional filtering."""
        try:
            roles, total = await auth.role_service.list_roles(
                page=page, limit=limit, is_global=is_global
            )

            # Calculate total pages
            pages = (total + limit - 1) // limit if total > 0 else 0

            # Convert to response schema (exclude Link fields)
            items = [
                RoleResponse(**role.model_dump(mode="json", exclude={"entity"}))
                for role in roles
            ]

            return PaginatedResponse(
                items=items, total=total, page=page, limit=limit, pages=pages
            )
        except HTTPException:
            raise
        except Exception as e:
            obs.log_500_error(e, page=page, limit=limit, is_global=is_global)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to list roles",
            )

    @router.post(
        "/",
        response_model=RoleResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Create role",
        description="Create new role (requires role:create permission)",
    )
    async def create_role(
        data: RoleCreateRequest,
        auth_result=Depends(auth.deps.require_permission("role:create")),
    ):
        """Create a new role."""
        try:
            # Log the incoming data for debugging
            import traceback

            if auth.observability:
                auth.observability.logger.debug(
                    "role_create_request",
                    name=data.name,
                    display_name=data.display_name,
                    permissions_count=len(data.permissions),
                    is_global=data.is_global,
                )

            role = await auth.role_service.create_role(
                name=data.name,
                display_name=data.display_name,
                description=data.description,
                permissions=data.permissions,
                is_global=data.is_global,
            )
            return RoleResponse(**role.model_dump(mode="json", exclude={"entity"}))
        except Exception as e:
            # Log error with observability
            if auth.observability:
                auth.observability.logger.error(
                    "role_create_error",
                    error=str(e),
                    error_type=type(e).__name__,
                    traceback=traceback.format_exc(),
                )
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    @router.get(
        "/{role_id}",
        response_model=RoleResponse,
        summary="Get role",
        description="Get role details by ID",
    )
    async def get_role(
        role_id: str, auth_result=Depends(auth.deps.require_permission("role:read"))
    ):
        """Get role details by ID."""
        try:
            role = await auth.role_service.get_role_by_id(role_id)
            if not role:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Role not found"
                )
            return RoleResponse(**role.model_dump(mode="json", exclude={"entity"}))
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
            )

    @router.patch(
        "/{role_id}",
        response_model=RoleResponse,
        summary="Update role",
        description="Update role details (requires role:update permission)",
    )
    async def update_role(
        role_id: str,
        data: RoleUpdateRequest,
        auth_result=Depends(auth.deps.require_permission("role:update")),
    ):
        """Update role details."""
        try:
            # Log the incoming data for debugging
            import traceback

            update_dict = data.model_dump(exclude_unset=True)

            if auth.observability:
                auth.observability.logger.debug(
                    "role_update_request",
                    role_id=role_id,
                    fields_to_update=list(update_dict.keys()),
                    has_permissions="permissions" in update_dict,
                )

            role = await auth.role_service.update_role(
                role_id=role_id, update_dict=update_dict
            )
            return RoleResponse(**role.model_dump(mode="json", exclude={"entity"}))
        except HTTPException:
            raise
        except Exception as e:
            # Log error with observability
            if auth.observability:
                auth.observability.logger.error(
                    "role_update_error",
                    role_id=role_id,
                    error=str(e),
                    error_type=type(e).__name__,
                    traceback=traceback.format_exc(),
                )
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    @router.delete(
        "/{role_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Delete role",
        description="Delete role (requires role:delete permission)",
    )
    async def delete_role(
        role_id: str, auth_result=Depends(auth.deps.require_permission("role:delete"))
    ):
        """Delete a role."""
        try:
            await auth.role_service.delete_role(role_id)
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        return None

    @router.post(
        "/{role_id}/permissions",
        response_model=RoleResponse,
        summary="Add permissions",
        description="Add permissions to role (requires role:update permission)",
    )
    async def add_permissions(
        role_id: str,
        permissions: List[str],
        auth_result=Depends(auth.deps.require_permission("role:update")),
    ):
        """Add permissions to a role."""
        try:
            role = await auth.role_service.add_permissions(
                role_id=role_id, permissions=permissions
            )
            return RoleResponse(**role.model_dump(mode="json", exclude={"entity"}))
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    @router.delete(
        "/{role_id}/permissions",
        response_model=RoleResponse,
        summary="Remove permissions",
        description="Remove permissions from role (requires role:update permission)",
    )
    async def remove_permissions(
        role_id: str,
        permissions: List[str],
        auth_result=Depends(auth.deps.require_permission("role:update")),
    ):
        """Remove permissions from a role."""
        try:
            role = await auth.role_service.remove_permissions(
                role_id=role_id, permissions=permissions
            )
            return RoleResponse(**role.model_dump(mode="json", exclude={"entity"}))
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return router
