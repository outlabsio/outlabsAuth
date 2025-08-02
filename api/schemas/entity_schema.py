"""
Entity schemas for request/response validation
"""
from datetime import datetime
from typing import Optional, Dict, Any, List, Literal
from pydantic import BaseModel, Field, field_validator
from beanie import PydanticObjectId
import re


class EntityCreate(BaseModel):
    """Create entity request schema"""
    name: str = Field(..., min_length=1, max_length=100)
    display_name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    entity_class: Literal["STRUCTURAL", "ACCESS_GROUP"]
    entity_type: str = Field(..., min_length=1, max_length=50)
    parent_entity_id: Optional[str] = None
    platform_id: Optional[str] = None
    status: Literal["active", "inactive", "archived"] = "active"
    config: Optional[Dict[str, Any]] = None
    
    @field_validator('name')
    def sanitize_name(cls, v):
        """Sanitize entity name to prevent injection attacks"""
        # Remove any SQL/NoSQL injection patterns
        # Allow alphanumeric, spaces, hyphens, underscores, and dots
        sanitized = re.sub(r'[^a-zA-Z0-9\s\-_\.]', '', v)
        # Remove multiple spaces
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()
        if not sanitized:
            raise ValueError('Name contains only invalid characters')
        # Prevent common injection patterns
        injection_patterns = [
            r"^.*[';].*$",  # SQL injection
            r"^.*--.*$",    # SQL comment
            r"^.*\/\*.*$",  # SQL comment
            r"^.*\$\{.*$",  # Template injection
            r"^.*\{\$.*$",  # MongoDB injection
        ]
        for pattern in injection_patterns:
            if re.match(pattern, v, re.IGNORECASE):
                # Return sanitized version instead of original
                return sanitized
        return v
    
    @field_validator('entity_type')
    def validate_entity_type(cls, v, info):
        """Validate entity type - now flexible, just ensure it's lowercase"""
        # Convert to lowercase for consistency
        return v.lower()
    
    @field_validator('parent_entity_id')
    def validate_parent_id(cls, v):
        """Validate parent entity ID format"""
        if v:
            try:
                PydanticObjectId(v)
            except Exception:
                raise ValueError('Invalid parent entity ID format')
        return v


class EntityUpdate(BaseModel):
    """Update entity request schema"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    display_name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    status: Optional[Literal["active", "inactive", "archived"]] = None
    config: Optional[Dict[str, Any]] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    
    @field_validator('name')
    def sanitize_name(cls, v):
        """Sanitize entity name to prevent injection attacks"""
        if v is None:
            return v
        # Remove any SQL/NoSQL injection patterns
        # Allow alphanumeric, spaces, hyphens, underscores, and dots
        sanitized = re.sub(r'[^a-zA-Z0-9\s\-_\.]', '', v)
        # Remove multiple spaces
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()
        if not sanitized:
            raise ValueError('Name contains only invalid characters')
        # Prevent common injection patterns
        injection_patterns = [
            r"^.*[';].*$",  # SQL injection
            r"^.*--.*$",    # SQL comment
            r"^.*\/\*.*$",  # SQL comment
            r"^.*\$\{.*$",  # Template injection
            r"^.*\{\$.*$",  # MongoDB injection
        ]
        for pattern in injection_patterns:
            if re.match(pattern, v, re.IGNORECASE):
                # Return sanitized version instead of original
                return sanitized
        return v
    
    @field_validator('valid_until')
    def validate_validity_period(cls, v, info):
        """Ensure valid_until is after valid_from"""
        if v and info.data and 'valid_from' in info.data and info.data['valid_from']:
            if v <= info.data['valid_from']:
                raise ValueError('valid_until must be after valid_from')
        return v


class EntityResponse(BaseModel):
    """Entity response schema"""
    id: str
    name: str
    display_name: str
    description: Optional[str] = None
    entity_class: Literal["STRUCTURAL", "ACCESS_GROUP"]
    entity_type: str
    parent_entity_id: Optional[str] = None
    platform_id: Optional[str] = None
    status: str
    direct_permissions: List[str] = []
    config: Dict[str, Any] = {}
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class EntityTreeResponse(EntityResponse):
    """Entity response with children"""
    children: List['EntityTreeResponse'] = []
    member_count: int = 0
    
    class Config:
        from_attributes = True


class EntityMemberAdd(BaseModel):
    """Add member to entity request"""
    user_id: str
    role_id: str
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    
    @field_validator('user_id', 'role_id')
    def validate_object_id(cls, v):
        """Validate MongoDB ObjectId format"""
        try:
            PydanticObjectId(v)
        except Exception:
            raise ValueError(f'Invalid ObjectId format: {v}')
        return v
    
    @field_validator('valid_until')
    def validate_validity_period(cls, v, info):
        """Ensure valid_until is after valid_from"""
        if v and info.data and 'valid_from' in info.data and info.data['valid_from']:
            if v <= info.data['valid_from']:
                raise ValueError('valid_until must be after valid_from')
        return v


class EntityMemberUpdate(BaseModel):
    """Update entity member request"""
    role_id: Optional[str] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    is_active: Optional[bool] = None
    
    @field_validator('role_id')
    def validate_role_id(cls, v):
        """Validate MongoDB ObjectId format"""
        if v:
            try:
                PydanticObjectId(v)
            except Exception:
                raise ValueError(f'Invalid role ID format: {v}')
        return v


class EntityMemberResponse(BaseModel):
    """Entity member response"""
    id: str
    user_id: str
    user_email: str
    user_name: str
    entity_id: str
    entity_name: str  # Display name for backward compatibility
    entity_system_name: Optional[str] = None  # System/technical name
    role_id: str
    role_name: str
    permissions: List[str] = []
    is_active: bool
    status: str  # Computed field for backward compatibility
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class EntitySearchParams(BaseModel):
    """Entity search parameters"""
    query: Optional[str] = Field(None, description="Search in name, display_name, description")
    entity_class: Optional[Literal["STRUCTURAL", "ACCESS_GROUP"]] = None
    entity_type: Optional[str] = None
    status: Optional[Literal["active", "inactive", "archived"]] = None
    parent_entity_id: Optional[str] = None
    platform_id: Optional[str] = None
    include_children: bool = Field(False, description="Include child entities in response")
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class EntityListResponse(BaseModel):
    """Paginated entity list response"""
    items: List[EntityResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class EntityPermissionCheck(BaseModel):
    """Check permissions for entity"""
    entity_id: str
    permissions: List[str] = Field(..., min_items=1)
    
    @field_validator('entity_id')
    def validate_entity_id(cls, v):
        """Validate MongoDB ObjectId format"""
        try:
            PydanticObjectId(v)
        except Exception:
            raise ValueError('Invalid entity ID format')
        return v


class EntityPermissionResponse(BaseModel):
    """Permission check response"""
    entity_id: str
    permissions: Dict[str, bool]
    source: Dict[str, str]  # Maps permission to source (direct, inherited, role)


# Update forward references for recursive model
EntityTreeResponse.model_rebuild()