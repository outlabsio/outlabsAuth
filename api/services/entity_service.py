"""
Entity Service
Handles entity CRUD operations and hierarchy management
"""
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple, Optional
from beanie import PydanticObjectId
from beanie.operators import In, Or, And
from fastapi import HTTPException, status

from api.models import EntityModel, EntityMembershipModel, UserModel, RoleModel
from api.models.entity_model import EntityClass
from api.schemas.entity_schema import (
    EntityCreate,
    EntityUpdate,
    EntitySearchParams
)


class EntityService:
    """Service for entity operations"""
    
    @staticmethod
    async def create_entity(
        entity_data: EntityCreate,
        created_by: UserModel
    ) -> EntityModel:
        """
        Create a new entity with hierarchy validation
        
        Args:
            entity_data: Entity creation data
            created_by: User creating the entity
        
        Returns:
            Created entity
        
        Raises:
            HTTPException: If validation fails
        """
        # Validate parent entity if provided
        parent_entity = None
        if entity_data.parent_entity_id:
            parent_entity = await EntityModel.get(entity_data.parent_entity_id, fetch_links=True)
            if not parent_entity:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Parent entity not found"
                )
            
            # Validate hierarchy rules
            await EntityService._validate_hierarchy(
                parent_entity,
                entity_data.entity_class,
                entity_data.entity_type
            )
            
            # Check for circular hierarchy (not needed for new entities, but good to have the method)
            # This is more relevant when updating parent_entity in the future
            
            # Inherit platform_id from parent
            if not entity_data.platform_id:
                entity_data.platform_id = parent_entity.platform_id
        
        
        # Check for duplicate names within same parent
        existing = await EntityModel.find_one(
            EntityModel.name == entity_data.name,
            EntityModel.parent_entity == parent_entity
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Entity with name '{entity_data.name}' already exists under this parent"
            )
        
        # Generate slug from name
        import re
        slug = re.sub(r'[^a-z0-9-]', '-', entity_data.name.lower())
        slug = re.sub(r'-+', '-', slug).strip('-')
        
        # Determine platform_id
        if parent_entity:
            # Inherit platform_id from parent
            platform_id = parent_entity.platform_id
        elif entity_data.entity_type.lower() == 'platform':
            # This is a root platform, use its own id (will be set after creation)
            platform_id = "temp_platform_id"  # Will update after save
        else:
            # For other root entities, get the first platform
            root_platform = await EntityModel.find_one({"entity_type": "platform"})
            if root_platform:
                platform_id = str(root_platform.id)
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No platform found. Please create a platform first."
                )
        
        # Create entity
        entity = EntityModel(
            name=entity_data.name,
            display_name=entity_data.display_name,
            slug=slug,
            description=entity_data.description,
            entity_class=entity_data.entity_class.lower(),  # Convert to lowercase
            entity_type=entity_data.entity_type.lower(),  # Convert to lowercase
            parent_entity=parent_entity,
            platform_id=platform_id,
            status=entity_data.status,
            metadata=entity_data.config or {}  # Use metadata instead of config
        )
        
        await entity.save()
        
        # Update platform_id for new platform entities
        if entity.entity_type == "platform" and platform_id == "temp_platform_id":
            entity.platform_id = str(entity.id)
            await entity.save()
        
        return entity
    
    @staticmethod
    async def get_entity(entity_id: str) -> EntityModel:
        """
        Get entity by ID
        
        Args:
            entity_id: Entity ID
        
        Returns:
            Entity model
        
        Raises:
            HTTPException: If entity not found
        """
        entity = await EntityModel.get(entity_id, fetch_links=True)
        if not entity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Entity not found"
            )
        return entity
    
    @staticmethod
    async def update_entity(
        entity_id: str,
        update_data: EntityUpdate,
        updated_by: UserModel
    ) -> EntityModel:
        """
        Update entity
        
        Args:
            entity_id: Entity ID
            update_data: Update data
            updated_by: User updating the entity
        
        Returns:
            Updated entity
        
        Raises:
            HTTPException: If entity not found or validation fails
        """
        entity = await EntityService.get_entity(entity_id)
        
        # Update fields using the schema - only update fields that are provided
        update_dict = update_data.model_dump(exclude_unset=True)
        
        # Update allowed fields from the schema
        for field, value in update_dict.items():
            if hasattr(entity, field):
                setattr(entity, field, value)
        
        entity.updated_at = datetime.now(timezone.utc)
        await entity.save()
        
        return entity
    
    @staticmethod
    async def delete_entity(
        entity_id: str,
        deleted_by: UserModel,
        cascade: bool = False
    ) -> bool:
        """
        Delete entity (soft delete by default)
        
        Args:
            entity_id: Entity ID
            deleted_by: User deleting the entity
            cascade: Whether to cascade delete children
        
        Returns:
            Success status
        
        Raises:
            HTTPException: If entity not found or has children
        """
        entity = await EntityService.get_entity(entity_id)
        
        # Prevent deletion of root platform
        if entity.metadata.get("is_root") or entity.slug == "root_platform":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot delete the root platform entity"
            )
        
        # Check for active children only
        children_count = await EntityModel.find(
            EntityModel.parent_entity.id == entity.id,
            EntityModel.status == "active"
        ).count()
        
        if children_count > 0 and not cascade:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete entity with children. Use cascade=true to delete all children."
            )
        
        if cascade:
            # Recursively delete active children only
            children = await EntityModel.find(
                EntityModel.parent_entity.id == entity.id,
                EntityModel.status == "active",
                fetch_links=True
            ).to_list()
            
            for child in children:
                await EntityService.delete_entity(
                    str(child.id),
                    deleted_by,
                    cascade=True
                )
        
        # Soft delete by default
        entity.status = "archived"
        entity.updated_at = datetime.now(timezone.utc)
        await entity.save()
        
        # Remove all memberships
        await EntityMembershipModel.find(
            EntityMembershipModel.entity.id == entity.id
        ).update({"$set": {"status": "revoked"}})
        
        return True
    
    @staticmethod
    async def search_entities(
        params: EntitySearchParams
    ) -> Tuple[List[EntityModel], int]:
        """
        Search entities with filtering and pagination
        
        Args:
            params: Search parameters
        
        Returns:
            Tuple of (entities, total_count)
        """
        # Build query
        query_conditions = []
        
        if params.query:
            # Text search in name, display_name, description
            import re
            pattern = re.compile(f".*{re.escape(params.query)}.*", re.IGNORECASE)
            query_conditions.append(
                Or(
                    {"name": {"$regex": pattern}},
                    {"display_name": {"$regex": pattern}},
                    {"description": {"$regex": pattern}}
                )
            )
        
        if params.entity_class:
            query_conditions.append(EntityModel.entity_class == params.entity_class)
        
        if params.entity_type:
            query_conditions.append(EntityModel.entity_type == params.entity_type)
        
        if params.status:
            query_conditions.append(EntityModel.status == params.status)
        
        if params.parent_entity_id is not None:
            # Special case: "null" string means find entities with no parent
            if params.parent_entity_id == "null":
                query_conditions.append(EntityModel.parent_entity == None)
            else:
                parent_id = PydanticObjectId(params.parent_entity_id)
                query_conditions.append(EntityModel.parent_entity.id == parent_id)
        
        if params.platform_id:
            # platform_id is stored as a string in the model
            query_conditions.append(EntityModel.platform_id == params.platform_id)
        
        # Combine conditions
        if query_conditions:
            query = EntityModel.find(And(*query_conditions), fetch_links=True)
        else:
            query = EntityModel.find_all(fetch_links=True)
        
        # Get total count
        total = await query.count()
        
        # Apply pagination
        skip = (params.page - 1) * params.page_size
        entities = await query.skip(skip).limit(params.page_size).to_list()
        
        return entities, total
    
    @staticmethod
    async def get_entity_tree(
        entity_id: str,
        max_depth: int = 10
    ) -> Dict[str, Any]:
        """
        Get entity with all its children as a tree
        
        Args:
            entity_id: Root entity ID
            max_depth: Maximum depth to traverse
        
        Returns:
            Entity tree structure
        """
        entity = await EntityService.get_entity(entity_id)
        
        async def build_tree(entity: EntityModel, depth: int = 0) -> Dict[str, Any]:
            if depth >= max_depth:
                return None
            
            # Get children
            children = await EntityModel.find(
                EntityModel.parent_entity.id == entity.id,
                EntityModel.status == "active",
                fetch_links=True
            ).to_list()
            
            # Get member count
            member_count = await EntityMembershipModel.find(
                EntityMembershipModel.entity.id == entity.id,
                EntityMembershipModel.status == "active"
            ).count()
            
            # Build tree node
            node = {
                "id": str(entity.id),
                "name": entity.name,
                "display_name": entity.display_name,
                "description": entity.description,
                "entity_class": entity.entity_class,
                "entity_type": entity.entity_type,
                "status": entity.status,
                "member_count": member_count,
                "children": []
            }
            
            # Recursively build children
            for child in children:
                child_node = await build_tree(child, depth + 1)
                if child_node:
                    node["children"].append(child_node)
            
            return node
        
        return await build_tree(entity)
    
    @staticmethod
    async def get_entity_path(entity_id: str) -> List[EntityModel]:
        """
        Get full path from root to entity
        
        Args:
            entity_id: Entity ID
        
        Returns:
            List of entities from root to current
        """
        entity = await EntityService.get_entity(entity_id)
        path = [entity]
        
        # Traverse up to root
        current = entity
        while current.parent_entity:
            # Get parent with its links populated
            parent = await EntityModel.get(current.parent_entity.id, fetch_links=True)
            if parent:
                path.insert(0, parent)
                current = parent
            else:
                break
        
        return path
    
    @staticmethod
    async def _validate_hierarchy(
        parent: EntityModel,
        child_class: str,
        child_type: str
    ) -> None:
        """
        Validate entity hierarchy rules
        
        Args:
            parent: Parent entity
            child_class: Child entity class
            child_type: Child entity type
        
        Raises:
            HTTPException: If hierarchy rules are violated
        """
        # Simplified hierarchy rules based on entity class only
        # STRUCTURAL entities can have any children
        # ACCESS_GROUP entities can only have other ACCESS_GROUP children
        
        if parent.entity_class == EntityClass.ACCESS_GROUP and child_class == "STRUCTURAL":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Access groups cannot have structural entities as children"
            )
        
        # That's it! Any other combination is allowed
        # This gives maximum flexibility while maintaining logical structure
        
        # Validate depth constraints
        path = await EntityService.get_entity_path(str(parent.id))
        if len(path) >= 10:  # Maximum depth
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum hierarchy depth (10) reached"
            )
    
    @staticmethod
    async def _check_circular_hierarchy(
        potential_parent: EntityModel,
        entity_id: Optional[str]
    ) -> None:
        """
        Check if setting a parent would create a circular hierarchy
        
        Args:
            potential_parent: The entity that would become the parent
            entity_id: The entity being updated (None for new entities)
        
        Raises:
            HTTPException: If circular hierarchy would be created
        """
        # For new entities, circular hierarchy is impossible
        if not entity_id:
            return
        
        # Walk up the parent chain from the potential parent
        current = potential_parent
        visited = set()
        
        while current:
            # Check if we've seen this entity before (loop detection)
            if str(current.id) in visited:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Circular hierarchy detected - an entity is its own ancestor"
                )
            
            visited.add(str(current.id))
            
            # Check if the potential parent is actually a descendant of the entity
            if str(current.id) == entity_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot set parent - would create circular hierarchy"
                )
            
            # Move up the chain
            if current.parent_entity:
                current = await EntityModel.get(current.parent_entity.id, fetch_links=True)
            else:
                current = None
    
    @staticmethod
    async def get_distinct_entity_types(
        platform_id: Optional[str] = None,
        entity_class: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get distinct entity types with usage counts
        
        Args:
            platform_id: Filter by platform (optional)
            entity_class: Filter by entity class (optional)
        
        Returns:
            List of entity types with counts
        """
        # Build match conditions
        match_conditions = {"status": "active"}
        
        if platform_id:
            match_conditions["platform_id"] = platform_id
        
        if entity_class:
            match_conditions["entity_class"] = entity_class.lower()
        
        # Aggregation pipeline
        pipeline = [
            {"$match": match_conditions},
            {
                "$group": {
                    "_id": "$entity_type",
                    "count": {"$sum": 1},
                    "last_used": {"$max": "$created_at"}
                }
            },
            {"$sort": {"count": -1, "last_used": -1}},
            {"$limit": 50},  # Limit to top 50 types
            {
                "$project": {
                    "entity_type": "$_id",
                    "count": 1,
                    "last_used": 1,
                    "_id": 0
                }
            }
        ]
        
        # Execute aggregation
        results = await EntityModel.aggregate(pipeline).to_list()
        
        return results
    
    @staticmethod
    async def validate_entity_access(
        entity_id: str,
        user: UserModel,
        required_permission: str = "entity:read"
    ) -> bool:
        """
        Check if user has permission on entity
        
        Args:
            entity_id: Entity ID
            user: User to check
            required_permission: Permission to check
        
        Returns:
            True if user has permission
        """
        from api.services.permission_service import permission_service
        
        # System users have full access
        if user.is_system_user:
            return True
            
        # Check permission
        has_permission, _ = await permission_service.check_permission(
            str(user.id),
            required_permission,
            entity_id
        )
        
        return has_permission
    
    @staticmethod
    async def get_user_visible_entities(
        user_id: str,
        include_tree_permissions: bool = True
    ) -> List[PydanticObjectId]:
        """
        Get all entities a user can see based on their permissions
        
        This considers:
        1. Direct membership entities
        2. Child entities of entities where user has _tree permissions
        
        Args:
            user_id: User ID
            include_tree_permissions: Whether to include entities accessible via _tree permissions
        
        Returns:
            List of entity IDs the user can see
        """
        from api.services.permission_service import permission_service
        
        visible_entity_ids = set()
        
        # Get all user memberships with entity links fetched
        memberships = await EntityMembershipModel.find(
            EntityMembershipModel.user.id == PydanticObjectId(user_id),
            EntityMembershipModel.status == "active"
        ).to_list()
        
        for membership in memberships:
            # Add direct membership entity
            if membership.entity:
                # Fetch entity if it's a link
                if hasattr(membership.entity, 'fetch'):
                    entity = await membership.entity.fetch()
                    if entity:
                        entity_id = entity.id
                    else:
                        continue
                else:
                    entity_id = membership.entity.id if hasattr(membership.entity, 'id') else membership.entity
                
                visible_entity_ids.add(entity_id)
                if include_tree_permissions:
                    # Check if user has any _tree permissions in this entity
                    tree_permissions = [
                        "entity:read_tree", "entity:update_tree", "entity:delete_tree",
                        "entity:create_tree", "user:read_tree", "user:create_tree",
                        "user:update_tree", "user:delete_tree", "role:read_tree",
                        "role:create_tree", "role:update_tree", "role:delete_tree",
                        "member:read_tree", "member:create_tree", "member:delete_tree"
                    ]
                    
                    for perm in tree_permissions:
                        try:
                            has_perm, _ = await permission_service.check_permission(
                                user_id,
                                perm,
                                str(entity_id),
                                use_cache=True  # Use cache to improve performance
                            )
                            if has_perm:
                                # User has tree permission - add all descendants
                                await EntityService._add_descendant_entities(
                                    entity_id,
                                    visible_entity_ids
                                )
                                break  # No need to check other permissions
                        except Exception:
                            # Skip on permission check error
                            continue
        
        return list(visible_entity_ids)
    
    @staticmethod
    async def _add_descendant_entities(
        parent_id: PydanticObjectId,
        entity_set: set
    ) -> None:
        """
        Recursively add all descendant entities to the set
        
        Args:
            parent_id: Parent entity ID
            entity_set: Set to add entity IDs to
        """
        # Find all children of the parent entity
        children = await EntityModel.find(
            EntityModel.parent_entity.id == parent_id,
            EntityModel.status == "active"
        ).to_list()
        
        for child in children:
            entity_set.add(child.id)
            # Recursively add descendants
            await EntityService._add_descendant_entities(child.id, entity_set)