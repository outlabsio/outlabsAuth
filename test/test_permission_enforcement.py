#!/usr/bin/env python3
"""
Test permission enforcement on endpoints
"""
from base_test import APITest
from auth_utils import get_system_admin_headers, AuthManager
from test_data_factory import TestDataFactory
import json


class PermissionEnforcementTest(APITest):
    """Test that endpoints properly enforce permission requirements"""
    
    def __init__(self, auth_manager):
        super().__init__("Permission Enforcement Test", auth_manager)
        self.factory = TestDataFactory(auth_manager)
        
    def run(self):
        """Run permission enforcement tests"""
        try:
            # Test 1: User endpoints permission requirements
            self.test_user_endpoint_permissions()
            
            # Test 2: Entity endpoints permission requirements
            self.test_entity_endpoint_permissions()
            
            # Test 3: Role endpoints permission requirements
            self.test_role_endpoint_permissions()
            
            # Test 4: Permission endpoints requirements
            self.test_permission_endpoint_permissions()
            
            # Test 5: Entity-scoped permission checks
            self.test_entity_scoped_permissions()
            
            # Test 6: Cross-entity access denial
            self.test_cross_entity_access_denial()
            
            # Test 7: Hierarchical permission inheritance
            self.test_hierarchical_permissions()
            
            # Test 8: Self-access permissions
            self.test_self_access_permissions()
            
            # Test 9: System user permissions
            self.test_system_user_permissions()
            
        finally:
            # Cleanup
            self.cleanup()
    
    def test_user_endpoint_permissions(self):
        """Test user endpoint permission requirements"""
        # Create test structure
        platform = self.factory.create_test_platform("user_perms")
        org = self.factory.create_entity(parent_id=platform['id'])
        
        # Create users with different permission levels
        reader_data = self.factory.create_user_with_role(
            org['id'],
            "reader",
            permissions=["user:read"]
        )
        
        manager_data = self.factory.create_user_with_role(
            org['id'],
            "manager",
            permissions=["user:manage"]
        )
        
        no_perm_data = self.factory.create_user_with_role(
            org['id'],
            "no_perm",
            permissions=["entity:read"]  # No user permissions
        )
        
        # Test GET /users (requires user:read)
        reader_headers = self.auth.get_headers(
            reader_data['user']['email'],
            reader_data['user']['test_password']
        )
        
        response = self.make_request(
            'GET',
            '/v1/users',
            headers=reader_headers
        )
        
        self.assert_status(
            response,
            200,
            "Reader can list users"
        )
        
        # Test with no permissions
        no_perm_headers = self.auth.get_headers(
            no_perm_data['user']['email'],
            no_perm_data['user']['test_password']
        )
        
        response = self.make_request(
            'GET',
            '/v1/users',
            headers=no_perm_headers
        )
        
        self.assert_status(
            response,
            403,
            "No permission user denied"
        )
        
        # Test POST /users (requires user:manage)
        response = self.make_request(
            'POST',
            '/v1/users',
            headers=reader_headers,
            json_data={
                "email": "newuser@test.com",
                "password": "TestPass123!",
                "entity_assignments": []
            }
        )
        
        self.assert_status(
            response,
            403,
            "Reader cannot create users"
        )
        
        # Manager can create users
        manager_headers = self.auth.get_headers(
            manager_data['user']['email'],
            manager_data['user']['test_password']
        )
        
        response = self.make_request(
            'POST',
            '/v1/users',
            headers=manager_headers,
            json_data={
                "email": self.factory.generate_unique_name("new") + "@test.com",
                "password": "TestPass123!",
                "entity_assignments": []
            }
        )
        
        self.assert_status(
            response,
            200,
            "Manager can create users"
        )
    
    def test_entity_endpoint_permissions(self):
        """Test entity endpoint permission requirements"""
        platform = self.factory.create_test_platform("entity_perms")
        org = self.factory.create_entity(parent_id=platform['id'])
        
        # Create users with different permissions
        reader_data = self.factory.create_user_with_role(
            org['id'],
            "entity_reader",
            permissions=["entity:read"]
        )
        
        updater_data = self.factory.create_user_with_role(
            org['id'],
            "entity_updater",
            permissions=["entity:update"]
        )
        
        # Manager with hierarchical permissions
        manager_data = self.factory.create_user_with_role(
            org['id'],
            "entity_manager",
            permissions=["entity:create", "entity:read_tree", "entity:update_tree", "entity:delete_tree"]
        )
        
        # Test GET /entities/{id} (requires entity:read)
        reader_headers = self.auth.get_headers(
            reader_data['user']['email'],
            reader_data['user']['test_password']
        )
        
        response = self.make_request(
            'GET',
            f'/v1/entities/{org["id"]}',
            headers=reader_headers
        )
        
        self.assert_status(
            response,
            200,
            "Reader can view entity"
        )
        
        # Test PUT /entities/{id} (requires entity:update)
        response = self.make_request(
            'PUT',
            f'/v1/entities/{org["id"]}',
            headers=reader_headers,
            json_data={
                "description": "Updated description"
            }
        )
        
        self.assert_status(
            response,
            403,
            "Reader cannot update entity"
        )
        
        # Updater can update
        updater_headers = self.auth.get_headers(
            updater_data['user']['email'],
            updater_data['user']['test_password']
        )
        
        response = self.make_request(
            'PUT',
            f'/v1/entities/{org["id"]}',
            headers=updater_headers,
            json_data={
                "description": "Updated by updater"
            }
        )
        
        self.assert_status(
            response,
            200,
            "Updater can update entity"
        )
        
        # Test DELETE /entities/{id} (requires entity:manage)
        response = self.make_request(
            'DELETE',
            f'/v1/entities/{org["id"]}',
            headers=updater_headers
        )
        
        self.assert_status(
            response,
            403,
            "Updater cannot delete entity"
        )
        
        # Manager can delete (create a test entity first)
        test_entity = self.factory.create_entity(
            parent_id=org['id'],
            entity_type="team",
            name_prefix="deletable"
        )
        
        manager_headers = self.auth.get_headers(
            manager_data['user']['email'],
            manager_data['user']['test_password']
        )
        # Add entity context header
        manager_headers['X-Entity-Context-Id'] = org['id']
        
        response = self.make_request(
            'DELETE',
            f'/v1/entities/{test_entity["id"]}',
            headers=manager_headers
        )
        
        # With hierarchical permissions, manager can delete child entities
        self.assert_status(
            response,
            200,
            "Manager can delete child entity with entity:delete_tree"
        )
    
    def test_role_endpoint_permissions(self):
        """Test role endpoint permission requirements"""
        platform = self.factory.create_test_platform("role_perms")
        org = self.factory.create_entity(parent_id=platform['id'])
        
        # Create users with different permissions
        reader_data = self.factory.create_user_with_role(
            org['id'],
            "role_reader",
            permissions=["role:read"]
        )
        
        manager_data = self.factory.create_user_with_role(
            org['id'],
            "role_manager",
            permissions=["role:manage"]
        )
        
        # Test GET /roles (authenticated users can list)
        reader_headers = self.auth.get_headers(
            reader_data['user']['email'],
            reader_data['user']['test_password']
        )
        
        response = self.make_request(
            'GET',
            '/v1/roles',
            headers=reader_headers
        )
        
        self.assert_status(
            response,
            200,
            "Authenticated user can list roles"
        )
        
        # Test POST /roles (requires role:manage)
        response = self.make_request(
            'POST',
            '/v1/roles',
            headers=reader_headers,
            json_data={
                "name": "test_role",
                "display_name": "Test Role",
                "permissions": ["entity:read"],
                "entity_id": org['id']
            }
        )
        
        self.assert_status(
            response,
            403,
            "Reader cannot create roles"
        )
        
        # Manager can create roles
        manager_headers = self.auth.get_headers(
            manager_data['user']['email'],
            manager_data['user']['test_password']
        )
        
        manager_headers['X-Entity-Context-Id'] = org['id']
        
        response = self.make_request(
            'POST',
            '/v1/roles',
            headers=manager_headers,
            json_data={
                "name": self.factory.generate_unique_name("test_role"),
                "display_name": "Test Role",
                "permissions": ["entity:read"],
                "entity_id": org['id'],
                "is_custom": True
            }
        )
        
        self.assert_status(
            response,
            200,
            "Manager can create roles"
        )
    
    def test_permission_endpoint_permissions(self):
        """Test permission endpoint permission requirements"""
        platform = self.factory.create_test_platform("perm_perms")
        org = self.factory.create_entity(parent_id=platform['id'])
        
        # Create user with no special permissions
        user_data = self.factory.create_user_with_role(
            org['id'],
            "basic_user",
            permissions=["entity:read"]
        )
        
        user_headers = self.auth.get_headers(
            user_data['user']['email'],
            user_data['user']['test_password']
        )
        
        # Test GET /permissions/available (should be accessible to authenticated users)
        response = self.make_request(
            'GET',
            '/v1/permissions/available',
            headers=user_headers
        )
        
        self.assert_status(
            response,
            200,
            "Authenticated user can list available permissions"
        )
        
        # Test POST /permissions/check (should be accessible to authenticated users)
        # Add entity context header for permission check
        user_headers['X-Entity-Context-Id'] = org['id']
        
        response = self.make_request(
            'POST',
            '/v1/permissions/check',
            headers=user_headers,
            json_data={
                "permission": "entity:read",
                "entity_id": org['id']
            }
        )
        
        self.assert_status(
            response,
            200,
            "Authenticated user can check permissions"
        )
        
        # Verify the check result if successful
        if response.status_code == 200:
            result = response.json()
            # Debug output
            self.log(f"Permission check result: {result}")
            self.assert_true(
                result.get('allowed', False),
                "Permission check returns correct result",
                "User correctly has entity:read permission"
            )
    
    def test_entity_scoped_permissions(self):
        """Test that permissions are properly scoped to entities"""
        platform = self.factory.create_test_platform("scoped_perms")
        
        # Create two separate organizations
        org1 = self.factory.create_entity(
            parent_id=platform['id'],
            name_prefix="org1"
        )
        org2 = self.factory.create_entity(
            parent_id=platform['id'],
            name_prefix="org2"
        )
        
        # Create manager in org1 with hierarchical permissions
        org1_manager = self.factory.create_user_with_role(
            org1['id'],
            "org1_manager",
            permissions=["entity:create", "entity:read_tree", "entity:update_tree", "entity:delete_tree", "user:manage_tree"]
        )
        
        # Create entity in org2
        org2_team = self.factory.create_entity(
            parent_id=org2['id'],
            entity_type="team",
            name_prefix="org2_team"
        )
        
        # Try to update org2's entity with org1 manager
        org1_headers = self.auth.get_headers(
            org1_manager['user']['email'],
            org1_manager['user']['test_password']
        )
        # Add entity context for org1
        org1_headers['X-Entity-Context-Id'] = org1['id']
        
        response = self.make_request(
            'PUT',
            f'/v1/entities/{org2_team["id"]}',
            headers=org1_headers,
            json_data={
                "description": "Unauthorized update attempt"
            }
        )
        
        self.assert_status(
            response,
            403,
            "Org1 manager cannot update org2 entity"
        )
        
        # But can update own org's entities
        org1_team = self.factory.create_entity(
            parent_id=org1['id'],
            entity_type="team",
            name_prefix="org1_team"
        )
        
        response = self.make_request(
            'PUT',
            f'/v1/entities/{org1_team["id"]}',
            headers=org1_headers,
            json_data={
                "description": "Authorized update"
            }
        )
        
        # With hierarchical permissions, manager can update child entities
        self.assert_status(
            response,
            200,
            "Org1 manager can update child entity with entity:update_tree"
        )
    
    def test_cross_entity_access_denial(self):
        """Test that users cannot access entities they're not members of"""
        platform = self.factory.create_test_platform("cross_entity")
        
        # Create two organizations
        org1 = self.factory.create_entity(parent_id=platform['id'], name_prefix="org1")
        org2 = self.factory.create_entity(parent_id=platform['id'], name_prefix="org2")
        
        # Create user in org1 only
        org1_user = self.factory.create_user_with_role(
            org1['id'],
            "org1_only",
            permissions=["entity:read", "user:read"]
        )
        
        org1_headers = self.auth.get_headers(
            org1_user['user']['email'],
            org1_user['user']['test_password']
        )
        
        # Should not be able to read org2 details
        response = self.make_request(
            'GET',
            f'/v1/entities/{org2["id"]}',
            headers=org1_headers
        )
        
        self.assert_status(
            response,
            403,
            "Cannot read entity not member of"
        )
        
        # Should not see org2 in entity list
        response = self.make_request(
            'GET',
            '/v1/entities',
            headers=org1_headers
        )
        
        if response.status_code == 200:
            entities = response.json().get('items', [])
            entity_ids = [e['id'] for e in entities]
            
            self.assert_not_contains(
                entity_ids,
                org2['id'],
                "Entity list filtering",
                "Org2 not visible to org1 user"
            )
    
    def test_hierarchical_permissions(self):
        """Test permission inheritance through entity hierarchy"""
        platform = self.factory.create_test_platform("hierarchy")
        org = self.factory.create_entity(parent_id=platform['id'])
        division = self.factory.create_entity(parent_id=org['id'], entity_type="division")
        team = self.factory.create_entity(parent_id=division['id'], entity_type="team")
        
        # Create user with hierarchical read permission at organization level
        org_user = self.factory.create_user_with_role(
            org['id'],
            "org_user",
            permissions=["entity:read_tree"]
        )
        
        org_headers = self.auth.get_headers(
            org_user['user']['email'],
            org_user['user']['test_password']
        )
        # Add entity context header for the organization  
        org_headers['X-Entity-Context-Id'] = org['id']
        
        # Should be able to read child entities
        response = self.make_request(
            'GET',
            f'/v1/entities/{team["id"]}',
            headers=org_headers
        )
        
        # With entity:read_tree, user can read child entities
        self.assert_status(
            response,
            200,
            "Can read child entity with entity:read_tree"
        )
        
        # Should see all entities in hierarchy
        response = self.make_request(
            'GET',
            '/v1/entities',
            headers=org_headers
        )
        
        if response.status_code == 200:
            entities = response.json().get('items', [])
            entity_ids = [e['id'] for e in entities]
            
            # With the updated implementation, user should see entities they have
            # membership in, plus descendants due to entity:read_tree permission
            self.assert_greater_than_or_equal(
                len(entities),
                3,  # Should see org, division, and team
                "Entity list with _tree permissions",
                f"User can see {len(entities)} entities (org + descendants)"
            )
            
            # Verify we can see all entities in the hierarchy
            self.assert_contains(
                entity_ids,
                org['id'],
                "Entity visibility",
                "Organization visible"
            )
            self.assert_contains(
                entity_ids,
                division['id'],
                "Entity visibility",
                "Division visible due to _tree permission"
            )
            self.assert_contains(
                entity_ids,
                team['id'],
                "Entity visibility",
                "Team visible due to _tree permission"
            )
    
    def test_self_access_permissions(self):
        """Test users can access their own data regardless of permissions"""
        platform = self.factory.create_test_platform("self_access")
        org = self.factory.create_entity(parent_id=platform['id'])
        
        # Create user with minimal permissions
        user_data = self.factory.create_user_with_role(
            org['id'],
            "minimal_user",
            permissions=["entity:read"]  # Minimal permission
        )
        
        user_headers = self.auth.get_headers(
            user_data['user']['email'],
            user_data['user']['test_password']
        )
        
        # Should be able to read own profile
        response = self.make_request(
            'GET',
            f'/v1/users/{user_data["user"]["id"]}',
            headers=user_headers
        )
        
        self.assert_status(
            response,
            200,
            "Can read own profile"
        )
        
        # Should be able to update own profile
        response = self.make_request(
            'PUT',
            f'/v1/users/{user_data["user"]["id"]}',
            headers=user_headers,
            json_data={
                "profile": {
                    "first_name": "Self",
                    "last_name": "Updated"
                }
            }
        )
        
        self.assert_status(
            response,
            200,
            "Can update own profile"
        )
        
        # Should NOT be able to read other users
        other_user = self.factory.create_test_user("other_user")
        
        response = self.make_request(
            'GET',
            f'/v1/users/{other_user["id"]}',
            headers=user_headers
        )
        
        self.assert_status(
            response,
            403,
            "Cannot read other users"
        )
    
    def test_system_user_permissions(self):
        """Test system user has elevated permissions"""
        # System admin should bypass permission checks
        headers = get_system_admin_headers(self.auth)
        
        # Create isolated platform
        platform = self.factory.create_test_platform("system_test")
        org = self.factory.create_entity(parent_id=platform['id'])
        
        # System user can do everything
        response = self.make_request(
            'GET',
            f'/v1/entities/{org["id"]}',
            headers=headers
        )
        
        self.assert_status(
            response,
            200,
            "System user can read any entity"
        )
        
        response = self.make_request(
            'PUT',
            f'/v1/entities/{org["id"]}',
            headers=headers,
            json_data={
                "description": "Updated by system"
            }
        )
        
        self.assert_status(
            response,
            200,
            "System user can update any entity"
        )
        
        # Create another platform's entity
        other_platform = self.factory.create_test_platform("other_platform")
        
        # System user can access cross-platform
        response = self.make_request(
            'GET',
            f'/v1/entities/{other_platform["id"]}',
            headers=headers
        )
        
        self.assert_status(
            response,
            200,
            "System user can access any platform"
        )
    
    def cleanup(self):
        """Cleanup test data"""
        self.log("Cleaning up test data...")
        self.factory.cleanup_test_data()


if __name__ == "__main__":
    # Run just this test
    from auth_utils import AuthManager
    
    auth = AuthManager()
    test = PermissionEnforcementTest(auth)
    test.run()
    test.print_summary()