"""
Entity schemas for request/response validation
"""
from datetime import datetime
from typing import Optional, Dict, Any, List, Literal
from pydantic import BaseModel, Field, field_validator
from beanie import PydanticObjectId


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
    
    @field_validator('entity_type')
    def validate_entity_type(cls, v, values):
        """Validate entity type based on entity class"""
        if 'entity_class' in values:
            if values['entity_class'] == 'STRUCTURAL':
                allowed_types = ['platform', 'organization', 'branch', 'team']
                if v not in allowed_types:
                    raise ValueError(f'For STRUCTURAL entities, type must be one of: {allowed_types}')
            elif values['entity_class'] == 'ACCESS_GROUP':
                # Access groups can have custom types
                if not v.islower():
                    raise ValueError('Access group types must be lowercase')
        return v
    
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
    display_name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    status: Optional[Literal["active", "inactive", "archived"]] = None
    config: Optional[Dict[str, Any]] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    
    @field_validator('valid_until')
    def validate_validity_period(cls, v, values):
        """Ensure valid_until is after valid_from"""
        if v and 'valid_from' in values and values['valid_from']:
            if v <= values['valid_from']:
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
    def validate_validity_period(cls, v, values):
        """Ensure valid_until is after valid_from"""
        if v and 'valid_from' in values and values['valid_from']:
            if v <= values['valid_from']:
                raise ValueError('valid_until must be after valid_from')
        return v


class EntityMemberUpdate(BaseModel):
    """Update entity member request"""
    role_id: Optional[str] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    status: Optional[Literal["active", "suspended", "revoked"]] = None
    
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
    entity_name: str
    role_id: str
    role_name: str
    permissions: List[str] = []
    status: str
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