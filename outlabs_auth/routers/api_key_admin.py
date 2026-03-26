"""Enterprise admin API key router factory."""

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from outlabs_auth.core.exceptions import InvalidInputError
from outlabs_auth.models.sql.enums import APIKeyKind, APIKeyStatus
from outlabs_auth.models.sql.user import User
from outlabs_auth.schemas.api_key import (
    AdminApiKeyCreateRequest,
    AdminApiKeyUpdateRequest,
    ApiKeyCreateResponse,
    ApiKeyGrantableScopesResponse,
    ApiKeyResponse,
)
from outlabs_auth.schemas.common import PaginatedResponse


def get_api_key_admin_router(auth: Any, prefix: str = "", tags: Optional[list[str]] = None) -> APIRouter:
    """
    Generate entity-first admin API key routes for EnterpriseRBAC.

    The v1 surface remains constrained to `personal` keys, but the route shape
    is future-ready for broader key kinds and delegated ownership.
    """
    router = APIRouter(prefix=prefix, tags=tags or ["api-key-admin"])

    async def _to_response(session: AsyncSession, api_key) -> ApiKeyResponse:
        scopes = await auth.api_key_service.get_api_key_scopes(session, api_key.id)
        ip_whitelist = await auth.api_key_service.get_api_key_ip_whitelist(session, api_key.id)
        is_currently_effective = None
        ineffective_reasons = None
        if getattr(auth, "api_key_policy_service", None) is not None:
            effectiveness = await auth.api_key_policy_service.evaluate_effectiveness(
                session,
                api_key=api_key,
                scopes=scopes,
            )
            is_currently_effective = effectiveness.is_currently_effective
            ineffective_reasons = effectiveness.ineffective_reasons
        return ApiKeyResponse(
            id=str(api_key.id),
            prefix=api_key.prefix,
            name=api_key.name,
            key_kind=api_key.key_kind,
            scopes=scopes,
            ip_whitelist=ip_whitelist or None,
            rate_limit_per_minute=api_key.rate_limit_per_minute,
            status=api_key.status,
            usage_count=api_key.usage_count,
            created_at=api_key.created_at,
            expires_at=api_key.expires_at,
            last_used_at=api_key.last_used_at,
            description=api_key.description,
            entity_ids=[str(api_key.entity_id)] if api_key.entity_id else None,
            inherit_from_tree=api_key.inherit_from_tree,
            owner_id=str(api_key.owner_id) if api_key.owner_id else None,
            is_currently_effective=is_currently_effective,
            ineffective_reasons=ineffective_reasons,
        )

    async def _get_entity_api_key(session: AsyncSession, entity_id: UUID, key_id: UUID):
        api_key = await auth.api_key_service.get_api_key(session, key_id)
        if not api_key or api_key.entity_id != entity_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
        return api_key

    @router.get(
        "/{entity_id}/grantable-scopes",
        response_model=ApiKeyGrantableScopesResponse,
        summary="Get grantable API key scopes",
        description="Return the currently grantable scopes for an actor/owner/entity/key-kind combination.",
    )
    async def get_grantable_scopes(
        entity_id: UUID,
        owner_id: Optional[UUID] = Query(default=None),
        key_kind: APIKeyKind = Query(default=APIKeyKind.PERSONAL),
        inherit_from_tree: bool = Query(default=False),
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.require_tree_permission("api_key:create", "entity_id", source="path")),
    ):
        policy_service = getattr(auth, "api_key_policy_service", None)
        if policy_service is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="API key policy service not configured",
            )

        actor_user_id = UUID(auth_result["user_id"])
        effective_owner_id = owner_id or actor_user_id
        owner = await session.get(User, effective_owner_id)
        if owner is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Owner not found")

        try:
            grantable_scopes = await policy_service.calculate_grantable_scopes(
                session,
                actor_user_id=actor_user_id,
                owner=owner,
                key_kind=key_kind,
                entity_id=entity_id,
                inherit_from_tree=inherit_from_tree,
            )
        except InvalidInputError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc

        return ApiKeyGrantableScopesResponse(
            actor_user_id=str(actor_user_id),
            owner_id=str(owner.id),
            entity_id=str(entity_id),
            key_kind=key_kind,
            inherit_from_tree=inherit_from_tree,
            allowed_key_kinds=policy_service.get_allowed_key_kinds(),
            personal_allowed_action_prefixes=policy_service.get_personal_allowed_action_prefixes(),
            grantable_scopes=grantable_scopes,
        )

    @router.get(
        "/{entity_id}/api-keys",
        response_model=PaginatedResponse[ApiKeyResponse],
        summary="List entity API keys",
        description="List API keys anchored to a specific entity with pagination and filters.",
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
            items=[await _to_response(session, api_key) for api_key in api_keys],
            total=total,
            page=page,
            limit=limit,
            pages=pages,
        )

    @router.post(
        "/{entity_id}/api-keys",
        response_model=ApiKeyCreateResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Create entity API key",
        description="Create a new API key anchored to the specified entity.",
    )
    async def create_entity_api_key(
        entity_id: UUID,
        data: AdminApiKeyCreateRequest,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.require_tree_permission("api_key:create", "entity_id", source="path")),
    ):
        actor_user_id = UUID(auth_result["user_id"])
        try:
            owner_id = UUID(data.owner_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(exc),
            ) from exc

        try:
            full_key, api_key_model = await auth.api_key_service.create_api_key(
                session,
                owner_id=owner_id,
                name=data.name,
                scopes=data.scopes,
                prefix_type=data.prefix_type,
                ip_whitelist=data.ip_whitelist,
                rate_limit_per_minute=data.rate_limit_per_minute,
                expires_in_days=data.expires_in_days,
                description=data.description,
                key_kind=data.key_kind,
                entity_id=entity_id,
                inherit_from_tree=data.inherit_from_tree,
                actor_user_id=actor_user_id,
                event_source="api_key_admin_router.create_entity_api_key",
            )
        except InvalidInputError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc

        api_key_response = await _to_response(session, api_key_model)
        return ApiKeyCreateResponse(**api_key_response.model_dump(), api_key=full_key)

    @router.get(
        "/{entity_id}/api-keys/{key_id}",
        response_model=ApiKeyResponse,
        summary="Get entity API key",
        description="Get an API key anchored to the specified entity.",
    )
    async def get_entity_api_key(
        entity_id: UUID,
        key_id: UUID,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.require_tree_permission("api_key:read", "entity_id", source="path")),
    ):
        del auth_result
        api_key = await _get_entity_api_key(session, entity_id, key_id)
        return await _to_response(session, api_key)

    @router.patch(
        "/{entity_id}/api-keys/{key_id}",
        response_model=ApiKeyResponse,
        summary="Update entity API key",
        description="Update an API key anchored to the specified entity.",
    )
    async def update_entity_api_key(
        entity_id: UUID,
        key_id: UUID,
        data: AdminApiKeyUpdateRequest,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.require_tree_permission("api_key:update", "entity_id", source="path")),
    ):
        await _get_entity_api_key(session, entity_id, key_id)
        updates = data.model_dump(exclude_unset=True)
        try:
            updated_key = await auth.api_key_service.update_api_key(
                session,
                key_id=key_id,
                actor_user_id=UUID(auth_result["user_id"]),
                event_source="api_key_admin_router.update_entity_api_key",
                **updates,
            )
        except InvalidInputError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc

        if updated_key is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
        return await _to_response(session, updated_key)

    @router.delete(
        "/{entity_id}/api-keys/{key_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Revoke entity API key",
        description="Revoke an API key anchored to the specified entity.",
    )
    async def delete_entity_api_key(
        entity_id: UUID,
        key_id: UUID,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.require_tree_permission("api_key:delete", "entity_id", source="path")),
    ):
        await _get_entity_api_key(session, entity_id, key_id)
        await auth.api_key_service.revoke_api_key(
            session,
            key_id,
            actor_user_id=UUID(auth_result["user_id"]),
            reason="API key revoked via admin route",
            event_source="api_key_admin_router.delete_entity_api_key",
        )
        return None

    @router.post(
        "/{entity_id}/api-keys/{key_id}/rotate",
        response_model=ApiKeyCreateResponse,
        summary="Rotate entity API key",
        description="Rotate an API key anchored to the specified entity.",
    )
    async def rotate_entity_api_key(
        entity_id: UUID,
        key_id: UUID,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.require_tree_permission("api_key:update", "entity_id", source="path")),
    ):
        await _get_entity_api_key(session, entity_id, key_id)
        full_key, new_key = await auth.api_key_service.rotate_api_key(
            session,
            key_id,
            actor_user_id=UUID(auth_result["user_id"]),
            event_source="api_key_admin_router.rotate_entity_api_key",
        )
        api_key_response = await _to_response(session, new_key)
        return ApiKeyCreateResponse(**api_key_response.model_dump(), api_key=full_key)

    return router
