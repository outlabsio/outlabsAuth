"""Permission schemas for router responses."""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


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
