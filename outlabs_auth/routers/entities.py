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
    EntityMoveRequest,
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
        entity_class=entity.entity_class.value
        if hasattr(entity.entity_class, "value")
        else entity.entity_class,
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
        parent_id: Optional[UUID] = Query(None, description="Filter by parent entity"),
        page: int = Query(1, ge=1, description="Page number (1-indexed)"),
        limit: int = Query(100, ge=1, le=1000, description="Items per page"),
        auth_result=Depends(auth.deps.require_auth()),
        session: AsyncSession = Depends(auth.uow),
    ):
        """List all entities with optional filtering and pagination."""
        from sqlalchemy import func, select

        from outlabs_auth.models.sql.entity import Entity
        from outlabs_auth.models.sql.enums import EntityClass

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
            filters.append(Entity.parent_id == parent_id)

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

    @router.post(
        "/",
        response_model=EntityResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Create entity",
        description="Create new entity (requires entity:create permission)",
    )
    async def create_entity(
        data: EntityCreateRequest,
        auth_result=Depends(
            auth.require_tree_permission(
                "entity:create", "parent_entity_id", source="body"
            )
        ),
        session: AsyncSession = Depends(auth.uow),
    ):
        """Create a new entity in the hierarchy."""
        from outlabs_auth.models.sql.enums import EntityClass

        # Parse entity class
        entity_class = (
            EntityClass(data.entity_class)
            if isinstance(data.entity_class, str)
            else data.entity_class
        )

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
        return _entity_to_response(entity)

    @router.get(
        "/{entity_id}",
        response_model=EntityResponse,
        summary="Get entity",
        description="Get entity details by ID",
    )
    async def get_entity(
        entity_id: UUID,
        auth_result=Depends(auth.deps.require_permission("entity:read")),
        session: AsyncSession = Depends(auth.uow),
    ):
        """Get entity details by ID."""
        entity = await auth.entity_service.get_entity(session, entity_id)
        if not entity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found"
            )
        return _entity_to_response(entity)

    @router.patch(
        "/{entity_id}",
        response_model=EntityResponse,
        summary="Update entity",
        description="Update entity details (requires entity:update permission)",
    )
    async def update_entity(
        entity_id: UUID,
        data: EntityUpdateRequest,
        auth_result=Depends(auth.deps.require_permission("entity:update")),
        session: AsyncSession = Depends(auth.uow),
    ):
        """Update entity details."""
        updates = data.model_dump(exclude_unset=True)
        entity = await auth.entity_service.update_entity(
            session=session,
            entity_id=entity_id,
            **updates,
        )
        return _entity_to_response(entity)

    @router.post(
        "/{entity_id}/move",
        response_model=EntityResponse,
        summary="Move entity",
        description="Re-parent an entity (requires entity:update permission on entity, and entity:create permission on new parent if provided)",
    )
    async def move_entity(
        entity_id: UUID,
        data: EntityMoveRequest,
        auth_result=Depends(
            auth.require_entity_permission("entity:update", "entity_id")
        ),
        session: AsyncSession = Depends(auth.uow),
    ):
        new_parent_id = UUID(data.new_parent_id) if data.new_parent_id else None

        # If moving under a new parent, require permission to create under that parent
        # (tree permissions from ancestors apply automatically via the closure table).
        if new_parent_id is not None:
            user_id = UUID(auth_result["user_id"])
            has_create = await auth.permission_service.check_permission(
                session,
                user_id=user_id,
                permission="entity:create_tree",
                entity_id=new_parent_id,
            )
            if not has_create:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions",
                )

        entity = await auth.entity_service.move_entity(
            session=session,
            entity_id=entity_id,
            new_parent_id=new_parent_id,
        )
        return _entity_to_response(entity)

    @router.delete(
        "/{entity_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Delete entity",
        description="Delete entity (requires entity:delete permission)",
    )
    async def delete_entity(
        entity_id: UUID,
        cascade: bool = Query(False, description="Cascade delete children"),
        auth_result=Depends(auth.deps.require_permission("entity:delete")),
        session: AsyncSession = Depends(auth.uow),
    ):
        """Delete an entity from the hierarchy."""
        await auth.entity_service.delete_entity(
            session=session,
            entity_id=entity_id,
            cascade=cascade,
        )
        return None

    @router.get(
        "/{entity_id}/children",
        response_model=List[EntityResponse],
        summary="Get child entities",
        description="Get direct children of an entity",
    )
    async def get_children(
        entity_id: UUID,
        auth_result=Depends(auth.deps.require_permission("entity:read")),
        session: AsyncSession = Depends(auth.uow),
    ):
        """Get all direct children of an entity."""
        children = await auth.entity_service.get_children(session, entity_id)
        return [_entity_to_response(child) for child in children]

    @router.get(
        "/{entity_id}/descendants",
        response_model=List[EntityResponse],
        summary="Get descendant entities",
        description="Get all descendants of an entity (entire subtree)",
    )
    async def get_descendants(
        entity_id: UUID,
        entity_type: Optional[str] = Query(None, description="Filter by entity type"),
        auth_result=Depends(auth.deps.require_permission("entity:read")),
        session: AsyncSession = Depends(auth.uow),
    ):
        """Get all descendant entities (entire subtree)."""
        descendants = await auth.entity_service.get_descendants(
            session=session,
            entity_id=entity_id,
            entity_type=entity_type,
        )
        return [_entity_to_response(desc) for desc in descendants]

    @router.get(
        "/{entity_id}/path",
        response_model=List[EntityResponse],
        summary="Get entity path",
        description="Get entity path from root to this entity",
    )
    async def get_entity_path(
        entity_id: UUID,
        auth_result=Depends(auth.deps.require_permission("entity:read")),
        session: AsyncSession = Depends(auth.uow),
    ):
        """Get the path from root to this entity."""
        path = await auth.entity_service.get_entity_path(session, entity_id)
        return [_entity_to_response(entity) for entity in path]

    @router.get(
        "/{entity_id}/members",
        response_model=PaginatedResponse[MemberResponse],
        summary="Get entity members",
        description="Get all members of an entity",
    )
    async def get_entity_members(
        entity_id: UUID,
        page: int = Query(1, ge=1),
        limit: int = Query(50, ge=1, le=100),
        auth_result=Depends(auth.deps.require_permission("entity:read")),
        session: AsyncSession = Depends(auth.uow),
    ):
        """Get all members of an entity."""
        from outlabs_auth.models.sql.user import User

        # Get memberships with pagination
        memberships, total = await auth.membership_service.get_entity_members(
            session=session,
            entity_id=entity_id,
            page=page,
            limit=limit,
        )

        # Build member responses
        members = []
        for membership in memberships:
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

    return router
