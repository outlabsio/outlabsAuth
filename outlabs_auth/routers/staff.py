"""Explicit staff mount; no administrative grants enter ordinary IAM checks."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from outlabs_auth.models.sql.user import User
from outlabs_auth.models.sql.entity_membership import EntityMembership
from outlabs_auth.models.sql.enums import UserStatus, MembershipStatus

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


class StaffProfileEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)


class StaffStatusEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: UserStatus


class StaffMemberEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role_ids: list[UUID] = Field(default_factory=list, max_length=64)


class StaffUserView(BaseModel):
    id: UUID
    root_entity_id: UUID
    email: str
    first_name: str | None
    last_name: str | None
    status: UserStatus


class StaffMemberView(BaseModel):
    id: UUID
    user_id: UUID
    entity_id: UUID
    status: MembershipStatus
    role_ids: list[UUID]


def get_staff_router(facade: AdministrativeAuthorization, *, prefix: str = "/staff") -> APIRouter:
    """Mount one app-lifetime facade under an explicit, separate surface.

    The explicit mount supports entity discovery, owned credentials and bounded
    customer account/member operations. Ordinary IAM admission stays separate.
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

    def user_view(user: User) -> StaffUserView:
        assert user.root_entity_id is not None
        return StaffUserView(
            id=user.id,
            root_entity_id=user.root_entity_id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            status=user.status,
        )

    async def account(
        session: AsyncSession, request: Request, user_id: UUID, action: str, write: bool = False
    ) -> tuple[Any, User]:
        context = await facade.authenticate(session, request)
        if not (
            await facade.authorize_account(session, context, action=action, user_id=user_id, protected_write=write)
        ).allowed:
            raise HTTPException(403, "Customer account admission refused")
        user = await session.get(User, user_id, populate_existing=True)
        assert user is not None
        return context, user

    @router.get("/users")
    async def user_page(
        request: Request,
        customer_root_id: UUID,
        limit: int = Query(50, ge=1, le=100),
        after: UUID | None = None,
        session: AsyncSession = Depends(facade.auth.uow),
    ) -> dict[str, Any]:
        context = await facade.authenticate(session, request)
        rows, total = await facade.customer_users(
            session, context, customer_root_id=customer_root_id, limit=limit, after=after
        )
        return {
            "items": [user_view(u) for u in rows],
            "total": total,
            "next_after": str(rows[-1].id) if len(rows) == limit else None,
        }

    @router.get("/users/{user_id}", response_model=StaffUserView)
    async def detail(
        user_id: UUID, request: Request, session: AsyncSession = Depends(facade.auth.uow)
    ) -> StaffUserView:
        _, user = await account(session, request, user_id, "user:read")
        return user_view(user)

    @router.patch("/users/{user_id}", response_model=StaffUserView)
    async def profile(
        user_id: UUID, body: StaffProfileEdit, request: Request, session: AsyncSession = Depends(facade.auth.uow)
    ) -> StaffUserView:
        _, user = await account(session, request, user_id, "user:update", True)
        await facade.auth.user_service.update_user_fields(session, user.id, **body.model_dump(exclude_unset=True))
        await session.refresh(user)
        return user_view(user)

    @router.post("/users/{user_id}/status", response_model=StaffUserView)
    async def account_status(
        user_id: UUID, body: StaffStatusEdit, request: Request, session: AsyncSession = Depends(facade.auth.uow)
    ) -> StaffUserView:
        _, user = await account(session, request, user_id, "user:update", True)
        if user.status == UserStatus.DELETED or body.status not in (UserStatus.ACTIVE, UserStatus.SUSPENDED):
            raise HTTPException(422, "Use explicit deletion/restore; account status supports active/suspended")
        await facade.auth.user_service.update_user_status(session, user.id, body.status)
        await session.refresh(user)
        return user_view(user)

    @router.delete("/users/{user_id}", status_code=204)
    async def delete_account(user_id: UUID, request: Request, session: AsyncSession = Depends(facade.auth.uow)) -> None:
        _, user = await account(session, request, user_id, "user:delete", True)
        await facade.auth.user_service.delete_user(session, user.id)

    @router.post("/users/{user_id}/restore", response_model=StaffUserView)
    async def restore_account(
        user_id: UUID, request: Request, session: AsyncSession = Depends(facade.auth.uow)
    ) -> StaffUserView:
        _, user = await account(session, request, user_id, "user:update", True)
        user = await facade.auth.user_service.restore_user(session, user.id)
        return user_view(user)

    def member_view(member: EntityMembership) -> StaffMemberView:
        return StaffMemberView(
            id=member.id,
            user_id=member.user_id,
            entity_id=member.entity_id,
            status=member.status,
            role_ids=[r.id for r in member.roles],
        )

    @router.get("/entities/{entity_id}/members/{user_id}", response_model=StaffMemberView)
    async def member_detail(
        entity_id: UUID, user_id: UUID, request: Request, session: AsyncSession = Depends(facade.auth.uow)
    ) -> StaffMemberView:
        context = await facade.authenticate(session, request)
        await facade.member_admission(session, context, action="membership:read", entity_id=entity_id, user_id=user_id)
        member = await facade.auth.membership_service.get_member(session, entity_id, user_id)
        if member is None:
            raise HTTPException(404, "Membership not found")
        return member_view(member)

    @router.put("/entities/{entity_id}/members/{user_id}", response_model=StaffMemberView)
    async def member_set(
        entity_id: UUID,
        user_id: UUID,
        body: StaffMemberEdit,
        request: Request,
        session: AsyncSession = Depends(facade.auth.uow),
    ) -> StaffMemberView:
        context = await facade.authenticate(session, request)
        # Acquire the subject fence before deciding whether this is creation.
        await facade.member_admission(
            session,
            context,
            action=(
                "membership:update"
                if await facade.auth.membership_service.get_member(session, entity_id, user_id)
                else "membership:create"
            ),
            entity_id=entity_id,
            user_id=user_id,
            role_ids=body.role_ids,
            write=True,
        )
        member = await facade.auth.membership_service.get_member(session, entity_id, user_id)
        action = "membership:create" if member is None else "membership:update"
        await facade.member_admission(
            session, context, action=action, entity_id=entity_id, user_id=user_id, role_ids=body.role_ids, write=True
        )
        if member is None:
            member = await facade.auth.membership_service.add_member(
                session, entity_id, user_id, role_ids=body.role_ids, joined_by_id=context.user_id, skip_auto_assign=True
            )
        else:
            member = await facade.auth.membership_service.update_member_roles(
                session, entity_id, user_id, body.role_ids
            )
        return member_view(member)

    @router.delete("/entities/{entity_id}/members/{user_id}", status_code=204)
    async def member_remove(
        entity_id: UUID, user_id: UUID, request: Request, session: AsyncSession = Depends(facade.auth.uow)
    ) -> None:
        context = await facade.authenticate(session, request)
        await facade.member_admission(
            session, context, action="membership:delete", entity_id=entity_id, user_id=user_id, write=True
        )
        await facade.auth.membership_service.remove_member(session, entity_id, user_id, revoked_by_id=context.user_id)

    @router.post("/entities/{entity_id}/members/{user_id}/reactivate", response_model=StaffMemberView)
    async def member_reactivate(
        entity_id: UUID, user_id: UUID, request: Request, session: AsyncSession = Depends(facade.auth.uow)
    ) -> StaffMemberView:
        context = await facade.authenticate(session, request)
        await facade.member_admission(
            session, context, action="membership:update", entity_id=entity_id, user_id=user_id, write=True
        )
        member = await facade.auth.membership_service.reactivate_membership(session, entity_id, user_id)
        return member_view(member)

    return mark_auth_surface(router, "staff")
