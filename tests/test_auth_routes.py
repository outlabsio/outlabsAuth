import pytest
from httpx import AsyncClient
import asyncio

# Mark all tests in this file as async
pytestmark = pytest.mark.asyncio

# This data corresponds to the user created in the seed script
ADMIN_USER_DATA = {
    "email": "admin@test.com",
    "password": "a_very_secure_password"
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
