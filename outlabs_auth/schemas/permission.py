"""Permission schemas for router responses."""

from typing import List
from pydantic import BaseModel


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
