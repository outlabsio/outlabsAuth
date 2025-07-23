"""
Role schemas for request/response validation
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator


class RoleCreate(BaseModel):
    """Create role request schema"""
    name: str = Field(..., min_length=1, max_length=50, pattern=r'^[a-zA-Z0-9_-]+$')
    display_name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    permissions: List[str] = Field(..., min_items=1)
    entity_id: Optional[str] = None
    assignable_at_types: Optional[List[str]] = Field(default_factory=list)
    is_global: bool = False
    
    @field_validator('permissions')
    def validate_permissions(cls, v):
        """Validate permission format"""
        for perm in v:
            if ":" not in perm and perm not in ["*"]:
                raise ValueError(f"Invalid permission format: {perm}")
        return v
    
    @field_validator('assignable_at_types')
    def validate_assignable_types(cls, v):
        """Validate assignable entity types"""
        # Entity types are now flexible strings, so we just ensure they're not empty
        if v:
            for entity_type in v:
                if not entity_type or not isinstance(entity_type, str):
                    raise ValueError(f"Invalid entity type: {entity_type}")
        return v


class RoleUpdate(BaseModel):
    """Update role request schema"""
    display_name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    permissions: Optional[List[str]] = None
    assignable_at_types: Optional[List[str]] = None
    
    @field_validator('permissions')
    def validate_permissions(cls, v):
        """Validate permission format"""
        if v is not None:
            for perm in v:
                if ":" not in perm and perm not in ["*"]:
                    raise ValueError(f"Invalid permission format: {perm}")
        return v


class RoleResponse(BaseModel):
    """Role response schema"""
    id: str
    name: str
    display_name: str
    description: Optional[str] = None
    permissions: List[str]
    entity_id: Optional[str] = None
    entity_name: Optional[str] = None  # Display name for backward compatibility
    entity_system_name: Optional[str] = None  # System/technical name
    assignable_at_types: List[str]
    is_system_role: bool
    is_global: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class RoleListResponse(BaseModel):
    """Paginated role list response"""
    items: List[RoleResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class RoleSearchParams(BaseModel):
    """Role search parameters"""
    entity_id: Optional[str] = None
    query: Optional[str] = Field(None, description="Search in name and description")
    is_global: Optional[bool] = None
    assignable_at_type: Optional[str] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class RoleAssignmentRequest(BaseModel):
    """Role assignment request"""
    role_id: str
    user_id: str
    entity_id: str
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None


class RoleAssignmentResponse(BaseModel):
    """Role assignment response"""
    id: str
    role_id: str
    role_name: str
    user_id: str
    user_email: str
    entity_id: str
    entity_name: str
    status: str
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    created_at: datetime


class RolePermissionTemplate(BaseModel):
    """Role permission template"""
    name: str
    display_name: str
    description: str
    permissions: List[str]
    suitable_for: List[str]  # Entity types this template is suitable for


class RoleTemplateResponse(BaseModel):
    """Role template response"""
    templates: Dict[str, RolePermissionTemplate]


class RoleUsageStats(BaseModel):
    """Role usage statistics"""
    role_id: str
    role_name: str
    active_assignments: int
    total_assignments: int
    entities_used_in: int
    last_assigned: Optional[datetime] = None


class RoleUsageStatsResponse(BaseModel):
    """Role usage statistics response"""
    stats: List[RoleUsageStats]