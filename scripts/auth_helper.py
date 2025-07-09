#!/usr/bin/env python3
"""
Authentication testing helper for outlabsAuth

This script provides utilities for testing authentication and authorization:
- Login with different user types
- Get access tokens for API testing
- Test permission checks
- Validate entity access

Usage:
    python scripts/auth_helper.py login --user system
    python scripts/auth_helper.py test-permissions --user org --entity-id <id>
    python scripts/auth_helper.py list-users
"""
import asyncio
import json
import sys
import os
import argparse
from typing import Optional, Dict, Any
import aiohttp

# Add the project root to Python path  
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from api.database import init_db
from api.models import UserModel, EntityModel, RoleModel


class AuthHelper:
    """Authentication testing helper"""
    
    def __init__(self, base_url: str = "http://localhost:8030"):
        self.base_url = base_url
        self.session = None
        
        # Predefined test users
        self.test_users = {
            "system": {"email": "system@outlabs.com", "password": "outlabs123"},
            "platform": {"email": "platform@outlabs.com", "password": "platform123"},
            "org": {"email": "org@outlabs.com", "password": "org123"},
            "team": {"email": "team@outlabs.com", "password": "team123"},
            "user": {"email": "user@outlabs.com", "password": "user123"},
            "viewer": {"email": "viewer@outlabs.com", "password": "viewer123"}
        }
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
            
    async def login_user(self, user_type: str, output_format: str = "json") -> Optional[Dict[str, Any]]:
        """Login a test user and get tokens"""
        if user_type not in self.test_users:
            print(f"❌ Unknown user type: {user_type}")
            print(f"Available users: {', '.join(self.test_users.keys())}")
            return None
            
        user_creds = self.test_users[user_type]
        
        try:
            async with self.session.post(
                f"{self.base_url}/v1/auth/login/json",
                json=user_creds,
                headers={"Content-Type": "application/json"}
            ) as response:
                
                if response.status == 200:
                    token_data = await response.json()
                    
                    if output_format == "json":
                        print(json.dumps(token_data, indent=2))
                    elif output_format == "token":
                        print(token_data["access_token"])
                    elif output_format == "export":
                        print(f"export ACCESS_TOKEN='{token_data['access_token']}'")
                        print(f"export REFRESH_TOKEN='{token_data['refresh_token']}'")
                    elif output_format == "curl":
                        print(f"ACCESS_TOKEN='{token_data['access_token']}'")
                        print(f"# Use in curl commands:")
                        print(f"curl -H \"Authorization: Bearer $ACCESS_TOKEN\" {self.base_url}/v1/auth/me")
                    
                    return token_data
                else:
                    error_data = await response.json()
                    print(f"❌ Login failed: {error_data}")
                    return None
                    
        except Exception as e:
            print(f"❌ Login error: {e}")
            return None
            
    async def test_user_info(self, access_token: str) -> Optional[Dict[str, Any]]:
        """Test getting current user info"""
        try:
            async with self.session.get(
                f"{self.base_url}/v1/auth/me",
                headers={"Authorization": f"Bearer {access_token}"}
            ) as response:
                
                if response.status == 200:
                    user_data = await response.json()
                    print("✅ User info retrieved:")
                    print(json.dumps(user_data, indent=2))
                    return user_data
                else:
                    error_data = await response.json()
                    print(f"❌ Failed to get user info: {error_data}")
                    return None
                    
        except Exception as e:
            print(f"❌ Error getting user info: {e}")
            return None
            
    async def test_permissions(self, user_type: str, entity_id: Optional[str] = None):
        """Test permission checks for a user"""
        print(f"🔐 Testing permissions for {user_type}...")
        
        # Login first
        token_data = await self.login_user(user_type, output_format="silent")
        if not token_data:
            return
            
        access_token = token_data["access_token"]
        
        # Test user info
        await self.test_user_info(access_token)
        
        # Test entity access if entity_id provided
        if entity_id:
            await self.test_entity_access(access_token, entity_id)
            
        # Test role endpoints
        await self.test_roles_access(access_token)
        
    async def test_entity_access(self, access_token: str, entity_id: str):
        """Test entity access with current token"""
        print(f"\n🏢 Testing entity access for {entity_id}...")
        
        endpoints_to_test = [
            ("GET", f"/v1/entities/{entity_id}", "Get entity"),
            ("GET", f"/v1/entities/{entity_id}/members", "List members"),
            ("GET", f"/v1/entities/{entity_id}/tree", "Get entity tree"),
            ("GET", f"/v1/entities/{entity_id}/path", "Get entity path")
        ]
        
        for method, endpoint, description in endpoints_to_test:
            try:
                async with self.session.request(
                    method,
                    f"{self.base_url}{endpoint}",
                    headers={"Authorization": f"Bearer {access_token}"}
                ) as response:
                    
                    if response.status < 400:
                        print(f"  ✅ {description}: {response.status}")
                    else:
                        print(f"  ❌ {description}: {response.status}")
                        
            except Exception as e:
                print(f"  ❌ {description}: Error - {e}")
                
    async def test_roles_access(self, access_token: str):
        """Test role endpoints access"""
        print(f"\n🎭 Testing role access...")
        
        endpoints_to_test = [
            ("GET", "/v1/roles/", "List roles"),
            ("GET", "/v1/roles/templates", "Get role templates")
        ]
        
        for method, endpoint, description in endpoints_to_test:
            try:
                async with self.session.request(
                    method,
                    f"{self.base_url}{endpoint}",
                    headers={"Authorization": f"Bearer {access_token}"}
                ) as response:
                    
                    if response.status < 400:
                        print(f"  ✅ {description}: {response.status}")
                    else:
                        print(f"  ❌ {description}: {response.status}")
                        
            except Exception as e:
                print(f"  ❌ {description}: Error - {e}")
                
    async def list_database_users(self):
        """List users from database"""
        try:
            await init_db()
            print("👥 Database Users:")
            
            users = await UserModel.find_all().to_list()
            for user in users:
                status_icon = "✅" if user.status == "active" else "❌"
                verified_icon = "📧" if user.email_verified else "📩"
                name = f"{user.profile.first_name} {user.profile.last_name}" if user.profile else "No Profile"
                print(f"  {status_icon} {verified_icon} {user.email:<30} - {name}")
                
        except Exception as e:
            print(f"❌ Error listing users: {e}")
            
    async def list_database_entities(self):
        """List entities from database"""
        try:
            await init_db()
            print("🏢 Database Entities:")
            
            entities = await EntityModel.find_all().to_list()
            for entity in entities:
                status_icon = "✅" if entity.status == "active" else "❌" 
                parent_name = ""
                if entity.parent_entity:
                    parent = await entity.parent_entity.fetch()
                    parent_name = f" (parent: {parent.name})" if parent else ""
                    
                print(f"  {status_icon} {entity.entity_type:<15} {entity.name:<25} - {entity.display_name}{parent_name}")
                
        except Exception as e:
            print(f"❌ Error listing entities: {e}")
            
    async def list_database_roles(self):
        """List roles from database"""
        try:
            await init_db()
            print("🎭 Database Roles:")
            
            roles = await RoleModel.find_all().to_list()
            for role in roles:
                global_icon = "🌍" if role.is_global else "🏢"
                system_icon = "⚙️" if role.is_system_role else "👤"
                entity_info = ""
                if role.entity_id:
                    entity = await EntityModel.get(role.entity_id)
                    entity_info = f" (entity: {entity.name})" if entity else " (entity: unknown)"
                    
                print(f"  {global_icon} {system_icon} {role.name:<20} - {role.display_name}{entity_info}")
                print(f"    Permissions: {', '.join(role.permissions[:3])}{'...' if len(role.permissions) > 3 else ''}")
                
        except Exception as e:
            print(f"❌ Error listing roles: {e}")
            
    async def check_api_health(self):
        """Check if API is running and healthy"""
        try:
            async with self.session.get(f"{self.base_url}/health") as response:
                if response.status == 200:
                    health_data = await response.json()
                    print(f"✅ API is healthy: {health_data}")
                    return True
                else:
                    print(f"❌ API health check failed: {response.status}")
                    return False
                    
        except Exception as e:
            print(f"❌ Cannot connect to API: {e}")
            print(f"Make sure the API is running on {self.base_url}")
            return False


async def main():
    """Main CLI function"""
    parser = argparse.ArgumentParser(description="Authentication testing helper")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Login command
    login_parser = subparsers.add_parser("login", help="Login as a test user")
    login_parser.add_argument("--user", choices=["system", "platform", "org", "team", "user", "viewer"], 
                             required=True, help="User type to login as")
    login_parser.add_argument("--format", choices=["json", "token", "export", "curl"], 
                             default="json", help="Output format")
    
    # Test permissions command
    test_parser = subparsers.add_parser("test-permissions", help="Test permissions for a user")
    test_parser.add_argument("--user", choices=["system", "platform", "org", "team", "user", "viewer"], 
                            required=True, help="User type to test")
    test_parser.add_argument("--entity-id", help="Entity ID to test access for")
    
    # List commands
    subparsers.add_parser("list-users", help="List users from database")
    subparsers.add_parser("list-entities", help="List entities from database") 
    subparsers.add_parser("list-roles", help="List roles from database")
    subparsers.add_parser("health", help="Check API health")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
        
    async with AuthHelper() as helper:
        # Check API health first for API-dependent commands
        if args.command in ["login", "test-permissions", "health"]:
            if not await helper.check_api_health():
                return
                
        if args.command == "login":
            await helper.login_user(args.user, args.format)
            
        elif args.command == "test-permissions":
            await helper.test_permissions(args.user, args.entity_id)
            
        elif args.command == "list-users":
            await helper.list_database_users()
            
        elif args.command == "list-entities":
            await helper.list_database_entities()
            
        elif args.command == "list-roles":
            await helper.list_database_roles()
            
        elif args.command == "health":
            # Already checked above
            pass


if __name__ == "__main__":
    asyncio.run(main())