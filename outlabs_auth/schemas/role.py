"""Role request/response schemas."""

from typing import Optional, List, Dict
from pydantic import BaseModel, Field


class RoleResponse(BaseModel):
    """Role response schema (safe to expose)."""
    id: str
    name: str
    display_name: str
    description: Optional[str] = None
    permissions: List[str] = Field(default_factory=list)
    entity_type_permissions: Optional[Dict[str, List[str]]] = None
    is_system_role: bool = False
    is_global: bool = False
    assignable_at_types: List[str] = Field(default_factory=list)

    class Config:
        from_attributes = True


class RoleCreateRequest(BaseModel):
    """Role creation request schema."""
    name: str = Field(..., min_length=1, max_length=100)
    display_name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    permissions: List[str] = Field(default_factory=list)
    entity_type_permissions: Optional[Dict[str, List[str]]] = None
    is_global: bool = False
    assignable_at_types: List[str] = Field(default_factory=list)


class RoleUpdateRequest(BaseModel):
    """Role update request schema."""
    display_name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    permissions: Optional[List[str]] = None
    entity_type_permissions: Optional[Dict[str, List[str]]] = None
    is_global: Optional[bool] = None
    assignable_at_types: Optional[List[str]] = None
