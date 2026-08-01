"""Cross-user audit search router factory."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from outlabs_auth.observability import ObservabilityContext, get_observability_with_auth
from outlabs_auth.schemas.common import PaginatedResponse
from outlabs_auth.schemas.user_audit import UserAuditEventResponse


def get_audit_router(
    auth: Any,
    prefix: str = "",
    tags: Optional[list[str | Enum]] = None,
) -> APIRouter:
    """Generate cross-user audit search router."""
    router = APIRouter(prefix=prefix, tags=tags or ["audit"])

    def _serialize_user_audit_event(event: Any) -> UserAuditEventResponse:
        return UserAuditEventResponse(
            id=str(event.id),
            occurred_at=event.occurred_at,
            event_category=event.event_category,
            event_type=event.event_type,
            event_source=event.event_source,
            actor_user_id=str(event.actor_user_id) if event.actor_user_id else None,
            subject_user_id=str(event.subject_user_id) if event.subject_user_id else None,
            subject_email_snapshot=event.subject_email_snapshot,
            root_entity_id=str(event.root_entity_id) if event.root_entity_id else None,
            entity_id=str(event.entity_id) if event.entity_id else None,
            role_id=str(event.role_id) if event.role_id else None,
            request_id=event.request_id,
            ip_address=event.ip_address,
            user_agent=event.user_agent,
            reason=event.reason,
            before=event.before,
            after=event.after,
            metadata=event.event_metadata,
        )

    async def _get_actor_user_or_401(session: AsyncSession, actor_user_id: Optional[str]) -> Any:
        if not actor_user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
            )
        try:
            actor_uuid = UUID(str(actor_user_id))
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
            ) from exc
        actor_user = await auth.user_service.get_user_by_id(session, actor_uuid)
        if not actor_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
            )
        return actor_user

    @router.get(
        "",
        response_model=PaginatedResponse[UserAuditEventResponse],
        summary="Search audit events",
        description=(
            "Search high-signal user audit events across users "
            "(requires user:read permission). Scoped actors only see events "
            "whose root_entity_id is in their access scope."
        ),
    )
    async def search_audit_events(
        page: int = Query(1, ge=1),
        limit: int = Query(50, ge=1, le=100),
        category: Optional[str] = Query(None, description="Filter by audit event category"),
        event_type: Optional[str] = Query(None, description="Filter by audit event type"),
        subject_user_id: Optional[UUID] = Query(None, description="Filter by subject user"),
        actor_user_id: Optional[UUID] = Query(None, description="Filter by actor user"),
        entity_id: Optional[UUID] = Query(None, description="Filter by related entity"),
        occurred_from: Optional[datetime] = Query(
            None, description="Inclusive lower bound for occurred_at"
        ),
        occurred_to: Optional[datetime] = Query(
            None, description="Inclusive upper bound for occurred_at"
        ),
        session: AsyncSession = Depends(auth.uow),
        obs: ObservabilityContext = Depends(
            get_observability_with_auth(
                auth.observability,
                auth.deps.require_permission("user:read"),
            )
        ),
    ):
        try:
            actor_user = await _get_actor_user_or_401(session, obs.user_id)

            root_entity_ids: Optional[list[UUID]] = None
            if auth.config.enforce_user_scope and getattr(auth, "access_scope_service", None):
                scope = cast(
                    dict[str, Any],
                    await auth.access_scope_service.resolve_for_auth_result(
                        session,
                        {
                            "source": "jwt",
                            "user_id": str(actor_user.id),
                            "user": actor_user,
                        },
                        include_member_user_ids=False,
                    ),
                )
                if not auth.config.enable_entity_hierarchy:
                    scope["is_global"] = True
                if not scope.get("is_global"):
                    entity_ids = [
                        UUID(str(entity_id_value))
                        for entity_id_value in (scope.get("entity_ids") or [])
                    ]
                    root_entity_ids = entity_ids

            if not getattr(auth, "user_audit_service", None):
                return PaginatedResponse(items=[], total=0, page=page, limit=limit, pages=0)

            events, total = await auth.user_audit_service.list_events(
                session,
                page=page,
                limit=limit,
                event_category=category,
                event_type=event_type,
                subject_user_id=subject_user_id,
                actor_user_id=actor_user_id,
                entity_id=entity_id,
                root_entity_ids=root_entity_ids,
                occurred_from=occurred_from,
                occurred_to=occurred_to,
            )
            items = [_serialize_user_audit_event(event) for event in events]
            pages = (total + limit - 1) // limit if total > 0 else 0
            return PaginatedResponse(
                items=items, total=total, page=page, limit=limit, pages=pages
            )
        except HTTPException:
            raise
        except Exception as e:
            obs.log_500_error(e, page=page, limit=limit)
            raise

    return router
