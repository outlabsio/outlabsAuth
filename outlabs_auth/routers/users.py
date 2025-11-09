"""
Users router factory.

Provides ready-to-use user management routes (DD-041).
"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from outlabs_auth.observability import ObservabilityContext, get_observability_with_auth
from outlabs_auth.schemas.common import PaginatedResponse
from outlabs_auth.schemas.user import (
    ChangePasswordRequest,
    UserCreateRequest,
    UserResponse,
    UserUpdateRequest,
)


def get_users_router(
    auth: Any,
    prefix: str = "",
    tags: Optional[list[str]] = None,
    requires_verification: bool = False,
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
        POST / - Create new user (admin only, requires user:create permission)
        GET / - List users with pagination (requires user:read permission)
        GET /me - Get current user profile
        PATCH /me - Update current user profile
        POST /me/change-password - Change password
        GET /{user_id} - Get user by ID (requires user:read permission)
        PATCH /{user_id} - Update user by ID (requires user:update permission)
        DELETE /{user_id} - Delete user by ID (requires user:delete permission)

    Example:
        ```python
        from outlabs_auth import SimpleRBAC
        from outlabs_auth.routers import get_users_router

        auth = SimpleRBAC(database=db)
        app.include_router(get_users_router(auth, prefix="/users"))
        ```
    """
    router = APIRouter(prefix=prefix, tags=tags or ["users"])

    @router.post(
        "/",
        response_model=UserResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Create user",
        description="Create a new user account (requires user:create permission)",
    )
    async def create_user(
        data: UserCreateRequest,
        obs: ObservabilityContext = Depends(
            get_observability_with_auth(
                auth.observability,
                auth.deps.require_permission("user:create"),
            )
        ),
    ):
        """
        Create a new user (admin only).

        Allows admins to create users with specific settings including is_superuser.
        Different from /auth/register which is for self-registration.

        Triggers on_after_register hook.
        """
        try:
            user = await auth.user_service.create_user(
                email=data.email,
                password=data.password,
                first_name=data.first_name,
                last_name=data.last_name,
                is_superuser=data.is_superuser,
            )

            # Trigger on_after_register hook
            await auth.user_service.on_after_register(user, None)

            # Log successful user creation
            obs.log_event("user_created", user_id=str(user.id), created_by=obs.user_id)

            return UserResponse(
                id=str(user.id),
                email=user.email,
                first_name=user.first_name,
                last_name=user.last_name,
                status=user.status.value,
                email_verified=user.email_verified,
                is_superuser=user.is_superuser,
            )
        except HTTPException:
            raise
        except Exception as e:
            obs.log_500_error(e, email=data.email)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user",
            )

    @router.get(
        "/",
        response_model=PaginatedResponse[UserResponse],
        summary="List users",
        description="List all users with pagination and optional search filtering (requires user:read permission)",
    )
    async def list_users(
        page: int = Query(1, ge=1, description="Page number (1-indexed)"),
        limit: int = Query(20, ge=1, le=100, description="Results per page"),
        search: Optional[str] = Query(
            None, description="Search by email, first name, or last name"
        ),
        obs: ObservabilityContext = Depends(
            get_observability_with_auth(
                auth.observability,
                auth.deps.require_permission("user:read"),
            )
        ),
    ):
        """
        List users with pagination and optional search.

        If search term is provided, searches across email, first_name, and last_name fields.
        Returns paginated results with total count.
        """
        try:
            if search:
                # Use search functionality (no pagination for search)
                all_users = await auth.user_service.search_users(
                    search_term=search, limit=1000
                )

                # Manual pagination of search results
                total = len(all_users)
                start_idx = (page - 1) * limit
                end_idx = start_idx + limit
                users = all_users[start_idx:end_idx]
            else:
                # Use standard list with pagination
                users, total = await auth.user_service.list_users(
                    page=page, limit=limit
                )

            # Calculate total pages
            pages = (total + limit - 1) // limit if total > 0 else 0

            # Convert to response schema
            items = [
                UserResponse(
                    id=str(user.id),
                    email=user.email,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    status=user.status.value,
                    email_verified=user.email_verified,
                    is_superuser=user.is_superuser,
                )
                for user in users
            ]

            return PaginatedResponse(
                items=items, total=total, page=page, limit=limit, pages=pages
            )

        except Exception as e:
            obs.log_500_error(e, page=page, limit=limit, search=search)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to list users",
            )

    @router.get(
        "/me",
        response_model=UserResponse,
        summary="Get current user",
        description="Get the authenticated user's profile",
    )
    async def get_me(
        auth_result=Depends(auth.deps.require_auth(verified=requires_verification)),
    ):
        """Get current user profile."""
        user = auth_result["user"]
        return UserResponse(
            id=str(user.id),
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            status=user.status.value,
            email_verified=user.email_verified,
            is_superuser=user.is_superuser,
        )

    @router.patch(
        "/me",
        response_model=UserResponse,
        summary="Update current user",
        description="Update the authenticated user's profile",
    )
    async def update_me(
        data: UserUpdateRequest,
        obs: ObservabilityContext = Depends(
            get_observability_with_auth(
                auth.observability,
                auth.deps.require_auth(verified=requires_verification),
            )
        ),
    ):
        """
        Update current user profile.

        Triggers on_after_update hook.
        """
        try:
            user = await auth.user_service.update_user(
                user_id=obs.user_id,
                update_dict=data.model_dump(exclude_unset=True),
            )
            obs.log_event("user_updated", user_id=obs.user_id)
            return user
        except HTTPException:
            raise
        except Exception as e:
            obs.log_500_error(e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update user profile",
            )

    @router.post(
        "/me/change-password",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Change password",
        description="Change the authenticated user's password",
    )
    async def change_password(
        data: ChangePasswordRequest,
        obs: ObservabilityContext = Depends(
            get_observability_with_auth(
                auth.observability,
                auth.deps.require_auth(verified=requires_verification),
            )
        ),
    ):
        """
        Change user password.

        Requires current password for verification.
        """
        try:
            # Get current user
            user = await auth.user_service.get_user(obs.user_id)

            # Verify current password
            is_valid = await auth.auth_service.verify_password(
                user=user, password=data.current_password
            )

            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid current password",
                )

            # Update password
            await auth.user_service.update_user(
                user_id=obs.user_id,
                update_dict={"password": data.new_password},
            )

            obs.log_event("password_changed", user_id=obs.user_id)

        except HTTPException:
            raise
        except Exception as e:
            obs.log_500_error(e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to change password",
            )

        return None

    @router.get(
        "/{user_id}",
        response_model=UserResponse,
        summary="Get user by ID",
        description="Get any user's profile (requires user:read permission)",
    )
    async def get_user(
        user_id: str,
        obs: ObservabilityContext = Depends(
            get_observability_with_auth(
                auth.observability,
                auth.deps.require_permission("user:read"),
            )
        ),
    ):
        """Get user by ID (admin only)."""
        try:
            user = await auth.user_service.get_user(user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
                )
            return user
        except HTTPException:
            raise
        except Exception as e:
            obs.log_500_error(e, target_user_id=user_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get user",
            )

    @router.patch(
        "/{user_id}",
        response_model=UserResponse,
        summary="Update user by ID",
        description="Update any user's profile (requires user:update permission)",
    )
    async def update_user(
        user_id: str,
        data: UserUpdateRequest,
        obs: ObservabilityContext = Depends(
            get_observability_with_auth(
                auth.observability,
                auth.deps.require_permission("user:update"),
            )
        ),
    ):
        """
        Update user by ID (admin only).

        Triggers on_after_update hook.
        """
        try:
            user = await auth.user_service.update_user(
                user_id=user_id, update_dict=data.model_dump(exclude_unset=True)
            )
            obs.log_event(
                "user_updated", target_user_id=user_id, updated_by=obs.user_id
            )
            return user
        except HTTPException:
            raise
        except Exception as e:
            obs.log_500_error(e, target_user_id=user_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update user",
            )

    @router.delete(
        "/{user_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Delete user",
        description="Delete user account (requires user:delete permission)",
    )
    async def delete_user(
        user_id: str,
        obs: ObservabilityContext = Depends(
            get_observability_with_auth(
                auth.observability,
                auth.deps.require_permission("user:delete"),
            )
        ),
    ):
        """
        Delete user by ID (admin only).

        Triggers on_before_delete and on_after_delete hooks.
        """
        try:
            await auth.user_service.delete_user(user_id)
            obs.log_event(
                "user_deleted", target_user_id=user_id, deleted_by=obs.user_id
            )
        except HTTPException:
            raise
        except Exception as e:
            obs.log_500_error(e, target_user_id=user_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete user",
            )

        return None

    return router
