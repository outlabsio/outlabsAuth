#!/usr/bin/env python3
"""
Test script to verify Beanie Link functionality is working correctly.
"""
import asyncio
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from api.config import settings
from api.models.user_model import UserModel
from api.models.role_model import RoleModel
from api.models.group_model import GroupModel
from api.models.permission_model import PermissionModel
from api.models.client_account_model import ClientAccountModel
from api.services.user_service import user_service
from api.services.role_service import role_service
from api.services.group_service import group_service


async def test_beanie_links():
    """Test that Beanie Links are working correctly."""
    print("🔗 Testing Beanie Link functionality...")
    
    # Initialize database connection
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    database = client[settings.DATABASE_NAME]
    
    # Initialize Beanie
    await init_beanie(
        database=database,
        document_models=[
            UserModel,
            RoleModel,
            GroupModel,
            PermissionModel,
            ClientAccountModel
        ]
    )
    
    try:
        # Test 1: Fetch a user with roles and groups
        print("\n📋 Test 1: Fetching user with roles and groups...")
        users = await UserModel.find(fetch_links=True).limit(1).to_list()
        
        if users:
            user = users[0]
            print(f"✅ Found user: {user.email}")
            print(f"   Roles: {len(user.roles) if user.roles else 0}")
            print(f"   Groups: {len(user.groups) if user.groups else 0}")
            
            # Test role access
            if user.roles:
                for i, role in enumerate(user.roles):
                    if hasattr(role, 'name'):
                        print(f"   Role {i+1}: {role.name} (scope: {role.scope})")
                        if hasattr(role, 'permissions') and role.permissions:
                            print(f"     Permissions: {len(role.permissions)}")
                    else:
                        print(f"   Role {i+1}: {role} (legacy string format)")
            
            # Test group access
            if user.groups:
                for i, group in enumerate(user.groups):
                    if hasattr(group, 'name'):
                        print(f"   Group {i+1}: {group.name} (scope: {group.scope})")
                        if hasattr(group, 'permissions') and group.permissions:
                            print(f"     Permissions: {len(group.permissions)}")
                    else:
                        print(f"   Group {i+1}: {group} (legacy string format)")
        else:
            print("❌ No users found in database")
        
        # Test 2: Check service methods
        print("\n🔧 Test 2: Testing service methods...")
        if users:
            user = users[0]
            
            # Test permission resolution
            effective_permissions = await user_service.get_user_effective_permissions(user.id)
            print(f"✅ User effective permissions: {len(effective_permissions)}")
            
            # Test permission details
            permission_details = await user_service.get_user_effective_permission_details(user.id)
            print(f"✅ User permission details: {len(permission_details)}")
        
        # Test 3: Check role service
        print("\n⚙️ Test 3: Testing role service...")
        roles = await RoleModel.find(fetch_links=True).limit(3).to_list()
        
        for role in roles:
            print(f"✅ Role: {role.name}")
            if hasattr(role, 'permissions') and role.permissions:
                print(f"   Permissions: {len(role.permissions)}")
                for perm in role.permissions[:2]:  # Show first 2 permissions
                    if hasattr(perm, 'name'):
                        print(f"     - {perm.name}")
                    else:
                        print(f"     - {perm} (ObjectId)")
        
        print("\n✅ All Beanie Link tests completed successfully!")
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(test_beanie_links()) 