"""Explicit staff mount; no administrative grants enter ordinary IAM checks."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from outlabs_auth.services.administrative_authorization import (
    AdministrativeAuthorization,
    StaffEntityPage,
    StaffKeyPage,
    StaffKeyView,
)
from outlabs_auth.models.sql.api_key import APIKey
from outlabs_auth.models.sql.enums import APIKeyStatus
from outlabs_auth.routers.capabilities import mark_auth_surface


class StaffKeyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    entity_id: UUID
    scopes: list[str] = Field(min_length=1, max_length=64)
    inherit_from_tree: bool = False
    expires_in_days: int = Field(default=30, ge=1, le=30)


class StaffKeyNarrow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scopes: list[str] = Field(min_length=1, max_length=64)
    expires_at: datetime | None = None


class StaffKeyIssued(BaseModel):
    secret: str
    key: StaffKeyView


def get_staff_router(facade: AdministrativeAuthorization, *, prefix: str = "/staff") -> APIRouter:
    """Mount one app-lifetime facade under an explicit, separate surface.

    This bounded first mount supports entity discovery and owned credentials.
    Customer IAM/account mutations require their own qualified operation pairing.
    Install auth.instrument_fastapi(app) before startup for commit-before-response.
    """
    router = APIRouter(prefix=prefix, tags=["staff"])

    def view(key: APIKey) -> StaffKeyView:
        return StaffKeyView(key.id, key.name, APIKeyStatus(key.status), key.entity_id, key.expires_at)

    @router.get("/entities", response_model=StaffEntityPage)
    async def entities(
        request: Request,
        limit: int = Query(50, ge=1, le=100),
        cursor: str | None = None,
        customer_root_id: UUID | None = None,
        session: AsyncSession = Depends(facade.auth.uow),
    ):
        context = await facade.authenticate(session, request)
        return await facade.entity_page(
            session, context, action="entity:read", limit=limit, cursor=cursor, customer_root_id=customer_root_id
        )

    @router.get("/keys", response_model=StaffKeyPage)
    async def keys(
        request: Request,
        limit: int = Query(50, ge=1, le=100),
        after: UUID | None = None,
        session: AsyncSession = Depends(facade.auth.uow),
    ):
        context = await facade.authenticate(session, request)
        return await facade.personal_key_page(session, context, limit=limit, after=after)

    @router.post("/keys", response_model=StaffKeyIssued, status_code=201)
    async def create(body: StaffKeyCreate, request: Request, session: AsyncSession = Depends(facade.auth.uow)):
        context = await facade.authenticate(session, request)
        secret, key = await facade.create_personal_key(session, context, **body.model_dump())
        return StaffKeyIssued(secret=secret, key=view(key))

    @router.patch("/keys/{key_id}", response_model=StaffKeyView)
    async def narrow(
        key_id: UUID, body: StaffKeyNarrow, request: Request, session: AsyncSession = Depends(facade.auth.uow)
    ):
        context = await facade.authenticate(session, request)
        return view(await facade.update_personal_key(session, context, key_id=key_id, **body.model_dump()))

    @router.post("/keys/{key_id}/rotate", response_model=StaffKeyIssued)
    async def rotate(key_id: UUID, request: Request, session: AsyncSession = Depends(facade.auth.uow)):
        context = await facade.authenticate(session, request)
        secret, key = await facade.rotate_personal_key(session, context, key_id=key_id)
        return StaffKeyIssued(secret=secret, key=view(key))

    @router.delete("/keys/{key_id}", status_code=204)
    async def revoke(key_id: UUID, request: Request, session: AsyncSession = Depends(facade.auth.uow)):
        context = await facade.authenticate(session, request)
        if not await facade.revoke_personal_key(session, context, key_id=key_id):
            raise HTTPException(404, "Key not found")

    return mark_auth_surface(router, "staff")
