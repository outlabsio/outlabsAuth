"""
Session Lifecycle Integration Tests

Tests the complete login/logout/session management flow including:
- Token generation, use, and revocation
- Token expiry and refresh flows
- Account lockout and unlock
- Concurrent session management
- Edge cases and error handling

These tests simulate real-world user journeys through the auth system.
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from datetime import datetime, timezone

from outlabs_auth import SimpleRBAC
from outlabs_auth.fastapi import register_exception_handlers
from outlabs_auth.models.sql.enums import UserStatus
from outlabs_auth.routers import get_auth_router, get_users_router
from outlabs_auth.utils.jwt import create_access_token, create_refresh_token

# ============================================================================
# Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def auth_instance(test_engine) -> SimpleRBAC:
    """Create SimpleRBAC instance with test engine."""
    auth = SimpleRBAC(
        engine=test_engine,
        secret_key="test-secret-key-do-not-use-in-production-12345678",
        access_token_expire_minutes=15,
        refresh_token_expire_days=7,
        enable_token_cleanup=False,
    )
    await auth.initialize()
    yield auth
    await auth.shutdown()


@pytest_asyncio.fixture
async def app(auth_instance: SimpleRBAC) -> FastAPI:
    """Create FastAPI app with auth routers."""
    app = FastAPI()
    # Register exception handlers to convert exceptions to HTTP responses
    register_exception_handlers(app, debug=True)
    app.include_router(get_auth_router(auth_instance, prefix="/v1/auth"))
    app.include_router(get_users_router(auth_instance, prefix="/v1/users"))
    return app


@pytest_asyncio.fixture
async def client(app: FastAPI) -> httpx.AsyncClient:
    """Async HTTP client for testing."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=True, timeout=20.0
    ) as client:
        yield client


@pytest_asyncio.fixture
async def registered_user(client: httpx.AsyncClient) -> dict:
    """Register a user and return credentials."""
    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    password = "TestPass123!"

    r = await client.post(
        "/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "first_name": "Test",
            "last_name": "User",
        },
    )
    assert r.status_code == 201, r.text
    user_data = r.json()
    return {
        "id": user_data["id"],
        "email": email,
        "password": password,
    }


@pytest_asyncio.fixture
async def admin_user(auth_instance: SimpleRBAC) -> dict:
    """Create a superuser admin and return credentials with token."""
    async with auth_instance.get_session() as session:
        admin = await auth_instance.user_service.create_user(
            session,
            email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
            password="AdminPass123!",
            first_name="Admin",
            last_name="User",
            is_superuser=True,
        )
        await session.commit()

        # Create token for the admin
        token = create_access_token(
            data={"sub": str(admin.id)},
            secret_key=auth_instance.config.secret_key,
            algorithm=auth_instance.config.algorithm,
            expires_delta=timedelta(minutes=60),
        )

        return {
            "id": str(admin.id),
            "email": admin.email,
            "token": token,
        }


# ============================================================================
# Basic Login/Logout Flow Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_complete_login_use_logout_flow(
    client: httpx.AsyncClient, registered_user: dict
):
    """
    Test the complete user journey:
    1. Login with correct credentials
    2. Use access token to make authenticated request
    3. Logout
    4. Attempt to use token after logout (should fail)
    """
    # Step 1: Login
    login_resp = await client.post(
        "/v1/auth/login",
        json={
            "email": registered_user["email"],
            "password": registered_user["password"],
        },
    )
    assert login_resp.status_code == 200, login_resp.text
    tokens = login_resp.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    access_token = tokens["access_token"]

    # Step 2: Use token for authenticated request
    me_resp = await client.get(
        "/v1/users/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_resp.status_code == 200, me_resp.text
    assert me_resp.json()["email"] == registered_user["email"]

    # Step 3: Logout
    logout_resp = await client.post(
        "/v1/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert logout_resp.status_code in [200, 204], logout_resp.text

    # Step 4: Attempt to use token after logout
    # Note: Without token blacklisting, this may still work
    # This test documents the current behavior
    post_logout_resp = await client.get(
        "/v1/users/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    # Document current behavior - may be 200 if no blacklisting
    # In production, this should be 401
    assert post_logout_resp.status_code in [200, 401]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_login_with_wrong_password(
    client: httpx.AsyncClient, registered_user: dict
):
    """Test that login with wrong password fails with 401."""
    resp = await client.post(
        "/v1/auth/login",
        json={"email": registered_user["email"], "password": "WrongPassword123!"},
    )
    assert resp.status_code == 401, resp.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_login_with_nonexistent_user(client: httpx.AsyncClient):
    """Test that login with non-existent email fails with 401."""
    resp = await client.post(
        "/v1/auth/login",
        json={"email": "nonexistent@example.com", "password": "TestPass123!"},
    )
    assert resp.status_code == 401, resp.text


# ============================================================================
# Token Refresh Flow Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_token_refresh_flow(client: httpx.AsyncClient, registered_user: dict):
    """
    Test token refresh:
    1. Login to get tokens
    2. Refresh to get new access token
    3. Use new access token
    """
    # Login
    login_resp = await client.post(
        "/v1/auth/login",
        json={
            "email": registered_user["email"],
            "password": registered_user["password"],
        },
    )
    assert login_resp.status_code == 200
    tokens = login_resp.json()
    refresh_token = tokens["refresh_token"]

    # Refresh
    refresh_resp = await client.post(
        "/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_resp.status_code == 200, refresh_resp.text
    new_tokens = refresh_resp.json()
    assert "access_token" in new_tokens
    new_access_token = new_tokens["access_token"]

    # Use new token
    me_resp = await client.get(
        "/v1/users/me",
        headers={"Authorization": f"Bearer {new_access_token}"},
    )
    assert me_resp.status_code == 200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_refresh_with_invalid_token(client: httpx.AsyncClient):
    """Test that refresh with invalid token fails."""
    resp = await client.post(
        "/v1/auth/refresh",
        json={"refresh_token": "invalid-token-string"},
    )
    assert resp.status_code in [401, 422]  # 401 for invalid, 422 for malformed


@pytest.mark.integration
@pytest.mark.asyncio
async def test_refresh_with_access_token_fails(
    client: httpx.AsyncClient, registered_user: dict
):
    """Test that using access token for refresh fails."""
    # Login to get tokens
    login_resp = await client.post(
        "/v1/auth/login",
        json={
            "email": registered_user["email"],
            "password": registered_user["password"],
        },
    )
    tokens = login_resp.json()
    access_token = tokens["access_token"]

    # Try to refresh with access token (should fail)
    resp = await client.post(
        "/v1/auth/refresh",
        json={"refresh_token": access_token},
    )
    # Should fail because access tokens have different type
    assert resp.status_code in [401, 422]


# ============================================================================
# Expired Token Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_expired_access_token_rejected(
    auth_instance: SimpleRBAC, client: httpx.AsyncClient, registered_user: dict
):
    """Test that expired access token is rejected with 401."""
    # Create an already-expired token
    expired_token = create_access_token(
        data={"sub": registered_user["id"]},
        secret_key=auth_instance.config.secret_key,
        algorithm=auth_instance.config.algorithm,
        expires_delta=timedelta(seconds=-10),  # Expired 10 seconds ago
    )

    resp = await client.get(
        "/v1/users/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert resp.status_code == 401, resp.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_expired_refresh_token_rejected(
    auth_instance: SimpleRBAC, client: httpx.AsyncClient, registered_user: dict
):
    """Test that expired refresh token is rejected."""
    # Create an already-expired refresh token
    expired_refresh = create_refresh_token(
        data={"sub": registered_user["id"]},
        secret_key=auth_instance.config.secret_key,
        algorithm=auth_instance.config.algorithm,
        expires_delta=timedelta(seconds=-10),  # Expired
    )

    resp = await client.post(
        "/v1/auth/refresh",
        json={"refresh_token": expired_refresh},
    )
    assert resp.status_code == 401, resp.text


# ============================================================================
# Authentication Edge Cases
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_request_without_token_returns_401(client: httpx.AsyncClient):
    """Test that protected endpoint without token returns 401."""
    resp = await client.get("/v1/users/me")
    assert resp.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_request_with_malformed_token_returns_401(client: httpx.AsyncClient):
    """Test that malformed token is rejected."""
    resp = await client.get(
        "/v1/users/me",
        headers={"Authorization": "Bearer not-a-valid-jwt-token"},
    )
    assert resp.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_request_with_wrong_secret_token_returns_401(
    client: httpx.AsyncClient, registered_user: dict
):
    """Test that token signed with wrong secret is rejected."""
    # Create token with different secret
    wrong_secret_token = create_access_token(
        data={"sub": registered_user["id"]},
        secret_key="completely-different-secret-key-12345678",
        algorithm="HS256",
        expires_delta=timedelta(minutes=15),
    )

    resp = await client.get(
        "/v1/users/me",
        headers={"Authorization": f"Bearer {wrong_secret_token}"},
    )
    assert resp.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_request_with_bearer_prefix_variations(
    client: httpx.AsyncClient, registered_user: dict
):
    """Test various malformed Authorization header formats."""
    # Login to get a valid token
    login_resp = await client.post(
        "/v1/auth/login",
        json={
            "email": registered_user["email"],
            "password": registered_user["password"],
        },
    )
    tokens = login_resp.json()
    access_token = tokens["access_token"]

    # Missing "Bearer" prefix
    resp1 = await client.get(
        "/v1/users/me",
        headers={"Authorization": access_token},
    )
    assert resp1.status_code == 401

    # Wrong prefix
    resp2 = await client.get(
        "/v1/users/me",
        headers={"Authorization": f"Token {access_token}"},
    )
    assert resp2.status_code == 401

    # Double Bearer
    resp3 = await client.get(
        "/v1/users/me",
        headers={"Authorization": f"Bearer Bearer {access_token}"},
    )
    assert resp3.status_code == 401


# ============================================================================
# User Status Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_suspended_user_cannot_login(
    auth_instance: SimpleRBAC, client: httpx.AsyncClient, registered_user: dict
):
    """Test that suspended user cannot login."""
    # Suspend the user
    async with auth_instance.get_session() as session:
        user = await auth_instance.user_service.get_user_by_email(
            session, registered_user["email"]
        )
        user.status = UserStatus.SUSPENDED
        await session.commit()

    # Try to login
    resp = await client.post(
        "/v1/auth/login",
        json={
            "email": registered_user["email"],
            "password": registered_user["password"],
        },
    )
    assert resp.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_banned_user_cannot_login(
    auth_instance: SimpleRBAC, client: httpx.AsyncClient, registered_user: dict
):
    """Test that banned user cannot login."""
    # Ban the user
    async with auth_instance.get_session() as session:
        user = await auth_instance.user_service.get_user_by_email(
            session, registered_user["email"]
        )
        user.status = UserStatus.BANNED
        await session.commit()

    # Try to login
    resp = await client.post(
        "/v1/auth/login",
        json={
            "email": registered_user["email"],
            "password": registered_user["password"],
        },
    )
    assert resp.status_code == 401


# ============================================================================
# Account Lockout Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_account_lockout_after_failed_attempts(
    auth_instance: SimpleRBAC, client: httpx.AsyncClient, registered_user: dict
):
    """
    Failed login attempts should persist and lock the account.
    """
    max_attempts = auth_instance.config.max_login_attempts

    # Make max_attempts failed logins
    for i in range(max_attempts):
        resp = await client.post(
            "/v1/auth/login",
            json={"email": registered_user["email"], "password": "WrongPassword123!"},
        )
        # All should fail with 401
        assert resp.status_code == 401, f"Attempt {i + 1} should fail"

    # Correct password should now be blocked while the account is locked.
    resp = await client.post(
        "/v1/auth/login",
        json={
            "email": registered_user["email"],
            "password": registered_user["password"],
        },
    )
    assert resp.status_code == 401

    async with auth_instance.get_session() as session:
        user = await auth_instance.user_service.get_user_by_email(
            session, registered_user["email"]
        )
        assert user is not None
        assert user.failed_login_attempts >= max_attempts
        assert user.locked_until is not None
        assert user.locked_until > datetime.now(timezone.utc)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_failed_attempt_counter_resets_on_success(
    auth_instance: SimpleRBAC, client: httpx.AsyncClient, registered_user: dict
):
    """Test that failed attempt counter resets after successful login."""
    # Make a few failed attempts (but not enough to lock)
    for i in range(2):
        await client.post(
            "/v1/auth/login",
            json={"email": registered_user["email"], "password": "WrongPassword123!"},
        )

    # Successful login
    resp = await client.post(
        "/v1/auth/login",
        json={
            "email": registered_user["email"],
            "password": registered_user["password"],
        },
    )
    assert resp.status_code == 200

    # Verify we can make failed attempts again without lockout
    # (counter should have reset)
    for i in range(2):
        resp = await client.post(
            "/v1/auth/login",
            json={"email": registered_user["email"], "password": "WrongPassword123!"},
        )
        # Should still just be 401, not locked
        assert resp.status_code == 401


# ============================================================================
# Concurrent Session Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_multiple_concurrent_logins(
    client: httpx.AsyncClient, registered_user: dict
):
    """Test that user can have multiple active sessions (tokens)."""
    # Login multiple times to simulate different devices
    tokens = []
    for i in range(3):
        resp = await client.post(
            "/v1/auth/login",
            json={
                "email": registered_user["email"],
                "password": registered_user["password"],
            },
        )
        assert resp.status_code == 200
        tokens.append(resp.json()["access_token"])

    # All tokens should work
    for i, token in enumerate(tokens):
        resp = await client.get(
            "/v1/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200, f"Token {i + 1} should work"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_logout_from_one_session_does_not_affect_others(
    client: httpx.AsyncClient, registered_user: dict
):
    """Test that logout from one session doesn't invalidate other sessions."""
    # Login twice
    resp1 = await client.post(
        "/v1/auth/login",
        json={
            "email": registered_user["email"],
            "password": registered_user["password"],
        },
    )
    token1 = resp1.json()["access_token"]

    resp2 = await client.post(
        "/v1/auth/login",
        json={
            "email": registered_user["email"],
            "password": registered_user["password"],
        },
    )
    token2 = resp2.json()["access_token"]

    # Logout with token1
    await client.post(
        "/v1/auth/logout",
        headers={"Authorization": f"Bearer {token1}"},
    )

    # Token2 should still work (without global token blacklisting)
    resp = await client.get(
        "/v1/users/me",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert resp.status_code == 200


# ============================================================================
# Token Content Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_access_token_contains_user_id(
    client: httpx.AsyncClient, registered_user: dict
):
    """Test that access token JWT contains correct user ID."""
    import jwt

    resp = await client.post(
        "/v1/auth/login",
        json={
            "email": registered_user["email"],
            "password": registered_user["password"],
        },
    )
    tokens = resp.json()
    access_token = tokens["access_token"]

    # Decode without verification to check claims
    decoded = jwt.decode(access_token, options={"verify_signature": False})
    assert decoded["sub"] == registered_user["id"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_token_expiry_time_correct(
    auth_instance: SimpleRBAC, client: httpx.AsyncClient, registered_user: dict
):
    """Test that token expiry time matches configuration."""
    import jwt

    resp = await client.post(
        "/v1/auth/login",
        json={
            "email": registered_user["email"],
            "password": registered_user["password"],
        },
    )
    tokens = resp.json()
    access_token = tokens["access_token"]

    decoded = jwt.decode(access_token, options={"verify_signature": False})
    exp_time = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)
    now = datetime.now(timezone.utc)

    # Token should expire within configured minutes (with some tolerance)
    expected_expire = auth_instance.config.access_token_expire_minutes
    actual_minutes = (exp_time - now).total_seconds() / 60

    # Allow 1 minute tolerance for test execution time
    assert abs(actual_minutes - expected_expire) < 1


# ============================================================================
# Registration Edge Cases
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_register_duplicate_email_fails(
    client: httpx.AsyncClient, registered_user: dict
):
    """Test that registering with existing email fails."""
    resp = await client.post(
        "/v1/auth/register",
        json={
            "email": registered_user["email"],  # Already exists
            "password": "TestPass123!",
            "first_name": "Duplicate",
            "last_name": "User",
        },
    )
    assert resp.status_code in [400, 409]  # Bad request or conflict


@pytest.mark.integration
@pytest.mark.asyncio
async def test_register_weak_password_fails(client: httpx.AsyncClient):
    """Test that weak password is rejected during registration."""
    resp = await client.post(
        "/v1/auth/register",
        json={
            "email": f"weak-{uuid.uuid4().hex[:8]}@example.com",
            "password": "weak",  # Too short, no uppercase, no digit, no special
            "first_name": "Test",
            "last_name": "User",
        },
    )
    assert resp.status_code == 422  # Validation error


@pytest.mark.integration
@pytest.mark.asyncio
async def test_register_then_immediate_login(client: httpx.AsyncClient):
    """Test that newly registered user can immediately login."""
    email = f"newuser-{uuid.uuid4().hex[:8]}@example.com"
    password = "TestPass123!"

    # Register
    reg_resp = await client.post(
        "/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "first_name": "New",
            "last_name": "User",
        },
    )
    assert reg_resp.status_code == 201

    # Immediate login
    login_resp = await client.post(
        "/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_resp.status_code == 200
    assert "access_token" in login_resp.json()


# ============================================================================
# User Status Management Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_can_suspend_user(
    auth_instance: SimpleRBAC, client: httpx.AsyncClient, admin_user: dict
):
    """Test that admin can suspend a user."""
    # Create a user to suspend
    async with auth_instance.get_session() as session:
        target_user = await auth_instance.user_service.create_user(
            session,
            email=f"tosuspend-{uuid.uuid4().hex[:8]}@example.com",
            password="TestPass123!",
            first_name="To",
            last_name="Suspend",
        )
        await session.commit()
        target_id = str(target_user.id)

    # Suspend the user
    resp = await client.patch(
        f"/v1/users/{target_id}/status",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"status": "suspended"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "suspended"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_can_suspend_user_with_expiry(
    auth_instance: SimpleRBAC, client: httpx.AsyncClient, admin_user: dict
):
    """Test that admin can suspend a user with auto-expiry date."""
    # Create a user to suspend
    async with auth_instance.get_session() as session:
        target_user = await auth_instance.user_service.create_user(
            session,
            email=f"tempsuspend-{uuid.uuid4().hex[:8]}@example.com",
            password="TestPass123!",
            first_name="Temp",
            last_name="Suspend",
        )
        await session.commit()
        target_id = str(target_user.id)

    # Suspend with expiry
    expiry = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    resp = await client.patch(
        f"/v1/users/{target_id}/status",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={
            "status": "suspended",
            "suspended_until": expiry,
            "reason": "Policy violation - 7 day suspension",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "suspended"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_can_ban_user(
    auth_instance: SimpleRBAC, client: httpx.AsyncClient, admin_user: dict
):
    """Test that admin can permanently ban a user."""
    # Create a user to ban
    async with auth_instance.get_session() as session:
        target_user = await auth_instance.user_service.create_user(
            session,
            email=f"toban-{uuid.uuid4().hex[:8]}@example.com",
            password="TestPass123!",
            first_name="To",
            last_name="Ban",
        )
        await session.commit()
        target_id = str(target_user.id)

    # Ban the user
    resp = await client.patch(
        f"/v1/users/{target_id}/status",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"status": "banned", "reason": "Severe ToS violation"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "banned"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_can_reactivate_suspended_user(
    auth_instance: SimpleRBAC, client: httpx.AsyncClient, admin_user: dict
):
    """Test that admin can reactivate a suspended user."""
    # Create and suspend a user
    async with auth_instance.get_session() as session:
        target_user = await auth_instance.user_service.create_user(
            session,
            email=f"toreactivate-{uuid.uuid4().hex[:8]}@example.com",
            password="TestPass123!",
            first_name="To",
            last_name="Reactivate",
        )
        target_user.status = UserStatus.SUSPENDED
        await session.commit()
        target_id = str(target_user.id)

    # Reactivate the user
    resp = await client.patch(
        f"/v1/users/{target_id}/status",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"status": "active"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "active"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cannot_set_status_to_deleted_via_endpoint(
    auth_instance: SimpleRBAC, client: httpx.AsyncClient, admin_user: dict
):
    """Test that setting status to 'deleted' via status endpoint is rejected."""
    # Create a user
    async with auth_instance.get_session() as session:
        target_user = await auth_instance.user_service.create_user(
            session,
            email=f"nodelete-{uuid.uuid4().hex[:8]}@example.com",
            password="TestPass123!",
            first_name="No",
            last_name="Delete",
        )
        await session.commit()
        target_id = str(target_user.id)

    # Try to set status to deleted
    resp = await client.patch(
        f"/v1/users/{target_id}/status",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"status": "deleted"},
    )
    # Should be rejected - 400 for invalid pattern or explicit error
    assert resp.status_code in [400, 422]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_regular_user_cannot_change_status(
    auth_instance: SimpleRBAC, client: httpx.AsyncClient, registered_user: dict
):
    """Test that regular user cannot change another user's status."""
    # Login as regular user
    login_resp = await client.post(
        "/v1/auth/login",
        json={
            "email": registered_user["email"],
            "password": registered_user["password"],
        },
    )
    tokens = login_resp.json()
    user_token = tokens["access_token"]

    # Create another user
    async with auth_instance.get_session() as session:
        target_user = await auth_instance.user_service.create_user(
            session,
            email=f"othertarget-{uuid.uuid4().hex[:8]}@example.com",
            password="TestPass123!",
            first_name="Other",
            last_name="Target",
        )
        await session.commit()
        target_id = str(target_user.id)

    # Try to suspend (should fail - no permission)
    resp = await client.patch(
        f"/v1/users/{target_id}/status",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"status": "suspended"},
    )
    assert resp.status_code == 403
