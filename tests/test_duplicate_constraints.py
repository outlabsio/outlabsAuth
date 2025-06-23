"""
Comprehensive tests for duplicate key constraints and data integrity validation.

This test module ensures that all unique constraints are properly enforced
across the entire application to maintain data integrity.
"""
import pytest
import pytest_asyncio
import asyncio
import time
from bson import ObjectId

class TestDuplicateConstraints:
    """Test suite for validating all unique constraints and data integrity."""
    
    def get_unique_timestamp(self):
        """Generate unique timestamp for test data."""
        return int(time.time() * 1000)
    
    @pytest_asyncio.fixture(autouse=True)
    async def setup_auth(self, client):
        """Set up authentication for tests."""
        # Login as admin to get token
        login_response = await client.post("/v1/auth/login", data={
            "username": "admin@test.com",
            "password": "admin123"  # Use the correct password from conftest
        })
        assert login_response.status_code == 200
        self.admin_token = login_response.json()["access_token"]
        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}

    @pytest.mark.asyncio
    async def test_user_email_unique_constraint(self, client):
        """Test that user emails must be unique."""
        timestamp = self.get_unique_timestamp()
        
        # Create first user
        user_data = {
            "email": f"test_user_{timestamp}@example.com",
            "password": "password123",
            "first_name": "Test",
            "last_name": "User"
        }
        
        response1 = await client.post("/v1/users/", json=user_data, headers=self.admin_headers)
        assert response1.status_code == 201
        
        # Try to create second user with same email - should fail
        duplicate_user_data = user_data.copy()
        duplicate_user_data["first_name"] = "Different"
        
        response2 = await client.post("/v1/users/", json=duplicate_user_data, headers=self.admin_headers)
        assert response2.status_code == 409  # Conflict due to duplicate email
        error_data = response2.json()
        assert "email already exists" in error_data["detail"]

    @pytest.mark.asyncio 
    async def test_client_account_name_unique_constraint(self, client, admin_headers):
        """Test that client account names must be unique."""
        timestamp = self.get_unique_timestamp()
        
        # Create first client account
        account_data = {
            "name": f"Test Account {timestamp}",
            "description": "First account"
        }
        
        response1 = await client.post("/v1/client_accounts/", json=account_data, headers=admin_headers)
        assert response1.status_code == 201
        
        # Try to create second account with same name - should fail
        duplicate_account_data = account_data.copy()
        duplicate_account_data["description"] = "Second account"
        
        response2 = await client.post("/v1/client_accounts/", json=duplicate_account_data, headers=admin_headers)
        assert response2.status_code == 409  # Conflict due to duplicate name
        error_data = response2.json()
        assert "name already exists" in error_data["detail"]

    @pytest.mark.asyncio
    async def test_role_name_unique_constraint(self, client, admin_headers):
        """Test that role names must be unique."""
        timestamp = self.get_unique_timestamp()
        
        # Create first role (using _id field based on schema)
        role_data = {
            "_id": f"test_role_{timestamp}",
            "name": f"Test Role {timestamp}",
            "description": "First role",
            "permissions": ["user:read"]  # Use a valid existing permission
        }
        
        response1 = await client.post("/v1/roles/", json=role_data, headers=admin_headers)
        assert response1.status_code == 201
        
        # Try to create second role with same name - should fail
        duplicate_role_data = {
            "_id": f"test_role_{timestamp}_2",
            "name": f"Test Role {timestamp}",  # Same name
            "description": "Second role",
            "permissions": ["user:read"]
        }
        
        response2 = await client.post("/v1/roles/", json=duplicate_role_data, headers=admin_headers)
        assert response2.status_code == 409  # Conflict due to duplicate name

    @pytest.mark.asyncio
    async def test_role_id_unique_constraint(self, client, admin_headers):
        """Test that role IDs must be unique."""
        timestamp = self.get_unique_timestamp()
        
        # Create first role (using _id field based on schema)
        role_data = {
            "_id": f"test_role_{timestamp}",
            "name": f"Test Role Name {timestamp}",
            "description": "First role",
            "permissions": ["user:read"]  # Use a valid existing permission
        }
        
        response1 = await client.post("/v1/roles/", json=role_data, headers=admin_headers)
        assert response1.status_code == 201
        
        # Try to create second role with same ID - should fail
        duplicate_role_data = {
            "_id": f"test_role_{timestamp}",  # Same ID
            "name": f"Different Role Name {timestamp}",
            "description": "Second role",
            "permissions": ["user:read"]
        }
        
        response2 = await client.post("/v1/roles/", json=duplicate_role_data, headers=admin_headers)
        assert response2.status_code == 409  # Conflict due to duplicate ID

    @pytest.mark.asyncio
    async def test_permission_id_unique_constraint(self, client, admin_headers):
        """Test that permission IDs must be unique."""
        timestamp = self.get_unique_timestamp()
        
        # Create first permission (using _id field based on schema)
        permission_data = {
            "_id": f"test:permission:{timestamp}",
            "description": f"Test Permission {timestamp}"
        }
        
        response1 = await client.post("/v1/permissions/", json=permission_data, headers=admin_headers)
        assert response1.status_code == 201
        
        # Try to create second permission with same ID - should fail
        duplicate_permission_data = {
            "_id": f"test:permission:{timestamp}",  # Same ID
            "description": f"Different Permission Description {timestamp}"
        }
        
        response2 = await client.post("/v1/permissions/", json=duplicate_permission_data, headers=admin_headers)
        assert response2.status_code == 409  # Conflict due to duplicate ID

    @pytest.mark.asyncio
    async def test_update_to_duplicate_values_blocked(self, client, admin_headers):
        """Test that updates to duplicate values are blocked."""
        timestamp = self.get_unique_timestamp()
        
        # Create two users
        user1_data = {
            "email": f"user1_{timestamp}@example.com",
            "password": "password123",
            "first_name": "User",
            "last_name": "One"
        }
        
        user2_data = {
            "email": f"user2_{timestamp}@example.com", 
            "password": "password123",
            "first_name": "User",
            "last_name": "Two"
        }
        
        response1 = await client.post("/v1/users/", json=user1_data, headers=admin_headers)
        assert response1.status_code == 201
        user1 = response1.json()
        
        response2 = await client.post("/v1/users/", json=user2_data, headers=admin_headers)
        assert response2.status_code == 201
        user2 = response2.json()
        
        # Try to update user2 to have user1's email - should fail
        update_data = {"email": user1_data["email"]}
        
        # Use the '_id' field from the response (actual field name from Beanie)
        user2_id = user2["_id"]
        response3 = await client.put(f"/v1/users/{user2_id}", json=update_data, headers=admin_headers)
        assert response3.status_code == 409  # Conflict due to duplicate email

    @pytest.mark.asyncio 
    async def test_case_sensitivity_in_unique_constraints(self, client, admin_headers):
        """Test that unique constraints are case-sensitive where appropriate."""
        timestamp = self.get_unique_timestamp()
        
        # Create user with lowercase email
        user_data = {
            "email": f"testuser_{timestamp}@example.com",
            "password": "password123",
            "first_name": "Test",
            "last_name": "User"
        }
        
        response1 = await client.post("/v1/users/", json=user_data, headers=admin_headers)
        assert response1.status_code == 201
        
        # Try to create user with uppercase email - should succeed (different case)
        uppercase_user_data = user_data.copy()
        uppercase_user_data["email"] = f"TESTUSER_{timestamp}@EXAMPLE.COM"
        uppercase_user_data["first_name"] = "Upper"
        
        response2 = await client.post("/v1/users/", json=uppercase_user_data, headers=admin_headers)
        # Email should be case-insensitive for most systems, but test actual behavior
        # This tests documents the actual behavior of your system
        print(f"Case sensitivity test result: {response2.status_code}")

    @pytest.mark.asyncio
    async def test_concurrent_duplicate_creation_blocked(self, client, admin_headers):
        """Test that concurrent attempts to create duplicates are properly handled."""
        timestamp = self.get_unique_timestamp()
        
        # Create the same client account data
        account_data = {
            "name": f"Concurrent Test Account {timestamp}",
            "description": "Test concurrent creation"
        }
        
        # Attempt to create the same account concurrently
        async def create_account():
            return await client.post("/v1/client_accounts/", json=account_data, headers=admin_headers)
        
        # Execute multiple concurrent requests
        responses = await asyncio.gather(
            create_account(),
            create_account(),
            create_account(),
            return_exceptions=True
        )
        
        # Only one should succeed (201), others should fail (409)
        status_codes = [r.status_code for r in responses if hasattr(r, 'status_code')]
        success_count = sum(1 for code in status_codes if code == 201)
        conflict_count = sum(1 for code in status_codes if code == 409)
        
        assert success_count == 1, f"Expected exactly 1 success, got {success_count}"
        assert conflict_count >= 1, f"Expected at least 1 conflict, got {conflict_count}"

    @pytest.mark.asyncio
    async def test_null_values_in_unique_fields(self, client, admin_headers):
        """Test behavior of unique constraints with null/empty values."""
        timestamp = self.get_unique_timestamp()
        
        # Test client accounts with null description (non-unique field)
        account1_data = {
            "name": f"Account 1 {timestamp}",
            "description": None
        }
        
        account2_data = {
            "name": f"Account 2 {timestamp}",  
            "description": None
        }
        
        response1 = await client.post("/v1/client_accounts/", json=account1_data, headers=admin_headers)
        assert response1.status_code == 201
        
        response2 = await client.post("/v1/client_accounts/", json=account2_data, headers=admin_headers)
        assert response2.status_code == 201  # Should succeed, nulls in non-unique field are OK

    @pytest.mark.asyncio 
    async def test_data_integrity_across_relationships(self, client, admin_headers):
        """Test that data integrity is maintained across related entities."""
        timestamp = self.get_unique_timestamp()
        
        # Create a client account
        account_data = {
            "name": f"Relationship Test Account {timestamp}",
            "description": "Test data integrity"
        }
        
        account_response = await client.post("/v1/client_accounts/", json=account_data, headers=admin_headers)
        assert account_response.status_code == 201
        account = account_response.json()
        account_id = account.get("id", account.get("_id"))
        
        # Create a user associated with this client account
        user_data = {
            "email": f"relationship_user_{timestamp}@example.com",
            "password": "password123",
            "first_name": "Relationship",
            "last_name": "User",
            "client_account_id": account_id
        }
        
        user_response = await client.post("/v1/users/", json=user_data, headers=admin_headers)
        assert user_response.status_code == 201
        user = user_response.json()
        
        # Verify the relationship was established
        assert user.get("client_account_id") == account_id 