"""
Entities router factory.

Provides ready-to-use entity hierarchy management routes for EnterpriseRBAC.
Uses SQLAlchemy for PostgreSQL backend.
"""

from enum import Enum
from typing import Any, List, Optional, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from outlabs_auth.routers._scope import (
    entity_in_scope,
    entity_not_found,
    resolve_principal_scope,
    scope_enforced,
)
from outlabs_auth.routers.capabilities import mark_auth_surface
from outlabs_auth.schemas.common import PaginatedResponse
from outlabs_auth.schemas.entity import (
    EntityCreateRequest,
    EntityMoveRequest,
    EntityResponse,
    EntityTypeSuggestionsResponse,
    EntityUpdateRequest,
    MemberResponse,
)


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
        entity_class=entity.entity_class.value if hasattr(entity.entity_class, "value") else entity.entity_class,
        entity_type=entity.entity_type,
        parent_entity_id=parent_id,
        status=entity.status,
        valid_from=entity.valid_from,
        valid_until=entity.valid_until,
        allowed_child_classes=entity.allowed_child_classes or [],
        allowed_child_types=entity.allowed_child_types or [],
        max_members=entity.max_members,
        child_name_pattern=entity.child_name_pattern,
        child_display_name_pattern=entity.child_display_name_pattern,
        child_slug_pattern=entity.child_slug_pattern,
        child_naming_guidance=entity.child_naming_guidance,
        created_at=getattr(entity, "__dict__", {}).get("created_at"),
        updated_at=getattr(entity, "__dict__", {}).get("updated_at"),
    )


def get_entities_router(auth: Any, prefix: str = "", tags: Optional[list[str | Enum]] = None) -> APIRouter:
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

    # DD-061: entity routes apply the same tenant scope as the user routes
    # (DD-056). Out-of-scope entities answer 404, indistinguishable from
    # nonexistent ones; structural changes that create or remove a tenant
    # (root create, move-to-root, root archive) require a global actor.

    async def _scope(session: AsyncSession, auth_result: Any) -> dict[str, Any]:
        if not scope_enforced(auth):
            return {"is_global": True, "entity_ids": []}
        return await resolve_principal_scope(auth, session, auth_result)

    async def _require_entity_in_scope(session: AsyncSession, auth_result: Any, entity_id: UUID) -> dict[str, Any]:
        scope = await _scope(session, auth_result)
        if not entity_in_scope(scope, entity_id):
            raise entity_not_found()
        return scope

    def _require_global(scope: dict[str, Any], detail: str) -> None:
        if not scope.get("is_global"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)

    def _actor_id(auth_result: Any) -> Optional[UUID]:
        raw = auth_result.get("user_id") if isinstance(auth_result, dict) else None
        try:
            return UUID(str(raw)) if raw else None
        except ValueError:
            return None

    @router.get(
        "/",
        response_model=PaginatedResponse[EntityResponse],
        summary="List entities",
        description="List all entities (requires entity:read permission)",
    )
    async def list_entities(
        search: Optional[str] = Query(None, description="Search by name, display name, description, or type"),
        entity_class: Optional[str] = Query(None, description="Filter by class (structural/access_group)"),
        entity_type: Optional[str] = Query(None, description="Filter by type (organization/department/team/etc)"),
        parent_id: Optional[UUID] = Query(None, description="Filter by parent entity"),
        root_only: bool = Query(False, description="Only include root entities"),
        page: int = Query(1, ge=1, description="Page number (1-indexed)"),
        limit: int = Query(100, ge=1, le=1000, description="Items per page"),
        auth_result=Depends(auth.deps.require_permission("entity:read")),
        session: AsyncSession = Depends(auth.uow),
    ):
        """List all entities with optional filtering and pagination."""
        from sqlalchemy import func, or_, select

        from outlabs_auth.models.sql.entity import Entity
        from outlabs_auth.models.sql.enums import EntityClass

        # Build query filters
        status_col = cast(Any, Entity.status)
        name_col = cast(Any, Entity.name)
        display_name_col = cast(Any, Entity.display_name)
        description_col = cast(Any, Entity.description)
        entity_type_col = cast(Any, Entity.entity_type)
        parent_id_col = cast(Any, Entity.parent_id)
        entity_class_col = cast(Any, Entity.entity_class)
        filters: list[Any] = [status_col == "active"]

        if search:
            pattern = f"%{search}%"
            filters.append(
                or_(
                    name_col.ilike(pattern),
                    display_name_col.ilike(pattern),
                    description_col.ilike(pattern),
                    entity_type_col.ilike(pattern),
                )
            )
        if root_only:
            filters.append(parent_id_col.is_(None))

        if entity_class:
            try:
                ec = EntityClass(entity_class.upper())
                filters.append(entity_class_col == ec)
            except ValueError:
                filters.append(entity_class_col == entity_class)

        if entity_type:
            filters.append(entity_type_col == entity_type.lower())

        if parent_id:
            filters.append(parent_id_col == parent_id)

        scope = await _scope(session, auth_result)
        if not scope.get("is_global"):
            visible_ids = [UUID(str(entity_id)) for entity_id in scope.get("entity_ids") or []]
            if not visible_ids:
                return PaginatedResponse(items=[], total=0, page=page, limit=limit, pages=0)
            filters.append(cast(Any, Entity.id).in_(visible_ids))

        # Get total count
        count_stmt = select(func.count()).select_from(Entity).where(*filters)
        count_result = await session.execute(count_stmt)
        total = count_result.scalar() or 0

        # Calculate pagination
        skip = (page - 1) * limit
        pages = (total + limit - 1) // limit if total > 0 else 0

        # Get paginated results
        stmt = select(Entity).where(*filters).order_by(name_col).offset(skip).limit(limit)
        result = await session.execute(stmt)
        entities = result.scalars().all()

        # Convert to response format
        items = [_entity_to_response(entity) for entity in entities]

        return PaginatedResponse(items=items, total=total, page=page, limit=limit, pages=pages)

    @router.post(
        "/",
        response_model=EntityResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Create entity",
        description="Create new entity (requires entity:create permission)",
    )
    async def create_entity(
        data: EntityCreateRequest,
        auth_result=Depends(auth.require_tree_permission("entity:create", "parent_entity_id", source="body")),
        session: AsyncSession = Depends(auth.uow),
    ):
        """Create a new entity in the hierarchy."""
        from outlabs_auth.models.sql.enums import EntityClass

        # Parse entity class
        entity_class = EntityClass(data.entity_class) if isinstance(data.entity_class, str) else data.entity_class

        parent_uuid = UUID(data.parent_entity_id) if data.parent_entity_id else None
        if parent_uuid is None:
            # A new root entity is a new tenant: only global actors may create one.
            _require_global(
                await _scope(session, auth_result),
                "Only global administrators can create root entities",
            )
        else:
            await _require_entity_in_scope(session, auth_result, parent_uuid)

        entity = await auth.entity_service.create_entity(
            session=session,
            name=data.name,
            display_name=data.display_name,
            slug=data.slug,
            description=data.description,
            entity_class=entity_class,
            entity_type=data.entity_type,
            parent_id=parent_uuid,
            status=data.status or "active",
            valid_from=data.valid_from,
            valid_until=data.valid_until,
            allowed_child_classes=data.allowed_child_classes,
            allowed_child_types=data.allowed_child_types,
            max_members=data.max_members,
            child_name_pattern=data.child_name_pattern,
            child_display_name_pattern=data.child_display_name_pattern,
            child_slug_pattern=data.child_slug_pattern,
            child_naming_guidance=data.child_naming_guidance,
            created_by_id=_actor_id(auth_result),
        )
        return _entity_to_response(entity)

    @router.get(
        "/type-suggestions",
        response_model=EntityTypeSuggestionsResponse,
        summary="Get entity type suggestions",
        description="Get suggested entity types for a root scope or parent scope during entity creation",
    )
    async def get_entity_type_suggestions(
        parent_id: Optional[UUID] = Query(
            None,
            description="Parent entity ID. Omit for root-level suggestions.",
        ),
        entity_class: Optional[str] = Query(
            None,
            pattern="^(structural|access_group)$",
            description="Optional entity class filter for suggestions.",
        ),
        auth_result=Depends(auth.require_tree_permission("entity:create", "parent_id", source="query")),
        session: AsyncSession = Depends(auth.uow),
    ):
        """Return sibling-based entity type suggestions for create flows."""
        from outlabs_auth.models.sql.enums import EntityClass

        if parent_id is not None:
            await _require_entity_in_scope(session, auth_result, parent_id)

        parsed_entity_class = EntityClass(entity_class) if isinstance(entity_class, str) else entity_class
        suggestions = await auth.entity_service.get_suggested_entity_types(
            session,
            parent_id=parent_id,
            entity_class=parsed_entity_class,
        )
        return EntityTypeSuggestionsResponse.model_validate(suggestions)

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
        await _require_entity_in_scope(session, auth_result, entity_id)
        entity = await auth.entity_service.get_entity(session, entity_id)
        if not entity:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")
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
        await _require_entity_in_scope(session, auth_result, entity_id)
        updates = data.model_dump(exclude_unset=True)
        entity = await auth.entity_service.update_entity(
            session=session,
            entity_id=entity_id,
            changed_by_id=_actor_id(auth_result),
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
        auth_result=Depends(auth.require_entity_permission("entity:update", "entity_id")),
        session: AsyncSession = Depends(auth.uow),
    ):
        new_parent_id = UUID(data.new_parent_id) if data.new_parent_id else None

        scope = await _require_entity_in_scope(session, auth_result, entity_id)
        if new_parent_id is None:
            # Promoting a subtree to a top-level entity creates a new tenant.
            from outlabs_auth.models.sql.entity import Entity

            current = await session.get(Entity, entity_id)
            if current is not None and current.parent_id is not None:
                _require_global(scope, "Only global administrators can move an entity to the root level")
        elif not entity_in_scope(scope, new_parent_id):
            raise entity_not_found()

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
            moved_by_id=_actor_id(auth_result),
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
        scope = await _require_entity_in_scope(session, auth_result, entity_id)
        from outlabs_auth.models.sql.entity import Entity

        target = await session.get(Entity, entity_id)
        if target is not None and target.parent_id is None:
            # Archiving a root removes a whole tenant.
            _require_global(scope, "Only global administrators can archive a root entity")
        await auth.entity_service.delete_entity(
            session=session,
            entity_id=entity_id,
            cascade=cascade,
            deleted_by_id=UUID(auth_result["user_id"]) if auth_result.get("user_id") else None,
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
        await _require_entity_in_scope(session, auth_result, entity_id)
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
        auth_result=Depends(auth.require_tree_permission("entity:read", "entity_id")),
        session: AsyncSession = Depends(auth.uow),
    ):
        """Get all descendant entities (entire subtree)."""
        await _require_entity_in_scope(session, auth_result, entity_id)
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
        """Get the path from root to this entity.

        The ancestors of an in-scope entity are returned even when the caller's
        scope starts below them: the breadcrumb is part of the visible entity.
        """
        await _require_entity_in_scope(session, auth_result, entity_id)
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
        auth_result=Depends(auth.require_tree_permission("membership:read", "entity_id")),
        session: AsyncSession = Depends(auth.uow),
    ):
        """Get all members of an entity."""
        await _require_entity_in_scope(session, auth_result, entity_id)
        # Get memberships with user details and roles already loaded to avoid
        # one user lookup per membership row on large entities.
        memberships, total = await auth.membership_service.get_entity_members_with_users(
            session=session,
            entity_id=entity_id,
            page=page,
            limit=limit,
        )

        # Build member responses
        members = []
        for membership in memberships:
            user = membership.user
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

    return mark_auth_surface(router, "entities")
