import pytest
import pytest_asyncio
import uuid
from httpx import AsyncClient
from bson import ObjectId


class TestGroupRoutes:
    """Enterprise-level test suite for group management routes."""

    @pytest_asyncio.fixture
    async def sample_group_data(self):
        """Sample group data for testing."""
        # Get the seeded client account ID
        from api.models.client_account_model import ClientAccountModel
        client_account = await ClientAccountModel.find_one(ClientAccountModel.name == "Test Organization")
        
        unique_suffix = str(uuid.uuid4())[:8]
        return {
            "name": f"Test Group {unique_suffix}",
            "description": "A test group for unit testing",
            "client_account_id": str(client_account.id) if client_account else str(ObjectId()),
            "roles": ["platform_admin"]
        }

    # ========================================
    # GROUP CREATION TESTS
    # ========================================

    @pytest.mark.asyncio
    async def test_create_group_success(self, client: AsyncClient, admin_headers, sample_group_data):
        """Test successful group creation."""
        response = await client.post(
            "/v1/groups/",
            json=sample_group_data,
            headers=admin_headers
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == sample_group_data["name"]
        assert data["description"] == sample_group_data["description"]
        assert data["roles"] == sample_group_data["roles"]
        assert "_id" in data
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_create_group_duplicate_name(self, client: AsyncClient, admin_headers, sample_group_data):
        """Test group creation with duplicate name within same client account."""
        # Create the first group
        await client.post(
            "/v1/groups/",
            json=sample_group_data,
            headers=admin_headers
        )
        
        # Try to create a duplicate
        response = await client.post(
            "/v1/groups/",
            json=sample_group_data,
            headers=admin_headers
        )
        
        assert response.status_code in [400, 409]  # Should fail with conflict or validation error

    @pytest.mark.asyncio
    async def test_create_group_invalid_client_account(self, client: AsyncClient, admin_headers):
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
            headers=admin_headers
        )
        
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_group_invalid_roles(self, client: AsyncClient, admin_headers, sample_group_data):
        """Test group creation with non-existent roles."""
        sample_group_data["roles"] = ["non_existent_role"]
        
        response = await client.post(
            "/v1/groups/",
            json=sample_group_data,
            headers=admin_headers
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

    # ========================================
    # GROUP LISTING TESTS
    # ========================================

    @pytest.mark.asyncio
    async def test_list_groups(self, client: AsyncClient, admin_headers):
        """Test listing all groups."""
        response = await client.get(
            "/v1/groups/",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_list_groups_with_pagination(self, client: AsyncClient, admin_headers):
        """Test listing groups with pagination."""
        response = await client.get(
            "/v1/groups/?skip=0&limit=5",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) <= 5

    # ========================================
    # GET GROUP TESTS
    # ========================================

    @pytest.mark.asyncio
    async def test_get_group_by_id(self, client: AsyncClient, admin_headers, sample_group_data):
        """Test getting a group by ID."""
        # First create a group
        create_response = await client.post(
            "/v1/groups/",
            json=sample_group_data,
            headers=admin_headers
        )
        group_data = create_response.json()
        group_id = group_data["_id"]
        
        # Get the group by ID
        response = await client.get(
            f"/v1/groups/{group_id}",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["_id"] == group_id
        assert data["name"] == sample_group_data["name"]

    @pytest.mark.asyncio
    async def test_get_group_not_found(self, client: AsyncClient, admin_headers):
        """Test getting a non-existent group."""
        non_existent_id = str(ObjectId())
        
        response = await client.get(
            f"/v1/groups/{non_existent_id}",
            headers=admin_headers
        )
        
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_group_invalid_id(self, client: AsyncClient, admin_headers):
        """Test getting a group with invalid ID format."""
        response = await client.get(
            "/v1/groups/invalid_id",
            headers=admin_headers
        )
        
        assert response.status_code == 400

    # ========================================
    # UPDATE GROUP TESTS
    # ========================================

    @pytest.mark.asyncio
    async def test_update_group(self, client: AsyncClient, admin_headers, sample_group_data):
        """Test updating a group."""
        # First create a group
        create_response = await client.post(
            "/v1/groups/",
            json=sample_group_data,
            headers=admin_headers
        )
        group_data = create_response.json()
        group_id = group_data["_id"]
        
        # Update the group
        update_data = {
            "name": "Updated Group Name",
            "description": "Updated description"
        }
        
        response = await client.put(
            f"/v1/groups/{group_id}",
            json=update_data,
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == update_data["name"]
        assert data["description"] == update_data["description"]

    @pytest.mark.asyncio
    async def test_update_group_not_found(self, client: AsyncClient, admin_headers):
        """Test updating a non-existent group."""
        non_existent_id = str(ObjectId())
        update_data = {
            "name": "Updated Name"
        }
        
        response = await client.put(
            f"/v1/groups/{non_existent_id}",
            json=update_data,
            headers=admin_headers
        )
        
        assert response.status_code == 404

    # ========================================
    # DELETE GROUP TESTS
    # ========================================

    @pytest.mark.asyncio
    async def test_delete_group(self, client: AsyncClient, admin_headers, sample_group_data):
        """Test deleting a group."""
        # First create a group
        create_response = await client.post(
            "/v1/groups/",
            json=sample_group_data,
            headers=admin_headers
        )
        group_data = create_response.json()
        group_id = group_data["_id"]
        
        # Delete the group
        response = await client.delete(
            f"/v1/groups/{group_id}",
            headers=admin_headers
        )
        
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_group_not_found(self, client: AsyncClient, admin_headers):
        """Test deleting a non-existent group."""
        non_existent_id = str(ObjectId())
        
        response = await client.delete(
            f"/v1/groups/{non_existent_id}",
            headers=admin_headers
        )
        
        assert response.status_code == 404

    # ========================================
    # GROUP MEMBERSHIP TESTS
    # ========================================

    @pytest.mark.asyncio
    async def test_add_users_to_group(self, client: AsyncClient, admin_headers, sample_group_data):
        """Test adding users to a group."""
        # First create a group
        create_response = await client.post(
            "/v1/groups/",
            json=sample_group_data,
            headers=admin_headers
        )
        group_data = create_response.json()
        group_id = group_data["_id"]
        
        # Create a test user first
        user_data = {
            "email": f"testuser{uuid.uuid4().hex[:8]}@test.com",
            "password": "test_password",
            "first_name": "Test",
            "last_name": "User",
            "client_account_id": sample_group_data["client_account_id"],
            "roles": ["basic_user"]
        }
        
        user_response = await client.post(
            "/v1/users/",
            json=user_data,
            headers=admin_headers
        )
        user_info = user_response.json()
        user_id = user_info["_id"]
        
        # Add user to group
        membership_data = {
            "user_ids": [user_id]
        }
        
        response = await client.post(
            f"/v1/groups/{group_id}/members",
            json=membership_data,
            headers=admin_headers
        )
        
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_remove_users_from_group(self, client: AsyncClient, admin_headers, sample_group_data):
        """Test removing users from a group."""
        # First create a group
        create_response = await client.post(
            "/v1/groups/",
            json=sample_group_data,
            headers=admin_headers
        )
        group_data = create_response.json()
        group_id = group_data["_id"]
        
        # Create a test user first
        user_data = {
            "email": f"testuser{uuid.uuid4().hex[:8]}@test.com",
            "password": "test_password",
            "first_name": "Test",
            "last_name": "User",
            "client_account_id": sample_group_data["client_account_id"],
            "roles": ["basic_user"]
        }
        
        user_response = await client.post(
            "/v1/users/",
            json=user_data,
            headers=admin_headers
        )
        user_info = user_response.json()
        user_id = user_info["_id"]
        
        # Add user to group first
        membership_data = {
            "user_ids": [user_id]
        }
        
        await client.post(
            f"/v1/groups/{group_id}/members",
            json=membership_data,
            headers=admin_headers
        )
        
        # Remove user from group
        response = await client.delete(
            f"/v1/groups/{group_id}/members",
            json=membership_data,
            headers=admin_headers
        )
        
        assert response.status_code == 200

    # ========================================
    # GROUP INFORMATION TESTS
    # ========================================

    @pytest.mark.asyncio
    async def test_get_group_members(self, client: AsyncClient, admin_headers, sample_group_data):
        """Test getting all members of a group."""
        # First create a group
        create_response = await client.post(
            "/v1/groups/",
            json=sample_group_data,
            headers=admin_headers
        )
        group_data = create_response.json()
        group_id = group_data["_id"]
        
        # Get group members
        response = await client.get(
            f"/v1/groups/{group_id}/members",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_user_groups(self, client: AsyncClient, admin_headers):
        """Test getting all groups that a user belongs to."""
        # Get admin user ID from token or create test user
        # For now, use a test ObjectId
        user_id = str(ObjectId())
        
        response = await client.get(
            f"/v1/users/{user_id}/groups",
            headers=admin_headers
        )
        
        # Should return 200 with empty list for non-existent user
        # or user with no groups, or 404 if user doesn't exist
        assert response.status_code in [200, 404]

    # ========================================
    # SECURITY AND PERMISSION TESTS
    # ========================================

    @pytest.mark.asyncio
    async def test_group_routes_without_permission(self, client: AsyncClient):
        """Test group routes without proper authentication/authorization."""
        sample_group_data = {
            "name": "Test Group",
            "description": "Test Description",
            "client_account_id": str(ObjectId()),
            "roles": ["platform_admin"]
        }
        
        # Test create without auth
        response = await client.post("/v1/groups/", json=sample_group_data)
        assert response.status_code == 401
        
        # Test list without auth
        response = await client.get("/v1/groups/")
        assert response.status_code == 401
        
        # Test get by ID without auth
        test_id = str(ObjectId())
        response = await client.get(f"/v1/groups/{test_id}")
        assert response.status_code == 401
        
        # Test update without auth
        response = await client.put(f"/v1/groups/{test_id}", json={"name": "Updated"})
        assert response.status_code == 401
        
        # Test delete without auth
        response = await client.delete(f"/v1/groups/{test_id}")
        assert response.status_code == 401 