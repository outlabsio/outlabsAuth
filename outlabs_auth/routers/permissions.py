"""
Permissions router factory.

Provides complete CRUD endpoints for permission management.
"""

from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from outlabs_auth.observability import ObservabilityContext, get_observability_with_auth
from outlabs_auth.schemas.common import PaginatedResponse
from outlabs_auth.schemas.permission import (
    PermissionCheckRequest,
    PermissionCheckResponse,
    PermissionCreateRequest,
    PermissionResponse,
    PermissionUpdateRequest,
)


def get_permissions_router(
    auth: Any, prefix: str = "", tags: Optional[list[str]] = None
) -> APIRouter:
    """
    Generate permissions management router.

    Args:
        auth: OutlabsAuth instance (SimpleRBAC or EnterpriseRBAC)
        prefix: Router prefix (default: "")
        tags: OpenAPI tags (default: ["permissions"])

    Returns:
        APIRouter with permission management endpoints

    Routes:
        GET / - List all permissions with pagination
        POST / - Create new permission
        GET /{permission_id} - Get permission details
        PATCH /{permission_id} - Update permission
        DELETE /{permission_id} - Delete permission
        GET /me - Get current user's permissions
        POST /check - Check if user has specific permissions
        GET /user/{user_id} - Get all permissions for a user

    Example:
        ```python
        from outlabs_auth import SimpleRBAC
        from outlabs_auth.routers import get_permissions_router

        auth = SimpleRBAC(database=db)
        app.include_router(get_permissions_router(auth, prefix="/permissions"))
        ```
    """
    router = APIRouter(prefix=prefix, tags=tags or ["permissions"])

    @router.get(
        "/",
        response_model=PaginatedResponse[PermissionResponse],
        summary="List permissions",
        description="List all permissions with pagination (requires permission:read permission)",
    )
    async def list_permissions(
        page: int = Query(1, ge=1, description="Page number (1-indexed)"),
        limit: int = Query(100, ge=1, le=1000, description="Results per page"),
        resource: Optional[str] = Query(None, description="Filter by resource type"),
        session: AsyncSession = Depends(auth.uow),
        obs: ObservabilityContext = Depends(
            get_observability_with_auth(
                auth.observability,
                auth.deps.require_permission("permission:read"),
            )
        ),
    ):
        """List all permissions with pagination and optional filtering."""
        try:
            permissions, total = await auth.permission_service.list_permissions(
                session, page=page, limit=limit, resource=resource
            )

            # Calculate total pages
            pages = (total + limit - 1) // limit if total > 0 else 0

            # Convert to response schema
            items = [
                PermissionResponse(
                    id=str(perm.id),
                    name=perm.name,
                    display_name=perm.display_name,
                    description=perm.description,
                    resource=perm.resource,
                    action=perm.action,
                    scope=perm.scope,
                    is_system=perm.is_system,
                    is_active=perm.is_active,
                    tags=[],
                    metadata={},
                )
                for perm in permissions
            ]

            return PaginatedResponse(
                items=items, total=total, page=page, limit=limit, pages=pages
            )
        except HTTPException:
            raise
        except Exception as e:
            obs.log_500_error(e, page=page, limit=limit, resource=resource)
            raise

    @router.post(
        "/",
        response_model=PermissionResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Create permission",
        description="Create new permission (requires permission:create permission)",
    )
    async def create_permission(
        data: PermissionCreateRequest,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_permission("permission:create")),
    ):
        """Create a new permission."""
        if auth.observability:
            auth.observability.logger.debug(
                "permission_create_request",
                name=data.name,
                display_name=data.display_name,
                is_system=data.is_system,
                is_active=data.is_active,
                tags_count=len(data.tags),
            )

        existing = await auth.permission_service.get_permission_by_name(
            session, data.name
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Permission with name '{data.name}' already exists",
            )

        permission = await auth.permission_service.create_permission(
            session,
            name=data.name,
            display_name=data.display_name,
            description=data.description or "",
            is_system=data.is_system,
            is_active=data.is_active,
            tags=data.tags,
        )

        permission = await auth.permission_service.get_permission_by_id(
            session, permission.id, load_tags=True
        )
        if not permission:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to load created permission",
            )

        return PermissionResponse(
            id=str(permission.id),
            name=permission.name,
            display_name=permission.display_name,
            description=permission.description,
            resource=permission.resource,
            action=permission.action,
            scope=permission.scope,
            is_system=permission.is_system,
            is_active=permission.is_active,
            tags=[t.name for t in permission.tags] if permission.tags else [],
            metadata={},
        )

    @router.get(
        "/{permission_id}",
        response_model=PermissionResponse,
        summary="Get permission",
        description="Get permission details by ID (requires permission:read permission)",
    )
    async def get_permission(
        permission_id: UUID,
        auth_result=Depends(auth.deps.require_permission("permission:read")),
        session: AsyncSession = Depends(auth.uow),
    ):
        """Get permission details by ID."""
        permission = await auth.permission_service.get_permission_by_id(
            session, permission_id, load_tags=True
        )
        if not permission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found"
            )

        return PermissionResponse(
            id=str(permission.id),
            name=permission.name,
            display_name=permission.display_name,
            description=permission.description,
            resource=permission.resource,
            action=permission.action,
            scope=permission.scope,
            is_system=permission.is_system,
            is_active=permission.is_active,
            tags=[tag.name for tag in permission.tags] if permission.tags else [],
            metadata={},
        )

    @router.patch(
        "/{permission_id}",
        response_model=PermissionResponse,
        summary="Update permission",
        description="Update permission details (requires permission:update permission)",
    )
    async def update_permission(
        permission_id: UUID,
        data: PermissionUpdateRequest,
        auth_result=Depends(auth.deps.require_permission("permission:update")),
        session: AsyncSession = Depends(auth.uow),
    ):
        """Update permission details."""
        await auth.permission_service.update_permission(
            session,
            permission_id,
            display_name=data.display_name,
            description=data.description,
            is_active=data.is_active,
            tags=data.tags,
        )

        permission = await auth.permission_service.get_permission_by_id(
            session, permission_id, load_tags=True
        )
        if not permission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Permission not found",
            )

        if auth.observability:
            auth.observability.logger.info(
                "permission_updated",
                permission_id=str(permission_id),
                permission_name=permission.name,
            )

        return PermissionResponse(
            id=str(permission.id),
            name=permission.name,
            display_name=permission.display_name,
            description=permission.description,
            resource=permission.resource,
            action=permission.action,
            scope=permission.scope,
            is_system=permission.is_system,
            is_active=permission.is_active,
            tags=[t.name for t in permission.tags] if permission.tags else [],
            metadata={},
        )

    @router.delete(
        "/{permission_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Delete permission",
        description="Delete permission (requires permission:delete permission). Cannot delete system permissions.",
    )
    async def delete_permission(
        permission_id: UUID,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_permission("permission:delete")),
    ):
        """Delete permission by ID."""
        deleted = await auth.permission_service.delete_permission(
            session, permission_id
        )

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found"
            )

        if auth.observability:
            auth.observability.logger.info(
                "permission_deleted", permission_id=str(permission_id)
            )

        return None  # 204 No Content

    @router.get(
        "/me",
        response_model=List[str],
        summary="Get current user's permissions",
        description="Get all permissions for the authenticated user",
    )
    async def get_my_permissions(
        entity_id: Optional[str] = None,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_auth()),
    ):
        """
        Get all permissions for the currently authenticated user.

        Optionally filter by entity context (for EnterpriseRBAC).
        """
        user_id = UUID(auth_result["user_id"])
        return await auth.permission_service.get_user_permissions(
            session, user_id=user_id
        )

    @router.post(
        "/check",
        response_model=PermissionCheckResponse,
        summary="Check permissions",
        description="Check if user has specific permissions (requires permission:check permission)",
    )
    async def check_permissions(
        data: PermissionCheckRequest,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_permission("permission:check")),
    ):
        """Check if a user has specific permissions."""
        user = await auth.user_service.get_user_by_id(session, UUID(data.user_id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        results = {}
        for permission in data.permissions:
            has_perm = await auth.permission_service.check_permission(
                session, user_id=UUID(data.user_id), permission=permission
            )
            results[permission] = has_perm

        has_all = all(results.values())
        return PermissionCheckResponse(
            user_id=data.user_id, has_all_permissions=has_all, results=results
        )

    @router.get(
        "/user/{user_id}",
        response_model=List[str],
        summary="Get user permissions",
        description="Get all permissions for a user (requires permission:read permission)",
    )
    async def get_user_permissions(
        user_id: UUID,
        entity_id: Optional[str] = None,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_permission("permission:read")),
    ):
        """Get all permissions for a user, optionally in a specific entity context."""
        user = await auth.user_service.get_user_by_id(session, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        return await auth.permission_service.get_user_permissions(
            session, user_id=user_id
        )

    return router
