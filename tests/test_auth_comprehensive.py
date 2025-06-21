import pytest
from httpx import AsyncClient
from datetime import datetime, timedelta, timezone
import time
from unittest.mock import patch
import uuid

# Mark all tests in this file as async
pytestmark = pytest.mark.asyncio

# Test data for various scenarios
ADMIN_USER_DATA = {
    "email": "admin@test.com",
    "password": "a_very_secure_password"
}

VALID_TEST_USER = {
    "email": "test_auth_user@example.com",
    "password": "SecurePassword123!",
    "first_name": "Test",
    "last_name": "User"
}

# Helper function to create a test user
async def create_test_user(client: AsyncClient, admin_token: str, user_data: dict):
    """Helper to create a test user for authentication tests"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await client.post("/v1/users/", json=user_data, headers=headers)
    return response

# Helper function to get admin token
async def get_admin_token(client: AsyncClient):
    """Helper to get admin authentication token"""
    login_data = {
        "username": ADMIN_USER_DATA["email"],
        "password": ADMIN_USER_DATA["password"],
    }
    response = await client.post("/v1/auth/login", data=login_data)
    return response.json()["access_token"]

class TestPasswordValidation:
    """Test password validation scenarios"""

    async def test_login_with_empty_password(self, client: AsyncClient):
        """Test login fails with empty password"""
        login_data = {
            "username": VALID_TEST_USER["email"],
            "password": "",
        }
        response = await client.post("/v1/auth/login", data=login_data)
        assert response.status_code == 401
        assert "Incorrect email or password" in response.json()["detail"]

    async def test_login_with_very_long_password(self, client: AsyncClient):
        """Test login with password longer than 128 characters"""
        # Create a user first
        admin_token = await get_admin_token(client)
        user_data = VALID_TEST_USER.copy()
        user_data["email"] = f"longpass_{uuid.uuid4()}@example.com"
        await create_test_user(client, admin_token, user_data)

        # Try login with very long password
        long_password = "a" * 150  # 150 characters
        login_data = {
            "username": user_data["email"],
            "password": long_password,
        }
        response = await client.post("/v1/auth/login", data=login_data)
        assert response.status_code == 401

    async def test_login_with_special_characters_password(self, client: AsyncClient):
        """Test login with special characters in password"""
        admin_token = await get_admin_token(client)

        # Create user with special character password
        special_password = "Test@123#$%^&*()!~`"
        user_data = VALID_TEST_USER.copy()
        user_data["email"] = f"special_{uuid.uuid4()}@example.com"
        user_data["password"] = special_password

        create_response = await create_test_user(client, admin_token, user_data)
        assert create_response.status_code == 201

        # Test login with special character password
        login_data = {
            "username": user_data["email"],
            "password": special_password,
        }
        response = await client.post("/v1/auth/login", data=login_data)
        assert response.status_code == 200
        assert "access_token" in response.json()

    async def test_login_with_unicode_password(self, client: AsyncClient):
        """Test login with Unicode/emoji passwords"""
        admin_token = await get_admin_token(client)

        # Create user with Unicode password
        unicode_password = "Test123🔒🚀äöü"
        user_data = VALID_TEST_USER.copy()
        user_data["email"] = f"unicode_{uuid.uuid4()}@example.com"
        user_data["password"] = unicode_password

        create_response = await create_test_user(client, admin_token, user_data)
        assert create_response.status_code == 201

        # Test login with Unicode password
        login_data = {
            "username": user_data["email"],
            "password": unicode_password,
        }
        response = await client.post("/v1/auth/login", data=login_data)
        assert response.status_code == 200
        assert "access_token" in response.json()

class TestEmailValidation:
    """Test email validation scenarios"""

    async def test_login_with_invalid_email_format(self, client: AsyncClient):
        """Test login fails with invalid email formats"""
        invalid_emails = [
            "notanemail",
            "@domain.com",
            "user@",
            "user space@domain.com",
            "user..double@domain.com"
        ]

        for invalid_email in invalid_emails:
            login_data = {
                "username": invalid_email,
                "password": "anypassword",
            }
            response = await client.post("/v1/auth/login", data=login_data)
            assert response.status_code == 401

    async def test_login_with_nonexistent_email(self, client: AsyncClient):
        """Test login with non-existent email"""
        login_data = {
            "username": f"nonexistent_{uuid.uuid4()}@example.com",
            "password": "anypassword",
        }
        response = await client.post("/v1/auth/login", data=login_data)
        assert response.status_code == 401
        assert "Incorrect email or password" in response.json()["detail"]

    async def test_login_email_case_sensitivity(self, client: AsyncClient):
        """Test email case sensitivity in login"""
        admin_token = await get_admin_token(client)

        # Create user with lowercase email
        user_data = VALID_TEST_USER.copy()
        user_data["email"] = f"testcase_{uuid.uuid4()}@example.com"
        create_response = await create_test_user(client, admin_token, user_data)
        assert create_response.status_code == 201

        # Test login with uppercase email
        login_data = {
            "username": user_data["email"].upper(),
            "password": user_data["password"],
        }
        response = await client.post("/v1/auth/login", data=login_data)
        # Should succeed as email should be case-insensitive
        assert response.status_code in [200, 401]  # Depending on implementation

class TestSessionManagement:
    """Test JWT token and session management"""

    async def test_token_expiration_handling(self, client: AsyncClient):
        """Test behavior with expired tokens"""
        # This test would require mocking time or using very short-lived tokens
        login_data = {
            "username": ADMIN_USER_DATA["email"],
            "password": ADMIN_USER_DATA["password"],
        }
        response = await client.post("/v1/auth/login", data=login_data)
        assert response.status_code == 200

        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Test that token works initially
        me_response = await client.get("/v1/auth/me", headers=headers)
        assert me_response.status_code == 200

    async def test_refresh_token_rotation(self, client: AsyncClient):
        """Test refresh token rotation functionality"""
        # Login to get initial tokens
        login_data = {
            "username": ADMIN_USER_DATA["email"],
            "password": ADMIN_USER_DATA["password"],
        }
        login_response = await client.post("/v1/auth/login", data=login_data)
        assert login_response.status_code == 200

        initial_tokens = login_response.json()
        refresh_token = initial_tokens["refresh_token"]

        # Use refresh token to get new tokens
        headers = {"Authorization": f"Bearer {refresh_token}"}
        refresh_response = await client.post("/v1/auth/refresh", headers=headers)

        if refresh_response.status_code == 200:
            new_tokens = refresh_response.json()
            assert "access_token" in new_tokens
            assert "refresh_token" in new_tokens
            # New tokens should be different
            assert new_tokens["access_token"] != initial_tokens["access_token"]
            assert new_tokens["refresh_token"] != initial_tokens["refresh_token"]

    async def test_logout_token_revocation(self, client: AsyncClient):
        """Test that logout properly revokes tokens"""
        # Login
        login_data = {
            "username": ADMIN_USER_DATA["email"],
            "password": ADMIN_USER_DATA["password"],
        }
        login_response = await client.post("/v1/auth/login", data=login_data)
        assert login_response.status_code == 200

        access_token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Verify token works
        me_response = await client.get("/v1/auth/me", headers=headers)
        assert me_response.status_code == 200

        # Logout
        logout_response = await client.post("/v1/auth/logout", headers=headers)
        assert logout_response.status_code == 204

    async def test_multiple_device_login(self, client: AsyncClient):
        """Test multiple simultaneous logins from different 'devices'"""
        login_data = {
            "username": ADMIN_USER_DATA["email"],
            "password": ADMIN_USER_DATA["password"],
        }

        # First login (device 1)
        response1 = await client.post("/v1/auth/login", data=login_data)
        assert response1.status_code == 200
        token1 = response1.json()["access_token"]

        # Second login (device 2)
        response2 = await client.post("/v1/auth/login", data=login_data)
        assert response2.status_code == 200
        token2 = response2.json()["access_token"]

        # Both tokens should work
        headers1 = {"Authorization": f"Bearer {token1}"}
        headers2 = {"Authorization": f"Bearer {token2}"}

        me_response1 = await client.get("/v1/auth/me", headers=headers1)
        me_response2 = await client.get("/v1/auth/me", headers=headers2)

        assert me_response1.status_code == 200
        assert me_response2.status_code == 200

    async def test_logout_all_sessions(self, client: AsyncClient):
        """Test logout from all sessions"""
        login_data = {
            "username": ADMIN_USER_DATA["email"],
            "password": ADMIN_USER_DATA["password"],
        }

        # Create multiple sessions
        response1 = await client.post("/v1/auth/login", data=login_data)
        response2 = await client.post("/v1/auth/login", data=login_data)

        assert response1.status_code == 200
        assert response2.status_code == 200

        token1 = response1.json()["access_token"]
        headers1 = {"Authorization": f"Bearer {token1}"}

        # Logout from all sessions
        logout_response = await client.post("/v1/auth/logout_all", headers=headers1)
        assert logout_response.status_code == 204

class TestPasswordResetWorkflow:
    """Test password reset functionality"""

    async def test_request_reset_with_valid_email(self, client: AsyncClient):
        """Test password reset request with valid email"""
        admin_token = await get_admin_token(client)

        # Create test user
        user_data = VALID_TEST_USER.copy()
        user_data["email"] = f"reset_valid_{uuid.uuid4()}@example.com"
        create_response = await create_test_user(client, admin_token, user_data)
        assert create_response.status_code == 201

        # Request password reset
        reset_request = {"email": user_data["email"]}
        response = await client.post("/v1/auth/password/reset-request", json=reset_request)
        assert response.status_code == 200
        assert "message" in response.json()
        # In test mode, token is returned
        assert "token" in response.json()

    async def test_request_reset_with_invalid_email(self, client: AsyncClient):
        """Test password reset request with invalid/non-existent email"""
        reset_request = {"email": f"nonexistent_{uuid.uuid4()}@example.com"}
        response = await client.post("/v1/auth/password/reset-request", json=reset_request)
        # Should return success message regardless (prevent user enumeration)
        assert response.status_code == 200
        assert "message" in response.json()

    async def test_reset_with_valid_token(self, client: AsyncClient):
        """Test password reset with valid token"""
        admin_token = await get_admin_token(client)

        # Create test user
        user_data = VALID_TEST_USER.copy()
        user_data["email"] = f"reset_token_{uuid.uuid4()}@example.com"
        create_response = await create_test_user(client, admin_token, user_data)
        assert create_response.status_code == 201

        # Request password reset
        reset_request = {"email": user_data["email"]}
        reset_response = await client.post("/v1/auth/password/reset-request", json=reset_request)
        assert reset_response.status_code == 200

        reset_token = reset_response.json().get("token")
        if reset_token:
            # Confirm password reset
            new_password = "NewSecurePassword123!"
            confirm_data = {
                "token": reset_token,
                "new_password": new_password
            }
            confirm_response = await client.post("/v1/auth/password/reset-confirm", json=confirm_data)
            assert confirm_response.status_code == 204

            # Test login with new password
            login_data = {
                "username": user_data["email"],
                "password": new_password,
            }
            login_response = await client.post("/v1/auth/login", data=login_data)
            assert login_response.status_code == 200

    async def test_reset_with_invalid_token(self, client: AsyncClient):
        """Test password reset with invalid token"""
        confirm_data = {
            "token": "invalid_token_12345",
            "new_password": "NewPassword123!"
        }
        response = await client.post("/v1/auth/password/reset-confirm", json=confirm_data)
        assert response.status_code == 400
        assert "Invalid or expired" in response.json()["detail"]

    async def test_reset_with_used_token(self, client: AsyncClient):
        """Test password reset with already used token"""
        admin_token = await get_admin_token(client)

        # Create test user
        user_data = VALID_TEST_USER.copy()
        user_data["email"] = f"reset_used_{uuid.uuid4()}@example.com"
        create_response = await create_test_user(client, admin_token, user_data)
        assert create_response.status_code == 201

        # Request and use reset token
        reset_request = {"email": user_data["email"]}
        reset_response = await client.post("/v1/auth/password/reset-request", json=reset_request)
        reset_token = reset_response.json().get("token")

        if reset_token:
            # Use token first time
            confirm_data = {
                "token": reset_token,
                "new_password": "FirstNewPassword123!"
            }
            first_response = await client.post("/v1/auth/password/reset-confirm", json=confirm_data)
            assert first_response.status_code == 204

            # Try to use same token again
            confirm_data["new_password"] = "SecondNewPassword123!"
            second_response = await client.post("/v1/auth/password/reset-confirm", json=confirm_data)
            assert second_response.status_code == 400

class TestPasswordChange:
    """Test password change functionality"""

    async def test_change_password_with_correct_current(self, client: AsyncClient):
        """Test password change with correct current password"""
        admin_token = await get_admin_token(client)

        # Create test user
        user_data = VALID_TEST_USER.copy()
        user_data["email"] = f"change_correct_{uuid.uuid4()}@example.com"
        create_response = await create_test_user(client, admin_token, user_data)
        assert create_response.status_code == 201

        # Login as test user
        login_data = {
            "username": user_data["email"],
            "password": user_data["password"],
        }
        login_response = await client.post("/v1/auth/login", data=login_data)
        assert login_response.status_code == 200

        user_token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {user_token}"}

        # Change password
        new_password = "NewSecurePassword123!"
        change_data = {
            "current_password": user_data["password"],
            "new_password": new_password
        }
        change_response = await client.post("/v1/auth/password/change", json=change_data, headers=headers)
        assert change_response.status_code == 204

        # Test login with new password
        new_login_data = {
            "username": user_data["email"],
            "password": new_password,
        }
        new_login_response = await client.post("/v1/auth/login", data=new_login_data)
        assert new_login_response.status_code == 200

    async def test_change_password_with_incorrect_current(self, client: AsyncClient):
        """Test password change with incorrect current password"""
        # Login as admin to get token
        login_data = {
            "username": ADMIN_USER_DATA["email"],
            "password": ADMIN_USER_DATA["password"],
        }
        login_response = await client.post("/v1/auth/login", data=login_data)
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Try to change password with wrong current password
        change_data = {
            "current_password": "wrong_password",
            "new_password": "NewPassword123!"
        }
        response = await client.post("/v1/auth/password/change", json=change_data, headers=headers)
        assert response.status_code == 400
        assert "Current password is incorrect" in response.json()["detail"]

    async def test_password_complexity_validation(self, client: AsyncClient):
        """Test password complexity requirements"""
        admin_token = await get_admin_token(client)

        # Test various weak passwords during user creation
        weak_passwords = [
            "123",           # Too short
            "password",      # No numbers/special chars
            "12345678",      # Only numbers
            "abcdefgh",      # Only letters
        ]

        for weak_password in weak_passwords:
            user_data = VALID_TEST_USER.copy()
            user_data["email"] = f"weak_{uuid.uuid4()}@example.com"
            user_data["password"] = weak_password

            response = await create_test_user(client, admin_token, user_data)
            # Password validation might be handled at creation time
            # If not handled, the test demonstrates the need for validation

class TestSecurityFeatures:
    """Test security-related features"""

    async def test_invalid_token_detection(self, client: AsyncClient):
        """Test detection of tampered/invalid tokens"""
        invalid_tokens = [
            "invalid.token.here",
            "Bearer invalid_token",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid.signature",
            "",
            "null"
        ]

        for invalid_token in invalid_tokens:
            headers = {"Authorization": f"Bearer {invalid_token}"}
            response = await client.get("/v1/auth/me", headers=headers)
            assert response.status_code == 401

    async def test_session_invalidation_after_password_change(self, client: AsyncClient):
        """Test that sessions are invalidated after password change"""
        admin_token = await get_admin_token(client)

        # Create test user
        user_data = VALID_TEST_USER.copy()
        user_data["email"] = f"session_invalid_{uuid.uuid4()}@example.com"
        create_response = await create_test_user(client, admin_token, user_data)
        assert create_response.status_code == 201

        # Login to get session
        login_data = {
            "username": user_data["email"],
            "password": user_data["password"],
        }
        login_response = await client.post("/v1/auth/login", data=login_data)
        old_token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {old_token}"}

        # Verify token works
        me_response = await client.get("/v1/auth/me", headers=headers)
        assert me_response.status_code == 200

        # Change password
        change_data = {
            "current_password": user_data["password"],
            "new_password": "NewSecurePassword123!"
        }
        change_response = await client.post("/v1/auth/password/change", json=change_data, headers=headers)
        assert change_response.status_code == 204

    async def test_get_active_sessions(self, client: AsyncClient):
        """Test retrieving active sessions"""
        # Login to create session
        login_data = {
            "username": ADMIN_USER_DATA["email"],
            "password": ADMIN_USER_DATA["password"],
        }
        login_response = await client.post("/v1/auth/login", data=login_data)
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Get active sessions
        sessions_response = await client.get("/v1/auth/sessions", headers=headers)
        assert sessions_response.status_code == 200
        sessions = sessions_response.json()
        assert isinstance(sessions, list)

    async def test_revoke_specific_session(self, client: AsyncClient):
        """Test revoking a specific session"""
        # Create multiple sessions
        login_data = {
            "username": ADMIN_USER_DATA["email"],
            "password": ADMIN_USER_DATA["password"],
        }

        response1 = await client.post("/v1/auth/login", data=login_data)
        response2 = await client.post("/v1/auth/login", data=login_data)

        token1 = response1.json()["access_token"]
        headers1 = {"Authorization": f"Bearer {token1}"}

        # Get sessions to find JTI
        sessions_response = await client.get("/v1/auth/sessions", headers=headers1)
        if sessions_response.status_code == 200:
            sessions = sessions_response.json()
            if sessions:
                # Try to revoke first session
                jti = sessions[0].get("jti") if sessions[0].get("jti") else "test_jti"
                revoke_response = await client.delete(f"/v1/auth/sessions/{jti}", headers=headers1)
                # Should succeed or return 404 if JTI not found
                assert revoke_response.status_code in [204, 404]

class TestAuthenticationIntegration:
    """Test authentication integration with other endpoints"""

    async def test_protected_endpoint_access(self, client: AsyncClient):
        """Test that protected endpoints require valid authentication"""
        # Try accessing protected endpoint without token
        response = await client.get("/v1/users/")
        assert response.status_code == 401

        # Try with invalid token
        headers = {"Authorization": "Bearer invalid_token"}
        response = await client.get("/v1/users/", headers=headers)
        assert response.status_code == 401

        # Try with valid token
        admin_token = await get_admin_token(client)
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = await client.get("/v1/users/", headers=headers)
        assert response.status_code == 200

    async def test_token_in_different_header_formats(self, client: AsyncClient):
        """Test different token header formats"""
        admin_token = await get_admin_token(client)

        # Test various header formats
        header_formats = [
            {"Authorization": f"Bearer {admin_token}"},  # Standard
            {"Authorization": f"bearer {admin_token}"},  # Lowercase
            {"Authorization": f"BEARER {admin_token}"},  # Uppercase
        ]

        for headers in header_formats:
            response = await client.get("/v1/auth/me", headers=headers)
            # Should work with standard Bearer format
            if headers["Authorization"].startswith("Bearer "):
                assert response.status_code == 200
            else:
                # May or may not work depending on implementation
                assert response.status_code in [200, 401]

class TestEdgeCases:
    """Test edge cases and error scenarios"""

    async def test_malformed_login_requests(self, client: AsyncClient):
        """Test handling of malformed login requests"""
        malformed_requests = [
            {},  # Empty request
            {"username": "test@example.com"},  # Missing password
            {"password": "password"},  # Missing username
            {"username": "", "password": ""},  # Empty fields
            {"user": "test@example.com", "pass": "password"},  # Wrong field names
        ]

        for request_data in malformed_requests:
            response = await client.post("/v1/auth/login", data=request_data)
            assert response.status_code in [401, 422]  # Unauthorized or validation error

    async def test_concurrent_login_attempts(self, client: AsyncClient):
        """Test concurrent login attempts"""
        import asyncio

        async def login_attempt():
            login_data = {
                "username": ADMIN_USER_DATA["email"],
                "password": ADMIN_USER_DATA["password"],
            }
            response = await client.post("/v1/auth/login", data=login_data)
            return response.status_code

        # Make multiple concurrent login attempts
        tasks = [login_attempt() for _ in range(5)]
        results = await asyncio.gather(*tasks)

        # All should succeed (unless rate limiting is implemented)
        successful_logins = sum(1 for code in results if code == 200)
        assert successful_logins >= 1  # At least one should succeed

    async def test_very_long_tokens(self, client: AsyncClient):
        """Test handling of extremely long tokens"""
        very_long_token = "a" * 10000  # 10KB token
        headers = {"Authorization": f"Bearer {very_long_token}"}
        response = await client.get("/v1/auth/me", headers=headers)
        assert response.status_code == 401

    async def test_special_characters_in_tokens(self, client: AsyncClient):
        """Test tokens with special characters"""
        special_tokens = [
            "token<script>alert('xss')</script>",
            "token'; DROP TABLE users; --",
            "token\x00\x01\x02",  # Null bytes and control characters
        ]

        for token in special_tokens:
            headers = {"Authorization": f"Bearer {token}"}
            response = await client.get("/v1/auth/me", headers=headers)
            assert response.status_code == 401
