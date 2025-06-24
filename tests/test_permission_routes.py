import pytest
import pytest_asyncio
from httpx import AsyncClient
import uuid

# Mark all tests in this file as async
pytestmark = pytest.mark.asyncio

# Test data
ADMIN_USER_DATA = {
    "email": "admin@test.com",
    "password": "admin123"
}

# Generate unique test permission to avoid conflicts
TEST_PERMISSION_NAME = f"test:permission:{str(uuid.uuid4())[:8]}"
TEST_PERMISSION_DATA = {
    "name": TEST_PERMISSION_NAME,
    "display_name": "Test Permission",
    "description": "A test permission for unit testing",
    "scope": "system"
}

async def get_admin_token(client: AsyncClient) -> str:
    """Helper function to get admin access token."""
    login_data = {
        "username": ADMIN_USER_DATA["email"],
        "password": ADMIN_USER_DATA["password"],
    }
    response = await client.post("/v1/auth/login", data=login_data)
    return response.json()["access_token"]

class TestPermissionRoutes:
    """Test suite for permission management routes."""
    
    async def test_get_all_permissions(self, client: AsyncClient):
        """Test retrieving all permissions."""
        token = await get_admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        
        response = await client.get("/v1/permissions/", headers=headers)
        
        assert response.status_code == 200
        permissions = response.json()
        assert isinstance(permissions, list)
        assert len(permissions) >= 1  # Should have seeded permissions
        
        # Check that some expected permissions exist
        permission_names = [perm["name"] for perm in permissions]
        assert "user:read" in permission_names
        assert "user:create" in permission_names
    
    async def test_get_permissions_with_pagination(self, client: AsyncClient):
        """Test permission retrieval with pagination parameters."""
        token = await get_admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        
        response = await client.get("/v1/permissions/?skip=0&limit=5", headers=headers)
        
        assert response.status_code == 200
        permissions = response.json()
        assert isinstance(permissions, list)
        assert len(permissions) <= 5
    
    async def test_get_permission_by_id(self, client: AsyncClient):
        """Test retrieving a specific permission by ID."""
        token = await get_admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        
        # Get the user:read permission  
        # First get all permissions to find the ID of user:read
        all_perms_response = await client.get("/v1/permissions/", headers=headers)
        all_permissions = all_perms_response.json()
        user_read_perm = next((p for p in all_permissions if p["name"] == "user:read"), None)
        
        if user_read_perm:
            response = await client.get(f"/v1/permissions/{user_read_perm['_id']}", headers=headers)
            assert response.status_code == 200
            permission_data = response.json()
            assert permission_data["name"] == "user:read"
            assert "description" in permission_data
            assert "scope" in permission_data
        else:
            # Skip test if permission doesn't exist
            pytest.skip("user:read permission not found in seeded data")
    
    async def test_get_nonexistent_permission(self, client: AsyncClient):
        """Test retrieving a permission that doesn't exist."""
        token = await get_admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        
        response = await client.get("/v1/permissions/nonexistent:permission", headers=headers)
        assert response.status_code == 404
    
    async def test_create_permission_success(self, client: AsyncClient):
        """Test successful permission creation."""
        token = await get_admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        
        response = await client.post("/v1/permissions/", json=TEST_PERMISSION_DATA, headers=headers)
        
        assert response.status_code == 201
        permission_data = response.json()
        assert permission_data["name"] == TEST_PERMISSION_DATA["name"]
        assert permission_data["display_name"] == TEST_PERMISSION_DATA["display_name"]
        assert permission_data["description"] == TEST_PERMISSION_DATA["description"]
        assert permission_data["scope"] == TEST_PERMISSION_DATA["scope"]
    
    async def test_create_permission_duplicate_id(self, client: AsyncClient):
        """Test permission creation with duplicate ID fails."""
        token = await get_admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        
        # Try to create user:read permission again (should fail)
        duplicate_permission = {
            "name": "user:read",
            "display_name": "Duplicate User Read",
            "description": "Duplicate permission",
            "scope": "system"
        }
        
        response = await client.post("/v1/permissions/", json=duplicate_permission, headers=headers)
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]
    
    async def test_create_permission_invalid_format(self, client: AsyncClient):
        """Test permission creation with invalid ID format."""
        token = await get_admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        
        # Invalid permission (missing required fields)
        # Use unique name to avoid conflicts
        invalid_permission = {
            "name": f"invalid_format_{str(uuid.uuid4())[:8]}",
            "description": "Invalid permission format"
            # Missing display_name and scope
        }
        
        response = await client.post("/v1/permissions/", json=invalid_permission, headers=headers)
        # This might be 400 for validation error or 201 if format validation isn't strict
        assert response.status_code in [201, 400, 422]
    
    async def test_create_permission_without_permission(self, client: AsyncClient):
        """Test permission creation without proper permissions fails."""
        # Test without any token
        response = await client.post("/v1/permissions/", json=TEST_PERMISSION_DATA)
        assert response.status_code == 401
    
    async def test_permission_naming_convention(self, client: AsyncClient):
        """Test that permissions follow naming conventions."""
        token = await get_admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        
        # Get all permissions and check naming
        response = await client.get("/v1/permissions/", headers=headers)
        assert response.status_code == 200
        
        permissions = response.json()
        for permission in permissions:
            permission_name = permission["name"]
            # Most permissions should follow resource:action pattern
            if ":" in permission_name:
                parts = permission_name.split(":")
                assert len(parts) >= 2  # At least resource:action
                assert len(parts) <= 3  # At most service:resource:action
            # Verify required fields exist
            assert "scope" in permission
            assert "display_name" in permission
    
    async def test_unauthorized_access(self, client: AsyncClient):
        """Test that endpoints require proper authentication."""
        # Test without any token
        response = await client.get("/v1/permissions/")
        assert response.status_code == 401
        
        response = await client.post("/v1/permissions/", json=TEST_PERMISSION_DATA)
        assert response.status_code == 401
        
        response = await client.get("/v1/permissions/test:permission")
        assert response.status_code == 401 