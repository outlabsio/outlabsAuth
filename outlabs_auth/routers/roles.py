"""
Roles router factory.

Provides ready-to-use role management routes (DD-041).
"""

from typing import Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query

from outlabs_auth.schemas.role import (
    RoleResponse,
    RoleCreateRequest,
    RoleUpdateRequest,
)


def get_roles_router(
    auth: Any,
    prefix: str = "",
    tags: Optional[list[str]] = None
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
        response_model=List[RoleResponse],
        summary="List roles",
        description="List all roles (requires role:read permission)"
    )
    async def list_roles(
        is_global: Optional[bool] = Query(None, description="Filter by global/non-global roles"),
        auth_result = Depends(auth.deps.require_permission("role:read"))
    ):
        """List all roles with optional filtering."""
        try:
            roles = await auth.role_service.list_roles(is_global=is_global)
            return [RoleResponse(**role.model_dump()) for role in roles]
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )

    @router.post(
        "/",
        response_model=RoleResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Create role",
        description="Create new role (requires role:create permission)"
    )
    async def create_role(
        data: RoleCreateRequest,
        auth_result = Depends(auth.deps.require_permission("role:create"))
    ):
        """Create a new role."""
        try:
            role = await auth.role_service.create_role(
                name=data.name,
                display_name=data.display_name,
                description=data.description,
                permissions=data.permissions,
                entity_type_permissions=data.entity_type_permissions,
                is_global=data.is_global,
                assignable_at_types=data.assignable_at_types
            )
            return RoleResponse(**role.model_dump())
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

    @router.get(
        "/{role_id}",
        response_model=RoleResponse,
        summary="Get role",
        description="Get role details by ID"
    )
    async def get_role(
        role_id: str,
        auth_result = Depends(auth.deps.require_permission("role:read"))
    ):
        """Get role details by ID."""
        try:
            role = await auth.role_service.get_role_by_id(role_id)
            if not role:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Role not found"
                )
            return RoleResponse(**role.model_dump())
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )

    @router.patch(
        "/{role_id}",
        response_model=RoleResponse,
        summary="Update role",
        description="Update role details (requires role:update permission)"
    )
    async def update_role(
        role_id: str,
        data: RoleUpdateRequest,
        auth_result = Depends(auth.deps.require_permission("role:update"))
    ):
        """Update role details."""
        try:
            role = await auth.role_service.update_role(
                role_id=role_id,
                update_dict=data.model_dump(exclude_unset=True)
            )
            return RoleResponse(**role.model_dump())
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

    @router.delete(
        "/{role_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Delete role",
        description="Delete role (requires role:delete permission)"
    )
    async def delete_role(
        role_id: str,
        auth_result = Depends(auth.deps.require_permission("role:delete"))
    ):
        """Delete a role."""
        try:
            await auth.role_service.delete_role(role_id)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        return None

    @router.post(
        "/{role_id}/permissions",
        response_model=RoleResponse,
        summary="Add permissions",
        description="Add permissions to role (requires role:update permission)"
    )
    async def add_permissions(
        role_id: str,
        permissions: List[str],
        auth_result = Depends(auth.deps.require_permission("role:update"))
    ):
        """Add permissions to a role."""
        try:
            role = await auth.role_service.add_permissions(
                role_id=role_id,
                permissions=permissions
            )
            return RoleResponse(**role.model_dump())
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

    @router.delete(
        "/{role_id}/permissions",
        response_model=RoleResponse,
        summary="Remove permissions",
        description="Remove permissions from role (requires role:update permission)"
    )
    async def remove_permissions(
        role_id: str,
        permissions: List[str],
        auth_result = Depends(auth.deps.require_permission("role:update"))
    ):
        """Remove permissions from a role."""
        try:
            role = await auth.role_service.remove_permissions(
                role_id=role_id,
                permissions=permissions
            )
            return RoleResponse(**role.model_dump())
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

    return router
