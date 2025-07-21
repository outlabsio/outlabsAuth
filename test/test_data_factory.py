#!/usr/bin/env python3
"""
Test Data Factory
Creates consistent test data for all test suites
"""
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
import requests
from auth_utils import AuthManager, get_system_admin_headers


class TestDataFactory:
    """Factory for creating test data via API calls"""
    
    def __init__(self, auth_manager: AuthManager):
        self.auth = auth_manager
        self.base_url = auth_manager.base_url
        # Track created resources for cleanup
        self.created_platforms = []
        self.created_entities = []
        self.created_users = []
        self.created_roles = []
        
    def _make_request(self, method: str, endpoint: str, headers: Dict[str, str], 
                     json_data: Optional[Dict] = None) -> requests.Response:
        """Make an API request"""
        url = f"{self.base_url}{endpoint}"
        return requests.request(
            method=method,
            url=url,
            headers=headers,
            json=json_data
        )
    
    def generate_unique_name(self, prefix: str) -> str:
        """Generate a unique name with timestamp"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        return f"test_{prefix}_{timestamp}_{unique_id}"
    
    def create_test_platform(self, name_prefix: str = "platform") -> Dict[str, Any]:
        """
        Create an isolated test platform
        Returns: Platform data including ID
        """
        headers = get_system_admin_headers(self.auth)
        platform_name = self.generate_unique_name(name_prefix)
        
        response = self._make_request(
            'POST',
            '/v1/entities',
            headers=headers,
            json_data={
                "name": platform_name,
                "display_name": f"Test {name_prefix.title()}",
                "entity_type": "platform",
                "entity_class": "STRUCTURAL",
                "description": f"Test platform for {name_prefix}",
                "status": "active"
            }
        )
        
        if response.status_code not in [200, 201]:
            raise Exception(f"Failed to create platform: {response.status_code} - {response.text}")
        
        platform = response.json()
        self.created_platforms.append(platform['id'])
        print(f"Created test platform: {platform_name} (ID: {platform['id']})")
        return platform
    
    def create_entity(self, parent_id: Optional[str] = None, 
                     entity_type: str = "organization",
                     entity_class: str = "STRUCTURAL",
                     name_prefix: str = None) -> Dict[str, Any]:
        """
        Create a test entity
        Returns: Entity data including ID
        """
        headers = get_system_admin_headers(self.auth)
        
        if name_prefix is None:
            name_prefix = entity_type
        
        entity_name = self.generate_unique_name(name_prefix)
        
        request_data = {
            "name": entity_name,
            "display_name": entity_name,  # Use same as name for consistency
            "entity_type": entity_type,
            "entity_class": entity_class,
            "description": f"Test {entity_type}",
            "status": "active"
        }
        
        if parent_id:
            request_data["parent_entity_id"] = parent_id
        
        response = self._make_request(
            'POST',
            '/v1/entities',
            headers=headers,
            json_data=request_data
        )
        
        if response.status_code not in [200, 201]:
            raise Exception(f"Failed to create entity: {response.status_code} - {response.text}")
        
        entity = response.json()
        self.created_entities.append(entity['id'])
        print(f"Created {entity_class} entity: {entity_name} (ID: {entity['id']})")
        return entity
    
    def create_entity_hierarchy(self, platform_id: str, depth: int = 3) -> List[Dict[str, Any]]:
        """
        Create a multi-level entity hierarchy
        Returns: List of created entities from top to bottom
        """
        entities = []
        parent_id = platform_id
        
        # Define entity types for each level
        entity_types = ["organization", "division", "team", "unit", "section"]
        
        for level in range(depth):
            entity_type = entity_types[level % len(entity_types)]
            entity = self.create_entity(
                parent_id=parent_id,
                entity_type=entity_type,
                entity_class="STRUCTURAL",
                name_prefix=f"level_{level}_{entity_type}"
            )
            entities.append(entity)
            parent_id = entity['id']
        
        return entities
    
    def create_test_user(self, email_prefix: str = "user", 
                        password: str = "TestPass123!") -> Dict[str, Any]:
        """
        Create a test user
        Returns: User data including ID and credentials
        """
        headers = get_system_admin_headers(self.auth)
        email = f"{self.generate_unique_name(email_prefix)}@test.com"
        
        response = self._make_request(
            'POST',
            '/v1/users',
            headers=headers,
            json_data={
                "email": email,
                "password": password,
                "profile": {
                    "first_name": "Test",
                    "last_name": email_prefix.title()
                }
            }
        )
        
        if response.status_code not in [200, 201]:
            raise Exception(f"Failed to create user: {response.status_code} - {response.text}")
        
        user = response.json()
        user['test_password'] = password  # Store password for login
        self.created_users.append(user['id'])
        print(f"Created test user: {email} (ID: {user['id']})")
        return user
    
    def create_role(self, entity_id: str, name_prefix: str = "role",
                   permissions: List[str] = None) -> Dict[str, Any]:
        """
        Create a test role in an entity
        Returns: Role data including ID
        """
        headers = get_system_admin_headers(self.auth)
        role_name = self.generate_unique_name(name_prefix)
        
        if permissions is None:
            permissions = ["entity:read", "user:read"]
        
        # Add X-Entity-Context-Id header for entity-scoped creation
        headers['X-Entity-Context-Id'] = entity_id
        
        response = self._make_request(
            'POST',
            '/v1/roles',
            headers=headers,
            json_data={
                "name": role_name,
                "display_name": f"Test {name_prefix.title()}",
                "description": f"Test role for {name_prefix}",
                "permissions": permissions,
                "entity_id": entity_id,
                "is_custom": True
            }
        )
        
        if response.status_code not in [200, 201]:
            raise Exception(f"Failed to create role: {response.status_code} - {response.text}")
        
        role = response.json()
        self.created_roles.append(role['id'])
        print(f"Created test role: {role_name} (ID: {role['id']})")
        return role
    
    def add_user_to_entity(self, user_id: str, entity_id: str, 
                          role_id: str) -> Dict[str, Any]:
        """
        Add a user to an entity with a specific role
        Returns: Membership data
        """
        headers = get_system_admin_headers(self.auth)
        
        response = self._make_request(
            'POST',
            f'/v1/entities/{entity_id}/members',
            headers=headers,
            json_data={
                "user_id": user_id,
                "role_id": role_id
            }
        )
        
        if response.status_code not in [200, 201]:
            raise Exception(f"Failed to add user to entity: {response.status_code} - {response.text}")
        
        membership = response.json()
        print(f"Added user {user_id} to entity {entity_id} with role {role_id}")
        return membership
    
    def create_user_with_role(self, entity_id: str, role_name: str = "member",
                             permissions: List[str] = None) -> Dict[str, Any]:
        """
        Create a user and assign them a role in an entity
        Returns: Dict with user, role, and membership data
        """
        # Create role first
        role = self.create_role(entity_id, name_prefix=role_name, permissions=permissions)
        
        # Use standard user creation endpoint with entity_assignments
        headers = get_system_admin_headers(self.auth)
        email = f"{self.generate_unique_name(role_name)}@test.com"
        password = "TestPass123!"
        
        response = self._make_request(
            'POST',
            '/v1/users',
            headers=headers,
            json_data={
                "email": email,
                "password": password,
                "first_name": "Test",
                "last_name": role_name.title(),
                "entity_assignments": [
                    {
                        "entity_id": entity_id,
                        "role_ids": [role['id']],
                        "status": "active"
                    }
                ],
                "is_active": True,
                "send_welcome_email": False
            }
        )
        
        if response.status_code not in [200, 201]:
            raise Exception(f"Failed to create user with role: {response.status_code} - {response.text}")
        
        user = response.json()
        user['test_password'] = password  # Store password for login
        self.created_users.append(user['id'])
        print(f"Created test user: {email} (ID: {user['id']}) with role in entity")
        
        return {
            "user": user,
            "role": role,
            "membership": {"entity_id": entity_id, "role_id": role['id']},
            "entity_id": entity_id
        }
    
    def get_user_headers(self, user_email: str, password: str) -> Dict[str, str]:
        """Get auth headers for a specific user"""
        return self.auth.get_headers(user_email, password)
    
    def cleanup_test_data(self):
        """
        Remove all test data created by this factory
        Should be called in reverse order of creation
        """
        headers = get_system_admin_headers(self.auth)
        
        # Note: We don't delete users as they might be referenced in audit logs
        # In a real test environment, you might want to deactivate them instead
        
        # Delete entities (this should cascade delete memberships and roles)
        for entity_id in reversed(self.created_entities):
            try:
                response = self._make_request(
                    'DELETE',
                    f'/v1/entities/{entity_id}?cascade=true',
                    headers=headers
                )
                if response.status_code == 200:
                    print(f"Deleted entity: {entity_id}")
            except Exception as e:
                print(f"Failed to delete entity {entity_id}: {e}")
        
        # Delete platforms
        for platform_id in reversed(self.created_platforms):
            try:
                response = self._make_request(
                    'DELETE',
                    f'/v1/entities/{platform_id}?cascade=true',
                    headers=headers
                )
                if response.status_code == 200:
                    print(f"Deleted platform: {platform_id}")
            except Exception as e:
                print(f"Failed to delete platform {platform_id}: {e}")
        
        # Clear tracking lists
        self.created_platforms.clear()
        self.created_entities.clear()
        self.created_users.clear()
        self.created_roles.clear()


if __name__ == "__main__":
    # Test the factory
    from auth_utils import AuthManager
    
    auth = AuthManager()
    factory = TestDataFactory(auth)
    
    try:
        # Create a test platform
        platform = factory.create_test_platform("factory_test")
        
        # Create entity hierarchy
        entities = factory.create_entity_hierarchy(platform['id'], depth=3)
        
        # Create a user with role in the last entity
        last_entity = entities[-1]
        user_data = factory.create_user_with_role(
            last_entity['id'],
            "test_member",
            permissions=["entity:read", "user:read"]
        )
        
        print(f"\nTest data created successfully!")
        print(f"Platform: {platform['name']}")
        print(f"Entities: {len(entities)}")
        print(f"User: {user_data['user']['email']}")
        
        # Cleanup
        input("\nPress Enter to cleanup test data...")
        factory.cleanup_test_data()
        
    except Exception as e:
        print(f"Error: {e}")
        factory.cleanup_test_data()