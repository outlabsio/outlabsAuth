"""
Users router factory.

Provides ready-to-use user management routes (DD-041).
"""

from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from outlabs_auth.observability import ObservabilityContext, get_observability_with_auth
from outlabs_auth.schemas.common import PaginatedResponse
from outlabs_auth.schemas.permission import PermissionResponse, UserPermissionSource
from outlabs_auth.schemas.role import RoleResponse
from outlabs_auth.schemas.user import (
    AdminResetPasswordRequest,
    ChangePasswordRequest,
    UserCreateRequest,
    UserResponse,
    UserUpdateRequest,
)
from outlabs_auth.schemas.user_role_membership import (
    AssignRoleRequest,
    UserRoleMembershipResponse,
)


def _get_status_value(status_val: Any) -> str:
    """Get status value as string, handling both enum and string types."""
    return status_val.value if hasattr(status_val, "value") else status_val


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
        session: AsyncSession = Depends(auth.uow),
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
                session,
                email=data.email,
                password=data.password,
                first_name=data.first_name,
                last_name=data.last_name,
                is_superuser=data.is_superuser,
            )

            # Trigger on_after_register hook
            await auth.user_service.on_after_register(user, None)

            # Log successful user creation
            if auth.observability:
                auth.observability.logger.info(
                    "user_created",
                    user_id=str(user.id),
                    email=user.email,
                    created_by=obs.user_id,
                )

            return UserResponse(
                id=str(user.id),
                email=user.email,
                first_name=user.first_name,
                last_name=user.last_name,
                status=_get_status_value(user.status),
                email_verified=user.email_verified,
                is_superuser=user.is_superuser,
            )
        except HTTPException:
            raise
        except Exception as e:
            obs.log_500_error(e, email=data.email)
            raise

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
        session: AsyncSession = Depends(auth.uow),
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
                    session, search_term=search, limit=1000
                )

                # Manual pagination of search results
                total = len(all_users)
                start_idx = (page - 1) * limit
                end_idx = start_idx + limit
                users = all_users[start_idx:end_idx]
            else:
                # Use standard list with pagination
                users, total = await auth.user_service.list_users(
                    session, page=page, limit=limit
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
                    status=_get_status_value(user.status),
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
            raise

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
            status=_get_status_value(user.status),
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
        session: AsyncSession = Depends(auth.uow),
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
            update_dict = data.model_dump(exclude_unset=True)
            user = await auth.user_service.update_user_fields(
                session,
                user_id=UUID(obs.user_id),
                email=update_dict.get("email"),
                first_name=update_dict.get("first_name"),
                last_name=update_dict.get("last_name"),
            )
            obs.log_event("user_updated", user_id=obs.user_id)
            await auth.user_service.on_after_update(user, update_dict, None)
            return user
        except HTTPException:
            raise
        except Exception as e:
            obs.log_500_error(e)
            raise

    @router.post(
        "/me/change-password",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Change password",
        description="Change the authenticated user's password",
    )
    async def change_password(
        data: ChangePasswordRequest,
        session: AsyncSession = Depends(auth.uow),
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
            await auth.user_service.change_password_with_current(
                session,
                user_id=UUID(obs.user_id),
                current_password=data.current_password,
                new_password=data.new_password,
            )

            # Log password change
            if auth.observability:
                auth.observability.logger.info(
                    "user_password_changed", user_id=obs.user_id
                )

        except HTTPException:
            raise
        except Exception as e:
            obs.log_500_error(e)
            raise

        return None

    @router.get(
        "/{user_id}",
        response_model=UserResponse,
        summary="Get user by ID",
        description="Get any user's profile (requires user:read permission)",
    )
    async def get_user(
        user_id: UUID,
        session: AsyncSession = Depends(auth.uow),
        obs: ObservabilityContext = Depends(
            get_observability_with_auth(
                auth.observability,
                auth.deps.require_permission("user:read"),
            )
        ),
    ):
        """Get user by ID (admin only)."""
        try:
            user = await auth.user_service.get_user_by_id(session, user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
                )

            return UserResponse(
                id=str(user.id),
                email=user.email,
                first_name=user.first_name,
                last_name=user.last_name,
                status=_get_status_value(user.status),
                email_verified=user.email_verified,
                is_superuser=user.is_superuser,
            )
        except HTTPException:
            raise
        except Exception as e:
            obs.log_500_error(e, target_user_id=str(user_id))
            raise

    @router.patch(
        "/{user_id}",
        response_model=UserResponse,
        summary="Update user by ID",
        description="Update any user's profile (requires user:update permission)",
    )
    async def update_user(
        user_id: UUID,
        data: UserUpdateRequest,
        session: AsyncSession = Depends(auth.uow),
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
            update_data = data.model_dump(exclude_unset=True)
            user = await auth.user_service.update_user_fields(
                session,
                user_id=user_id,
                email=update_data.get("email"),
                first_name=update_data.get("first_name"),
                last_name=update_data.get("last_name"),
            )
            await auth.user_service.on_after_update(user, update_data, None)
            # TODO: Add proper observability logging for user updates
            return UserResponse(
                id=str(user.id),
                email=user.email,
                first_name=user.first_name,
                last_name=user.last_name,
                status=_get_status_value(user.status),
                email_verified=user.email_verified,
                is_superuser=user.is_superuser,
            )
        except HTTPException:
            raise
        except Exception as e:
            obs.log_500_error(e, target_user_id=str(user_id))
            raise

    @router.patch(
        "/{user_id}/password",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Reset user password (admin)",
        description="Reset user password without requiring current password (requires user:update permission)",
    )
    async def admin_reset_password(
        user_id: UUID,
        data: AdminResetPasswordRequest,
        session: AsyncSession = Depends(auth.uow),
        obs: ObservabilityContext = Depends(
            get_observability_with_auth(
                auth.observability,
                auth.deps.require_permission("user:update"),
            )
        ),
    ):
        """
        Reset user password (admin only).

        Allows administrators to reset a user's password without knowing their current password.
        This is different from /me/change-password which requires the current password.

        Triggers password_changed notification.
        """
        try:
            # Change user password using user service
            await auth.user_service.change_password(
                session,
                user_id=user_id,
                new_password=data.new_password,
            )

            # Log admin password reset
            if auth.observability:
                auth.observability.logger.info(
                    "admin_password_reset", target_user_id=user_id, reset_by=obs.user_id
                )

        except HTTPException:
            raise
        except Exception as e:
            obs.log_500_error(e, target_user_id=str(user_id))
            raise

        return None

    @router.delete(
        "/{user_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Delete user",
        description="Delete user account (requires user:delete permission)",
    )
    async def delete_user(
        user_id: UUID,
        session: AsyncSession = Depends(auth.uow),
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
            user = await auth.user_service.get_user_by_id(session, user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
                )

            await auth.user_service.on_before_delete(user, None)
            deleted = await auth.user_service.delete_user(session, user_id)
            if not deleted:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
                )
            await auth.user_service.on_after_delete(user, None)

            # Log event
            if auth.observability:
                auth.observability.logger.info(
                    "user_deleted", target_user_id=user_id, deleted_by=obs.user_id
                )
        except HTTPException:
            raise
        except Exception as e:
            obs.log_500_error(e, target_user_id=str(user_id))
            raise

        return None

    # ============================================================
    # USER ROLE MANAGEMENT ENDPOINTS
    # ============================================================

    @router.get(
        "/{user_id}/roles",
        response_model=List[RoleResponse],
        summary="Get user's roles",
        description="Get all roles assigned to a user (requires user:read permission)",
    )
    async def get_user_roles(
        user_id: UUID,
        include_inactive: bool = Query(
            False, description="Include inactive memberships"
        ),
        session: AsyncSession = Depends(auth.uow),
        obs: ObservabilityContext = Depends(
            get_observability_with_auth(
                auth.observability,
                auth.deps.require_permission("user:read"),
            )
        ),
    ):
        """
        Get all roles assigned to a user.

        Returns list of roles with their details. Optionally includes inactive memberships.
        """
        try:
            # Validate user exists
            user = await auth.user_service.get_user_by_id(session, user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
                )

            # Get roles using role service
            roles = await auth.role_service.get_user_roles(
                session, user_id=user_id, include_inactive=include_inactive
            )

            # Convert to response schema
            return [
                RoleResponse(**role.model_dump(mode="json", exclude={"entity"}))
                for role in roles
            ]

        except HTTPException:
            raise
        except Exception as e:
            obs.log_500_error(e, target_user_id=str(user_id))
            raise

    @router.post(
        "/{user_id}/roles",
        response_model=UserRoleMembershipResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Assign role to user",
        description="Assign a role to a user (requires user:update permission)",
    )
    async def assign_role_to_user_endpoint(
        user_id: UUID,
        data: AssignRoleRequest,
        session: AsyncSession = Depends(auth.uow),
        obs: ObservabilityContext = Depends(
            get_observability_with_auth(
                auth.observability,
                auth.deps.require_permission("user:update"),
            )
        ),
    ):
        """
        Assign a role to a user.

        Creates a new role membership with optional time-based validity.
        """
        try:
            # Validate user exists
            user = await auth.user_service.get_user_by_id(session, user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
                )

            # Validate role exists
            role = await auth.role_service.get_role_by_id(session, UUID(data.role_id))
            if not role:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Role not found"
                )

            # Assign role
            membership = await auth.role_service.assign_role_to_user(
                session,
                user_id=user_id,
                role_id=UUID(data.role_id),
                assigned_by_id=UUID(obs.user_id),
                valid_from=data.valid_from,
                valid_until=data.valid_until,
            )

            # Log event
            if auth.observability:
                auth.observability.logger.info(
                    "role_assigned",
                    user_id=user_id,
                    role_id=data.role_id,
                    assigned_by=obs.user_id,
                )

            return UserRoleMembershipResponse(
                id=str(membership.id),
                user_id=str(membership.user_id),
                role_id=str(membership.role_id),
                assigned_at=membership.assigned_at,
                assigned_by_id=str(membership.assigned_by_id)
                if membership.assigned_by_id
                else None,
                valid_from=membership.valid_from,
                valid_until=membership.valid_until,
                status=membership.status,
                revoked_at=membership.revoked_at,
                revoked_by_id=str(membership.revoked_by_id)
                if membership.revoked_by_id
                else None,
                is_currently_valid=membership.is_currently_valid(),
                can_grant_permissions=membership.can_grant_permissions(),
            )

        except HTTPException:
            raise
        except Exception as e:
            obs.log_500_error(e, target_user_id=str(user_id), role_id=data.role_id)
            raise

    @router.delete(
        "/{user_id}/roles/{role_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Remove role from user",
        description="Revoke a role from a user (requires user:update permission)",
    )
    async def remove_role_from_user_endpoint(
        user_id: UUID,
        role_id: UUID,
        session: AsyncSession = Depends(auth.uow),
        obs: ObservabilityContext = Depends(
            get_observability_with_auth(
                auth.observability,
                auth.deps.require_permission("user:update"),
            )
        ),
    ):
        """
        Revoke a role from a user.

        Soft deletes the role membership (changes status to REVOKED).
        """
        try:
            # Validate user exists
            user = await auth.user_service.get_user_by_id(session, UUID(user_id))
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
                )

            # Revoke role
            success = await auth.role_service.revoke_role_from_user(
                session,
                user_id=user_id,
                role_id=role_id,
                revoked_by_id=UUID(obs.user_id),
            )

            if not success:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User does not have this role assigned",
                )

            # Log event
            if auth.observability:
                auth.observability.logger.info(
                    "role_revoked",
                    user_id=str(user_id),
                    role_id=str(role_id),
                    revoked_by=obs.user_id,
                )

            return None

        except HTTPException:
            raise
        except Exception as e:
            obs.log_500_error(e, target_user_id=str(user_id), role_id=str(role_id))
            raise

    @router.get(
        "/{user_id}/permissions",
        response_model=List[UserPermissionSource],
        summary="Get user's permissions",
        description="Get all effective permissions for a user with source information (requires user:read permission)",
    )
    async def get_user_permissions(
        user_id: UUID,
        obs: ObservabilityContext = Depends(
            get_observability_with_auth(
                auth.observability,
                auth.deps.require_permission("user:read"),
            )
        ),
        session: AsyncSession = Depends(auth.uow),
    ):
        """
        Get all effective permissions for a user with source information.

        Returns detailed permission objects with information about which role granted each permission.
        """
        try:
            # Validate user exists
            user = await auth.user_service.get_user_by_id(session, user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
                )

            # Get user's roles
            roles = await auth.role_service.get_user_roles(session, user_id=user_id)

            # Collect permissions with their sources
            permission_sources = []
            seen_permissions = set()

            for role in roles:
                # Get permissions for this role
                role_permissions = (
                    await auth.permission_service.get_permissions_for_role(
                        session, role.id
                    )
                )
                for perm in role_permissions:
                    if perm.name not in seen_permissions:
                        permission_sources.append(
                            UserPermissionSource(
                                permission=PermissionResponse(
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
                                ),
                                source="role",
                                source_id=str(role.id),
                                source_name=role.name,
                            )
                        )
                        seen_permissions.add(perm.name)

            # Sort by permission name
            permission_sources.sort(key=lambda x: x.permission.name)

            return permission_sources

        except HTTPException:
            raise
        except Exception as e:
            obs.log_500_error(e, target_user_id=str(user_id))
            raise

    return router
