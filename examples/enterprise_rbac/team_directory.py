"""Enterprise example router showing host-side reads via auth.host_query_service."""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

try:
    from .models import Lead
except ImportError:  # pragma: no cover - script execution path
    from models import Lead


class TeamDirectoryRoleResponse(BaseModel):
    """Minimal role data exposed to the example host app."""

    id: str
    name: str
    display_name: str


class TeamDirectoryMemberResponse(BaseModel):
    """Host-facing team member row enriched with lead workload."""

    membership_id: str
    user_id: str
    entity_id: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    user_status: str
    membership_status: str
    joined_at: str
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None
    assigned_lead_count: int
    roles: list[TeamDirectoryRoleResponse]


class TeamDirectoryResponse(BaseModel):
    """Paginated team directory response for the enterprise example."""

    entity_id: str
    total: int
    page: int
    limit: int
    pages: int
    items: list[TeamDirectoryMemberResponse]


def get_team_directory_router(
    auth: Any,
    *,
    prefix: str = "",
    tags: Optional[list[str]] = None,
) -> APIRouter:
    """
    Example host-app router using auth.host_query_service.

    This demonstrates the intended embedded-plugin boundary: the host app asks
    OutlabsAuth for entity memberships and user details, then combines those
    projections with host-owned domain data (lead workload) without joining
    auth tables directly.
    """

    router = APIRouter(prefix=prefix, tags=tags or ["team-directory"])

    @router.get(
        "/entities/{entity_id}/team-directory",
        response_model=TeamDirectoryResponse,
        summary="Get entity team directory",
        description=(
            "Return members of one entity with role details and host-domain lead counts. "
            "This route demonstrates the recommended host integration path via "
            "`auth.host_query_service`."
        ),
    )
    async def get_team_directory(
        entity_id: UUID,
        page: int = Query(1, ge=1),
        limit: int = Query(50, ge=1, le=100),
        include_inactive: bool = Query(False),
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.require_tree_permission("membership:read", "entity_id", source="path")),
    ):
        host_queries = getattr(auth, "host_query_service", None)
        if host_queries is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Host query service is unavailable for this auth preset",
            )

        memberships, total = await host_queries.list_entity_members(
            session=session,
            entity_id=entity_id,
            page=page,
            limit=limit,
            active_only=not include_inactive,
        )

        user_ids = [membership.user_id for membership in memberships]
        lead_counts: dict[UUID, int] = {}
        if user_ids:
            count_stmt = (
                select(Lead.assigned_to, func.count(Lead.id))
                .where(
                    Lead.entity_id == entity_id,
                    Lead.assigned_to.is_not(None),
                    Lead.assigned_to.in_(user_ids),
                )
                .group_by(Lead.assigned_to)
            )
            count_result = await session.execute(count_stmt)
            lead_counts = {
                user_id: int(count)
                for user_id, count in count_result.all()
                if user_id is not None
            }

        items = [
            TeamDirectoryMemberResponse(
                membership_id=str(membership.id),
                user_id=str(membership.user_id),
                entity_id=str(membership.entity_id),
                email=membership.user.email,
                first_name=membership.user.first_name,
                last_name=membership.user.last_name,
                phone=membership.user.phone,
                user_status=membership.user.status,
                membership_status=membership.status,
                joined_at=membership.joined_at.isoformat(),
                valid_from=membership.valid_from.isoformat() if membership.valid_from else None,
                valid_until=membership.valid_until.isoformat() if membership.valid_until else None,
                assigned_lead_count=lead_counts.get(membership.user_id, 0),
                roles=[
                    TeamDirectoryRoleResponse(
                        id=str(role.id),
                        name=role.name,
                        display_name=role.display_name,
                    )
                    for role in membership.roles
                ],
            )
            for membership in memberships
        ]

        pages = (total + limit - 1) // limit if total > 0 else 0
        return TeamDirectoryResponse(
            entity_id=str(entity_id),
            total=total,
            page=page,
            limit=limit,
            pages=pages,
            items=items,
        )

    return router
