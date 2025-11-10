"""Permission schemas for router responses."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class PermissionResponse(BaseModel):
    """Permission response schema for API endpoints."""

    id: str
    name: str
    display_name: str
    description: Optional[str] = None
    resource: Optional[str] = None
    action: Optional[str] = None
    scope: Optional[str] = None
    is_system: bool = False
    is_active: bool = True
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        from_attributes = True


class PermissionCreateRequest(BaseModel):
    """Permission creation request schema."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Permission name in format resource:action",
    )
    display_name: str = Field(
        ..., min_length=1, max_length=200, description="Human-readable permission name"
    )
    description: Optional[str] = Field(
        None,
        max_length=1000,
        description="Detailed description of what this permission allows",
    )
    is_system: bool = Field(
        default=False,
        description="Whether this is a system permission (cannot be deleted)",
    )
    is_active: bool = Field(
        default=True, description="Whether this permission is currently active"
    )
    tags: List[str] = Field(
        default_factory=list, description="Tags for categorizing this permission"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )

    @field_validator("name")
    @classmethod
    def validate_name_format(cls, v: str) -> str:
        """Validate permission name follows resource:action format"""
        if ":" not in v:
            raise ValueError("Permission name must follow 'resource:action' format")

        parts = v.split(":")
        if len(parts) != 2:
            raise ValueError("Permission name must have exactly one colon")

        resource, action = parts
        if not resource or not action:
            raise ValueError("Both resource and action must be non-empty")

        # Validate characters (alphanumeric, underscore, hyphen, or asterisk for wildcard)
        import re

        if resource != "*" and not re.match(r"^[a-zA-Z0-9_-]+$", resource):
            raise ValueError(
                "Resource must contain only letters, numbers, underscores, hyphens, or asterisk"
            )
        if action != "*" and not re.match(r"^[a-zA-Z0-9_-]+$", action):
            raise ValueError(
                "Action must contain only letters, numbers, underscores, hyphens, or asterisk"
            )

        return v.lower()  # Normalize to lowercase


class PermissionUpdateRequest(BaseModel):
    """Permission update request schema."""

    display_name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    is_active: Optional[bool] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class PermissionCheckRequest(BaseModel):
    """Request to check if user has specific permissions."""

    user_id: str
    permissions: List[str]
    entity_id: str = None  # Optional entity context


class PermissionCheckResponse(BaseModel):
    """Response from permission check."""

    user_id: str
    has_all_permissions: bool
    results: dict  # Map of permission -> bool


class UserPermissionSource(BaseModel):
    """User permission with source information."""

    permission: PermissionResponse
    source: str = Field(..., description="Source of permission: 'role' or 'direct'")
    source_id: Optional[str] = Field(
        None, description="ID of the role if source is 'role'"
    )
    source_name: Optional[str] = Field(
        None, description="Name of the role if source is 'role'"
    )

    class Config:
        from_attributes = True
