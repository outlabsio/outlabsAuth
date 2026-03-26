"""
Entity Service

Manages entity hierarchy and operations for EnterpriseRBAC.
Handles entity CRUD, hierarchy validation, and closure table maintenance.
Uses SQLAlchemy for PostgreSQL backend.
"""

import re
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from uuid import UUID

if TYPE_CHECKING:
    from outlabs_auth.observability import ObservabilityService
    from outlabs_auth.services.api_key import APIKeyService
    from outlabs_auth.services.config import ConfigService
    from outlabs_auth.services.membership import MembershipService
    from outlabs_auth.services.redis_client import RedisClient
    from outlabs_auth.services.role import RoleService

from sqlalchemy import and_, insert, or_, select
from sqlalchemy import delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import (
    EntityNotFoundError,
    InvalidInputError,
)
from outlabs_auth.models.sql.closure import EntityClosure
from outlabs_auth.models.sql.entity import Entity
from outlabs_auth.models.sql.enums import EntityClass
from outlabs_auth.services.base import BaseService

ROOT_NAMING_PATTERN_FIELDS = (
    "child_name_pattern",
    "child_display_name_pattern",
    "child_slug_pattern",
)
ROOT_ONLY_GOVERNANCE_FIELDS = ROOT_NAMING_PATTERN_FIELDS + ("child_naming_guidance",)


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
        self,
        config: AuthConfig,
        redis_client: Optional["RedisClient"] = None,
        observability: Optional["ObservabilityService"] = None,
        config_service: Optional["ConfigService"] = None,
    ):
        """
        Initialize EntityService.

        Args:
            config: Authentication configuration
            redis_client: Optional Redis client for caching
            observability: Optional observability service for metrics/logging
            config_service: Optional config service for entity type configuration
        """
        super().__init__(Entity)
        self.config = config
        self.max_depth = getattr(config, "max_entity_depth", 10)
        self.redis_client = redis_client
        self.observability = observability
        self.config_service = config_service
        self.membership_service: Optional["MembershipService"] = None
        self.role_service: Optional["RoleService"] = None
        self.api_key_service: Optional["APIKeyService"] = None

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
            **kwargs: Additional fields (status, valid_from, valid_until, etc.)

        Returns:
            Entity: Created entity

        Raises:
            EntityNotFoundError: If parent entity not found
            InvalidInputError: If hierarchy validation fails or entity with same slug exists
        """
        start_time = time.perf_counter()
        normalized_name = name.lower()
        normalized_entity_type = entity_type.lower()
        normalized_kwargs = dict(kwargs)
        self._normalize_root_governance_values(normalized_kwargs)

        # Generate slug before validation so descendant naming rules can inspect it.
        if not slug:
            slug = self._generate_slug(name)

        # Validate and fetch parent if provided
        parent_entity = None
        parent_depth = -1
        parent_path = None

        if parent_id:
            if self._has_root_governance_values(normalized_kwargs):
                raise InvalidInputError(
                    message="Root naming governance can only be configured on root entities",
                    details={"fields": list(ROOT_ONLY_GOVERNANCE_FIELDS)},
                )

            parent_entity = await self.get_by_id(session, parent_id)
            if not parent_entity:
                raise EntityNotFoundError(
                    message="Parent entity not found",
                    details={"parent_id": str(parent_id)},
                )

            # Validate hierarchy rules
            await self._validate_hierarchy(
                session,
                parent_entity,
                entity_class,
                normalized_entity_type,
            )
            await self._validate_root_naming_rules(
                session,
                parent_entity,
                name=normalized_name,
                display_name=display_name,
                slug=slug,
            )
            parent_depth = parent_entity.depth
            parent_path = parent_entity.path
        else:
            await self._validate_root_entity_type(
                session,
                entity_class=entity_class,
                entity_type=normalized_entity_type,
            )
            self._validate_root_governance_values(normalized_kwargs)

        # Check for duplicate slug.
        existing = await self.get_one(
            session,
            Entity.slug == slug,
        )
        if existing:
            raise InvalidInputError(
                message=f"Entity with slug '{slug}' already exists",
                details={"slug": slug},
            )

        # Create entity
        entity = Entity(
            name=normalized_name,
            display_name=display_name,
            slug=slug,
            description=description,
            entity_class=entity_class,
            entity_type=normalized_entity_type,
            parent_id=parent_id,
            depth=parent_depth + 1,
            **normalized_kwargs,
        )

        # Set materialized path
        entity.update_path(parent_path)

        # Save entity
        session.add(entity)
        await session.flush()
        await session.refresh(entity)

        # Maintain closure table
        await self._create_closure_records(session, entity)

        # Log observability
        if self.observability:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.observability.log_entity_operation(
                operation="create",
                entity_id=str(entity.id),
                entity_type=entity_type,
                duration_ms=duration_ms,
                parent_id=str(parent_id) if parent_id else None,
            )

        await self._invalidate_permission_cache(entity.id)
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
            raise EntityNotFoundError(message="Entity not found", details={"entity_id": str(entity_id)})
        return entity

    async def get_entity_by_slug(self, session: AsyncSession, slug: str) -> Optional[Entity]:
        """
        Get entity by slug.

        Args:
            session: Database session
            slug: Entity slug
        Returns:
            Entity or None: Entity if found
        """
        return await self.get_one(session, Entity.slug == slug)

    async def update_entity(self, session: AsyncSession, entity_id: UUID, **updates) -> Entity:
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
        start_time = time.perf_counter()

        entity = await self.get_entity(session, entity_id)
        normalized_updates = dict(updates)
        self._normalize_root_governance_values(normalized_updates)

        if entity.parent_id is not None and self._has_root_governance_values(normalized_updates):
            raise InvalidInputError(
                message="Root naming governance can only be configured on root entities",
                details={"entity_id": str(entity_id), "fields": list(ROOT_ONLY_GOVERNANCE_FIELDS)},
            )

        if entity.parent_id is None:
            self._validate_root_governance_values(normalized_updates)
        elif "display_name" in normalized_updates and normalized_updates["display_name"] is not None:
            parent_entity = await self.get_entity(session, entity.parent_id)
            await self._validate_root_naming_rules(
                session,
                parent_entity,
                name=entity.name,
                display_name=normalized_updates["display_name"],
                slug=entity.slug,
            )

        # Update fields
        for field, value in normalized_updates.items():
            if hasattr(entity, field):
                setattr(entity, field, value)

        await session.flush()
        await session.refresh(entity)

        # Log observability
        if self.observability:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.observability.log_entity_operation(
                operation="update",
                entity_id=str(entity.id),
                entity_type=entity.entity_type,
                duration_ms=duration_ms,
            )

        await self._invalidate_permission_cache(entity.id)
        return entity

    async def move_entity(
        self,
        session: AsyncSession,
        entity_id: UUID,
        new_parent_id: Optional[UUID],
    ) -> Entity:
        """
        Move (re-parent) an entity to a new parent.

        This updates:
        - `entities.parent_id`
        - `entities.depth` and materialized `entities.path` for the entire subtree
        - `entity_closure` rows so ancestor/descendant queries stay correct

        Args:
            session: Database session
            entity_id: Entity being moved (root of subtree)
            new_parent_id: New parent entity ID, or None to move to root

        Raises:
            EntityNotFoundError: If entity or new parent does not exist
            InvalidInputError: If move would create a cycle or violates hierarchy rules
        """
        start_time = time.perf_counter()

        entity = await self.get_entity(session, entity_id)

        if new_parent_id == entity.parent_id:
            return entity

        if new_parent_id == entity.id:
            raise InvalidInputError(
                message="Entity cannot be its own parent",
                details={"entity_id": str(entity_id)},
            )

        new_parent: Optional[Entity] = None
        if new_parent_id is not None:
            new_parent = await self.get_by_id(session, new_parent_id)
            if not new_parent:
                raise EntityNotFoundError(
                    message="Parent entity not found",
                    details={"parent_id": str(new_parent_id)},
                )

            # Prevent cycles: cannot move under own descendant.
            if await self.is_ancestor_of(session, ancestor_id=entity.id, descendant_id=new_parent.id):
                raise InvalidInputError(
                    message="Cannot move entity under its own descendant",
                    details={
                        "entity_id": str(entity_id),
                        "new_parent_id": str(new_parent_id),
                    },
                )

            # Validate hierarchy rules as if `entity` were created under new_parent.
            await self._validate_hierarchy(
                session,
                parent=new_parent,
                child_class=entity.entity_class,
                child_type=entity.entity_type,
            )

        # Fetch subtree (descendants including self) and their depths-from-root via closure.
        subtree_stmt = (
            select(Entity, EntityClosure.depth)
            .join(EntityClosure, EntityClosure.descendant_id == Entity.id)
            .where(EntityClosure.ancestor_id == entity.id)
            .order_by(EntityClosure.depth.asc())
        )
        subtree_result = await session.execute(subtree_stmt)
        subtree_rows = subtree_result.all()
        if not subtree_rows:
            raise InvalidInputError(
                message="Closure table missing subtree records for entity",
                details={"entity_id": str(entity_id)},
            )

        subtree_depth_by_id: dict[UUID, int] = {row[0].id: row[1] for row in subtree_rows}
        subtree_entities: list[Entity] = [row[0] for row in subtree_rows]
        subtree_ids = list(subtree_depth_by_id.keys())

        # Determine old/new root path prefixes for safe path rebuild.
        old_root_path = (entity.path or "").strip() or None
        if old_root_path and not old_root_path.endswith("/"):
            old_root_path = old_root_path + "/"

        new_parent_path = (new_parent.path if new_parent else None) if new_parent_id else None
        if new_parent_path and not new_parent_path.endswith("/"):
            new_parent_path = new_parent_path + "/"

        new_root_path = f"/{entity.slug}/" if not new_parent_path else f"{new_parent_path}{entity.slug}/"

        # Update entity parent pointer early (so fallbacks can read it if needed).
        entity.parent_id = new_parent_id

        # Update depth + path for entire subtree.
        new_root_depth = (new_parent.depth + 1) if new_parent else 0
        entities_by_id: dict[UUID, Entity] = {e.id: e for e in subtree_entities}

        for node in subtree_entities:
            rel_depth = subtree_depth_by_id.get(node.id, 0)
            node.depth = new_root_depth + rel_depth

            # Fast path: prefix replacement when old paths are consistent.
            if old_root_path and node.path and node.path.startswith(old_root_path):
                suffix = node.path[len(old_root_path) :]
                node.path = f"{new_root_path}{suffix}"
                continue

            # Fallback: rebuild from (updated) parent pointers in depth order.
            if node.id == entity.id:
                node.path = new_root_path
                continue

            parent = entities_by_id.get(node.parent_id) if node.parent_id else None
            parent_path = parent.path if parent else None
            node.update_path(parent_path)

        await session.flush()

        # Closure maintenance:
        # 1) Remove links from old ancestors (outside subtree) to moved subtree.
        delete_stmt = sql_delete(EntityClosure).where(
            EntityClosure.descendant_id.in_(subtree_ids),
            EntityClosure.ancestor_id.notin_(subtree_ids),
        )
        await session.execute(delete_stmt)

        # 2) Insert links from new ancestors (outside subtree) to moved subtree.
        if new_parent is not None:
            ancestors_stmt = select(EntityClosure.ancestor_id, EntityClosure.depth).where(
                EntityClosure.descendant_id == new_parent.id
            )
            ancestors_result = await session.execute(ancestors_stmt)
            ancestor_rows = ancestors_result.all()  # (ancestor_id, depth_to_parent)

            rows_to_insert: list[dict[str, object]] = []
            for ancestor_id, depth_to_parent in ancestor_rows:
                for descendant_id, depth_from_root in subtree_depth_by_id.items():
                    rows_to_insert.append(
                        {
                            "ancestor_id": ancestor_id,
                            "descendant_id": descendant_id,
                            "depth": int(depth_to_parent) + 1 + int(depth_from_root),
                        }
                    )

            if rows_to_insert:
                await session.execute(insert(EntityClosure).values(rows_to_insert))

        await session.flush()

        # Invalidate caches affected by this move.
        await self.invalidate_entity_tree_cache(session, entity.id)

        await session.refresh(entity)

        # Log observability
        if self.observability:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.observability.log_entity_operation(
                operation="move",
                entity_id=str(entity.id),
                entity_type=entity.entity_type,
                duration_ms=duration_ms,
                parent_id=str(new_parent_id) if new_parent_id else None,
            )

        await self._invalidate_permission_cache(entity.id)
        return entity

    async def delete_entity(
        self,
        session: AsyncSession,
        entity_id: UUID,
        cascade: bool = False,
        deleted_by_id: Optional[UUID] = None,
    ) -> bool:
        """
        Delete entity (soft delete by setting status to 'archived').

        Args:
            session: Database session
            entity_id: Entity ID
            cascade: Whether to cascade delete children
            deleted_by_id: Optional actor performing the archive

        Returns:
            bool: True if deleted

        Raises:
            EntityNotFoundError: If entity not found
            InvalidInputError: If entity has children and cascade=False
        """
        start_time = time.perf_counter()

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
                await self.delete_entity(
                    session,
                    child.id,
                    cascade=True,
                    deleted_by_id=deleted_by_id,
                )

        # Soft delete
        entity.status = "archived"
        await session.flush()

        archive_reason = f"Entity '{entity.display_name}' archived"

        if self.membership_service is not None:
            await self.membership_service.archive_memberships_for_entity(
                session,
                entity.id,
                revoked_by_id=deleted_by_id,
                reason=archive_reason,
                event_source="entity_service.delete_entity",
            )

        if self.role_service is not None:
            await self.role_service.revoke_memberships_for_archived_entities(
                session,
                [entity.id],
                revoked_by_id=deleted_by_id,
                reason=archive_reason,
            )

        if self.api_key_service is not None:
            await self.api_key_service.revoke_entity_api_keys(
                session,
                entity.id,
                revoked_by_id=deleted_by_id,
                reason=archive_reason,
                event_source="entity_service.delete_entity",
            )

        # Delete closure records
        await self._delete_closure_records(session, entity)

        # Log observability
        if self.observability:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.observability.log_entity_operation(
                operation="delete",
                entity_id=str(entity_id),
                entity_type=entity.entity_type,
                duration_ms=duration_ms,
                cascade=cascade,
            )

        await self._invalidate_permission_cache(entity_id)
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
            await self.redis_client.set(cache_key, cache_data, ttl=self.config.cache_entity_ttl)

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
        stmt = select(EntityClosure.descendant_id).where(
            EntityClosure.ancestor_id == entity_id,
            EntityClosure.depth > 0,
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
        if self.redis_client and self.redis_client.is_available and not entity_type and entities:
            cache_key = self.redis_client.make_entity_descendants_key(str(entity_id))
            cache_data = [{"id": str(e.id)} for e in entities]
            await self.redis_client.set(cache_key, cache_data, ttl=self.config.cache_entity_ttl)

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
        suggestions = sorted(type_counts.values(), key=lambda x: x["count"], reverse=True)

        # Get parent entity info if provided
        parent_entity_data = None
        if parent_id:
            parent_entity = await self.get_entity(session, parent_id)
            parent_entity_data = {
                "id": str(parent_entity.id),
                "name": parent_entity.name,
                "display_name": parent_entity.display_name,
                "entity_type": parent_entity.entity_type,
                "entity_class": (
                    parent_entity.entity_class.value
                    if hasattr(parent_entity.entity_class, "value")
                    else parent_entity.entity_class
                ),
            }

        return {
            "suggestions": suggestions,
            "parent_entity": parent_entity_data,
            "total_children": len(entities),
        }

    async def _validate_root_entity_type(
        self,
        session: AsyncSession,
        *,
        entity_class: EntityClass,
        entity_type: str,
    ) -> None:
        """
        Validate configured root entity type restrictions.
        """
        if self.config_service is None:
            return

        config = await self.config_service.get_entity_type_config(session)
        root_type_config = getattr(config.allowed_root_types, entity_class.value, [])
        allowed_root_types = [value.strip().lower() for value in root_type_config if value and value.strip()]

        if not allowed_root_types:
            class_label = entity_class.value.replace("_", "-")
            raise InvalidInputError(
                message=f"No {class_label} root entity types are configured",
                details={"entity_class": entity_class.value},
            )

        if entity_type.lower() not in allowed_root_types:
            class_label = entity_class.value.replace("_", "-")
            raise InvalidInputError(
                message=f"Entity type '{entity_type}' is not allowed for {class_label} root entities",
                details={
                    "entity_class": entity_class.value,
                    "allowed_root_types": allowed_root_types,
                    "requested_type": entity_type,
                },
            )

    def _normalize_root_governance_values(self, payload: Dict[str, Any]) -> None:
        """Normalize optional root-governance strings to trimmed values or None."""
        for field in ROOT_ONLY_GOVERNANCE_FIELDS:
            if field not in payload:
                continue

            value = payload[field]
            if value is None:
                continue

            if isinstance(value, str):
                trimmed_value = value.strip()
                payload[field] = trimmed_value or None

    def _has_root_governance_values(self, payload: Dict[str, Any]) -> bool:
        """Check whether a payload includes any populated root-only governance values."""
        return any(payload.get(field) is not None for field in ROOT_ONLY_GOVERNANCE_FIELDS)

    def _validate_root_governance_values(self, payload: Dict[str, Any]) -> None:
        """Ensure configured regex patterns are valid before persisting them."""
        for field in ROOT_NAMING_PATTERN_FIELDS:
            pattern = payload.get(field)
            if not pattern:
                continue

            try:
                re.compile(pattern)
            except re.error as exc:
                raise InvalidInputError(
                    message=f"{field.replace('_', ' ')} must be a valid regular expression",
                    details={"field": field, "pattern": pattern, "error": str(exc)},
                ) from exc

    async def _validate_root_naming_rules(
        self,
        session: AsyncSession,
        parent: Entity,
        *,
        name: str,
        display_name: str,
        slug: str,
    ) -> None:
        """Validate descendant naming against the root entity's configured rules."""
        root_entity = await self._get_root_entity(session, parent)
        if not root_entity:
            return

        values_to_validate = (
            ("child_name_pattern", name, "system name"),
            ("child_display_name_pattern", display_name, "display name"),
            ("child_slug_pattern", slug, "slug"),
        )

        for field, value, label in values_to_validate:
            pattern = getattr(root_entity, field, None)
            if not pattern:
                continue

            if re.fullmatch(pattern, value) is None:
                raise InvalidInputError(
                    message=f"{label} '{value}' does not match the root naming rule",
                    details={
                        "field": label,
                        "pattern": pattern,
                        "root_entity_id": str(root_entity.id),
                        "root_entity_name": root_entity.display_name,
                    },
                )

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
        )
        session.add(self_closure)

        # If has parent, copy parent's ancestors and add parent
        if entity.parent_id:
            # Get all ancestors of parent
            stmt = select(EntityClosure).where(EntityClosure.descendant_id == entity.parent_id)
            result = await session.execute(stmt)
            parent_closures = result.scalars().all()

            # Create closure records for all ancestors
            for closure in parent_closures:
                ancestor_closure = EntityClosure(
                    ancestor_id=closure.ancestor_id,
                    descendant_id=entity.id,
                    depth=closure.depth + 1,
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
        - Allowed child types (from root entity config or system defaults)

        Args:
            session: Database session
            parent: Parent entity
            child_class: Child entity class
            child_type: Child entity type

        Raises:
            InvalidInputError: If validation fails
        """
        # Rule 1: ACCESS_GROUP cannot have STRUCTURAL children
        if parent.entity_class == EntityClass.ACCESS_GROUP and child_class == EntityClass.STRUCTURAL:
            raise InvalidInputError(
                message="Access groups cannot have structural entities as children",
                details={
                    "parent_class": (
                        parent.entity_class.value if hasattr(parent.entity_class, "value") else str(parent.entity_class)
                    ),
                    "child_class": child_class.value if hasattr(child_class, "value") else str(child_class),
                },
            )

        # Rule 2: Check depth limit
        path = await self.get_entity_path(session, parent.id)
        if len(path) >= self.max_depth:
            raise InvalidInputError(
                message=f"Maximum hierarchy depth ({self.max_depth}) reached",
                details={"current_depth": len(path), "max_depth": self.max_depth},
            )

        # Rule 3: Check allowed child types
        # Priority: parent's allowed_child_types > root entity's allowed_child_types > system defaults
        allowed_types = await self._get_allowed_child_types(session, parent, child_class)

        if allowed_types:
            if child_type.lower() not in [t.lower() for t in allowed_types]:
                raise InvalidInputError(
                    message=f"Entity type '{child_type}' not allowed as child of '{parent.entity_type}'",
                    details={
                        "allowed_types": allowed_types,
                        "requested_type": child_type,
                    },
                )

    async def _get_allowed_child_types(
        self,
        session: AsyncSession,
        parent: Entity,
        child_class: EntityClass,
    ) -> list[str]:
        """
        Get allowed child types for a parent entity.

        Priority:
        1. Parent entity's allowed_child_types (if configured)
        2. Root entity's allowed_child_types (if configured)
        3. System defaults from ConfigService

        Args:
            session: Database session
            parent: Parent entity
            child_class: Child entity class (structural or access_group)

        Returns:
            List of allowed entity type strings
        """
        # Check if parent has explicit allowed_child_types
        if hasattr(parent, "allowed_child_types") and parent.allowed_child_types:
            return parent.allowed_child_types

        # Get root entity to check its allowed_child_types
        root_entity = await self._get_root_entity(session, parent)
        if root_entity and hasattr(root_entity, "allowed_child_types") and root_entity.allowed_child_types:
            return root_entity.allowed_child_types

        # No restrictions if neither parent nor root has explicit allowed_child_types
        # System defaults are suggestions for the UI, not hard enforcement
        # This allows flexibility while still providing guidance in the frontend
        return []

    async def _get_root_entity(
        self,
        session: AsyncSession,
        entity: Entity,
    ) -> Optional[Entity]:
        """
        Get the root entity (top of hierarchy) for a given entity.

        Args:
            session: Database session
            entity: Entity to find root for

        Returns:
            Root entity (entity with no parent) or None
        """
        if entity.parent_id is None:
            # This entity is already a root
            return entity

        # Use closure table to find the root (ancestor with depth = max depth from this entity)
        path = await self.get_entity_path(session, entity.id)
        if path:
            # First entity in path is the root
            return path[0]

        return None

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
                self.config.redis_invalidation_channel,
                f"entity:{entity_id_str}:hierarchy",
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
            await self.redis_client.publish(self.config.redis_invalidation_channel, "all:entities")

        return deleted

    # Helper methods for ancestor/descendant checks

    async def is_ancestor_of(self, session: AsyncSession, ancestor_id: UUID, descendant_id: UUID) -> bool:
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

    async def _invalidate_permission_cache(self, entity_id: UUID) -> None:
        cache_service = getattr(self, "cache_service", None)
        if cache_service is None:
            return
        await cache_service.publish_entity_permissions_invalidation(str(entity_id))
        await cache_service.publish_all_permissions_invalidation()

    async def get_ancestors(self, session: AsyncSession, entity_id: UUID, include_self: bool = False) -> List[Entity]:
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
