"""
Entity Service

Manages entity hierarchy and operations for EnterpriseRBAC.
Handles entity CRUD, hierarchy validation, and closure table maintenance.
"""

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import (
    EntityNotFoundError,
    InvalidInputError,
)
from outlabs_auth.models.closure import EntityClosureModel
from outlabs_auth.models.entity import EntityClass, EntityModel
from outlabs_auth.models.membership import EntityMembershipModel


class EntityService:
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
        self.config = config
        self.max_depth = getattr(config, "max_entity_depth", 10)
        self.redis_client = redis_client

    async def create_entity(
        self,
        name: str,
        display_name: str,
        entity_class: EntityClass,
        entity_type: str,
        parent_id: Optional[str] = None,
        description: Optional[str] = None,
        slug: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> EntityModel:
        """
        Create a new entity with hierarchy validation and closure table maintenance.

        Args:
            name: System name (lowercase, underscores)
            display_name: User-friendly name
            entity_class: STRUCTURAL or ACCESS_GROUP
            entity_type: Flexible type (e.g., "organization", "department")
            parent_id: Optional parent entity ID
            description: Optional description
            slug: Optional URL-friendly identifier (auto-generated if not provided)
            metadata: Optional metadata dict
            **kwargs: Additional fields (status, valid_from, valid_until, etc.)

        Returns:
            EntityModel: Created entity

        Raises:
            EntityNotFoundError: If parent entity not found
            InvalidInputError: If hierarchy validation fails or entity with same slug exists

        Example:
            >>> entity = await entity_service.create_entity(
            ...     name="engineering",
            ...     display_name="Engineering Department",
            ...     entity_class=EntityClass.STRUCTURAL,
            ...     entity_type="department",
            ...     parent_id=org_id
            ... )
        """
        # Validate and fetch parent if provided
        parent_entity = None
        if parent_id:
            parent_entity = await EntityModel.get(parent_id)
            if not parent_entity:
                raise EntityNotFoundError(
                    message="Parent entity not found", details={"parent_id": parent_id}
                )

            # Validate hierarchy rules
            await self._validate_hierarchy(parent_entity, entity_class, entity_type)

        # Generate slug if not provided
        if not slug:
            slug = self._generate_slug(name)

        # Check for duplicate slug
        existing = await EntityModel.find_one(EntityModel.slug == slug)
        if existing:
            raise InvalidInputError(
                message=f"Entity with slug '{slug}' already exists",
                details={"slug": slug},
            )

        # Create entity
        entity = EntityModel(
            name=name.lower(),
            display_name=display_name,
            slug=slug,
            description=description,
            entity_class=entity_class,
            entity_type=entity_type.lower(),
            parent_entity=parent_entity,
            metadata=metadata or {},
            **kwargs,
        )

        await entity.save()

        # Maintain closure table
        await self._create_closure_records(entity)

        return entity

    async def get_entity(self, entity_id: str) -> EntityModel:
        """
        Get entity by ID.

        Args:
            entity_id: Entity ID

        Returns:
            EntityModel: Entity

        Raises:
            EntityNotFoundError: If entity not found

        Example:
            >>> entity = await entity_service.get_entity(entity_id)
        """
        entity = await EntityModel.get(entity_id)
        if not entity:
            raise EntityNotFoundError(
                message="Entity not found", details={"entity_id": entity_id}
            )
        return entity

    async def get_entity_by_slug(self, slug: str) -> Optional[EntityModel]:
        """
        Get entity by slug.

        Args:
            slug: Entity slug

        Returns:
            EntityModel or None: Entity if found

        Example:
            >>> entity = await entity_service.get_entity_by_slug("engineering-dept")
        """
        return await EntityModel.find_one(EntityModel.slug == slug)

    async def update_entity(self, entity_id: str, **updates) -> EntityModel:
        """
        Update entity.

        Args:
            entity_id: Entity ID
            **updates: Fields to update

        Returns:
            EntityModel: Updated entity

        Raises:
            EntityNotFoundError: If entity not found

        Example:
            >>> entity = await entity_service.update_entity(
            ...     entity_id,
            ...     display_name="New Name",
            ...     description="Updated description"
            ... )
        """
        entity = await self.get_entity(entity_id)

        # Update fields
        for field, value in updates.items():
            if hasattr(entity, field):
                setattr(entity, field, value)

        entity.updated_at = datetime.now(timezone.utc)
        await entity.save()

        return entity

    async def delete_entity(self, entity_id: str, cascade: bool = False) -> bool:
        """
        Delete entity (soft delete by setting status to 'archived').

        Args:
            entity_id: Entity ID
            cascade: Whether to cascade delete children

        Returns:
            bool: True if deleted

        Raises:
            EntityNotFoundError: If entity not found
            InvalidInputError: If entity has children and cascade=False

        Example:
            >>> await entity_service.delete_entity(entity_id, cascade=True)
        """
        entity = await self.get_entity(entity_id)

        # Check for children
        children_count = await EntityModel.find(
            EntityModel.parent_entity.id == entity.id, EntityModel.status == "active"
        ).count()

        if children_count > 0 and not cascade:
            raise InvalidInputError(
                message="Cannot delete entity with children. Use cascade=True to delete all children.",
                details={"entity_id": entity_id, "children_count": children_count},
            )

        if cascade:
            # Recursively delete children
            children = await EntityModel.find(
                EntityModel.parent_entity.id == entity.id,
                EntityModel.status == "active",
            ).to_list()

            for child in children:
                await self.delete_entity(str(child.id), cascade=True)

        # Soft delete
        entity.status = "archived"
        entity.updated_at = datetime.now(timezone.utc)
        await entity.save()

        # Delete closure records
        await self._delete_closure_records(entity)

        # Archive memberships
        await EntityMembershipModel.find(
            EntityMembershipModel.entity.id == entity.id
        ).update_many({"$set": {"is_active": False}})

        return True

    async def get_entity_path(self, entity_id: str) -> List[EntityModel]:
        """
        Get path from root to entity (ancestors in order).

        Uses closure table for O(1) performance.
        Cached in Redis if enabled.

        Args:
            entity_id: Entity ID

        Returns:
            List[EntityModel]: Path from root to entity

        Example:
            >>> path = await entity_service.get_entity_path(team_id)
            >>> # Returns: [Platform, Org, Dept, Team]
        """
        # Try Redis cache first (if enabled)
        if self.redis_client and self.redis_client.is_available:
            cache_key = self.redis_client.make_entity_path_key(entity_id)
            cached = await self.redis_client.get(cache_key)
            if cached is not None:
                # Reconstruct entity models from cached data
                entities = []
                for entity_data in cached:
                    entity = EntityModel(**entity_data)
                    entities.append(entity)
                return entities

        # Get all ancestors from closure table (sorted from root to entity)
        closures = (
            await EntityClosureModel.find(EntityClosureModel.descendant_id == entity_id)
            .sort([("depth", -1)])
            .to_list()
        )  # Sort by depth DESC (root first)

        # Fetch entities
        entity_ids = [closure.ancestor_id for closure in closures]
        entities = []

        for eid in entity_ids:
            entity = await EntityModel.get(eid)
            if entity:
                entities.append(entity)

        # Cache result (if Redis enabled)
        if self.redis_client and self.redis_client.is_available and entities:
            cache_key = self.redis_client.make_entity_path_key(entity_id)
            # Serialize entities for caching
            cache_data = [entity.model_dump(mode="json") for entity in entities]
            await self.redis_client.set(
                cache_key, cache_data, ttl=self.config.cache_entity_ttl
            )

        return entities

    async def get_descendants(
        self, entity_id: str, entity_type: Optional[str] = None
    ) -> List[EntityModel]:
        """
        Get all descendant entities.

        Uses closure table for O(1) performance.
        Cached in Redis if enabled.

        Args:
            entity_id: Entity ID
            entity_type: Optional filter by entity_type

        Returns:
            List[EntityModel]: All descendants

        Example:
            >>> descendants = await entity_service.get_descendants(org_id)
            >>> # Returns all entities under the organization
        """
        # Try Redis cache first (if enabled and no entity_type filter)
        if self.redis_client and self.redis_client.is_available and not entity_type:
            cache_key = self.redis_client.make_entity_descendants_key(entity_id)
            cached = await self.redis_client.get(cache_key)
            if cached is not None:
                # Reconstruct entity models from cached data
                entities = []
                for entity_data in cached:
                    entity = EntityModel(**entity_data)
                    entities.append(entity)
                return entities

        # Get all descendants from closure table (excluding self)
        closures = await EntityClosureModel.find(
            EntityClosureModel.ancestor_id == entity_id, EntityClosureModel.depth > 0
        ).to_list()

        # Fetch entities
        from bson import ObjectId

        # Convert string IDs to ObjectIds for querying
        entity_ids = [ObjectId(closure.descendant_id) for closure in closures]

        # Build query
        if entity_type:
            entities = await EntityModel.find(
                {"_id": {"$in": entity_ids}, "entity_type": entity_type.lower()}
            ).to_list()
        else:
            entities = await EntityModel.find({"_id": {"$in": entity_ids}}).to_list()

        # Cache result (if Redis enabled and no entity_type filter)
        if (
            self.redis_client
            and self.redis_client.is_available
            and not entity_type
            and entities
        ):
            cache_key = self.redis_client.make_entity_descendants_key(entity_id)
            # Serialize entities for caching
            cache_data = [entity.model_dump(mode="json") for entity in entities]
            await self.redis_client.set(
                cache_key, cache_data, ttl=self.config.cache_entity_ttl
            )

        return entities

    async def get_children(self, entity_id: str) -> List[EntityModel]:
        """
        Get direct children of entity.

        Args:
            entity_id: Entity ID

        Returns:
            List[EntityModel]: Direct children

        Example:
            >>> children = await entity_service.get_children(dept_id)
        """
        from bson import ObjectId

        # Query by parent_entity.$id (DBRef syntax)
        return await EntityModel.find(
            {"parent_entity.$id": ObjectId(entity_id), "status": "active"}
        ).to_list()

    async def get_suggested_entity_types(
        self,
        parent_id: Optional[str] = None,
        entity_class: Optional[EntityClass] = None,
    ) -> Dict[str, Any]:
        """
        Get suggested entity types based on siblings (entities with same parent).

        Helps maintain naming consistency by suggesting entity types
        that already exist at the same hierarchy level.

        Args:
            parent_id: Parent entity ID (None for root level)
            entity_class: Filter by entity class (optional)

        Returns:
            Dict with suggestions, parent info, and total count:
            {
                "suggestions": [
                    {
                        "entity_type": "brokerage",
                        "count": 5,
                        "examples": ["RE/MAX Downtown", "Century 21 West", ...]
                    },
                    ...
                ],
                "parent_entity": {...} or None,
                "total_children": 17
            }

        Example:
            >>> # Get suggestions for creating entity under RE/MAX California
            >>> suggestions = await entity_service.get_suggested_entity_types(
            ...     parent_id=remax_california_id
            ... )
            >>> # Returns: [{"entity_type": "brokerage", "count": 15, ...}, ...]
        """
        # Build query for siblings (same parent)
        query = {}

        if parent_id:
            # Find entities with this parent
            parent_entity = await self.get_entity(parent_id)
            query["parent_entity.$id"] = parent_id
        else:
            # Find root-level entities (no parent)
            query["parent_entity"] = None

        # Filter by entity_class if provided
        if entity_class:
            query["entity_class"] = entity_class.value

        # Filter only active entities
        query["status"] = "active"

        # Query all siblings
        entities = await EntityModel.find(query).to_list()

        # Group by entity_type
        type_counts = {}
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
            parent_entity = await self.get_entity(parent_id)
            parent_entity_data = {
                "id": str(parent_entity.id),
                "name": parent_entity.name,
                "display_name": parent_entity.display_name,
                "entity_type": parent_entity.entity_type,
                "entity_class": parent_entity.entity_class.value,
            }

        return {
            "suggestions": suggestions,
            "parent_entity": parent_entity_data,
            "total_children": len(entities),
        }

    # Closure table maintenance

    async def _create_closure_records(self, entity: EntityModel) -> None:
        """
        Create closure table records for new entity.

        Creates:
        - Self-reference (depth 0)
        - References to all ancestors (inherited from parent)

        Args:
            entity: Newly created entity
        """
        # Create self-reference
        await EntityClosureModel(
            ancestor_id=str(entity.id),
            descendant_id=str(entity.id),
            depth=0,
            tenant_id=entity.tenant_id,
        ).insert()

        # If has parent, copy parent's ancestors and add parent
        if entity.parent_entity:
            parent_id = str(entity.parent_entity.id)

            # Get all ancestors of parent
            parent_closures = await EntityClosureModel.find(
                EntityClosureModel.descendant_id == parent_id
            ).to_list()

            # Create closure records for all ancestors
            for closure in parent_closures:
                await EntityClosureModel(
                    ancestor_id=closure.ancestor_id,
                    descendant_id=str(entity.id),
                    depth=closure.depth + 1,
                    tenant_id=entity.tenant_id,
                ).insert()

    async def _delete_closure_records(self, entity: EntityModel) -> None:
        """
        Delete closure table records for entity.

        Deletes all records where entity is ancestor or descendant.

        Args:
            entity: Entity being deleted
        """
        entity_id = str(entity.id)

        # Delete records where entity is ancestor or descendant
        await EntityClosureModel.find(
            {"$or": [{"ancestor_id": entity_id}, {"descendant_id": entity_id}]}
        ).delete()

    # Validation helpers

    async def _validate_hierarchy(
        self, parent: EntityModel, child_class: EntityClass, child_type: str
    ) -> None:
        """
        Validate entity hierarchy rules.

        Rules:
        - ACCESS_GROUP cannot have STRUCTURAL children
        - Maximum depth must not be exceeded
        - Allowed child types (if configured)

        Args:
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
                    "parent_class": parent.entity_class,
                    "child_class": child_class,
                },
            )

        # Rule 2: Check depth limit
        path = await self.get_entity_path(str(parent.id))
        if len(path) >= self.max_depth:
            raise InvalidInputError(
                message=f"Maximum hierarchy depth ({self.max_depth}) reached",
                details={"current_depth": len(path), "max_depth": self.max_depth},
            )

        # Rule 3: Check allowed child types (if configured)
        if parent.allowed_child_types and child_type.lower() not in [
            t.lower() for t in parent.allowed_child_types
        ]:
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

        Example:
            >>> self._generate_slug("Engineering Department")
            'engineering-department'
        """
        # Convert to lowercase and replace special chars with hyphens
        slug = re.sub(r"[^a-z0-9-]", "-", name.lower())
        # Remove multiple consecutive hyphens
        slug = re.sub(r"-+", "-", slug)
        # Strip leading/trailing hyphens
        return slug.strip("-")

    # Cache Management Methods

    async def invalidate_entity_cache(self, entity_id: str) -> int:
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

        Example:
            >>> deleted = await entity_service.invalidate_entity_cache(entity_id)
        """
        if not self.redis_client or not self.redis_client.is_available:
            return 0

        deleted = 0

        # Invalidate path cache for this entity
        path_key = self.redis_client.make_entity_path_key(entity_id)
        if await self.redis_client.delete(path_key):
            deleted += 1

        # Invalidate descendants cache for this entity
        descendants_key = self.redis_client.make_entity_descendants_key(entity_id)
        if await self.redis_client.delete(descendants_key):
            deleted += 1

        # Publish invalidation event
        if deleted > 0:
            await self.redis_client.publish(
                self.config.redis_invalidation_channel, f"entity:{entity_id}:hierarchy"
            )

        return deleted

    async def invalidate_entity_tree_cache(self, entity_id: str) -> int:
        """
        Invalidate cache for entity and all ancestors/descendants.

        Use this when hierarchy changes affect multiple entities.

        Args:
            entity_id: Root entity ID

        Returns:
            int: Number of cache keys deleted

        Example:
            >>> deleted = await entity_service.invalidate_entity_tree_cache(entity_id)
        """
        if not self.redis_client or not self.redis_client.is_available:
            return 0

        deleted = 0

        # Get all ancestors and descendants
        path = await self.get_entity_path(entity_id)
        descendants = await self.get_descendants(entity_id)

        # Invalidate cache for all related entities
        all_entities = path + descendants + [await EntityModel.get(entity_id)]

        for entity in all_entities:
            if entity:
                deleted += await self.invalidate_entity_cache(str(entity.id))

        return deleted

    async def invalidate_all_entity_cache(self) -> int:
        """
        Invalidate all entity cache entries.

        Use sparingly - only when major system changes occur.

        Returns:
            int: Number of cache keys deleted

        Example:
            >>> deleted = await entity_service.invalidate_all_entity_cache()
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
