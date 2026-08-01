"""Schemas for user audit timeline events."""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict


class UserAuditEventResponse(BaseModel):
    """One user-centric audit event."""

    id: str
    occurred_at: datetime
    event_category: str
    event_type: str
    event_source: str
    actor_user_id: Optional[str] = None
    subject_user_id: Optional[str] = None
    subject_email_snapshot: str
    root_entity_id: Optional[str] = None
    entity_id: Optional[str] = None
    role_id: Optional[str] = None
    request_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    reason: Optional[str] = None
    before: Optional[Dict[str, Any]] = None
    after: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)
