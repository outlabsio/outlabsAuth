import pytest
import pytest_asyncio
from bson import ObjectId
import uuid

# Test data for client accounts  
import uuid
import time

def get_unique_client_account_data():
    """Generate unique test data for each test to avoid duplicate key errors."""
    timestamp = int(time.time() * 1000)  # milliseconds
    return {
        "name": f"Test Client Account {timestamp}",
        "description": "Test client account for testing purposes"
    }

# Default test data (will be made unique in each test)
test_client_account_data = get_unique_client_account_data()

class TestClientAccountRoutes:
    """Test suite for client account management routes."""
    
    @pytest_asyncio.fixture(autouse=True)
    async def setup_method(self, client):
        """Setup for each test method."""
        # Login as admin to get auth token
        login_data = {
            "username": "admin@test.com",
            "password": "a_very_secure_password"
        }
        login_response = await client.post("/v1/auth/login", data=login_data)
        assert login_response.status_code == 200
        self.admin_token = login_response.json()["access_token"]
        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
    
    @pytest.mark.asyncio
    async def test_create_client_account_success(self, client):
        """Test creating a client account with valid data."""
        unique_data = get_unique_client_account_data()
        response = await client.post(
            "/v1/client_accounts/",
            json=unique_data,
            headers=self.admin_headers
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == unique_data["name"]
        assert data["description"] == unique_data["description"]
        assert data["status"] == "active"  # Default status
    
    @pytest.mark.asyncio
    async def test_create_client_account_duplicate_name(self, client):
        """Test creating a client account with duplicate name (should fail due to unique constraint)."""
        # First creation should succeed
        unique_data = get_unique_client_account_data()
        response1 = await client.post(
            "/v1/client_accounts/",
            json=unique_data,
            headers=self.admin_headers
        )
        assert response1.status_code == 201
        
        # Duplicate name creation should fail due to unique constraint
        duplicate_data = unique_data.copy()  # Same name
        response2 = await client.post(
            "/v1/client_accounts/",
            json=duplicate_data,
            headers=self.admin_headers
        )
        # Should return 409 Conflict due to duplicate name constraint
        assert response2.status_code == 409
        error_data = response2.json()
        assert "name already exists" in error_data["detail"]
    
    @pytest.mark.asyncio
    async def test_create_client_account_invalid_data(self, client):
        """Test creating a client account with invalid data."""
        invalid_data = {
            "name": "",  # Empty name should be invalid
            "description": "Test description"
        }
        response = await client.post(
            "/v1/client_accounts/",
            json=invalid_data,
            headers=self.admin_headers
        )
        assert response.status_code == 422  # Validation error
    
    @pytest.mark.asyncio
    async def test_create_client_account_unauthorized(self, client):
        """Test creating a client account without proper permissions."""
        response = await client.post(
            "/v1/client_accounts/",
            json=test_client_account_data
        )
        assert response.status_code == 401  # Unauthorized
    
    @pytest.mark.asyncio
    async def test_get_all_client_accounts_success(self, client):
        """Test retrieving all client accounts with admin token."""
        response = await client.get(
            "/v1/client_accounts/",
            headers=self.admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    @pytest.mark.asyncio
    async def test_get_client_accounts_with_pagination(self, client):
        """Test retrieving client accounts with pagination parameters."""
        response = await client.get(
            "/v1/client_accounts/?skip=0&limit=10",
            headers=self.admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) <= 10
    
    @pytest.mark.asyncio
    async def test_get_client_account_by_id_success(self, client):
        """Test retrieving a client account by valid ID."""
        # First create a client account
        unique_data = get_unique_client_account_data()
        create_response = await client.post(
            "/v1/client_accounts/",
            json=unique_data,
            headers=self.admin_headers
        )
        assert create_response.status_code == 201
        created_account = create_response.json()
        account_id = created_account.get("id", created_account.get("_id"))
        
        # Then retrieve it
        response = await client.get(
            f"/v1/client_accounts/{account_id}",
            headers=self.admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == unique_data["name"]
    
    @pytest.mark.asyncio
    async def test_get_client_account_by_invalid_id(self, client):
        """Test retrieving a client account with invalid ID format."""
        response = await client.get(
            "/v1/client_accounts/invalid-id",
            headers=self.admin_headers
        )
        assert response.status_code == 400  # Bad Request for invalid ObjectId format
    
    @pytest.mark.asyncio
    async def test_get_client_account_not_found(self, client):
        """Test retrieving a non-existent client account."""
        fake_id = str(ObjectId())
        response = await client.get(
            f"/v1/client_accounts/{fake_id}",
            headers=self.admin_headers
        )
        assert response.status_code == 404  # Not found
    
    @pytest.mark.asyncio
    async def test_update_client_account_success(self, client):
        """Test updating a client account successfully."""
        # First create a client account
        unique_data = get_unique_client_account_data()
        create_response = await client.post(
            "/v1/client_accounts/",
            json=unique_data,
            headers=self.admin_headers
        )
        assert create_response.status_code == 201
        created_account = create_response.json()
        account_id = created_account.get("id", created_account.get("_id"))
        
        # Then update it
        timestamp = int(time.time() * 1000)
        update_data = {
            "name": f"Updated Client Account Name {timestamp}",
            "description": "Updated description"
        }
        response = await client.put(
            f"/v1/client_accounts/{account_id}",
            json=update_data,
            headers=self.admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == update_data["name"]
        assert data["description"] == update_data["description"]
    
    @pytest.mark.asyncio
    async def test_update_client_account_not_found(self, client):
        """Test updating a non-existent client account."""
        fake_id = str(ObjectId())
        update_data = {
            "name": "Updated Name"
        }
        response = await client.put(
            f"/v1/client_accounts/{fake_id}",
            json=update_data,
            headers=self.admin_headers
        )
        assert response.status_code == 404  # Not found
    
    @pytest.mark.asyncio
    async def test_delete_client_account_success(self, client):
        """Test deleting a client account successfully."""
        # First create a client account
        unique_account_data = get_unique_client_account_data()
        unique_account_data["description"] = "Client account to be deleted"
        create_response = await client.post(
            "/v1/client_accounts/",
            json=unique_account_data,
            headers=self.admin_headers
        )
        assert create_response.status_code == 201
        created_account = create_response.json()
        account_id = created_account.get("id", created_account.get("_id"))
        
        # Then delete it
        response = await client.delete(
            f"/v1/client_accounts/{account_id}",
            headers=self.admin_headers
        )
        assert response.status_code == 204  # No content
    
    @pytest.mark.asyncio
    async def test_delete_client_account_not_found(self, client):
        """Test deleting a non-existent client account."""
        fake_id = str(ObjectId())
        response = await client.delete(
            f"/v1/client_accounts/{fake_id}",
            headers=self.admin_headers
        )
        assert response.status_code == 404  # Not found
    
    @pytest.mark.asyncio
    async def test_client_account_unauthorized_access(self, client):
        """Test unauthorized access to client account endpoints."""
        fake_id = str(ObjectId())
        
        # Test all endpoints without auth token
        endpoints = [
            ("GET", "/v1/client_accounts/"),
            ("GET", f"/v1/client_accounts/{fake_id}"),
            ("POST", "/v1/client_accounts/"),
            ("PUT", f"/v1/client_accounts/{fake_id}"),
            ("DELETE", f"/v1/client_accounts/{fake_id}")
        ]
        
        for method, url in endpoints:
            if method == "GET":
                response = await client.get(url)
            elif method == "POST":
                response = await client.post(url, json=test_client_account_data)
            elif method == "PUT":
                response = await client.put(url, json={"name": "Test"})
            elif method == "DELETE":
                response = await client.delete(url)
            
            assert response.status_code == 401  # Unauthorized 