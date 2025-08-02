#!/usr/bin/env python3
"""Debug tree permissions issue"""
import asyncio
import sys
sys.path.insert(0, '.')

from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
import os
os.environ.setdefault("ENVIRONMENT", "development")

from api.models import EntityModel, UserModel, RoleModel, EntityMembershipModel
from api.services.permission_service import PermissionService
from api.services.entity_service import EntityService
from api.config import settings


async def debug_tree_permissions():
    # Initialize database
    client = AsyncIOMotorClient(settings.DATABASE_URL)
    await init_beanie(
        database=client[settings.MONGO_DATABASE],
        document_models=[
            UserModel, EntityModel, RoleModel, EntityMembershipModel
        ]
    )
    
    # Find a platform admin scenario
    # Look for a platform with entity:update_tree permissions
    platforms = await EntityModel.find(
        EntityModel.entity_type == "platform",
        {"name": {"$regex": "test_platform_admin_test"}}
    ).sort("-created_at").limit(1).to_list()
    
    if not platforms:
        print("No test platform found")
        return
        
    platform = platforms[0]
    print(f"Platform: {platform.name} (ID: {platform.id})")
    
    # Find organizations under this platform
    orgs = await EntityModel.find(
        EntityModel.parent_entity.id == platform.id,
        EntityModel.entity_type == "organization"
    ).to_list()
    
    if not orgs:
        print("No organizations found")
        return
        
    org = orgs[0]
    print(f"Organization: {org.name} (ID: {org.id})")
    print(f"Organization parent: {org.parent_entity}")
    
    # Get entity path
    entity_path = await EntityService.get_entity_path(str(org.id))
    print(f"Entity path for org: {[e.name for e in entity_path]}")
    print(f"Entity path IDs: {[str(e.id) for e in entity_path]}")
    
    # Find platform admin user
    memberships = await EntityMembershipModel.find(
        EntityMembershipModel.entity.id == platform.id,
        EntityMembershipModel.is_active == True
    ).to_list()
    
    if not memberships:
        print("No memberships found")
        # Try to find by email pattern
        users = await UserModel.find(
            {"email": {"$regex": "platform_admin"}}
        ).sort("-created_at").limit(1).to_list()
        
        if users:
            user = users[0]
            print(f"\nFound user by email: {user.email} (ID: {user.id})")
            
            # Find their memberships
            memberships = await EntityMembershipModel.find(
                EntityMembershipModel.user.id == user.id,
                EntityMembershipModel.is_active == True
            ).to_list()
            
            if not memberships:
                print("No active memberships for this user")
                return
                
            # Find membership in platform
            platform_membership = None
            for m in memberships:
                if m.entity and hasattr(m.entity, 'id') and str(m.entity.id) == str(platform.id):
                    platform_membership = m
                    break
                    
            if not platform_membership:
                print("User not a member of this platform")
                return
                
            membership = platform_membership
        else:
            return
    else:        
        membership = memberships[0]
        user = await membership.user.fetch()
        print(f"\nUser: {user.email} (ID: {user.id})")
    
    # Check roles
    roles = []
    for role_ref in membership.roles:
        role = await role_ref.fetch()
        roles.append(role)
        print(f"Role: {role.name} with permissions: {role.permissions}")
    
    # Now test permission checks
    print("\n--- Permission Checks ---")
    
    # Create permission service instance
    permission_service = PermissionService()
    
    # Direct update permission in org
    has_perm, source = await permission_service.check_permission(
        str(user.id),
        "entity:update",
        str(org.id)
    )
    print(f"entity:update in org: {has_perm} (source: {source})")
    
    # Update tree permission in platform
    has_perm, source = await permission_service.check_permission(
        str(user.id),
        "entity:update_tree",
        str(platform.id)
    )
    print(f"entity:update_tree in platform: {has_perm} (source: {source})")
    
    # Check what permissions user has in platform
    user_perms = await permission_service.resolve_user_permissions(
        str(user.id),
        str(platform.id)
    )
    print(f"\nUser permissions in platform: {user_perms}")
    
    # Check what permissions user has in org
    user_perms_org = await permission_service.resolve_user_permissions(
        str(user.id),
        str(org.id)
    )
    print(f"User permissions in org: {user_perms_org}")
    
    # Test the actual permission check logic
    print("\n--- Testing Dependency Logic ---")
    
    # Simulate the dependency check
    print(f"Checking if user can update org {org.id}")
    print(f"Parents to check: {[str(e.id) for e in entity_path[1:]]}")
    
    for parent_entity in entity_path[1:]:
        has_update_tree, source = await permission_service.check_permission(
            str(user.id),
            "entity:update_tree",
            str(parent_entity.id)
        )
        print(f"  Check update_tree in {parent_entity.name} ({parent_entity.id}): {has_update_tree} (source: {source})")
        
        has_manage_tree, source = await permission_service.check_permission(
            str(user.id),
            "entity:manage_tree",
            str(parent_entity.id)
        )
        print(f"  Check manage_tree in {parent_entity.name} ({parent_entity.id}): {has_manage_tree} (source: {source})")


if __name__ == "__main__":
    asyncio.run(debug_tree_permissions())