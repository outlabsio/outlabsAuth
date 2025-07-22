"""
Test entity tree permissions functionality
"""
import pytest
from httpx import AsyncClient
from beanie import PydanticObjectId

from api.models import UserModel, EntityModel, RoleModel, EntityMembershipModel, PermissionModel


@pytest.mark.asyncio
class TestEntityTreePermissions:
    """Test entity operations with tree permissions"""
    
    async def setup_tree_hierarchy(self, db_session):
        """Create a test hierarchy with users and permissions"""
        from api.services.auth_service import AuthService
        auth_service = AuthService()
        
        # Create platform
        platform = EntityModel(
            name="test_platform",
            display_name="Test Platform",
            entity_type="platform",
            entity_class="structural",
            slug="test-platform",
            platform_id="temp_id"
        )
        await platform.save()
        platform.platform_id = str(platform.id)
        await platform.save()
        
        # Create organization under platform
        org = EntityModel(
            name="test_org",
            display_name="Test Organization",
            entity_type="organization",
            entity_class="structural",
            slug="test-org",
            parent_entity=platform,
            platform_id=str(platform.id)
        )
        await org.save()
        
        # Create division under organization
        division = EntityModel(
            name="test_division",
            display_name="Test Division",
            entity_type="division",
            entity_class="structural",
            slug="test-division",
            parent_entity=org,
            platform_id=str(platform.id)
        )
        await division.save()
        
        # Create users
        org_admin = UserModel(
            email="org_admin@test.com",
            is_active=True,
            is_verified=True,
            hashed_password="temp_hash"  # Will be updated before login
        )
        await org_admin.save()
        
        division_admin = UserModel(
            email="division_admin@test.com",
            is_active=True,
            is_verified=True,
            hashed_password="temp_hash"  # Will be updated before login
        )
        await division_admin.save()
        
        regular_user = UserModel(
            email="regular@test.com",
            is_active=True,
            is_verified=True,
            hashed_password="temp_hash"  # Will be updated before login
        )
        await regular_user.save()
        
        # Create roles with tree permissions
        org_admin_role = RoleModel(
            name="org_admin",
            display_name="Organization Admin",
            entity=org,
            permissions=[
                "entity:read",
                "entity:update",
                "entity:create_tree",  # Can create child entities
                "entity:update_tree",  # Can update child entities
                "entity:delete_tree"   # Can delete child entities
            ]
        )
        await org_admin_role.save()
        
        division_admin_role = RoleModel(
            name="division_admin",
            display_name="Division Admin",
            entity=division,
            permissions=[
                "entity:read",
                "entity:update",
                "entity:create",  # Can only create at same level
                "entity:delete"
            ]
        )
        await division_admin_role.save()
        
        # Create memberships
        await EntityMembershipModel(
            user=org_admin,
            entity=org,
            roles=[org_admin_role],
            status="active"
        ).save()
        
        await EntityMembershipModel(
            user=division_admin,
            entity=division,
            roles=[division_admin_role],
            status="active"
        ).save()
        
        await EntityMembershipModel(
            user=regular_user,
            entity=division,
            roles=[],  # No roles, just membership
            status="active"
        ).save()
        
        return {
            "platform": platform,
            "org": org,
            "division": division,
            "org_admin": org_admin,
            "division_admin": division_admin,
            "regular_user": regular_user
        }
    
    async def test_create_entity_with_tree_permission(
        self,
        client: AsyncClient,
        db_session
    ):
        """Test that user with entity:create_tree in parent can create child entities"""
        # Setup hierarchy
        data = await self.setup_tree_hierarchy(db_session)
        
        # Login as org admin
        
        # Update password hash for org admin
        org_admin = data["org_admin"]
        org_admin.hashed_password = auth_service.hash_password("password")
        await org_admin.save()
        
        login_response = await client.post(
            "/v1/auth/login/json",
            json={"email": "org_admin@test.com", "password": "password"}
        )
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Create a department under division (org admin has create_tree in org)
        create_data = {
            "name": "test_department",
            "display_name": "Test Department",
            "entity_type": "department",
            "entity_class": "STRUCTURAL",
            "parent_entity_id": str(data["division"].id)
        }
        
        response = await client.post(
            "/v1/entities",
            json=create_data,
            headers=headers
        )
        
        assert response.status_code == 200
        created_entity = response.json()
        assert created_entity["name"] == "test_department"
        assert created_entity["parent_entity_id"] == str(data["division"].id)
    
    async def test_create_entity_without_tree_permission_fails(
        self,
        client: AsyncClient,
        db_session
    ):
        """Test that user without entity:create_tree cannot create child entities"""
        # Setup hierarchy
        data = await self.setup_tree_hierarchy(db_session)
        
        # Login as division admin (no tree permissions)
        division_admin = data["division_admin"]
        division_admin.hashed_password = auth_service.hash_password("password")
        await division_admin.save()
        
        login_response = await client.post(
            "/v1/auth/login/json",
            json={"email": "division_admin@test.com", "password": "password"}
        )
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Try to create a department under division
        create_data = {
            "name": "test_department",
            "display_name": "Test Department",
            "entity_type": "department",
            "entity_class": "STRUCTURAL",
            "parent_entity_id": str(data["division"].id)
        }
        
        response = await client.post(
            "/v1/entities",
            json=create_data,
            headers=headers
        )
        
        # Should fail because division admin doesn't have entity:create_tree
        assert response.status_code == 403
        assert "entity:create or entity:create_tree" in response.json()["detail"]
    
    async def test_update_entity_with_tree_permission(
        self,
        client: AsyncClient,
        db_session
    ):
        """Test that user with entity:update_tree in parent can update child entities"""
        # Setup hierarchy
        data = await self.setup_tree_hierarchy(db_session)
        
        # Login as org admin
        org_admin = data["org_admin"]
        org_admin.hashed_password = auth_service.hash_password("password")
        await org_admin.save()
        
        login_response = await client.post(
            "/v1/auth/login/json",
            json={"email": "org_admin@test.com", "password": "password"}
        )
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Update the division (org admin has update_tree in org)
        update_data = {
            "display_name": "Updated Division Name"
        }
        
        response = await client.put(
            f"/v1/entities/{data['division'].id}",
            json=update_data,
            headers=headers
        )
        
        assert response.status_code == 200
        updated_entity = response.json()
        assert updated_entity["display_name"] == "Updated Division Name"
    
    async def test_update_entity_without_tree_permission_fails(
        self,
        client: AsyncClient,
        db_session
    ):
        """Test that user without entity:update_tree cannot update entities outside their scope"""
        # Setup hierarchy
        data = await self.setup_tree_hierarchy(db_session)
        
        # Create a department under division
        department = EntityModel(
            name="test_department",
            display_name="Test Department",
            entity_type="department",
            entity_class="structural",
            slug="test-department",
            parent_entity=data["division"],
            platform_id=str(data["platform"].id)
        )
        await department.save()
        
        # Login as division admin (has update in division but not update_tree)
        division_admin = data["division_admin"]
        division_admin.hashed_password = auth_service.hash_password("password")
        await division_admin.save()
        
        login_response = await client.post(
            "/v1/auth/login/json",
            json={"email": "division_admin@test.com", "password": "password"}
        )
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Try to update the department
        update_data = {
            "display_name": "Should Not Work"
        }
        
        response = await client.put(
            f"/v1/entities/{department.id}",
            json=update_data,
            headers=headers
        )
        
        # Should fail because division admin doesn't have update_tree
        assert response.status_code == 403
        assert "entity:update or entity:update_tree" in response.json()["detail"]
    
    async def test_tree_permission_inheritance_depth(
        self,
        client: AsyncClient,
        db_session
    ):
        """Test that tree permissions work at any depth in the hierarchy"""
        # Setup hierarchy
        data = await self.setup_tree_hierarchy(db_session)
        
        # Create a deeper hierarchy
        department = EntityModel(
            name="test_department",
            display_name="Test Department",
            entity_type="department",
            entity_class="structural",
            slug="test-department",
            parent_entity=data["division"],
            platform_id=str(data["platform"].id)
        )
        await department.save()
        
        team = EntityModel(
            name="test_team",
            display_name="Test Team",
            entity_type="team",
            entity_class="structural",
            slug="test-team",
            parent_entity=department,
            platform_id=str(data["platform"].id)
        )
        await team.save()
        
        # Login as org admin
        org_admin = data["org_admin"]
        org_admin.hashed_password = auth_service.hash_password("password")
        await org_admin.save()
        
        login_response = await client.post(
            "/v1/auth/login/json",
            json={"email": "org_admin@test.com", "password": "password"}
        )
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Org admin should be able to update team (3 levels down)
        update_data = {
            "display_name": "Updated Team Name"
        }
        
        response = await client.put(
            f"/v1/entities/{team.id}",
            json=update_data,
            headers=headers
        )
        
        assert response.status_code == 200
        updated_entity = response.json()
        assert updated_entity["display_name"] == "Updated Team Name"
    
    async def test_regular_user_cannot_create_or_update(
        self,
        client: AsyncClient,
        db_session
    ):
        """Test that regular user without permissions cannot create or update entities"""
        # Setup hierarchy
        data = await self.setup_tree_hierarchy(db_session)
        
        # Login as regular user
        regular_user = data["regular_user"]
        regular_user.hashed_password = auth_service.hash_password("password")
        await regular_user.save()
        
        login_response = await client.post(
            "/v1/auth/login/json",
            json={"email": "regular@test.com", "password": "password"}
        )
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Try to create entity
        create_data = {
            "name": "should_fail",
            "display_name": "Should Fail",
            "entity_type": "team",
            "entity_class": "STRUCTURAL",
            "parent_entity_id": str(data["division"].id)
        }
        
        response = await client.post(
            "/v1/entities",
            json=create_data,
            headers=headers
        )
        assert response.status_code == 403
        
        # Try to update entity
        update_data = {
            "display_name": "Should Also Fail"
        }
        
        response = await client.put(
            f"/v1/entities/{data['division'].id}",
            json=update_data,
            headers=headers
        )
        assert response.status_code == 403