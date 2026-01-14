"""
Stateless Logout Tests (Mode 3)

Configuration:
- store_refresh_tokens=False (no MongoDB storage)
- enable_token_blacklist=False (no Redis)

Expected Behavior:
- Logout returns success but cannot actually revoke tokens
- Both access and refresh tokens work until expiration
- No tokens stored in MongoDB
- True stateless JWT behavior
"""
import pytest
from outlabs_auth.models.token import RefreshTokenModel


@pytest.mark.asyncio
async def test_login_returns_tokens(auth_stateless, active_user, password):
    """Login returns both access and refresh tokens."""
    user, tokens = await auth_stateless.auth_service.login(
        email=active_user.email,
        password=password
    )

    assert tokens.access_token is not None
    assert tokens.refresh_token is not None
    assert tokens.token_type == "bearer"
    assert user.id == active_user.id


@pytest.mark.asyncio
async def test_login_does_not_store_refresh_tokens(auth_stateless, active_user, password):
    """Login does not store refresh tokens in MongoDB."""
    # Login
    user, tokens = await auth_stateless.auth_service.login(
        email=active_user.email,
        password=password
    )

    # No tokens should be stored in MongoDB
    all_tokens = await RefreshTokenModel.find_all().to_list()
    assert len(all_tokens) == 0


@pytest.mark.asyncio
async def test_multiple_logins_no_storage(auth_stateless, active_user, password):
    """Multiple logins do not create token records."""
    # Login 3 times
    for i in range(3):
        await auth_stateless.auth_service.login(
            email=active_user.email,
            password=password
        )

    # Still no tokens in MongoDB
    all_tokens = await RefreshTokenModel.find_all().to_list()
    assert len(all_tokens) == 0


@pytest.mark.asyncio
async def test_logout_returns_false_without_storage(auth_stateless, active_user, password):
    """Logout returns False when token storage is disabled."""
    # Login
    user, tokens = await auth_stateless.auth_service.login(
        email=active_user.email,
        password=password
    )

    # Logout (should return False because can't revoke)
    result = await auth_stateless.auth_service.logout(tokens.refresh_token)
    assert result is False


@pytest.mark.asyncio
async def test_access_token_works_after_logout(auth_stateless, active_user, password):
    """Access token still works after logout (cannot be revoked)."""
    # Login
    user, tokens = await auth_stateless.auth_service.login(
        email=active_user.email,
        password=password
    )

    # Logout (does nothing)
    await auth_stateless.auth_service.logout(tokens.refresh_token)

    # Access token still works
    current_user = await auth_stateless.auth_service.get_current_user(
        tokens.access_token
    )
    assert current_user.id == active_user.id


@pytest.mark.asyncio
async def test_refresh_token_works_after_logout(auth_stateless, active_user, password):
    """Refresh token still works after logout (cannot be revoked)."""
    # Login
    user, tokens = await auth_stateless.auth_service.login(
        email=active_user.email,
        password=password
    )

    # Logout (does nothing)
    await auth_stateless.auth_service.logout(tokens.refresh_token)

    # Refresh token still works
    new_tokens = await auth_stateless.auth_service.refresh_access_token(
        tokens.refresh_token
    )
    assert new_tokens.access_token is not None
    assert new_tokens.access_token != tokens.access_token  # New token generated


@pytest.mark.asyncio
async def test_logout_with_blacklist_params_ignored(auth_stateless, active_user, password):
    """Logout with blacklist parameters is ignored (no Redis)."""
    # Login
    user, tokens = await auth_stateless.auth_service.login(
        email=active_user.email,
        password=password
    )

    # Logout with blacklist params (should be ignored)
    result = await auth_stateless.auth_service.logout(
        tokens.refresh_token,
        blacklist_access_token=True,
        access_token_jti="some_jti"
    )

    # Returns False (can't revoke refresh token without storage)
    assert result is False

    # Both tokens still work
    current_user = await auth_stateless.auth_service.get_current_user(
        tokens.access_token
    )
    assert current_user.id == active_user.id

    new_tokens = await auth_stateless.auth_service.refresh_access_token(
        tokens.refresh_token
    )
    assert new_tokens.access_token is not None


@pytest.mark.asyncio
async def test_stateless_tokens_are_independent(auth_stateless, active_user, password):
    """Each login creates independent tokens that don't interfere."""
    # Login from "device 1"
    user1, tokens1 = await auth_stateless.auth_service.login(
        email=active_user.email,
        password=password
    )

    # Login from "device 2"
    user2, tokens2 = await auth_stateless.auth_service.login(
        email=active_user.email,
        password=password
    )

    # Both access tokens work
    current_user1 = await auth_stateless.auth_service.get_current_user(tokens1.access_token)
    current_user2 = await auth_stateless.auth_service.get_current_user(tokens2.access_token)
    assert current_user1.id == active_user.id
    assert current_user2.id == active_user.id

    # Both refresh tokens work
    new_tokens1 = await auth_stateless.auth_service.refresh_access_token(tokens1.refresh_token)
    new_tokens2 = await auth_stateless.auth_service.refresh_access_token(tokens2.refresh_token)
    assert new_tokens1.access_token is not None
    assert new_tokens2.access_token is not None

    # Tokens are different
    assert tokens1.access_token != tokens2.access_token
    assert tokens1.refresh_token != tokens2.refresh_token


@pytest.mark.asyncio
async def test_stateless_no_session_tracking(auth_stateless, password):
    """Multiple users have no session tracking in database."""
    # Create two users
    user1 = await auth_stateless.user_service.create_user(
        email="stateless1@test.com",
        password=password,
        first_name="User",
        last_name="One"
    )

    user2 = await auth_stateless.user_service.create_user(
        email="stateless2@test.com",
        password=password,
        first_name="User",
        last_name="Two"
    )

    # Both login multiple times
    for i in range(3):
        await auth_stateless.auth_service.login(email=user1.email, password=password)
        await auth_stateless.auth_service.login(email=user2.email, password=password)

    # No tokens in database
    all_tokens = await RefreshTokenModel.find_all().to_list()
    assert len(all_tokens) == 0


@pytest.mark.asyncio
async def test_stateless_security_tradeoff(auth_stateless, active_user, password):
    """
    Stateless mode security tradeoff:
    - Cannot revoke tokens before expiration
    - Must rely on short token lifetimes
    - Good for performance, bad for immediate revocation needs
    """
    # Login
    user, tokens = await auth_stateless.auth_service.login(
        email=active_user.email,
        password=password
    )

    # Simulate security breach - try to logout
    logout_result = await auth_stateless.auth_service.logout(tokens.refresh_token)
    assert logout_result is False  # Cannot revoke

    # Tokens still work (security window = token lifetime)
    current_user = await auth_stateless.auth_service.get_current_user(tokens.access_token)
    assert current_user.id == active_user.id

    # This is the tradeoff: performance vs. security
    # Stateless = fast but can't revoke
    # Standard = slower but can revoke
