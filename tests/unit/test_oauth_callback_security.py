from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import select

from outlabs_auth import SimpleRBAC
from outlabs_auth.models.sql.social_account import SocialAccount
from outlabs_auth.routers.oauth import oauth_callback


@pytest_asyncio.fixture
async def oauth_auth_instance(test_engine) -> SimpleRBAC:
    auth = SimpleRBAC(
        engine=test_engine,
        secret_key="test-secret-key-do-not-use-in-production-12345678",
        enable_token_cleanup=False,
    )
    await auth.initialize()
    yield auth
    await auth.shutdown()


@pytest_asyncio.fixture
async def oauth_secure_auth_instance(test_engine) -> SimpleRBAC:
    auth = SimpleRBAC(
        engine=test_engine,
        secret_key="test-secret-key-do-not-use-in-production-12345678",
        enable_token_cleanup=False,
        store_oauth_provider_tokens=True,
        oauth_token_encryption_key=Fernet.generate_key().decode(),
    )
    await auth.initialize()
    yield auth
    await auth.shutdown()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_oauth_callback_rejects_unverified_email_association(
    oauth_auth_instance: SimpleRBAC,
):
    email = f"oauth-{uuid4().hex[:8]}@example.com"
    async with oauth_auth_instance.get_session() as session:
        await oauth_auth_instance.user_service.create_user(
            session,
            email=email,
            password="TestPass123!",
            first_name="OAuth",
            last_name="User",
        )
        await session.commit()

    async with oauth_auth_instance.get_session() as session:
        with pytest.raises(HTTPException) as exc_info:
            await oauth_callback(
                auth=oauth_auth_instance,
                session=session,
                provider="github",
                access_token="provider-access-token",
                refresh_token="provider-refresh-token",
                account_id="github-user-123",
                account_email=email,
                account_email_verified=False,
                associate_by_email=True,
                is_verified_by_default=False,
            )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "associate_by_email requires a provider-verified email"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_oauth_callback_encrypts_provider_tokens_and_persists_verified_email(
    oauth_secure_auth_instance: SimpleRBAC,
):
    email = f"oauth-new-{uuid4().hex[:8]}@example.com"

    async with oauth_secure_auth_instance.get_session() as session:
        user = await oauth_callback(
            auth=oauth_secure_auth_instance,
            session=session,
            provider="github",
            access_token="provider-access-token",
            refresh_token="provider-refresh-token",
            account_id="github-user-456",
            account_email=email,
            account_email_verified=True,
            associate_by_email=False,
            is_verified_by_default=True,
        )
        await session.commit()

    async with oauth_secure_auth_instance.get_session() as session:
        stored_user = await oauth_secure_auth_instance.user_service.get_user_by_email(
            session, email
        )
        assert stored_user is not None
        assert stored_user.id == user.id
        assert stored_user.email_verified is True

        social_account = (
            await session.execute(
                select(SocialAccount).where(
                    SocialAccount.user_id == user.id,
                    SocialAccount.provider == "github",
                )
            )
        ).scalar_one()

        assert social_account.provider_email_verified is True
        assert social_account.access_token != "provider-access-token"
        assert social_account.refresh_token != "provider-refresh-token"
        assert (
            oauth_secure_auth_instance.oauth_token_cipher.decrypt(
                social_account.access_token
            )
            == "provider-access-token"
        )
        assert (
            oauth_secure_auth_instance.oauth_token_cipher.decrypt(
                social_account.refresh_token
            )
            == "provider-refresh-token"
        )
