#!/usr/bin/env python3
"""
Reset Test Environment Script
Quickly resets the SimpleRBAC example database to a known good state for testing.

Usage:
    python reset_test_env.py

Environment Variables:
    MONGODB_URL: MongoDB connection string (default: mongodb://localhost:27018)
    DATABASE_NAME: Database name (default: blog_simple_rbac)
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path so we can import outlabs_auth
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from datetime import UTC, datetime

from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from outlabs_auth.models.permission import PermissionModel
from outlabs_auth.models.role import RoleModel

# Import models
from outlabs_auth.models.user import UserModel
from outlabs_auth.models.user_role_membership import UserRoleMembership
from outlabs_auth.utils.password import hash_password

# Configuration
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27018")
DATABASE_NAME = os.getenv("DATABASE_NAME", "blog_simple_rbac")


async def reset_database():
    """Reset database to clean test state using Beanie models."""
    print("🔄 Connecting to MongoDB...")
    client = AsyncIOMotorClient(MONGODB_URL)
    db = client[DATABASE_NAME]

    # Initialize Beanie with all models
    await init_beanie(
        database=db,
        document_models=[
            UserModel,
            RoleModel,
            PermissionModel,
            UserRoleMembership,
        ],
    )

    # Drop existing test data
    print("🗑️  Dropping existing test data...")
    await UserModel.delete_all()
    await RoleModel.delete_all()
    await UserRoleMembership.delete_all()
    await PermissionModel.delete_all()
    print("✅ Test data cleared\n")

    # Create permissions
    print("📝 Creating permissions...")
    permissions_data = [
        # User permissions
        {
            "name": "user:read",
            "display_name": "User Read",
            "resource": "user",
            "action": "read",
        },
        {
            "name": "user:create",
            "display_name": "User Create",
            "resource": "user",
            "action": "create",
        },
        {
            "name": "user:update",
            "display_name": "User Update",
            "resource": "user",
            "action": "update",
        },
        {
            "name": "user:delete",
            "display_name": "User Delete",
            "resource": "user",
            "action": "delete",
        },
        {
            "name": "user:manage",
            "display_name": "User Manage",
            "resource": "user",
            "action": "manage",
        },
        # Role permissions
        {
            "name": "role:read",
            "display_name": "Role Read",
            "resource": "role",
            "action": "read",
        },
        {
            "name": "role:create",
            "display_name": "Role Create",
            "resource": "role",
            "action": "create",
        },
        {
            "name": "role:update",
            "display_name": "Role Update",
            "resource": "role",
            "action": "update",
        },
        {
            "name": "role:delete",
            "display_name": "Role Delete",
            "resource": "role",
            "action": "delete",
        },
        # Permission permissions
        {
            "name": "permission:read",
            "display_name": "Permission Read",
            "resource": "permission",
            "action": "read",
        },
        {
            "name": "permission:create",
            "display_name": "Permission Create",
            "resource": "permission",
            "action": "create",
        },
        {
            "name": "permission:update",
            "display_name": "Permission Update",
            "resource": "permission",
            "action": "update",
        },
        # API Key permissions
        {
            "name": "apikey:read",
            "display_name": "API Key Read",
            "resource": "apikey",
            "action": "read",
        },
        {
            "name": "apikey:create",
            "display_name": "API Key Create",
            "resource": "apikey",
            "action": "create",
        },
        {
            "name": "apikey:revoke",
            "display_name": "API Key Revoke",
            "resource": "apikey",
            "action": "revoke",
        },
        # Blog-specific permissions
        {
            "name": "post:read",
            "display_name": "Post Read",
            "resource": "post",
            "action": "read",
        },
        {
            "name": "post:create",
            "display_name": "Post Create",
            "resource": "post",
            "action": "create",
        },
        {
            "name": "post:update",
            "display_name": "Post Update",
            "resource": "post",
            "action": "update",
        },
        {
            "name": "post:delete",
            "display_name": "Post Delete",
            "resource": "post",
            "action": "delete",
        },
        {
            "name": "comment:create",
            "display_name": "Comment Create",
            "resource": "comment",
            "action": "create",
        },
        {
            "name": "comment:delete",
            "display_name": "Comment Delete",
            "resource": "comment",
            "action": "delete",
        },
    ]

    permissions = []
    for perm_data in permissions_data:
        perm = PermissionModel(
            name=perm_data["name"],
            display_name=perm_data["display_name"],
            resource=perm_data["resource"],
            action=perm_data["action"],
            description=f"Permission to {perm_data['action']} {perm_data['resource']}",
            is_system=True,
            is_active=True,
        )
        await perm.insert()
        permissions.append(perm)

    print(f"   Created {len(permissions)} permissions\n")

    # Create roles
    print("🎭 Creating roles...")
    roles_data = [
        {
            "name": "reader",
            "display_name": "Reader",
            "description": "Read-only access to blog posts",
            "permissions": ["post:read"],
        },
        {
            "name": "writer",
            "display_name": "Writer",
            "description": "Can create and manage own blog posts",
            "permissions": [
                "post:read",
                "post:create",
                "post:update",
                "comment:create",
            ],
        },
        {
            "name": "editor",
            "display_name": "Editor",
            "description": "Can manage all blog content",
            "permissions": [
                "post:read",
                "post:create",
                "post:update",
                "post:delete",
                "comment:create",
                "comment:delete",
            ],
        },
        {
            "name": "admin",
            "display_name": "Administrator",
            "description": "Full system access",
            "permissions": [
                "post:read",
                "post:create",
                "post:update",
                "post:delete",
                "comment:create",
                "comment:delete",
                "user:read",
                "user:create",
                "user:update",
                "user:delete",
                "user:manage",
                "role:read",
                "role:create",
                "role:update",
                "role:delete",
                "permission:read",
                "permission:create",
                "permission:update",
                "apikey:read",
                "apikey:create",
                "apikey:revoke",
            ],
        },
    ]

    roles_map = {}
    for role_data in roles_data:
        role = RoleModel(
            name=role_data["name"],
            display_name=role_data["display_name"],
            description=role_data["description"],
            permissions=role_data["permissions"],
            is_system_role=True,
            is_global=True,
        )
        await role.insert()
        roles_map[role_data["name"]] = role

    print(f"   Created {len(roles_map)} roles\n")

    # Create test users with role assignments
    print("👥 Creating test users...")
    users_data = [
        {
            "email": "admin@test.com",
            "password": "Test123!!",
            "first_name": "Admin",
            "last_name": "User",
            "role": "admin",
            "is_superuser": True,
        },
        {
            "email": "editor@test.com",
            "password": "Test123!!",
            "first_name": "Editor",
            "last_name": "User",
            "role": "editor",
            "is_superuser": False,
        },
        {
            "email": "writer@test.com",
            "password": "Test123!!",
            "first_name": "Writer",
            "last_name": "User",
            "role": "writer",
            "is_superuser": False,
        },
    ]

    for user_data in users_data:
        # Create user
        user = UserModel(
            email=user_data["email"],
            hashed_password=hash_password(user_data["password"]),
            first_name=user_data["first_name"],
            last_name=user_data["last_name"],
            is_superuser=user_data["is_superuser"],
            is_active=True,
            status="active",
            can_login=True,
        )
        await user.insert()

        # Assign role using proper Beanie Links
        role = roles_map[user_data["role"]]
        membership = UserRoleMembership(
            user=user,  # Beanie Link
            role=role,  # Beanie Link
            status="active",
            assigned_at=datetime.now(UTC),
        )
        await membership.insert()

    print(f"   Created {len(users_data)} test users with role assignments\n")

    # Print credentials
    print("=" * 60)
    print("✅ Test Environment Reset Complete!")
    print("=" * 60)
    print("\n📋 Test User Credentials:\n")

    for user_data in users_data:
        role_display = roles_map[user_data["role"]].display_name
        print(f"   {user_data['first_name']} {user_data['last_name']} ({role_display})")
        print(f"   Email:    {user_data['email']}")
        print(f"   Password: {user_data['password']}")
        print()

    print("🌐 Application URLs:")
    print(f"   Backend:  http://localhost:8003")
    print(f"   API Docs: http://localhost:8003/docs")
    print(f"   Admin UI: http://localhost:3000")
    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(reset_database())
