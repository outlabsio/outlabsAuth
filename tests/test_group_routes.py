import pytest
import uuid
from httpx import AsyncClient
from bson import ObjectId


class TestGroupRoutes:
    """Test suite for group management routes."""

    @pytest.fixture
    async def admin_token(self, admin_user_with_auth_header):
        """Fixture to get admin token from header."""
        return admin_user_with_auth_header["Authorization"].replace("Bearer ", "")

    @pytest.fixture
    def sample_group_data(self):
        """Sample group data for testing."""
        unique_suffix = str(uuid.uuid4())[:8]
        return {
            "name": f"Test Group {unique_suffix}",
            "description": "A test group for unit testing",
            "client_account_id": str(ObjectId()),
            "roles": ["platform_admin"]
        }

    @pytest.mark.asyncio
    async def test_create_group_success(self, client: AsyncClient, admin_user_with_auth_header, sample_group_data):
        """Test successful group creation."""
        response = await client.post(
            "/v1/groups/",
            json=sample_group_data,
            headers=admin_user_with_auth_header
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == sample_group_data["name"]
        assert data["description"] == sample_group_data["description"]
        assert data["roles"] == sample_group_data["roles"]
        assert "id" in data
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_create_group_duplicate_name(self, client: AsyncClient, admin_user_with_auth_header, sample_group_data):
        """Test group creation with duplicate name within same client account."""
        # Create the first group
        await client.post(
            "/v1/groups/",
            json=sample_group_data,
            headers=admin_user_with_auth_header
        )
        
        # Try to create a duplicate
        response = await client.post(
            "/v1/groups/",
            json=sample_group_data,
            headers=admin_user_with_auth_header
        )
        
        assert response.status_code in [400, 409]  # Should fail with conflict or validation error

    @pytest.mark.asyncio
    async def test_create_group_invalid_client_account(self, client: AsyncClient, admin_user_with_auth_header):
        """Test group creation with invalid client account ID."""
        invalid_group_data = {
            "name": "Invalid Group",
            "description": "A group with invalid client account",
            "client_account_id": str(ObjectId()),  # Non-existent client account
            "roles": ["platform_admin"]
        }
        
        response = await client.post(
            "/v1/groups/",
            json=invalid_group_data,
            headers=admin_user_with_auth_header
        )
        
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_group_invalid_roles(self, client: AsyncClient, admin_user_with_auth_header, sample_group_data):
        """Test group creation with non-existent roles."""
        sample_group_data["roles"] = ["non_existent_role"]
        
        response = await client.post(
            "/v1/groups/",
            json=sample_group_data,
            headers=admin_user_with_auth_header
        )
        
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_create_group_without_permission(self, client: AsyncClient, sample_group_data):
        """Test group creation without proper permissions."""
        response = await client.post(
            "/v1/groups/",
            json=sample_group_data
        )
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_groups(self, client: AsyncClient, admin_user_with_auth_header):
        """Test listing all groups."""
        response = await client.get(
            "/v1/groups/",
            headers=admin_user_with_auth_header
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_list_groups_with_pagination(self, client: AsyncClient, admin_user_with_auth_header):
        """Test listing groups with pagination."""
        response = await client.get(
            "/v1/groups/?skip=0&limit=5",
            headers=admin_user_with_auth_header
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) <= 5

    @pytest.mark.asyncio
    async def test_get_group_by_id(self, client: AsyncClient, admin_user_with_auth_header, sample_group_data):
        """Test getting a group by ID."""
        # First create a group
        create_response = await client.post(
            "/v1/groups/",
            json=sample_group_data,
            headers=admin_user_with_auth_header
        )
        group_data = create_response.json()
        group_id = group_data["id"]
        
        # Get the group by ID
        response = await client.get(
            f"/v1/groups/{group_id}",
            headers=admin_user_with_auth_header
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == group_id
        assert data["name"] == sample_group_data["name"]

    @pytest.mark.asyncio
    async def test_get_group_not_found(self, client: AsyncClient, admin_user_with_auth_header):
        """Test getting a non-existent group."""
        non_existent_id = str(ObjectId())
        
        response = await client.get(
            f"/v1/groups/{non_existent_id}",
            headers=admin_user_with_auth_header
        )
        
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_group_invalid_id(self, client: AsyncClient, admin_user_with_auth_header):
        """Test getting a group with invalid ID format."""
        response = await client.get(
            "/v1/groups/invalid_id",
            headers=admin_user_with_auth_header
        )
        
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_update_group(self, client: AsyncClient, admin_user_with_auth_header, sample_group_data):
        """Test updating a group."""
        # First create a group
        create_response = await client.post(
            "/v1/groups/",
            json=sample_group_data,
            headers=admin_user_with_auth_header
        )
        group_data = create_response.json()
        group_id = group_data["id"]
        
        # Update the group
        update_data = {
            "name": "Updated Group Name",
            "description": "Updated description"
        }
        
        response = await client.put(
            f"/v1/groups/{group_id}",
            json=update_data,
            headers=admin_user_with_auth_header
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == update_data["name"]
        assert data["description"] == update_data["description"]

    @pytest.mark.asyncio
    async def test_update_group_not_found(self, client: AsyncClient, admin_user_with_auth_header):
        """Test updating a non-existent group."""
        non_existent_id = str(ObjectId())
        update_data = {"name": "Updated Name"}
        
        response = await client.put(
            f"/v1/groups/{non_existent_id}",
            json=update_data,
            headers=admin_user_with_auth_header
        )
        
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_group(self, client: AsyncClient, admin_user_with_auth_header, sample_group_data):
        """Test deleting a group."""
        # First create a group
        create_response = await client.post(
            "/v1/groups/",
            json=sample_group_data,
            headers=admin_user_with_auth_header
        )
        group_data = create_response.json()
        group_id = group_data["id"]
        
        # Delete the group
        response = await client.delete(
            f"/v1/groups/{group_id}",
            headers=admin_user_with_auth_header
        )
        
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_group_not_found(self, client: AsyncClient, admin_user_with_auth_header):
        """Test deleting a non-existent group."""
        non_existent_id = str(ObjectId())
        
        response = await client.delete(
            f"/v1/groups/{non_existent_id}",
            headers=admin_user_with_auth_header
        )
        
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_add_users_to_group(self, client: AsyncClient, admin_user_with_auth_header, sample_group_data):
        """Test adding users to a group."""
        # First create a group
        create_response = await client.post(
            "/v1/groups/",
            json=sample_group_data,
            headers=admin_user_with_auth_header
        )
        group_data = create_response.json()
        group_id = group_data["id"]
        
        # Create test users first
        user_data = {
            "email": f"testuser_{uuid.uuid4()}@example.com",
            "password": "testpassword123",
            "first_name": "Test",
            "last_name": "User",
            "roles": [],
            "groups": []
        }
        
        user_response = await client.post(
            "/v1/users/",
            json=user_data,
            headers=admin_user_with_auth_header
        )
        user_id = user_response.json()["id"]
        
        # Add user to group
        membership_data = {"user_ids": [user_id]}
        
        response = await client.post(
            f"/v1/groups/{group_id}/members",
            json=membership_data,
            headers=admin_user_with_auth_header
        )
        
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_remove_users_from_group(self, client: AsyncClient, admin_user_with_auth_header, sample_group_data):
        """Test removing users from a group."""
        # First create a group
        create_response = await client.post(
            "/v1/groups/",
            json=sample_group_data,
            headers=admin_user_with_auth_header
        )
        group_data = create_response.json()
        group_id = group_data["id"]
        
        # Create test user
        user_data = {
            "email": f"testuser_{uuid.uuid4()}@example.com",
            "password": "testpassword123",
            "first_name": "Test",
            "last_name": "User",
            "roles": [],
            "groups": [group_id]  # Add to group during creation
        }
        
        user_response = await client.post(
            "/v1/users/",
            json=user_data,
            headers=admin_user_with_auth_header
        )
        user_id = user_response.json()["id"]
        
        # Remove user from group
        membership_data = {"user_ids": [user_id]}
        
        response = await client.delete(
            f"/v1/groups/{group_id}/members",
            json=membership_data,
            headers=admin_user_with_auth_header
        )
        
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_group_members(self, client: AsyncClient, admin_user_with_auth_header, sample_group_data):
        """Test getting all members of a group."""
        # First create a group
        create_response = await client.post(
            "/v1/groups/",
            json=sample_group_data,
            headers=admin_user_with_auth_header
        )
        group_data = create_response.json()
        group_id = group_data["id"]
        
        response = await client.get(
            f"/v1/groups/{group_id}/members",
            headers=admin_user_with_auth_header
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "group_id" in data
        assert "group_name" in data
        assert "members" in data
        assert isinstance(data["members"], list)

    @pytest.mark.asyncio
    async def test_get_user_groups(self, client: AsyncClient, admin_user_with_auth_header):
        """Test getting all groups that a user belongs to."""
        # Create test user
        user_data = {
            "email": f"testuser_{uuid.uuid4()}@example.com",
            "password": "testpassword123",
            "first_name": "Test",
            "last_name": "User",
            "roles": ["platform_admin"],
            "groups": []
        }
        
        user_response = await client.post(
            "/v1/users/",
            json=user_data,
            headers=admin_user_with_auth_header
        )
        user_id = user_response.json()["id"]
        
        response = await client.get(
            f"/v1/groups/users/{user_id}/groups",
            headers=admin_user_with_auth_header
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "user_id" in data
        assert "groups" in data
        assert "effective_roles" in data
        assert "effective_permissions" in data
        assert isinstance(data["groups"], list)
        assert isinstance(data["effective_roles"], list)
        assert isinstance(data["effective_permissions"], list)

    @pytest.mark.asyncio
    async def test_group_routes_without_permission(self, client: AsyncClient):
        """Test all group routes without authentication."""
        group_id = str(ObjectId())
        user_id = str(ObjectId())
        
        # Test all endpoints without auth
        test_cases = [
            ("GET", "/v1/groups/"),
            ("POST", "/v1/groups/", {"name": "Test"}),
            ("GET", f"/v1/groups/{group_id}"),
            ("PUT", f"/v1/groups/{group_id}", {"name": "Updated"}),
            ("DELETE", f"/v1/groups/{group_id}"),
            ("POST", f"/v1/groups/{group_id}/members", {"user_ids": [user_id]}),
            ("DELETE", f"/v1/groups/{group_id}/members", {"user_ids": [user_id]}),
            ("GET", f"/v1/groups/{group_id}/members"),
            ("GET", f"/v1/groups/users/{user_id}/groups"),
        ]
        
        for method, url, *json_data in test_cases:
            if method == "GET":
                response = await client.get(url)
            elif method == "POST":
                response = await client.post(url, json=json_data[0] if json_data else {})
            elif method == "PUT":
                response = await client.put(url, json=json_data[0] if json_data else {})
            elif method == "DELETE":
                response = await client.delete(url, json=json_data[0] if json_data else None)
            
            assert response.status_code == 401, f"Expected 401 for {method} {url}, got {response.status_code}" 