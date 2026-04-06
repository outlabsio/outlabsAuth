"""Minimal self-service user router factory for embedded hosts."""

from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from outlabs_auth.response_builders import build_user_response_async
from outlabs_auth.schemas.user import UserResponse


def get_self_service_users_router(
    auth: Any,
    prefix: str = "",
    tags: Optional[list[str]] = None,
    requires_verification: bool = False,
) -> APIRouter:
    """
    Generate a minimal self-service users router for embedded applications.

    Routes:
        GET /me
        GET /me/permissions
    """
    router = APIRouter(prefix=prefix, tags=tags or ["users-self-service"])

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
        return await build_user_response_async(session, auth_result["user"])

    @router.get(
        "/me/permissions",
        response_model=List[str],
        summary="Get current user's permissions",
        description="Get all effective permissions for the authenticated user",
    )
    async def get_my_permissions(
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_auth(verified=requires_verification)),
    ):
        user_id = UUID(auth_result["user_id"])
        return await auth.permission_service.get_user_permissions(session, user_id=user_id)

    return router
