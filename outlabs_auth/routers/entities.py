"""
Entities router factory.

Provides ready-to-use entity hierarchy management routes for EnterpriseRBAC.
"""

from typing import Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query

from outlabs_auth.schemas.entity import (
    EntityResponse,
    EntityCreateRequest,
    EntityUpdateRequest,
    MemberResponse,
)


def get_entities_router(
    auth: Any,
    prefix: str = "",
    tags: Optional[list[str]] = None
) -> APIRouter:
    """
    Generate entity hierarchy management router.

    Args:
        auth: OutlabsAuth instance (EnterpriseRBAC)
        prefix: Router prefix (default: "")
        tags: OpenAPI tags (default: ["entities"])

    Returns:
        APIRouter with entity management endpoints

    Routes:
        GET / - List all entities
        POST / - Create new entity
        GET /{entity_id} - Get entity details
        PATCH /{entity_id} - Update entity
        DELETE /{entity_id} - Delete entity
        GET /{entity_id}/children - Get child entities
        GET /{entity_id}/descendants - Get all descendant entities
        GET /{entity_id}/path - Get entity path (from root to entity)
        GET /{entity_id}/members - Get entity members

    Example:
        ```python
        from outlabs_auth import EnterpriseRBAC
        from outlabs_auth.routers import get_entities_router

        auth = EnterpriseRBAC(database=db)
        app.include_router(get_entities_router(auth, prefix="/entities"))
        ```
    """
    router = APIRouter(prefix=prefix, tags=tags or ["entities"])

    @router.get(
        "/",
        response_model=List[EntityResponse],
        summary="List entities",
        description="List all entities (requires entity:read permission)"
    )
    async def list_entities(
        entity_class: Optional[str] = Query(None, description="Filter by class (structural/access_group)"),
        entity_type: Optional[str] = Query(None, description="Filter by type (organization/department/team/etc)"),
        parent_id: Optional[str] = Query(None, description="Filter by parent entity"),
        auth_result = Depends(auth.deps.require_permission("entity:read"))
    ):
        """List all entities with optional filtering."""
        try:
            # TODO: Implement filtering in entity service
            # For now, get all entities and filter in Python
            from outlabs_auth.models.entity import EntityModel

            query = {}
            if entity_class:
                query["entity_class"] = entity_class
            if entity_type:
                query["entity_type"] = entity_type
            if parent_id:
                query["parent_entity_id"] = parent_id

            entities = await EntityModel.find(query).to_list()
            return [EntityResponse(**entity.model_dump()) for entity in entities]
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )

    @router.post(
        "/",
        response_model=EntityResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Create entity",
        description="Create new entity (requires entity:create permission)"
    )
    async def create_entity(
        data: EntityCreateRequest,
        auth_result = Depends(auth.deps.require_permission("entity:create"))
    ):
        """Create a new entity in the hierarchy."""
        try:
            entity = await auth.entity_service.create_entity(
                name=data.name,
                display_name=data.display_name,
                slug=data.slug,
                description=data.description,
                entity_class=data.entity_class,
                entity_type=data.entity_type,
                parent_entity_id=data.parent_entity_id,
                status=data.status,
                valid_from=data.valid_from,
                valid_until=data.valid_until,
                direct_permissions=data.direct_permissions,
                metadata=data.metadata,
                allowed_child_classes=data.allowed_child_classes,
                allowed_child_types=data.allowed_child_types,
                max_members=data.max_members
            )
            return EntityResponse(**entity.model_dump())
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

    @router.get(
        "/{entity_id}",
        response_model=EntityResponse,
        summary="Get entity",
        description="Get entity details by ID"
    )
    async def get_entity(
        entity_id: str,
        auth_result = Depends(auth.deps.require_permission("entity:read"))
    ):
        """Get entity details by ID."""
        try:
            entity = await auth.entity_service.get_entity(entity_id)
            if not entity:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Entity not found"
                )
            return EntityResponse(**entity.model_dump())
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )

    @router.patch(
        "/{entity_id}",
        response_model=EntityResponse,
        summary="Update entity",
        description="Update entity details (requires entity:update permission)"
    )
    async def update_entity(
        entity_id: str,
        data: EntityUpdateRequest,
        auth_result = Depends(auth.deps.require_permission("entity:update"))
    ):
        """Update entity details."""
        try:
            entity = await auth.entity_service.update_entity(
                entity_id=entity_id,
                update_dict=data.model_dump(exclude_unset=True)
            )
            return EntityResponse(**entity.model_dump())
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

    @router.delete(
        "/{entity_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Delete entity",
        description="Delete entity (requires entity:delete permission)"
    )
    async def delete_entity(
        entity_id: str,
        auth_result = Depends(auth.deps.require_permission("entity:delete"))
    ):
        """Delete an entity from the hierarchy."""
        try:
            await auth.entity_service.delete_entity(entity_id)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        return None

    @router.get(
        "/{entity_id}/children",
        response_model=List[EntityResponse],
        summary="Get child entities",
        description="Get direct children of an entity"
    )
    async def get_children(
        entity_id: str,
        auth_result = Depends(auth.deps.require_permission("entity:read"))
    ):
        """Get all direct children of an entity."""
        try:
            children = await auth.entity_service.get_children(entity_id)
            return [EntityResponse(**child.model_dump()) for child in children]
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )

    @router.get(
        "/{entity_id}/descendants",
        response_model=List[EntityResponse],
        summary="Get descendant entities",
        description="Get all descendants of an entity (entire subtree)"
    )
    async def get_descendants(
        entity_id: str,
        max_depth: Optional[int] = Query(None, description="Maximum depth to traverse"),
        auth_result = Depends(auth.deps.require_permission("entity:read"))
    ):
        """Get all descendant entities (entire subtree)."""
        try:
            descendants = await auth.entity_service.get_descendants(
                entity_id=entity_id,
                max_depth=max_depth
            )
            return [EntityResponse(**desc.model_dump()) for desc in descendants]
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )

    @router.get(
        "/{entity_id}/path",
        response_model=List[EntityResponse],
        summary="Get entity path",
        description="Get entity path from root to this entity"
    )
    async def get_entity_path(
        entity_id: str,
        auth_result = Depends(auth.deps.require_permission("entity:read"))
    ):
        """Get the path from root to this entity."""
        try:
            path = await auth.entity_service.get_entity_path(entity_id)
            return [EntityResponse(**entity.model_dump()) for entity in path]
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )

    @router.get(
        "/{entity_id}/members",
        response_model=List[MemberResponse],
        summary="Get entity members",
        description="Get all members of an entity"
    )
    async def get_entity_members(
        entity_id: str,
        auth_result = Depends(auth.deps.require_permission("entity:read"))
    ):
        """Get all members of an entity."""
        try:
            # Get all memberships for this entity
            from outlabs_auth.models.membership import EntityMembershipModel
            from outlabs_auth.models.user import UserModel

            memberships = await EntityMembershipModel.find(
                EntityMembershipModel.entity_id == entity_id
            ).to_list()

            # Fetch user details for each membership
            members = []
            for membership in memberships:
                user = await UserModel.get(membership.user_id)
                if user:
                    members.append(MemberResponse(
                        user_id=str(user.id),
                        email=user.email,
                        first_name=user.first_name,
                        last_name=user.last_name,
                        role_ids=[str(rid) for rid in membership.role_ids],
                        role_names=[]  # TODO: Fetch role names
                    ))

            return members
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )

    return router
