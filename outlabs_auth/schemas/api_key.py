"""API Key request/response schemas."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from outlabs_auth.models.sql.enums import APIKeyStatus


class ApiKeyCreateRequest(BaseModel):
    """API key creation request schema."""

    name: str = Field(..., description="Friendly name for the API key")
    scopes: List[str] = Field(
        default_factory=list, description="List of allowed permissions/scopes"
    )
    prefix_type: str = Field(
        default="sk_live", description="Key prefix type: sk_live, sk_test, etc."
    )
    ip_whitelist: Optional[List[str]] = Field(
        default=None, description="IP whitelist (optional)"
    )
    rate_limit_per_minute: int = Field(default=60, description="Rate limit per minute")
    expires_in_days: Optional[int] = Field(
        default=None,
        description="Days until expiration (service converts to expires_at)",
    )
    description: Optional[str] = Field(
        default=None, description="Optional key description"
    )
    entity_ids: Optional[List[str]] = Field(
        default=None, description="Restrict to specific entities (None = all)"
    )


class ApiKeyResponse(BaseModel):
    """API key response schema."""

    id: str
    prefix: str  # First 12 chars only
    name: str
    scopes: List[str]
    ip_whitelist: Optional[List[str]] = None
    rate_limit_per_minute: int
    status: APIKeyStatus
    usage_count: int
    created_at: datetime
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    description: Optional[str] = None
    entity_ids: Optional[List[str]] = None
    owner_id: Optional[str] = None  # String representation of owner ID

    model_config = ConfigDict(from_attributes=True)


class ApiKeyCreateResponse(ApiKeyResponse):
    """API key creation response (includes full key - ONLY shown once!)."""

    api_key: str  # Full key with prefix


class ApiKeyUpdateRequest(BaseModel):
    """API key update request schema."""

    name: Optional[str] = None
    scopes: Optional[List[str]] = None
    ip_whitelist: Optional[List[str]] = None
    rate_limit_per_minute: Optional[int] = None
    status: Optional[APIKeyStatus] = None
    description: Optional[str] = None
    entity_ids: Optional[List[str]] = None
