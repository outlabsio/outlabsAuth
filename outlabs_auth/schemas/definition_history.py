"""Response schemas for append-only role/permission definition history."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class DefinitionHistoryEventResponse(BaseModel):
    """One append-only change to a role or permission definition."""

    id: str
    definition_kind: Literal["role", "permission"]
    definition_id: str
    event_type: str
    event_source: str
    occurred_at: datetime
    actor_user_id: Optional[str] = None
    name: str = Field(..., description="Definition name at the time of the event")
    display_name: str = Field(..., description="Definition display name at the time of the event")
    status: str = Field(..., description="Definition status at the time of the event")
    permission_names: List[str] = Field(
        default_factory=list,
        description="Role events: the role's permission names after the event",
    )
    before: Optional[Dict[str, Any]] = None
    after: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


def _status_text(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


def role_history_event_response(event: Any) -> DefinitionHistoryEventResponse:
    return DefinitionHistoryEventResponse(
        id=str(event.id),
        definition_kind="role",
        definition_id=str(event.role_id),
        event_type=event.event_type,
        event_source=event.event_source,
        occurred_at=event.occurred_at,
        actor_user_id=str(event.actor_user_id) if event.actor_user_id else None,
        name=event.role_name_snapshot,
        display_name=event.role_display_name_snapshot,
        status=_status_text(event.status_snapshot),
        permission_names=list(event.permission_names_snapshot or []),
        before=event.before,
        after=event.after,
        metadata=event.event_metadata,
    )


def permission_history_event_response(event: Any) -> DefinitionHistoryEventResponse:
    return DefinitionHistoryEventResponse(
        id=str(event.id),
        definition_kind="permission",
        definition_id=str(event.permission_id),
        event_type=event.event_type,
        event_source=event.event_source,
        occurred_at=event.occurred_at,
        actor_user_id=str(event.actor_user_id) if event.actor_user_id else None,
        name=event.permission_name_snapshot,
        display_name=event.permission_display_name_snapshot,
        status=_status_text(event.status_snapshot),
        before=event.before,
        after=event.after,
        metadata=event.event_metadata,
    )
