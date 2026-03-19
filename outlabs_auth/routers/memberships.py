"""
Memberships router factory.

Provides entity membership management routes for EnterpriseRBAC.
"""

from datetime import datetime, timezone
from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from outlabs_auth.models.sql.entity_membership import EntityMembership
from outlabs_auth.models.sql.enums import MembershipStatus
from outlabs_auth.schemas.membership import (
    EntityMemberResponse,
    MembershipCreateRequest,
    MembershipResponse,
    MembershipUpdateRequest,
)
from outlabs_auth.schemas.role import RoleSummary


def get_memberships_router(auth: Any, prefix: str = "", tags: Optional[list[str]] = None) -> APIRouter:
    """
    Generate entity membership management router.

    Args:
        auth: OutlabsAuth instance (EnterpriseRBAC)
        prefix: Router prefix (default: "")
        tags: OpenAPI tags (default: ["memberships"])

    Returns:
        APIRouter with membership management endpoints

    Routes:
        GET /me - Get current user's memberships
        POST / - Add user to entity
        GET /entity/{entity_id} - Get all members of an entity
        GET /user/{user_id} - Get all entities for a user
        PATCH /{entity_id}/{user_id} - Update user's roles in entity
        DELETE /{entity_id}/{user_id} - Remove user from entity

    Example:
        ```python
        from outlabs_auth import EnterpriseRBAC
        from outlabs_auth.routers import get_memberships_router

        auth = EnterpriseRBAC(database=db)
        app.include_router(get_memberships_router(auth, prefix="/memberships"))
        ```
    """
    router = APIRouter(prefix=prefix, tags=tags or ["memberships"])

    def resolve_effective_status(membership: EntityMembership) -> str:
        """Derive the current effective status from lifecycle state + validity window."""
        if membership.status != MembershipStatus.ACTIVE:
            return getattr(membership.status, "value", membership.status)

        now = datetime.now(timezone.utc)
        if membership.valid_from and now < membership.valid_from:
            return MembershipStatus.PENDING.value
        if membership.valid_until and now > membership.valid_until:
            return MembershipStatus.EXPIRED.value
        return MembershipStatus.ACTIVE.value

    def serialize_membership(membership: EntityMembership) -> MembershipResponse:
        """Convert membership model into a stable API response."""
        role_ids = sorted(str(role.id) for role in membership.roles)

        return MembershipResponse(
            id=str(membership.id),
            entity_id=str(membership.entity_id),
            user_id=str(membership.user_id),
            role_ids=role_ids,
            status=getattr(membership.status, "value", membership.status),
            effective_status=resolve_effective_status(membership),
            joined_at=membership.joined_at,
            joined_by_id=(str(membership.joined_by_id) if membership.joined_by_id else None),
            valid_from=membership.valid_from,
            valid_until=membership.valid_until,
            revoked_at=membership.revoked_at,
            revoked_by_id=(str(membership.revoked_by_id) if membership.revoked_by_id else None),
            revocation_reason=membership.revocation_reason,
            is_currently_valid=membership.is_currently_valid(),
            can_grant_permissions=membership.can_grant_permissions(),
        )

    @router.get(
        "/me",
        response_model=List[MembershipResponse],
        summary="Get my memberships",
        description="Get all entity memberships for the authenticated user",
    )
    async def get_my_memberships(
        include_inactive: bool = Query(
            False,
            description="Include suspended, revoked, pending, and expired memberships",
        ),
        auth_result=Depends(auth.deps.require_auth()),
        session: AsyncSession = Depends(auth.uow),
    ):
        """
        Get all entity memberships for the currently authenticated user.

        This endpoint is used for context switching in the admin UI.
        Users can always see their own memberships without special permissions.

        If membership service is not configured, returns empty list.
        """
        if not getattr(auth, "membership_service", None):
            return []

        user_id = UUID(auth_result["user_id"])
        memberships, _ = await auth.membership_service.get_user_entities(
            session=session,
            user_id=user_id,
            page=1,
            limit=100,
            active_only=not include_inactive,
        )
        return [serialize_membership(membership) for membership in memberships]

    @router.post(
        "/",
        response_model=MembershipResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Add member",
        description="Add user to entity with roles (requires membership:create permission)",
    )
    async def add_member(
        data: MembershipCreateRequest,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.require_tree_permission("membership:create", "entity_id", source="body")),
    ):
        """Add a user to an entity with specific roles."""
        membership = await auth.membership_service.add_member(
            session=session,
            entity_id=UUID(data.entity_id),
            user_id=UUID(data.user_id),
            role_ids=[UUID(rid) for rid in data.role_ids],
            joined_by_id=UUID(auth_result["user_id"]),
            valid_from=data.valid_from,
            valid_until=data.valid_until,
            status=data.status,
            reason=data.reason,
        )
        return serialize_membership(membership)

    @router.get(
        "/entity/{entity_id}",
        response_model=List[MembershipResponse],
        summary="Get entity members",
        description="Get all members of an entity (requires membership:read permission)",
    )
    async def get_entity_members(
        entity_id: UUID,
        page: int = Query(1, ge=1),
        limit: int = Query(50, ge=1, le=100),
        include_inactive: bool = Query(
            False,
            description="Include suspended, revoked, pending, and expired memberships",
        ),
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.require_tree_permission("membership:read", "entity_id", source="path")),
    ):
        """Get all members of an entity."""
        memberships, _ = await auth.membership_service.get_entity_members(
            session=session,
            entity_id=entity_id,
            page=page,
            limit=limit,
            active_only=not include_inactive,
        )
        return [serialize_membership(membership) for membership in memberships]

    @router.get(
        "/entity/{entity_id}/details",
        response_model=List[EntityMemberResponse],
        summary="Get entity members with details",
        description="Get all members of an entity with user details and roles (requires membership:read permission)",
    )
    async def get_entity_members_with_details(
        entity_id: UUID,
        page: int = Query(1, ge=1),
        limit: int = Query(50, ge=1, le=100),
        include_inactive: bool = Query(
            False,
            description="Include suspended, revoked, pending, and expired memberships",
        ),
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.require_tree_permission("membership:read", "entity_id", source="path")),
    ):
        """Get all members of an entity with user details and role information."""
        memberships, _ = await auth.membership_service.get_entity_members_with_users(
            session=session,
            entity_id=entity_id,
            page=page,
            limit=limit,
            active_only=not include_inactive,
        )
        return [
            EntityMemberResponse(
                id=str(m.id),
                user_id=str(m.user_id),
                user_email=m.user.email if m.user else "",
                user_first_name=m.user.first_name if m.user else None,
                user_last_name=m.user.last_name if m.user else None,
                user_status=(getattr(m.user.status, "value", m.user.status) if m.user else "unknown"),
                roles=[
                    RoleSummary(
                        id=str(r.id),
                        name=r.name,
                        display_name=r.display_name,
                    )
                    for r in m.roles
                ],
                status=getattr(m.status, "value", m.status),
                effective_status=resolve_effective_status(m),
                joined_at=m.joined_at,
                valid_from=m.valid_from,
                valid_until=m.valid_until,
            )
            for m in memberships
        ]

    @router.get(
        "/user/{user_id}",
        response_model=List[MembershipResponse],
        summary="Get user memberships",
        description="Get all entity memberships for a user (requires membership:read permission)",
    )
    async def get_user_memberships(
        user_id: UUID,
        page: int = Query(1, ge=1),
        limit: int = Query(50, ge=1, le=100),
        include_inactive: bool = Query(
            False,
            description="Include suspended, revoked, pending, and expired memberships",
        ),
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_permission("membership:read")),
    ):
        """Get all entity memberships for a user."""
        memberships, _ = await auth.membership_service.get_user_entities(
            session=session,
            user_id=user_id,
            page=page,
            limit=limit,
            active_only=not include_inactive,
        )
        return [serialize_membership(membership) for membership in memberships]

    @router.patch(
        "/{entity_id}/{user_id}",
        response_model=MembershipResponse,
        summary="Update member access",
        description="Update a user's roles, status, or validity window in an entity (requires membership:update permission)",
    )
    async def update_member_access(
        entity_id: UUID,
        user_id: UUID,
        data: MembershipUpdateRequest,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.require_tree_permission("membership:update", "entity_id", source="path")),
    ):
        """Update a user's roles and lifecycle state in an entity."""
        fields_set = data.model_fields_set

        membership = await auth.membership_service.update_membership(
            session=session,
            entity_id=entity_id,
            user_id=user_id,
            role_ids=[UUID(rid) for rid in data.role_ids] if data.role_ids else None,
            update_roles="role_ids" in fields_set,
            status=data.status,
            update_status="status" in fields_set,
            valid_from=data.valid_from,
            update_valid_from="valid_from" in fields_set,
            valid_until=data.valid_until,
            update_valid_until="valid_until" in fields_set,
            reason=data.reason,
            update_reason="reason" in fields_set,
            changed_by_id=UUID(auth_result["user_id"]),
        )
        return serialize_membership(membership)

    @router.delete(
        "/{entity_id}/{user_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Remove member",
        description="Remove user from entity (requires membership:delete permission)",
    )
    async def remove_member(
        entity_id: UUID,
        user_id: UUID,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.require_tree_permission("membership:delete", "entity_id", source="path")),
    ):
        """Remove a user from an entity."""
        await auth.membership_service.remove_member(
            session=session,
            entity_id=entity_id,
            user_id=user_id,
            revoked_by_id=UUID(auth_result["user_id"]),
        )
        return None

    return router
