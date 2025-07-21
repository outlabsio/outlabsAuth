#!/usr/bin/env python3
"""
Test just the regional manager scenario for debugging
"""
from base_test import APITest
from auth_utils import get_system_admin_headers, AuthManager
from test_data_factory import TestDataFactory
import json


class RegionalManagerTest(APITest):
    """Test regional manager with tree permissions"""
    
    def __init__(self, auth_manager):
        super().__init__("Regional Manager Debug Test", auth_manager)
        self.factory = TestDataFactory(auth_manager)
        
    def run(self):
        """Run regional manager test"""
        try:
            self.test_regional_manager_scenario()
        finally:
            self.cleanup()
    
    def test_regional_manager_scenario(self):
        """Test regional manager with tree permissions seeing all sub-entities"""
        # Create hierarchy: Platform -> Region -> Office -> Team
        platform = self.factory.create_test_platform("regional_test")
        
        # Create regional structure
        region = self.factory.create_entity(
            parent_id=platform['id'],
            entity_type="region",
            name_prefix="west_region"
        )
        
        # Create offices under region
        office1 = self.factory.create_entity(
            parent_id=region['id'],
            entity_type="office",
            name_prefix="seattle_office"
        )
        
        office2 = self.factory.create_entity(
            parent_id=region['id'],
            entity_type="office",
            name_prefix="portland_office"
        )
        
        # Create teams under offices
        team1 = self.factory.create_entity(
            parent_id=office1['id'],
            entity_type="team",
            name_prefix="sales_team"
        )
        
        team2 = self.factory.create_entity(
            parent_id=office2['id'],
            entity_type="team",
            name_prefix="support_team"
        )
        
        # Create regional manager with tree permissions at region level
        regional_manager = self.factory.create_test_user("regional_manager")
        
        # Create role with tree permissions
        role = self.factory.create_role(
            entity_id=region['id'],
            name_prefix="reg_mgr",
            permissions=[
                "entity:read_tree",
                "user:read_tree",
                "user:manage_tree",
                "member:read_tree"
            ]
        )
        
        # Assign regional manager to region with the role
        self.factory.add_user_to_entity(
            user_id=regional_manager['id'],
            entity_id=region['id'],
            role_id=role['id']
        )
        
        # Check memberships first
        self.log(f"Regional manager ID: {regional_manager['id']}")
        self.log(f"Region ID: {region['id']}")
        
        # Test: Regional manager can see all entities in the region
        manager_headers = self.auth.get_headers(
            regional_manager['email'], 
            regional_manager['test_password']
        )
        
        # First test - can they see the region they're a member of?
        response = self.make_request(
            'GET',
            f'/v1/entities/{region["id"]}',
            headers=manager_headers
        )
        
        self.log(f"Can access region directly: {response.status_code}")
        
        # Get user's memberships
        response = self.make_request(
            'GET',
            f'/v1/entities/users/{regional_manager["id"]}/memberships',
            headers=manager_headers
        )
        
        if response.status_code == 200:
            memberships = response.json()
            self.log(f"User memberships: {json.dumps(memberships, indent=2)}")
        
        # Search entities - should see region and all sub-entities
        response = self.make_request(
            'GET',
            '/v1/entities?page_size=50',
            headers=manager_headers
        )
        
        self.assert_status(response, 200, "Regional manager lists entities")
        
        data = response.json()
        entity_ids = [item['id'] for item in data['items']]
        entity_names = [item['name'] for item in data['items']]
        
        # Debug output
        self.log(f"Regional manager can see {len(entity_ids)} entities")
        self.log(f"Entity IDs: {entity_ids}")
        self.log(f"Entity names: {entity_names}")
        self.log(f"Total entities returned: {data.get('total', 0)}")
        
        # Test specific entity access
        for entity_id, entity_name in [(region['id'], 'region'), (office1['id'], 'office1'), 
                                       (team1['id'], 'team1')]:
            response = self.make_request(
                'GET',
                f'/v1/entities/{entity_id}',
                headers=manager_headers
            )
            self.log(f"Direct access to {entity_name}: {response.status_code}")
            if response.status_code != 200:
                self.log(f"Error: {response.text}")
    
    def cleanup(self):
        """Cleanup test data"""
        self.log("Cleaning up test data...")
        self.factory.cleanup_test_data()


if __name__ == "__main__":
    # Run just this test
    from auth_utils import AuthManager
    
    auth = AuthManager()
    test = RegionalManagerTest(auth)
    test.run()
    test.print_summary()