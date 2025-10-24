"""
Test login behavior with different user statuses.

Tests all 4 user statuses (ACTIVE, SUSPENDED, BANNED, DELETED) plus locked state.

Covers:
- Login with each status
- Token refresh with each status
- get_current_user() with each status
- Error messages are status-specific
"""
import pytest
from datetime import datetime, timedelta, timezone
from outlabs_auth.models.user import UserStatus
from outlabs_auth.core.exceptions import (
    AccountInactiveError,
    AccountLockedError,
    InvalidCredentialsError,
)


# ============================================================================
# ACTIVE User Tests
# ============================================================================

@pytest.mark.asyncio
async def test_active_user_can_login(auth_standard, active_user, password):
    """ACTIVE user can successfully authenticate."""
    user, tokens = await auth_standard.auth_service.login(
        email=active_user.email,
        password=password
    )

    assert user.status == UserStatus.ACTIVE
    assert tokens.access_token is not None
    assert tokens.refresh_token is not None
    assert tokens.token_type == "bearer"
    assert tokens.expires_in == 15 * 60  # 15 minutes in seconds


@pytest.mark.asyncio
async def test_active_user_can_refresh_token(auth_standard, user_with_tokens):
    """ACTIVE user can refresh access token."""
    new_tokens = await auth_standard.auth_service.refresh_access_token(
        user_with_tokens["refresh_token"]
    )

    assert new_tokens.access_token is not None
    assert new_tokens.access_token != user_with_tokens["access_token"]  # New token
    assert new_tokens.refresh_token == user_with_tokens["refresh_token"]  # Same refresh token


@pytest.mark.asyncio
async def test_active_user_get_current_user(auth_standard, user_with_tokens):
    """ACTIVE user can be retrieved via get_current_user()."""
    user = await auth_standard.auth_service.get_current_user(
        user_with_tokens["access_token"]
    )

    assert user.id == user_with_tokens["user"].id
    assert user.status == UserStatus.ACTIVE


# ============================================================================
# SUSPENDED User Tests
# ============================================================================

@pytest.mark.asyncio
async def test_suspended_user_cannot_login(auth_standard, suspended_user, password):
    """SUSPENDED user cannot authenticate."""
    with pytest.raises(AccountInactiveError) as exc_info:
        await auth_standard.auth_service.login(
            email=suspended_user.email,
            password=password
        )

    error = exc_info.value
    assert "suspended" in str(error).lower()
    assert error.details["status"] == "suspended"


@pytest.mark.asyncio
async def test_suspended_user_with_expiry_shows_date(auth_standard, suspended_user_with_expiry, password):
    """SUSPENDED user with expiry date shows suspension end time in error."""
    with pytest.raises(AccountInactiveError) as exc_info:
        await auth_standard.auth_service.login(
            email=suspended_user_with_expiry.email,
            password=password
        )

    error = exc_info.value
    assert "suspended" in str(error).lower()
    assert error.details["suspended_until"] is not None
    assert "until" in str(error).lower()


@pytest.mark.asyncio
async def test_suspended_user_cannot_refresh_token(auth_standard, active_user, password):
    """SUSPENDED user cannot refresh tokens (suspend after login)."""
    # Login as ACTIVE
    user, tokens = await auth_standard.auth_service.login(
        email=active_user.email,
        password=password
    )

    # Suspend user
    active_user.status = UserStatus.SUSPENDED
    await active_user.save()

    # Try to refresh - should fail
    with pytest.raises(AccountInactiveError) as exc_info:
        await auth_standard.auth_service.refresh_access_token(tokens.refresh_token)

    assert "suspended" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_suspended_user_get_current_user_fails(auth_standard, active_user, password):
    """SUSPENDED user's access token is invalid for get_current_user()."""
    # Login as ACTIVE
    user, tokens = await auth_standard.auth_service.login(
        email=active_user.email,
        password=password
    )

    # Suspend user
    active_user.status = UserStatus.SUSPENDED
    await active_user.save()

    # Try to get current user - should fail
    with pytest.raises(AccountInactiveError) as exc_info:
        await auth_standard.auth_service.get_current_user(tokens.access_token)

    assert "suspended" in str(exc_info.value).lower()


# ============================================================================
# BANNED User Tests
# ============================================================================

@pytest.mark.asyncio
async def test_banned_user_cannot_login(auth_standard, banned_user, password):
    """BANNED user cannot authenticate."""
    with pytest.raises(AccountInactiveError) as exc_info:
        await auth_standard.auth_service.login(
            email=banned_user.email,
            password=password
        )

    error = exc_info.value
    assert "banned" in str(error).lower()
    assert error.details["status"] == "banned"


@pytest.mark.asyncio
async def test_banned_user_cannot_refresh_token(auth_standard, active_user, password):
    """BANNED user cannot refresh tokens (ban after login)."""
    # Login as ACTIVE
    user, tokens = await auth_standard.auth_service.login(
        email=active_user.email,
        password=password
    )

    # Ban user
    active_user.status = UserStatus.BANNED
    await active_user.save()

    # Try to refresh - should fail
    with pytest.raises(AccountInactiveError) as exc_info:
        await auth_standard.auth_service.refresh_access_token(tokens.refresh_token)

    assert "banned" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_banned_user_get_current_user_fails(auth_standard, active_user, password):
    """BANNED user's access token is invalid for get_current_user()."""
    # Login as ACTIVE
    user, tokens = await auth_standard.auth_service.login(
        email=active_user.email,
        password=password
    )

    # Ban user
    active_user.status = UserStatus.BANNED
    await active_user.save()

    # Try to get current user - should fail
    with pytest.raises(AccountInactiveError) as exc_info:
        await auth_standard.auth_service.get_current_user(tokens.access_token)

    assert "banned" in str(exc_info.value).lower()


# ============================================================================
# DELETED User Tests
# ============================================================================

@pytest.mark.asyncio
async def test_deleted_user_cannot_login(auth_standard, deleted_user, password):
    """DELETED user cannot authenticate."""
    with pytest.raises(AccountInactiveError) as exc_info:
        await auth_standard.auth_service.login(
            email=deleted_user.email,
            password=password
        )

    error = exc_info.value
    assert "deleted" in str(error).lower()
    assert error.details["status"] == "deleted"
    assert error.details.get("deleted_at") is not None


@pytest.mark.asyncio
async def test_deleted_user_cannot_refresh_token(auth_standard, active_user, password):
    """DELETED user cannot refresh tokens (delete after login)."""
    # Login as ACTIVE
    user, tokens = await auth_standard.auth_service.login(
        email=active_user.email,
        password=password
    )

    # Delete user (soft delete)
    active_user.status = UserStatus.DELETED
    active_user.deleted_at = datetime.now(timezone.utc)
    await active_user.save()

    # Try to refresh - should fail
    with pytest.raises(AccountInactiveError) as exc_info:
        await auth_standard.auth_service.refresh_access_token(tokens.refresh_token)

    assert "deleted" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_deleted_user_get_current_user_fails(auth_standard, active_user, password):
    """DELETED user's access token is invalid for get_current_user()."""
    # Login as ACTIVE
    user, tokens = await auth_standard.auth_service.login(
        email=active_user.email,
        password=password
    )

    # Delete user (soft delete)
    active_user.status = UserStatus.DELETED
    active_user.deleted_at = datetime.now(timezone.utc)
    await active_user.save()

    # Try to get current user - should fail
    with pytest.raises(AccountInactiveError) as exc_info:
        await auth_standard.auth_service.get_current_user(tokens.access_token)

    assert "deleted" in str(exc_info.value).lower()


# ============================================================================
# Locked User Tests (Separate from Status)
# ============================================================================

@pytest.mark.asyncio
async def test_locked_user_cannot_login(auth_standard, locked_user, password):
    """User with too many failed attempts is locked and cannot login."""
    with pytest.raises(AccountLockedError) as exc_info:
        await auth_standard.auth_service.login(
            email=locked_user.email,
            password=password  # Even with correct password!
        )

    error = exc_info.value
    assert "locked" in str(error).lower()
    assert error.details.get("locked_until") is not None


@pytest.mark.asyncio
async def test_failed_login_increments_counter(auth_standard, active_user):
    """Failed login attempts increment counter."""
    initial_attempts = active_user.failed_login_attempts

    # Fail login
    with pytest.raises(InvalidCredentialsError):
        await auth_standard.auth_service.login(
            email=active_user.email,
            password="WrongPassword!"
        )

    # Reload user
    from outlabs_auth.models.user import UserModel
    updated_user = await UserModel.get(active_user.id)

    assert updated_user.failed_login_attempts == initial_attempts + 1


@pytest.mark.asyncio
async def test_successful_login_resets_failed_attempts(auth_standard, active_user, password):
    """Successful login resets failed attempts counter."""
    # Simulate failed attempts
    active_user.failed_login_attempts = 3
    await active_user.save()

    # Login successfully
    user, tokens = await auth_standard.auth_service.login(
        email=active_user.email,
        password=password
    )

    assert user.failed_login_attempts == 0
    assert user.locked_until is None


@pytest.mark.asyncio
async def test_max_failed_attempts_locks_account(auth_standard, active_user):
    """Reaching max failed attempts locks account."""
    max_attempts = auth_standard.config.max_login_attempts

    # Fail login max_attempts times
    for i in range(max_attempts):
        with pytest.raises(InvalidCredentialsError):
            await auth_standard.auth_service.login(
                email=active_user.email,
                password="WrongPassword!"
            )

    # Reload user
    from outlabs_auth.models.user import UserModel
    updated_user = await UserModel.get(active_user.id)

    assert updated_user.failed_login_attempts == max_attempts
    assert updated_user.locked_until is not None
    assert updated_user.is_locked is True

    # Next attempt should raise AccountLockedError
    with pytest.raises(AccountLockedError):
        await auth_standard.auth_service.login(
            email=active_user.email,
            password="Password123!"  # Correct password doesn't matter
        )


# ============================================================================
# can_authenticate() Method Tests
# ============================================================================

@pytest.mark.asyncio
async def test_can_authenticate_active_user(active_user):
    """ACTIVE user can authenticate."""
    assert active_user.can_authenticate() is True
    assert active_user.status == UserStatus.ACTIVE
    assert active_user.is_locked is False


@pytest.mark.asyncio
async def test_can_authenticate_suspended_user(suspended_user):
    """SUSPENDED user cannot authenticate."""
    assert suspended_user.can_authenticate() is False
    assert suspended_user.status == UserStatus.SUSPENDED


@pytest.mark.asyncio
async def test_can_authenticate_banned_user(banned_user):
    """BANNED user cannot authenticate."""
    assert banned_user.can_authenticate() is False
    assert banned_user.status == UserStatus.BANNED


@pytest.mark.asyncio
async def test_can_authenticate_deleted_user(deleted_user):
    """DELETED user cannot authenticate."""
    assert deleted_user.can_authenticate() is False
    assert deleted_user.status == UserStatus.DELETED


@pytest.mark.asyncio
async def test_can_authenticate_locked_active_user(locked_user):
    """ACTIVE but locked user cannot authenticate."""
    assert locked_user.can_authenticate() is False
    assert locked_user.status == UserStatus.ACTIVE  # Status is ACTIVE
    assert locked_user.is_locked is True  # But locked


@pytest.mark.asyncio
async def test_can_authenticate_locked_expired(auth_standard, active_user):
    """User with expired lockout can authenticate."""
    # Set lockout that expired 1 minute ago
    active_user.locked_until = datetime.now(timezone.utc) - timedelta(minutes=1)
    await active_user.save()

    assert active_user.is_locked is False
    assert active_user.can_authenticate() is True


# ============================================================================
# Status Transition Tests
# ============================================================================

@pytest.mark.asyncio
async def test_reactivate_suspended_user(auth_standard, suspended_user, password):
    """SUSPENDED user can be reactivated to ACTIVE."""
    # Cannot login while suspended
    with pytest.raises(AccountInactiveError):
        await auth_standard.auth_service.login(
            email=suspended_user.email,
            password=password
        )

    # Reactivate
    suspended_user.status = UserStatus.ACTIVE
    suspended_user.suspended_until = None
    await suspended_user.save()

    # Can now login
    user, tokens = await auth_standard.auth_service.login(
        email=suspended_user.email,
        password=password
    )

    assert user.status == UserStatus.ACTIVE
    assert tokens.access_token is not None


@pytest.mark.asyncio
async def test_recover_deleted_user(auth_standard, deleted_user, password):
    """DELETED user can be recovered to ACTIVE."""
    # Cannot login while deleted
    with pytest.raises(AccountInactiveError):
        await auth_standard.auth_service.login(
            email=deleted_user.email,
            password=password
        )

    # Recover account
    deleted_user.status = UserStatus.ACTIVE
    deleted_user.deleted_at = None
    await deleted_user.save()

    # Can now login
    user, tokens = await auth_standard.auth_service.login(
        email=deleted_user.email,
        password=password
    )

    assert user.status == UserStatus.ACTIVE


# ============================================================================
# Edge Cases
# ============================================================================

@pytest.mark.asyncio
async def test_login_checks_status_before_password(auth_standard, suspended_user):
    """Login checks status BEFORE verifying password (security)."""
    # Even with wrong password, should get AccountInactiveError (not InvalidCredentialsError)
    with pytest.raises(AccountInactiveError) as exc_info:
        await auth_standard.auth_service.login(
            email=suspended_user.email,
            password="WrongPassword!"
        )

    assert "suspended" in str(exc_info.value).lower()

    # Failed attempts should NOT increment for non-ACTIVE users
    from outlabs_auth.models.user import UserModel
    user = await UserModel.get(suspended_user.id)
    assert user.failed_login_attempts == 0  # Not incremented


@pytest.mark.asyncio
async def test_status_change_during_active_session(auth_standard, active_user, password):
    """Changing status during active session invalidates tokens on next use."""
    # Login
    user, tokens = await auth_standard.auth_service.login(
        email=active_user.email,
        password=password
    )

    # Access token works
    current_user = await auth_standard.auth_service.get_current_user(tokens.access_token)
    assert current_user.id == user.id

    # Change status
    active_user.status = UserStatus.BANNED
    await active_user.save()

    # Access token no longer works (status checked on each request)
    with pytest.raises(AccountInactiveError):
        await auth_standard.auth_service.get_current_user(tokens.access_token)


@pytest.mark.asyncio
async def test_multiple_users_different_statuses(auth_standard, password):
    """Multiple users with different statuses behave independently."""
    # Create 3 users with different statuses
    active = await auth_standard.user_service.create_user(
        email="multi1@test.com",
        password=password,
        first_name="Active",
        last_name="User"
    )

    suspended = await auth_standard.user_service.create_user(
        email="multi2@test.com",
        password=password,
        first_name="Suspended",
        last_name="User"
    )
    suspended.status = UserStatus.SUSPENDED
    await suspended.save()

    banned = await auth_standard.user_service.create_user(
        email="multi3@test.com",
        password=password,
        first_name="Banned",
        last_name="User"
    )
    banned.status = UserStatus.BANNED
    await banned.save()

    # ACTIVE can login
    user1, tokens1 = await auth_standard.auth_service.login(
        email=active.email,
        password=password
    )
    assert tokens1.access_token is not None

    # SUSPENDED cannot login
    with pytest.raises(AccountInactiveError):
        await auth_standard.auth_service.login(
            email=suspended.email,
            password=password
        )

    # BANNED cannot login
    with pytest.raises(AccountInactiveError):
        await auth_standard.auth_service.login(
            email=banned.email,
            password=password
        )
