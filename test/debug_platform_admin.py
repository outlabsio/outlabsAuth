#!/usr/bin/env python3
"""Debug platform admin tree permissions issue"""
import sys
sys.path.insert(0, '.')

from base_test import APITest
from auth_utils import get_system_admin_headers, AuthManager
from test_data_factory import TestDataFactory
import json


class DebugPlatformAdmin(APITest):
    def __init__(self, auth_manager):
        super().__init__("Debug Platform Admin", auth_manager)
        self.factory = TestDataFactory(auth_manager)
    
    def run(self):
        try:
            # Create platform
            platform = self.factory.create_test_platform("debug_platform")
            print(f"Created platform: {platform['name']} (ID: {platform['id']})")
            
            # Create platform admin user
            platform_admin = self.factory.create_test_user("debug_admin")
            print(f"Created user: {platform_admin['email']} (ID: {platform_admin['id']})")
            
            # Create platform admin role with tree permissions
            admin_role = self.factory.create_role(
                entity_id=platform['id'],
                name_prefix="debug_admin",
                permissions=[
                    "entity:read_tree",
                    "entity:create_tree", 
                    "entity:update_tree",
                    "entity:delete_tree"
                ]
            )
            print(f"Created role with permissions: {admin_role['permissions']}")
            
            # Assign platform admin
            self.factory.add_user_to_entity(
                user_id=platform_admin['id'],
                entity_id=platform['id'],
                role_id=admin_role['id']
            )
            print(f"Added user to platform with role")
            
            # Get admin headers
            admin_headers = self.auth.get_headers(
                platform_admin['email'],
                platform_admin['test_password']
            )
            
            # Create an organization
            org = self.factory.create_entity(
                parent_id=platform['id'],
                entity_type="organization",
                name_prefix="debug_org"
            )
            print(f"\nCreated org: {org['name']} (ID: {org['id']})")
            print(f"Org parent: {org.get('parent_entity_id')}")
            
            # Now test updating the org
            print("\n--- Testing Update ---")
            response = self.make_request(
                'PUT',
                f'/v1/entities/{org["id"]}',
                headers=admin_headers,
                json_data={
                    "description": "Updated by platform admin"
                }
            )
            
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
            
            if response.status_code != 200:
                # Debug - check what permissions the user actually has
                print("\n--- Debugging Permissions ---")
                
                # Check user's permissions at platform level
                sys_headers = get_system_admin_headers()
                
                # Get user's memberships
                response = self.make_request(
                    'GET',
                    f'/v1/users/{platform_admin["id"]}/memberships',
                    headers=sys_headers
                )
                
                if response.status_code == 200:
                    memberships = response.json()
                    print(f"User has {len(memberships)} memberships")
                    for m in memberships:
                        print(f"  Entity: {m.get('entity', {}).get('name')} - Roles: {[r.get('name') for r in m.get('roles', [])]}")
            
            # Don't cleanup so we can debug
            # self.factory.cleanup()
            print("\nKeeping data for debugging...")
            
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    auth_manager = AuthManager()
    test = DebugPlatformAdmin(auth_manager)
    test.run()