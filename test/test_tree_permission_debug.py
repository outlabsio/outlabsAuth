#!/usr/bin/env python3
"""
Debug tree permission checking
"""
from base_test import APITest
from auth_utils import get_system_admin_headers, AuthManager
from test_data_factory import TestDataFactory


class TreePermissionDebugTest(APITest):
    """Debug why tree permissions aren't working for member:manage"""
    
    def __init__(self, auth_manager):
        super().__init__("Tree Permission Debug Test", auth_manager)
        self.factory = TestDataFactory(auth_manager)
        
    def run(self):
        """Run test"""
        try:
            # Create simple hierarchy
            platform = self.factory.create_test_platform("debug_test")
            
            parent = self.factory.create_entity(
                parent_id=platform['id'],
                entity_type="organization"
            )
            
            child = self.factory.create_entity(
                parent_id=parent['id'],
                entity_type="team"
            )
            
            # Create user with member:manage_tree at parent
            user = self.factory.create_test_user("tree_user")
            
            role = self.factory.create_role(
                entity_id=parent['id'],
                name_prefix="tree_role",
                permissions=["member:manage_tree"]
            )
            
            self.factory.add_user_to_entity(
                user_id=user['id'],
                entity_id=parent['id'],
                role_id=role['id']
            )
            
            # Test adding member to child entity
            headers = self.auth.get_headers(user['email'], user['test_password'])
            
            # Create another user to add
            new_member = self.factory.create_test_user("new_member")
            
            # Create a role in the child entity
            child_role = self.factory.create_role(
                entity_id=child['id'],
                name_prefix="member",
                permissions=["entity:read"]
            )
            
            # Try to add member to child entity
            response = self.make_request(
                'POST',
                f'/v1/entities/{child["id"]}/members',
                headers=headers,
                json_data={
                    "user_id": new_member['id'],
                    "role_id": child_role['id']
                }
            )
            
            self.log(f"Response status: {response.status_code}")
            if response.status_code != 200:
                self.log(f"Response: {response.text}")
            
            # Also test direct permission check
            admin_headers = get_system_admin_headers(self.auth)
            response = self.make_request(
                'POST',
                f'/v1/entities/{child["id"]}/check-permissions',
                headers=headers,
                json_data={
                    "permissions": ["member:manage", "member:manage_tree"]
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                self.log(f"Permission check result: {data}")
                
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Cleanup test data"""
        self.log("Cleaning up...")
        self.factory.cleanup_test_data()


if __name__ == "__main__":
    auth = AuthManager()
    test = TreePermissionDebugTest(auth)
    test.run()
    test.print_summary()