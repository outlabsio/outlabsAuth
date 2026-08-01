import uuid

import httpx
import pytest
from fastapi import FastAPI

from outlabs_auth import SimpleRBAC
from outlabs_auth.fastapi import register_exception_handlers
from outlabs_auth.models.sql.social_account import SocialAccount
from outlabs_auth.routers import get_auth_router, get_users_router


def _build_app(auth) -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app, debug=True)
    app.include_router(get_auth_router(auth, prefix="/v1/auth"))
    app.include_router(get_users_router(auth, prefix="/v1/users"))
    return app


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_and_unlink_social_accounts(test_engine):
    auth = SimpleRBAC(
        engine=test_engine,
        secret_key="test-secret-key-do-not-use-in-production-12345678",
        access_token_expire_minutes=60,
        enable_token_cleanup=False,
    )
    await auth.initialize()
    try:
        password = "SocialPass123!"
        async with auth.get_session() as session:
            user = await auth.user_service.create_user(
                session=session,
                email=f"social-{uuid.uuid4().hex[:8]}@example.com",
                password=password,
                first_name="Social",
                last_name="User",
            )
            account = SocialAccount(
                user_id=user.id,
                provider="google",
                provider_user_id=f"google-{uuid.uuid4().hex[:8]}",
                provider_email=user.email,
                provider_email_verified=True,
                display_name="Social User",
            )
            session.add(account)
            user.auth_methods = list(
                set([*(user.auth_methods or []), "PASSWORD", "GOOGLE"])
            )
            await session.commit()
            user_email = user.email
            account_id = str(account.id)

        app = _build_app(auth)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            login = await client.post(
                "/v1/auth/login",
                json={"email": user_email, "password": password},
            )
            assert login.status_code == 200, login.text
            token = login.json()["access_token"]

            listed = await client.get(
                "/v1/users/me/social-accounts",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert listed.status_code == 200, listed.text
            items = listed.json()
            assert len(items) == 1
            assert items[0]["id"] == account_id
            assert items[0]["provider"] == "google"

            unlink = await client.delete(
                f"/v1/users/me/social-accounts/{account_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert unlink.status_code == 204, unlink.text

            listed_after = await client.get(
                "/v1/users/me/social-accounts",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert listed_after.status_code == 200
            assert listed_after.json() == []
    finally:
        await auth.shutdown()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cannot_unlink_last_social_account_without_password(test_engine):
    auth = SimpleRBAC(
        engine=test_engine,
        secret_key="test-secret-key-do-not-use-in-production-12345678",
        access_token_expire_minutes=60,
        enable_token_cleanup=False,
    )
    await auth.initialize()
    try:
        password = "SocialPass123!"
        async with auth.get_session() as session:
            user = await auth.user_service.create_user(
                session=session,
                email=f"oauth-only-{uuid.uuid4().hex[:8]}@example.com",
                password=password,
                first_name="OAuth",
                last_name="Only",
            )
            # Simulate OAuth-only account: clear password method/hash, keep Google.
            user.hashed_password = None
            user.auth_methods = ["GOOGLE"]
            account = SocialAccount(
                user_id=user.id,
                provider="google",
                provider_user_id=f"google-{uuid.uuid4().hex[:8]}",
                provider_email=user.email,
                provider_email_verified=True,
            )
            session.add(account)
            await session.commit()
            user_id = user.id
            account_id = str(account.id)

        # Mint a JWT without password login (OAuth-only users have no password).
        async with auth.get_session() as session:
            user = await auth.user_service.get_user_by_id(session, user_id)
            assert user is not None
            tokens = await auth.auth_service.create_tokens_for_user(session, user)

        app = _build_app(auth)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            unlink = await client.delete(
                f"/v1/users/me/social-accounts/{account_id}",
                headers={"Authorization": f"Bearer {tokens.access_token}"},
            )
            assert unlink.status_code == 400, unlink.text
    finally:
        await auth.shutdown()
