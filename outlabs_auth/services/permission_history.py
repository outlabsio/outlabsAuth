"""Service for append-only permission definition history."""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.models.sql.enums import DefinitionStatus
from outlabs_auth.models.sql.permission_definition_history import (
    PermissionDefinitionHistory,
)
from outlabs_auth.services.base import BaseService


class PermissionHistoryService(BaseService[PermissionDefinitionHistory]):
    """Persist and query append-only permission definition history."""

    def __init__(self, config: AuthConfig):
        super().__init__(PermissionDefinitionHistory)
        self.config = config

    async def record_event(
        self,
        session: AsyncSession,
        *,
        permission_id: UUID,
        event_type: str,
        event_source: str,
        snapshot: Dict[str, Any],
        actor_user_id: Optional[UUID] = None,
        before: Optional[Dict[str, Any]] = None,
        after: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        occurred_at: Optional[datetime] = None,
    ) -> PermissionDefinitionHistory:
        """Append one permission definition history row."""
        normalized_snapshot = self._normalize_payload(snapshot) or {}
        is_active_snapshot = bool(normalized_snapshot.get("is_active", True))
        event = PermissionDefinitionHistory(
            permission_id=permission_id,
            actor_user_id=actor_user_id,
            event_type=event_type,
            event_source=event_source,
            occurred_at=occurred_at or datetime.now(timezone.utc),
            permission_name_snapshot=str(
                normalized_snapshot.get("permission_name") or ""
            ),
            permission_display_name_snapshot=str(
                normalized_snapshot.get("permission_display_name") or ""
            ),
            permission_description_snapshot=self._maybe_str(
                normalized_snapshot.get("permission_description")
            ),
            resource_snapshot=self._maybe_str(normalized_snapshot.get("resource")),
            action_snapshot=self._maybe_str(normalized_snapshot.get("action")),
            scope_snapshot=self._maybe_str(normalized_snapshot.get("scope")),
            is_system_snapshot=bool(normalized_snapshot.get("is_system", False)),
            status_snapshot=self._resolve_status_snapshot(
                normalized_snapshot,
                fallback_active=is_active_snapshot,
            ),
            is_active_snapshot=is_active_snapshot,
            tag_names_snapshot=list(normalized_snapshot.get("tag_names") or []),
            before=self._normalize_payload(before),
            after=self._normalize_payload(after),
            event_metadata=self._normalize_payload(metadata),
        )
        session.add(event)
        await session.flush()
        return event

    async def list_permission_events(
        self,
        session: AsyncSession,
        permission_id: UUID,
        *,
        page: int = 1,
        limit: int = 50,
        event_type: Optional[str] = None,
    ) -> Tuple[List[PermissionDefinitionHistory], int]:
        """Return paginated definition history rows for one permission."""
        filters = [PermissionDefinitionHistory.permission_id == permission_id]
        if event_type:
            filters.append(PermissionDefinitionHistory.event_type == event_type)

        count_stmt = (
            select(func.count())
            .select_from(PermissionDefinitionHistory)
            .where(*filters)
        )
        total = int((await session.execute(count_stmt)).scalar_one())

        stmt = (
            select(PermissionDefinitionHistory)
            .where(*filters)
            .order_by(
                PermissionDefinitionHistory.occurred_at.desc(),
                PermissionDefinitionHistory.created_at.desc(),
            )
            .offset((page - 1) * limit)
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all()), total

    @classmethod
    def _normalize_payload(
        cls,
        payload: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
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

    @staticmethod
    def _maybe_str(value: Any) -> Optional[str]:
        if value in (None, ""):
            return None
        return str(value)

    @staticmethod
    def _resolve_status_snapshot(
        snapshot: Dict[str, Any],
        *,
        fallback_active: bool,
    ) -> DefinitionStatus:
        raw_status = snapshot.get("status")
        if raw_status not in (None, ""):
            try:
                return (
                    raw_status
                    if isinstance(raw_status, DefinitionStatus)
                    else DefinitionStatus(str(raw_status))
                )
            except ValueError:
                pass

        return (
            DefinitionStatus.ACTIVE
            if fallback_active
            else DefinitionStatus.INACTIVE
        )
