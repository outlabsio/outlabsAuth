"""
Permission Service
Handles permission resolution, caching, and hierarchical checking
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Set, Tuple, Any
from beanie import PydanticObjectId
from beanie.operators import In, And
import redis
import json
import hashlib

from api.models import UserModel, EntityModel, EntityMembershipModel, RoleModel
from api.config import settings


class PermissionService:
    """Service for permission resolution and checking"""
    
    def __init__(self):
        # Redis client for caching
        self.redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        
        # Cache TTL in seconds
        self.cache_ttl = 300  # 5 minutes
        
        # Permission hierarchy definitions
        self.permission_hierarchy = {
            # System level (highest)
            "system": {
                "manage_all": ["read_all", "create_all", "update_all", "delete_all"],
                "read_all": [],
                "create_all": [],
                "update_all": [],
                "delete_all": []
            },
            # Platform level
            "platform": {
                "manage_platform": ["read_platform", "create_platform", "update_platform", "delete_platform"],
                "read_platform": [],
                "create_platform": [],
                "update_platform": [],
                "delete_platform": []
            },
            # Entity level
            "entity": {
                "manage": ["read", "create", "update", "delete"],
                "read": [],
                "create": [],
                "update": [],
                "delete": []
            },
            # User level
            "user": {
                "manage": ["read", "create", "update", "delete"],
                "read": [],
                "create": [],
                "update": [],
                "delete": []
            },
            # Role level
            "role": {
                "manage": ["read", "create", "update", "delete", "assign"],
                "read": [],
                "create": [],
                "update": [],
                "delete": [],
                "assign": []
            },
            # Member level
            "member": {
                "manage": ["read", "add", "update", "remove"],
                "read": [],
                "add": [],
                "update": [],
                "remove": []
            }
        }
    
    async def resolve_user_permissions(
        self,
        user_id: str,
        entity_id: Optional[str] = None,
        use_cache: bool = True
    ) -> Dict[str, List[str]]:
        """
        Resolve all permissions for a user in a given entity context
        
        Args:
            user_id: User ID
            entity_id: Entity context (None for global)
            use_cache: Whether to use Redis cache
        
        Returns:
            Dictionary mapping permission sources to permission lists
        """
        # Generate cache key
        cache_key = self._generate_cache_key("user_permissions", user_id, entity_id)
        
        # Try cache first
        if use_cache:
            cached = await self._get_from_cache(cache_key)
            if cached:
                return cached
        
        # Resolve permissions
        permissions = {
            "direct": [],
            "role": [],
            "inherited": [],
            "system": []
        }
        
        # Get user
        user = await UserModel.get(user_id)
        if not user:
            return permissions
        
        # System-level permissions for system users
        if user.is_system_user:
            permissions["system"] = ["*:manage_all"]
        
        # Get entity context
        entity = None
        if entity_id:
            entity = await EntityModel.get(entity_id)
            if not entity:
                return permissions
        
        # Get user memberships
        memberships = await self._get_user_memberships(user_id, entity_id)
        
        # Process each membership
        for membership in memberships:
            # Get role permissions
            role_perms = await self._get_role_permissions(membership["role_id"])
            permissions["role"].extend(role_perms)
            
            # Get inherited permissions from parent entities
            inherited_perms = await self._get_inherited_permissions(
                membership["entity_id"],
                role_perms
            )
            permissions["inherited"].extend(inherited_perms)
        
        # Get direct entity permissions
        if entity:
            permissions["direct"] = entity.direct_permissions
        
        # Expand permissions based on hierarchy
        expanded_permissions = {}
        for source, perms in permissions.items():
            expanded_permissions[source] = self._expand_permissions(perms)
        
        # Cache the result
        if use_cache:
            await self._set_cache(cache_key, expanded_permissions, self.cache_ttl)
        
        return expanded_permissions
    
    async def check_permission(
        self,
        user_id: str,
        permission: str,
        entity_id: Optional[str] = None,
        use_cache: bool = True
    ) -> Tuple[bool, str]:
        """
        Check if user has a specific permission
        
        Args:
            user_id: User ID
            permission: Permission to check (e.g., "entity:read")
            entity_id: Entity context
            use_cache: Whether to use cache
        
        Returns:
            Tuple of (has_permission, source)
        """
        # Get all user permissions
        user_permissions = await self.resolve_user_permissions(
            user_id, entity_id, use_cache
        )
        
        # Check each source
        for source, perms in user_permissions.items():
            if permission in perms or "*:manage_all" in perms:
                return True, source
        
        # Check for wildcard permissions
        resource, action = permission.split(":", 1) if ":" in permission else (permission, "")
        
        for source, perms in user_permissions.items():
            # Check for resource-level wildcards
            if f"{resource}:*" in perms:
                return True, source
            
            # Check for action-level wildcards
            if f"*:{action}" in perms:
                return True, source
        
        return False, "none"
    
    async def check_multiple_permissions(
        self,
        user_id: str,
        permissions: List[str],
        entity_id: Optional[str] = None,
        require_all: bool = True
    ) -> Dict[str, Tuple[bool, str]]:
        """
        Check multiple permissions for a user
        
        Args:
            user_id: User ID
            permissions: List of permissions to check
            entity_id: Entity context
            require_all: Whether all permissions are required
        
        Returns:
            Dictionary mapping permission to (has_permission, source)
        """
        results = {}
        
        # Get all user permissions once
        user_permissions = await self.resolve_user_permissions(user_id, entity_id)
        
        # Check each permission
        for permission in permissions:
            has_perm, source = await self.check_permission(
                user_id, permission, entity_id, use_cache=False
            )
            results[permission] = (has_perm, source)
            
            # Early exit if require_all and permission failed
            if require_all and not has_perm:
                break
        
        return results
    
    async def get_user_entities_with_permission(
        self,
        user_id: str,
        permission: str,
        entity_type: Optional[str] = None
    ) -> List[str]:
        """
        Get all entities where user has a specific permission
        
        Args:
            user_id: User ID
            permission: Permission to check
            entity_type: Filter by entity type
        
        Returns:
            List of entity IDs
        """
        # Get user memberships
        memberships = await self._get_user_memberships(user_id)
        
        entity_ids = []
        for membership in memberships:
            # Check permission in this entity
            has_perm, _ = await self.check_permission(
                user_id, permission, membership["entity_id"]
            )
            
            if has_perm:
                entity_ids.append(membership["entity_id"])
        
        # Filter by entity type if specified
        if entity_type:
            entities = await EntityModel.find(
                In(EntityModel.id, [PydanticObjectId(eid) for eid in entity_ids]),
                EntityModel.entity_type == entity_type
            ).to_list()
            entity_ids = [str(e.id) for e in entities]
        
        return entity_ids
    
    async def invalidate_user_cache(self, user_id: str) -> None:
        """
        Invalidate all cached permissions for a user
        
        Args:
            user_id: User ID
        """
        # Pattern to match all user permission cache keys
        pattern = f"perm:user_permissions:{user_id}:*"
        
        # Get all matching keys
        keys = await self.redis_client.keys(pattern)
        
        # Delete all keys
        if keys:
            await self.redis_client.delete(*keys)
    
    async def invalidate_entity_cache(self, entity_id: str) -> None:
        """
        Invalidate all cached permissions for an entity
        
        Args:
            entity_id: Entity ID
        """
        try:
            # Pattern to match all entity permission cache keys
            pattern = f"perm:*:{entity_id}"
            
            # Get all matching keys
            keys = await self.redis_client.keys(pattern)
            
            # Delete all keys
            if keys:
                await self.redis_client.delete(*keys)
        except Exception as e:
            # If Redis is unavailable, log but don't fail
            print(f"Warning: Redis cache invalidation failed: {e}")
            pass
    
    async def _get_user_memberships(
        self,
        user_id: str,
        entity_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get user's active memberships
        
        Args:
            user_id: User ID
            entity_id: Filter by entity ID
        
        Returns:
            List of membership data
        """
        # Build query
        query_conditions = [
            EntityMembershipModel.user.id == PydanticObjectId(user_id),
            EntityMembershipModel.status == "active"
        ]
        
        if entity_id:
            query_conditions.append(
                EntityMembershipModel.entity.id == PydanticObjectId(entity_id)
            )
        
        # Get memberships
        memberships = await EntityMembershipModel.find(
            And(*query_conditions)
        ).to_list()
        
        # Check time validity
        now = datetime.now(timezone.utc)
        valid_memberships = []
        
        for membership in memberships:
            # Check time validity
            if membership.valid_from and now < membership.valid_from:
                continue
            if membership.valid_until and now > membership.valid_until:
                continue
            
            valid_memberships.append({
                "id": str(membership.id),
                "entity_id": str(membership.entity.id),
                "role_id": str(membership.role.id),
                "valid_from": membership.valid_from,
                "valid_until": membership.valid_until
            })
        
        return valid_memberships
    
    async def _get_role_permissions(self, role_id: str) -> List[str]:
        """
        Get permissions for a role
        
        Args:
            role_id: Role ID
        
        Returns:
            List of permissions
        """
        role = await RoleModel.get(role_id)
        if not role:
            return []
        
        return role.permissions
    
    async def _get_inherited_permissions(
        self,
        entity_id: str,
        role_permissions: List[str]
    ) -> List[str]:
        """
        Get inherited permissions from parent entities
        
        Args:
            entity_id: Entity ID
            role_permissions: Role permissions to inherit
        
        Returns:
            List of inherited permissions
        """
        # Get entity
        entity = await EntityModel.get(entity_id)
        if not entity or not entity.parent_entity:
            return []
        
        inherited_perms = []
        
        # Get parent entity
        parent = await entity.parent_entity.fetch()
        if parent:
            # Only certain permissions inherit to children
            inheritable_perms = [
                "entity:read",
                "user:read",
                "member:read"
            ]
            
            for perm in role_permissions:
                if perm in inheritable_perms:
                    inherited_perms.append(perm)
        
        return inherited_perms
    
    def _expand_permissions(self, permissions: List[str]) -> List[str]:
        """
        Expand permissions based on hierarchy
        
        Args:
            permissions: List of permissions
        
        Returns:
            Expanded list of permissions
        """
        expanded = set(permissions)
        
        for perm in permissions:
            if ":" not in perm:
                continue
            
            resource, action = perm.split(":", 1)
            
            # Check if resource exists in hierarchy
            if resource in self.permission_hierarchy:
                resource_perms = self.permission_hierarchy[resource]
                
                # Check if action exists and has children
                if action in resource_perms:
                    child_actions = resource_perms[action]
                    for child_action in child_actions:
                        expanded.add(f"{resource}:{child_action}")
        
        return list(expanded)
    
    def _generate_cache_key(
        self,
        key_type: str,
        user_id: str,
        entity_id: Optional[str] = None
    ) -> str:
        """
        Generate cache key for permissions
        
        Args:
            key_type: Type of cache key
            user_id: User ID
            entity_id: Entity ID
        
        Returns:
            Cache key
        """
        key_parts = ["perm", key_type, user_id]
        if entity_id:
            key_parts.append(entity_id)
        
        return ":".join(key_parts)
    
    async def _get_from_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get data from Redis cache
        
        Args:
            key: Cache key
        
        Returns:
            Cached data or None
        """
        try:
            data = await self.redis_client.get(key)
            if data:
                return json.loads(data)
        except Exception:
            # Cache miss or error
            pass
        
        return None
    
    async def _set_cache(
        self,
        key: str,
        data: Dict[str, Any],
        ttl: int
    ) -> None:
        """
        Set data in Redis cache
        
        Args:
            key: Cache key
            data: Data to cache
            ttl: Time to live in seconds
        """
        try:
            await self.redis_client.setex(
                key,
                ttl,
                json.dumps(data, default=str)
            )
        except Exception:
            # Cache write error - non-critical
            pass


# Global permission service instance
permission_service = PermissionService()