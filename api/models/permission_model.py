"""
Permission Model
Defines custom permissions that can be created by organizations
Supports ABAC (Attribute-Based Access Control) through conditional permissions
"""
from typing import Optional, List, Dict, Any, Union
from pydantic import Field, field_validator, BaseModel
from beanie import PydanticObjectId

from api.models.base_model import BaseDocument


class Condition(BaseModel):
    """
    Represents a single condition for ABAC evaluation
    Conditions are evaluated against user, resource, entity, and environment attributes
    """
    # The attribute to check using dot notation (e.g., "user.department", "resource.value")
    attribute: str = Field(..., min_length=1, max_length=200)
    
    # The comparison operator
    operator: str = Field(..., pattern="^(EQUALS|NOT_EQUALS|LESS_THAN|LESS_THAN_OR_EQUAL|GREATER_THAN|GREATER_THAN_OR_EQUAL|IN|NOT_IN|CONTAINS|NOT_CONTAINS|STARTS_WITH|ENDS_WITH|REGEX_MATCH|EXISTS|NOT_EXISTS)$")
    
    # The value to compare against (can be static value or dynamic reference)
    value: Union[str, int, float, bool, List[Any], Dict[str, Any]] = Field(...)
    
    @field_validator('attribute')
    @classmethod
    def validate_attribute_path(cls, v: str) -> str:
        """Validate attribute path format"""
        # Must start with valid prefix
        valid_prefixes = ['user.', 'resource.', 'entity.', 'environment.']
        if not any(v.startswith(prefix) for prefix in valid_prefixes):
            raise ValueError(f"Attribute must start with one of: {', '.join(valid_prefixes)}")
        
        # Validate path structure
        import re
        if not re.match(r'^[a-zA-Z]+(\.[a-zA-Z0-9_]+)*$', v):
            raise ValueError("Invalid attribute path format")
        
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "attribute": "resource.value",
                "operator": "LESS_THAN_OR_EQUAL",
                "value": 50000
            }
        }


class PermissionModel(BaseDocument):
    """
    Permission model for custom business-specific permissions
    
    Permissions follow the format: resource:action or resource:action_scope
    Examples:
    - lead:read
    - invoice:approve
    - report:view_department
    - finance_report:generate_quarterly
    """
    
    # Permission identifier (e.g., "lead:create", "invoice:approve")
    name: str = Field(..., min_length=3, max_length=100)
    
    # Human-readable name (e.g., "Create Leads", "Approve Invoices")
    display_name: str = Field(..., min_length=3, max_length=200)
    
    # Detailed description of what this permission allows
    description: Optional[str] = Field(None, max_length=500)
    
    # Resource this permission applies to (e.g., "lead", "invoice", "report")
    resource: Optional[str] = Field(None, min_length=1, max_length=50)
    
    # Action allowed on the resource (e.g., "read", "create", "approve")
    action: Optional[str] = Field(None, min_length=1, max_length=50)
    
    # Optional scope modifier (e.g., "team", "department", "all")
    scope: Optional[str] = Field(None, max_length=50)
    
    # Entity that owns this permission (organization-specific permissions)
    entity_id: Optional[PydanticObjectId] = None
    
    # Whether this is a system permission (built-in) or custom
    is_system: bool = Field(default=False)
    
    # Whether this permission is active
    is_active: bool = Field(default=True)
    
    # Tags for categorizing permissions (e.g., ["finance", "reporting"])
    tags: List[str] = Field(default_factory=list)
    
    # ABAC Conditions - evaluated when checking this permission
    # All conditions must evaluate to true (AND logic)
    conditions: List[Condition] = Field(default_factory=list)
    
    # Additional metadata (e.g., UI hints, validation rules)
    # DEPRECATED: Use conditions instead for business rules
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Who created this permission
    created_by: Optional[PydanticObjectId] = None
    
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
    
    # Note: resource and action are auto-derived from name in model_post_init
    # No separate validation needed since name validation ensures correct format
    
    def model_post_init(self, __context):
        """Initialize permission and auto-populate resource/action from name"""
        # Auto-populate resource and action from name if not provided
        if self.name and ':' in self.name:
            parts = self.name.split(':')
            if not self.resource:
                self.resource = parts[0]
            if not self.action and len(parts) > 1:
                # Handle cases like "report:view_team" where action might have underscore
                self.action = parts[1]
                
                # Extract scope if present (e.g., view_team -> action=view, scope=team)
                if '_' in self.action and not self.scope:
                    action_parts = self.action.split('_', 1)
                    if len(action_parts) == 2 and action_parts[1] in ['all', 'team', 'department', 'organization', 'client', 'platform']:
                        self.action = action_parts[0]
                        self.scope = action_parts[1]
        
        # Ensure resource and action are set
        if not self.resource or not self.action:
            raise ValueError("Could not derive resource and action from permission name")
    
    class Settings:
        name = "permissions"
        indexes = [
            ["name", "entity_id"],  # Unique within entity
            "resource",
            "is_system",
            "is_active",
            "entity_id"
        ]

    class Config:
        json_schema_extra = {
            "example": {
                "name": "invoice:approve",
                "display_name": "Approve Invoices",
                "description": "Allows approving invoices for payment with value limits",
                "resource": "invoice",
                "action": "approve",
                "entity_id": "507f1f77bcf86cd799439011",
                "is_system": False,
                "is_active": True,
                "tags": ["finance", "accounting"],
                "conditions": [
                    {
                        "attribute": "resource.value",
                        "operator": "LESS_THAN_OR_EQUAL",
                        "value": 50000
                    },
                    {
                        "attribute": "resource.status",
                        "operator": "EQUALS",
                        "value": "pending_approval"
                    }
                ]
            }
        }