import pytest
from fastapi.testclient import TestClient
from bson import ObjectId
import uuid

from api.main import app

client = TestClient(app)

# Test data for client accounts
test_client_account_id = str(uuid.uuid4())
test_client_account_data = {
    "_id": test_client_account_id,
    "name": "Test Client Account",
    "contact_email": "contact@testclient.com",
    "is_active": True
}

class TestClientAccountRoutes:
    """Test suite for client account management routes."""
    
    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Setup for each test method."""
        # Login as admin to get auth token
        login_response = client.post("/v1/auth/login/", json={
            "email": "admin@test.com",
            "password": "admin123"
        })
        assert login_response.status_code == 200
        self.admin_token = login_response.json()["access_token"]
        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
    
    def test_create_client_account_success(self):
        """Test creating a client account with valid data."""
        response = client.post(
            "/v1/client_accounts/",
            json=test_client_account_data,
            headers=self.admin_headers
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == test_client_account_data["name"]
        assert data["contact_email"] == test_client_account_data["contact_email"]
        assert data["is_active"] == test_client_account_data["is_active"]
    
    def test_create_client_account_duplicate_id(self):
        """Test creating a client account with duplicate ID."""
        # First creation should succeed
        response1 = client.post(
            "/v1/client_accounts/",
            json=test_client_account_data,
            headers=self.admin_headers
        )
        assert response1.status_code == 201
        
        # Duplicate creation should fail
        duplicate_data = test_client_account_data.copy()
        response2 = client.post(
            "/v1/client_accounts/",
            json=duplicate_data,
            headers=self.admin_headers
        )
        assert response2.status_code == 409  # Conflict
    
    def test_create_client_account_invalid_data(self):
        """Test creating a client account with invalid data."""
        invalid_data = {
            "_id": str(uuid.uuid4()),
            "name": "",  # Empty name should be invalid
            "contact_email": "invalid-email",  # Invalid email format
            "is_active": True
        }
        response = client.post(
            "/v1/client_accounts/",
            json=invalid_data,
            headers=self.admin_headers
        )
        assert response.status_code == 422  # Validation error
    
    def test_create_client_account_unauthorized(self):
        """Test creating a client account without proper permissions."""
        response = client.post(
            "/v1/client_accounts/",
            json=test_client_account_data
        )
        assert response.status_code == 401  # Unauthorized
    
    def test_get_all_client_accounts_success(self):
        """Test retrieving all client accounts with admin token."""
        response = client.get(
            "/v1/client_accounts/",
            headers=self.admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_get_client_accounts_with_pagination(self):
        """Test retrieving client accounts with pagination parameters."""
        response = client.get(
            "/v1/client_accounts/?skip=0&limit=10",
            headers=self.admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) <= 10
    
    def test_get_client_account_by_id_success(self):
        """Test retrieving a client account by valid ID."""
        # First create a client account
        create_response = client.post(
            "/v1/client_accounts/",
            json=test_client_account_data,
            headers=self.admin_headers
        )
        assert create_response.status_code == 201
        created_account = create_response.json()
        account_id = created_account["id"]
        
        # Then retrieve it
        response = client.get(
            f"/v1/client_accounts/{account_id}",
            headers=self.admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == test_client_account_data["name"]
    
    def test_get_client_account_by_invalid_id(self):
        """Test retrieving a client account with invalid ID format."""
        response = client.get(
            "/v1/client_accounts/invalid-id",
            headers=self.admin_headers
        )
        assert response.status_code == 422  # Validation error
    
    def test_get_client_account_not_found(self):
        """Test retrieving a non-existent client account."""
        fake_id = str(ObjectId())
        response = client.get(
            f"/v1/client_accounts/{fake_id}",
            headers=self.admin_headers
        )
        assert response.status_code == 404  # Not found
    
    def test_update_client_account_success(self):
        """Test updating a client account successfully."""
        # First create a client account
        create_response = client.post(
            "/v1/client_accounts/",
            json=test_client_account_data,
            headers=self.admin_headers
        )
        assert create_response.status_code == 201
        created_account = create_response.json()
        account_id = created_account["id"]
        
        # Then update it
        update_data = {
            "name": "Updated Client Account Name",
            "contact_email": "updated@testclient.com"
        }
        response = client.put(
            f"/v1/client_accounts/{account_id}",
            json=update_data,
            headers=self.admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == update_data["name"]
        assert data["contact_email"] == update_data["contact_email"]
    
    def test_update_client_account_not_found(self):
        """Test updating a non-existent client account."""
        fake_id = str(ObjectId())
        update_data = {
            "name": "Updated Name"
        }
        response = client.put(
            f"/v1/client_accounts/{fake_id}",
            json=update_data,
            headers=self.admin_headers
        )
        assert response.status_code == 404  # Not found
    
    def test_delete_client_account_success(self):
        """Test deleting a client account successfully."""
        # First create a client account
        unique_account_data = {
            "_id": str(uuid.uuid4()),
            "name": "Account to Delete",
            "contact_email": "delete@testclient.com",
            "is_active": True
        }
        create_response = client.post(
            "/v1/client_accounts/",
            json=unique_account_data,
            headers=self.admin_headers
        )
        assert create_response.status_code == 201
        created_account = create_response.json()
        account_id = created_account["id"]
        
        # Then delete it
        response = client.delete(
            f"/v1/client_accounts/{account_id}",
            headers=self.admin_headers
        )
        assert response.status_code == 204  # No content
    
    def test_delete_client_account_not_found(self):
        """Test deleting a non-existent client account."""
        fake_id = str(ObjectId())
        response = client.delete(
            f"/v1/client_accounts/{fake_id}",
            headers=self.admin_headers
        )
        assert response.status_code == 404  # Not found
    
    def test_client_account_unauthorized_access(self):
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
                response = client.get(url)
            elif method == "POST":
                response = client.post(url, json=test_client_account_data)
            elif method == "PUT":
                response = client.put(url, json={"name": "Test"})
            elif method == "DELETE":
                response = client.delete(url)
            
            assert response.status_code == 401  # Unauthorized 