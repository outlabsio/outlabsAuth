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
from datetime import datetime, UTC
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext
from bson import ObjectId

# Configuration
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27018")
DATABASE_NAME = os.getenv("DATABASE_NAME", "blog_simple_rbac")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def reset_database():
    """Reset database to clean test state."""
    print("🔄 Connecting to MongoDB...")
    client = AsyncIOMotorClient(MONGODB_URL)
    db = client[DATABASE_NAME]

    # Drop existing test data
    print("🗑️  Dropping existing test data...")
    await db.users.delete_many({})
    await db.roles.delete_many({})
    await db.user_role_memberships.delete_many({})
    await db.permissions.delete_many({})

    print("✅ Test data cleared\n")

    # Create permissions
    print("📝 Creating permissions...")
    permissions_data = [
        # User permissions
        {"name": "user:read", "display_name": "User Read", "resource": "user", "action": "read"},
        {"name": "user:create", "display_name": "User Create", "resource": "user", "action": "create"},
        {"name": "user:update", "display_name": "User Update", "resource": "user", "action": "update"},
        {"name": "user:delete", "display_name": "User Delete", "resource": "user", "action": "delete"},
        {"name": "user:manage", "display_name": "User Manage", "resource": "user", "action": "manage"},

        # Role permissions
        {"name": "role:read", "display_name": "Role Read", "resource": "role", "action": "read"},
        {"name": "role:create", "display_name": "Role Create", "resource": "role", "action": "create"},
        {"name": "role:update", "display_name": "Role Update", "resource": "role", "action": "update"},
        {"name": "role:delete", "display_name": "Role Delete", "resource": "role", "action": "delete"},

        # Permission permissions
        {"name": "permission:read", "display_name": "Permission Read", "resource": "permission", "action": "read"},
        {"name": "permission:create", "display_name": "Permission Create", "resource": "permission", "action": "create"},
        {"name": "permission:update", "display_name": "Permission Update", "resource": "permission", "action": "update"},

        # API Key permissions
        {"name": "apikey:read", "display_name": "API Key Read", "resource": "apikey", "action": "read"},
        {"name": "apikey:create", "display_name": "API Key Create", "resource": "apikey", "action": "create"},
        {"name": "apikey:revoke", "display_name": "API Key Revoke", "resource": "apikey", "action": "revoke"},

        # Blog-specific permissions
        {"name": "post:read", "display_name": "Post Read", "resource": "post", "action": "read"},
        {"name": "post:create", "display_name": "Post Create", "resource": "post", "action": "create"},
        {"name": "post:update", "display_name": "Post Update", "resource": "post", "action": "update"},
        {"name": "post:delete", "display_name": "Post Delete", "resource": "post", "action": "delete"},
        {"name": "comment:create", "display_name": "Comment Create", "resource": "comment", "action": "create"},
        {"name": "comment:delete", "display_name": "Comment Delete", "resource": "comment", "action": "delete"},
    ]

    for perm in permissions_data:
        perm["_id"] = ObjectId()
        perm["description"] = f"Permission to {perm['action']} {perm['resource']}"
        perm["is_system"] = True
        perm["is_active"] = True
        perm["created_at"] = datetime.now(UTC)
        perm["updated_at"] = datetime.now(UTC)

    await db.permissions.insert_many(permissions_data)
    print(f"   Created {len(permissions_data)} permissions\n")

    # Create roles
    print("🎭 Creating roles...")
    roles = [
        {
            "name": "reader",
            "display_name": "Reader",
            "description": "Read-only access to blog posts",
            "permissions": ["post:read"],
            "is_system_role": True,
            "is_global": True,
        },
        {
            "name": "writer",
            "display_name": "Writer",
            "description": "Can create and manage own blog posts",
            "permissions": ["post:read", "post:create", "post:update", "comment:create"],
            "is_system_role": True,
            "is_global": True,
        },
        {
            "name": "editor",
            "display_name": "Editor",
            "description": "Can manage all blog content",
            "permissions": [
                "post:read", "post:create", "post:update", "post:delete",
                "comment:create", "comment:delete"
            ],
            "is_system_role": True,
            "is_global": True,
        },
        {
            "name": "admin",
            "display_name": "Administrator",
            "description": "Full system access",
            "permissions": [
                "post:create", "post:update", "post:delete",
                "comment:create", "comment:delete",
                "user:read", "user:create", "user:update", "user:delete", "user:manage",
                "role:read", "role:create", "role:update", "role:delete",
                "permission:read", "permission:create", "permission:update", "permission:delete",
            ],
            "is_system_role": True,
            "is_global": True,
        },
    ]

    role_ids = {}
    for role in roles:
        role["_id"] = ObjectId()
        role["created_at"] = datetime.now(UTC)
        role["updated_at"] = datetime.now(UTC)
        role_ids[role["name"]] = role["_id"]

    await db.roles.insert_many(roles)
    print(f"   Created {len(roles)} roles\n")

    # Create test users
    print("👥 Creating test users...")
    users = [
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

    user_records = []
    memberships = []

    for user_data in users:
        user = {
            "_id": ObjectId(),
            "email": user_data["email"],
            "hashed_password": pwd_context.hash(user_data["password"]),
            "first_name": user_data["first_name"],
            "last_name": user_data["last_name"],
            "is_superuser": user_data["is_superuser"],
            "is_active": True,
            "status": "active",
            "can_login": True,
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }
        user_records.append(user)

        # Create role membership
        membership = {
            "_id": ObjectId(),
            "user_id": user["_id"],
            "role_id": role_ids[user_data["role"]],
            "status": "active",
            "can_grant": True,
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }
        memberships.append(membership)

    await db.users.insert_many(user_records)
    await db.user_role_memberships.insert_many(memberships)
    print(f"   Created {len(user_records)} test users\n")

    # Print credentials
    print("=" * 60)
    print("✅ Test Environment Reset Complete!")
    print("=" * 60)
    print("\n📋 Test User Credentials:\n")

    for user_data in users:
        role_display = next(r["display_name"] for r in roles if r["name"] == user_data["role"])
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
