"""
Unit tests for the user invitation system.

Tests invite_user(), accept_invite(), resend_invite(), and INVITED status handling.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import (
    AccountInactiveError,
    InvalidInputError,
    TokenExpiredError,
    TokenInvalidError,
    UserAlreadyExistsError,
)
from outlabs_auth.models.sql.enums import UserStatus
from outlabs_auth.models.sql.user import User
from outlabs_auth.services.auth import AuthService
from outlabs_auth.services.user import UserService


@pytest.fixture
def config():
    return AuthConfig(
        secret_key="test-secret-key",
        enable_invitations=True,
        invite_token_expire_days=7,
    )


@pytest.fixture
def user_service(config):
    return UserService(config)


@pytest.fixture
def auth_service(config):
    return AuthService(config)


class TestUserStatusEnum:
    """Test INVITED status in UserStatus enum."""

    def test_invited_status_exists(self):
        assert hasattr(UserStatus, "INVITED")
        assert UserStatus.INVITED.value == "invited"

    def test_invited_is_distinct_from_active(self):
        assert UserStatus.INVITED != UserStatus.ACTIVE


class TestInviteConfig:
    """Test invitation configuration."""

    def test_default_config(self):
        config = AuthConfig(secret_key="test")
        assert config.enable_invitations is True
        assert config.invite_token_expire_days == 7

    def test_custom_config(self):
        config = AuthConfig(
            secret_key="test",
            enable_invitations=False,
            invite_token_expire_days=14,
        )
        assert config.enable_invitations is False
        assert config.invite_token_expire_days == 14


class TestInviteUser:
    """Test UserService.invite_user()."""

    @pytest.mark.asyncio
    async def test_invite_creates_user_with_invited_status(self, user_service):
        session = AsyncMock()
        # get_one returns None (no existing user)
        session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

        created_user = None

        async def capture_add(obj):
            nonlocal created_user
            created_user = obj

        session.add = capture_add
        session.flush = AsyncMock()

        with patch.object(user_service, "get_one", return_value=None), \
             patch.object(user_service, "create", new_callable=AsyncMock) as mock_create:

            async def set_id(session, user):
                user.id = uuid4()
                user.created_at = datetime.now(timezone.utc)

            mock_create.side_effect = set_id

            user, plain_token = await user_service.invite_user(
                session,
                email="invite@example.com",
                first_name="Test",
                last_name="User",
                invited_by_id=uuid4(),
            )

            assert user.status == UserStatus.INVITED
            assert user.hashed_password is None
            assert user.is_superuser is False
            assert user.email == "invite@example.com"
            assert user.first_name == "Test"
            assert user.last_name == "User"
            assert user.invite_token is not None
            assert user.invite_token_expires is not None
            assert user.invited_by_id is not None
            assert len(plain_token) > 0

            # Token should be stored as SHA-256 hash, not plain
            expected_hash = hashlib.sha256(plain_token.encode()).hexdigest()
            assert user.invite_token == expected_hash

    @pytest.mark.asyncio
    async def test_invite_can_mark_user_as_superuser(self, user_service):
        session = AsyncMock()

        with patch.object(user_service, "get_one", return_value=None), \
             patch.object(user_service, "create", new_callable=AsyncMock) as mock_create:

            async def set_id(session, user):
                user.id = uuid4()
                user.created_at = datetime.now(timezone.utc)

            mock_create.side_effect = set_id

            user, _ = await user_service.invite_user(
                session,
                email="super-invite@example.com",
                is_superuser=True,
            )

            assert user.status == UserStatus.INVITED
            assert user.is_superuser is True

    @pytest.mark.asyncio
    async def test_invite_rejects_existing_email(self, user_service):
        session = AsyncMock()
        existing_user = User(email="existing@example.com", status=UserStatus.ACTIVE)

        with patch.object(user_service, "get_one", return_value=existing_user):
            with pytest.raises(UserAlreadyExistsError):
                await user_service.invite_user(session, email="existing@example.com")

    @pytest.mark.asyncio
    async def test_invite_token_expiry_uses_config(self, config, user_service):
        session = AsyncMock()

        with patch.object(user_service, "get_one", return_value=None), \
             patch.object(user_service, "create", new_callable=AsyncMock) as mock_create:

            async def set_id(session, user):
                user.id = uuid4()
                user.created_at = datetime.now(timezone.utc)

            mock_create.side_effect = set_id

            user, _ = await user_service.invite_user(session, email="test@example.com")

            # Should expire in ~7 days (config default)
            expected_min = datetime.now(timezone.utc) + timedelta(days=6, hours=23)
            expected_max = datetime.now(timezone.utc) + timedelta(days=7, minutes=1)
            assert expected_min < user.invite_token_expires < expected_max


class TestResendInvite:
    """Test UserService.resend_invite()."""

    @pytest.mark.asyncio
    async def test_resend_regenerates_token(self, user_service):
        session = AsyncMock()
        user_id = uuid4()

        old_token = hashlib.sha256(b"old-token").hexdigest()
        user = User(
            id=user_id,
            email="invited@example.com",
            status=UserStatus.INVITED,
            invite_token=old_token,
            invite_token_expires=datetime.now(timezone.utc) + timedelta(days=3),
        )

        with patch.object(user_service, "get_by_id", return_value=user), \
             patch.object(user_service, "update", new_callable=AsyncMock):

            returned_user, new_plain_token = await user_service.resend_invite(session, user_id)

            assert returned_user.invite_token != old_token
            new_expected_hash = hashlib.sha256(new_plain_token.encode()).hexdigest()
            assert returned_user.invite_token == new_expected_hash

    @pytest.mark.asyncio
    async def test_resend_rejects_non_invited_user(self, user_service):
        session = AsyncMock()
        user_id = uuid4()
        user = User(id=user_id, email="active@example.com", status=UserStatus.ACTIVE)

        with patch.object(user_service, "get_by_id", return_value=user):
            with pytest.raises(InvalidInputError, match="INVITED"):
                await user_service.resend_invite(session, user_id)


class TestAcceptInvite:
    """Test AuthService.accept_invite()."""

    @pytest.mark.asyncio
    async def test_accept_activates_user(self, auth_service):
        session = AsyncMock()
        plain_token = secrets.token_urlsafe(32)
        hashed_token = hashlib.sha256(plain_token.encode()).hexdigest()

        user = User(
            id=uuid4(),
            email="invited@example.com",
            status=UserStatus.INVITED,
            hashed_password=None,
            invite_token=hashed_token,
            invite_token_expires=datetime.now(timezone.utc) + timedelta(days=5),
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        session.execute = AsyncMock(return_value=mock_result)
        session.flush = AsyncMock()

        activated_user = await auth_service.accept_invite(
            session,
            token=plain_token,
            new_password="SecurePass123!",
        )

        assert activated_user.status == UserStatus.ACTIVE
        assert activated_user.hashed_password is not None
        assert activated_user.email_verified is True
        assert activated_user.invite_token is None
        assert activated_user.invite_token_expires is None

    @pytest.mark.asyncio
    async def test_accept_rejects_invalid_token(self, auth_service):
        session = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(TokenInvalidError):
            await auth_service.accept_invite(session, token="bad-token", new_password="Pass123!!")

    @pytest.mark.asyncio
    async def test_accept_rejects_expired_token(self, auth_service):
        session = AsyncMock()
        plain_token = secrets.token_urlsafe(32)
        hashed_token = hashlib.sha256(plain_token.encode()).hexdigest()

        user = User(
            id=uuid4(),
            email="invited@example.com",
            status=UserStatus.INVITED,
            invite_token=hashed_token,
            invite_token_expires=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        session.execute = AsyncMock(return_value=mock_result)
        session.flush = AsyncMock()

        with pytest.raises(TokenExpiredError):
            await auth_service.accept_invite(session, token=plain_token, new_password="Pass123!!")

    @pytest.mark.asyncio
    async def test_accept_rejects_already_active_user(self, auth_service):
        session = AsyncMock()
        plain_token = secrets.token_urlsafe(32)
        hashed_token = hashlib.sha256(plain_token.encode()).hexdigest()

        user = User(
            id=uuid4(),
            email="active@example.com",
            status=UserStatus.ACTIVE,
            invite_token=hashed_token,
            invite_token_expires=datetime.now(timezone.utc) + timedelta(days=5),
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(AccountInactiveError, match="already been accepted"):
            await auth_service.accept_invite(session, token=plain_token, new_password="Pass123!!")


class TestCheckUserStatusWithInvited:
    """Test that _check_user_status handles INVITED status."""

    def test_invited_status_raises_account_inactive(self, auth_service):
        user = User(
            id=uuid4(),
            email="invited@example.com",
            status=UserStatus.INVITED,
        )
        with pytest.raises(AccountInactiveError, match="not been activated"):
            auth_service._check_user_status(user)

    def test_active_status_passes(self, auth_service):
        user = User(
            id=uuid4(),
            email="active@example.com",
            status=UserStatus.ACTIVE,
        )
        # Should not raise
        auth_service._check_user_status(user)


class TestInviteSchemas:
    """Test invitation request/response schemas."""

    def test_invite_user_request(self):
        from outlabs_auth.schemas.auth import InviteUserRequest

        req = InviteUserRequest(email="test@example.com")
        assert req.email == "test@example.com"
        assert req.first_name is None
        assert req.is_superuser is False
        assert req.role_ids is None
        assert req.entity_id is None

    def test_invite_user_request_full(self):
        from outlabs_auth.schemas.auth import InviteUserRequest

        req = InviteUserRequest(
            email="test@example.com",
            first_name="John",
            last_name="Doe",
            is_superuser=True,
            role_ids=["role-1"],
            entity_id="entity-1",
        )
        assert req.first_name == "John"
        assert req.is_superuser is True
        assert req.role_ids == ["role-1"]

    def test_accept_invite_request(self):
        from outlabs_auth.schemas.auth import AcceptInviteRequest

        req = AcceptInviteRequest(token="abc123", new_password="SecurePass1!")
        assert req.token == "abc123"
        assert req.new_password == "SecurePass1!"

    def test_accept_invite_request_rejects_short_password(self):
        from outlabs_auth.schemas.auth import AcceptInviteRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            AcceptInviteRequest(token="abc123", new_password="short")
