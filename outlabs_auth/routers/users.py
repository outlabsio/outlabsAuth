"""
Users router factory.

Provides ready-to-use user management routes (DD-041).
"""

from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status

from outlabs_auth.schemas.user import (
    UserResponse,
    UserUpdateRequest,
    ChangePasswordRequest,
)


def get_users_router(
    auth: Any,
    prefix: str = "",
    tags: Optional[list[str]] = None,
    requires_verification: bool = False
) -> APIRouter:
    """
    Generate user management router.

    Args:
        auth: OutlabsAuth instance (SimpleRBAC or EnterpriseRBAC)
        prefix: Router prefix (default: "")
        tags: OpenAPI tags (default: ["users"])
        requires_verification: Require email verification (default: False)

    Returns:
        APIRouter with user management endpoints

    Routes:
        GET /me - Get current user profile
        PATCH /me - Update current user profile
        POST /me/change-password - Change password
        GET /{user_id} - Get user by ID (admin only)
        PATCH /{user_id} - Update user by ID (admin only)
        DELETE /{user_id} - Delete user by ID (admin only)

    Example:
        ```python
        from outlabs_auth import SimpleRBAC
        from outlabs_auth.routers import get_users_router

        auth = SimpleRBAC(database=db)
        app.include_router(get_users_router(auth, prefix="/users"))
        ```
    """
    router = APIRouter(prefix=prefix, tags=tags or ["users"])

    @router.get(
        "/me",
        response_model=UserResponse,
        summary="Get current user",
        description="Get the authenticated user's profile"
    )
    async def get_me(auth_result = Depends(auth.deps.require_auth(verified=requires_verification))):
        """Get current user profile."""
        user = auth_result["user"]
        return UserResponse(
            id=str(user.id),
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            status=user.status.value,
            email_verified=user.email_verified,
            is_superuser=user.is_superuser
        )

    @router.patch(
        "/me",
        response_model=UserResponse,
        summary="Update current user",
        description="Update the authenticated user's profile"
    )
    async def update_me(
        data: UserUpdateRequest,
        auth_result = Depends(auth.deps.require_auth(verified=requires_verification))
    ):
        """
        Update current user profile.

        Triggers on_after_update hook.
        """
        try:
            user = await auth.user_service.update_user(
                user_id=auth_result["user_id"],
                update_dict=data.model_dump(exclude_unset=True)
            )
            return user
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

    @router.post(
        "/me/change-password",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Change password",
        description="Change the authenticated user's password"
    )
    async def change_password(
        data: ChangePasswordRequest,
        auth_result = Depends(auth.deps.require_auth(verified=requires_verification))
    ):
        """
        Change user password.

        Requires current password for verification.
        """
        try:
            # Verify current password
            is_valid = await auth.auth_service.verify_password(
                user=auth_result["user"],
                password=data.current_password
            )

            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid current password"
                )

            # Update password
            await auth.user_service.update_user(
                user_id=auth_result["user_id"],
                update_dict={"password": data.new_password}
            )

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )

        return None

    @router.get(
        "/{user_id}",
        response_model=UserResponse,
        summary="Get user by ID",
        description="Get any user's profile (requires user:read permission)"
    )
    async def get_user(
        user_id: str,
        auth_result = Depends(auth.deps.require_permission("user:read"))
    ):
        """Get user by ID (admin only)."""
        try:
            user = await auth.user_service.get_user(user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            return user
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )

    @router.patch(
        "/{user_id}",
        response_model=UserResponse,
        summary="Update user by ID",
        description="Update any user's profile (requires user:update permission)"
    )
    async def update_user(
        user_id: str,
        data: UserUpdateRequest,
        auth_result = Depends(auth.deps.require_permission("user:update"))
    ):
        """
        Update user by ID (admin only).

        Triggers on_after_update hook.
        """
        try:
            user = await auth.user_service.update_user(
                user_id=user_id,
                update_dict=data.model_dump(exclude_unset=True)
            )
            return user
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

    @router.delete(
        "/{user_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Delete user",
        description="Delete user account (requires user:delete permission)"
    )
    async def delete_user(
        user_id: str,
        auth_result = Depends(auth.deps.require_permission("user:delete"))
    ):
        """
        Delete user by ID (admin only).

        Triggers on_before_delete and on_after_delete hooks.
        """
        try:
            await auth.user_service.delete_user(user_id)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

        return None

    return router
