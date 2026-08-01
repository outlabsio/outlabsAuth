"""Enterprise admin API key inventory router factory."""

from enum import Enum
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from outlabs_auth.models.sql.enums import APIKeyKind, APIKeyStatus
from outlabs_auth.routers._api_key_response import (
    build_api_key_response,
    build_api_key_responses,
)
from outlabs_auth.schemas.api_key import ApiKeyResponse
from outlabs_auth.schemas.common import PaginatedResponse


def get_api_key_admin_router(
    auth: Any,
    prefix: str = "",
    tags: Optional[list[str | Enum]] = None,
) -> APIRouter:
    """
    Generate entity-first admin API key inventory routes for EnterpriseRBAC.

    This surface is intentionally inventory/incident-response only. Durable
    system key creation and lifecycle management live under the dedicated
    integration-principal admin routes.
    """
    router = APIRouter(prefix=prefix, tags=tags or ["api-key-admin"])

    async def _get_entity_api_key(session: AsyncSession, entity_id: UUID, key_id: UUID):
        api_key = await auth.api_key_service.get_api_key(session, key_id)
        if not api_key or api_key.entity_id != entity_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
        return api_key

    @router.get(
        "/{entity_id}/api-keys",
        response_model=PaginatedResponse[ApiKeyResponse],
        summary="List entity API keys",
        description="List every API key anchored to the specified entity for inventory and incident response.",
    )
    async def list_entity_api_keys(
        entity_id: UUID,
        page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
        limit: int = Query(default=20, ge=1, le=100, description="Results per page"),
        owner_id: Optional[UUID] = Query(default=None),
        status_filter: Optional[APIKeyStatus] = Query(default=None, alias="status"),
        key_kind: Optional[APIKeyKind] = Query(default=None),
        search: Optional[str] = Query(default=None, min_length=1),
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.require_tree_permission("api_key:read", "entity_id", source="path")),
    ):
        del auth_result
        api_keys, total = await auth.api_key_service.list_entity_api_keys_paginated(
            session,
            entity_id=entity_id,
            owner_id=owner_id,
            status=status_filter,
            key_kind=key_kind,
            search=search,
            page=page,
            limit=limit,
        )
        pages = (total + limit - 1) // limit if total > 0 else 0
        return PaginatedResponse(
            items=await build_api_key_responses(auth, session, api_keys),
            total=total,
            page=page,
            limit=limit,
            pages=pages,
        )

    @router.get(
        "/{entity_id}/api-keys/{key_id}",
        response_model=ApiKeyResponse,
        summary="Get entity API key",
        description="Get an anchored API key for inventory or incident response.",
    )
    async def get_entity_api_key(
        entity_id: UUID,
        key_id: UUID,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.require_tree_permission("api_key:read", "entity_id", source="path")),
    ):
        del auth_result
        api_key = await _get_entity_api_key(session, entity_id, key_id)
        return await build_api_key_response(auth, session, api_key)

    @router.delete(
        "/{entity_id}/api-keys/{key_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Revoke entity API key",
        description="Revoke an anchored API key for incident response.",
    )
    async def delete_entity_api_key(
        entity_id: UUID,
        key_id: UUID,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.require_tree_permission("api_key:delete", "entity_id", source="path")),
    ):
        await _get_entity_api_key(session, entity_id, key_id)
        actor_user_id = auth_result.get("user_id")
        await auth.api_key_service.revoke_api_key(
            session,
            key_id,
            actor_user_id=UUID(str(actor_user_id)) if actor_user_id else None,
            reason="API key revoked via admin inventory route",
            event_source="api_key_admin_router.delete_entity_api_key",
        )
        return None

    return router
