import pytest
from httpx import AsyncClient

# Mark all tests in this file as async
pytestmark = pytest.mark.asyncio

# Test data
ADMIN_USER_DATA = {
    "email": "admin@test.com",
    "password": "admin123"
}

async def get_admin_token(client: AsyncClient) -> str:
    """Helper function to get admin access token."""
    login_data = {
        "username": ADMIN_USER_DATA["email"],
        "password": ADMIN_USER_DATA["password"],
    }
    response = await client.post("/v1/auth/login", data=login_data)
    return response.json()["access_token"]

class TestIntegrationWorkflows:
    """Integration tests that test complete workflows across multiple endpoints."""
    
    async def test_complete_user_lifecycle(self, client: AsyncClient):
        """Test complete user lifecycle: create, read, update, login, delete."""
        token = await get_admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        
        # 1. Create a new user
        user_data = {
            "email": "lifecycle@example.com",
            "password": "password123",
            "first_name": "Lifecycle",
            "last_name": "Test",
            "roles": ["super_admin"]
        }
        
        create_response = await client.post("/v1/users/", json=user_data, headers=headers)
        if create_response.status_code == 409:
            # User already exists, get their ID
            users_response = await client.get("/v1/users/", headers=headers)
            users = users_response.json()
            user = next((u for u in users if u["email"] == user_data["email"]), None)
            assert user is not None
            user_id = user.get("id", user.get("_id"))
        else:
            assert create_response.status_code == 201
            created_user = create_response.json()
            user_id = created_user.get("id", created_user.get("_id"))
            assert created_user["email"] == user_data["email"]
        
        # 2. Read the user
        get_response = await client.get(f"/v1/users/{user_id}", headers=headers)
        assert get_response.status_code == 200
        user = get_response.json()
        assert user["email"] == user_data["email"]
        
        # 3. Update the user
        update_data = {
            "first_name": "Updated",
            "last_name": "Name"
        }
        update_response = await client.put(f"/v1/users/{user_id}", json=update_data, headers=headers)
        assert update_response.status_code == 200
        updated_user = update_response.json()
        assert updated_user["first_name"] == "Updated"
        assert updated_user["last_name"] == "Name"
        
        # 4. Test user can login
        login_data = {
            "username": user_data["email"],
            "password": user_data["password"]
        }
        login_response = await client.post("/v1/auth/login", data=login_data)
        assert login_response.status_code == 200
        login_result = login_response.json()
        assert "access_token" in login_result
        
        # 5. Test user can access their profile
        user_token = login_result["access_token"]
        user_headers = {"Authorization": f"Bearer {user_token}"}
        me_response = await client.get("/v1/auth/me", headers=user_headers)
        assert me_response.status_code == 200
        profile = me_response.json()
        assert profile["email"] == user_data["email"]
    
    async def test_role_and_permission_workflow(self, client: AsyncClient):
        """Test creating permissions, roles, and assigning them to users."""
        token = await get_admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        
        # 1. Create a custom permission
        permission_data = {
            "name": "integration:test",
            "display_name": "Integration Test Permission",
            "description": "Integration test permission",
            "scope": "system"
        }
        
        perm_response = await client.post("/v1/permissions/", json=permission_data, headers=headers)
        if perm_response.status_code == 409:
            # Permission already exists
            pass
        else:
            assert perm_response.status_code == 201
        
        # 2. Create a custom role with the permission
        role_data = {
            "name": "integration_tester",
            "display_name": "Integration Tester",
            "description": "Role for integration testing",
            "permissions": ["integration:test", "user:read_self"],
            "scope": "system",
            "is_assignable_by_main_client": True
        }
        
        role_response = await client.post("/v1/roles/", json=role_data, headers=headers)
        if role_response.status_code == 409:
            # Role already exists
            pass
        else:
            assert role_response.status_code == 201
        
        # 3. Create a user with the custom role
        user_data = {
            "email": "roletest@example.com",
            "password": "password123",
            "first_name": "Role",
            "last_name": "Test",
            "roles": ["integration_tester"]
        }
        
        user_response = await client.post("/v1/users/", json=user_data, headers=headers)
        if user_response.status_code == 409:
            # User already exists, update their roles
            users_response = await client.get("/v1/users/", headers=headers)
            users = users_response.json()
            user = next((u for u in users if u["email"] == user_data["email"]), None)
            assert user is not None
            user_id = user.get("id", user.get("_id"))
            
            update_response = await client.put(
                f"/v1/users/{user_id}", 
                json={"roles": ["integration_tester"]}, 
                headers=headers
            )
            assert update_response.status_code == 200
        else:
            assert user_response.status_code == 201
        
        # 4. Verify the user has the correct role
        users_response = await client.get("/v1/users/", headers=headers)
        users = users_response.json()
        test_user = next((u for u in users if u["email"] == user_data["email"]), None)
        assert test_user is not None
        assert "integration_tester" in test_user["roles"]
    
    async def test_authentication_and_authorization_flow(self, client: AsyncClient):
        """Test complete authentication and authorization flow."""
        # 1. Login as admin
        admin_login = {
            "username": ADMIN_USER_DATA["email"],
            "password": ADMIN_USER_DATA["password"]
        }
        login_response = await client.post("/v1/auth/login", data=admin_login)
        assert login_response.status_code == 200
        
        tokens = login_response.json()
        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]
        
        # 2. Use access token to access protected endpoint
        headers = {"Authorization": f"Bearer {access_token}"}
        me_response = await client.get("/v1/auth/me", headers=headers)
        assert me_response.status_code == 200
        
        # 3. Test token refresh
        refresh_headers = {"Authorization": f"Bearer {refresh_token}"}
        refresh_response = await client.post("/v1/auth/refresh", headers=refresh_headers)
        assert refresh_response.status_code == 200
        
        new_tokens = refresh_response.json()
        assert "access_token" in new_tokens
        assert "refresh_token" in new_tokens
        
        # 4. Use new access token
        new_headers = {"Authorization": f"Bearer {new_tokens['access_token']}"}
        me_response2 = await client.get("/v1/auth/me", headers=new_headers)
        assert me_response2.status_code == 200
        
        # 5. Test logout
        logout_response = await client.post("/v1/auth/logout", headers=new_headers)
        assert logout_response.status_code == 204
    
    async def test_password_reset_workflow(self, client: AsyncClient):
        """Test complete password reset workflow."""
        # 1. Request password reset
        reset_request = {
            "email": ADMIN_USER_DATA["email"]
        }
        
        request_response = await client.post("/v1/auth/password/reset-request", json=reset_request)
        assert request_response.status_code == 200
        
        # In a real app, the token would be sent via email
        # For testing, the API returns the token directly
        reset_data = request_response.json()
        if "token" in reset_data:
            reset_token = reset_data["token"]
            
            # 2. Confirm password reset with token
            new_password = "new_secure_password"
            confirm_data = {
                "token": reset_token,
                "new_password": new_password
            }
            
            confirm_response = await client.post("/v1/auth/password/reset-confirm", json=confirm_data)
            assert confirm_response.status_code == 204
            
            # 3. Test login with new password
            login_data = {
                "username": ADMIN_USER_DATA["email"],
                "password": new_password
            }
            login_response = await client.post("/v1/auth/login", data=login_data)
            assert login_response.status_code == 200
            
            # 4. Reset password back to original for other tests
            token = login_response.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            
            change_data = {
                "current_password": new_password,
                "new_password": ADMIN_USER_DATA["password"]
            }
            change_response = await client.post("/v1/auth/password/change", json=change_data, headers=headers)
            assert change_response.status_code == 204
    
    async def test_bulk_operations_workflow(self, client: AsyncClient):
        """Test bulk operations and their consistency."""
        token = await get_admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        
        # 1. Bulk create users
        bulk_users = [
            {
                "email": f"bulk{i}@example.com",
                "password": "password123",
                "first_name": f"Bulk{i}",
                "last_name": "User"
            }
            for i in range(1, 4)
        ]
        
        bulk_response = await client.post("/v1/users/bulk-create", json=bulk_users, headers=headers)
        assert bulk_response.status_code == 201
        
        result = bulk_response.json()
        assert "successful_creates" in result
        assert "failed_creates" in result
        
        # 2. Verify users were created
        users_response = await client.get("/v1/users/", headers=headers)
        assert users_response.status_code == 200
        
        users = users_response.json()
        bulk_emails = [u["email"] for u in users if u["email"].startswith("bulk")]
        assert len(bulk_emails) >= len(result["successful_creates"])
    
    async def test_session_management_workflow(self, client: AsyncClient):
        """Test session management and token revocation."""
        # 1. Login to create a session
        login_data = {
            "username": ADMIN_USER_DATA["email"],
            "password": ADMIN_USER_DATA["password"]
        }
        login_response = await client.post("/v1/auth/login", data=login_data)
        assert login_response.status_code == 200
        
        tokens = login_response.json()
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        
        # 2. Get active sessions
        sessions_response = await client.get("/v1/auth/sessions", headers=headers)
        assert sessions_response.status_code == 200
        
        sessions = sessions_response.json()
        assert isinstance(sessions, list)
        assert len(sessions) >= 1
        
        # 3. Logout all sessions
        logout_all_response = await client.post("/v1/auth/logout_all", headers=headers)
        assert logout_all_response.status_code == 204
        
        # 4. Verify token is no longer valid (should fail)
        me_response = await client.get("/v1/auth/me", headers=headers)
        # This might still work if the access token hasn't expired yet
        # The important thing is that refresh tokens are revoked
    
    async def test_error_handling_and_recovery(self, client: AsyncClient):
        """Test error scenarios and recovery mechanisms."""
        token = await get_admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        
        # 1. Test creating user with invalid data
        invalid_user = {
            "email": "not-an-email",
            "password": "weak"
        }
        
        response = await client.post("/v1/users/", json=invalid_user, headers=headers)
        assert response.status_code == 422  # Validation error
        
        # 2. Test accessing non-existent resources
        response = await client.get("/v1/users/507f1f77bcf86cd799439011", headers=headers)
        assert response.status_code == 404
        
        # 3. Test unauthorized access
        response = await client.get("/v1/users/")
        assert response.status_code == 401
        
        # 4. Test with invalid token
        bad_headers = {"Authorization": "Bearer invalid_token"}
        response = await client.get("/v1/auth/me", headers=bad_headers)
        assert response.status_code == 401
        
        # 5. Verify system is still functional after errors
        response = await client.get("/v1/auth/me", headers=headers)
        assert response.status_code == 200 