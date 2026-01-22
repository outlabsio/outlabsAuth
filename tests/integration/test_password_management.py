"""
Password Management Lifecycle Integration Tests

Tests the complete password lifecycle:
- Password change flow (user changes their own password via /me/change-password)
- Admin password reset flow (admin resets user's password via /{user_id}/password)
- Password validation enforcement
- Security behaviors around password changes

These tests ensure password management works correctly end-to-end.
"""

import uuid

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from outlabs_auth import SimpleRBAC
from outlabs_auth.fastapi import register_exception_handlers
from outlabs_auth.routers import get_auth_router, get_users_router
from outlabs_auth.utils.jwt import create_access_token

# ============================================================================
# Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def auth_instance(test_engine) -> SimpleRBAC:
    """Create SimpleRBAC instance for password testing."""
    auth = SimpleRBAC(
        engine=test_engine,
        secret_key="test-secret-key-do-not-use-in-production-12345678",
        access_token_expire_minutes=60,
        enable_token_cleanup=False,
    )
    await auth.initialize()
    yield auth
    await auth.shutdown()


@pytest_asyncio.fixture
async def app(auth_instance: SimpleRBAC) -> FastAPI:
    """Create FastAPI app with auth routers."""
    app = FastAPI()
    register_exception_handlers(app, debug=True)
    app.include_router(get_auth_router(auth_instance, prefix="/v1/auth"))
    app.include_router(get_users_router(auth_instance, prefix="/v1/users"))
    return app


@pytest_asyncio.fixture
async def client(app: FastAPI) -> httpx.AsyncClient:
    """Async HTTP client."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=True, timeout=20.0
    ) as client:
        yield client


@pytest_asyncio.fixture
async def test_user(auth_instance: SimpleRBAC) -> dict:
    """Create test user and return credentials."""
    async with auth_instance.get_session() as session:
        user = await auth_instance.user_service.create_user(
            session=session,
            email=f"testuser-{uuid.uuid4().hex[:8]}@example.com",
            password="OldPass123!",
            first_name="Test",
            last_name="User",
            is_superuser=False,
        )
        await session.commit()

        token = create_access_token(
            {"sub": str(user.id)},
            secret_key=auth_instance.config.secret_key,
            algorithm=auth_instance.config.algorithm,
        )

        return {
            "id": str(user.id),
            "email": user.email,
            "password": "OldPass123!",
            "token": token,
        }


@pytest_asyncio.fixture
async def admin_user(auth_instance: SimpleRBAC) -> dict:
    """Create admin user (superuser) and return credentials."""
    async with auth_instance.get_session() as session:
        admin = await auth_instance.user_service.create_user(
            session=session,
            email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
            password="AdminPass123!",
            first_name="Admin",
            last_name="User",
            is_superuser=True,
        )
        await session.commit()

        token = create_access_token(
            {"sub": str(admin.id)},
            secret_key=auth_instance.config.secret_key,
            algorithm=auth_instance.config.algorithm,
        )

        return {
            "id": str(admin.id),
            "email": admin.email,
            "password": "AdminPass123!",
            "token": token,
        }


# ============================================================================
# User Password Change Tests (via /users/me/change-password)
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_can_change_own_password(client: httpx.AsyncClient, test_user: dict):
    """Test that user can change their own password via POST /users/me/change-password."""
    new_password = "NewSecure123!"

    # Change password (requires current password)
    resp = await client.post(
        "/v1/users/me/change-password",
        headers={"Authorization": f"Bearer {test_user['token']}"},
        json={
            "current_password": test_user["password"],
            "new_password": new_password,
        },
    )
    assert resp.status_code == 204

    # Verify new password works
    login_resp = await client.post(
        "/v1/auth/login",
        json={"email": test_user["email"], "password": new_password},
    )
    assert login_resp.status_code == 200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_old_password_fails_after_change(
    client: httpx.AsyncClient, test_user: dict
):
    """Test that old password no longer works after changing it."""
    new_password = "NewSecure123!"
    old_password = test_user["password"]

    # Change password
    resp = await client.post(
        "/v1/users/me/change-password",
        headers={"Authorization": f"Bearer {test_user['token']}"},
        json={
            "current_password": old_password,
            "new_password": new_password,
        },
    )
    assert resp.status_code == 204

    # Old password should fail
    login_resp = await client.post(
        "/v1/auth/login",
        json={"email": test_user["email"], "password": old_password},
    )
    assert login_resp.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_wrong_current_password_rejected(
    client: httpx.AsyncClient, test_user: dict
):
    """Test that wrong current password is rejected when changing password."""
    resp = await client.post(
        "/v1/users/me/change-password",
        headers={"Authorization": f"Bearer {test_user['token']}"},
        json={
            "current_password": "WrongPassword123!",
            "new_password": "NewSecure123!",
        },
    )
    # Should be 400 or 401 (unauthorized/incorrect current password)
    assert resp.status_code in [400, 401]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_password_change_requires_authentication(client: httpx.AsyncClient):
    """Test that password change endpoint requires authentication."""
    resp = await client.post(
        "/v1/users/me/change-password",
        json={
            "current_password": "OldPass123!",
            "new_password": "NewSecure123!",
        },
    )
    assert resp.status_code == 401


# ============================================================================
# Admin Password Reset Tests (via /users/{user_id}/password)
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_can_reset_user_password(
    client: httpx.AsyncClient, admin_user: dict, test_user: dict
):
    """Test that admin can reset another user's password."""
    new_password = "AdminReset123!"

    # Admin resets user's password (doesn't require current password)
    resp = await client.patch(
        f"/v1/users/{test_user['id']}/password",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"new_password": new_password},
    )
    assert resp.status_code == 204

    # User can login with new password
    login_resp = await client.post(
        "/v1/auth/login",
        json={"email": test_user["email"], "password": new_password},
    )
    assert login_resp.status_code == 200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_non_admin_cannot_reset_other_user_password(
    client: httpx.AsyncClient, test_user: dict, auth_instance: SimpleRBAC
):
    """Test that non-admin cannot reset another user's password."""
    # Create another regular user
    async with auth_instance.get_session() as session:
        other_user = await auth_instance.user_service.create_user(
            session=session,
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
            password="OtherPass123!",
            first_name="Other",
            last_name="User",
            is_superuser=False,
        )
        await session.commit()
        other_user_id = str(other_user.id)

    # Try to reset other user's password (should fail - no user:update permission)
    resp = await client.patch(
        f"/v1/users/{other_user_id}/password",
        headers={"Authorization": f"Bearer {test_user['token']}"},
        json={"new_password": "HackedPassword123!"},
    )
    assert resp.status_code == 403


@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_reset_requires_authentication(
    client: httpx.AsyncClient, test_user: dict
):
    """Test that admin reset endpoint requires authentication."""
    resp = await client.patch(
        f"/v1/users/{test_user['id']}/password",
        json={"new_password": "NewPass123!"},
    )
    assert resp.status_code == 401


# ============================================================================
# Password Validation Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_short_new_password_rejected(client: httpx.AsyncClient, test_user: dict):
    """Test that password shorter than 8 chars is rejected by schema validation."""
    resp = await client.post(
        "/v1/users/me/change-password",
        headers={"Authorization": f"Bearer {test_user['token']}"},
        json={
            "current_password": test_user["password"],
            "new_password": "Abc12!",  # 6 chars - below schema minimum
        },
    )
    # Should be 422 (validation error) or 400
    assert resp.status_code in [400, 422]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_password_with_unicode_characters_rejected(
    client: httpx.AsyncClient, test_user: dict
):
    """Test that passwords with non-ASCII unicode characters are rejected.

    Note: The password validation requires ASCII letters only. Unicode
    characters like 'ü' are rejected to ensure consistent behavior
    across different systems and encodings.
    """
    unicode_password = "Über$ecure123!"  # Contains 'ü'

    # Change to unicode password - should be rejected
    resp = await client.post(
        "/v1/users/me/change-password",
        headers={"Authorization": f"Bearer {test_user['token']}"},
        json={
            "current_password": test_user["password"],
            "new_password": unicode_password,
        },
    )
    # Non-ASCII characters are rejected by password validation
    assert resp.status_code == 400


@pytest.mark.integration
@pytest.mark.asyncio
async def test_very_long_password_accepted(client: httpx.AsyncClient, test_user: dict):
    """Test that very long passwords are accepted (up to reasonable limit)."""
    long_password = "A" * 50 + "bcde123!"  # 58 chars

    resp = await client.post(
        "/v1/users/me/change-password",
        headers={"Authorization": f"Bearer {test_user['token']}"},
        json={
            "current_password": test_user["password"],
            "new_password": long_password,
        },
    )
    assert resp.status_code == 204

    # Login with long password
    login_resp = await client.post(
        "/v1/auth/login",
        json={"email": test_user["email"], "password": long_password},
    )
    assert login_resp.status_code == 200


# ============================================================================
# Registration Password Validation Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_registration_rejects_short_password(client: httpx.AsyncClient):
    """Test that registration rejects passwords shorter than 8 chars."""
    resp = await client.post(
        "/v1/auth/register",
        json={
            "email": f"shortpass-{uuid.uuid4().hex[:8]}@example.com",
            "password": "Abc12!",  # 6 chars
            "first_name": "Short",
            "last_name": "Password",
        },
    )
    # Schema validation should reject
    assert resp.status_code in [400, 422]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_registration_accepts_strong_password(client: httpx.AsyncClient):
    """Test that registration accepts passwords meeting requirements."""
    resp = await client.post(
        "/v1/auth/register",
        json={
            "email": f"strongpass-{uuid.uuid4().hex[:8]}@example.com",
            "password": "VeryStr0ng!Pass",
            "first_name": "Strong",
            "last_name": "Password",
        },
    )
    assert resp.status_code == 201


# ============================================================================
# Password Security Edge Cases
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_password_not_returned_in_responses(
    client: httpx.AsyncClient, test_user: dict
):
    """Test that password hash is never returned in API responses."""
    # Get user profile
    resp = await client.get(
        "/v1/users/me",
        headers={"Authorization": f"Bearer {test_user['token']}"},
    )
    data = resp.json()

    # Password fields should not be present
    assert "password" not in data
    assert "hashed_password" not in data
    assert "password_hash" not in data


@pytest.mark.integration
@pytest.mark.asyncio
async def test_password_with_special_characters(
    client: httpx.AsyncClient, test_user: dict
):
    """Test that passwords with various special characters work."""
    special_password = "P@ss!w0rd#$%^&*()_+-=[]{}|;':\",./<>?"

    resp = await client.post(
        "/v1/users/me/change-password",
        headers={"Authorization": f"Bearer {test_user['token']}"},
        json={
            "current_password": test_user["password"],
            "new_password": special_password,
        },
    )
    assert resp.status_code == 204

    # Login with special chars password
    login_resp = await client.post(
        "/v1/auth/login",
        json={"email": test_user["email"], "password": special_password},
    )
    assert login_resp.status_code == 200


# ============================================================================
# Multiple Password Changes
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_multiple_consecutive_password_changes(
    client: httpx.AsyncClient, test_user: dict
):
    """Test that multiple consecutive password changes work correctly."""
    passwords = [
        ("OldPass123!", "FirstChange123!"),
        ("FirstChange123!", "SecondChange456!"),
        ("SecondChange456!", "ThirdChange789!"),
    ]

    for current_pass, new_pass in passwords:
        # Change password
        resp = await client.post(
            "/v1/users/me/change-password",
            headers={"Authorization": f"Bearer {test_user['token']}"},
            json={
                "current_password": current_pass,
                "new_password": new_pass,
            },
        )
        assert resp.status_code == 204

        # Login with new password
        login_resp = await client.post(
            "/v1/auth/login",
            json={"email": test_user["email"], "password": new_pass},
        )
        assert login_resp.status_code == 200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_token_still_valid_after_password_change(
    client: httpx.AsyncClient, test_user: dict
):
    """Test that existing token remains valid after password change.

    Note: This tests current behavior. Some systems invalidate tokens on
    password change for security, but the default behavior here is to
    keep existing tokens valid until they expire.
    """
    # Change password
    resp = await client.post(
        "/v1/users/me/change-password",
        headers={"Authorization": f"Bearer {test_user['token']}"},
        json={
            "current_password": test_user["password"],
            "new_password": "NewPassword123!",
        },
    )
    assert resp.status_code == 204

    # Original token should still work for protected endpoints
    profile_resp = await client.get(
        "/v1/users/me",
        headers={"Authorization": f"Bearer {test_user['token']}"},
    )
    # Token remains valid (depends on implementation - adjust if needed)
    assert profile_resp.status_code == 200


# ============================================================================
# Admin Password Reset Edge Cases
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_reset_short_password_rejected(
    client: httpx.AsyncClient, admin_user: dict, test_user: dict
):
    """Test that admin cannot reset to a password shorter than 8 chars."""
    resp = await client.patch(
        f"/v1/users/{test_user['id']}/password",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"new_password": "Abc12!"},  # 6 chars
    )
    # Schema validation should reject
    assert resp.status_code in [400, 422]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_cannot_reset_nonexistent_user(
    client: httpx.AsyncClient, admin_user: dict
):
    """Test that admin cannot reset password for non-existent user."""
    fake_user_id = str(uuid.uuid4())
    resp = await client.patch(
        f"/v1/users/{fake_user_id}/password",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"new_password": "NewPassword123!"},
    )
    assert resp.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_can_reset_own_password(
    client: httpx.AsyncClient, admin_user: dict
):
    """Test that admin can reset their own password via admin endpoint."""
    new_password = "AdminNewPass123!"

    resp = await client.patch(
        f"/v1/users/{admin_user['id']}/password",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"new_password": new_password},
    )
    assert resp.status_code == 204

    # Can login with new password
    login_resp = await client.post(
        "/v1/auth/login",
        json={"email": admin_user["email"], "password": new_password},
    )
    assert login_resp.status_code == 200
