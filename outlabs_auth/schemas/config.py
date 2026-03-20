"""Configuration request/response schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from outlabs_auth.models.sql.system_config import (
    DEFAULT_ACCESS_GROUP_ROOT_TYPES,
    DEFAULT_STRUCTURAL_ROOT_TYPES,
)


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


class AllowedRootTypes(BaseModel):
    """Allowed root entity types organized by entity class."""

    structural: List[str] = Field(
        default_factory=lambda: list(DEFAULT_STRUCTURAL_ROOT_TYPES),
        description="Allowed structural entity types at the root of a hierarchy",
    )
    access_group: List[str] = Field(
        default_factory=lambda: list(DEFAULT_ACCESS_GROUP_ROOT_TYPES),
        description="Allowed access-group entity types at the root of a hierarchy",
    )


class EntityTypeConfig(BaseModel):
    """
    Entity type configuration.

    Defines allowed root entity types and default child types
    that can be created within the system.
    """

    allowed_root_types: AllowedRootTypes = Field(
        default_factory=AllowedRootTypes,
        description="Entity types allowed for root entities (no parent), grouped by entity class",
    )
    default_child_types: DefaultChildTypes = Field(
        default_factory=DefaultChildTypes,
        description="Default child types suggested when creating child entities",
    )

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy_allowed_root_types(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value

        allowed_root_types = value.get("allowed_root_types")
        if isinstance(allowed_root_types, list):
            normalized = dict(value)
            normalized["allowed_root_types"] = {
                "structural": allowed_root_types,
                "access_group": list(DEFAULT_ACCESS_GROUP_ROOT_TYPES),
            }
            return normalized

        return value


class EntityTypeConfigResponse(BaseModel):
    """Response schema for entity type configuration endpoint."""

    allowed_root_types: AllowedRootTypes
    default_child_types: DefaultChildTypes
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class EntityTypeConfigUpdateRequest(BaseModel):
    """Request schema for updating entity type configuration."""

    allowed_root_types: Optional[AllowedRootTypes] = Field(
        None,
        description="Entity types allowed for root entities, grouped by entity class",
    )
    default_child_types: Optional[DefaultChildTypes] = Field(
        None,
        description="Default child types for new entities",
    )

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy_allowed_root_types(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value

        allowed_root_types = value.get("allowed_root_types")
        if isinstance(allowed_root_types, list):
            normalized = dict(value)
            normalized["allowed_root_types"] = {
                "structural": allowed_root_types,
                "access_group": list(DEFAULT_ACCESS_GROUP_ROOT_TYPES),
            }
            return normalized

        return value
