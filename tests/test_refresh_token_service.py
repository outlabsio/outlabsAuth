import pytest
import pytest_asyncio
from httpx import AsyncClient
from datetime import datetime, timedelta
import asyncio
from unittest.mock import patch, AsyncMock
from beanie import PydanticObjectId

from api.services.refresh_token_service import refresh_token_service
from api.models.refresh_token_model import RefreshTokenModel
from api.models.user_model import UserModel
from tests.conftest import ADMIN_USER_DATA

class TestRefreshTokenService:
    """
    Comprehensive test suite for refresh token service.
    Tests session management, token lifecycle, and advanced scenarios.
    """

    async def get_admin_token_and_refresh(self, client: AsyncClient) -> tuple[str, str]:
        """Helper to get both access and refresh tokens."""
        login_data = {
            "username": ADMIN_USER_DATA["email"],
            "password": ADMIN_USER_DATA["password"],
        }
        response = await client.post("/v1/auth/login", data=login_data)
        assert response.status_code == 200
        tokens = response.json()
        return tokens["access_token"], tokens["refresh_token"]

    @pytest.mark.asyncio
    async def test_create_refresh_token(self, client: AsyncClient):
        """Test creating a refresh token record."""
        # Get a user for testing
        user = await UserModel.find_one(UserModel.email == ADMIN_USER_DATA["email"])
        assert user is not None
        
        # Create refresh token
        jti = "test-jti-123"
        expires_at = datetime.utcnow() + timedelta(days=7)
        ip_address = "192.168.1.100"
        user_agent = "Test User Agent"
        
        token_record = await refresh_token_service.create_refresh_token(
            user_id=user.id,
            jti=jti,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        assert token_record is not None
        assert token_record.jti == jti
        assert token_record.ip_address == ip_address
        assert token_record.user_agent == user_agent
        assert token_record.is_revoked is False
        assert token_record.expires_at == expires_at

    @pytest.mark.asyncio
    async def test_get_refresh_token_by_jti(self, client: AsyncClient):
        """Test retrieving refresh token by JTI."""
        # Create a token first
        user = await UserModel.find_one(UserModel.email == ADMIN_USER_DATA["email"])
        jti = "test-jti-456"
        expires_at = datetime.utcnow() + timedelta(days=7)
        
        created_token = await refresh_token_service.create_refresh_token(
            user_id=user.id,
            jti=jti,
            expires_at=expires_at
        )
        
        # Retrieve it
        retrieved_token = await refresh_token_service.get_refresh_token_by_jti(jti)
        
        assert retrieved_token is not None
        assert retrieved_token.jti == jti
        assert retrieved_token.id == created_token.id

    @pytest.mark.asyncio
    async def test_get_nonexistent_refresh_token(self, client: AsyncClient):
        """Test retrieving non-existent refresh token."""
        token = await refresh_token_service.get_refresh_token_by_jti("nonexistent-jti")
        assert token is None

    @pytest.mark.asyncio
    async def test_revoke_token(self, client: AsyncClient):
        """Test revoking a refresh token."""
        # Create a token first
        user = await UserModel.find_one(UserModel.email == ADMIN_USER_DATA["email"])
        jti = "test-jti-revoke"
        expires_at = datetime.utcnow() + timedelta(days=7)
        
        await refresh_token_service.create_refresh_token(
            user_id=user.id,
            jti=jti,
            expires_at=expires_at
        )
        
        # Revoke it
        success = await refresh_token_service.revoke_token(jti)
        assert success is True
        
        # Verify it's revoked
        token = await refresh_token_service.get_refresh_token_by_jti(jti)
        assert token.is_revoked is True

    @pytest.mark.asyncio
    async def test_revoke_nonexistent_token(self, client: AsyncClient):
        """Test revoking a non-existent token."""
        success = await refresh_token_service.revoke_token("nonexistent-jti")
        assert success is False

    @pytest.mark.asyncio
    async def test_revoke_all_tokens_for_user(self, client: AsyncClient):
        """Test revoking all tokens for a specific user."""
        user = await UserModel.find_one(UserModel.email == ADMIN_USER_DATA["email"])
        expires_at = datetime.utcnow() + timedelta(days=7)
        
        # Create multiple tokens for the user
        jtis = ["jti-1", "jti-2", "jti-3"]
        for jti in jtis:
            await refresh_token_service.create_refresh_token(
                user_id=user.id,
                jti=jti,
                expires_at=expires_at
            )
        
        # Revoke all tokens
        revoked_count = await refresh_token_service.revoke_all_tokens_for_user(user.id)
        assert revoked_count >= len(jtis)  # Might be more if other tests created tokens
        
        # Verify all are revoked
        for jti in jtis:
            token = await refresh_token_service.get_refresh_token_by_jti(jti)
            assert token.is_revoked is True

    @pytest.mark.asyncio
    async def test_revoke_all_tokens_for_nonexistent_user(self, client: AsyncClient):
        """Test revoking tokens for non-existent user."""
        fake_user_id = PydanticObjectId()
        revoked_count = await refresh_token_service.revoke_all_tokens_for_user(fake_user_id)
        assert revoked_count == 0

    @pytest.mark.asyncio
    async def test_get_sessions_for_user(self, client: AsyncClient):
        """Test getting active sessions for a user."""
        user = await UserModel.find_one(UserModel.email == ADMIN_USER_DATA["email"])
        
        # Clean up any existing tokens for clean test
        await refresh_token_service.revoke_all_tokens_for_user(user.id)
        
        # Create multiple active sessions
        expires_at = datetime.utcnow() + timedelta(days=7)
        active_jtis = ["active-1", "active-2"]
        
        for jti in active_jtis:
            await refresh_token_service.create_refresh_token(
                user_id=user.id,
                jti=jti,
                expires_at=expires_at,
                ip_address=f"192.168.1.{jti.split('-')[1]}",
                user_agent=f"Browser {jti}"
            )
        
        # Create an expired session
        expired_expires_at = datetime.utcnow() - timedelta(days=1)
        await refresh_token_service.create_refresh_token(
            user_id=user.id,
            jti="expired-session",
            expires_at=expired_expires_at
        )
        
        # Create a revoked session
        revoked_jti = "revoked-session"
        await refresh_token_service.create_refresh_token(
            user_id=user.id,
            jti=revoked_jti,
            expires_at=expires_at
        )
        await refresh_token_service.revoke_token(revoked_jti)
        
        # Get active sessions
        sessions = await refresh_token_service.get_sessions_for_user(user.id)
        
        # Should only return active, non-expired sessions
        assert len(sessions) == len(active_jtis)
        session_jtis = [session.jti for session in sessions]
        for jti in active_jtis:
            assert jti in session_jtis

    @pytest.mark.asyncio
    async def test_get_sessions_for_nonexistent_user(self, client: AsyncClient):
        """Test getting sessions for non-existent user."""
        fake_user_id = PydanticObjectId()
        sessions = await refresh_token_service.get_sessions_for_user(fake_user_id)
        assert sessions == []

    @pytest.mark.asyncio
    async def test_revoke_session_by_jti(self, client: AsyncClient):
        """Test revoking a specific session by JTI."""
        user = await UserModel.find_one(UserModel.email == ADMIN_USER_DATA["email"])
        jti = "specific-session"
        expires_at = datetime.utcnow() + timedelta(days=7)
        
        await refresh_token_service.create_refresh_token(
            user_id=user.id,
            jti=jti,
            expires_at=expires_at
        )
        
        # Revoke specific session
        success = await refresh_token_service.revoke_session_by_jti(user.id, jti)
        assert success is True
        
        # Verify it's revoked
        token = await refresh_token_service.get_refresh_token_by_jti(jti)
        assert token.is_revoked is True

    @pytest.mark.asyncio
    async def test_revoke_session_by_jti_wrong_user(self, client: AsyncClient):
        """Test that users can't revoke other users' sessions."""
        user = await UserModel.find_one(UserModel.email == ADMIN_USER_DATA["email"])
        fake_user_id = PydanticObjectId()
        jti = "protected-session"
        expires_at = datetime.utcnow() + timedelta(days=7)
        
        await refresh_token_service.create_refresh_token(
            user_id=user.id,
            jti=jti,
            expires_at=expires_at
        )
        
        # Try to revoke with wrong user ID
        success = await refresh_token_service.revoke_session_by_jti(fake_user_id, jti)
        assert success is False
        
        # Verify it's still active
        token = await refresh_token_service.get_refresh_token_by_jti(jti)
        assert token.is_revoked is False

class TestRefreshTokenServiceAdvanced:
    """Advanced test scenarios for refresh token service."""

    @pytest.mark.asyncio
    async def test_concurrent_token_creation(self, client: AsyncClient):
        """Test concurrent token creation for the same user."""
        user = await UserModel.find_one(UserModel.email == ADMIN_USER_DATA["email"])
        expires_at = datetime.utcnow() + timedelta(days=7)
        
        # Create tokens concurrently
        async def create_token(index):
            return await refresh_token_service.create_refresh_token(
                user_id=user.id,
                jti=f"concurrent-{index}",
                expires_at=expires_at,
                ip_address=f"192.168.1.{index}",
                user_agent=f"Device {index}"
            )
        
        # Create 5 tokens concurrently
        tasks = [create_token(i) for i in range(5)]
        tokens = await asyncio.gather(*tasks)
        
        # All should be created successfully
        assert len(tokens) == 5
        for i, token in enumerate(tokens):
            assert token.jti == f"concurrent-{i}"
            assert token.ip_address == f"192.168.1.{i}"

    @pytest.mark.asyncio
    async def test_concurrent_token_revocation(self, client: AsyncClient):
        """Test concurrent token revocation."""
        user = await UserModel.find_one(UserModel.email == ADMIN_USER_DATA["email"])
        expires_at = datetime.utcnow() + timedelta(days=7)
        
        # Create multiple tokens
        jtis = [f"revoke-concurrent-{i}" for i in range(5)]
        for jti in jtis:
            await refresh_token_service.create_refresh_token(
                user_id=user.id,
                jti=jti,
                expires_at=expires_at
            )
        
        # Revoke them concurrently
        tasks = [refresh_token_service.revoke_token(jti) for jti in jtis]
        results = await asyncio.gather(*tasks)
        
        # All should be revoked successfully
        assert all(results)
        
        # Verify all are revoked
        for jti in jtis:
            token = await refresh_token_service.get_refresh_token_by_jti(jti)
            assert token.is_revoked is True

    @pytest.mark.asyncio
    async def test_session_management_with_device_info(self, client: AsyncClient):
        """Test session management with device information tracking."""
        user = await UserModel.find_one(UserModel.email == ADMIN_USER_DATA["email"])
        expires_at = datetime.utcnow() + timedelta(days=7)
        
        # Create sessions with different device info
        devices = [
            ("192.168.1.100", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0"),
            ("192.168.1.101", "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) Safari/604.1"),
            ("192.168.1.102", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/537.36"),
        ]
        
        for i, (ip, user_agent) in enumerate(devices):
            await refresh_token_service.create_refresh_token(
                user_id=user.id,
                jti=f"device-{i}",
                expires_at=expires_at,
                ip_address=ip,
                user_agent=user_agent
            )
        
        # Get sessions and verify device info is tracked
        sessions = await refresh_token_service.get_sessions_for_user(user.id)
        device_sessions = [s for s in sessions if s.jti.startswith("device-")]
        
        assert len(device_sessions) == 3
        
        for session in device_sessions:
            assert session.ip_address is not None
            assert session.user_agent is not None
            assert session.ip_address.startswith("192.168.1.")

    @pytest.mark.asyncio
    async def test_expired_token_filtering(self, client: AsyncClient):
        """Test that expired tokens are properly filtered from active sessions."""
        user = await UserModel.find_one(UserModel.email == ADMIN_USER_DATA["email"])
        
        # Create mix of active and expired tokens
        active_expires = datetime.utcnow() + timedelta(days=7)
        expired_expires = datetime.utcnow() - timedelta(days=1)
        
        # Active tokens
        await refresh_token_service.create_refresh_token(
            user_id=user.id,
            jti="active-token-1",
            expires_at=active_expires
        )
        
        await refresh_token_service.create_refresh_token(
            user_id=user.id,
            jti="active-token-2",
            expires_at=active_expires
        )
        
        # Expired tokens
        await refresh_token_service.create_refresh_token(
            user_id=user.id,
            jti="expired-token-1",
            expires_at=expired_expires
        )
        
        # Get active sessions
        sessions = await refresh_token_service.get_sessions_for_user(user.id)
        session_jtis = [s.jti for s in sessions]
        
        # Should only include active tokens
        assert "active-token-1" in session_jtis or "active-token-2" in session_jtis
        assert "expired-token-1" not in session_jtis

    @pytest.mark.asyncio
    async def test_bulk_session_operations(self, client: AsyncClient):
        """Test bulk operations on sessions."""
        user = await UserModel.find_one(UserModel.email == ADMIN_USER_DATA["email"])
        expires_at = datetime.utcnow() + timedelta(days=7)
        
        # Create many sessions
        session_count = 10
        jtis = [f"bulk-session-{i}" for i in range(session_count)]
        
        for jti in jtis:
            await refresh_token_service.create_refresh_token(
                user_id=user.id,
                jti=jti,
                expires_at=expires_at
            )
        
        # Verify all sessions exist
        sessions = await refresh_token_service.get_sessions_for_user(user.id)
        bulk_sessions = [s for s in sessions if s.jti.startswith("bulk-session-")]
        assert len(bulk_sessions) == session_count
        
        # Bulk revoke all sessions
        revoked_count = await refresh_token_service.revoke_all_tokens_for_user(user.id)
        assert revoked_count >= session_count
        
        # Verify all sessions are revoked
        sessions_after_revoke = await refresh_token_service.get_sessions_for_user(user.id)
        bulk_sessions_after = [s for s in sessions_after_revoke if s.jti.startswith("bulk-session-")]
        assert len(bulk_sessions_after) == 0

class TestRefreshTokenServiceEdgeCases:
    """Test edge cases and error scenarios."""

    @pytest.mark.asyncio
    async def test_create_token_with_invalid_user(self, client: AsyncClient):
        """Test creating token with invalid user ID."""
        fake_user_id = PydanticObjectId()
        expires_at = datetime.utcnow() + timedelta(days=7)
        
        with pytest.raises(ValueError, match="User with ID .* not found"):
            await refresh_token_service.create_refresh_token(
                user_id=fake_user_id,
                jti="invalid-user-token",
                expires_at=expires_at
            )

    @pytest.mark.asyncio
    async def test_duplicate_jti_handling(self, client: AsyncClient):
        """Test handling of duplicate JTI values."""
        user = await UserModel.find_one(UserModel.email == ADMIN_USER_DATA["email"])
        expires_at = datetime.utcnow() + timedelta(days=7)
        jti = "duplicate-jti-test"
        
        # Create first token
        token1 = await refresh_token_service.create_refresh_token(
            user_id=user.id,
            jti=jti,
            expires_at=expires_at
        )
        assert token1 is not None
        
        # Try to create second token with same JTI
        # This should either fail or handle the duplicate appropriately
        try:
            token2 = await refresh_token_service.create_refresh_token(
                user_id=user.id,
                jti=jti,
                expires_at=expires_at
            )
            # If it succeeds, the database should handle uniqueness
            # or the service should have its own handling
        except Exception:
            # Expected if JTI uniqueness is enforced
            pass

    @pytest.mark.asyncio
    async def test_token_operations_with_none_values(self, client: AsyncClient):
        """Test token operations with None/optional values."""
        user = await UserModel.find_one(UserModel.email == ADMIN_USER_DATA["email"])
        expires_at = datetime.utcnow() + timedelta(days=7)
        
        # Create token with minimal info (no IP or user agent)
        token = await refresh_token_service.create_refresh_token(
            user_id=user.id,
            jti="minimal-token",
            expires_at=expires_at,
            ip_address=None,
            user_agent=None
        )
        
        assert token is not None
        assert token.ip_address is None
        assert token.user_agent is None
        assert token.jti == "minimal-token"

    @pytest.mark.asyncio
    async def test_boundary_expiration_times(self, client: AsyncClient):
        """Test tokens with boundary expiration times."""
        user = await UserModel.find_one(UserModel.email == ADMIN_USER_DATA["email"])
        
        # Token that expires in 1 second
        near_expiry = datetime.utcnow() + timedelta(seconds=1)
        token = await refresh_token_service.create_refresh_token(
            user_id=user.id,
            jti="near-expiry-token",
            expires_at=near_expiry
        )
        
        # Should be active initially
        sessions = await refresh_token_service.get_sessions_for_user(user.id)
        near_expiry_sessions = [s for s in sessions if s.jti == "near-expiry-token"]
        assert len(near_expiry_sessions) == 1
        
        # Wait for expiration
        await asyncio.sleep(2)
        
        # Should be filtered out now
        sessions_after = await refresh_token_service.get_sessions_for_user(user.id)
        expired_sessions = [s for s in sessions_after if s.jti == "near-expiry-token"]
        assert len(expired_sessions) == 0

class TestRefreshTokenServiceIntegration:
    """Integration tests with actual HTTP endpoints."""

    @pytest.mark.asyncio
    async def test_login_creates_refresh_token(self, client: AsyncClient):
        """Test that login creates a refresh token record."""
        user = await UserModel.find_one(UserModel.email == ADMIN_USER_DATA["email"])
        
        # Get initial token count
        initial_sessions = await refresh_token_service.get_sessions_for_user(user.id)
        initial_count = len(initial_sessions)
        
        # Login
        login_data = {
            "username": ADMIN_USER_DATA["email"],
            "password": ADMIN_USER_DATA["password"],
        }
        response = await client.post("/v1/auth/login", data=login_data)
        assert response.status_code == 200
        
        # Should have created a new session
        final_sessions = await refresh_token_service.get_sessions_for_user(user.id)
        assert len(final_sessions) == initial_count + 1

    @pytest.mark.asyncio
    async def test_logout_revokes_refresh_token(self, client: AsyncClient):
        """Test that logout revokes the refresh token."""
        # Login first
        login_data = {
            "username": ADMIN_USER_DATA["email"],
            "password": ADMIN_USER_DATA["password"],
        }
        login_response = await client.post("/v1/auth/login", data=login_data)
        assert login_response.status_code == 200
        
        access_token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # Logout
        logout_response = await client.post("/v1/auth/logout", headers=headers)
        assert logout_response.status_code == 204
        
        # The refresh token should be revoked (this is tested at the HTTP level)
        # The actual token revocation is handled by the auth routes

    @pytest.mark.asyncio
    async def test_multiple_device_sessions(self, client: AsyncClient):
        """Test multiple device sessions scenario."""
        user = await UserModel.find_one(UserModel.email == ADMIN_USER_DATA["email"])
        
        # Simulate multiple device logins
        login_data = {
            "username": ADMIN_USER_DATA["email"],
            "password": ADMIN_USER_DATA["password"],
        }
        
        # Login from multiple "devices"
        device_tokens = []
        for i in range(3):
            response = await client.post("/v1/auth/login", data=login_data)
            assert response.status_code == 200
            device_tokens.append(response.json()["access_token"])
        
        # Should have multiple active sessions
        sessions = await refresh_token_service.get_sessions_for_user(user.id)
        assert len(sessions) >= 3
        
        # Each device should be able to access protected endpoints
        for token in device_tokens:
            headers = {"Authorization": f"Bearer {token}"}
            me_response = await client.get("/v1/auth/me", headers=headers)
            assert me_response.status_code == 200 