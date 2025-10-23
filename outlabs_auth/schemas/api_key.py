"""API Key request/response schemas."""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class ApiKeyCreateRequest(BaseModel):
    """API key creation request schema."""
    name: str = Field(..., description="Friendly name for the API key")
    permissions: List[str] = Field(default_factory=list, description="List of allowed permissions")
    environment: str = Field(default="production", description="Environment: production, staging, development, test")
    allowed_ips: Optional[List[str]] = Field(default=None, description="IP whitelist (optional)")
    rate_limit_per_minute: int = Field(default=60, description="Rate limit per minute")
    expires_at: Optional[datetime] = Field(default=None, description="Optional expiration date")


class ApiKeyResponse(BaseModel):
    """API key response schema."""
    id: str
    key_prefix: str  # First 12 chars only
    name: str
    permissions: List[str]
    environment: str
    allowed_ips: Optional[List[str]] = None
    rate_limit_per_minute: int
    is_active: bool
    usage_count: int
    created_at: datetime
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ApiKeyCreateResponse(ApiKeyResponse):
    """API key creation response (includes full key - ONLY shown once!)."""
    api_key: str  # Full key with prefix


class ApiKeyUpdateRequest(BaseModel):
    """API key update request schema."""
    name: Optional[str] = None
    permissions: Optional[List[str]] = None
    allowed_ips: Optional[List[str]] = None
    rate_limit_per_minute: Optional[int] = None
    is_active: Optional[bool] = None
