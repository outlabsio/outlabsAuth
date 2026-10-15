"""Persisted lifecycle values must reject retained setup tokens without side effects."""

import hashlib
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, select

from outlabs_auth import EnterpriseRBAC
from outlabs_auth.fastapi import register_exception_handlers
from outlabs_auth.models.sql.enums import UserStatus
from outlabs_auth.models.sql.token import RefreshToken
from outlabs_auth.models.sql.user import User
from outlabs_auth.routers import get_auth_router


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["active", "suspended", "banned", "deleted"])
async def test_retained_invite_on_non_invited_persisted_user_denies_without_mutation(test_engine, state):
    auth = EnterpriseRBAC(
        engine=test_engine, secret_key="isolated-retained-invite-test-secret-only", enable_token_cleanup=False
    )
    await auth.initialize()
    token = uuid4().hex
    try:
        async with auth.get_session() as session:
            user = User(
                email=uuid4().hex + "@example.com",
                status=state,
                hashed_password="unchanged-existing-hash",
                invite_token=hashlib.sha256(token.encode()).hexdigest(),
                invite_token_expires=datetime.now(timezone.utc) + timedelta(days=1),
            )
            session.add(user)
            await session.commit()
            identity = user.id
            await session.refresh(user)
            assert isinstance(user.status, str) and not isinstance(user.status, UserStatus)
            before = dict((await session.execute(select(User.__table__).where(User.id == identity))).mappings().one())
        app = FastAPI()
        register_exception_handlers(app)
        app.include_router(get_auth_router(auth, prefix="/auth"))
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://local.test"
        ) as client:
            for _ in range(2):
                response = await client.post(
                    "/auth/accept-invite", json={"token": token, "new_password": "FreshInvite123!"}
                )
                assert response.status_code == 401, response.text
                payload = response.json()
                assert "ACCOUNT_INACTIVE" in str(payload)
                assert "access_token" not in payload and "refresh_token" not in payload
        async with auth.get_session() as session:
            after = dict((await session.execute(select(User.__table__).where(User.id == identity))).mappings().one())
            assert after == before
            assert (
                await session.execute(
                    select(func.count()).select_from(RefreshToken).where(RefreshToken.user_id == identity)
                )
            ).scalar_one() == 0
    finally:
        await auth.shutdown()
