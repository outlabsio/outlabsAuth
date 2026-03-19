"""Service for append-only role definition history."""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.models.sql.enums import DefinitionStatus
from outlabs_auth.models.sql.role_definition_history import RoleDefinitionHistory
from outlabs_auth.services.base import BaseService


class RoleHistoryService(BaseService[RoleDefinitionHistory]):
    """Persist and query append-only role definition history."""

    def __init__(self, config: AuthConfig):
        super().__init__(RoleDefinitionHistory)
        self.config = config

    async def record_event(
        self,
        session: AsyncSession,
        *,
        role_id: UUID,
        event_type: str,
        event_source: str,
        snapshot: Dict[str, Any],
        actor_user_id: Optional[UUID] = None,
        before: Optional[Dict[str, Any]] = None,
        after: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        occurred_at: Optional[datetime] = None,
    ) -> RoleDefinitionHistory:
        """Append one role definition history row."""
        normalized_snapshot = self._normalize_payload(snapshot) or {}
        event = RoleDefinitionHistory(
            role_id=role_id,
            actor_user_id=actor_user_id,
            root_entity_id=self._maybe_uuid(snapshot.get("root_entity_id")),
            scope_entity_id=self._maybe_uuid(snapshot.get("scope_entity_id")),
            event_type=event_type,
            event_source=event_source,
            occurred_at=occurred_at or datetime.now(timezone.utc),
            role_name_snapshot=str(normalized_snapshot.get("role_name") or ""),
            role_display_name_snapshot=str(normalized_snapshot.get("role_display_name") or ""),
            role_description_snapshot=self._maybe_str(normalized_snapshot.get("role_description")),
            root_entity_name_snapshot=self._maybe_str(normalized_snapshot.get("root_entity_name")),
            scope_entity_name_snapshot=self._maybe_str(normalized_snapshot.get("scope_entity_name")),
            is_system_role_snapshot=bool(normalized_snapshot.get("is_system_role", False)),
            is_global_snapshot=bool(normalized_snapshot.get("is_global", False)),
            scope_snapshot=str(normalized_snapshot.get("scope") or ""),
            status_snapshot=self._resolve_status_snapshot(normalized_snapshot),
            is_auto_assigned_snapshot=bool(normalized_snapshot.get("is_auto_assigned", False)),
            assignable_at_types_snapshot=list(normalized_snapshot.get("assignable_at_types") or []),
            permission_ids_snapshot=[
                UUID(str(permission_id))
                for permission_id in (normalized_snapshot.get("permission_ids") or [])
            ],
            permission_names_snapshot=list(normalized_snapshot.get("permission_names") or []),
            entity_type_permissions_snapshot=self._normalize_value(
                snapshot.get("entity_type_permissions")
            ),
            before=self._normalize_payload(before),
            after=self._normalize_payload(after),
            event_metadata=self._normalize_payload(metadata),
        )
        session.add(event)
        await session.flush()
        return event

    async def list_role_events(
        self,
        session: AsyncSession,
        role_id: UUID,
        *,
        page: int = 1,
        limit: int = 50,
        event_type: Optional[str] = None,
    ) -> Tuple[List[RoleDefinitionHistory], int]:
        """Return paginated definition history rows for one role."""
        filters = [RoleDefinitionHistory.role_id == role_id]
        if event_type:
            filters.append(RoleDefinitionHistory.event_type == event_type)

        count_stmt = select(func.count()).select_from(RoleDefinitionHistory).where(*filters)
        total = int((await session.execute(count_stmt)).scalar_one())

        stmt = (
            select(RoleDefinitionHistory)
            .where(*filters)
            .order_by(RoleDefinitionHistory.occurred_at.desc(), RoleDefinitionHistory.created_at.desc())
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

    @staticmethod
    def _maybe_uuid(value: Any) -> Optional[UUID]:
        if value in (None, ""):
            return None
        return UUID(str(value))

    @staticmethod
    def _maybe_str(value: Any) -> Optional[str]:
        if value in (None, ""):
            return None
        return str(value)

    @staticmethod
    def _resolve_status_snapshot(snapshot: Dict[str, Any]) -> DefinitionStatus:
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

        return DefinitionStatus.ACTIVE
