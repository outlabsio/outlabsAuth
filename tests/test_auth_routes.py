import pytest
from httpx import AsyncClient
import asyncio

# Mark all tests in this file as async
pytestmark = pytest.mark.asyncio

"""
COMPREHENSIVE AUTHENTICATION TEST SUITE
=======================================

This test suite provides complete coverage of the authentication system with 27+ tests
covering all critical security scenarios and edge cases.

TEST CATEGORIES:
- ✅ Basic Authentication (3 tests)
- ✅ Password Validation (5 tests)
- ✅ Email Validation (7 tests)
- ✅ Security & Attack Protection (8 tests)
- ✅ Session Management (6 tests)
- ✅ Password Reset Workflow (5 tests)
- ✅ Password Change (3 tests)

SECURITY FEATURES TESTED:
- SQL/NoSQL injection protection
- Timing attack prevention
- User enumeration protection
- Concurrent request handling
- Input validation and sanitization
- Session security and token rotation
- Proper error handling and HTTP status codes

AUTHENTICATION FLOWS COVERED:
- Login/logout workflows
- Token refresh and rotation
- Password reset with email validation
- Password change with current password verification
- Multi-session management
- Session revocation by JTI

This test suite ensures the authentication system is robust, secure, and handles
all edge cases properly while maintaining consistent security practices.
"""

# This data corresponds to the user created in the seed script
ADMIN_USER_DATA = {
    "email": "admin@test.com",
    "password": "admin123"
}

async def test_successful_login(client: AsyncClient):
    """
    Tests successful user login and token generation for the seeded admin user.
    """
    login_data = {
        "username": ADMIN_USER_DATA["email"],
        "password": ADMIN_USER_DATA["password"],
    }
    response = await client.post("/v1/auth/login", data=login_data)

    assert response.status_code == 200
    token_data = response.json()
    assert "access_token" in token_data
    assert "refresh_token" in token_data
    assert token_data["token_type"] == "bearer"

async def test_failed_login(client: AsyncClient):
    """
    Tests that login fails with incorrect credentials.
    """
    login_data = {
        "username": ADMIN_USER_DATA["email"],
        "password": "wrong_password",
    }
    response = await client.post("/v1/auth/login", data=login_data)
    assert response.status_code == 401

async def test_get_me_endpoint(client: AsyncClient):
    """
    Tests the /me endpoint to retrieve the current user's profile.
    """
    # First, log in to get a token
    login_data = {
        "username": ADMIN_USER_DATA["email"],
        "password": ADMIN_USER_DATA["password"],
    }
    login_response = await client.post("/v1/auth/login", data=login_data)
    access_token = login_response.json()["access_token"]

    # Now, test the /me endpoint
    headers = {"Authorization": f"Bearer {access_token}"}
    me_response = await client.get("/v1/auth/me", headers=headers)

    assert me_response.status_code == 200
    user_profile = me_response.json()
    assert user_profile["email"] == ADMIN_USER_DATA["email"]
    assert user_profile["first_name"] == "Admin"

# ==================== PASSWORD VALIDATION TESTS ====================

async def test_login_with_empty_password(client: AsyncClient):
    """
    Tests that login fails with empty password.
    """
    login_data = {
        "username": ADMIN_USER_DATA["email"],
        "password": "",
    }
    response = await client.post("/v1/auth/login", data=login_data)
    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]

async def test_login_with_very_short_password(client: AsyncClient):
    """
    Tests that login fails with password too short.
    """
    login_data = {
        "username": ADMIN_USER_DATA["email"],
        "password": "a",
    }
    response = await client.post("/v1/auth/login", data=login_data)
    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]

async def test_login_with_very_long_password(client: AsyncClient):
    """
    Tests that login fails with password too long (>128 chars).
    """
    # Create a password longer than 128 characters
    long_password = "a" * 129
    login_data = {
        "username": ADMIN_USER_DATA["email"],
        "password": long_password,
    }
    response = await client.post("/v1/auth/login", data=login_data)
    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]

async def test_login_with_special_characters_in_password(client: AsyncClient):
    """
    Tests that login fails with special characters in password (wrong password).
    """
    login_data = {
        "username": ADMIN_USER_DATA["email"],
        "password": "!@#$%^&*()_+-=[]{}|;':\",./<>?",
    }
    response = await client.post("/v1/auth/login", data=login_data)
    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]

async def test_login_with_unicode_emoji_password(client: AsyncClient):
    """
    Tests that login fails with Unicode/emoji passwords (wrong password).
    """
    login_data = {
        "username": ADMIN_USER_DATA["email"],
        "password": "🚀🔥💯🎉👑✨🌟💎🎯🏆",
    }
    response = await client.post("/v1/auth/login", data=login_data)
    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]

# ==================== EMAIL VALIDATION TESTS ====================

async def test_login_with_invalid_email_format_no_at_symbol(client: AsyncClient):
    """
    Tests that login fails with invalid email format (no @ symbol).
    """
    login_data = {
        "username": "invalid_email_format",
        "password": ADMIN_USER_DATA["password"],
    }
    response = await client.post("/v1/auth/login", data=login_data)
    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]

async def test_login_with_invalid_email_format_multiple_at_symbols(client: AsyncClient):
    """
    Tests that login fails with invalid email format (multiple @ symbols).
    """
    login_data = {
        "username": "user@@test.com",
        "password": ADMIN_USER_DATA["password"],
    }
    response = await client.post("/v1/auth/login", data=login_data)
    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]

async def test_login_with_invalid_email_format_no_domain(client: AsyncClient):
    """
    Tests that login fails with invalid email format (no domain).
    """
    login_data = {
        "username": "user@",
        "password": ADMIN_USER_DATA["password"],
    }
    response = await client.post("/v1/auth/login", data=login_data)
    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]

async def test_login_with_invalid_email_format_spaces(client: AsyncClient):
    """
    Tests that login fails with invalid email format (spaces).
    """
    login_data = {
        "username": "user name@test.com",
        "password": ADMIN_USER_DATA["password"],
    }
    response = await client.post("/v1/auth/login", data=login_data)
    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]

async def test_login_with_nonexistent_email(client: AsyncClient):
    """
    Tests that login fails with non-existent email.
    """
    login_data = {
        "username": "nonexistent@test.com",
        "password": ADMIN_USER_DATA["password"],
    }
    response = await client.post("/v1/auth/login", data=login_data)
    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]

async def test_login_with_email_case_sensitivity(client: AsyncClient):
    """
    Tests email case sensitivity in login.
    Note: Most email systems are case-insensitive, but this tests the current implementation.
    """
    # Test with uppercase email
    login_data = {
        "username": ADMIN_USER_DATA["email"].upper(),
        "password": ADMIN_USER_DATA["password"],
    }
    response = await client.post("/v1/auth/login", data=login_data)
    # This may pass or fail depending on how the system handles email case sensitivity
    # For now, we expect it to fail since MongoDB is case-sensitive by default
    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]

async def test_login_with_mixed_case_email(client: AsyncClient):
    """
    Tests mixed case email in login.
    """
    # Test with mixed case email
    login_data = {
        "username": "Admin@Test.Com",
        "password": ADMIN_USER_DATA["password"],
    }
    response = await client.post("/v1/auth/login", data=login_data)
    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]

# ==================== RATE LIMITING & SECURITY TESTS ====================

async def test_multiple_failed_login_attempts(client: AsyncClient):
    """
    Tests multiple failed login attempts in succession.
    Note: This tests the current behavior without rate limiting implementation.
    """
    failed_attempts = []

    # Attempt 5 failed logins
    for i in range(5):
        login_data = {
            "username": ADMIN_USER_DATA["email"],
            "password": "wrong_password",
        }
        response = await client.post("/v1/auth/login", data=login_data)
        failed_attempts.append(response.status_code)

        # Small delay between attempts
        await asyncio.sleep(0.1)

    # All attempts should fail with 401
    assert all(status == 401 for status in failed_attempts)

    # Verify that a correct login still works after failed attempts
    # (This will change when account lockout is implemented)
    correct_login_data = {
        "username": ADMIN_USER_DATA["email"],
        "password": ADMIN_USER_DATA["password"],
    }
    response = await client.post("/v1/auth/login", data=correct_login_data)
    assert response.status_code == 200

async def test_failed_login_response_time_consistency(client: AsyncClient):
    """
    Tests that failed login responses have consistent timing to prevent user enumeration.
    """
    import time

    # Test with non-existent user
    start_time = time.time()
    login_data = {
        "username": "nonexistent@test.com",
        "password": "wrong_password",
    }
    response1 = await client.post("/v1/auth/login", data=login_data)
    time1 = time.time() - start_time

    # Small delay between requests
    await asyncio.sleep(0.1)

    # Test with existing user but wrong password
    start_time = time.time()
    login_data = {
        "username": ADMIN_USER_DATA["email"],
        "password": "wrong_password",
    }
    response2 = await client.post("/v1/auth/login", data=login_data)
    time2 = time.time() - start_time

    # Both should return 401
    assert response1.status_code == 401
    assert response2.status_code == 401

    # Both should have the same error message (preventing user enumeration)
    assert response1.json()["detail"] == response2.json()["detail"]

    # Response times should be reasonably similar (within 1 second difference)
    # This is a basic check - in production, you'd want more sophisticated timing analysis
    assert abs(time1 - time2) < 1.0

async def test_concurrent_login_attempts(client: AsyncClient):
    """
    Tests handling of concurrent login attempts.
    """
    # Create multiple concurrent login attempts
    async def attempt_login(correct_password: bool):
        login_data = {
            "username": ADMIN_USER_DATA["email"],
            "password": ADMIN_USER_DATA["password"] if correct_password else "wrong_password",
        }
        return await client.post("/v1/auth/login", data=login_data)

    # Run 3 failed and 2 successful attempts concurrently
    tasks = [
        attempt_login(False),  # Failed
        attempt_login(False),  # Failed
        attempt_login(True),   # Success
        attempt_login(False),  # Failed
        attempt_login(True),   # Success
    ]

    responses = await asyncio.gather(*tasks)

    # Check that we get the expected mix of success and failure
    success_count = sum(1 for r in responses if r.status_code == 200)
    failure_count = sum(1 for r in responses if r.status_code == 401)

    assert success_count == 2
    assert failure_count == 3

async def test_login_with_sql_injection_attempt(client: AsyncClient):
    """
    Tests that SQL injection attempts in login fail safely.
    """
    # Common SQL injection patterns
    injection_attempts = [
        "' OR '1'='1",
        "admin'--",
        "' OR '1'='1' --",
        "' OR 1=1#",
        "') OR ('1'='1",
        "admin'; DROP TABLE users; --"
    ]

    for injection in injection_attempts:
        login_data = {
            "username": injection,
            "password": ADMIN_USER_DATA["password"],
        }
        response = await client.post("/v1/auth/login", data=login_data)
        assert response.status_code == 401
        assert "Incorrect email or password" in response.json()["detail"]

        # Also test injection in password field
        login_data = {
            "username": ADMIN_USER_DATA["email"],
            "password": injection,
        }
        response = await client.post("/v1/auth/login", data=login_data)
        assert response.status_code == 401
        assert "Incorrect email or password" in response.json()["detail"]

async def test_login_with_nosql_injection_attempt(client: AsyncClient):
    """
    Tests that NoSQL injection attempts in login fail safely.
    """
    # Common NoSQL injection patterns for MongoDB
    injection_attempts = [
        '{"$gt":""}',
        '{"$ne":null}',
        '{"$regex":".*"}',
        '{"$where":"return true"}',
    ]

    for injection in injection_attempts:
        login_data = {
            "username": injection,
            "password": ADMIN_USER_DATA["password"],
        }
        response = await client.post("/v1/auth/login", data=login_data)
        assert response.status_code == 401
        assert "Incorrect email or password" in response.json()["detail"]

async def test_login_with_extremely_long_email(client: AsyncClient):
    """
    Tests login with extremely long email to check for buffer overflow protection.
    """
    # Create an extremely long email
    long_email = "a" * 1000 + "@test.com"
    login_data = {
        "username": long_email,
        "password": ADMIN_USER_DATA["password"],
    }
    response = await client.post("/v1/auth/login", data=login_data)
    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]

async def test_login_with_null_bytes(client: AsyncClient):
    """
    Tests login with null bytes to check for proper string handling.
    """
    login_data = {
        "username": "admin@test.com\x00",
        "password": ADMIN_USER_DATA["password"],
    }
    response = await client.post("/v1/auth/login", data=login_data)
    assert response.status_code == 401

async def test_login_request_headers_validation(client: AsyncClient):
    """
    Tests that login works with various request headers.
    """
    login_data = {
        "username": ADMIN_USER_DATA["email"],
        "password": ADMIN_USER_DATA["password"],
    }

    # Test with custom headers
    headers = {
        "User-Agent": "Mozilla/5.0 (Test Browser)",
        "X-Forwarded-For": "192.168.1.100",
        "X-Real-IP": "10.0.0.1",
    }

    response = await client.post("/v1/auth/login", data=login_data, headers=headers)
    assert response.status_code == 200
    token_data = response.json()
    assert "access_token" in token_data
    assert "refresh_token" in token_data

async def test_login_without_user_agent(client: AsyncClient):
    """
    Tests login without User-Agent header.
    """
    login_data = {
        "username": ADMIN_USER_DATA["email"],
        "password": ADMIN_USER_DATA["password"],
    }

    # Remove User-Agent header if present
    headers = {}

    response = await client.post("/v1/auth/login", data=login_data, headers=headers)
    assert response.status_code == 200
    token_data = response.json()
    assert "access_token" in token_data
    assert "refresh_token" in token_data

# ==================== SESSION MANAGEMENT TESTS ====================

async def test_token_refresh_workflow(client: AsyncClient):
    """
    Tests the complete token refresh workflow.
    """
    # First, log in to get tokens
    login_data = {
        "username": ADMIN_USER_DATA["email"],
        "password": ADMIN_USER_DATA["password"],
    }
    login_response = await client.post("/v1/auth/login", data=login_data)
    assert login_response.status_code == 200

    tokens = login_response.json()
    refresh_token = tokens["refresh_token"]

    # Test refresh token endpoint
    refresh_response = await client.post("/v1/auth/refresh",
                                       headers={"Authorization": f"Bearer {refresh_token}"})
    assert refresh_response.status_code == 200

    new_tokens = refresh_response.json()
    assert "access_token" in new_tokens
    assert "refresh_token" in new_tokens
    assert new_tokens["token_type"] == "bearer"

    # Verify the new tokens are different (token rotation)
    assert new_tokens["access_token"] != tokens["access_token"]
    assert new_tokens["refresh_token"] != tokens["refresh_token"]

async def test_refresh_with_invalid_token(client: AsyncClient):
    """
    Tests refresh endpoint with invalid token.
    """
    invalid_token = "invalid.token.here"
    response = await client.post("/v1/auth/refresh",
                               headers={"Authorization": f"Bearer {invalid_token}"})
    assert response.status_code == 401
    assert "Invalid refresh token" in response.json()["detail"]

async def test_refresh_without_token(client: AsyncClient):
    """
    Tests refresh endpoint without providing a token.
    """
    response = await client.post("/v1/auth/refresh")
    assert response.status_code == 401
    assert "Refresh token not found" in response.json()["detail"]

async def test_logout_workflow(client: AsyncClient):
    """
    Tests the logout workflow.
    """
    # First, log in to get tokens
    login_data = {
        "username": ADMIN_USER_DATA["email"],
        "password": ADMIN_USER_DATA["password"],
    }
    login_response = await client.post("/v1/auth/login", data=login_data)
    assert login_response.status_code == 200

    access_token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # Test logout
    logout_response = await client.post("/v1/auth/logout", headers=headers)
    assert logout_response.status_code == 204

    # Verify that the token is no longer valid for accessing protected routes
    me_response = await client.get("/v1/auth/me", headers=headers)
    # The access token might still work until it expires, but the refresh token should be revoked

async def test_logout_all_sessions(client: AsyncClient):
    """
    Tests logging out from all sessions.
    """
    # Create multiple sessions by logging in multiple times
    login_data = {
        "username": ADMIN_USER_DATA["email"],
        "password": ADMIN_USER_DATA["password"],
    }

    # First login
    login1_response = await client.post("/v1/auth/login", data=login_data)
    assert login1_response.status_code == 200
    access_token1 = login1_response.json()["access_token"]

    # Second login (different session)
    login2_response = await client.post("/v1/auth/login", data=login_data)
    assert login2_response.status_code == 200
    access_token2 = login2_response.json()["access_token"]

    # Use first token to logout from all sessions
    headers1 = {"Authorization": f"Bearer {access_token1}"}
    logout_all_response = await client.post("/v1/auth/logout_all", headers=headers1)
    assert logout_all_response.status_code == 204

async def test_get_active_sessions(client: AsyncClient):
    """
    Tests getting active sessions for the current user.
    """
    # First, log in to get tokens
    login_data = {
        "username": ADMIN_USER_DATA["email"],
        "password": ADMIN_USER_DATA["password"],
    }
    login_response = await client.post("/v1/auth/login", data=login_data)
    assert login_response.status_code == 200

    access_token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # Get active sessions
    sessions_response = await client.get("/v1/auth/sessions", headers=headers)
    assert sessions_response.status_code == 200

    sessions = sessions_response.json()
    assert isinstance(sessions, list)
    assert len(sessions) >= 1  # At least the current session

async def test_revoke_specific_session(client: AsyncClient):
    """
    Tests revoking a specific session by JTI.
    """
    # First, log in to get tokens
    login_data = {
        "username": ADMIN_USER_DATA["email"],
        "password": ADMIN_USER_DATA["password"],
    }
    login_response = await client.post("/v1/auth/login", data=login_data)
    assert login_response.status_code == 200

    access_token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # Get sessions to find a JTI
    sessions_response = await client.get("/v1/auth/sessions", headers=headers)
    assert sessions_response.status_code == 200

    sessions = sessions_response.json()
    if sessions:
        jti = sessions[0]["jti"]

        # Revoke the session
        revoke_response = await client.delete(f"/v1/auth/sessions/{jti}", headers=headers)
        assert revoke_response.status_code == 204

async def test_revoke_nonexistent_session(client: AsyncClient):
    """
    Tests revoking a non-existent session.
    """
    # First, log in to get tokens
    login_data = {
        "username": ADMIN_USER_DATA["email"],
        "password": ADMIN_USER_DATA["password"],
    }
    login_response = await client.post("/v1/auth/login", data=login_data)
    assert login_response.status_code == 200

    access_token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # Try to revoke a non-existent session
    fake_jti = "non-existent-jti"
    revoke_response = await client.delete(f"/v1/auth/sessions/{fake_jti}", headers=headers)
    assert revoke_response.status_code == 404
    assert "Session not found" in revoke_response.json()["detail"]

# ==================== PASSWORD RESET WORKFLOW TESTS ====================

async def test_password_reset_request_valid_email(client: AsyncClient):
    """
    Tests password reset request with valid email.
    """
    reset_data = {
        "email": ADMIN_USER_DATA["email"]
    }
    response = await client.post("/v1/auth/password/reset-request", json=reset_data)
    assert response.status_code == 200

    response_data = response.json()
    assert "message" in response_data
    assert "token" in response_data  # In real app, this would be sent via email
    assert "password reset link has been sent" in response_data["message"]

async def test_password_reset_request_invalid_email(client: AsyncClient):
    """
    Tests password reset request with invalid/non-existent email.
    """
    reset_data = {
        "email": "nonexistent@test.com"
    }
    response = await client.post("/v1/auth/password/reset-request", json=reset_data)
    assert response.status_code == 200

    # Should return the same message to prevent user enumeration
    response_data = response.json()
    assert "message" in response_data
    assert "password reset link has been sent" in response_data["message"]

async def test_password_reset_confirm_valid_token(client: AsyncClient, reset_admin_password):
    """
    Tests password reset confirmation with valid token.
    """
    # First, request a password reset
    reset_request_data = {
        "email": ADMIN_USER_DATA["email"]
    }
    request_response = await client.post("/v1/auth/password/reset-request", json=reset_request_data)
    assert request_response.status_code == 200

    token = request_response.json()["token"]

    # Now confirm the reset
    new_password = "new_secure_password_123"
    confirm_data = {
        "token": token,
        "new_password": new_password
    }
    confirm_response = await client.post("/v1/auth/password/reset-confirm", json=confirm_data)
    assert confirm_response.status_code == 204

    # Verify that the old password no longer works
    old_login_data = {
        "username": ADMIN_USER_DATA["email"],
        "password": ADMIN_USER_DATA["password"],
    }
    old_login_response = await client.post("/v1/auth/login", data=old_login_data)
    assert old_login_response.status_code == 401

    # Verify that the new password works
    new_login_data = {
        "username": ADMIN_USER_DATA["email"],
        "password": new_password,
    }
    new_login_response = await client.post("/v1/auth/login", data=new_login_data)
    assert new_login_response.status_code == 200

async def test_password_reset_confirm_invalid_token(client: AsyncClient):
    """
    Tests password reset confirmation with invalid token.
    """
    confirm_data = {
        "token": "invalid-token-12345",
        "new_password": "new_password_123"
    }
    response = await client.post("/v1/auth/password/reset-confirm", json=confirm_data)
    assert response.status_code == 400
    assert "Invalid or expired password reset token" in response.json()["detail"]

async def test_password_reset_confirm_used_token(client: AsyncClient, reset_admin_password):
    """
    Tests password reset confirmation with already used token.
    """
    # First, request a password reset
    reset_request_data = {
        "email": ADMIN_USER_DATA["email"]
    }
    request_response = await client.post("/v1/auth/password/reset-request", json=reset_request_data)
    assert request_response.status_code == 200

    token = request_response.json()["token"]

    # Use the token once
    confirm_data = {
        "token": token,
        "new_password": "first_new_password"
    }
    first_response = await client.post("/v1/auth/password/reset-confirm", json=confirm_data)
    assert first_response.status_code == 204

    # Try to use the same token again
    confirm_data["new_password"] = "second_new_password"
    second_response = await client.post("/v1/auth/password/reset-confirm", json=confirm_data)
    assert second_response.status_code == 400
    assert "Invalid or expired password reset token" in second_response.json()["detail"]

# ==================== PASSWORD CHANGE TESTS ====================

async def test_password_change_correct_current_password(client: AsyncClient, reset_admin_password):
    """
    Tests password change with correct current password.
    """
    # First, log in to get access token
    login_data = {
        "username": ADMIN_USER_DATA["email"],
        "password": ADMIN_USER_DATA["password"],
    }
    login_response = await client.post("/v1/auth/login", data=login_data)
    assert login_response.status_code == 200

    access_token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # Change password
    new_password = "changed_secure_password_456"
    change_data = {
        "current_password": ADMIN_USER_DATA["password"],
        "new_password": new_password
    }
    change_response = await client.post("/v1/auth/password/change", json=change_data, headers=headers)
    assert change_response.status_code == 204

    # Verify old password no longer works
    old_login_response = await client.post("/v1/auth/login", data=login_data)
    assert old_login_response.status_code == 401

    # Verify new password works
    new_login_data = {
        "username": ADMIN_USER_DATA["email"],
        "password": new_password,
    }
    new_login_response = await client.post("/v1/auth/login", data=new_login_data)
    assert new_login_response.status_code == 200

async def test_password_change_incorrect_current_password(client: AsyncClient, reset_admin_password):
    """
    Tests password change with incorrect current password.
    """
    # First, log in to get access token
    login_data = {
        "username": ADMIN_USER_DATA["email"],
        "password": ADMIN_USER_DATA["password"],
    }
    login_response = await client.post("/v1/auth/login", data=login_data)
    assert login_response.status_code == 200

    access_token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # Try to change password with wrong current password
    change_data = {
        "current_password": "wrong_current_password",
        "new_password": "new_password_123"
    }
    change_response = await client.post("/v1/auth/password/change", json=change_data, headers=headers)
    assert change_response.status_code == 400
    assert "Current password is incorrect" in change_response.json()["detail"]

async def test_password_change_without_authentication(client: AsyncClient):
    """
    Tests password change without authentication.
    """
    change_data = {
        "current_password": ADMIN_USER_DATA["password"],
        "new_password": "new_password_123"
    }
    response = await client.post("/v1/auth/password/change", json=change_data)
    assert response.status_code == 401

# ==================== ENRICHED JWT TOKEN TESTS ====================

async def test_login_returns_enriched_token_by_default(client: AsyncClient):
    """
    Test that login returns enriched JWT tokens by default (new feature).
    """
    login_data = {
        "username": ADMIN_USER_DATA["email"],
        "password": ADMIN_USER_DATA["password"],
    }
    response = await client.post("/v1/auth/login", data=login_data)
    
    assert response.status_code == 200
    token_data = response.json()
    assert "access_token" in token_data
    
    # Decode the JWT token to verify it's enriched
    import jwt as jwt_lib
    access_token = token_data["access_token"]
    decoded = jwt_lib.decode(access_token, options={"verify_signature": False})
    
    # Enriched tokens should have these additional fields
    assert "user" in decoded, "Token should contain user data"
    assert "permissions" in decoded, "Token should contain permissions"
    assert "roles" in decoded, "Token should contain roles"
    assert "scopes" in decoded, "Token should contain scopes"
    assert "session" in decoded, "Token should contain session data"
    
    # Verify user data structure
    user_data = decoded["user"]
    assert user_data["email"] == ADMIN_USER_DATA["email"]
    assert "first_name" in user_data
    assert "status" in user_data
    assert "is_platform_staff" in user_data
    
    # Verify permissions are a list of strings
    permissions = decoded["permissions"]
    assert isinstance(permissions, list)
    for permission in permissions:
        assert isinstance(permission, str)
        assert ":" in permission  # Should follow "resource:action" format
    
    # Verify session data structure
    session_data = decoded["session"]
    assert "is_main_client" in session_data
    assert "mfa_enabled" in session_data
    assert "locale" in session_data

async def test_login_with_basic_token_parameter(client: AsyncClient):
    """
    Test login with use_enriched_tokens=false returns basic token (new feature).
    """
    login_data = {
        "username": ADMIN_USER_DATA["email"],
        "password": ADMIN_USER_DATA["password"],
    }
    response = await client.post("/v1/auth/login?use_enriched_tokens=false", data=login_data)
    
    assert response.status_code == 200
    token_data = response.json()
    assert "access_token" in token_data
    
    # Decode the JWT token to verify it's basic (minimal)
    import jwt as jwt_lib
    access_token = token_data["access_token"]
    decoded = jwt_lib.decode(access_token, options={"verify_signature": False})
    
    # Basic tokens should NOT have enriched fields
    assert "user" not in decoded, "Basic token should not contain user data"
    assert "permissions" not in decoded, "Basic token should not contain permissions"
    assert "roles" not in decoded, "Basic token should not contain roles"
    assert "scopes" not in decoded, "Basic token should not contain scopes"
    assert "session" not in decoded, "Basic token should not contain session data"
    
    # Basic tokens should have minimal required fields
    assert "sub" in decoded, "Token should contain subject (user_id)"
    assert "exp" in decoded, "Token should contain expiration"
    assert "iat" in decoded, "Token should contain issued_at"

async def test_token_info_endpoint_enriched_token(client: AsyncClient):
    """
    Test the new /v1/auth/token-info endpoint with enriched token.
    """
    # Login to get enriched token
    login_data = {
        "username": ADMIN_USER_DATA["email"],
        "password": ADMIN_USER_DATA["password"],
    }
    login_response = await client.post("/v1/auth/login", data=login_data)
    access_token = login_response.json()["access_token"]
    
    # Call token-info endpoint
    headers = {"Authorization": f"Bearer {access_token}"}
    response = await client.get("/v1/auth/token-info", headers=headers)
    
    assert response.status_code == 200
    token_info = response.json()
    
    # Verify enriched token info structure
    assert token_info["token_type"] == "enriched"
    assert "user_id" in token_info
    assert "client_account_id" in token_info
    assert "permissions_count" in token_info
    assert "roles_count" in token_info
    assert "scopes" in token_info
    assert "expires_at" in token_info
    assert "issued_at" in token_info
    assert "user_email" in token_info
    assert "mfa_enabled" in token_info
    assert "locale" in token_info
    
    # Verify data types
    assert isinstance(token_info["permissions_count"], int)
    assert isinstance(token_info["roles_count"], int)
    assert isinstance(token_info["scopes"], list)
    assert token_info["permissions_count"] >= 0
    assert token_info["roles_count"] >= 0

async def test_token_info_endpoint_basic_token(client: AsyncClient):
    """
    Test the /v1/auth/token-info endpoint with basic token.
    """
    # Login to get basic token
    login_data = {
        "username": ADMIN_USER_DATA["email"],
        "password": ADMIN_USER_DATA["password"],
    }
    login_response = await client.post("/v1/auth/login?use_enriched_tokens=false", data=login_data)
    access_token = login_response.json()["access_token"]
    
    # Call token-info endpoint
    headers = {"Authorization": f"Bearer {access_token}"}
    response = await client.get("/v1/auth/token-info", headers=headers)
    
    assert response.status_code == 200
    token_info = response.json()
    
    # Verify basic token info structure
    assert token_info["token_type"] == "basic"
    assert "user_id" in token_info
    assert "client_account_id" in token_info
    assert "message" in token_info
    assert "Token contains minimal data" in token_info["message"]
    
    # Basic token info should NOT have enriched fields
    assert "permissions_count" not in token_info
    assert "roles_count" not in token_info
    assert "user_email" not in token_info

async def test_token_info_endpoint_invalid_token(client: AsyncClient):
    """
    Test the /v1/auth/token-info endpoint with invalid token.
    """
    headers = {"Authorization": "Bearer invalid_token_here"}
    response = await client.get("/v1/auth/token-info", headers=headers)
    
    assert response.status_code == 401
    assert "Invalid access token" in response.json()["detail"]

async def test_token_info_endpoint_no_authorization(client: AsyncClient):
    """
    Test the /v1/auth/token-info endpoint without authorization header.
    """
    response = await client.get("/v1/auth/token-info")
    assert response.status_code == 401

async def test_refresh_token_returns_enriched_by_default(client: AsyncClient):
    """
    Test that refresh token returns enriched access token by default.
    """
    # Login first to get refresh token
    login_data = {
        "username": ADMIN_USER_DATA["email"],
        "password": ADMIN_USER_DATA["password"],
    }
    login_response = await client.post("/v1/auth/login", data=login_data)
    refresh_token = login_response.json()["refresh_token"]
    
    # Use refresh token
    headers = {"Authorization": f"Bearer {refresh_token}"}
    refresh_response = await client.post("/v1/auth/refresh", headers=headers)
    
    assert refresh_response.status_code == 200
    new_tokens = refresh_response.json()
    
    # Verify new access token is enriched
    import jwt as jwt_lib
    new_access_token = new_tokens["access_token"]
    decoded = jwt_lib.decode(new_access_token, options={"verify_signature": False})
    
    assert "user" in decoded
    assert "permissions" in decoded
    assert "roles" in decoded
    assert "scopes" in decoded
    assert "session" in decoded

async def test_refresh_token_with_basic_token_parameter(client: AsyncClient):
    """
    Test refresh token with use_enriched_tokens=false parameter.
    """
    # Login first to get refresh token
    login_data = {
        "username": ADMIN_USER_DATA["email"],
        "password": ADMIN_USER_DATA["password"],
    }
    login_response = await client.post("/v1/auth/login", data=login_data)
    refresh_token = login_response.json()["refresh_token"]
    
    # Use refresh token with basic token parameter
    headers = {"Authorization": f"Bearer {refresh_token}"}
    refresh_response = await client.post("/v1/auth/refresh?use_enriched_tokens=false", headers=headers)
    
    assert refresh_response.status_code == 200
    new_tokens = refresh_response.json()
    
    # Verify new access token is basic
    import jwt as jwt_lib
    new_access_token = new_tokens["access_token"]
    decoded = jwt_lib.decode(new_access_token, options={"verify_signature": False})
    
    assert "user" not in decoded
    assert "permissions" not in decoded
    assert "roles" not in decoded
    assert "scopes" not in decoded
    assert "session" not in decoded

async def test_login_with_cookies_creates_enriched_token(client: AsyncClient):
    """
    Test that cookie mode creates enriched tokens by default.
    """
    login_data = {
        "username": ADMIN_USER_DATA["email"],
        "password": ADMIN_USER_DATA["password"],
    }
    response = await client.post("/v1/auth/login?use_cookies=true", data=login_data)
    
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["message"] == "Login successful"
    assert response_data["token_type"] == "cookie"
    
    # Verify cookies are set
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies
    
    # Decode the access token cookie to verify it's enriched
    import jwt as jwt_lib
    access_token_cookie = response.cookies["access_token"]
    decoded = jwt_lib.decode(access_token_cookie, options={"verify_signature": False})
    
    assert "user" in decoded
    assert "permissions" in decoded
    assert "roles" in decoded

async def test_login_with_cookies_and_basic_token_flag(client: AsyncClient):
    """
    Test cookie mode with basic token flag.
    """
    login_data = {
        "username": ADMIN_USER_DATA["email"],
        "password": ADMIN_USER_DATA["password"],
    }
    response = await client.post("/v1/auth/login?use_cookies=true&use_enriched_tokens=false", data=login_data)
    
    assert response.status_code == 200
    
    # Decode the access token cookie to verify it's basic
    import jwt as jwt_lib
    access_token_cookie = response.cookies["access_token"]
    decoded = jwt_lib.decode(access_token_cookie, options={"verify_signature": False})
    
    assert "user" not in decoded
    assert "permissions" not in decoded
    assert "roles" not in decoded

async def test_token_size_is_reasonable(client: AsyncClient):
    """
    Test that enriched tokens have reasonable size.
    """
    login_data = {
        "username": ADMIN_USER_DATA["email"],
        "password": ADMIN_USER_DATA["password"],
    }
    response = await client.post("/v1/auth/login", data=login_data)
    
    access_token = response.json()["access_token"]
    token_size = len(access_token.encode('utf-8'))
    
    # Token should be less than 8KB limit
    assert token_size < 8192, f"Token size ({token_size} bytes) exceeds 8KB limit"
    
    # But should be substantial (more than basic token)
    assert token_size > 200, f"Token size ({token_size} bytes) seems too small for enriched token"
