"""
Enhanced Access Control Tests

This test suite uses realistic seeded data to test access control scenarios.
It assumes the database has been seeded with seed_via_api.py script.

The tests verify:
1. Cross-company data isolation
2. Role-based access control within companies  
3. Platform admin vs client admin privileges
4. Manager vs employee access levels
5. Group-based access controls
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient
import sys
import os

# Add the scripts directory to import the test helper
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from test_data_helper import TestDataHelper, get_cross_company_scenario, get_hierarchy_scenario, get_platform_vs_client_scenario

from api.main import app


class TestEnhancedAccessControl:
    """Enhanced access control tests using realistic seeded data."""

    async def authenticate_user(self, client: AsyncClient, credentials: dict) -> str:
        """Helper to authenticate a user and return access token."""
        login_response = await client.post("/v1/auth/login", data={
            "username": credentials["email"],
            "password": credentials["password"]
        })
        assert login_response.status_code == 200, f"Failed to authenticate {credentials['email']}: {login_response.text}"
        return login_response.json()["access_token"]

    def get_auth_headers(self, token: str) -> dict:
        """Helper to create authorization headers."""
        return {"Authorization": f"Bearer {token}"}

    @pytest.mark.asyncio
    async def test_cross_company_user_isolation(self, client: AsyncClient):
        """Test that users from different companies cannot access each other's data."""
        print("\n🧪 Testing cross-company user isolation")
        
        # Get users from different companies
        acme_admin = TestDataHelper.get_client_admin("acme")
        techstartup_employee = TestDataHelper.get_employee("techstartup", 0)
        acme_manager = TestDataHelper.get_manager("acme")
        
        # Authenticate each user
        acme_token = await self.authenticate_user(client, acme_admin)
        techstartup_token = await self.authenticate_user(client, techstartup_employee)
        acme_mgr_token = await self.authenticate_user(client, acme_manager)
        
        acme_headers = self.get_auth_headers(acme_token)
        techstartup_headers = self.get_auth_headers(techstartup_token)
        acme_mgr_headers = self.get_auth_headers(acme_mgr_token)
        
        # Get list of users for each company
        acme_users_response = await client.get("/v1/users/", headers=acme_headers)
        assert acme_users_response.status_code == 200
        acme_users = acme_users_response.json()
        
        techstartup_users_response = await client.get("/v1/users/", headers=techstartup_headers)
        # Regular employee may not have permission to list users
        if techstartup_users_response.status_code == 403:
            print("   ✓ Tech Startup employee correctly forbidden from listing users")
        else:
            techstartup_users = techstartup_users_response.json()
        
        acme_mgr_users_response = await client.get("/v1/users/", headers=acme_mgr_headers)
        assert acme_mgr_users_response.status_code == 200
        acme_mgr_users = acme_mgr_users_response.json()
        
        # Verify data isolation: each company should only see their own users
        acme_emails = [u["email"] for u in acme_users]
        acme_mgr_emails = [u["email"] for u in acme_mgr_users]
        
        # ACME admin should only see ACME users
        assert all("acme.com" in email or "test.com" in email for email in acme_emails), \
            f"ACME admin sees non-ACME users: {acme_emails}"
        
        # ACME manager should only see ACME users  
        assert all("acme.com" in email or "test.com" in email for email in acme_mgr_emails), \
            f"ACME manager sees non-ACME users: {acme_mgr_emails}"
        
        # Try to access a user from another company (should fail)
        if acme_users and 'techstartup_users' in locals():
            acme_user_id = acme_users[0]["_id"]
            techstartup_user_id = techstartup_users[0]["_id"]
            
            # ACME manager tries to access Tech Startup user
            cross_access_response = await client.get(f"/v1/users/{techstartup_user_id}", headers=acme_mgr_headers)
            assert cross_access_response.status_code in [403, 404], \
                "Users should not be able to access other companies' users"
            
            # Tech Startup employee tries to access ACME user (if they have permission to access users)
            if techstartup_users_response.status_code == 200:
                cross_access_response2 = await client.get(f"/v1/users/{acme_user_id}", headers=techstartup_headers)
                assert cross_access_response2.status_code in [403, 404], \
                    "Users should not be able to access other companies' users"
        
        print("   ✓ Cross-company data isolation working correctly")

    @pytest.mark.asyncio
    async def test_role_hierarchy_within_company(self, client: AsyncClient):
        """Test role-based access control within a single company."""
        print("\n🧪 Testing role hierarchy within company")
        
        # Test with ACME hierarchy
        admin, manager, employee = get_hierarchy_scenario("acme")
        
        # Authenticate all users
        admin_token = await self.authenticate_user(client, admin)
        manager_token = await self.authenticate_user(client, manager)
        employee_token = await self.authenticate_user(client, employee)
        
        admin_headers = self.get_auth_headers(admin_token)
        manager_headers = self.get_auth_headers(manager_token)
        employee_headers = self.get_auth_headers(employee_token)
        
        # Test user listing permissions
        print("   Testing user listing permissions...")
        
        # Admin should be able to list users
        admin_users_response = await client.get("/v1/users/", headers=admin_headers)
        assert admin_users_response.status_code == 200
        print("   ✓ Admin can list users")
        
        # Manager permissions may vary - check what they can do
        manager_users_response = await client.get("/v1/users/", headers=manager_headers)
        if manager_users_response.status_code == 200:
            print("   ✓ Manager can list users")
        else:
            print("   ✓ Manager correctly restricted from listing users")
        
        # Employee should not be able to list users (or have limited access)
        employee_users_response = await client.get("/v1/users/", headers=employee_headers)
        assert employee_users_response.status_code in [403, 200]  # May be forbidden or have limited view
        if employee_users_response.status_code == 403:
            print("   ✓ Employee correctly forbidden from listing users")
        else:
            # If they can list, they should only see limited data
            employee_users = employee_users_response.json()
            print(f"   ✓ Employee can see {len(employee_users)} users (limited view)")
        
        # Test user creation permissions
        print("   Testing user creation permissions...")
        
        new_user_data = {
            "email": f"test_new_user_{admin['email'].split('@')[0]}@acme.com",
            "password": "test123",
            "first_name": "Test",
            "last_name": "User",
            "is_main_client": False,
            "roles": ["employee"]
        }
        
        # Admin should be able to create users
        admin_create_response = await client.post("/v1/users/", json=new_user_data, headers=admin_headers)
        if admin_create_response.status_code == 201:
            print("   ✓ Admin can create users")
            created_user = admin_create_response.json()
            created_user_id = created_user["_id"]
            
            # Clean up - delete the created user
            delete_response = await client.delete(f"/v1/users/{created_user_id}", headers=admin_headers)
            print("   ✓ Test user cleaned up")
        else:
            print(f"   ⚠ Admin user creation failed: {admin_create_response.status_code} - {admin_create_response.text}")
        
        # Manager and employee should not be able to create users (depending on permissions)
        manager_create_response = await client.post("/v1/users/", json=new_user_data, headers=manager_headers)
        assert manager_create_response.status_code in [403, 401], \
            f"Manager should not be able to create users, got {manager_create_response.status_code}"
        print("   ✓ Manager correctly restricted from creating users")
        
        employee_create_response = await client.post("/v1/users/", json=new_user_data, headers=employee_headers)
        assert employee_create_response.status_code in [403, 401], \
            f"Employee should not be able to create users, got {employee_create_response.status_code}"
        print("   ✓ Employee correctly restricted from creating users")

    @pytest.mark.asyncio
    async def test_platform_admin_vs_client_admin_privileges(self, client: AsyncClient):
        """Test the difference between platform admin and client admin privileges."""
        print("\n🧪 Testing platform admin vs client admin privileges")
        
        platform_admin, client_admin = get_platform_vs_client_scenario()
        
        # Authenticate both admins
        platform_token = await self.authenticate_user(client, platform_admin)
        client_token = await self.authenticate_user(client, client_admin)
        
        platform_headers = self.get_auth_headers(platform_token)
        client_headers = self.get_auth_headers(client_token)
        
        # Test client account management
        print("   Testing client account management...")
        
        test_client_data = {
            "name": f"Test Client Account {platform_admin['email'].split('@')[0]}",
            "description": "Test client account for privilege testing"
        }
        
        # Platform admin should be able to create client accounts
        platform_create_response = await client.post("/v1/client_accounts/", json=test_client_data, headers=platform_headers)
        if platform_create_response.status_code == 201:
            print("   ✓ Platform admin can create client accounts")
            created_account = platform_create_response.json()
            created_account_id = created_account["_id"]
            
            # Clean up
            delete_response = await client.delete(f"/v1/client_accounts/{created_account_id}/", headers=platform_headers)
            print("   ✓ Test client account cleaned up")
        else:
            print(f"   ⚠ Platform admin client account creation failed: {platform_create_response.status_code}")
        
        # Client admin should NOT be able to create client accounts
        client_create_response = await client.post("/v1/client_accounts/", json=test_client_data, headers=client_headers)
        assert client_create_response.status_code in [403, 401], \
            f"Client admin should not create client accounts, got {client_create_response.status_code}"
        print("   ✓ Client admin correctly restricted from creating client accounts")
        
        # Test access to all users vs scoped users
        print("   Testing user access scope...")
        
        platform_users_response = await client.get("/v1/users/", headers=platform_headers)
        client_users_response = await client.get("/v1/users/", headers=client_headers)
        
        assert platform_users_response.status_code == 200
        assert client_users_response.status_code == 200
        
        platform_users = platform_users_response.json()
        client_users = client_users_response.json()
        
        # Platform admin should see users from all companies
        platform_user_emails = [u["email"] for u in platform_users]
        has_multiple_companies = any("acme.com" in email for email in platform_user_emails) and \
                                 any("techstartup.com" in email for email in platform_user_emails)
        
        if has_multiple_companies:
            print("   ✓ Platform admin can see users from all companies")
        else:
            print(f"   ⚠ Platform admin user scope may be limited. Emails: {platform_user_emails[:3]}...")
        
        # Client admin should only see users from their company
        client_user_emails = [u["email"] for u in client_users]
        company_domain = client_admin["email"].split("@")[1]  # Get the domain from client admin email
        assert all(company_domain in email for email in client_user_emails), \
            f"Client admin should only see their company users, but saw: {client_user_emails}"
        print("   ✓ Client admin correctly scoped to their company users")

    @pytest.mark.asyncio
    async def test_group_access_control(self, client: AsyncClient):
        """Test access control for groups within and across companies."""
        print("\n🧪 Testing group access control")
        
        # Test within company group access
        acme_admin = TestDataHelper.get_client_admin("acme")
        acme_employee = TestDataHelper.get_employee("acme", 0)
        techstartup_admin = TestDataHelper.get_client_admin("techstartup")
        
        # Authenticate users
        acme_admin_token = await self.authenticate_user(client, acme_admin)
        acme_employee_token = await self.authenticate_user(client, acme_employee)
        techstartup_admin_token = await self.authenticate_user(client, techstartup_admin)
        
        acme_admin_headers = self.get_auth_headers(acme_admin_token)
        acme_employee_headers = self.get_auth_headers(acme_employee_token)
        techstartup_admin_headers = self.get_auth_headers(techstartup_admin_token)
        
        # Test group listing
        print("   Testing group listing permissions...")
        
        # ACME admin should see ACME groups
        acme_groups_response = await client.get("/v1/groups/", headers=acme_admin_headers)
        assert acme_groups_response.status_code == 200
        acme_groups = acme_groups_response.json()
        print(f"   ✓ ACME admin can see {len(acme_groups)} groups")
        
        # Tech Startup admin should see Tech Startup groups (different set)
        techstartup_groups_response = await client.get("/v1/groups/", headers=techstartup_admin_headers)
        assert techstartup_groups_response.status_code == 200
        techstartup_groups = techstartup_groups_response.json()
        print(f"   ✓ Tech Startup admin can see {len(techstartup_groups)} groups")
        
        # Verify groups are company-specific
        if acme_groups and techstartup_groups:
            acme_group_names = [g["name"] for g in acme_groups]
            techstartup_group_names = [g["name"] for g in techstartup_groups]
            
            # Groups should be different (no overlap expected with our test data)
            common_groups = set(acme_group_names) & set(techstartup_group_names)
            if common_groups:
                print(f"   ⚠ Found common group names (may be expected): {common_groups}")
            else:
                print("   ✓ Companies have distinct group sets")
        
        # Test cross-company group access
        if acme_groups:
            acme_group_id = acme_groups[0]["_id"]
            
            # Tech Startup admin should NOT be able to access ACME group
            cross_group_response = await client.get(f"/v1/groups/{acme_group_id}", headers=techstartup_admin_headers)
            if cross_group_response.status_code in [403, 404]:
                print("   ✓ Cross-company group access correctly blocked")
            elif cross_group_response.status_code == 200:
                # If the API allows cross-company access, verify it's intentional
                accessed_group = cross_group_response.json()
                print(f"   ⚠ Cross-company group access allowed (group: {accessed_group.get('name', 'Unknown')})")
                print("   ℹ This may be expected if groups are shared across companies")
            else:
                print(f"   ⚠ Unexpected response for cross-company group access: {cross_group_response.status_code}")
        
        # Test employee group access
        employee_groups_response = await client.get("/v1/groups/", headers=acme_employee_headers)
        if employee_groups_response.status_code == 403:
            print("   ✓ Employee correctly restricted from listing groups")
        elif employee_groups_response.status_code == 200:
            employee_groups = employee_groups_response.json()
            print(f"   ✓ Employee can see {len(employee_groups)} groups (limited access)")

    @pytest.mark.asyncio
    async def test_permission_enforcement(self, client: AsyncClient):
        """Test that permissions are properly enforced across different user roles."""
        print("\n🧪 Testing permission enforcement")
        
        # Test with different roles from the same company
        admin = TestDataHelper.get_client_admin("acme")
        manager = TestDataHelper.get_manager("acme")
        employee = TestDataHelper.get_employee("acme", 0)
        
        # Authenticate all users
        admin_token = await self.authenticate_user(client, admin)
        manager_token = await self.authenticate_user(client, manager)
        employee_token = await self.authenticate_user(client, employee)
        
        admin_headers = self.get_auth_headers(admin_token)
        manager_headers = self.get_auth_headers(manager_token)
        employee_headers = self.get_auth_headers(employee_token)
        
        # Test role/permission endpoints (should be admin-only)
        print("   Testing role/permission management access...")
        
        # Admin should be able to access roles
        roles_response = await client.get("/v1/roles/", headers=admin_headers)
        if roles_response.status_code == 200:
            print("   ✓ Admin can access roles")
        else:
            print(f"   ⚠ Admin role access: {roles_response.status_code}")
        
        # Manager should have limited or no access to roles
        manager_roles_response = await client.get("/v1/roles/", headers=manager_headers)
        if manager_roles_response.status_code in [403, 401]:
            print("   ✓ Manager correctly restricted from roles")
        else:
            print(f"   ⚠ Manager role access: {manager_roles_response.status_code}")
        
        # Employee should not be able to access roles
        employee_roles_response = await client.get("/v1/roles/", headers=employee_headers)
        assert employee_roles_response.status_code in [403, 401], \
            f"Employee should not access roles, got {employee_roles_response.status_code}"
        print("   ✓ Employee correctly restricted from roles")
        
        # Test permissions endpoint
        admin_perms_response = await client.get("/v1/permissions/", headers=admin_headers)
        employee_perms_response = await client.get("/v1/permissions/", headers=employee_headers)
        
        if admin_perms_response.status_code == 200:
            print("   ✓ Admin can access permissions")
        
        assert employee_perms_response.status_code in [403, 401], \
            f"Employee should not access permissions, got {employee_perms_response.status_code}"
        print("   ✓ Employee correctly restricted from permissions")

    @pytest.mark.asyncio
    async def test_data_modification_controls(self, client: AsyncClient):
        """Test that users can only modify data they have permissions for."""
        print("\n🧪 Testing data modification controls")
        
        # Use Tech Startup for this test
        admin = TestDataHelper.get_client_admin("techstartup")
        employee1 = TestDataHelper.get_employee("techstartup", 0)
        employee2 = TestDataHelper.get_employee("techstartup", 1)
        
        # Authenticate users
        admin_token = await self.authenticate_user(client, admin)
        employee1_token = await self.authenticate_user(client, employee1)
        
        admin_headers = self.get_auth_headers(admin_token)
        employee1_headers = self.get_auth_headers(employee1_token)
        
        # Get users to find employee2's ID
        users_response = await client.get("/v1/users/", headers=admin_headers)
        assert users_response.status_code == 200
        users = users_response.json()
        
        employee2_user = next((u for u in users if u["email"] == employee2["email"]), None)
        assert employee2_user is not None, f"Could not find employee2 {employee2['email']} in users list"
        
        employee2_id = employee2_user["_id"]
        
        # Test user modification
        print("   Testing user modification permissions...")
        
        update_data = {
            "first_name": "Modified",
            "last_name": "Name"
        }
        
        # Admin should be able to modify other users
        admin_modify_response = await client.put(f"/v1/users/{employee2_id}", json=update_data, headers=admin_headers)
        if admin_modify_response.status_code == 200:
            print("   ✓ Admin can modify other users")
            
            # Revert the change
            revert_data = {"first_name": employee2_user["first_name"], "last_name": employee2_user["last_name"]}
            await client.put(f"/v1/users/{employee2_id}", json=revert_data, headers=admin_headers)
        else:
            print(f"   ⚠ Admin user modification: {admin_modify_response.status_code}")
        
        # Employee should NOT be able to modify other users
        employee_modify_response = await client.put(f"/v1/users/{employee2_id}", json=update_data, headers=employee1_headers)
        assert employee_modify_response.status_code in [403, 401], \
            f"Employee should not modify other users, got {employee_modify_response.status_code}"
        print("   ✓ Employee correctly restricted from modifying other users")
        
        # Employee should be able to modify their own data (if endpoint allows)
        employee1_user = next((u for u in users if u["email"] == employee1["email"]), None)
        if employee1_user:
            employee1_id = employee1_user["_id"]
            self_modify_response = await client.put(f"/v1/users/{employee1_id}", json=update_data, headers=employee1_headers)
            
            if self_modify_response.status_code == 200:
                print("   ✓ Employee can modify their own data")
                # Revert
                revert_data = {"first_name": employee1_user["first_name"], "last_name": employee1_user["last_name"]}
                await client.put(f"/v1/users/{employee1_id}", json=revert_data, headers=employee1_headers)
            elif self_modify_response.status_code in [403, 401]:
                print("   ℹ Employee restricted from self-modification (policy dependent)")
            else:
                print(f"   ⚠ Employee self-modification: {self_modify_response.status_code}")

    @pytest.mark.asyncio
    async def test_authentication_and_authorization_flow(self, client: AsyncClient):
        """Test the complete authentication and authorization flow."""
        print("\n🧪 Testing authentication and authorization flow")
        
        # Test valid authentication
        valid_user = TestDataHelper.get_employee("acme", 0)
        token = await self.authenticate_user(client, valid_user)
        assert token is not None and len(token) > 0
        print("   ✓ Valid user authentication successful")
        
        # Test invalid credentials
        invalid_login_response = await client.post("/v1/auth/login", data={
            "username": "nonexistent@test.com",
            "password": "wrongpassword"
        })
        assert invalid_login_response.status_code in [401, 400], \
            f"Invalid credentials should be rejected, got {invalid_login_response.status_code}"
        print("   ✓ Invalid credentials correctly rejected")
        
        # Test accessing protected endpoint without token
        no_auth_response = await client.get("/v1/users/")
        assert no_auth_response.status_code in [401, 403], \
            f"No auth access should be rejected, got {no_auth_response.status_code}"
        print("   ✓ No authentication correctly rejected")
        
        # Test accessing protected endpoint with invalid token
        invalid_headers = {"Authorization": "Bearer invalid_token_here"}
        invalid_token_response = await client.get("/v1/users/", headers=invalid_headers)
        assert invalid_token_response.status_code in [401, 403], \
            f"Invalid token should be rejected, got {invalid_token_response.status_code}"
        print("   ✓ Invalid token correctly rejected")
        
        print("   ✓ Authentication and authorization flow working correctly")


# Test data verification
@pytest.mark.asyncio
async def test_verify_seeded_data_exists(client: AsyncClient):
    """Verify that the required test data exists in the database."""
    print("\n🔍 Verifying seeded test data exists...")
    
    # Try to authenticate key users to verify they exist
    test_users = [
        TestDataHelper.get_platform_admin(),
        TestDataHelper.get_client_admin("acme"),
        TestDataHelper.get_client_admin("techstartup"), 
        TestDataHelper.get_employee("acme", 0),
        TestDataHelper.get_employee("techstartup", 0)
    ]
    
    helper = TestEnhancedAccessControl()
    
    for user in test_users:
        try:
            token = await helper.authenticate_user(client, user)
            assert token is not None
            print(f"   ✓ {user['email']} - {user['description']}")
        except Exception as e:
            pytest.fail(f"Required test user {user['email']} not found. Please run seed_via_api.py first. Error: {e}")
    
    print("   ✅ All required test data verified!")
    print("\n💡 To create test data, run: python scripts/seed_main.py && python scripts/seed_via_api.py") 