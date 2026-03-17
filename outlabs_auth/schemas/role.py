"""Role request/response schemas."""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RoleScopeEnum(str, Enum):
    """Role scope for API schemas."""

    ENTITY_ONLY = "entity_only"
    HIERARCHY = "hierarchy"


class RoleSummary(BaseModel):
    """Minimal role information for embedding in other responses."""

    id: str
    name: str
    display_name: str

    model_config = ConfigDict(from_attributes=True)


class RoleResponse(BaseModel):
    """Role response schema."""

    id: str
    name: str
    display_name: str
    description: Optional[str] = None
    permissions: List[str] = Field(default_factory=list)
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

    # Entity-local role fields (DD-053)
    scope_entity_id: Optional[str] = Field(
        None,
        description="Entity where this role is defined. NULL for root/system-level roles.",
    )
    scope_entity_name: Optional[str] = Field(
        None,
        description="Display name of the scope entity (for convenience).",
    )
    scope: RoleScopeEnum = Field(
        default=RoleScopeEnum.HIERARCHY,
        description="Controls where permissions apply: entity_only or hierarchy.",
    )
    is_auto_assigned: bool = Field(
        default=False,
        description="If true, automatically assigned to members within scope.",
    )

    model_config = ConfigDict(from_attributes=True)


class RoleCreateRequest(BaseModel):
    """Role creation request schema."""

    name: str = Field(..., min_length=1, max_length=100)
    display_name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    permissions: List[str] = Field(default_factory=list)
    is_global: bool = Field(
        default=True,
        description="If True with no root_entity_id, role is available system-wide.",
    )
    root_entity_id: Optional[str] = Field(
        None,
        description="Root entity (organization) that owns this role. Must be a root entity. Omit for system-wide roles.",
    )
    assignable_at_types: List[str] = Field(default_factory=list)

    # Entity-local role fields (DD-053)
    scope_entity_id: Optional[str] = Field(
        None,
        description="Entity where this role is defined. If set, creates an entity-local role.",
    )
    scope: RoleScopeEnum = Field(
        default=RoleScopeEnum.HIERARCHY,
        description="Controls where permissions apply: entity_only (just this entity) or hierarchy (entity + descendants).",
    )
    is_auto_assigned: bool = Field(
        default=False,
        description="If true, automatically assigned to all members within scope (retroactive).",
    )

    @field_validator("assignable_at_types")
    @classmethod
    def normalize_assignable_at_types(cls, value: List[str]) -> List[str]:
        return list(dict.fromkeys(item.strip().lower() for item in value if item and item.strip()))


class RoleUpdateRequest(BaseModel):
    """Role update request schema."""

    display_name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    permissions: Optional[List[str]] = None
    is_global: Optional[bool] = None
    assignable_at_types: Optional[List[str]] = None

    # Entity-local role fields (DD-053)
    scope: Optional[RoleScopeEnum] = Field(
        None,
        description="Controls where permissions apply: entity_only or hierarchy.",
    )
    is_auto_assigned: Optional[bool] = Field(
        None,
        description="If true, automatically assigned to all members within scope (retroactive when changed to true).",
    )

    @field_validator("assignable_at_types")
    @classmethod
    def normalize_optional_assignable_at_types(
        cls, value: Optional[List[str]]
    ) -> Optional[List[str]]:
        if value is None:
            return None
        return list(dict.fromkeys(item.strip().lower() for item in value if item and item.strip()))
