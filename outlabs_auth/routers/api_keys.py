"""
API Keys router factory.

Provides ready-to-use API key management routes (DD-041).
"""

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status

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

    @router.get(
        "/",
        response_model=List[ApiKeyResponse],
        summary="List API keys",
        description="List all API keys for the authenticated user",
    )
    async def list_api_keys(auth_result=Depends(auth.deps.require_auth())):
        """List all API keys for the current user."""
        try:
            api_keys = await auth.api_key_service.list_user_api_keys(
                user_id=auth_result["user_id"]
            )

            # Convert to response format
            response_list = []
            for api_key in api_keys:
                response_data = api_key.model_dump()
                response_data["id"] = str(api_key.id)
                response_data["owner_id"] = (
                    str(api_key.owner.ref.id) if api_key.owner else None
                )
                response_list.append(ApiKeyResponse(**response_data))

            return response_list
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
            )

    @router.post(
        "/",
        response_model=ApiKeyCreateResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Create API key",
        description="Create new API key (full key shown ONLY ONCE!)",
    )
    async def create_api_key(
        data: ApiKeyCreateRequest, auth_result=Depends(auth.deps.require_auth())
    ):
        """
        Create new API key.

        WARNING: The full API key is returned ONLY ONCE!
        Store it securely. You cannot retrieve it later.

        Triggers on_api_key_created hook (should email the key to user).
        """
        try:
            # create_api_key returns tuple: (full_key, api_key_model)
            full_key, api_key_model = await auth.api_key_service.create_api_key(
                owner_id=auth_result["user_id"],
                name=data.name,
                scopes=data.scopes,
                prefix_type=data.prefix_type,
                ip_whitelist=data.ip_whitelist,
                rate_limit_per_minute=data.rate_limit_per_minute,
                expires_at=data.expires_at,
                description=data.description,
                entity_ids=data.entity_ids,
            )

            # Convert model to response with full key
            response_data = api_key_model.model_dump()
            response_data["id"] = str(api_key_model.id)
            response_data["owner_id"] = (
                str(api_key_model.owner.ref.id) if api_key_model.owner else None
            )
            response_data["api_key"] = full_key  # Full key (ONLY time it's shown!)

            return ApiKeyCreateResponse(**response_data)

        except Exception as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    @router.get(
        "/{key_id}",
        response_model=ApiKeyResponse,
        summary="Get API key",
        description="Get API key details (NOT the full key)",
    )
    async def get_api_key(key_id: str, auth_result=Depends(auth.deps.require_auth())):
        """Get API key details (without the secret key)."""
        try:
            api_key = await auth.api_key_service.get_api_key(key_id)

            if not api_key:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="API key not found"
                )

            # Verify ownership
            owner_id = str(api_key.owner.ref.id) if api_key.owner else None
            if owner_id != auth_result["user_id"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
                )

            # Convert to response format
            response_data = api_key.model_dump()
            response_data["id"] = str(api_key.id)
            response_data["owner_id"] = owner_id
            return ApiKeyResponse(**response_data)

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
            )

    @router.patch(
        "/{key_id}",
        response_model=ApiKeyResponse,
        summary="Update API key",
        description="Update API key settings",
    )
    async def update_api_key(
        key_id: str,
        data: ApiKeyUpdateRequest,
        auth_result=Depends(auth.deps.require_auth()),
    ):
        """Update API key settings."""
        try:
            # Get and verify ownership
            api_key = await auth.api_key_service.get_api_key(key_id)
            owner_id = str(api_key.owner.ref.id) if api_key and api_key.owner else None
            if not api_key or owner_id != auth_result["user_id"]:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="API key not found"
                )

            # Update
            updated_key = await auth.api_key_service.update_api_key(
                key_id=key_id, **data.model_dump(exclude_unset=True)
            )

            # Convert to response format
            response_data = updated_key.model_dump()
            response_data["id"] = str(updated_key.id)
            response_data["owner_id"] = (
                str(updated_key.owner.ref.id) if updated_key.owner else None
            )
            return ApiKeyResponse(**response_data)

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    @router.delete(
        "/{key_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Delete API key",
        description="Delete (revoke) API key",
    )
    async def delete_api_key(
        key_id: str, auth_result=Depends(auth.deps.require_auth())
    ):
        """
        Delete (revoke) API key.

        Triggers on_api_key_revoked hook.
        """
        try:
            # Get and verify ownership
            api_key = await auth.api_key_service.get_api_key(key_id)
            owner_id = str(api_key.owner.ref.id) if api_key and api_key.owner else None
            if not api_key or owner_id != auth_result["user_id"]:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="API key not found"
                )

            # Delete (revoke)
            await auth.api_key_service.revoke_api_key(key_id)

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        return None

    @router.post(
        "/{key_id}/rotate",
        response_model=ApiKeyCreateResponse,
        summary="Rotate API key",
        description="Create new key and revoke old one",
    )
    async def rotate_api_key(
        key_id: str, auth_result=Depends(auth.deps.require_auth())
    ):
        """
        Rotate API key (create new, revoke old).

        The new full key is returned ONLY ONCE!

        Triggers on_api_key_rotated hook.
        """
        try:
            # Get and verify ownership
            api_key = await auth.api_key_service.get_api_key(key_id)
            owner_id = str(api_key.owner.ref.id) if api_key and api_key.owner else None
            if not api_key or owner_id != auth_result["user_id"]:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="API key not found"
                )

            # TODO: Implement rotate_api_key in service
            # For now, manually rotate: create new with same settings, revoke old
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="API key rotation not yet implemented",
            )

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return router
