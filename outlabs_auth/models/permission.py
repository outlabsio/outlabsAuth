"""
Permission model for RBAC and ABAC (optional)
"""
from typing import Optional, List, Dict, Any
from pydantic import Field, field_validator
from beanie import Indexed

from outlabs_auth.models.base import BaseDocument
from outlabs_auth.models.condition import Condition, ConditionGroup


class PermissionModel(BaseDocument):
    """
    Permission model for custom business-specific permissions.

    Permission Naming Convention:
    - Format: resource:action or resource:action_scope
    - Examples:
      - "user:create" - Create users
      - "user:read" - Read users
      - "user:create_tree" - Create users in descendant entities (EnterpriseRBAC)
      - "invoice:approve" - Approve invoices
      - "report:generate_all" - Generate reports platform-wide

    Library Approach Changes:
    - Removed platform-specific fields
    - Added optional tenant_id for multi-tenant mode
    - ABAC conditions are optional (EnterpriseRBAC with enable_abac=True)
    """

    # Permission identifier (e.g., "user:create", "invoice:approve")
    name: str = Indexed()

    # Human-readable name (e.g., "Create Users", "Approve Invoices")
    display_name: str

    # Detailed description of what this permission allows
    description: Optional[str] = None

    # Resource this permission applies to (auto-derived from name)
    resource: Optional[str] = None

    # Action allowed on the resource (auto-derived from name)
    action: Optional[str] = None

    # Optional scope modifier (e.g., "tree", "all") - auto-derived from action
    scope: Optional[str] = None

    # Whether this is a system permission (built-in) or custom
    is_system: bool = Field(default=False)

    # Whether this permission is active
    is_active: bool = Field(default=True)

    # Tags for categorizing permissions (e.g., ["finance", "reporting"])
    tags: List[str] = Field(default_factory=list)

    # ABAC Conditions (EnterpriseRBAC only - when enable_abac=True)
    # Simple list: All conditions must evaluate to true (AND logic)
    # For complex logic (OR/nested), use condition_groups instead
    conditions: List[Condition] = Field(default_factory=list)

    # Advanced ABAC: Condition groups with AND/OR logic
    # If specified, this takes precedence over simple conditions list
    condition_groups: Optional[List[ConditionGroup]] = None

    # Additional metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('name')
    @classmethod
    def validate_name_format(cls, v: str) -> str:
        """Validate permission name follows resource:action format"""
        if ':' not in v:
            raise ValueError("Permission name must follow 'resource:action' format")

        parts = v.split(':')
        if len(parts) != 2:
            raise ValueError("Permission name must have exactly one colon")

        resource, action = parts
        if not resource or not action:
            raise ValueError("Both resource and action must be non-empty")

        # Validate characters (alphanumeric, underscore, hyphen, or asterisk for wildcard)
        import re
        if resource != '*' and not re.match(r'^[a-zA-Z0-9_-]+$', resource):
            raise ValueError("Resource must contain only letters, numbers, underscores, hyphens, or asterisk")
        if action != '*' and not re.match(r'^[a-zA-Z0-9_-]+$', action):
            raise ValueError("Action must contain only letters, numbers, underscores, hyphens, or asterisk")

        return v.lower()  # Normalize to lowercase

    def model_post_init(self, __context):
        """Auto-populate resource/action/scope from name"""
        if self.name and ':' in self.name:
            parts = self.name.split(':')

            # Set resource
            if not self.resource:
                self.resource = parts[0]

            # Set action and scope
            if not self.action and len(parts) > 1:
                full_action = parts[1]
                self.action = full_action

                # Extract scope if present (e.g., "create_tree" -> action="create", scope="tree")
                if '_' in full_action and not self.scope:
                    action_parts = full_action.rsplit('_', 1)
                    if len(action_parts) == 2 and action_parts[1] in ['tree', 'all']:
                        self.action = action_parts[0]
                        self.scope = action_parts[1]

    class Settings:
        name = "permissions"
        indexes = [
            [("name", 1)],
            [("resource", 1)],
            [("is_system", 1)],
            [("is_active", 1)],
            [("tenant_id", 1)],  # For multi-tenant filtering
        ]
