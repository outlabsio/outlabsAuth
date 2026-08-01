"""User session (active refresh token) response schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UserSessionResponse(BaseModel):
    """One active login session (refresh token), without secrets."""

    id: UUID
    device_name: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime
    last_used_at: Optional[datetime] = None
    expires_at: datetime
    usage_count: int = Field(default=0)

    model_config = ConfigDict(from_attributes=True)
