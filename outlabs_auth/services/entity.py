"""
Entity Service

Manages entity hierarchy and operations for EnterpriseRBAC.
Handles entity CRUD, hierarchy validation, and closure table maintenance.
Uses SQLAlchemy for PostgreSQL backend.
"""

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, update, and_, or_, delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import (
    EntityNotFoundError,
    InvalidInputError,
)
from outlabs_auth.models.sql.entity import Entity
from outlabs_auth.models.sql.closure import EntityClosure
from outlabs_auth.models.sql.entity_membership import EntityMembership
from outlabs_auth.models.sql.enums import EntityClass, MembershipStatus
from outlabs_auth.services.base import BaseService


class EntityService(BaseService[Entity]):
    """
    Service for entity hierarchy management.

    Features:
    - Entity CRUD operations
    - Hierarchy validation (cycles, depth, allowed types)
    - Closure table maintenance for O(1) ancestor/descendant queries
    - Path and tree traversal
    - Redis caching for paths and descendants (optional)
    """

    def __init__(
        self, config: AuthConfig, redis_client: Optional["RedisClient"] = None
    ):
        """
        Initialize EntityService.

        Args:
            config: Authentication configuration
            redis_client: Optional Redis client for caching
        """
        super().__init__(Entity)
        self.config = config
        self.max_depth = getattr(config, "max_entity_depth", 10)
        self.redis_client = redis_client

    async def create_entity(
        self,
        session: AsyncSession,
        name: str,
        display_name: str,
        entity_class: EntityClass,
        entity_type: str,
        parent_id: Optional[UUID] = None,
        description: Optional[str] = None,
        slug: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tenant_id: Optional[UUID] = None,
        **kwargs,
    ) -> Entity:
        """
        Create a new entity with hierarchy validation and closure table maintenance.

        Args:
            session: Database session
            name: System name (lowercase, underscores)
            display_name: User-friendly name
            entity_class: STRUCTURAL or ACCESS_GROUP
            entity_type: Flexible type (e.g., "organization", "department")
            parent_id: Optional parent entity ID
            description: Optional description
            slug: Optional URL-friendly identifier (auto-generated if not provided)
            metadata: Optional metadata dict
            tenant_id: Optional tenant ID for multi-tenancy
            **kwargs: Additional fields (status, valid_from, valid_until, etc.)

        Returns:
            Entity: Created entity

        Raises:
            EntityNotFoundError: If parent entity not found
            InvalidInputError: If hierarchy validation fails or entity with same slug exists
        """
        # Validate and fetch parent if provided
        parent_entity = None
        parent_depth = -1
        parent_path = None

        if parent_id:
            parent_entity = await self.get_by_id(session, parent_id)
            if not parent_entity:
                raise EntityNotFoundError(
                    message="Parent entity not found", details={"parent_id": str(parent_id)}
                )

            # Validate hierarchy rules
            await self._validate_hierarchy(session, parent_entity, entity_class, entity_type)
            parent_depth = parent_entity.depth
            parent_path = parent_entity.path

        # Generate slug if not provided
        if not slug:
            slug = self._generate_slug(name)

        # Check for duplicate slug (within tenant)
        existing = await self.get_one(
            session,
            Entity.slug == slug,
            Entity.tenant_id == tenant_id if tenant_id else True,
        )
        if existing:
            raise InvalidInputError(
                message=f"Entity with slug '{slug}' already exists",
                details={"slug": slug},
            )

        # Create entity
        entity = Entity(
            name=name.lower(),
            display_name=display_name,
            slug=slug,
            description=description,
            entity_class=entity_class,
            entity_type=entity_type.lower(),
            parent_id=parent_id,
            depth=parent_depth + 1,
            tenant_id=tenant_id,
            **kwargs,
        )

        # Set materialized path
        entity.update_path(parent_path)

        # Save entity
        session.add(entity)
        await session.flush()
        await session.refresh(entity)

        # Maintain closure table
        await self._create_closure_records(session, entity)

        return entity

    async def get_entity(self, session: AsyncSession, entity_id: UUID) -> Entity:
        """
        Get entity by ID.

        Args:
            session: Database session
            entity_id: Entity ID

        Returns:
            Entity: Entity

        Raises:
            EntityNotFoundError: If entity not found
        """
        entity = await self.get_by_id(session, entity_id)
        if not entity:
            raise EntityNotFoundError(
                message="Entity not found", details={"entity_id": str(entity_id)}
            )
        return entity

    async def get_entity_by_slug(
        self, session: AsyncSession, slug: str, tenant_id: Optional[UUID] = None
    ) -> Optional[Entity]:
        """
        Get entity by slug.

        Args:
            session: Database session
            slug: Entity slug
            tenant_id: Optional tenant ID

        Returns:
            Entity or None: Entity if found
        """
        filters = [Entity.slug == slug]
        if tenant_id:
            filters.append(Entity.tenant_id == tenant_id)
        return await self.get_one(session, *filters)

    async def update_entity(
        self, session: AsyncSession, entity_id: UUID, **updates
    ) -> Entity:
        """
        Update entity.

        Args:
            session: Database session
            entity_id: Entity ID
            **updates: Fields to update

        Returns:
            Entity: Updated entity

        Raises:
            EntityNotFoundError: If entity not found
        """
        entity = await self.get_entity(session, entity_id)

        # Update fields
        for field, value in updates.items():
            if hasattr(entity, field):
                setattr(entity, field, value)

        entity.updated_at = datetime.now(timezone.utc)
        await session.flush()
        await session.refresh(entity)

        return entity

    async def delete_entity(
        self, session: AsyncSession, entity_id: UUID, cascade: bool = False
    ) -> bool:
        """
        Delete entity (soft delete by setting status to 'archived').

        Args:
            session: Database session
            entity_id: Entity ID
            cascade: Whether to cascade delete children

        Returns:
            bool: True if deleted

        Raises:
            EntityNotFoundError: If entity not found
            InvalidInputError: If entity has children and cascade=False
        """
        entity = await self.get_entity(session, entity_id)

        # Check for children
        children_count = await self.count(
            session,
            Entity.parent_id == entity.id,
            Entity.status == "active",
        )

        if children_count > 0 and not cascade:
            raise InvalidInputError(
                message="Cannot delete entity with children. Use cascade=True to delete all children.",
                details={"entity_id": str(entity_id), "children_count": children_count},
            )

        if cascade:
            # Recursively delete children
            children = await self.get_many(
                session,
                Entity.parent_id == entity.id,
                Entity.status == "active",
            )

            for child in children:
                await self.delete_entity(session, child.id, cascade=True)

        # Soft delete
        entity.status = "archived"
        entity.updated_at = datetime.now(timezone.utc)
        await session.flush()

        # Delete closure records
        await self._delete_closure_records(session, entity)

        # Archive memberships
        stmt = (
            update(EntityMembership)
            .where(EntityMembership.entity_id == entity.id)
            .values(status=MembershipStatus.REVOKED)
        )
        await session.execute(stmt)

        return True

    async def get_entity_path(self, session: AsyncSession, entity_id: UUID) -> List[Entity]:
        """
        Get path from root to entity (ancestors in order).

        Uses closure table for O(1) performance.
        Cached in Redis if enabled.

        Args:
            session: Database session
            entity_id: Entity ID

        Returns:
            List[Entity]: Path from root to entity
        """
        # Try Redis cache first (if enabled)
        if self.redis_client and self.redis_client.is_available:
            cache_key = self.redis_client.make_entity_path_key(str(entity_id))
            cached = await self.redis_client.get(cache_key)
            if cached is not None:
                # For cached data, we need to fetch fresh entities by ID
                entity_ids = [UUID(e["id"]) for e in cached]
                entities = []
                for eid in entity_ids:
                    entity = await self.get_by_id(session, eid)
                    if entity:
                        entities.append(entity)
                return entities

        # Get all ancestors from closure table (sorted from root to entity)
        stmt = (
            select(EntityClosure)
            .where(EntityClosure.descendant_id == entity_id)
            .order_by(EntityClosure.depth.desc())  # Root first (highest depth)
        )
        result = await session.execute(stmt)
        closures = result.scalars().all()

        # Fetch entities
        entities = []
        for closure in closures:
            entity = await self.get_by_id(session, closure.ancestor_id)
            if entity:
                entities.append(entity)

        # Cache result (if Redis enabled)
        if self.redis_client and self.redis_client.is_available and entities:
            cache_key = self.redis_client.make_entity_path_key(str(entity_id))
            cache_data = [{"id": str(e.id)} for e in entities]
            await self.redis_client.set(
                cache_key, cache_data, ttl=self.config.cache_entity_ttl
            )

        return entities

    async def get_descendants(
        self, session: AsyncSession, entity_id: UUID, entity_type: Optional[str] = None
    ) -> List[Entity]:
        """
        Get all descendant entities.

        Uses closure table for O(1) performance.
        Cached in Redis if enabled.

        Args:
            session: Database session
            entity_id: Entity ID
            entity_type: Optional filter by entity_type

        Returns:
            List[Entity]: All descendants
        """
        # Try Redis cache first (if enabled and no entity_type filter)
        if self.redis_client and self.redis_client.is_available and not entity_type:
            cache_key = self.redis_client.make_entity_descendants_key(str(entity_id))
            cached = await self.redis_client.get(cache_key)
            if cached is not None:
                entity_ids = [UUID(e["id"]) for e in cached]
                entities = []
                for eid in entity_ids:
                    entity = await self.get_by_id(session, eid)
                    if entity:
                        entities.append(entity)
                return entities

        # Get all descendants from closure table (excluding self)
        stmt = (
            select(EntityClosure.descendant_id)
            .where(
                EntityClosure.ancestor_id == entity_id,
                EntityClosure.depth > 0,
            )
        )
        result = await session.execute(stmt)
        descendant_ids = [row[0] for row in result.all()]

        if not descendant_ids:
            return []

        # Fetch entities with optional type filter
        filters = [Entity.id.in_(descendant_ids)]
        if entity_type:
            filters.append(Entity.entity_type == entity_type.lower())

        entities = await self.get_many(session, *filters, limit=10000)

        # Cache result (if Redis enabled and no entity_type filter)
        if (
            self.redis_client
            and self.redis_client.is_available
            and not entity_type
            and entities
        ):
            cache_key = self.redis_client.make_entity_descendants_key(str(entity_id))
            cache_data = [{"id": str(e.id)} for e in entities]
            await self.redis_client.set(
                cache_key, cache_data, ttl=self.config.cache_entity_ttl
            )

        return entities

    async def get_children(self, session: AsyncSession, entity_id: UUID) -> List[Entity]:
        """
        Get direct children of entity.

        Args:
            session: Database session
            entity_id: Entity ID

        Returns:
            List[Entity]: Direct children
        """
        return await self.get_many(
            session,
            Entity.parent_id == entity_id,
            Entity.status == "active",
            limit=1000,
        )

    async def get_suggested_entity_types(
        self,
        session: AsyncSession,
        parent_id: Optional[UUID] = None,
        entity_class: Optional[EntityClass] = None,
    ) -> Dict[str, Any]:
        """
        Get suggested entity types based on siblings (entities with same parent).

        Helps maintain naming consistency by suggesting entity types
        that already exist at the same hierarchy level.

        Args:
            session: Database session
            parent_id: Parent entity ID (None for root level)
            entity_class: Filter by entity class (optional)

        Returns:
            Dict with suggestions, parent info, and total count
        """
        # Build filters
        filters = [Entity.status == "active"]

        if parent_id:
            filters.append(Entity.parent_id == parent_id)
        else:
            filters.append(Entity.parent_id.is_(None))

        if entity_class:
            filters.append(Entity.entity_class == entity_class)

        # Query all siblings
        entities = await self.get_many(session, *filters, limit=10000)

        # Group by entity_type
        type_counts: Dict[str, Dict[str, Any]] = {}
        for entity in entities:
            entity_type = entity.entity_type

            if entity_type not in type_counts:
                type_counts[entity_type] = {
                    "entity_type": entity_type,
                    "count": 0,
                    "examples": [],
                }

            type_counts[entity_type]["count"] += 1

            # Add up to 3 example names
            if len(type_counts[entity_type]["examples"]) < 3:
                type_counts[entity_type]["examples"].append(entity.display_name)

        # Sort by count (most common first)
        suggestions = sorted(
            type_counts.values(), key=lambda x: x["count"], reverse=True
        )

        # Get parent entity info if provided
        parent_entity_data = None
        if parent_id:
            parent_entity = await self.get_entity(session, parent_id)
            parent_entity_data = {
                "id": str(parent_entity.id),
                "name": parent_entity.name,
                "display_name": parent_entity.display_name,
                "entity_type": parent_entity.entity_type,
                "entity_class": parent_entity.entity_class.value if hasattr(parent_entity.entity_class, 'value') else parent_entity.entity_class,
            }

        return {
            "suggestions": suggestions,
            "parent_entity": parent_entity_data,
            "total_children": len(entities),
        }

    # Closure table maintenance

    async def _create_closure_records(self, session: AsyncSession, entity: Entity) -> None:
        """
        Create closure table records for new entity.

        Creates:
        - Self-reference (depth 0)
        - References to all ancestors (inherited from parent)

        Args:
            session: Database session
            entity: Newly created entity
        """
        # Create self-reference
        self_closure = EntityClosure(
            ancestor_id=entity.id,
            descendant_id=entity.id,
            depth=0,
            tenant_id=entity.tenant_id,
        )
        session.add(self_closure)

        # If has parent, copy parent's ancestors and add parent
        if entity.parent_id:
            # Get all ancestors of parent
            stmt = select(EntityClosure).where(
                EntityClosure.descendant_id == entity.parent_id
            )
            result = await session.execute(stmt)
            parent_closures = result.scalars().all()

            # Create closure records for all ancestors
            for closure in parent_closures:
                ancestor_closure = EntityClosure(
                    ancestor_id=closure.ancestor_id,
                    descendant_id=entity.id,
                    depth=closure.depth + 1,
                    tenant_id=entity.tenant_id,
                )
                session.add(ancestor_closure)

        await session.flush()

    async def _delete_closure_records(self, session: AsyncSession, entity: Entity) -> None:
        """
        Delete closure table records for entity.

        Deletes all records where entity is ancestor or descendant.

        Args:
            session: Database session
            entity: Entity being deleted
        """
        stmt = sql_delete(EntityClosure).where(
            or_(
                EntityClosure.ancestor_id == entity.id,
                EntityClosure.descendant_id == entity.id,
            )
        )
        await session.execute(stmt)

    # Validation helpers

    async def _validate_hierarchy(
        self,
        session: AsyncSession,
        parent: Entity,
        child_class: EntityClass,
        child_type: str,
    ) -> None:
        """
        Validate entity hierarchy rules.

        Rules:
        - ACCESS_GROUP cannot have STRUCTURAL children
        - Maximum depth must not be exceeded
        - Allowed child types (if configured)

        Args:
            session: Database session
            parent: Parent entity
            child_class: Child entity class
            child_type: Child entity type

        Raises:
            InvalidInputError: If validation fails
        """
        # Rule 1: ACCESS_GROUP cannot have STRUCTURAL children
        if (
            parent.entity_class == EntityClass.ACCESS_GROUP
            and child_class == EntityClass.STRUCTURAL
        ):
            raise InvalidInputError(
                message="Access groups cannot have structural entities as children",
                details={
                    "parent_class": parent.entity_class.value if hasattr(parent.entity_class, 'value') else str(parent.entity_class),
                    "child_class": child_class.value if hasattr(child_class, 'value') else str(child_class),
                },
            )

        # Rule 2: Check depth limit
        path = await self.get_entity_path(session, parent.id)
        if len(path) >= self.max_depth:
            raise InvalidInputError(
                message=f"Maximum hierarchy depth ({self.max_depth}) reached",
                details={"current_depth": len(path), "max_depth": self.max_depth},
            )

        # Rule 3: Check allowed child types (if configured)
        # Note: allowed_child_types is not in current SQL model, so skip if not present
        if hasattr(parent, 'allowed_child_types') and parent.allowed_child_types:
            if child_type.lower() not in [t.lower() for t in parent.allowed_child_types]:
                raise InvalidInputError(
                    message=f"Entity type '{child_type}' not allowed as child of '{parent.entity_type}'",
                    details={
                        "allowed_types": parent.allowed_child_types,
                        "requested_type": child_type,
                    },
                )

    def _generate_slug(self, name: str) -> str:
        """
        Generate URL-friendly slug from name.

        Args:
            name: Entity name

        Returns:
            str: URL-friendly slug
        """
        # Convert to lowercase and replace special chars with hyphens
        slug = re.sub(r"[^a-z0-9-]", "-", name.lower())
        # Remove multiple consecutive hyphens
        slug = re.sub(r"-+", "-", slug)
        # Strip leading/trailing hyphens
        return slug.strip("-")

    # Cache Management Methods

    async def invalidate_entity_cache(self, entity_id: UUID) -> int:
        """
        Invalidate cache entries for a specific entity.

        Call this when:
        - Entity is updated
        - Entity is deleted
        - Entity hierarchy changes

        Args:
            entity_id: Entity ID

        Returns:
            int: Number of cache keys deleted
        """
        if not self.redis_client or not self.redis_client.is_available:
            return 0

        deleted = 0
        entity_id_str = str(entity_id)

        # Invalidate path cache for this entity
        path_key = self.redis_client.make_entity_path_key(entity_id_str)
        if await self.redis_client.delete(path_key):
            deleted += 1

        # Invalidate descendants cache for this entity
        descendants_key = self.redis_client.make_entity_descendants_key(entity_id_str)
        if await self.redis_client.delete(descendants_key):
            deleted += 1

        # Publish invalidation event
        if deleted > 0:
            await self.redis_client.publish(
                self.config.redis_invalidation_channel, f"entity:{entity_id_str}:hierarchy"
            )

        return deleted

    async def invalidate_entity_tree_cache(self, session: AsyncSession, entity_id: UUID) -> int:
        """
        Invalidate cache for entity and all ancestors/descendants.

        Use this when hierarchy changes affect multiple entities.

        Args:
            session: Database session
            entity_id: Root entity ID

        Returns:
            int: Number of cache keys deleted
        """
        if not self.redis_client or not self.redis_client.is_available:
            return 0

        deleted = 0

        # Get all ancestors and descendants
        path = await self.get_entity_path(session, entity_id)
        descendants = await self.get_descendants(session, entity_id)
        current_entity = await self.get_by_id(session, entity_id)

        # Invalidate cache for all related entities
        all_entities = path + descendants
        if current_entity:
            all_entities.append(current_entity)

        for entity in all_entities:
            if entity:
                deleted += await self.invalidate_entity_cache(entity.id)

        return deleted

    async def invalidate_all_entity_cache(self) -> int:
        """
        Invalidate all entity cache entries.

        Use sparingly - only when major system changes occur.

        Returns:
            int: Number of cache keys deleted
        """
        if not self.redis_client or not self.redis_client.is_available:
            return 0

        pattern = self.redis_client.make_key("auth", "entity", "*")
        deleted = await self.redis_client.delete_pattern(pattern)

        # Publish invalidation event
        if deleted > 0:
            await self.redis_client.publish(
                self.config.redis_invalidation_channel, "all:entities"
            )

        return deleted

    # Helper methods for ancestor/descendant checks

    async def is_ancestor_of(
        self, session: AsyncSession, ancestor_id: UUID, descendant_id: UUID
    ) -> bool:
        """
        Check if one entity is an ancestor of another.

        Args:
            session: Database session
            ancestor_id: Potential ancestor entity ID
            descendant_id: Potential descendant entity ID

        Returns:
            bool: True if ancestor_id is an ancestor of descendant_id
        """
        stmt = select(EntityClosure).where(
            EntityClosure.ancestor_id == ancestor_id,
            EntityClosure.descendant_id == descendant_id,
            EntityClosure.depth > 0,  # Exclude self-reference
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def get_ancestors(
        self, session: AsyncSession, entity_id: UUID, include_self: bool = False
    ) -> List[Entity]:
        """
        Get all ancestor entities.

        Args:
            session: Database session
            entity_id: Entity ID
            include_self: Whether to include the entity itself

        Returns:
            List[Entity]: Ancestors ordered from immediate parent to root
        """
        min_depth = 0 if include_self else 1
        stmt = (
            select(EntityClosure.ancestor_id, EntityClosure.depth)
            .where(
                EntityClosure.descendant_id == entity_id,
                EntityClosure.depth >= min_depth,
            )
            .order_by(EntityClosure.depth.asc())  # Parent first
        )
        result = await session.execute(stmt)
        rows = result.all()

        entities = []
        for ancestor_id, _ in rows:
            entity = await self.get_by_id(session, ancestor_id)
            if entity:
                entities.append(entity)

        return entities
