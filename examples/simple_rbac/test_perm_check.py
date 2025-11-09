#!/usr/bin/env python3
"""Test permission checking directly."""
import asyncio
import os

os.environ["MONGODB_URL"] = "mongodb://localhost:27018"
os.environ["DATABASE_NAME"] = "blog_simple_rbac"

async def test():
    from outlabs_auth.services.permission import PermissionService
    from motor.motor_asyncio import AsyncIOMotorClient

    client = AsyncIOMotorClient("mongodb://localhost:27018")
    db = client["blog_simple_rbac"]

    perm_service = PermissionService()

    # Find admin user
    user = await db.users.find_one({"email": "admin@test.com"})
    user_id = str(user["_id"])

    print(f"Testing permission check for user: {user_id}")
    print(f"Is superuser: {user.get('is_superuser')}")

    # Test check_permission
    has_role_read = await perm_service.check_permission(
        user_id=user_id,
        permission="role:read"
    )
    print(f"\nHas 'role:read' permission: {has_role_read}")

    # Get all permissions
    all_perms = await perm_service.get_user_permissions(user_id=user_id)
    print(f"All permissions: {all_perms}")

asyncio.run(test())
