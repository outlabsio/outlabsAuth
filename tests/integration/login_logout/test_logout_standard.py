"""
Standard Logout Tests (Mode 1)

Configuration:
- store_refresh_tokens=True (MongoDB storage)
- enable_token_blacklist=False (no Redis)

Expected Behavior:
- Logout revokes refresh token in MongoDB immediately
- Access token remains valid for 15 minutes (security window)
- Refresh token cannot be used after logout
- Multiple sessions can be managed independently
"""
import pytest
from datetime import datetime, timezone
from outlabs_auth.core.exceptions import RefreshTokenInvalidError
from outlabs_auth.models.token import RefreshTokenModel


@pytest.mark.asyncio
async def test_login_returns_tokens(auth_standard, active_user, password):
    """Login returns both access and refresh tokens."""
    user, tokens = await auth_standard.auth_service.login(
        email=active_user.email,
        password=password
    )

    assert tokens.access_token is not None
    assert tokens.refresh_token is not None
    assert tokens.token_type == "bearer"
    assert user.id == active_user.id


@pytest.mark.asyncio
async def test_logout_revokes_refresh_token(auth_standard, active_user, password):
    """Logout revokes the refresh token in MongoDB."""
    # Login
    user, tokens = await auth_standard.auth_service.login(
        email=active_user.email,
        password=password
    )

    # Verify refresh token is stored
    all_tokens = await RefreshTokenModel.find_all().to_list()
    assert len(all_tokens) == 1
    assert all_tokens[0].is_revoked is False

    # Logout
    result = await auth_standard.auth_service.logout(tokens.refresh_token)
    assert result is True

    # Verify token is now revoked
    all_tokens = await RefreshTokenModel.find_all().to_list()
    assert len(all_tokens) == 1
    assert all_tokens[0].is_revoked is True
    assert all_tokens[0].revoked_at is not None
    assert all_tokens[0].revoked_reason == "User logout"


@pytest.mark.asyncio
async def test_access_token_works_after_logout(auth_standard, active_user, password):
    """Access token still works after logout (15-min security window)."""
    # Login
    user, tokens = await auth_standard.auth_service.login(
        email=active_user.email,
        password=password
    )

    # Logout
    await auth_standard.auth_service.logout(tokens.refresh_token)

    # Access token should still work (15-min window)
    current_user = await auth_standard.auth_service.get_current_user(
        tokens.access_token
    )
    assert current_user.id == active_user.id


@pytest.mark.asyncio
async def test_refresh_token_fails_after_logout(auth_standard, active_user, password):
    """Refresh token cannot be used after logout."""
    # Login
    user, tokens = await auth_standard.auth_service.login(
        email=active_user.email,
        password=password
    )

    # Logout
    await auth_standard.auth_service.logout(tokens.refresh_token)

    # Refresh token should fail
    with pytest.raises(RefreshTokenInvalidError) as exc_info:
        await auth_standard.auth_service.refresh_access_token(tokens.refresh_token)

    assert "revoked" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_logout_invalid_token_returns_false(auth_standard):
    """Logout with invalid token returns False (not found)."""
    result = await auth_standard.auth_service.logout("invalid_refresh_token_123")
    assert result is False


@pytest.mark.asyncio
async def test_logout_already_revoked_token(auth_standard, active_user, password):
    """Logout of already-revoked token returns False."""
    # Login
    user, tokens = await auth_standard.auth_service.login(
        email=active_user.email,
        password=password
    )

    # First logout
    result1 = await auth_standard.auth_service.logout(tokens.refresh_token)
    assert result1 is True

    # Second logout (same token, already revoked)
    result2 = await auth_standard.auth_service.logout(tokens.refresh_token)
    assert result2 is False


@pytest.mark.asyncio
async def test_multiple_sessions_logout_one_device(auth_standard, active_user, password):
    """Logout one session does not affect other sessions."""
    # Login from "device 1"
    user1, tokens1 = await auth_standard.auth_service.login(
        email=active_user.email,
        password=password
    )

    # Login from "device 2"
    user2, tokens2 = await auth_standard.auth_service.login(
        email=active_user.email,
        password=password
    )

    # Should have 2 refresh tokens stored
    all_tokens = await RefreshTokenModel.find_all().to_list()
    assert len(all_tokens) == 2
    assert all(not t.is_revoked for t in all_tokens)

    # Logout device 1
    await auth_standard.auth_service.logout(tokens1.refresh_token)

    # Device 1 refresh token should fail
    with pytest.raises(RefreshTokenInvalidError):
        await auth_standard.auth_service.refresh_access_token(tokens1.refresh_token)

    # Device 2 should still work
    new_tokens2 = await auth_standard.auth_service.refresh_access_token(tokens2.refresh_token)
    assert new_tokens2.access_token is not None

    # Check token states
    all_tokens = await RefreshTokenModel.find_all().to_list()
    revoked_count = sum(1 for t in all_tokens if t.is_revoked)
    active_count = sum(1 for t in all_tokens if not t.is_revoked)
    assert revoked_count == 1  # Device 1 revoked
    assert active_count == 1   # Device 2 still active


@pytest.mark.asyncio
async def test_logout_blacklist_params_ignored_without_redis(auth_standard, active_user, password):
    """Blacklist parameters are ignored when Redis is not enabled."""
    # Login
    user, tokens = await auth_standard.auth_service.login(
        email=active_user.email,
        password=password
    )

    # Logout with blacklist params (should be ignored)
    result = await auth_standard.auth_service.logout(
        tokens.refresh_token,
        blacklist_access_token=True,
        access_token_jti="some_jti_123"
    )

    # Should still succeed (just ignores blacklist params)
    assert result is True

    # Refresh token should be revoked
    with pytest.raises(RefreshTokenInvalidError):
        await auth_standard.auth_service.refresh_access_token(tokens.refresh_token)

    # Access token still works (no Redis blacklist)
    current_user = await auth_standard.auth_service.get_current_user(
        tokens.access_token
    )
    assert current_user.id == active_user.id


@pytest.mark.asyncio
async def test_logout_updates_revoked_at_timestamp(auth_standard, active_user, password):
    """Logout sets revoked_at timestamp."""
    # Login
    user, tokens = await auth_standard.auth_service.login(
        email=active_user.email,
        password=password
    )

    before_logout = datetime.now(timezone.utc)

    # Logout
    await auth_standard.auth_service.logout(tokens.refresh_token)

    after_logout = datetime.now(timezone.utc)

    # Check revoked_at is set correctly
    all_tokens = await RefreshTokenModel.find_all().to_list()
    assert len(all_tokens) == 1
    token = all_tokens[0]

    assert token.revoked_at is not None
    # Ensure revoked_at is timezone-aware before comparison
    revoked_at = token.revoked_at.replace(tzinfo=timezone.utc) if token.revoked_at.tzinfo is None else token.revoked_at
    assert before_logout <= revoked_at <= after_logout


@pytest.mark.asyncio
async def test_refresh_after_logout_provides_clear_error(auth_standard, active_user, password):
    """Refresh attempt after logout provides clear error message."""
    # Login
    user, tokens = await auth_standard.auth_service.login(
        email=active_user.email,
        password=password
    )

    # Logout
    await auth_standard.auth_service.logout(tokens.refresh_token)

    # Try to refresh
    with pytest.raises(RefreshTokenInvalidError) as exc_info:
        await auth_standard.auth_service.refresh_access_token(tokens.refresh_token)

    error = exc_info.value
    assert "revoked" in str(error).lower()
    assert error.details.get("reason") == "revoked"


@pytest.mark.asyncio
async def test_multiple_users_logout_independently(auth_standard, password):
    """Multiple users can logout without affecting each other."""
    # Create two users
    user1 = await auth_standard.user_service.create_user(
        email="logout1@test.com",
        password=password,
        first_name="User",
        last_name="One"
    )

    user2 = await auth_standard.user_service.create_user(
        email="logout2@test.com",
        password=password,
        first_name="User",
        last_name="Two"
    )

    # Both login
    _, tokens1 = await auth_standard.auth_service.login(
        email=user1.email,
        password=password
    )
    _, tokens2 = await auth_standard.auth_service.login(
        email=user2.email,
        password=password
    )

    # User 1 logs out
    await auth_standard.auth_service.logout(tokens1.refresh_token)

    # User 1 cannot refresh
    with pytest.raises(RefreshTokenInvalidError):
        await auth_standard.auth_service.refresh_access_token(tokens1.refresh_token)

    # User 2 can still refresh
    new_tokens2 = await auth_standard.auth_service.refresh_access_token(tokens2.refresh_token)
    assert new_tokens2.access_token is not None
