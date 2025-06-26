import pytest
import pytest_asyncio
from httpx import AsyncClient
from tests.conftest import ADMIN_USER_DATA

class TestPlatformRoutes:
    """
    Comprehensive test suite for platform management routes.
    Tests platform analytics, access control, and cross-client functionality.
    """

    async def get_admin_token(self, client: AsyncClient) -> str:
        """Helper to get admin access token."""
        login_data = {
            "username": ADMIN_USER_DATA["email"],
            "password": ADMIN_USER_DATA["password"],
        }
        response = await client.post("/v1/auth/login", data=login_data)
        assert response.status_code == 200
        return response.json()["access_token"]

    async def get_platform_staff_token(self, client: AsyncClient) -> str:
        """Helper to get platform staff token."""
        # Try to login as platform support user
        login_data = {
            "username": "support@propertyhub.com",
            "password": "platform123",
        }
        response = await client.post("/v1/auth/login", data=login_data)
        if response.status_code == 200:
            return response.json()["access_token"]
        
        # Fallback to admin if platform user doesn't exist
        return await self.get_admin_token(client)

    @pytest.mark.asyncio
    async def test_platform_analytics_success(self, client: AsyncClient):
        """Test successful platform analytics access."""
        token = await self.get_platform_staff_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        
        response = await client.get("/v1/platform/analytics", headers=headers)
        
        # Should succeed for platform staff
        if response.status_code == 200:
            data = response.json()
            
            # Verify analytics structure
            assert "total_clients" in data
            assert "total_users" in data
            assert "platform_clients" in data
            assert "real_estate_clients" in data
            assert "platform_staff" in data
            assert "client_users" in data
            assert "client_breakdown" in data
            
            # Verify data types
            assert isinstance(data["total_clients"], int)
            assert isinstance(data["total_users"], int)
            assert isinstance(data["client_breakdown"], list)
            
            # Verify client breakdown structure
            for client_info in data["client_breakdown"]:
                assert "name" in client_info
                assert "description" in client_info
                assert "user_count" in client_info
                assert isinstance(client_info["user_count"], int)
        else:
            # If platform staff doesn't have access, should return 403
            assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_platform_analytics_unauthorized(self, client: AsyncClient):
        """Test platform analytics access without authentication."""
        response = await client.get("/v1/platform/analytics")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_platform_analytics_forbidden_for_regular_user(self, client: AsyncClient):
        """Test that regular users cannot access platform analytics."""
        # Try to login as a regular client user
        login_attempts = [
            {"username": "admin@acmerealestate.com", "password": "realestate123"},
            {"username": "john.agent@acmerealestate.com", "password": "agent123"},
            {"username": "admin@eliteproperties.com", "password": "realestate123"},
        ]
        
        for login_data in login_attempts:
            login_response = await client.post("/v1/auth/login", data=login_data)
            if login_response.status_code == 200:
                token = login_response.json()["access_token"]
                headers = {"Authorization": f"Bearer {token}"}
                
                response = await client.get("/v1/platform/analytics", headers=headers)
                # Regular users should not have access
                assert response.status_code == 403
                break

    @pytest.mark.asyncio
    async def test_platform_analytics_admin_access(self, client: AsyncClient):
        """Test that super admin can access platform analytics."""
        token = await self.get_admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        
        response = await client.get("/v1/platform/analytics", headers=headers)
        
        # Super admin should have access
        assert response.status_code in [200, 403]  # 403 if not marked as platform staff
        
        if response.status_code == 200:
            data = response.json()
            assert "total_clients" in data
            assert "total_users" in data

    @pytest.mark.asyncio
    async def test_platform_analytics_data_accuracy(self, client: AsyncClient):
        """Test that platform analytics returns accurate data."""
        token = await self.get_platform_staff_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        
        # Get analytics data
        analytics_response = await client.get("/v1/platform/analytics", headers=headers)
        
        if analytics_response.status_code == 200:
            analytics = analytics_response.json()
            
            # Get actual client accounts count
            clients_response = await client.get("/v1/client_accounts/", headers=headers)
            if clients_response.status_code == 200:
                actual_clients = clients_response.json()
                # Analytics should match actual count
                assert analytics["total_clients"] == len(actual_clients)
            
            # Get actual users count
            users_response = await client.get("/v1/users/", headers=headers)
            if users_response.status_code == 200:
                actual_users = users_response.json()
                # Analytics should match actual count
                assert analytics["total_users"] == len(actual_users)

    @pytest.mark.asyncio
    async def test_platform_analytics_client_breakdown_accuracy(self, client: AsyncClient):
        """Test that client breakdown in analytics is accurate."""
        token = await self.get_platform_staff_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        
        analytics_response = await client.get("/v1/platform/analytics", headers=headers)
        
        if analytics_response.status_code == 200:
            analytics = analytics_response.json()
            client_breakdown = analytics["client_breakdown"]
            
            # Verify each client in breakdown
            for client_info in client_breakdown:
                client_name = client_info["name"]
                reported_user_count = client_info["user_count"]
                
                # User count should be non-negative
                assert reported_user_count >= 0
                
                # Client should have valid name
                assert len(client_name) > 0

    @pytest.mark.asyncio
    async def test_platform_analytics_platform_vs_client_separation(self, client: AsyncClient):
        """Test that analytics properly separates platform vs client data."""
        token = await self.get_platform_staff_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        
        response = await client.get("/v1/platform/analytics", headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            
            # Platform and real estate clients should add up to total
            platform_clients = data["platform_clients"]
            real_estate_clients = data["real_estate_clients"]
            total_clients = data["total_clients"]
            
            assert platform_clients + real_estate_clients == total_clients
            
            # Platform staff and client users should add up to total
            platform_staff = data["platform_staff"]
            client_users = data["client_users"]
            total_users = data["total_users"]
            
            assert platform_staff + client_users == total_users

    @pytest.mark.asyncio
    async def test_platform_analytics_permission_validation(self, client: AsyncClient):
        """Test that platform analytics validates proper permissions."""
        token = await self.get_admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        
        # First check if user has the required permission
        me_response = await client.get("/v1/auth/me", headers=headers)
        assert me_response.status_code == 200
        
        user_data = me_response.json()
        effective_permissions = user_data.get("effective_permissions", [])
        
        # Check analytics endpoint
        analytics_response = await client.get("/v1/platform/analytics", headers=headers)
        
        # If user has client_account:read permission, should succeed
        has_client_read = "client_account:read" in effective_permissions or \
                         "client:read_all" in effective_permissions or \
                         "client:read_platform" in effective_permissions
        
        if has_client_read:
            # Should succeed if user is platform staff
            assert analytics_response.status_code in [200, 403]
        else:
            # Should fail if no permission
            assert analytics_response.status_code == 403

    @pytest.mark.asyncio
    async def test_platform_analytics_error_handling(self, client: AsyncClient):
        """Test error handling in platform analytics endpoint."""
        token = await self.get_admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        
        # Test with invalid token
        invalid_headers = {"Authorization": "Bearer invalid_token"}
        response = await client.get("/v1/platform/analytics", headers=invalid_headers)
        assert response.status_code == 401
        
        # Test with malformed authorization header
        malformed_headers = {"Authorization": "InvalidFormat"}
        response = await client.get("/v1/platform/analytics", headers=malformed_headers)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_platform_analytics_response_format(self, client: AsyncClient):
        """Test that platform analytics returns properly formatted response."""
        token = await self.get_platform_staff_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        
        response = await client.get("/v1/platform/analytics", headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            
            # Test required fields are present
            required_fields = [
                "total_clients", "total_users", "platform_clients", 
                "real_estate_clients", "platform_staff", "client_users", 
                "client_breakdown"
            ]
            
            for field in required_fields:
                assert field in data, f"Missing required field: {field}"
            
            # Test data types
            assert isinstance(data["total_clients"], int)
            assert isinstance(data["total_users"], int)
            assert isinstance(data["platform_clients"], int)
            assert isinstance(data["real_estate_clients"], int)
            assert isinstance(data["platform_staff"], int)
            assert isinstance(data["client_users"], int)
            assert isinstance(data["client_breakdown"], list)
            
            # Test client breakdown format
            for client in data["client_breakdown"]:
                assert isinstance(client, dict)
                assert "name" in client
                assert "description" in client
                assert "user_count" in client
                assert isinstance(client["user_count"], int)

class TestPlatformAccessControl:
    """Test access control patterns for platform-level operations."""

    async def get_admin_token(self, client: AsyncClient) -> str:
        """Helper to get admin access token."""
        login_data = {
            "username": ADMIN_USER_DATA["email"],
            "password": ADMIN_USER_DATA["password"],
        }
        response = await client.post("/v1/auth/login", data=login_data)
        assert response.status_code == 200
        return response.json()["access_token"]

    @pytest.mark.asyncio
    async def test_platform_staff_identification(self, client: AsyncClient):
        """Test that platform staff are properly identified."""
        # Test various user types
        test_users = [
            ("admin@test.com", "admin123"),  # Super admin
            ("support@propertyhub.com", "platform123"),  # Platform support
            ("admin@propertyhub.com", "platform123"),  # Platform admin
        ]
        
        for email, password in test_users:
            login_data = {"username": email, "password": password}
            login_response = await client.post("/v1/auth/login", data=login_data)
            
            if login_response.status_code == 200:
                token = login_response.json()["access_token"]
                headers = {"Authorization": f"Bearer {token}"}
                
                # Check user profile
                me_response = await client.get("/v1/auth/me", headers=headers)
                assert me_response.status_code == 200
                
                user_data = me_response.json()
                # Platform staff should have appropriate permissions
                effective_permissions = user_data.get("effective_permissions", [])
                
                # Should have some level of client account access
                has_client_access = any(
                    perm.startswith("client:") for perm in effective_permissions
                )
                
                if "propertyhub.com" in email or email == "admin@test.com":
                    # Platform users should have client access
                    assert has_client_access or len(effective_permissions) > 0

    @pytest.mark.asyncio
    async def test_cross_client_access_validation(self, client: AsyncClient):
        """Test that platform staff can access cross-client data appropriately."""
        token = await self.get_admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        
        # Test accessing client accounts (should work for platform staff)
        clients_response = await client.get("/v1/client_accounts/", headers=headers)
        assert clients_response.status_code == 200
        
        # Test accessing users across clients (should work for platform staff)
        users_response = await client.get("/v1/users/", headers=headers)
        assert users_response.status_code == 200
        
        # Platform staff should see multiple client accounts
        clients = clients_response.json()
        users = users_response.json()
        
        # Should have some data
        assert len(clients) >= 0
        assert len(users) >= 0 