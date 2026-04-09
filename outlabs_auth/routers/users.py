"""
Users router factory.

Provides ready-to-use user management routes (DD-041).
"""

from enum import Enum
from typing import Any, List, Optional, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from outlabs_auth.models.sql.entity_membership import EntityMembership
from outlabs_auth.models.sql.enums import DefinitionStatus, UserStatus
from outlabs_auth.observability import ObservabilityContext, get_observability_with_auth
from outlabs_auth.response_builders import (
    build_role_response,
    build_user_response_async,
    build_user_responses,
)
from outlabs_auth.schemas.common import PaginatedResponse
from outlabs_auth.schemas.membership_history import (
    MembershipHistoryEventResponse,
    OrphanedUserResponse,
)
from outlabs_auth.schemas.permission import PermissionResponse, UserPermissionSource
from outlabs_auth.schemas.role import RoleResponse
from outlabs_auth.schemas.user_audit import UserAuditEventResponse
from outlabs_auth.schemas.user import (
    AdminResetPasswordRequest,
    ChangePasswordRequest,
    UserCreateRequest,
    UserResponse,
    UserStatusUpdateRequest,
    UserUpdateRequest,
)
from outlabs_auth.schemas.user_role_membership import (
    AssignRoleRequest,
    UserRoleMembershipDetailResponse,
    UserRoleMembershipResponse,
)


def get_users_router(
    auth: Any,
    prefix: str = "",
    tags: Optional[list[str | Enum]] = None,
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

    async def _get_actor_user_or_401(session: AsyncSession, actor_user_id: Optional[str]) -> Any:
        if not actor_user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
            )
        try:
            actor_uuid = UUID(str(actor_user_id))
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user identity",
            )

        actor_user = await auth.user_service.get_user_by_id(session, actor_uuid)
        if not actor_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )
        return actor_user

    async def _get_target_user_or_404(
        session: AsyncSession,
        target_user_id: UUID,
        actor_user: Any,
    ) -> Any:
        target_user = await auth.user_service.get_user_by_id(session, target_user_id)
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        return target_user

    def _serialize_membership_history_event(event: Any) -> MembershipHistoryEventResponse:
        return MembershipHistoryEventResponse(
            id=str(event.id),
            membership_id=str(event.membership_id),
            user_id=str(event.user_id),
            entity_id=str(event.entity_id),
            root_entity_id=str(event.root_entity_id) if event.root_entity_id else None,
            actor_user_id=str(event.actor_user_id) if event.actor_user_id else None,
            event_type=event.event_type,
            event_source=event.event_source,
            event_at=event.event_at,
            reason=event.reason,
            status=event.status,
            previous_status=event.previous_status,
            valid_from=event.valid_from,
            valid_until=event.valid_until,
            previous_valid_from=event.previous_valid_from,
            previous_valid_until=event.previous_valid_until,
            role_ids=[str(role_id) for role_id in (event.role_ids or [])],
            previous_role_ids=[str(role_id) for role_id in (event.previous_role_ids or [])],
            role_names=list(event.role_names or []),
            previous_role_names=list(event.previous_role_names or []),
            entity_display_name=event.entity_display_name,
            entity_path=list(event.entity_path or []),
            root_entity_name=event.root_entity_name,
        )

    def _serialize_user_audit_event(event: Any) -> UserAuditEventResponse:
        return UserAuditEventResponse(
            id=str(event.id),
            occurred_at=event.occurred_at,
            event_category=event.event_category,
            event_type=event.event_type,
            event_source=event.event_source,
            actor_user_id=str(event.actor_user_id) if event.actor_user_id else None,
            subject_user_id=str(event.subject_user_id) if event.subject_user_id else None,
            subject_email_snapshot=event.subject_email_snapshot,
            root_entity_id=str(event.root_entity_id) if event.root_entity_id else None,
            entity_id=str(event.entity_id) if event.entity_id else None,
            role_id=str(event.role_id) if event.role_id else None,
            request_id=event.request_id,
            ip_address=event.ip_address,
            user_agent=event.user_agent,
            reason=event.reason,
            before=event.before,
            after=event.after,
            metadata=event.event_metadata,
        )

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
            actor_user = await _get_actor_user_or_401(session, obs.user_id)

            if data.is_superuser and not actor_user.is_superuser:
                has_superuser_create_permission = await auth.permission_service.check_permission(
                    session,
                    user_id=UUID(str(actor_user.id)),
                    permission="user:create_superuser",
                )
                if not has_superuser_create_permission:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Only superusers or users with user:create_superuser can create superusers",
                    )

            user = await auth.user_service.create_user(
                session,
                email=data.email,
                password=data.password,
                first_name=data.first_name,
                last_name=data.last_name,
                is_superuser=data.is_superuser,
                root_entity_id=UUID(data.root_entity_id) if data.root_entity_id else None,
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

            return await build_user_response_async(session, user)
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
        search: Optional[str] = Query(None, description="Search by email, first name, or last name"),
        user_status: Optional[str] = Query(
            None, alias="status", description="Filter by account status"
        ),
        is_superuser: Optional[bool] = Query(None, description="Filter by superuser flag"),
        root_entity_id: Optional[UUID] = Query(None, description="Filter by root entity assignment"),
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
            await _get_actor_user_or_401(session, obs.user_id)

            parsed_status = None
            if user_status is not None:
                try:
                    parsed_status = UserStatus(user_status)
                except ValueError:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid status: {user_status}. Must be one of: active, suspended, banned, deleted",
                    )

            if search:
                # Use search functionality (no pagination for search)
                all_users = await auth.user_service.search_users(
                    session,
                    search_term=search,
                    limit=1000,
                    status=parsed_status,
                    is_superuser=is_superuser,
                    root_entity_id=root_entity_id,
                )

                # Manual pagination of search results
                total = len(all_users)
                start_idx = (page - 1) * limit
                end_idx = start_idx + limit
                users = all_users[start_idx:end_idx]
            else:
                # Use standard list with pagination
                users, total = await auth.user_service.list_users(
                    session,
                    page=page,
                    limit=limit,
                    status=parsed_status,
                    is_superuser=is_superuser,
                    root_entity_id=root_entity_id,
                )

            # Calculate total pages
            pages = (total + limit - 1) // limit if total > 0 else 0

            # Convert to response schema
            items = await build_user_responses(session, users)

            return PaginatedResponse(items=items, total=total, page=page, limit=limit, pages=pages)

        except HTTPException:
            raise
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
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_auth(verified=requires_verification)),
    ):
        """Get current user profile."""
        user = auth_result["user"]
        return await build_user_response_async(session, user)

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
                changed_by_id=UUID(obs.user_id),
            )
            obs.log_event("user_updated", user_id=obs.user_id)
            await auth.user_service.on_after_update(user, update_dict, None)
            return await build_user_response_async(session, user)
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
                auth.observability.logger.info("user_password_changed", user_id=obs.user_id)

        except HTTPException:
            raise
        except Exception as e:
            obs.log_500_error(e)
            raise

        return None

    @router.get(
        "/orphaned",
        response_model=PaginatedResponse[OrphanedUserResponse],
        summary="List orphaned users",
        description="List users with no active entity memberships but historical assignments (requires user:read permission)",
    )
    async def list_orphaned_users(
        page: int = Query(1, ge=1, description="Page number (1-indexed)"),
        limit: int = Query(20, ge=1, le=100, description="Results per page"),
        search: Optional[str] = Query(None, description="Search by email, first name, or last name"),
        root_entity_id: Optional[UUID] = Query(None, description="Filter by root entity assignment"),
        session: AsyncSession = Depends(auth.uow),
        obs: ObservabilityContext = Depends(
            get_observability_with_auth(
                auth.observability,
                auth.deps.require_permission("user:read"),
            )
        ),
    ):
        """List orphaned users with latest membership history context."""
        try:
            await _get_actor_user_or_401(session, obs.user_id)

            if not getattr(auth, "membership_service", None):
                return PaginatedResponse(items=[], total=0, page=page, limit=limit, pages=0)

            orphaned_records, total = await auth.membership_service.list_orphaned_users(
                session,
                page=page,
                limit=limit,
                search=search,
                root_entity_id=root_entity_id,
            )

            user_payloads = await build_user_responses(session, [record.user for record in orphaned_records])
            user_by_id = {payload.id: payload for payload in user_payloads}
            items = [
                OrphanedUserResponse(
                    user=user_by_id[str(record.user.id)],
                    active_membership_count=record.active_membership_count,
                    total_membership_count=record.total_membership_count,
                    last_membership_event_type=record.last_event_type,
                    last_membership_event_at=record.last_event_at,
                    last_entity_id=str(record.last_entity_id) if record.last_entity_id else None,
                    last_entity_name=record.last_entity_name,
                )
                for record in orphaned_records
            ]
            pages = (total + limit - 1) // limit if total > 0 else 0
            return PaginatedResponse(items=items, total=total, page=page, limit=limit, pages=pages)
        except HTTPException:
            raise
        except Exception as e:
            obs.log_500_error(e, page=page, limit=limit, search=search)
            raise

    @router.get(
        "/{user_id}/membership-history",
        response_model=PaginatedResponse[MembershipHistoryEventResponse],
        summary="Get user membership history",
        description="Get append-only entity membership lifecycle history for a user (requires user:read permission)",
    )
    async def get_user_membership_history(
        user_id: UUID,
        page: int = Query(1, ge=1, description="Page number (1-indexed)"),
        limit: int = Query(50, ge=1, le=100, description="Results per page"),
        entity_id: Optional[UUID] = Query(None, description="Filter to one entity"),
        event_type: Optional[str] = Query(None, description="Filter by event type"),
        session: AsyncSession = Depends(auth.uow),
        obs: ObservabilityContext = Depends(
            get_observability_with_auth(
                auth.observability,
                auth.deps.require_permission("user:read"),
            )
        ),
    ):
        """Get paginated entity membership history for a user."""
        try:
            actor_user = await _get_actor_user_or_401(session, obs.user_id)
            await _get_target_user_or_404(session, user_id, actor_user)

            if not getattr(auth, "membership_service", None):
                return PaginatedResponse(items=[], total=0, page=page, limit=limit, pages=0)

            events, total = await auth.membership_service.get_user_membership_history(
                session,
                user_id,
                page=page,
                limit=limit,
                entity_id=entity_id,
                event_type=event_type,
            )
            items = [_serialize_membership_history_event(event) for event in events]
            pages = (total + limit - 1) // limit if total > 0 else 0
            return PaginatedResponse(items=items, total=total, page=page, limit=limit, pages=pages)
        except HTTPException:
            raise
        except Exception as e:
            obs.log_500_error(
                e,
                target_user_id=str(user_id),
                page=page,
                limit=limit,
                event_type=event_type,
            )
            raise

    @router.get(
        "/{user_id}/audit-events",
        response_model=PaginatedResponse[UserAuditEventResponse],
        summary="Get user audit events",
        description="Get high-signal user lifecycle audit events (requires user:read permission)",
    )
    async def get_user_audit_events(
        user_id: UUID,
        page: int = Query(1, ge=1, description="Page number (1-indexed)"),
        limit: int = Query(50, ge=1, le=100, description="Results per page"),
        category: Optional[str] = Query(None, description="Filter by audit event category"),
        event_type: Optional[str] = Query(None, description="Filter by audit event type"),
        entity_id: Optional[UUID] = Query(None, description="Filter by related entity"),
        session: AsyncSession = Depends(auth.uow),
        obs: ObservabilityContext = Depends(
            get_observability_with_auth(
                auth.observability,
                auth.deps.require_permission("user:read"),
            )
        ),
    ):
        """Get paginated user-centric audit events."""
        try:
            actor_user = await _get_actor_user_or_401(session, obs.user_id)
            await _get_target_user_or_404(session, user_id, actor_user)

            if not getattr(auth, "user_audit_service", None):
                return PaginatedResponse(items=[], total=0, page=page, limit=limit, pages=0)

            events, total = await auth.user_audit_service.list_user_events(
                session,
                user_id,
                page=page,
                limit=limit,
                event_category=category,
                event_type=event_type,
                entity_id=entity_id,
            )
            items = [_serialize_user_audit_event(event) for event in events]
            pages = (total + limit - 1) // limit if total > 0 else 0
            return PaginatedResponse(items=items, total=total, page=page, limit=limit, pages=pages)
        except HTTPException:
            raise
        except Exception as e:
            obs.log_500_error(
                e,
                target_user_id=str(user_id),
                page=page,
                limit=limit,
                category=category,
                event_type=event_type,
            )
            raise

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
            actor_user = await _get_actor_user_or_401(session, obs.user_id)
            user = await _get_target_user_or_404(session, user_id, actor_user)

            return await build_user_response_async(session, user)
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
            actor_user = await _get_actor_user_or_401(session, obs.user_id)
            await _get_target_user_or_404(session, user_id, actor_user)

            update_data = data.model_dump(exclude_unset=True)
            user = await auth.user_service.update_user_fields(
                session,
                user_id=user_id,
                email=update_data.get("email"),
                first_name=update_data.get("first_name"),
                last_name=update_data.get("last_name"),
                changed_by_id=actor_user.id,
            )
            await auth.user_service.on_after_update(user, update_data, None)
            # TODO: Add proper observability logging for user updates
            return await build_user_response_async(session, user)
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
            actor_user = await _get_actor_user_or_401(session, obs.user_id)
            await _get_target_user_or_404(session, user_id, actor_user)

            # Change user password using user service
            await auth.user_service.change_password(
                session,
                user_id=user_id,
                new_password=data.new_password,
                changed_by_id=actor_user.id,
            )

            # Log admin password reset
            if auth.observability:
                auth.observability.logger.info("admin_password_reset", target_user_id=user_id, reset_by=obs.user_id)

        except HTTPException:
            raise
        except Exception as e:
            obs.log_500_error(e, target_user_id=str(user_id))
            raise

        return None

    @router.patch(
        "/{user_id}/status",
        response_model=UserResponse,
        summary="Update user status",
        description="Change user account status (activate, suspend, ban). Requires user:update permission.",
    )
    async def update_user_status(
        user_id: UUID,
        data: UserStatusUpdateRequest,
        session: AsyncSession = Depends(auth.uow),
        obs: ObservabilityContext = Depends(
            get_observability_with_auth(
                auth.observability,
                auth.deps.require_permission("user:update"),
            )
        ),
    ):
        """
        Update user account status.

        Allows administrators to:
        - Activate a suspended/banned user
        - Suspend a user temporarily
        - Ban a user permanently

        Note: Cannot change status to 'deleted' via this endpoint.
        Use DELETE /{user_id} for soft deletion.
        """
        try:
            actor_user = await _get_actor_user_or_401(session, obs.user_id)
            target_user = await _get_target_user_or_404(session, user_id, actor_user)

            # Convert string status to enum
            try:
                new_status = UserStatus(data.status)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status: {data.status}. Must be one of: active, suspended, banned",
                )

            # Prevent setting status to deleted via this endpoint
            if new_status == UserStatus.DELETED:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot set status to 'deleted'. Use DELETE endpoint instead.",
                )
            if target_user.status == UserStatus.DELETED:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot change status for a deleted user. Use the restore endpoint instead.",
                )

            # Parse suspended_until if provided
            suspended_until = None
            if data.suspended_until and new_status == UserStatus.SUSPENDED:
                from datetime import datetime as dt

                try:
                    suspended_until = dt.fromisoformat(data.suspended_until.replace("Z", "+00:00"))
                except ValueError:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid suspended_until format. Use ISO 8601 datetime.",
                    )

            user = await auth.user_service.update_user_status(
                session,
                user_id=user_id,
                status=new_status,
                suspended_until=suspended_until,
                changed_by_id=actor_user.id,
                reason=data.reason,
            )

            # Log status change
            if auth.observability:
                auth.observability.logger.info(
                    "user_status_changed",
                    target_user_id=str(user_id),
                    new_status=data.status,
                    reason=data.reason,
                    suspended_until=data.suspended_until,
                    changed_by=obs.user_id,
                )

            return await build_user_response_async(session, user)

        except HTTPException:
            raise
        except Exception as e:
            obs.log_500_error(e, target_user_id=str(user_id))
            raise

    @router.post(
        "/{user_id}/restore",
        response_model=UserResponse,
        summary="Restore user",
        description="Restore a deleted user identity only (requires user:update permission)",
    )
    async def restore_user(
        user_id: UUID,
        session: AsyncSession = Depends(auth.uow),
        obs: ObservabilityContext = Depends(
            get_observability_with_auth(
                auth.observability,
                auth.deps.require_permission("user:update"),
            )
        ),
    ):
        """Restore a deleted user without restoring access grants or credentials."""
        try:
            actor_user = await _get_actor_user_or_401(session, obs.user_id)
            await _get_target_user_or_404(session, user_id, actor_user)

            user = await auth.user_service.restore_user(
                session,
                user_id=user_id,
                restored_by_id=actor_user.id,
            )

            if auth.observability:
                auth.observability.logger.info(
                    "user_restored",
                    target_user_id=str(user_id),
                    restored_by=obs.user_id,
                )

            return await build_user_response_async(session, user)
        except HTTPException:
            raise
        except Exception as e:
            obs.log_500_error(e, target_user_id=str(user_id))
            raise

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
            actor_user = await _get_actor_user_or_401(session, obs.user_id)
            user = await _get_target_user_or_404(session, user_id, actor_user)

            await auth.user_service.on_before_delete(user, None)
            deleted = await auth.user_service.delete_user(
                session,
                user_id,
                deleted_by_id=actor_user.id,
            )
            if not deleted:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
            await auth.user_service.on_after_delete(user, None)

            # Log event
            if auth.observability:
                auth.observability.logger.info("user_deleted", target_user_id=user_id, deleted_by=obs.user_id)
        except HTTPException:
            raise
        except Exception as e:
            obs.log_500_error(e, target_user_id=str(user_id))
            raise

        return None

    @router.post(
        "/{user_id}/resend-invite",
        response_model=UserResponse,
        summary="Resend invitation",
        description="Resend invitation email to an INVITED user (requires user:update permission)",
    )
    async def resend_invite(
        user_id: UUID,
        session: AsyncSession = Depends(auth.uow),
        obs: ObservabilityContext = Depends(
            get_observability_with_auth(
                auth.observability,
                auth.deps.require_permission("user:update"),
            )
        ),
    ):
        """
        Resend invitation by regenerating the invite token.

        Only works for users with INVITED status.
        Triggers on_after_invite hook with the new token.
        """
        try:
            actor_user = await _get_actor_user_or_401(session, obs.user_id)
            await _get_target_user_or_404(session, user_id, actor_user)

            user, plain_token = await auth.user_service.resend_invite(
                session,
                user_id,
                resent_by_id=actor_user.id,
            )

            # Trigger hook
            await auth.user_service.on_after_invite(user, plain_token)

            if auth.observability:
                auth.observability.logger.info(
                    "invite_resent",
                    target_user_id=str(user_id),
                    resent_by=obs.user_id,
                )

            return await build_user_response_async(session, user)

        except HTTPException:
            raise
        except Exception as e:
            obs.log_500_error(e, target_user_id=str(user_id))
            raise

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
        include_inactive: bool = Query(False, description="Include inactive memberships"),
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
            actor_user = await _get_actor_user_or_401(session, obs.user_id)
            await _get_target_user_or_404(session, user_id, actor_user)

            # Get roles using role service
            roles = await auth.role_service.get_user_roles(session, user_id=user_id, include_inactive=include_inactive)

            # Convert to response schema
            return [await build_role_response(session, role) for role in roles]

        except HTTPException:
            raise
        except Exception as e:
            obs.log_500_error(e, target_user_id=str(user_id))
            raise

    @router.get(
        "/{user_id}/role-memberships",
        response_model=List[UserRoleMembershipDetailResponse],
        summary="Get user's direct role memberships",
        description="Get direct role assignment records with lifecycle metadata (requires user:read permission)",
    )
    async def get_user_role_memberships(
        user_id: UUID,
        include_inactive: bool = Query(False, description="Include inactive role memberships"),
        session: AsyncSession = Depends(auth.uow),
        obs: ObservabilityContext = Depends(
            get_observability_with_auth(
                auth.observability,
                auth.deps.require_permission("user:read"),
            )
        ),
    ):
        """
        Get direct role membership records for a user.

        Returns assignment metadata such as validity windows and revocation info
        alongside the embedded role definition.
        """
        try:
            actor_user = await _get_actor_user_or_401(session, obs.user_id)
            await _get_target_user_or_404(session, user_id, actor_user)

            memberships = await auth.role_service.get_user_role_memberships(
                session,
                user_id=user_id,
                include_inactive=include_inactive,
            )

            response_items = []
            for membership in memberships:
                response_items.append(
                    UserRoleMembershipDetailResponse(
                        id=str(membership.id),
                        user_id=str(membership.user_id),
                        role_id=str(membership.role_id),
                        assigned_at=membership.assigned_at,
                        assigned_by_id=str(membership.assigned_by_id) if membership.assigned_by_id else None,
                        valid_from=membership.valid_from,
                        valid_until=membership.valid_until,
                        status=membership.status,
                        revoked_at=membership.revoked_at,
                        revoked_by_id=str(membership.revoked_by_id) if membership.revoked_by_id else None,
                        revocation_reason=membership.revocation_reason,
                        is_currently_valid=membership.is_currently_valid(),
                        can_grant_permissions=membership.can_grant_permissions(),
                        role=await build_role_response(session, membership.role),
                    )
                )

            return response_items

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
            actor_user = await _get_actor_user_or_401(session, obs.user_id)
            await _get_target_user_or_404(session, user_id, actor_user)

            # Validate role exists
            role = await auth.role_service.get_role_by_id(session, UUID(data.role_id))
            if not role:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

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
                assigned_by_id=str(membership.assigned_by_id) if membership.assigned_by_id else None,
                valid_from=membership.valid_from,
                valid_until=membership.valid_until,
                status=membership.status,
                revoked_at=membership.revoked_at,
                revoked_by_id=str(membership.revoked_by_id) if membership.revoked_by_id else None,
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
            actor_user = await _get_actor_user_or_401(session, obs.user_id)
            await _get_target_user_or_404(session, user_id, actor_user)

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
        description=(
            "Get all effective permissions for a user with source information. "
            "Users may read their own permissions; reading another user's permissions "
            "requires user:read permission."
        ),
    )
    async def get_user_permissions(
        user_id: UUID,
        obs: ObservabilityContext = Depends(
            get_observability_with_auth(
                auth.observability,
                auth.deps.require_auth(verified=requires_verification),
            )
        ),
        session: AsyncSession = Depends(auth.uow),
    ):
        """
        Get all effective permissions for a user with source information.

        Returns detailed permission objects with information about which role granted each permission.
        """
        try:
            actor_user = await _get_actor_user_or_401(session, obs.user_id)
            await _get_target_user_or_404(session, user_id, actor_user)

            is_self_request = actor_user.id == user_id
            if not is_self_request and not actor_user.is_superuser:
                can_read_users = await auth.permission_service.check_permission(
                    session,
                    user_id=UUID(str(actor_user.id)),
                    permission="user:read",
                )
                if not can_read_users:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Not enough permissions",
                    )

            permission_sources = []
            seen_permissions = set()

            async def _append_role_permissions(role: Any) -> None:
                if role is None:
                    return
                if getattr(role, "status", DefinitionStatus.ACTIVE) != DefinitionStatus.ACTIVE:
                    return

                role_permissions = await auth.permission_service.get_permissions_for_role(session, role.id)
                for perm in role_permissions:
                    if perm.name in seen_permissions:
                        continue
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

            # Direct user role memberships.
            roles = await auth.role_service.get_user_roles(session, user_id=user_id)
            for role in roles:
                await _append_role_permissions(role)

            # Enterprise entity memberships also grant permissions and must be
            # reflected here so host/UI permission gates match runtime behavior.
            entity_memberships_stmt = (
                select(EntityMembership)
                .options(selectinload(cast(Any, EntityMembership.roles)))
                .where(
                    cast(Any, EntityMembership.user_id) == user_id,
                )
            )
            entity_memberships_result = await session.execute(entity_memberships_stmt)
            entity_memberships = entity_memberships_result.scalars().all()

            for membership in entity_memberships:
                if not membership.can_grant_permissions():
                    continue
                for role in membership.roles:
                    await _append_role_permissions(role)

            # Sort by permission name
            permission_sources.sort(key=lambda x: x.permission.name)

            return permission_sources

        except HTTPException:
            raise
        except Exception as e:
            obs.log_500_error(e, target_user_id=str(user_id))
            raise

    return router
