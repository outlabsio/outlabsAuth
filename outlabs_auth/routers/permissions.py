"""
Permissions router factory.

Provides complete CRUD endpoints for permission management.
"""

from typing import Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status

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
    auth: Any,
    prefix: str = "",
    tags: Optional[list[str]] = None
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
        description="List all permissions with pagination (requires permission:read permission)"
    )
    async def list_permissions(
        page: int = Query(1, ge=1, description="Page number (1-indexed)"),
        limit: int = Query(100, ge=1, le=1000, description="Results per page"),
        resource: Optional[str] = Query(None, description="Filter by resource type"),
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
                page=page,
                limit=limit,
                resource=resource
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
                    tags=perm.tags or [],
                    metadata=perm.metadata or {}
                )
                for perm in permissions
            ]

            return PaginatedResponse(
                items=items,
                total=total,
                page=page,
                limit=limit,
                pages=pages
            )
        except HTTPException:
            raise
        except Exception as e:
            obs.log_500_error(e, page=page, limit=limit, resource=resource)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to list permissions"
            )

    @router.post(
        "/",
        response_model=PermissionResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Create permission",
        description="Create new permission (requires permission:create permission)"
    )
    async def create_permission(
        data: PermissionCreateRequest,
        auth_result = Depends(auth.deps.require_permission("permission:create"))
    ):
        """Create a new permission."""
        try:
            # Log the incoming data for debugging
            if auth.observability:
                auth.observability.logger.debug(
                    "permission_create_request",
                    name=data.name,
                    display_name=data.display_name,
                    is_system=data.is_system,
                    is_active=data.is_active,
                    tags_count=len(data.tags)
                )

            # Check if permission already exists
            existing = await auth.permission_service.get_permission_by_name(data.name)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Permission with name '{data.name}' already exists"
                )

            # Create permission using service
            permission = await auth.permission_service.create_permission(
                name=data.name,
                display_name=data.display_name,
                description=data.description or "",
                is_system=data.is_system
            )

            # Update additional fields if provided
            if data.tags:
                permission.tags = data.tags
            if data.metadata:
                permission.metadata = data.metadata
            if not data.is_active:
                permission.is_active = data.is_active

            # Save updated permission
            await permission.save()

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
                tags=permission.tags or [],
                metadata=permission.metadata or {}
            )
        except HTTPException:
            raise
        except Exception as e:
            # Log error with observability
            if auth.observability:
                auth.observability.logger.error(
                    "permission_create_error",
                    error=str(e),
                    error_type=type(e).__name__
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

    @router.get(
        "/{permission_id}",
        response_model=PermissionResponse,
        summary="Get permission",
        description="Get permission details by ID (requires permission:read permission)"
    )
    async def get_permission(
        permission_id: str,
        auth_result = Depends(auth.deps.require_permission("permission:read"))
    ):
        """Get permission details by ID."""
        try:
            from outlabs_auth.models.permission import PermissionModel

            permission = await PermissionModel.get(permission_id)
            if not permission:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Permission not found"
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
                tags=permission.tags or [],
                metadata=permission.metadata or {}
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )

    @router.patch(
        "/{permission_id}",
        response_model=PermissionResponse,
        summary="Update permission",
        description="Update permission details (requires permission:update permission)"
    )
    async def update_permission(
        permission_id: str,
        data: PermissionUpdateRequest,
        auth_result = Depends(auth.deps.require_permission("permission:update"))
    ):
        """Update permission details."""
        try:
            from outlabs_auth.models.permission import PermissionModel

            permission = await PermissionModel.get(permission_id)
            if not permission:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Permission not found"
                )

            # System permissions have restrictions (cannot change name)
            if permission.is_system:
                # Only allow updating description, tags, and metadata for system permissions
                if data.is_active is not None and not data.is_active:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Cannot deactivate system permissions"
                    )

            # Update fields if provided
            if data.display_name is not None:
                permission.display_name = data.display_name
            if data.description is not None:
                permission.description = data.description
            if data.is_active is not None:
                permission.is_active = data.is_active
            if data.tags is not None:
                permission.tags = data.tags
            if data.metadata is not None:
                permission.metadata = data.metadata

            # Save changes
            await permission.save()

            # Log update
            if auth.observability:
                auth.observability.logger.info(
                    "permission_updated",
                    permission_id=permission_id,
                    permission_name=permission.name
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
                tags=permission.tags or [],
                metadata=permission.metadata or {}
            )
        except HTTPException:
            raise
        except Exception as e:
            if auth.observability:
                auth.observability.logger.error(
                    "permission_update_error",
                    error=str(e),
                    permission_id=permission_id
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

    @router.delete(
        "/{permission_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Delete permission",
        description="Delete permission (requires permission:delete permission). Cannot delete system permissions."
    )
    async def delete_permission(
        permission_id: str,
        auth_result = Depends(auth.deps.require_permission("permission:delete"))
    ):
        """Delete permission by ID."""
        try:
            deleted = await auth.permission_service.delete_permission(permission_id)

            if not deleted:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Permission not found"
                )

            # Log deletion
            if auth.observability:
                auth.observability.logger.info(
                    "permission_deleted",
                    permission_id=permission_id
                )

            return None  # 204 No Content
        except HTTPException:
            raise
        except Exception as e:
            if auth.observability:
                auth.observability.logger.error(
                    "permission_delete_error",
                    error=str(e),
                    permission_id=permission_id
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

    @router.get(
        "/me",
        response_model=List[str],
        summary="Get current user's permissions",
        description="Get all permissions for the authenticated user"
    )
    async def get_my_permissions(
        entity_id: Optional[str] = None,
        auth_result = Depends(auth.deps.require_auth())
    ):
        """
        Get all permissions for the currently authenticated user.

        Optionally filter by entity context (for EnterpriseRBAC).
        """
        try:
            user_id = auth_result["user_id"]

            # Get permissions (handle both SimpleRBAC and EnterpriseRBAC)
            # SimpleRBAC: get_user_permissions(user_id)
            # EnterpriseRBAC: get_user_permissions(user_id, entity_id=None)
            try:
                # Try with entity_id parameter (EnterpriseRBAC)
                permissions = await auth.permission_service.get_user_permissions(
                    user_id=user_id,
                    entity_id=entity_id
                )
            except TypeError:
                # Fall back to SimpleRBAC (no entity_id parameter)
                permissions = await auth.permission_service.get_user_permissions(
                    user_id=user_id
                )

            return permissions
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )

    @router.post(
        "/check",
        response_model=PermissionCheckResponse,
        summary="Check permissions",
        description="Check if user has specific permissions (requires permission:check permission)"
    )
    async def check_permissions(
        data: PermissionCheckRequest,
        auth_result = Depends(auth.deps.require_permission("permission:check"))
    ):
        """Check if a user has specific permissions."""
        try:
            # Get user
            user = await auth.user_service.get_user(data.user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )

            # Check each permission
            results = {}
            for permission in data.permissions:
                has_perm = await auth.permission_service.check_permission(
                    user_id=data.user_id,
                    permission=permission,
                    entity_id=data.entity_id
                )
                results[permission] = has_perm

            has_all = all(results.values())

            return PermissionCheckResponse(
                user_id=data.user_id,
                has_all_permissions=has_all,
                results=results
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )

    @router.get(
        "/user/{user_id}",
        response_model=List[str],
        summary="Get user permissions",
        description="Get all permissions for a user (requires permission:read permission)"
    )
    async def get_user_permissions(
        user_id: str,
        entity_id: Optional[str] = None,
        auth_result = Depends(auth.deps.require_permission("permission:read"))
    ):
        """Get all permissions for a user, optionally in a specific entity context."""
        try:
            # Get user
            user = await auth.user_service.get_user(user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )

            # Get permissions (handle both SimpleRBAC and EnterpriseRBAC)
            try:
                # Try with entity_id parameter (EnterpriseRBAC)
                permissions = await auth.permission_service.get_user_permissions(
                    user_id=user_id,
                    entity_id=entity_id
                )
            except TypeError:
                # Fall back to SimpleRBAC (no entity_id parameter)
                permissions = await auth.permission_service.get_user_permissions(
                    user_id=user_id
                )

            return permissions
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )

    return router
