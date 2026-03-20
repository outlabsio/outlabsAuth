"""
Configuration router factory.

Provides endpoints for managing system-level configuration.
Only superusers can modify these settings.
"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from outlabs_auth.schemas.config import (
    EntityTypeConfig,
    EntityTypeConfigResponse,
    EntityTypeConfigUpdateRequest,
)
from outlabs_auth.services.config import ConfigService


def get_config_router(
    auth: Any, prefix: str = "", tags: Optional[list[str]] = None
) -> APIRouter:
    """
    Generate configuration management router.

    Args:
        auth: OutlabsAuth instance (SimpleRBAC or EnterpriseRBAC)
        prefix: Router prefix (default: "")
        tags: OpenAPI tags (default: ["config"])

    Returns:
        APIRouter with configuration management endpoints

    Routes:
        GET /entity-types - Get entity type configuration
        PUT /entity-types - Update entity type configuration (superuser only)

    Example:
        ```python
        from outlabs_auth import EnterpriseRBAC
        from outlabs_auth.routers import get_config_router

        auth = EnterpriseRBAC(database_url=..., secret_key=...)
        app.include_router(get_config_router(auth, prefix="/config"))
        ```
    """
    router = APIRouter(prefix=prefix, tags=tags or ["config"])
    config_service = ConfigService()

    @router.get(
        "/entity-types",
        response_model=EntityTypeConfigResponse,
        summary="Get entity type configuration",
        description="Get the current entity type configuration including allowed root types and default child types.",
    )
    async def get_entity_type_config(
        session: AsyncSession = Depends(auth.uow),
    ):
        """
        Get entity type configuration.

        This endpoint is public (no auth required) so the frontend
        can fetch configuration before the user is logged in.
        """
        config = await config_service.get_entity_type_config(session)
        return EntityTypeConfigResponse(
            allowed_root_types=config.allowed_root_types,
            default_child_types=config.default_child_types,
        )

    @router.put(
        "/entity-types",
        response_model=EntityTypeConfigResponse,
        summary="Update entity type configuration",
        description="Update entity type configuration. Requires superuser permissions.",
    )
    async def update_entity_type_config(
        data: EntityTypeConfigUpdateRequest,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_superuser()),
    ):
        """
        Update entity type configuration.

        Only superusers can modify this configuration.
        """
        # Get current config
        current = await config_service.get_entity_type_config(session)

        # Merge updates
        new_config = EntityTypeConfig(
            allowed_root_types=data.allowed_root_types
            if data.allowed_root_types is not None
            else current.allowed_root_types,
            default_child_types=data.default_child_types
            if data.default_child_types is not None
            else current.default_child_types,
        )

        # Validate at least one root type across all classes
        if (
            len(new_config.allowed_root_types.structural) == 0
            and len(new_config.allowed_root_types.access_group) == 0
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one root entity type must be configured",
            )

        # Get user ID for audit trail
        user_id = None
        if auth_result and "user_id" in auth_result:
            from uuid import UUID

            user_id = UUID(auth_result["user_id"])

        # Save
        await config_service.set_entity_type_config(
            session, new_config, updated_by_id=user_id
        )

        if auth.observability:
            auth.observability.logger.info(
                "entity_type_config_updated",
                allowed_root_types=new_config.allowed_root_types.model_dump(),
                updated_by=str(user_id) if user_id else None,
            )

        return EntityTypeConfigResponse(
            allowed_root_types=new_config.allowed_root_types,
            default_child_types=new_config.default_child_types,
        )

    return router
