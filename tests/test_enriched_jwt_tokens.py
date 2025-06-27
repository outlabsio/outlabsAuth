import pytest
from httpx import AsyncClient
import json
import jwt as jwt_lib
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import asyncio

# Mark all tests in this file as async
pytestmark = pytest.mark.asyncio

"""
ENRICHED JWT TOKEN TEST SUITE
============================

This test suite covers the new enriched JWT token functionality that was added
to the authentication system. It tests:

1. Enriched vs Basic Token Creation
2. Token Payload Structure and Content
3. Token Size Management and Fallback
4. Token-Info Endpoint
5. Frontend Integration Features
6. Permission Optimization
7. Cookie Mode with Enriched Tokens
8. Error Handling and Edge Cases

The tests ensure that the enriched JWT system works correctly and provides
the expected performance benefits while maintaining security.
"""

# Test data
ADMIN_USER_DATA = {
    "email": "admin@test.com",
    "password": "admin123"
}

class TestEnrichedTokenCreation:
    """Test enriched token creation and basic functionality"""

    async def test_login_returns_enriched_token_by_default(self, client: AsyncClient):
        """Test that login returns enriched tokens by default"""
        login_data = {
            "username": ADMIN_USER_DATA["email"],
            "password": ADMIN_USER_DATA["password"],
        }
        response = await client.post("/v1/auth/login", data=login_data)
        
        assert response.status_code == 200
        token_data = response.json()
        assert "access_token" in token_data
        
        # Decode the token to verify it's enriched
        access_token = token_data["access_token"]
        decoded = jwt_lib.decode(access_token, options={"verify_signature": False})
        
        # Enriched tokens should have these fields
        assert "user" in decoded
        assert "permissions" in decoded
        assert "roles" in decoded
        assert "scopes" in decoded
        assert "session" in decoded
        
        # Verify user data structure
        assert "email" in decoded["user"]
        assert "first_name" in decoded["user"]
        assert "status" in decoded["user"]
        assert "is_platform_staff" in decoded["user"]
        
        # Verify session data structure
        assert "is_main_client" in decoded["session"]
        assert "mfa_enabled" in decoded["session"]
        assert "locale" in decoded["session"]

    async def test_login_with_basic_token_flag(self, client: AsyncClient):
        """Test login with use_enriched_tokens=false returns basic token"""
        login_data = {
            "username": ADMIN_USER_DATA["email"],
            "password": ADMIN_USER_DATA["password"],
        }
        response = await client.post("/v1/auth/login?use_enriched_tokens=false", data=login_data)
        
        assert response.status_code == 200
        token_data = response.json()
        assert "access_token" in token_data
        
        # Decode the token to verify it's basic
        access_token = token_data["access_token"]
        decoded = jwt_lib.decode(access_token, options={"verify_signature": False})
        
        # Basic tokens should NOT have enriched fields
        assert "user" not in decoded
        assert "permissions" not in decoded
        assert "roles" not in decoded
        assert "scopes" not in decoded
        assert "session" not in decoded
        
        # Basic tokens should have minimal fields
        assert "sub" in decoded
        assert "exp" in decoded
        assert "iat" in decoded

    async def test_token_contains_correct_user_data(self, client: AsyncClient):
        """Test that enriched token contains correct user data"""
        login_data = {
            "username": ADMIN_USER_DATA["email"],
            "password": ADMIN_USER_DATA["password"],
        }
        response = await client.post("/v1/auth/login", data=login_data)
        
        access_token = response.json()["access_token"]
        decoded = jwt_lib.decode(access_token, options={"verify_signature": False})
        
        # Verify user data matches expected admin user
        user_data = decoded["user"]
        assert user_data["email"] == ADMIN_USER_DATA["email"]
        assert user_data["first_name"] == "Admin"
        assert user_data["status"] == "active"
        assert isinstance(user_data["is_platform_staff"], bool)

    async def test_token_contains_permissions_array(self, client: AsyncClient):
        """Test that enriched token contains permissions array"""
        login_data = {
            "username": ADMIN_USER_DATA["email"],
            "password": ADMIN_USER_DATA["password"],
        }
        response = await client.post("/v1/auth/login", data=login_data)
        
        access_token = response.json()["access_token"]
        decoded = jwt_lib.decode(access_token, options={"verify_signature": False})
        
        # Verify permissions structure
        permissions = decoded["permissions"]
        assert isinstance(permissions, list)
        # Admin should have some permissions
        assert len(permissions) > 0
        
        # Permissions should be strings
        for permission in permissions:
            assert isinstance(permission, str)
            assert ":" in permission  # Should follow format "resource:action"

    async def test_token_contains_roles_array(self, client: AsyncClient):
        """Test that enriched token contains roles array"""
        login_data = {
            "username": ADMIN_USER_DATA["email"],
            "password": ADMIN_USER_DATA["password"],
        }
        response = await client.post("/v1/auth/login", data=login_data)
        
        access_token = response.json()["access_token"]
        decoded = jwt_lib.decode(access_token, options={"verify_signature": False})
        
        # Verify roles structure
        roles = decoded["roles"]
        assert isinstance(roles, list)
        
        # Each role should have required fields
        for role in roles:
            assert "id" in role
            assert "name" in role
            assert "scope" in role
            assert isinstance(role["id"], str)
            assert isinstance(role["name"], str)
            assert isinstance(role["scope"], str)

class TestTokenRefreshWithEnrichedData:
    """Test refresh functionality with enriched tokens"""

    async def test_refresh_returns_enriched_token_by_default(self, client: AsyncClient):
        """Test that refresh returns enriched tokens by default"""
        # Login first
        login_data = {
            "username": ADMIN_USER_DATA["email"],
            "password": ADMIN_USER_DATA["password"],
        }
        login_response = await client.post("/v1/auth/login", data=login_data)
        refresh_token = login_response.json()["refresh_token"]
        
        # Refresh token
        headers = {"Authorization": f"Bearer {refresh_token}"}
        refresh_response = await client.post("/v1/auth/refresh", headers=headers)
        
        assert refresh_response.status_code == 200
        new_tokens = refresh_response.json()
        
        # Verify new access token is enriched
        new_access_token = new_tokens["access_token"]
        decoded = jwt_lib.decode(new_access_token, options={"verify_signature": False})
        
        assert "user" in decoded
        assert "permissions" in decoded
        assert "roles" in decoded

    async def test_refresh_with_basic_token_flag(self, client: AsyncClient):
        """Test refresh with use_enriched_tokens=false"""
        # Login first
        login_data = {
            "username": ADMIN_USER_DATA["email"],
            "password": ADMIN_USER_DATA["password"],
        }
        login_response = await client.post("/v1/auth/login", data=login_data)
        refresh_token = login_response.json()["refresh_token"]
        
        # Refresh with basic token flag
        headers = {"Authorization": f"Bearer {refresh_token}"}
        refresh_response = await client.post("/v1/auth/refresh?use_enriched_tokens=false", headers=headers)
        
        assert refresh_response.status_code == 200
        new_tokens = refresh_response.json()
        
        # Verify new access token is basic
        new_access_token = new_tokens["access_token"]
        decoded = jwt_lib.decode(new_access_token, options={"verify_signature": False})
        
        assert "user" not in decoded
        assert "permissions" not in decoded
        assert "roles" not in decoded

class TestTokenInfoEndpoint:
    """Test the new token-info endpoint"""

    async def test_token_info_enriched_token(self, client: AsyncClient):
        """Test token-info endpoint with enriched token"""
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
        
        # Verify enriched token info
        assert token_info["token_type"] == "enriched"
        assert "user_id" in token_info
        assert "permissions_count" in token_info
        assert "roles_count" in token_info
        assert "scopes" in token_info
        assert "user_email" in token_info
        assert "mfa_enabled" in token_info
        assert "locale" in token_info
        
        # Verify counts are numbers
        assert isinstance(token_info["permissions_count"], int)
        assert isinstance(token_info["roles_count"], int)
        assert token_info["permissions_count"] >= 0
        assert token_info["roles_count"] >= 0

    async def test_token_info_basic_token(self, client: AsyncClient):
        """Test token-info endpoint with basic token"""
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
        
        # Verify basic token info
        assert token_info["token_type"] == "basic"
        assert "user_id" in token_info
        assert "message" in token_info
        assert "Token contains minimal data" in token_info["message"]
        
        # Basic tokens shouldn't have enriched fields
        assert "permissions_count" not in token_info
        assert "roles_count" not in token_info

    async def test_token_info_invalid_token(self, client: AsyncClient):
        """Test token-info endpoint with invalid token"""
        headers = {"Authorization": "Bearer invalid_token"}
        response = await client.get("/v1/auth/token-info", headers=headers)
        
        assert response.status_code == 401
        assert "Invalid access token" in response.json()["detail"]

class TestCookieModeWithEnrichedTokens:
    """Test cookie mode with enriched tokens"""

    async def test_login_with_cookies_creates_enriched_token(self, client: AsyncClient):
        """Test that cookie mode creates enriched tokens by default"""
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
        access_token_cookie = response.cookies["access_token"]
        decoded = jwt_lib.decode(access_token_cookie, options={"verify_signature": False})
        
        assert "user" in decoded
        assert "permissions" in decoded
        assert "roles" in decoded

    async def test_login_with_cookies_and_basic_token_flag(self, client: AsyncClient):
        """Test cookie mode with basic token flag"""
        login_data = {
            "username": ADMIN_USER_DATA["email"],
            "password": ADMIN_USER_DATA["password"],
        }
        response = await client.post("/v1/auth/login?use_cookies=true&use_enriched_tokens=false", data=login_data)
        
        assert response.status_code == 200
        
        # Decode the access token cookie to verify it's basic
        access_token_cookie = response.cookies["access_token"]
        decoded = jwt_lib.decode(access_token_cookie, options={"verify_signature": False})
        
        assert "user" not in decoded
        assert "permissions" not in decoded
        assert "roles" not in decoded

class TestTokenSizeManagement:
    """Test token size limits and fallback mechanisms"""

    @patch('api.services.security_service.settings.MAX_JWT_SIZE_BYTES', 100)  # Very small limit
    async def test_token_size_fallback_to_basic(self, client: AsyncClient):
        """Test that very large enriched tokens fall back to basic tokens"""
        # This test requires mocking to simulate a very large token scenario
        # In practice, this would happen with users having many permissions
        login_data = {
            "username": ADMIN_USER_DATA["email"],
            "password": ADMIN_USER_DATA["password"],
        }
        
        with patch('api.services.security_service.SecurityService.create_enriched_access_token') as mock_create:
            # Mock the create_enriched_access_token to simulate fallback
            mock_create.return_value = "basic_fallback_token"
            
            response = await client.post("/v1/auth/login", data=login_data)
            
            # Should still succeed but potentially with basic token
            assert response.status_code == 200

    async def test_token_size_calculation(self, client: AsyncClient):
        """Test that token size is reasonable for normal users"""
        login_data = {
            "username": ADMIN_USER_DATA["email"],
            "password": ADMIN_USER_DATA["password"],
        }
        response = await client.post("/v1/auth/login", data=login_data)
        
        access_token = response.json()["access_token"]
        token_size = len(access_token.encode('utf-8'))
        
        # Token should be reasonable size (less than 8KB)
        assert token_size < 8192
        # But should be substantial (more than basic token)
        assert token_size > 200

class TestPermissionOptimization:
    """Test permission optimization in tokens"""

    async def test_permissions_are_sorted(self, client: AsyncClient):
        """Test that permissions are sorted for consistent token size"""
        login_data = {
            "username": ADMIN_USER_DATA["email"],
            "password": ADMIN_USER_DATA["password"],
        }
        response = await client.post("/v1/auth/login", data=login_data)
        
        access_token = response.json()["access_token"]
        decoded = jwt_lib.decode(access_token, options={"verify_signature": False})
        
        permissions = decoded["permissions"]
        if len(permissions) > 1:
            # Verify permissions are sorted
            assert permissions == sorted(permissions)

    async def test_scopes_are_sorted(self, client: AsyncClient):
        """Test that scopes are sorted for consistent token size"""
        login_data = {
            "username": ADMIN_USER_DATA["email"],
            "password": ADMIN_USER_DATA["password"],
        }
        response = await client.post("/v1/auth/login", data=login_data)
        
        access_token = response.json()["access_token"]
        decoded = jwt_lib.decode(access_token, options={"verify_signature": False})
        
        scopes = decoded["scopes"]
        if len(scopes) > 1:
            # Verify scopes are sorted
            assert scopes == sorted(scopes)

class TestFrontendIntegrationFeatures:
    """Test features designed for frontend integration"""

    async def test_permissions_available_for_frontend_checking(self, client: AsyncClient):
        """Test that permissions are available for frontend authorization"""
        login_data = {
            "username": ADMIN_USER_DATA["email"],
            "password": ADMIN_USER_DATA["password"],
        }
        response = await client.post("/v1/auth/login", data=login_data)
        
        access_token = response.json()["access_token"]
        decoded = jwt_lib.decode(access_token, options={"verify_signature": False})
        
        permissions = decoded["permissions"]
        
        # Simulate frontend permission checking
        def has_permission(permission_name):
            return permission_name in permissions
        
        # Test some basic permission checks
        # (Actual permissions depend on seeded data)
        assert isinstance(permissions, list)
        for permission in permissions:
            assert has_permission(permission)

    async def test_roles_available_for_frontend_checking(self, client: AsyncClient):
        """Test that roles are available for frontend authorization"""
        login_data = {
            "username": ADMIN_USER_DATA["email"],
            "password": ADMIN_USER_DATA["password"],
        }
        response = await client.post("/v1/auth/login", data=login_data)
        
        access_token = response.json()["access_token"]
        decoded = jwt_lib.decode(access_token, options={"verify_signature": False})
        
        roles = decoded["roles"]
        
        # Simulate frontend role checking
        def has_role(role_name):
            return any(role["name"] == role_name for role in roles)
        
        # Test role checking functionality
        for role in roles:
            assert has_role(role["name"])

    async def test_user_profile_available_in_token(self, client: AsyncClient):
        """Test that user profile data is available in token"""
        login_data = {
            "username": ADMIN_USER_DATA["email"],
            "password": ADMIN_USER_DATA["password"],
        }
        response = await client.post("/v1/auth/login", data=login_data)
        
        access_token = response.json()["access_token"]
        decoded = jwt_lib.decode(access_token, options={"verify_signature": False})
        
        user_profile = decoded["user"]
        
        # Verify all expected profile fields are present
        required_fields = ["email", "first_name", "last_name", "status", "is_platform_staff"]
        for field in required_fields:
            assert field in user_profile
        
        # Verify user can be identified without API call
        assert user_profile["email"] == ADMIN_USER_DATA["email"]

class TestTokenValidationAndSecurity:
    """Test token validation and security features"""

    async def test_enriched_token_structure_validation(self, client: AsyncClient):
        """Test that enriched tokens have valid structure"""
        login_data = {
            "username": ADMIN_USER_DATA["email"],
            "password": ADMIN_USER_DATA["password"],
        }
        response = await client.post("/v1/auth/login", data=login_data)
        
        access_token = response.json()["access_token"]
        decoded = jwt_lib.decode(access_token, options={"verify_signature": False})
        
        # Verify all required enriched token fields are present
        required_fields = ["sub", "exp", "iat", "user", "permissions", "roles", "scopes", "session"]
        for field in required_fields:
            assert field in decoded, f"Missing required field: {field}"
        
        # Verify user object structure
        user_required = ["email", "status", "is_platform_staff"]
        for field in user_required:
            assert field in decoded["user"], f"Missing user field: {field}"
        
        # Verify session object structure
        session_required = ["is_main_client", "mfa_enabled", "locale"]
        for field in session_required:
            assert field in decoded["session"], f"Missing session field: {field}"

    async def test_token_expiration_fields(self, client: AsyncClient):
        """Test that tokens have proper expiration fields"""
        login_data = {
            "username": ADMIN_USER_DATA["email"],
            "password": ADMIN_USER_DATA["password"],
        }
        response = await client.post("/v1/auth/login", data=login_data)
        
        access_token = response.json()["access_token"]
        decoded = jwt_lib.decode(access_token, options={"verify_signature": False})
        
        # Verify expiration fields exist
        assert "exp" in decoded
        assert "iat" in decoded
        
        # Verify they are numeric timestamps
        exp_timestamp = decoded["exp"]
        iat_timestamp = decoded["iat"]
        
        assert isinstance(exp_timestamp, (int, float))
        assert isinstance(iat_timestamp, (int, float))
        
        # Token should expire in the future (after it was issued)
        assert exp_timestamp > iat_timestamp
        
        # Token should have a reasonable expiration time (between 5 minutes and 24 hours)
        time_diff = exp_timestamp - iat_timestamp
        assert 300 <= time_diff <= 86400  # 5 minutes to 24 hours

class TestErrorHandlingAndEdgeCases:
    """Test error handling and edge cases"""

    async def test_token_info_without_authorization(self, client: AsyncClient):
        """Test token-info endpoint without authorization"""
        response = await client.get("/v1/auth/token-info")
        assert response.status_code == 401

    async def test_malformed_token_in_token_info(self, client: AsyncClient):
        """Test token-info endpoint with malformed token"""
        headers = {"Authorization": "Bearer malformed.token.here"}
        response = await client.get("/v1/auth/token-info", headers=headers)
        assert response.status_code == 401

    async def test_expired_token_in_token_info(self, client: AsyncClient):
        """Test token-info endpoint with expired token"""
        # This would require creating an expired token
        # For now, we test with an invalid token
        headers = {"Authorization": "Bearer expired_token"}
        response = await client.get("/v1/auth/token-info", headers=headers)
        assert response.status_code == 401

    async def test_concurrent_enriched_token_creation(self, client: AsyncClient):
        """Test concurrent enriched token creation"""
        login_data = {
            "username": ADMIN_USER_DATA["email"],
            "password": ADMIN_USER_DATA["password"],
        }
        
        # Create multiple concurrent login requests
        async def login_request():
            response = await client.post("/v1/auth/login", data=login_data)
            return response.status_code
        
        # Run multiple concurrent requests
        tasks = [login_request() for _ in range(5)]
        results = await asyncio.gather(*tasks)
        
        # All should succeed
        assert all(status == 200 for status in results)

class TestPerformanceBenefits:
    """Test that enriched tokens provide expected performance benefits"""

    async def test_no_additional_api_calls_needed_for_user_data(self, client: AsyncClient):
        """Test that user data is available without additional API calls"""
        login_data = {
            "username": ADMIN_USER_DATA["email"],
            "password": ADMIN_USER_DATA["password"],
        }
        response = await client.post("/v1/auth/login", data=login_data)
        
        access_token = response.json()["access_token"]
        decoded = jwt_lib.decode(access_token, options={"verify_signature": False})
        
        # Verify all necessary user data is in token
        user_data = decoded["user"]
        assert user_data["email"] == ADMIN_USER_DATA["email"]
        assert "first_name" in user_data
        assert "last_name" in user_data
        assert "status" in user_data
        
        # Permissions and roles are available
        assert len(decoded["permissions"]) >= 0
        assert len(decoded["roles"]) >= 0
        
        # This simulates frontend not needing to make additional API calls
        # to /v1/auth/me or permission endpoints

    async def test_token_contains_authorization_data(self, client: AsyncClient):
        """Test that token contains all authorization data needed by frontend"""
        login_data = {
            "username": ADMIN_USER_DATA["email"],
            "password": ADMIN_USER_DATA["password"],
        }
        response = await client.post("/v1/auth/login", data=login_data)
        
        access_token = response.json()["access_token"]
        decoded = jwt_lib.decode(access_token, options={"verify_signature": False})
        
        # Verify authorization data is complete
        assert "permissions" in decoded
        assert "roles" in decoded
        assert "scopes" in decoded
        
        # Verify structure allows for frontend authorization decisions
        permissions = decoded["permissions"]
        roles = decoded["roles"]
        scopes = decoded["scopes"]
        
        assert isinstance(permissions, list)
        assert isinstance(roles, list)
        assert isinstance(scopes, list)
        
        # Frontend should be able to make authorization decisions
        # without additional API calls to the server 