"""Entity request/response schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class EntityResponse(BaseModel):
    """Entity response schema (safe to expose)."""

    id: str
    name: str
    display_name: str
    slug: str
    description: Optional[str] = None
    entity_class: str  # "structural" or "access_group"
    entity_type: str  # "organization", "department", "team", etc.
    parent_entity_id: Optional[str] = None
    status: str = "active"
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    direct_permissions: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    allowed_child_classes: List[str] = Field(default_factory=list)
    allowed_child_types: List[str] = Field(default_factory=list)
    max_members: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class EntityCreateRequest(BaseModel):
    """Entity creation request schema."""

    name: str = Field(..., min_length=1, max_length=100)
    display_name: str = Field(..., min_length=1, max_length=200)
    slug: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    entity_class: str = Field(..., pattern="^(structural|access_group)$")
    entity_type: str = Field(..., min_length=1, max_length=50)
    parent_entity_id: Optional[str] = None
    status: str = Field(default="active", pattern="^(active|inactive|archived)$")
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    direct_permissions: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    allowed_child_classes: List[str] = Field(default_factory=list)
    allowed_child_types: List[str] = Field(default_factory=list)
    max_members: Optional[int] = None


class EntityUpdateRequest(BaseModel):
    """Entity update request schema."""

    display_name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(active|inactive|archived)$")
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    direct_permissions: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    allowed_child_classes: Optional[List[str]] = None
    allowed_child_types: Optional[List[str]] = None
    max_members: Optional[int] = None


class MemberResponse(BaseModel):
    """Entity member response schema."""

    user_id: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role_ids: List[str] = Field(default_factory=list)
    role_names: List[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
