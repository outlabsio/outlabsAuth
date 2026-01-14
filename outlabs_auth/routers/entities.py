"""
Entities router factory.

Provides ready-to-use entity hierarchy management routes for EnterpriseRBAC.
Uses SQLAlchemy for PostgreSQL backend.
"""

from typing import Any, Generic, List, Optional, TypeVar
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from outlabs_auth.schemas.entity import (
    EntityCreateRequest,
    EntityResponse,
    EntityUpdateRequest,
    MemberResponse,
)

# Generic paginated response
T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response wrapper"""

    items: List[T]
    total: int
    page: int
    limit: int
    pages: int


def _entity_to_response(entity: Any) -> EntityResponse:
    """Convert Entity to EntityResponse, handling relationships."""
    parent_id = None
    if entity.parent_id:
        parent_id = str(entity.parent_id)

    return EntityResponse(
        id=str(entity.id),
        name=entity.name,
        display_name=entity.display_name,
        slug=entity.slug,
        description=entity.description,
        entity_class=entity.entity_class.value if hasattr(entity.entity_class, 'value') else entity.entity_class,
        entity_type=entity.entity_type,
        parent_entity_id=parent_id,
        status=entity.status,
        valid_from=entity.valid_from,
        valid_until=entity.valid_until,
        direct_permissions=[],  # Not used in current SQL model
        metadata={},
        allowed_child_classes=[],
        allowed_child_types=[],
        max_members=entity.max_members,
    )


def get_entities_router(
    auth: Any, prefix: str = "", tags: Optional[list[str]] = None
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
    """
    router = APIRouter(prefix=prefix, tags=tags or ["entities"])

    @router.get(
        "/",
        response_model=PaginatedResponse[EntityResponse],
        summary="List entities",
        description="List all entities (requires entity:read permission)",
    )
    async def list_entities(
        entity_class: Optional[str] = Query(
            None, description="Filter by class (structural/access_group)"
        ),
        entity_type: Optional[str] = Query(
            None, description="Filter by type (organization/department/team/etc)"
        ),
        parent_id: Optional[str] = Query(None, description="Filter by parent entity"),
        page: int = Query(1, ge=1, description="Page number (1-indexed)"),
        limit: int = Query(100, ge=1, le=1000, description="Items per page"),
        auth_result=Depends(auth.deps.require_auth()),
        session: AsyncSession = Depends(auth.get_session),
    ):
        """List all entities with optional filtering and pagination."""
        try:
            from outlabs_auth.models.sql.entity import Entity
            from outlabs_auth.models.sql.enums import EntityClass
            from sqlalchemy import select, func

            # Build query filters
            filters = [Entity.status == "active"]

            if entity_class:
                try:
                    ec = EntityClass(entity_class.upper())
                    filters.append(Entity.entity_class == ec)
                except ValueError:
                    filters.append(Entity.entity_class == entity_class)

            if entity_type:
                filters.append(Entity.entity_type == entity_type.lower())

            if parent_id:
                filters.append(Entity.parent_id == UUID(parent_id))

            # Get total count
            count_stmt = select(func.count()).select_from(Entity).where(*filters)
            count_result = await session.execute(count_stmt)
            total = count_result.scalar() or 0

            # Calculate pagination
            skip = (page - 1) * limit
            pages = (total + limit - 1) // limit if total > 0 else 0

            # Get paginated results
            stmt = (
                select(Entity)
                .where(*filters)
                .order_by(Entity.name)
                .offset(skip)
                .limit(limit)
            )
            result = await session.execute(stmt)
            entities = result.scalars().all()

            # Convert to response format
            items = [_entity_to_response(entity) for entity in entities]

            return PaginatedResponse(
                items=items, total=total, page=page, limit=limit, pages=pages
            )
        except Exception as e:
            import traceback

            error_detail = f"{str(e)}\n\nTraceback:\n{traceback.format_exc()}"
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error_detail
            )

    @router.post(
        "/",
        response_model=EntityResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Create entity",
        description="Create new entity (requires entity:create permission)",
    )
    async def create_entity(
        data: EntityCreateRequest,
        auth_result=Depends(auth.deps.require_permission("entity:create")),
        session: AsyncSession = Depends(auth.get_session),
    ):
        """Create a new entity in the hierarchy."""
        try:
            from outlabs_auth.models.sql.enums import EntityClass

            # Parse entity class
            entity_class = EntityClass(data.entity_class.upper()) if isinstance(data.entity_class, str) else data.entity_class

            entity = await auth.entity_service.create_entity(
                session=session,
                name=data.name,
                display_name=data.display_name,
                slug=data.slug,
                description=data.description,
                entity_class=entity_class,
                entity_type=data.entity_type,
                parent_id=UUID(data.parent_entity_id) if data.parent_entity_id else None,
                status=data.status or "active",
            )
            await session.commit()
            return _entity_to_response(entity)
        except Exception as e:
            await session.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    @router.get(
        "/{entity_id}",
        response_model=EntityResponse,
        summary="Get entity",
        description="Get entity details by ID",
    )
    async def get_entity(
        entity_id: str,
        auth_result=Depends(auth.deps.require_permission("entity:read")),
        session: AsyncSession = Depends(auth.get_session),
    ):
        """Get entity details by ID."""
        try:
            entity = await auth.entity_service.get_entity(session, UUID(entity_id))
            if not entity:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found"
                )
            return _entity_to_response(entity)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
            )

    @router.patch(
        "/{entity_id}",
        response_model=EntityResponse,
        summary="Update entity",
        description="Update entity details (requires entity:update permission)",
    )
    async def update_entity(
        entity_id: str,
        data: EntityUpdateRequest,
        auth_result=Depends(auth.deps.require_permission("entity:update")),
        session: AsyncSession = Depends(auth.get_session),
    ):
        """Update entity details."""
        try:
            updates = data.model_dump(exclude_unset=True)
            entity = await auth.entity_service.update_entity(
                session=session,
                entity_id=UUID(entity_id),
                **updates,
            )
            await session.commit()
            return _entity_to_response(entity)
        except Exception as e:
            await session.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    @router.delete(
        "/{entity_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Delete entity",
        description="Delete entity (requires entity:delete permission)",
    )
    async def delete_entity(
        entity_id: str,
        cascade: bool = Query(False, description="Cascade delete children"),
        auth_result=Depends(auth.deps.require_permission("entity:delete")),
        session: AsyncSession = Depends(auth.get_session),
    ):
        """Delete an entity from the hierarchy."""
        try:
            await auth.entity_service.delete_entity(
                session=session,
                entity_id=UUID(entity_id),
                cascade=cascade,
            )
            await session.commit()
        except Exception as e:
            await session.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        return None

    @router.get(
        "/{entity_id}/children",
        response_model=List[EntityResponse],
        summary="Get child entities",
        description="Get direct children of an entity",
    )
    async def get_children(
        entity_id: str,
        auth_result=Depends(auth.deps.require_permission("entity:read")),
        session: AsyncSession = Depends(auth.get_session),
    ):
        """Get all direct children of an entity."""
        try:
            children = await auth.entity_service.get_children(session, UUID(entity_id))
            return [_entity_to_response(child) for child in children]
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
            )

    @router.get(
        "/{entity_id}/descendants",
        response_model=List[EntityResponse],
        summary="Get descendant entities",
        description="Get all descendants of an entity (entire subtree)",
    )
    async def get_descendants(
        entity_id: str,
        entity_type: Optional[str] = Query(None, description="Filter by entity type"),
        auth_result=Depends(auth.deps.require_permission("entity:read")),
        session: AsyncSession = Depends(auth.get_session),
    ):
        """Get all descendant entities (entire subtree)."""
        try:
            descendants = await auth.entity_service.get_descendants(
                session=session,
                entity_id=UUID(entity_id),
                entity_type=entity_type,
            )
            return [_entity_to_response(desc) for desc in descendants]
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
            )

    @router.get(
        "/{entity_id}/path",
        response_model=List[EntityResponse],
        summary="Get entity path",
        description="Get entity path from root to this entity",
    )
    async def get_entity_path(
        entity_id: str,
        auth_result=Depends(auth.deps.require_permission("entity:read")),
        session: AsyncSession = Depends(auth.get_session),
    ):
        """Get the path from root to this entity."""
        try:
            path = await auth.entity_service.get_entity_path(session, UUID(entity_id))
            return [_entity_to_response(entity) for entity in path]
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
            )

    @router.get(
        "/{entity_id}/members",
        response_model=PaginatedResponse[MemberResponse],
        summary="Get entity members",
        description="Get all members of an entity",
    )
    async def get_entity_members(
        entity_id: str,
        page: int = Query(1, ge=1),
        limit: int = Query(50, ge=1, le=100),
        auth_result=Depends(auth.deps.require_permission("entity:read")),
        session: AsyncSession = Depends(auth.get_session),
    ):
        """Get all members of an entity."""
        try:
            from outlabs_auth.models.sql.entity_membership import EntityMembership
            from outlabs_auth.models.sql.user import User
            from sqlalchemy.orm import selectinload

            # Get memberships with pagination
            memberships, total = await auth.membership_service.get_entity_members(
                session=session,
                entity_id=UUID(entity_id),
                page=page,
                limit=limit,
            )

            # Build member responses
            members = []
            for membership in memberships:
                # Get user
                user = await session.get(User, membership.user_id)
                if user:
                    members.append(
                        MemberResponse(
                            user_id=str(user.id),
                            email=user.email,
                            first_name=user.first_name,
                            last_name=user.last_name,
                            role_ids=[str(role.id) for role in membership.roles],
                            role_names=[role.name for role in membership.roles],
                        )
                    )

            pages = (total + limit - 1) // limit if total > 0 else 0

            return PaginatedResponse(
                items=members,
                total=total,
                page=page,
                limit=limit,
                pages=pages,
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
            )

    return router
