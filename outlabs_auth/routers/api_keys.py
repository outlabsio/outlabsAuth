"""
API Keys router factory.

Provides ready-to-use API key management routes (DD-041).
"""

from enum import Enum
from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from outlabs_auth.core.exceptions import InvalidInputError
from outlabs_auth.models.sql.enums import APIKeyKind
from outlabs_auth.routers._api_key_response import (
    build_api_key_response,
    build_api_key_responses,
)
from outlabs_auth.schemas.api_key import (
    ApiKeyCreateRequest,
    ApiKeyCreateResponse,
    ApiKeyGrantableScopesResponse,
    ApiKeyResponse,
    ApiKeyUpdateRequest,
)


def get_api_keys_router(
    auth: Any,
    prefix: str = "",
    tags: Optional[list[str | Enum]] = None,
) -> APIRouter:
    """
    Generate API key management router.

    Args:
        auth: OutlabsAuth instance (SimpleRBAC or EnterpriseRBAC)
        prefix: Router prefix (default: "")
        tags: OpenAPI tags (default: ["api-keys"])

    Returns:
        APIRouter with API key management endpoints

    Routes:
        GET / - List user's API keys
        POST / - Create new API key
        GET /{key_id} - Get API key details
        PATCH /{key_id} - Update API key
        DELETE /{key_id} - Delete (revoke) API key
        POST /{key_id}/rotate - Rotate API key

    Example:
        ```python
        from outlabs_auth import SimpleRBAC
        from outlabs_auth.routers import get_api_keys_router

        auth = SimpleRBAC(database=db)
        app.include_router(get_api_keys_router(auth, prefix="/api-keys"))
        ```
    """
    router = APIRouter(prefix=prefix, tags=tags or ["api-keys"])

    @router.get(
        "/",
        response_model=List[ApiKeyResponse],
        summary="List API keys",
        description="List all API keys for the authenticated user",
    )
    async def list_api_keys(
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_auth()),
    ):
        """List all API keys for the current user."""
        user_id = UUID(auth_result["user_id"])
        api_keys = await auth.api_key_service.list_user_api_keys(session, user_id=user_id)
        return await build_api_key_responses(auth, session, api_keys)

    @router.get(
        "/grantable-scopes",
        response_model=ApiKeyGrantableScopesResponse,
        summary="Get personal API key grantable scopes",
        description="Get the mounted grant-policy result for the authenticated user's personal API keys.",
    )
    async def get_personal_key_grantable_scopes(
        entity_id: Optional[UUID] = Query(default=None),
        inherit_from_tree: bool = Query(default=False),
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_auth()),
    ):
        actor_user_id = auth_result.get("user_id")
        owner = auth_result.get("user")
        if actor_user_id is None or owner is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Authenticated user context is required for personal API key grantable scopes",
            )
        if getattr(auth, "api_key_policy_service", None) is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="API key policy service is unavailable",
            )

        try:
            grantable_scopes = await auth.api_key_policy_service.calculate_grantable_scopes(
                session,
                actor_user_id=UUID(str(actor_user_id)),
                owner=owner,
                key_kind=APIKeyKind.PERSONAL,
                entity_id=entity_id,
                inherit_from_tree=inherit_from_tree,
            )
        except InvalidInputError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=exc.message,
            ) from exc

        return ApiKeyGrantableScopesResponse(
            actor_user_id=str(actor_user_id),
            owner_id=str(owner.id),
            entity_id=str(entity_id) if entity_id else None,
            key_kind=APIKeyKind.PERSONAL,
            inherit_from_tree=inherit_from_tree,
            allowed_key_kinds=[APIKeyKind.PERSONAL],
            personal_allowed_action_prefixes=auth.api_key_policy_service.get_personal_allowed_action_prefixes(),
            grantable_scopes=grantable_scopes,
        )

    @router.post(
        "/",
        response_model=ApiKeyCreateResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Create API key",
        description="Create new API key (full key shown ONLY ONCE!)",
    )
    async def create_api_key(
        data: ApiKeyCreateRequest,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_auth()),
    ):
        """
        Create new API key.

        WARNING: The full API key is returned ONLY ONCE!
        Store it securely. You cannot retrieve it later.

        Triggers on_api_key_created hook (should email the key to user).
        """
        owner_id = UUID(auth_result["user_id"])
        if data.key_kind != APIKeyKind.PERSONAL:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Self-service API keys only support personal keys",
            )

        entity_id = None
        if data.entity_ids:
            if len(data.entity_ids) != 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Multiple entity_ids not supported (use 1 or omit)",
                )
            try:
                entity_id = UUID(data.entity_ids[0])
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=str(e),
                )

        if (
            getattr(auth, "api_key_policy_service", None) is not None
            and getattr(auth.config, "enable_entity_hierarchy", False)
            and data.key_kind == APIKeyKind.PERSONAL
            and data.scopes
            and entity_id is None
        ):
            actor_user_id = auth_result.get("user_id")
            owner = auth_result.get("user")
            if actor_user_id is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Authenticated user context is required for personal API keys",
                )
            if owner is None:
                from outlabs_auth.models.sql.user import User

                owner = await session.get(User, UUID(str(actor_user_id)))
            if owner is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Authenticated user context is required for personal API keys",
                )

            try:
                grantable_scopes = await auth.api_key_policy_service.calculate_grantable_scopes(
                    session,
                    actor_user_id=UUID(str(actor_user_id)),
                    owner=owner,
                    key_kind=APIKeyKind.PERSONAL,
                    entity_id=entity_id,
                    inherit_from_tree=data.inherit_from_tree,
                )
            except InvalidInputError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=exc.message,
                ) from exc

            missing_scopes = [
                scope
                for scope in data.scopes
                if not grantable_scopes or not auth.api_key_service.scopes_allow_permission(grantable_scopes, scope)
            ]
            if missing_scopes:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Requested scopes require an entity anchor in EnterpriseRBAC",
                )

        # create_api_key returns tuple: (full_key, api_key_model)
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
                actor_user_id=owner_id,
                event_source="api_keys_router.create_api_key",
            )
        except InvalidInputError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=exc.message,
            ) from exc

        api_key_response = await build_api_key_response(auth, session, api_key_model)
        return ApiKeyCreateResponse(**api_key_response.model_dump(), api_key=full_key)

    @router.get(
        "/{key_id}",
        response_model=ApiKeyResponse,
        summary="Get API key",
        description="Get API key details (NOT the full key)",
    )
    async def get_api_key(
        key_id: UUID,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_auth()),
    ):
        """Get API key details (without the secret key)."""
        api_key = await auth.api_key_service.get_api_key(session, key_id)

        if not api_key:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

        # Verify ownership
        if str(api_key.owner_id) != auth_result["user_id"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

        return await build_api_key_response(auth, session, api_key)

    @router.patch(
        "/{key_id}",
        response_model=ApiKeyResponse,
        summary="Update API key",
        description="Update API key settings",
    )
    async def update_api_key(
        key_id: UUID,
        data: ApiKeyUpdateRequest,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_auth()),
    ):
        """Update API key settings."""
        # Get and verify ownership
        api_key = await auth.api_key_service.get_api_key(session, key_id)
        if not api_key or str(api_key.owner_id) != auth_result["user_id"]:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

        updates = data.model_dump(exclude_unset=True)
        if "entity_ids" in updates:
            entity_ids = updates.pop("entity_ids")
            if entity_ids:
                if len(entity_ids) != 1:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Multiple entity_ids not supported (use 1 or omit)",
                    )
                updates["entity_id"] = UUID(entity_ids[0])
            else:
                updates["entity_id"] = None

        # Update
        try:
            updated_key = await auth.api_key_service.update_api_key(
                session,
                key_id=key_id,
                actor_user_id=UUID(auth_result["user_id"]),
                event_source="api_keys_router.update_api_key",
                **updates,
            )
        except InvalidInputError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=exc.message,
            ) from exc

        if not updated_key:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
        return await build_api_key_response(auth, session, updated_key)

    @router.delete(
        "/{key_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Delete API key",
        description="Delete (revoke) API key",
    )
    async def delete_api_key(
        key_id: UUID,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_auth()),
    ):
        """
        Delete (revoke) API key.

        Triggers on_api_key_revoked hook.
        """
        # Get and verify ownership
        api_key = await auth.api_key_service.get_api_key(session, key_id)
        if not api_key or str(api_key.owner_id) != auth_result["user_id"]:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

        # Delete (revoke)
        await auth.api_key_service.revoke_api_key(
            session,
            key_id,
            actor_user_id=UUID(auth_result["user_id"]),
            reason="API key revoked by owner",
            event_source="api_keys_router.delete_api_key",
        )

        return None

    @router.post(
        "/{key_id}/rotate",
        response_model=ApiKeyCreateResponse,
        summary="Rotate API key",
        description="Create new key and revoke old one",
    )
    async def rotate_api_key(
        key_id: UUID,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_auth()),
    ):
        """
        Rotate API key (create new, revoke old).

        The new full key is returned ONLY ONCE!

        Triggers on_api_key_rotated hook.
        """
        # Get and verify ownership
        api_key = await auth.api_key_service.get_api_key(session, key_id)
        if not api_key or str(api_key.owner_id) != auth_result["user_id"]:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

        full_key, new_key = await auth.api_key_service.rotate_api_key(
            session,
            key_id,
            actor_user_id=UUID(auth_result["user_id"]),
            event_source="api_keys_router.rotate_api_key",
        )

        api_key_response = await build_api_key_response(auth, session, new_key)
        return ApiKeyCreateResponse(**api_key_response.model_dump(), api_key=full_key)

    return router
