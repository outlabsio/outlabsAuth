"""
Permission Service
Handles permission resolution, caching, hierarchical checking, and ABAC policy evaluation
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Set, Tuple, Any, Union
from beanie import PydanticObjectId
from beanie.operators import In, And
import redis
import json
import hashlib
import re
from enum import Enum

from api.models import UserModel, EntityModel, EntityMembershipModel, RoleModel
from api.models.permission_model import PermissionModel, Condition
from api.config import settings


class PolicyResult:
    """Result of policy evaluation"""
    def __init__(self, allowed: bool, reason: str = "", details: Optional[Dict[str, Any]] = None):
        self.allowed = allowed
        self.reason = reason
        self.details = details or {}


class PolicyEvaluationEngine:
    """
    Engine for evaluating ABAC policies and conditions
    Supports attribute-based access control with dynamic evaluation
    """
    
    def __init__(self):
        self.redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        self.policy_cache_ttl = 60  # 1 minute for policy results
    
    async def evaluate_permission(
        self,
        user: UserModel,
        permission_name: str,
        entity: Optional[EntityModel] = None,
        resource_attributes: Optional[Dict[str, Any]] = None,
        use_cache: bool = True
    ) -> PolicyResult:
        """
        Evaluate a permission request with ABAC conditions
        
        Args:
            user: User requesting access
            permission_name: Permission name (e.g., "invoice:approve")
            entity: Entity context
            resource_attributes: Attributes of the resource being accessed
            use_cache: Whether to use cache for policy results
        
        Returns:
            PolicyResult with allowed status and reason
        """
        # Generate cache key for this specific evaluation
        cache_key = self._generate_policy_cache_key(
            user.id, permission_name, entity.id if entity else None, resource_attributes
        )
        
        # Check cache first
        if use_cache:
            cached_result = await self._get_cached_policy_result(cache_key)
            if cached_result:
                return cached_result
        
        # Check if it's a system permission first
        from api.services.permission_management_service import PermissionManagementService
        if permission_name in PermissionManagementService.SYSTEM_PERMISSIONS:
            # System permissions have no conditions - pure RBAC
            return PolicyResult(True, "No conditions to evaluate")
        
        # Get the permission definition
        permission = await self._get_permission_definition(permission_name, entity.id if entity else None)
        if not permission:
            return PolicyResult(False, f"Permission '{permission_name}' not found")
        
        # If permission has no conditions, it's a simple RBAC check (handled elsewhere)
        if not permission.conditions:
            return PolicyResult(True, "No conditions to evaluate")
        
        # Build evaluation context
        context = await self._build_evaluation_context(user, entity, resource_attributes)
        
        # Evaluate all conditions (AND logic)
        evaluation_details = []
        for condition in permission.conditions:
            result = await self._evaluate_condition(condition, context)
            evaluation_details.append({
                "attribute": condition.attribute,
                "operator": condition.operator,
                "expected": condition.value,
                "actual": result.get("actual_value"),
                "passed": result["passed"],
                "reason": result.get("reason", "")
            })
            
            # If any condition fails, deny access
            if not result["passed"]:
                return PolicyResult(
                    False,
                    f"Condition failed: {condition.attribute} {condition.operator} {condition.value}",
                    {"evaluations": evaluation_details}
                )
        
        # All conditions passed
        result = PolicyResult(
            True,
            "All conditions passed",
            {"evaluations": evaluation_details}
        )
        
        # Cache the result
        if use_cache:
            await self._cache_policy_result(cache_key, result)
        
        return result
    
    async def _build_evaluation_context(
        self,
        user: UserModel,
        entity: Optional[EntityModel],
        resource_attributes: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build the evaluation context with all available attributes"""
        context = {
            "user": {
                "id": str(user.id),
                "email": user.email,
                "status": user.status.value,
                "can_authenticate": user.can_authenticate(),
                "email_verified": user.email_verified,
                "is_system_user": user.is_system_user,
                "created_at": user.created_at.isoformat() if user.created_at else None,
            },
            "resource": resource_attributes or {},
            "entity": {},
            "environment": {
                "time": datetime.now(timezone.utc).isoformat(),
                "day_of_week": datetime.now(timezone.utc).strftime("%A").lower(),
                "hour": datetime.now(timezone.utc).hour,
            }
        }
        
        # Add user profile attributes if available
        if user.profile:
            context["user"].update({
                "department": user.profile.department,
                "team": user.profile.team,
                "location": user.profile.location,
                "manager_id": user.profile.manager_id,
            })
            # Add any custom attributes from profile metadata
            if user.profile.metadata:
                for key, value in user.profile.metadata.items():
                    if key not in context["user"]:
                        context["user"][key] = value
        
        # Add entity attributes if available
        if entity:
            context["entity"] = {
                "id": str(entity.id),
                "name": entity.name,
                "type": entity.entity_type,
                "status": entity.status,
                "member_count": getattr(entity, 'member_count', 0),
            }
            # Add entity settings/metadata
            if entity.settings:
                context["entity"]["settings"] = entity.settings
        
        return context
    
    async def _evaluate_condition(
        self,
        condition: Condition,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Evaluate a single condition against the context"""
        # Extract the attribute value from context
        attribute_value = self._extract_attribute_value(condition.attribute, context)
        
        # Handle EXISTS/NOT_EXISTS operators
        if condition.operator == "EXISTS":
            return {
                "passed": attribute_value is not None,
                "actual_value": attribute_value,
                "reason": f"Attribute {'exists' if attribute_value is not None else 'does not exist'}"
            }
        
        if condition.operator == "NOT_EXISTS":
            return {
                "passed": attribute_value is None,
                "actual_value": attribute_value,
                "reason": f"Attribute {'does not exist' if attribute_value is None else 'exists'}"
            }
        
        # If attribute doesn't exist and it's not an existence check, fail
        if attribute_value is None:
            return {
                "passed": False,
                "actual_value": None,
                "reason": f"Attribute '{condition.attribute}' not found in context"
            }
        
        # Evaluate based on operator
        try:
            passed = self._evaluate_operator(
                attribute_value,
                condition.operator,
                condition.value
            )
            return {
                "passed": passed,
                "actual_value": attribute_value,
                "reason": "Condition evaluation successful"
            }
        except Exception as e:
            return {
                "passed": False,
                "actual_value": attribute_value,
                "reason": f"Evaluation error: {str(e)}"
            }
    
    def _extract_attribute_value(self, attribute_path: str, context: Dict[str, Any]) -> Any:
        """Extract attribute value from context using dot notation"""
        parts = attribute_path.split('.')
        value = context
        
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return None
        
        return value
    
    def _evaluate_operator(self, actual_value: Any, operator: str, expected_value: Any) -> bool:
        """Evaluate the operator comparison"""
        # Type conversion for numeric comparisons
        if operator in ["LESS_THAN", "LESS_THAN_OR_EQUAL", "GREATER_THAN", "GREATER_THAN_OR_EQUAL"]:
            try:
                actual_value = float(actual_value)
                expected_value = float(expected_value)
            except (TypeError, ValueError):
                return False
        
        # Operator evaluation
        if operator == "EQUALS":
            return str(actual_value).lower() == str(expected_value).lower()
        
        elif operator == "NOT_EQUALS":
            return str(actual_value).lower() != str(expected_value).lower()
        
        elif operator == "LESS_THAN":
            return actual_value < expected_value
        
        elif operator == "LESS_THAN_OR_EQUAL":
            return actual_value <= expected_value
        
        elif operator == "GREATER_THAN":
            return actual_value > expected_value
        
        elif operator == "GREATER_THAN_OR_EQUAL":
            return actual_value >= expected_value
        
        elif operator == "IN":
            if isinstance(expected_value, list):
                return actual_value in expected_value
            return False
        
        elif operator == "NOT_IN":
            if isinstance(expected_value, list):
                return actual_value not in expected_value
            return True
        
        elif operator == "CONTAINS":
            if isinstance(actual_value, (list, str)):
                return expected_value in actual_value
            return False
        
        elif operator == "NOT_CONTAINS":
            if isinstance(actual_value, (list, str)):
                return expected_value not in actual_value
            return True
        
        elif operator == "STARTS_WITH":
            return str(actual_value).startswith(str(expected_value))
        
        elif operator == "ENDS_WITH":
            return str(actual_value).endswith(str(expected_value))
        
        elif operator == "REGEX_MATCH":
            try:
                return bool(re.match(str(expected_value), str(actual_value)))
            except re.error:
                return False
        
        return False
    
    async def _get_permission_definition(
        self,
        permission_name: str,
        entity_id: Optional[str] = None
    ) -> Optional[PermissionModel]:
        """Get permission definition from database"""
        # First try entity-specific permission
        if entity_id:
            permission = await PermissionModel.find_one(
                PermissionModel.name == permission_name,
                PermissionModel.entity_id == PydanticObjectId(entity_id),
                PermissionModel.is_active == True
            )
            if permission:
                return permission
        
        # Fall back to system-level permission
        permission = await PermissionModel.find_one(
            PermissionModel.name == permission_name,
            PermissionModel.entity_id == None,
            PermissionModel.is_system == True,
            PermissionModel.is_active == True
        )
        
        return permission
    
    def _generate_policy_cache_key(
        self,
        user_id: str,
        permission: str,
        entity_id: Optional[str],
        resource_attributes: Optional[Dict[str, Any]]
    ) -> str:
        """Generate cache key for policy evaluation result"""
        # Create a deterministic hash of resource attributes
        attr_hash = ""
        if resource_attributes:
            # Sort keys for consistency
            sorted_attrs = json.dumps(resource_attributes, sort_keys=True)
            attr_hash = hashlib.md5(sorted_attrs.encode()).hexdigest()[:8]
        
        parts = ["policy", str(user_id), permission]
        if entity_id:
            parts.append(str(entity_id))
        if attr_hash:
            parts.append(attr_hash)
        
        return ":".join(parts)
    
    async def _get_cached_policy_result(self, cache_key: str) -> Optional[PolicyResult]:
        """Get cached policy result"""
        try:
            data = await self.redis_client.get(cache_key)
            if data:
                result_data = json.loads(data)
                return PolicyResult(
                    allowed=result_data["allowed"],
                    reason=result_data.get("reason", ""),
                    details=result_data.get("details", {})
                )
        except Exception:
            pass
        return None
    
    async def _cache_policy_result(self, cache_key: str, result: PolicyResult) -> None:
        """Cache policy result"""
        try:
            data = {
                "allowed": result.allowed,
                "reason": result.reason,
                "details": result.details
            }
            await self.redis_client.setex(
                cache_key,
                self.policy_cache_ttl,
                json.dumps(data)
            )
        except Exception:
            pass


class PermissionService:
    """Service for permission resolution and checking"""
    
    def __init__(self):
        # Redis client for caching
        self.redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        
        # Cache TTL in seconds
        self.cache_ttl = 300  # 5 minutes
        
        # Policy evaluation engine for ABAC
        self.policy_engine = PolicyEvaluationEngine()
        
        # Permission hierarchy definitions - removed all compound "manage" permissions
        # Now each permission stands on its own without automatic expansion
        self.permission_hierarchy = {}
    
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
            permissions["system"] = ["*"]
        
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
            # Get role permissions - now handling multiple roles per membership
            all_role_perms = []
            for role_id in membership.get("role_ids", []):
                role_perms = await self._get_role_permissions(role_id)
                permissions["role"].extend(role_perms)
                all_role_perms.extend(role_perms)
            
            # Get inherited permissions from parent entities
            inherited_perms = await self._get_inherited_permissions(
                membership["entity_id"],
                all_role_perms  # Pass all permissions from all roles
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
        
        Handles three permission scoping levels:
        1. Entity-specific: resource:action (only in specific entity)
        2. Hierarchical: resource:action_tree (in entity and descendants)
        3. Platform-wide: resource:action_all (across entire platform)
        
        Args:
            user_id: User ID
            permission: Permission to check (e.g., "entity:read")
            entity_id: Entity context
            use_cache: Whether to use cache
        
        Returns:
            Tuple of (has_permission, source)
        """
        # Parse permission components
        if ":" not in permission:
            resource, action = permission, ""
        else:
            resource, action = permission.split(":", 1)
        
        # Check direct permission at target entity
        user_permissions = await self.resolve_user_permissions(
            user_id, entity_id, use_cache
        )
        
        # Check each source for exact permission
        for source, perms in user_permissions.items():
            if permission in perms or "*" in perms:
                return True, source
        
        # Check for _all permissions (platform-wide)
        all_permission = f"{resource}:{action}_all"
        for source, perms in user_permissions.items():
            if all_permission in perms:
                return True, source
        
        # Check for _tree permissions in parent entities
        if entity_id and not action.endswith("_tree") and not action.endswith("_all"):
            # Get parent entities
            from api.services.entity_service import EntityService
            entity_path = await EntityService.get_entity_path(entity_id)
            
            
            # Check each parent for _tree permission
            tree_permission = f"{resource}:{action}_tree"
            
            
            # entity_path[:-1] gets all entities except the last one (the target entity)
            for i, parent_entity in enumerate(entity_path[:-1], 1):  # Check all parents
                
                parent_permissions = await self.resolve_user_permissions(
                    user_id, str(parent_entity.id), use_cache
                )
                
                
                for source, perms in parent_permissions.items():
                    if tree_permission in perms:
                        return True, f"{source}_tree"
        
        # Check for wildcard permissions
        for source, perms in user_permissions.items():
            # Check for resource-level wildcards
            if f"{resource}:*" in perms:
                return True, source
            
            # Check for action-level wildcards
            if f"*:{action}" in perms:
                return True, source
        
        return False, "none"
    
    async def check_permission_with_context(
        self,
        user_id: str,
        permission: str,
        entity_id: Optional[str] = None,
        resource_attributes: Optional[Dict[str, Any]] = None,
        use_cache: bool = True
    ) -> PolicyResult:
        """
        Check permission with full hybrid RBAC + ABAC evaluation
        
        This is the main entry point for permission checking that combines:
        1. Traditional RBAC (role-based) checks
        2. ReBAC (relationship-based) checks through entity hierarchy
        3. ABAC (attribute-based) condition evaluation
        
        Args:
            user_id: User ID
            permission: Permission to check (e.g., "invoice:approve")
            entity_id: Entity context
            resource_attributes: Attributes of the resource being accessed
            use_cache: Whether to use cache
        
        Returns:
            PolicyResult with allowed status, reason, and evaluation details
        """
        # Step 1: Traditional RBAC check
        has_permission, source = await self.check_permission(
            user_id, permission, entity_id, use_cache
        )
        
        # If no basic permission, deny immediately
        if not has_permission:
            return PolicyResult(
                False, 
                f"User lacks basic permission '{permission}'",
                {"rbac_check": False, "source": source}
            )
        
        # Step 2: Get user and entity for ABAC evaluation
        user = await UserModel.get(user_id)
        if not user:
            return PolicyResult(False, "User not found")
        
        entity = None
        if entity_id:
            entity = await EntityModel.get(entity_id)
            if not entity:
                return PolicyResult(False, "Entity not found")
        
        # Step 3: ABAC evaluation if permission has conditions
        policy_result = await self.policy_engine.evaluate_permission(
            user, permission, entity, resource_attributes, use_cache
        )
        
        # If no conditions, permission is granted based on RBAC alone
        if policy_result.reason == "No conditions to evaluate":
            return PolicyResult(
                True,
                "Permission granted (RBAC only)",
                {"rbac_check": True, "source": source, "abac_check": "not_required"}
            )
        
        # Add RBAC info to the policy result
        policy_result.details["rbac_check"] = True
        policy_result.details["rbac_source"] = source
        
        return policy_result
    
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
            EntityMembershipModel.is_active == True
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
            
            # Handle entity and roles - they might be Link objects
            entity_id = None
            if hasattr(membership.entity, 'id'):
                entity_id = str(membership.entity.id)
            elif hasattr(membership.entity, 'ref'):
                entity_id = str(membership.entity.ref.id)
            
            # Extract role IDs from the list of roles/links
            role_ids = []
            if membership.roles:
                for role in membership.roles:
                    if hasattr(role, 'id'):
                        role_ids.append(str(role.id))
                    elif hasattr(role, 'ref'):
                        # It's a Link object
                        role_ids.append(str(role.ref.id))
            
            if entity_id:
                valid_memberships.append({
                    "id": str(membership.id),
                    "entity_id": entity_id,
                    "role_ids": role_ids,
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
        
        Since we removed compound "manage" permissions, this now just returns
        the permissions as-is without any expansion.
        
        Args:
            permissions: List of permissions
        
        Returns:
            Same list of permissions (no expansion)
        """
        # No longer expanding permissions since we removed compound permissions
        return permissions
    
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