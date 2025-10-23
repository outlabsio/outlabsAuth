"""
Memberships router factory.

Provides entity membership management routes for EnterpriseRBAC.
"""

from typing import Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, status

from outlabs_auth.schemas.membership import (
    MembershipResponse,
    MembershipCreateRequest,
    MembershipUpdateRequest,
)


def get_memberships_router(
    auth: Any,
    prefix: str = "",
    tags: Optional[list[str]] = None
) -> APIRouter:
    """
    Generate entity membership management router.

    Args:
        auth: OutlabsAuth instance (EnterpriseRBAC)
        prefix: Router prefix (default: "")
        tags: OpenAPI tags (default: ["memberships"])

    Returns:
        APIRouter with membership management endpoints

    Routes:
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

    @router.post(
        "/",
        response_model=MembershipResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Add member",
        description="Add user to entity with roles (requires membership:create permission)"
    )
    async def add_member(
        data: MembershipCreateRequest,
        auth_result = Depends(auth.deps.require_permission("membership:create"))
    ):
        """Add a user to an entity with specific roles."""
        try:
            membership = await auth.membership_service.add_member(
                entity_id=data.entity_id,
                user_id=data.user_id,
                role_ids=data.role_ids
            )
            return MembershipResponse(**membership.model_dump())
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

    @router.get(
        "/entity/{entity_id}",
        response_model=List[MembershipResponse],
        summary="Get entity members",
        description="Get all members of an entity (requires membership:read permission)"
    )
    async def get_entity_members(
        entity_id: str,
        auth_result = Depends(auth.deps.require_permission("membership:read"))
    ):
        """Get all members of an entity."""
        try:
            memberships = await auth.membership_service.get_entity_members(entity_id)
            return [MembershipResponse(**m.model_dump()) for m in memberships]
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )

    @router.get(
        "/user/{user_id}",
        response_model=List[MembershipResponse],
        summary="Get user memberships",
        description="Get all entity memberships for a user (requires membership:read permission)"
    )
    async def get_user_memberships(
        user_id: str,
        auth_result = Depends(auth.deps.require_permission("membership:read"))
    ):
        """Get all entity memberships for a user."""
        try:
            memberships = await auth.membership_service.get_user_entities(user_id)
            return [MembershipResponse(**m.model_dump()) for m in memberships]
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )

    @router.patch(
        "/{entity_id}/{user_id}",
        response_model=MembershipResponse,
        summary="Update member roles",
        description="Update user's roles in an entity (requires membership:update permission)"
    )
    async def update_member_roles(
        entity_id: str,
        user_id: str,
        data: MembershipUpdateRequest,
        auth_result = Depends(auth.deps.require_permission("membership:update"))
    ):
        """Update a user's roles in an entity."""
        try:
            membership = await auth.membership_service.update_member_roles(
                entity_id=entity_id,
                user_id=user_id,
                role_ids=data.role_ids
            )
            return MembershipResponse(**membership.model_dump())
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

    @router.delete(
        "/{entity_id}/{user_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Remove member",
        description="Remove user from entity (requires membership:delete permission)"
    )
    async def remove_member(
        entity_id: str,
        user_id: str,
        auth_result = Depends(auth.deps.require_permission("membership:delete"))
    ):
        """Remove a user from an entity."""
        try:
            await auth.membership_service.remove_member(
                entity_id=entity_id,
                user_id=user_id
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        return None

    return router
