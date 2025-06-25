"""
Test suite for access control and data scoping.
Tests that non-platform admin users are properly restricted.
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from beanie import PydanticObjectId
import asyncio

from api.main import app


class TestAccessControl:
    """Test access control for non-platform admin users."""

    def get_unique_timestamp(self):
        """Generate unique timestamp for test data."""
        import time
        return str(int(time.time() * 1000000))

    @pytest_asyncio.fixture(autouse=True)
    async def setup_auth(self, client):
        """Setup authentication for tests."""
        # Login as admin to get auth token for setup
        login_response = await client.post("/v1/auth/login", data={
            "username": "admin@test.com",
            "password": "admin123"
        })
        assert login_response.status_code == 200
        token_data = login_response.json()
        self.admin_headers = {"Authorization": f"Bearer {token_data['access_token']}"}

    @pytest.mark.asyncio
    async def test_client_admin_data_scoping(self, client):
        """Test that client admins can only access users in their client account."""
        timestamp = self.get_unique_timestamp()
        
        # Create two client accounts
        account1_data = {
            "name": f"Client Account 1 {timestamp}",
            "description": "First client account for testing"
        }
        account2_data = {
            "name": f"Client Account 2 {timestamp}",
            "description": "Second client account for testing"
        }
        
        account1_response = await client.post("/v1/client_accounts/", json=account1_data, headers=self.admin_headers)
        assert account1_response.status_code == 201
        account1 = account1_response.json()
        account1_id = account1.get("_id")
        
        account2_response = await client.post("/v1/client_accounts/", json=account2_data, headers=self.admin_headers)
        assert account2_response.status_code == 201
        account2 = account2_response.json()
        account2_id = account2.get("_id")

        # Create client admin user for account 1
        client_admin_data = {
            "email": f"client_admin1_{timestamp}@example.com",
            "password": "password123",
            "first_name": "Client",
            "last_name": "Admin1",
            "client_account_id": account1_id,
            "roles": ["admin"]
        }
        
        admin_response = await client.post("/v1/users/", json=client_admin_data, headers=self.admin_headers)
        assert admin_response.status_code == 201
        client_admin = admin_response.json()

        # Create regular users in both accounts
        user1_data = {
            "email": f"user1_{timestamp}@example.com",
            "password": "password123",
            "first_name": "User",
            "last_name": "One",
            "client_account_id": account1_id
        }
        
        user2_data = {
            "email": f"user2_{timestamp}@example.com",
            "password": "password123",
            "first_name": "User",
            "last_name": "Two",
            "client_account_id": account2_id
        }

        user1_response = await client.post("/v1/users/", json=user1_data, headers=self.admin_headers)
        assert user1_response.status_code == 201
        user1 = user1_response.json()
        
        user2_response = await client.post("/v1/users/", json=user2_data, headers=self.admin_headers)
        assert user2_response.status_code == 201
        user2 = user2_response.json()

        # Login as client admin
        client_admin_login = await client.post("/v1/auth/login", data={
            "username": client_admin_data["email"],
            "password": client_admin_data["password"]
        })
        assert client_admin_login.status_code == 200
        client_admin_token = client_admin_login.json()["access_token"]
        client_admin_headers = {"Authorization": f"Bearer {client_admin_token}"}

        # Client admin should be able to see user1 (same client account)
        user1_get_response = await client.get(f"/v1/users/{user1['_id']}", headers=client_admin_headers)
        assert user1_get_response.status_code == 200

        # Client admin should NOT be able to see user2 (different client account)
        user2_get_response = await client.get(f"/v1/users/{user2['_id']}", headers=client_admin_headers)
        assert user2_get_response.status_code == 404  # Should be blocked by data scoping

        # Client admin should only see users from their client account in list
        users_list_response = await client.get("/v1/users/", headers=client_admin_headers)
        assert users_list_response.status_code == 200
        users_list = users_list_response.json()
        
        # Filter for our test users
        test_user_emails = [user1_data["email"], user2_data["email"], client_admin_data["email"]]
        found_users = [u for u in users_list if u.get("email") in test_user_emails]
        
        # Should only see users from account1 (user1 and client_admin themselves)
        assert len(found_users) == 2
        found_emails = [u["email"] for u in found_users]
        assert client_admin_data["email"] in found_emails
        assert user1_data["email"] in found_emails
        assert user2_data["email"] not in found_emails

    @pytest.mark.asyncio
    async def test_regular_user_cannot_access_other_users(self, client):
        """Test that regular users cannot access other users' data."""
        timestamp = self.get_unique_timestamp()
        
        # Create a client account
        account_data = {
            "name": f"Regular User Test Account {timestamp}",
            "description": "Account for testing regular user access"
        }
        
        account_response = await client.post("/v1/client_accounts/", json=account_data, headers=self.admin_headers)
        assert account_response.status_code == 201
        account = account_response.json()
        account_id = account.get("_id")

        # Create two regular users
        user1_data = {
            "email": f"regular_user1_{timestamp}@example.com",
            "password": "password123",
            "first_name": "Regular",
            "last_name": "User1",
            "client_account_id": account_id,
            "roles": ["basic_user"]
        }
        
        user2_data = {
            "email": f"regular_user2_{timestamp}@example.com",
            "password": "password123",
            "first_name": "Regular",
            "last_name": "User2",
            "client_account_id": account_id,
            "roles": ["basic_user"]
        }

        user1_response = await client.post("/v1/users/", json=user1_data, headers=self.admin_headers)
        assert user1_response.status_code == 201
        user1 = user1_response.json()
        
        user2_response = await client.post("/v1/users/", json=user2_data, headers=self.admin_headers)
        assert user2_response.status_code == 201
        user2 = user2_response.json()

        # Login as user1
        user1_login = await client.post("/v1/auth/login", data={
            "username": user1_data["email"],
            "password": user1_data["password"]
        })
        assert user1_login.status_code == 200
        user1_token = user1_login.json()["access_token"]
        user1_headers = {"Authorization": f"Bearer {user1_token}"}

        # User1 should be able to access their own data
        self_get_response = await client.get(f"/v1/users/{user1['_id']}", headers=user1_headers)
        assert self_get_response.status_code == 200

        # User1 should NOT be able to access user2's data
        other_get_response = await client.get(f"/v1/users/{user2['_id']}", headers=user1_headers)
        assert other_get_response.status_code == 403  # Should be forbidden

        # User1 should NOT be able to list users (requires admin permissions)
        users_list_response = await client.get("/v1/users/", headers=user1_headers)
        assert users_list_response.status_code == 403  # Should be forbidden

    @pytest.mark.asyncio
    async def test_permission_based_access_control(self, client):
        """Test that users can only perform actions they have permissions for."""
        timestamp = self.get_unique_timestamp()
        
        # Create a role with limited permissions (only user:read_self)
        limited_role_data = {
            "name": f"limited_role_{timestamp}",
            "display_name": f"Limited Role {timestamp}",
            "description": "Role with limited permissions",
            "permissions": ["user:read_self"],  # Only self read permission
            "scope": "client"
        }
        
        role_response = await client.post("/v1/roles/", json=limited_role_data, headers=self.admin_headers)
        assert role_response.status_code == 201

        # Create a client account
        account_data = {
            "name": f"Permission Test Account {timestamp}",
            "description": "Account for testing permissions"
        }
        
        account_response = await client.post("/v1/client_accounts/", json=account_data, headers=self.admin_headers)
        assert account_response.status_code == 201
        account = account_response.json()
        account_id = account.get("_id")

        # Create user with limited role
        limited_user_data = {
            "email": f"limited_user_{timestamp}@example.com",
            "password": "password123",
            "first_name": "Limited",
            "last_name": "User",
            "client_account_id": account_id,
            "roles": [limited_role_data["name"]]
        }
        
        limited_user_response = await client.post("/v1/users/", json=limited_user_data, headers=self.admin_headers)
        assert limited_user_response.status_code == 201
        limited_user = limited_user_response.json()

        # Login as limited user
        limited_login = await client.post("/v1/auth/login", data={
            "username": limited_user_data["email"],
            "password": limited_user_data["password"]
        })
        assert limited_login.status_code == 200
        limited_token = limited_login.json()["access_token"]
        limited_headers = {"Authorization": f"Bearer {limited_token}"}

        # User should be able to read their own data (has user:read_self permission)
        read_response = await client.get(f"/v1/users/{limited_user['_id']}", headers=limited_headers)
        assert read_response.status_code == 200

        # User should NOT be able to create new users (lacks user:create permission)
        new_user_data = {
            "email": f"new_user_{timestamp}@example.com",
            "password": "password123",
            "first_name": "New",
            "last_name": "User",
            "client_account_id": account_id
        }
        
        create_response = await client.post("/v1/users/", json=new_user_data, headers=limited_headers)
        assert create_response.status_code == 403  # Should be forbidden

        # User should NOT be able to update users (lacks user:update permission)
        update_data = {"first_name": "Updated"}
        update_response = await client.put(f"/v1/users/{limited_user['_id']}", json=update_data, headers=limited_headers)
        assert update_response.status_code == 403  # Should be forbidden

        # User should NOT be able to delete users (lacks user:delete permission)
        delete_response = await client.delete(f"/v1/users/{limited_user['_id']}", headers=limited_headers)
        assert delete_response.status_code == 403  # Should be forbidden

    @pytest.mark.asyncio
    async def test_cross_client_account_isolation(self, client):
        """Test complete isolation between different client accounts."""
        timestamp = self.get_unique_timestamp()
        
        # Create two separate client accounts
        account1_data = {
            "name": f"Isolation Account 1 {timestamp}",
            "description": "First isolated account"
        }
        account2_data = {
            "name": f"Isolation Account 2 {timestamp}",
            "description": "Second isolated account"
        }
        
        account1_response = await client.post("/v1/client_accounts/", json=account1_data, headers=self.admin_headers)
        assert account1_response.status_code == 201
        account1 = account1_response.json()
        account1_id = account1.get("_id")
        
        account2_response = await client.post("/v1/client_accounts/", json=account2_data, headers=self.admin_headers)
        assert account2_response.status_code == 201
        account2 = account2_response.json()
        account2_id = account2.get("_id")

        # Create client admins for each account
        admin1_data = {
            "email": f"admin1_{timestamp}@example.com",
            "password": "password123",
            "first_name": "Admin",
            "last_name": "One",
            "client_account_id": account1_id,
            "roles": ["admin"]
        }
        
        admin2_data = {
            "email": f"admin2_{timestamp}@example.com",
            "password": "password123",
            "first_name": "Admin",
            "last_name": "Two",
            "client_account_id": account2_id,
            "roles": ["admin"]
        }

        admin1_response = await client.post("/v1/users/", json=admin1_data, headers=self.admin_headers)
        assert admin1_response.status_code == 201
        
        admin2_response = await client.post("/v1/users/", json=admin2_data, headers=self.admin_headers)
        assert admin2_response.status_code == 201

        # Create groups in each account
        group1_data = {
            "name": f"group_1_{timestamp}",
            "display_name": f"Group 1 {timestamp}",
            "description": "Group in account 1",
            "scope": "client"
        }
        
        group2_data = {
            "name": f"group_2_{timestamp}",
            "display_name": f"Group 2 {timestamp}",
            "description": "Group in account 2",
            "scope": "client"
        }

        group1_response = await client.post(f"/v1/groups/?scope_id={account1_id}", json=group1_data, headers=self.admin_headers)
        assert group1_response.status_code == 201
        group1 = group1_response.json()
        
        group2_response = await client.post(f"/v1/groups/?scope_id={account2_id}", json=group2_data, headers=self.admin_headers)
        assert group2_response.status_code == 201
        group2 = group2_response.json()

        # Login as admin1
        admin1_login = await client.post("/v1/auth/login", data={
            "username": admin1_data["email"],
            "password": admin1_data["password"]
        })
        assert admin1_login.status_code == 200
        admin1_token = admin1_login.json()["access_token"]
        admin1_headers = {"Authorization": f"Bearer {admin1_token}"}

        # Admin1 should be able to access group1
        group1_get_response = await client.get(f"/v1/groups/{group1['_id']}", headers=admin1_headers)
        assert group1_get_response.status_code == 200

        # Admin1 should NOT be able to access group2
        group2_get_response = await client.get(f"/v1/groups/{group2['_id']}", headers=admin1_headers)
        assert group2_get_response.status_code == 404  # Should be blocked by data scoping

        # Admin1 should only see groups from their account
        groups_list_response = await client.get("/v1/groups/", headers=admin1_headers)
        assert groups_list_response.status_code == 200
        groups_list = groups_list_response.json()
        
        # Filter for our test groups
        test_group_names = [group1_data["name"], group2_data["name"]]
        found_groups = [g for g in groups_list if g.get("name") in test_group_names]
        
        # Should only see group1
        assert len(found_groups) == 1
        assert found_groups[0]["name"] == group1_data["name"]

    @pytest.mark.asyncio
    async def test_unauthorized_access_attempts(self, client):
        """Test various unauthorized access attempts."""
        timestamp = self.get_unique_timestamp()
        
        # Create a user without any roles/permissions
        no_permissions_data = {
            "email": f"no_perms_{timestamp}@example.com",
            "password": "password123",
            "first_name": "No",
            "last_name": "Permissions"
        }
        
        no_perms_response = await client.post("/v1/users/", json=no_permissions_data, headers=self.admin_headers)
        assert no_perms_response.status_code == 201

        # Login as user with no permissions
        no_perms_login = await client.post("/v1/auth/login", data={
            "username": no_permissions_data["email"],
            "password": no_permissions_data["password"]
        })
        assert no_perms_login.status_code == 200
        no_perms_token = no_perms_login.json()["access_token"]
        no_perms_headers = {"Authorization": f"Bearer {no_perms_token}"}

        # Should not be able to access any admin endpoints
        admin_endpoints = [
            "/v1/users/",
            "/v1/roles/",
            "/v1/permissions/",
            "/v1/groups/",
            "/v1/client_accounts/"
        ]
        
        for endpoint in admin_endpoints:
            response = await client.get(endpoint, headers=no_perms_headers)
            assert response.status_code == 403, f"Expected 403 for {endpoint}, got {response.status_code}"

        # Should not be able to create resources
        test_role_data = {
            "_id": f"unauthorized_role_{timestamp}",
            "name": f"Unauthorized Role {timestamp}",
            "description": "Should not be created",
            "permissions": ["user:read_self"]
        }
        
        create_role_response = await client.post("/v1/roles/", json=test_role_data, headers=no_perms_headers)
        assert create_role_response.status_code == 403 

    @pytest.mark.asyncio
    async def test_regular_user_cannot_access_admin_endpoints(self, client):
        """Test that regular users cannot access admin endpoints."""
        timestamp = self.get_unique_timestamp()
        
        # Create a user without admin roles
        regular_user_data = {
            "email": f"regular_user_{timestamp}@example.com",
            "password": "password123",
            "first_name": "Regular",
            "last_name": "User",
            "roles": ["basic_user"]
        }
        
        user_response = await client.post("/v1/users/", json=regular_user_data, headers=self.admin_headers)
        assert user_response.status_code == 201

        # Login as regular user
        user_login = await client.post("/v1/auth/login", data={
            "username": regular_user_data["email"],
            "password": regular_user_data["password"]
        })
        assert user_login.status_code == 200
        user_token = user_login.json()["access_token"]
        user_headers = {"Authorization": f"Bearer {user_token}"}

        # Should not be able to access admin endpoints
        admin_endpoints = [
            "/v1/users/",
            "/v1/roles/",
            "/v1/permissions/",
            "/v1/groups/",
            "/v1/client_accounts/"
        ]
        
        for endpoint in admin_endpoints:
            response = await client.get(endpoint, headers=user_headers)
            assert response.status_code == 403, f"Expected 403 for {endpoint}, got {response.status_code}" 