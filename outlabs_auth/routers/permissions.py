"""
Permissions router factory.

Provides utility endpoints for permission checking and listing.
"""

from typing import Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, status

from outlabs_auth.schemas.permission import (
    PermissionCheckRequest,
    PermissionCheckResponse,
)


def get_permissions_router(
    auth: Any,
    prefix: str = "",
    tags: Optional[list[str]] = None
) -> APIRouter:
    """
    Generate permissions utility router.

    Args:
        auth: OutlabsAuth instance (SimpleRBAC or EnterpriseRBAC)
        prefix: Router prefix (default: "")
        tags: OpenAPI tags (default: ["permissions"])

    Returns:
        APIRouter with permission utility endpoints

    Routes:
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

            # Get permissions
            permissions = await auth.permission_service.get_user_permissions(
                user_id=user_id,
                entity_id=entity_id
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
