"""
Entity Service
Handles entity CRUD operations and hierarchy management
"""
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple
from beanie import PydanticObjectId
from beanie.operators import In, Or, And
from fastapi import HTTPException, status

from api.models import EntityModel, EntityMembershipModel, UserModel, RoleModel
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
        
        # Update fields
        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
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
            query_conditions.append(
                Or(
                    EntityModel.name.regex(f".*{params.query}.*", "i"),
                    EntityModel.display_name.regex(f".*{params.query}.*", "i"),
                    EntityModel.description.regex(f".*{params.query}.*", "i")
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
            platform_id = PydanticObjectId(params.platform_id)
            query_conditions.append(EntityModel.platform_id == platform_id)
        
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
        # Define hierarchy rules
        hierarchy_rules = {
            "platform": ["organization", "access_group"],
            "organization": ["branch", "team", "access_group"],
            "branch": ["team", "access_group"],
            "team": ["access_group"],
            "access_group": ["access_group"]  # Access groups can be nested
        }
        
        # Check if parent type allows this child type
        allowed_children = hierarchy_rules.get(parent.entity_type, [])
        
        if child_class == "STRUCTURAL":
            if child_type not in allowed_children:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"A {parent.entity_type} cannot have a {child_type} as a child"
                )
        elif child_class == "ACCESS_GROUP":
            if "access_group" not in allowed_children:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"A {parent.entity_type} cannot have access groups as children"
                )
        
        # Validate depth constraints
        path = await EntityService.get_entity_path(str(parent.id))
        if len(path) >= 10:  # Maximum depth
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum hierarchy depth (10) reached"
            )
    
    @staticmethod
    async def validate_entity_access(
        entity_id: str,
        user: UserModel
    ) -> bool:
        """
        Check if user has permission on entity
        
        Args:
            entity_id: Entity ID
            user: User to check
            required_permission: Permission to check
        
        Returns:
            True if user has permission
        
        Note: This is a placeholder - full implementation will come with permission service
        """
        # TODO: Implement with permission service
        # For now, just check if user is a member
        membership = await EntityMembershipModel.find_one(
            EntityMembershipModel.entity.id == PydanticObjectId(entity_id),
            EntityMembershipModel.user.id == user.id,
            EntityMembershipModel.status == "active"
        )
        
        return membership is not None