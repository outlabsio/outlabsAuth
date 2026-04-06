"""Integration principal request and response schemas."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from outlabs_auth.models.sql.enums import IntegrationPrincipalScopeKind, IntegrationPrincipalStatus


class IntegrationPrincipalCreateRequest(BaseModel):
    """Create request for an integration principal."""

    name: str = Field(..., description="Human-readable principal name")
    description: Optional[str] = Field(default=None, description="Optional description")
    allowed_scopes: List[str] = Field(default_factory=list, description="Maximum scopes this principal may delegate")
    inherit_from_tree: bool = Field(
        default=False,
        description="Whether entity-scoped principals may access descendant entities",
    )


class IntegrationPrincipalUpdateRequest(BaseModel):
    """Patch request for mutable principal fields."""

    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[IntegrationPrincipalStatus] = None
    allowed_scopes: Optional[List[str]] = None
    inherit_from_tree: Optional[bool] = None


class IntegrationPrincipalResponse(BaseModel):
    """Read model for an integration principal."""

    id: str
    name: str
    description: Optional[str] = None
    status: IntegrationPrincipalStatus
    scope_kind: IntegrationPrincipalScopeKind
    anchor_entity_id: Optional[str] = None
    inherit_from_tree: bool
    allowed_scopes: List[str]
    created_by_user_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
