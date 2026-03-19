from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import select

from outlabs_auth import SimpleRBAC
from outlabs_auth.models.sql.social_account import SocialAccount
from outlabs_auth.models.sql.user import User
from outlabs_auth.oauth.exceptions import ProviderError
from outlabs_auth.oauth.models import OAuthUserInfo
from outlabs_auth.routers.oauth import oauth_callback
from outlabs_auth.routers.oauth_utils import get_oauth_user_info


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


@pytest.mark.unit
@pytest.mark.asyncio
async def test_oauth_callback_rejects_missing_usable_email_for_new_user(
    oauth_auth_instance: SimpleRBAC,
):
    async with oauth_auth_instance.get_session() as session:
        with pytest.raises(HTTPException) as exc_info:
            await oauth_callback(
                auth=oauth_auth_instance,
                session=session,
                provider="github",
                access_token="provider-access-token",
                refresh_token="provider-refresh-token",
                account_id="github-user-no-email",
                account_email="   ",
                account_email_verified=False,
                associate_by_email=False,
                is_verified_by_default=False,
            )

        existing_users = (await session.execute(select(User))).scalars().all()
        existing_links = (await session.execute(select(SocialAccount))).scalars().all()

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Email not available from OAuth provider"
    assert existing_users == []
    assert existing_links == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_oauth_callback_existing_mapping_can_login_without_new_provider_email(
    oauth_auth_instance: SimpleRBAC,
):
    email = f"oauth-existing-{uuid4().hex[:8]}@example.com"

    async with oauth_auth_instance.get_session() as session:
        user = await oauth_auth_instance.user_service.create_user(
            session,
            email=email,
            password="TestPass123!",
            first_name="OAuth",
            last_name="Mapped",
        )
        session.add(
            SocialAccount(
                user_id=user.id,
                provider="github",
                provider_user_id="github-existing-user",
                provider_email=email,
                provider_email_verified=True,
            )
        )
        await session.commit()

    async with oauth_auth_instance.get_session() as session:
        returned_user = await oauth_callback(
            auth=oauth_auth_instance,
            session=session,
            provider="github",
            access_token="provider-access-token",
            refresh_token="provider-refresh-token",
            account_id="github-existing-user",
            account_email="",
            account_email_verified=False,
            associate_by_email=False,
            is_verified_by_default=False,
        )
        await session.commit()

    async with oauth_auth_instance.get_session() as session:
        social_account = (
            await session.execute(
                select(SocialAccount).where(
                    SocialAccount.user_id == returned_user.id,
                    SocialAccount.provider == "github",
                )
            )
        ).scalar_one()

    assert returned_user.email == email
    assert social_account.provider_email == email
    assert social_account.provider_email_verified is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_oauth_user_info_uses_verified_id_token_parsing():
    class DummyOAuthClient:
        async def get_user_info(self, access_token: str):
            raise NotImplementedError

        def parse_id_token(self, id_token: str, verify: bool = False) -> OAuthUserInfo:
            assert id_token == "apple-id-token"
            assert verify is True
            return OAuthUserInfo(
                provider_user_id="apple-user-123",
                email="apple@example.com",
                email_verified=True,
            )

    user_info = await get_oauth_user_info(
        DummyOAuthClient(),
        {"access_token": "provider-access-token", "id_token": "apple-id-token"},
    )

    assert user_info.provider_user_id == "apple-user-123"
    assert user_info.email == "apple@example.com"
    assert user_info.email_verified is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_oauth_user_info_rejects_invalid_verified_id_token():
    class DummyOAuthClient:
        async def get_user_info(self, access_token: str):
            raise NotImplementedError

        def parse_id_token(self, id_token: str, verify: bool = False) -> OAuthUserInfo:
            raise ProviderError(
                provider="apple",
                error="invalid_id_token",
                error_description="signature check failed",
            )

    with pytest.raises(HTTPException) as exc_info:
        await get_oauth_user_info(
            DummyOAuthClient(),
            {"access_token": "provider-access-token", "id_token": "apple-id-token"},
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Invalid OAuth provider ID token"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_oauth_user_info_prefers_access_token_userinfo_over_id_token():
    class DummyOAuthClient:
        async def get_user_info(self, access_token: str):
            assert access_token == "provider-access-token"
            return OAuthUserInfo(
                provider_user_id="google-user-123",
                email="google@example.com",
                email_verified=True,
            )

        def parse_id_token(self, id_token: str, verify: bool = False) -> OAuthUserInfo:
            raise AssertionError("parse_id_token should not be used when get_user_info succeeds")

    user_info = await get_oauth_user_info(
        DummyOAuthClient(),
        {"access_token": "provider-access-token", "id_token": "should-not-be-used"},
    )

    assert user_info.provider_user_id == "google-user-123"
    assert user_info.email == "google@example.com"
