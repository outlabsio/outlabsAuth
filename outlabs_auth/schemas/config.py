"""Configuration request/response schemas."""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class DefaultChildTypes(BaseModel):
    """Default child entity types organized by entity class."""

    structural: List[str] = Field(
        default_factory=lambda: ["department", "team", "branch"],
        description="Default types for structural child entities",
    )
    access_group: List[str] = Field(
        default_factory=lambda: ["permission_group", "admin_group"],
        description="Default types for access group child entities",
    )


class EntityTypeConfig(BaseModel):
    """
    Entity type configuration.

    Defines allowed root entity types and default child types
    that can be created within the system.
    """

    allowed_root_types: List[str] = Field(
        default_factory=lambda: ["organization"],
        description="Entity types allowed for root entities (no parent)",
    )
    default_child_types: DefaultChildTypes = Field(
        default_factory=DefaultChildTypes,
        description="Default child types suggested when creating child entities",
    )

    model_config = ConfigDict(from_attributes=True)


class EntityTypeConfigResponse(BaseModel):
    """Response schema for entity type configuration endpoint."""

    allowed_root_types: List[str]
    default_child_types: DefaultChildTypes
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class EntityTypeConfigUpdateRequest(BaseModel):
    """Request schema for updating entity type configuration."""

    allowed_root_types: Optional[List[str]] = Field(
        None,
        min_length=1,
        description="Entity types allowed for root entities",
    )
    default_child_types: Optional[DefaultChildTypes] = Field(
        None,
        description="Default child types for new entities",
    )
