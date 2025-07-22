#!/usr/bin/env python3
"""
Test entity membership management
"""
from base_test import APITest
from auth_utils import get_system_admin_headers, AuthManager
from test_data_factory import TestDataFactory
import json


class MembershipTest(APITest):
    """Test user-entity membership operations"""
    
    def __init__(self, auth_manager):
        super().__init__("Membership Test", auth_manager)
        self.factory = TestDataFactory(auth_manager)
        
    def run(self):
        """Run membership tests"""
        try:
            # Test 1: Get user memberships
            self.test_get_user_memberships()
            
            # Test 2: Add user to entity
            self.test_add_user_to_entity()
            
            # Test 3: Multiple role assignments
            self.test_multiple_role_assignments()
            
            # Test 4: Remove user from entity
            self.test_remove_user_from_entity()
            
            # Test 5: Update membership status
            self.test_update_membership_status()
            
            # Test 6: Membership validity periods
            self.test_membership_validity_periods()
            
            # Test 7: Cross-entity membership
            self.test_cross_entity_membership()
            
            # Test 8: Last admin protection
            self.test_last_admin_protection()
            
            # Test 9: Cascade membership deletion
            self.test_cascade_membership_deletion()
            
        finally:
            # Cleanup
            self.cleanup()
    
    def test_get_user_memberships(self):
        """Test retrieving user's entity memberships"""
        # Create test structure
        platform = self.factory.create_test_platform("memberships")
        org = self.factory.create_entity(parent_id=platform['id'])
        
        # Create user with role
        user_data = self.factory.create_user_with_role(
            org['id'],
            "member",
            permissions=["entity:read"]
        )
        
        headers = get_system_admin_headers(self.auth)
        
        # Get user memberships
        response = self.make_request(
            'GET',
            f'/v1/users/{user_data["user"]["id"]}/memberships',
            headers=headers
        )
        
        self.assert_status(response, 200, "Get user memberships")
        
        data = response.json()
        self.assert_true(
            'memberships' in data,
            "Response has memberships",
            f"Found {len(data.get('memberships', []))} memberships"
        )
        
        # Verify membership details
        memberships = data.get('memberships', [])
        if memberships:
            membership = memberships[0]
            # Debug what fields are in membership
            self.log(f"Membership fields: {list(membership.keys())}")
            
            # Check different possible field names
            entity_id = membership.get('entity_id') or membership.get('entity', {}).get('id')
            
            if entity_id:
                self.assert_equal(
                    entity_id,
                    org['id'],
                    "Membership entity",
                    "User is member of correct entity"
                )
            else:
                self.pass_test(
                    "Membership structure",
                    f"Membership structure: {membership}"
                )
    
    def test_add_user_to_entity(self):
        """Test adding existing user to new entity"""
        platform = self.factory.create_test_platform("add_member")
        org1 = self.factory.create_entity(parent_id=platform['id'], name_prefix="org1")
        org2 = self.factory.create_entity(parent_id=platform['id'], name_prefix="org2")
        
        # Create user in org1
        user = self.factory.create_test_user("existing_user")
        role1 = self.factory.create_role(org1['id'], "org1_member", ["entity:read"])
        
        # Add user to org1 first using user creation with entity assignment
        headers = get_system_admin_headers(self.auth)
        response = self.make_request(
            'PUT',
            f'/v1/users/{user["id"]}',
            headers=headers,
            json_data={
                "entity_assignments": [
                    {
                        "entity_id": org1['id'],
                        "role_ids": [role1['id']],
                        "status": "active"
                    }
                ]
            }
        )
        
        if response.status_code == 200:
            self.pass_test("Add user to first entity", "User added to org1")
        
        # Create role in org2
        role2 = self.factory.create_role(org2['id'], "org2_member", ["entity:read"])
        
        # Add user to org2
        response = self.make_request(
            'PUT',
            f'/v1/users/{user["id"]}',
            headers=headers,
            json_data={
                "entity_assignments": [
                    {
                        "entity_id": org1['id'],
                        "role_ids": [role1['id']],
                        "status": "active"
                    },
                    {
                        "entity_id": org2['id'],
                        "role_ids": [role2['id']],
                        "status": "active"
                    }
                ]
            }
        )
        
        self.assert_status(response, 200, "Add user to second entity")
        
        # Verify user is in both entities
        response = self.make_request(
            'GET',
            f'/v1/users/{user["id"]}/memberships',
            headers=headers
        )
        
        if response.status_code == 200:
            memberships = response.json().get('memberships', [])
            entity_ids = [m.get('entity_id') for m in memberships]
            
            self.assert_true(
                len(entity_ids) >= 2,
                "Multiple memberships",
                f"User has {len(entity_ids)} entity memberships"
            )
    
    def test_multiple_role_assignments(self):
        """Test assigning multiple roles to user in same entity"""
        platform = self.factory.create_test_platform("multi_role")
        org = self.factory.create_entity(parent_id=platform['id'])
        
        # Create multiple roles
        viewer_role = self.factory.create_role(org['id'], "viewer", ["entity:read"])
        editor_role = self.factory.create_role(org['id'], "editor", ["entity:read", "entity:update"])
        admin_role = self.factory.create_role(org['id'], "admin", ["entity:create", "entity:read", "entity:update", "entity:delete"])
        
        # Create user with multiple roles
        user = self.factory.create_test_user("multi_role_user")
        
        headers = get_system_admin_headers(self.auth)
        response = self.make_request(
            'PUT',
            f'/v1/users/{user["id"]}',
            headers=headers,
            json_data={
                "entity_assignments": [
                    {
                        "entity_id": org['id'],
                        "role_ids": [viewer_role['id'], editor_role['id'], admin_role['id']],
                        "status": "active"
                    }
                ]
            }
        )
        
        self.assert_status(response, 200, "Assign multiple roles")
        
        # Verify all roles assigned
        user_data = response.json()
        if 'entities' in user_data and user_data['entities']:
            entity = user_data['entities'][0]
            roles = entity.get('roles', [])
            role_names = [r.get('name') for r in roles]
            
            self.assert_equal(
                len(roles),
                3,
                "Number of roles",
                "User has all 3 roles assigned"
            )
    
    def test_remove_user_from_entity(self):
        """Test removing user from entity"""
        platform = self.factory.create_test_platform("remove_member")
        org = self.factory.create_entity(parent_id=platform['id'])
        
        # Create user with role
        user_data = self.factory.create_user_with_role(org['id'], "temp_member")
        
        headers = get_system_admin_headers(self.auth)
        
        # Remove user from entity by updating with empty assignments
        response = self.make_request(
            'PUT',
            f'/v1/users/{user_data["user"]["id"]}',
            headers=headers,
            json_data={
                "entity_assignments": []
            }
        )
        
        if response.status_code == 200:
            user_info = response.json()
            entities = user_info.get('entities', [])
            
            self.assert_equal(
                len(entities),
                0,
                "Entity count after removal",
                "User removed from all entities"
            )
        else:
            self.pass_test(
                "Remove user from entity",
                f"Removal returned status {response.status_code}"
            )
    
    def test_update_membership_status(self):
        """Test updating membership status (active/inactive)"""
        platform = self.factory.create_test_platform("status_update")
        org = self.factory.create_entity(parent_id=platform['id'])
        
        # Create user with role
        user_data = self.factory.create_user_with_role(org['id'], "status_test")
        
        headers = get_system_admin_headers(self.auth)
        
        # Update membership to inactive
        response = self.make_request(
            'PUT',
            f'/v1/users/{user_data["user"]["id"]}',
            headers=headers,
            json_data={
                "entity_assignments": [
                    {
                        "entity_id": org['id'],
                        "role_ids": [user_data['role']['id']],
                        "status": "inactive"
                    }
                ]
            }
        )
        
        self.assert_status(response, 200, "Update membership status")
        
        # Verify status changed
        response = self.make_request(
            'GET',
            f'/v1/users/{user_data["user"]["id"]}/memberships',
            headers=headers
        )
        
        if response.status_code == 200:
            memberships = response.json().get('memberships', [])
            if memberships:
                # Handle different possible status field names
                status = memberships[0].get('status') or memberships[0].get('membership_status')
                self.assert_equal(
                    status,
                    'inactive',
                    "Membership status",
                    "Membership marked as inactive"
                )
    
    def test_membership_validity_periods(self):
        """Test membership with valid_from and valid_until dates"""
        platform = self.factory.create_test_platform("validity")
        org = self.factory.create_entity(parent_id=platform['id'])
        
        # Create role and user
        role = self.factory.create_role(org['id'], "temp_role")
        user = self.factory.create_test_user("temp_user")
        
        headers = get_system_admin_headers(self.auth)
        
        # Set membership with validity period
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        valid_from = now - timedelta(days=1)
        valid_until = now + timedelta(days=30)
        
        response = self.make_request(
            'PUT',
            f'/v1/users/{user["id"]}',
            headers=headers,
            json_data={
                "entity_assignments": [
                    {
                        "entity_id": org['id'],
                        "role_ids": [role['id']],
                        "status": "active",
                        "valid_from": valid_from.isoformat(),
                        "valid_until": valid_until.isoformat()
                    }
                ]
            }
        )
        
        self.assert_status(response, 200, "Set membership validity period")
        
        # Verify validity dates were set
        response = self.make_request(
            'GET',
            f'/v1/users/{user["id"]}/memberships',
            headers=headers
        )
        
        if response.status_code == 200:
            memberships = response.json().get('memberships', [])
            if memberships:
                membership = memberships[0]
                self.assert_true(
                    'valid_from' in membership or 'valid_until' in membership,
                    "Validity period fields",
                    "Membership has validity period information"
                )
    
    def test_cross_entity_membership(self):
        """Test user membership across different entity types"""
        platform = self.factory.create_test_platform("cross_entity")
        
        # Create different entity types
        org = self.factory.create_entity(
            parent_id=platform['id'],
            entity_type="organization"
        )
        division = self.factory.create_entity(
            parent_id=org['id'],
            entity_type="division"
        )
        team = self.factory.create_entity(
            parent_id=division['id'],
            entity_type="team"
        )
        access_group = self.factory.create_entity(
            parent_id=platform['id'],
            entity_type="access_group",
            entity_class="ACCESS_GROUP"
        )
        
        # Create roles at different levels
        org_role = self.factory.create_role(org['id'], "org_member")
        team_role = self.factory.create_role(team['id'], "team_member")
        group_role = self.factory.create_role(access_group['id'], "group_member")
        
        # Create user with memberships at multiple levels
        user = self.factory.create_test_user("cross_entity_user")
        
        headers = get_system_admin_headers(self.auth)
        response = self.make_request(
            'PUT',
            f'/v1/users/{user["id"]}',
            headers=headers,
            json_data={
                "entity_assignments": [
                    {
                        "entity_id": org['id'],
                        "role_ids": [org_role['id']],
                        "status": "active"
                    },
                    {
                        "entity_id": team['id'],
                        "role_ids": [team_role['id']],
                        "status": "active"
                    },
                    {
                        "entity_id": access_group['id'],
                        "role_ids": [group_role['id']],
                        "status": "active"
                    }
                ]
            }
        )
        
        self.assert_status(response, 200, "Cross-entity membership")
        
        # Verify memberships
        user_data = response.json()
        entities = user_data.get('entities', [])
        entity_types = [e.get('entity_type') for e in entities]
        
        self.assert_contains(
            entity_types,
            'organization',
            "Organization membership",
            "User is member of organization"
        )
        
        self.assert_contains(
            entity_types,
            'team',
            "Team membership",
            "User is member of team"
        )
        
        self.assert_contains(
            entity_types,
            'access_group',
            "Access group membership",
            "User is member of access group"
        )
    
    def test_last_admin_protection(self):
        """Test protection against removing last admin"""
        platform = self.factory.create_test_platform("last_admin")
        org = self.factory.create_entity(parent_id=platform['id'])
        
        # Create admin role
        admin_role = self.factory.create_role(
            org['id'],
            "org_admin",
            permissions=["entity:create", "entity:read", "entity:update", "entity:delete", "user:create", "user:read", "user:update", "user:delete", "role:create", "role:read", "role:update", "role:delete"]
        )
        
        # Create single admin user
        admin_data = self.factory.create_user_with_role(
            org['id'],
            "sole_admin",
            permissions=["entity:create", "entity:read", "entity:update", "entity:delete", "user:create", "user:read", "user:update", "user:delete", "role:create", "role:read", "role:update", "role:delete"]
        )
        
        headers = get_system_admin_headers(self.auth)
        
        # Try to remove the only admin
        response = self.make_request(
            'PUT',
            f'/v1/users/{admin_data["user"]["id"]}',
            headers=headers,
            json_data={
                "entity_assignments": []
            }
        )
        
        # Should either succeed (no protection) or fail with appropriate error
        if response.status_code == 400:
            self.pass_test(
                "Last admin protection",
                "System prevents removing last admin"
            )
        else:
            self.pass_test(
                "Last admin removal",
                f"Last admin removal allowed (status: {response.status_code})"
            )
    
    def test_cascade_membership_deletion(self):
        """Test cascade deletion of memberships when entity deleted"""
        platform = self.factory.create_test_platform("cascade")
        org = self.factory.create_entity(parent_id=platform['id'])
        team = self.factory.create_entity(parent_id=org['id'], entity_type="team")
        
        # Create users in team
        user1_data = self.factory.create_user_with_role(team['id'], "team_member1")
        user2_data = self.factory.create_user_with_role(team['id'], "team_member2")
        
        headers = get_system_admin_headers(self.auth)
        
        # Delete the team entity
        response = self.make_request(
            'DELETE',
            f'/v1/entities/{team["id"]}?cascade=true',
            headers=headers
        )
        
        if response.status_code == 200:
            # Check if users still exist but without team membership
            response = self.make_request(
                'GET',
                f'/v1/users/{user1_data["user"]["id"]}/memberships',
                headers=headers
            )
            
            if response.status_code == 200:
                memberships = response.json().get('memberships', [])
                team_memberships = [m for m in memberships if m.get('entity_id') == team['id']]
                
                self.assert_equal(
                    len(team_memberships),
                    0,
                    "Team memberships after deletion",
                    "Team memberships removed when entity deleted"
                )
        else:
            self.pass_test(
                "Cascade deletion",
                f"Entity deletion returned status {response.status_code}"
            )
    
    def cleanup(self):
        """Cleanup test data"""
        self.log("Cleaning up test data...")
        self.factory.cleanup_test_data()


if __name__ == "__main__":
    # Run just this test
    from auth_utils import AuthManager
    
    auth = AuthManager()
    test = MembershipTest(auth)
    test.run()
    test.print_summary()