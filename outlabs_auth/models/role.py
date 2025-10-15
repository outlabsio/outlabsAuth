"""
Role model for role-based access control
"""
from typing import Optional, List, Dict
from beanie import Link, Indexed
from pydantic import Field

from outlabs_auth.models.base import BaseDocument
from outlabs_auth.models.condition import Condition, ConditionGroup


class RoleModel(BaseDocument):
    """
    Role model for RBAC (Role-Based Access Control).

    Features:
    - Default permissions (applied in all contexts)
    - Context-aware permissions (EnterpriseRBAC only - opt-in via enable_context_aware_roles)
    - Entity scoping (for EnterpriseRBAC)
    - Global roles (assignable anywhere)
    - Type-specific assignment rules

    Library Approach Changes:
    - Removed platform_id (no multi-platform)
    - Added optional tenant_id (for multi-tenant mode)
    - Kept context-aware roles as optional feature
    """

    # Identity
    name: str = Indexed()
    display_name: str
    description: Optional[str] = None

    # Permissions (default for all contexts)
    permissions: List[str] = Field(default_factory=list)

    # Context-aware permissions (EnterpriseRBAC only - optional feature)
    # Maps entity_type -> permissions
    # Example: {"department": ["user:manage_tree"], "team": ["user:read"]}
    entity_type_permissions: Optional[Dict[str, List[str]]] = None

    # Entity scope (for EnterpriseRBAC)
    # If set, role can only be assigned within this entity and its descendants
    entity: Optional[Link["EntityModel"]] = None  # type: ignore

    # Role configuration
    is_system_role: bool = Field(default=False)  # System roles cannot be modified
    is_global: bool = Field(default=False)  # Can be assigned anywhere (SimpleRBAC + EnterpriseRBAC)

    # Type-specific assignment (EnterpriseRBAC only)
    # If set, role can only be assigned at specified entity types
    # Example: ["department", "team"] means can only assign in departments or teams
    assignable_at_types: List[str] = Field(default_factory=list)

    # ABAC Conditions (EnterpriseRBAC only - when enable_abac=True)
    # Conditions that must be met for this role's permissions to apply
    # Example: Role only applies during business hours, or when user is in same department
    conditions: List[Condition] = Field(default_factory=list)

    # Advanced ABAC: Condition groups with AND/OR logic
    # If specified, this takes precedence over simple conditions list
    condition_groups: Optional[List[ConditionGroup]] = None

    def get_permissions_for_entity_type(self, entity_type: Optional[str] = None) -> List[str]:
        """
        Get permissions for a specific entity type.

        Args:
            entity_type: Entity type (e.g., "department", "team")

        Returns:
            List of permissions for that entity type, or default permissions
        """
        # If no context-aware permissions, return default
        if not self.entity_type_permissions:
            return self.permissions

        # If entity type not specified, return default
        if not entity_type:
            return self.permissions

        # Return type-specific permissions if available, else default
        return self.entity_type_permissions.get(entity_type, self.permissions)

    def is_assignable_at_type(self, entity_type: str) -> bool:
        """
        Check if role can be assigned at a specific entity type.

        Args:
            entity_type: Entity type to check

        Returns:
            True if assignable at this type
        """
        # Global roles can be assigned anywhere
        if self.is_global:
            return True

        # If no type restrictions, allow anywhere
        if not self.assignable_at_types:
            return True

        # Check if type is in allowed list
        return entity_type in self.assignable_at_types

    class Settings:
        name = "roles"
        indexes = [
            [("name", 1)],
            [("is_global", 1)],
            [("entity", 1)],
            [("tenant_id", 1)],  # For multi-tenant filtering
        ]
