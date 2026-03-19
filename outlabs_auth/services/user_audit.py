"""Service for user-centric audit timeline events."""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.models.sql.user_audit_event import UserAuditEvent
from outlabs_auth.services.base import BaseService


class UserAuditService(BaseService[UserAuditEvent]):
    """Persist and query append-only user audit events."""

    def __init__(self, config: AuthConfig):
        super().__init__(UserAuditEvent)
        self.config = config

    async def record_event(
        self,
        session: AsyncSession,
        *,
        event_category: str,
        event_type: str,
        event_source: str,
        subject_user_id: Optional[UUID],
        subject_email_snapshot: str,
        actor_user_id: Optional[UUID] = None,
        root_entity_id: Optional[UUID] = None,
        entity_id: Optional[UUID] = None,
        role_id: Optional[UUID] = None,
        request_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        reason: Optional[str] = None,
        before: Optional[Dict[str, Any]] = None,
        after: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        occurred_at: Optional[datetime] = None,
    ) -> UserAuditEvent:
        """Append one audit event."""
        event = UserAuditEvent(
            occurred_at=occurred_at or datetime.now(timezone.utc),
            event_category=event_category,
            event_type=event_type,
            event_source=event_source,
            actor_user_id=actor_user_id,
            subject_user_id=subject_user_id,
            subject_email_snapshot=subject_email_snapshot,
            root_entity_id=root_entity_id,
            entity_id=entity_id,
            role_id=role_id,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            reason=reason,
            before=self._normalize_payload(before),
            after=self._normalize_payload(after),
            event_metadata=self._normalize_payload(metadata),
        )
        session.add(event)
        await session.flush()
        return event

    async def list_user_events(
        self,
        session: AsyncSession,
        user_id: UUID,
        *,
        page: int = 1,
        limit: int = 50,
        event_category: Optional[str] = None,
        event_type: Optional[str] = None,
        entity_id: Optional[UUID] = None,
    ) -> Tuple[List[UserAuditEvent], int]:
        """Return paginated audit events for one user."""
        filters = [UserAuditEvent.subject_user_id == user_id]
        if event_category:
            filters.append(UserAuditEvent.event_category == event_category)
        if event_type:
            filters.append(UserAuditEvent.event_type == event_type)
        if entity_id:
            filters.append(UserAuditEvent.entity_id == entity_id)

        count_stmt = select(func.count()).select_from(UserAuditEvent).where(*filters)
        total = int((await session.execute(count_stmt)).scalar_one())

        stmt = (
            select(UserAuditEvent)
            .where(*filters)
            .order_by(UserAuditEvent.occurred_at.desc(), UserAuditEvent.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all()), total

    @classmethod
    def _normalize_payload(cls, payload: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if payload is None:
            return None
        return {str(key): cls._normalize_value(value) for key, value in payload.items()}

    @classmethod
    def _normalize_value(cls, value: Any) -> Any:
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, dict):
            return {str(key): cls._normalize_value(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [cls._normalize_value(item) for item in value]
        return value
