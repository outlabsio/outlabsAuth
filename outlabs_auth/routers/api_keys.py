"""
API Keys router factory.

Provides ready-to-use API key management routes (DD-041).
"""

from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from outlabs_auth.schemas.api_key import (
    ApiKeyCreateRequest,
    ApiKeyCreateResponse,
    ApiKeyResponse,
    ApiKeyUpdateRequest,
)


def get_api_keys_router(
    auth: Any, prefix: str = "", tags: Optional[list[str]] = None
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

    async def _to_response(session: AsyncSession, api_key) -> ApiKeyResponse:
        scopes = await auth.api_key_service.get_api_key_scopes(session, api_key.id)
        ip_whitelist = await auth.api_key_service.get_api_key_ip_whitelist(
            session, api_key.id
        )
        return ApiKeyResponse(
            id=str(api_key.id),
            prefix=api_key.prefix,
            name=api_key.name,
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
            owner_id=str(api_key.owner_id) if api_key.owner_id else None,
        )

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
        api_keys = await auth.api_key_service.list_user_api_keys(
            session, user_id=user_id
        )
        return [await _to_response(session, key) for key in api_keys]

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
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=str(e),
                )

        # create_api_key returns tuple: (full_key, api_key_model)
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
            entity_id=entity_id,
        )

        api_key_response = await _to_response(session, api_key_model)
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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="API key not found"
            )

        # Verify ownership
        if str(api_key.owner_id) != auth_result["user_id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )

        return await _to_response(session, api_key)

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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="API key not found"
            )

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
        updated_key = await auth.api_key_service.update_api_key(
            session, key_id=key_id, **updates
        )

        if not updated_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="API key not found"
            )
        return await _to_response(session, updated_key)

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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="API key not found"
            )

        # Delete (revoke)
        await auth.api_key_service.revoke_api_key(session, key_id)

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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="API key not found"
            )

        # Create new key with same settings
        new_key, full_key = await auth.api_key_service.create_api_key(
            session=session,
            owner_id=api_key.owner_id,
            name=f"{api_key.name} (rotated)",
            scopes=api_key.scopes or [],
            prefix_type=api_key.prefix[:7] if api_key.prefix else "sk_live",
            ip_whitelist=api_key.ip_whitelist,
            rate_limit_per_minute=api_key.rate_limit_per_minute,
            expires_in_days=None,  # Keep same expiry policy - new key starts fresh
            description=api_key.description,
            entity_ids=api_key.entity_ids,
        )

        # Revoke old key
        await auth.api_key_service.revoke_api_key(session, key_id)

        return ApiKeyCreateResponse(
            id=str(new_key.id),
            prefix=new_key.prefix,
            name=new_key.name,
            scopes=new_key.scopes or [],
            ip_whitelist=new_key.ip_whitelist,
            rate_limit_per_minute=new_key.rate_limit_per_minute,
            status=new_key.status,
            usage_count=new_key.usage_count,
            created_at=new_key.created_at,
            expires_at=new_key.expires_at,
            last_used_at=new_key.last_used_at,
            description=new_key.description,
            entity_ids=new_key.entity_ids,
            owner_id=str(new_key.owner_id) if new_key.owner_id else None,
            api_key=full_key,
        )

    return router
