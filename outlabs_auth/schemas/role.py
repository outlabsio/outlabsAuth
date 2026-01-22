"""Role request/response schemas."""

from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class RoleResponse(BaseModel):
    """Role response schema."""

    id: str
    name: str
    display_name: str
    description: Optional[str] = None
    permissions: List[str] = Field(default_factory=list)
    entity_type_permissions: Optional[Dict[str, List[str]]] = None
    is_system_role: bool = False
    is_global: bool = False
    root_entity_id: Optional[str] = Field(
        None,
        description="Root entity (organization) that owns this role. NULL for system-wide roles.",
    )
    root_entity_name: Optional[str] = Field(
        None,
        description="Display name of the root entity (for convenience).",
    )
    assignable_at_types: List[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class RoleCreateRequest(BaseModel):
    """Role creation request schema."""

    name: str = Field(..., min_length=1, max_length=100)
    display_name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    permissions: List[str] = Field(default_factory=list)
    entity_type_permissions: Optional[Dict[str, List[str]]] = None
    is_global: bool = Field(
        default=True,
        description="If True with no root_entity_id, role is available system-wide.",
    )
    root_entity_id: Optional[str] = Field(
        None,
        description="Root entity (organization) that owns this role. Must be a root entity. Omit for system-wide roles.",
    )
    assignable_at_types: List[str] = Field(default_factory=list)


class RoleUpdateRequest(BaseModel):
    """Role update request schema."""

    """Role update request schema."""
    display_name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    permissions: Optional[List[str]] = None
    entity_type_permissions: Optional[Dict[str, List[str]]] = None
    is_global: Optional[bool] = None
    assignable_at_types: Optional[List[str]] = None
