#!/usr/bin/env python3
"""Debug permissions in detail"""
import asyncio
import sys
sys.path.insert(0, '..')

from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
import os
os.environ.setdefault("ENVIRONMENT", "development")

from api.models import EntityModel, UserModel, RoleModel, EntityMembershipModel
from api.services.permission_service import PermissionService
from api.services.entity_service import EntityService
from api.config import settings


async def debug_permissions():
    # Initialize database
    client = AsyncIOMotorClient(settings.DATABASE_URL)
    await init_beanie(
        database=client[settings.MONGO_DATABASE],
        document_models=[
            UserModel, EntityModel, RoleModel, EntityMembershipModel
        ]
    )
    
    # Find the entities we just created - get the most recent one
    orgs = await EntityModel.find(
        {"name": {"$regex": "test_debug_org"}}
    ).sort("-created_at").limit(1).to_list()
    
    if not orgs:
        print("No debug org found")
        return
        
    org = orgs[0]
        
    print(f"Found org: {org.name} (ID: {org.id})")
    
    # Get platform
    platform = await EntityModel.get(org.parent_entity.id, fetch_links=True)
    print(f"Platform: {platform.name} (ID: {platform.id})")
    
    # Find user
    user = await UserModel.find_one(
        {"email": {"$regex": "test_debug_admin"}}
    )
    
    if not user:
        print("No debug user found")
        return
        
    print(f"User: {user.email} (ID: {user.id})")
    
    # Get user's membership in platform
    membership = await EntityMembershipModel.find_one(
        EntityMembershipModel.user.id == user.id,
        EntityMembershipModel.entity.id == platform.id
    )
    
    if not membership:
        print("No membership found")
        return
        
    print(f"\nMembership found in platform")
    
    # Check roles
    for role_ref in membership.roles:
        role = await role_ref.fetch()
        print(f"Role: {role.name}")
        print(f"Permissions: {role.permissions}")
    
    # Test permission service
    perm_service = PermissionService()
    
    print("\n--- Direct Permission Checks ---")
    
    # Check update permission in org (should fail)
    has_perm, source = await perm_service.check_permission(
        str(user.id),
        "entity:update",
        str(org.id)
    )
    print(f"entity:update in org: {has_perm} (source: {source})")
    
    # Check update_tree permission in platform (should pass)
    has_perm, source = await perm_service.check_permission(
        str(user.id),
        "entity:update_tree", 
        str(platform.id)
    )
    print(f"entity:update_tree in platform: {has_perm} (source: {source})")
    
    # Get entity path
    entity_path = await EntityService.get_entity_path(str(org.id))
    print(f"\nEntity path: {[e.name for e in entity_path]}")
    
    # Now simulate what the dependency does
    print("\n--- Simulating Dependency Check ---")
    
    # The dependency skips the org itself and checks parents
    parents_to_check = entity_path[1:]
    print(f"Parents to check: {[e.name for e in parents_to_check]}")
    
    for parent in parents_to_check:
        print(f"\nChecking parent: {parent.name} (ID: {parent.id})")
        
        # Check update_tree
        has_perm, source = await perm_service.check_permission(
            str(user.id),
            "entity:update_tree",
            str(parent.id)
        )
        print(f"  entity:update_tree: {has_perm} (source: {source})")
        
        # Check what permissions user has in this entity
        user_perms = await perm_service.resolve_user_permissions(
            str(user.id),
            str(parent.id)
        )
        print(f"  All permissions in {parent.name}: {user_perms}")
    
    # Also check if the issue is with how permissions are resolved
    print("\n--- Permission Resolution Details ---")
    
    # Check permissions at org level  
    org_perms = await perm_service.resolve_user_permissions(
        str(user.id),
        str(org.id)
    )
    print(f"Permissions at org level: {org_perms}")
    
    # Check if tree permissions from parent show up
    print("\n--- Checking Tree Permission Logic ---")
    
    # The permission service should check tree permissions from parents
    # Let's trace through the exact logic
    print(f"When checking 'entity:update' in org {org.id}:")
    print(f"1. Direct permission check: {await perm_service.check_permission(str(user.id), 'entity:update', str(org.id))}")
    print(f"2. Should check parents for entity:update_tree...")
    
    # The issue might be in the permission service itself
    # Let's check if it's properly checking tree permissions from parents


if __name__ == "__main__":
    asyncio.run(debug_permissions())