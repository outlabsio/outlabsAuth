"""
Roles router factory.

Provides ready-to-use role management routes (DD-041).
"""

from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

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
        session: AsyncSession = Depends(auth.uow),
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
                session, page=page, limit=limit, is_global=is_global
            )

            # Calculate total pages
            pages = (total + limit - 1) // limit if total > 0 else 0

            items: List[RoleResponse] = []
            for role in roles:
                permission_names = await auth.role_service.get_role_permission_names(
                    session, role.id
                )
                items.append(
                    RoleResponse(
                        id=str(role.id),
                        name=role.name,
                        display_name=role.display_name,
                        description=role.description,
                        permissions=permission_names,
                        entity_type_permissions=None,
                        is_system_role=role.is_system_role,
                        is_global=role.is_global,
                        assignable_at_types=[],
                    )
                )

            return PaginatedResponse(
                items=items, total=total, page=page, limit=limit, pages=pages
            )
        except HTTPException:
            raise
        except Exception as e:
            obs.log_500_error(e, page=page, limit=limit, is_global=is_global)
            raise

    @router.post(
        "/",
        response_model=RoleResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Create role",
        description="Create new role (requires role:create permission)",
    )
    async def create_role(
        data: RoleCreateRequest,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_permission("role:create")),
    ):
        """Create a new role."""
        role = await auth.role_service.create_role(
            session,
            name=data.name,
            display_name=data.display_name,
            description=data.description,
            permission_names=data.permissions,
            is_global=data.is_global,
        )

        permission_names = await auth.role_service.get_role_permission_names(
            session, role.id
        )
        return RoleResponse(
            id=str(role.id),
            name=role.name,
            display_name=role.display_name,
            description=role.description,
            permissions=permission_names,
            entity_type_permissions=None,
            is_system_role=role.is_system_role,
            is_global=role.is_global,
            assignable_at_types=[],
        )

    @router.get(
        "/{role_id}",
        response_model=RoleResponse,
        summary="Get role",
        description="Get role details by ID",
    )
    async def get_role(
        role_id: UUID,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_permission("role:read")),
    ):
        """Get role details by ID."""
        role = await auth.role_service.get_role_by_id(
            session, role_id, load_permissions=True
        )
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Role not found"
            )
        return RoleResponse(
            id=str(role.id),
            name=role.name,
            display_name=role.display_name,
            description=role.description,
            permissions=role.get_permission_names(),
            entity_type_permissions=None,
            is_system_role=role.is_system_role,
            is_global=role.is_global,
            assignable_at_types=[],
        )

    @router.patch(
        "/{role_id}",
        response_model=RoleResponse,
        summary="Update role",
        description="Update role details (requires role:update permission)",
    )
    async def update_role(
        role_id: UUID,
        data: RoleUpdateRequest,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_permission("role:update")),
    ):
        """Update role details."""
        update_dict = data.model_dump(exclude_unset=True)

        role = await auth.role_service.update_role(
            session,
            role_id=role_id,
            display_name=update_dict.get("display_name"),
            description=update_dict.get("description"),
            is_global=update_dict.get("is_global"),
        )

        if "permissions" in update_dict and update_dict["permissions"] is not None:
            role = await auth.role_service.set_permissions_by_name(
                session,
                role_id=role_id,
                permission_names=update_dict["permissions"],
            )

        return RoleResponse(
            id=str(role.id),
            name=role.name,
            display_name=role.display_name,
            description=role.description,
            permissions=role.get_permission_names()
            if hasattr(role, "permissions")
            else [],
            entity_type_permissions=None,
            is_system_role=role.is_system_role,
            is_global=role.is_global,
            assignable_at_types=[],
        )

    @router.delete(
        "/{role_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Delete role",
        description="Delete role (requires role:delete permission)",
    )
    async def delete_role(
        role_id: UUID,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_permission("role:delete")),
    ):
        """Delete a role."""
        deleted = await auth.role_service.delete_role(session, role_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Role not found"
            )
        return None

    @router.post(
        "/{role_id}/permissions",
        response_model=RoleResponse,
        summary="Add permissions",
        description="Add permissions to role (requires role:update permission)",
    )
    async def add_permissions(
        role_id: UUID,
        permissions: List[str],
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_permission("role:update")),
    ):
        """Add permissions to a role."""
        role = await auth.role_service.add_permissions_by_name(
            session,
            role_id=role_id,
            permission_names=permissions,
        )
        return RoleResponse(
            id=str(role.id),
            name=role.name,
            display_name=role.display_name,
            description=role.description,
            permissions=role.get_permission_names(),
            entity_type_permissions=None,
            is_system_role=role.is_system_role,
            is_global=role.is_global,
            assignable_at_types=[],
        )

    @router.delete(
        "/{role_id}/permissions",
        response_model=RoleResponse,
        summary="Remove permissions",
        description="Remove permissions from role (requires role:update permission)",
    )
    async def remove_permissions(
        role_id: UUID,
        permissions: List[str],
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_permission("role:update")),
    ):
        """Remove permissions from a role."""
        role = await auth.role_service.remove_permissions_by_name(
            session,
            role_id=role_id,
            permission_names=permissions,
        )
        return RoleResponse(
            id=str(role.id),
            name=role.name,
            display_name=role.display_name,
            description=role.description,
            permissions=role.get_permission_names(),
            entity_type_permissions=None,
            is_system_role=role.is_system_role,
            is_global=role.is_global,
            assignable_at_types=[],
        )

    return router
