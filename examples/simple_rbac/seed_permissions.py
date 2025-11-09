"""
Seed Permission Models for SimpleRBAC Example

Creates PermissionModel documents for all permissions used in the blog application.
These are the permission metadata/definitions, separate from the permission strings in roles.
"""

import asyncio
import os
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from outlabs_auth.models.permission import PermissionModel
from outlabs_auth.models.role import RoleModel
from outlabs_auth.models.user import UserModel
from outlabs_auth.models.user_role_membership import UserRoleMembership
from outlabs_auth.models.token import RefreshTokenModel

# Configuration
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27018")
DATABASE_NAME = os.getenv("DATABASE_NAME", "blog_simple_rbac")

# Permission definitions
PERMISSIONS = [
    # Blog post permissions
    {
        "name": "post:create",
        "display_name": "Create Posts",
        "description": "Can create new blog posts",
        "resource": "post",
        "action": "create",
    },
    {
        "name": "post:update",
        "display_name": "Update Any Post",
        "description": "Can update any blog post (admin)",
        "resource": "post",
        "action": "update",
    },
    {
        "name": "post:update_own",
        "display_name": "Update Own Posts",
        "description": "Can update their own blog posts",
        "resource": "post",
        "action": "update_own",
    },
    {
        "name": "post:delete",
        "display_name": "Delete Any Post",
        "description": "Can delete any blog post (admin)",
        "resource": "post",
        "action": "delete",
    },
    {
        "name": "post:delete_own",
        "display_name": "Delete Own Posts",
        "description": "Can delete their own blog posts",
        "resource": "post",
        "action": "delete_own",
    },
    # Comment permissions
    {
        "name": "comment:create",
        "display_name": "Create Comments",
        "description": "Can add comments to blog posts",
        "resource": "comment",
        "action": "create",
    },
    {
        "name": "comment:delete",
        "display_name": "Delete Any Comment",
        "description": "Can delete any comment (admin)",
        "resource": "comment",
        "action": "delete",
    },
    {
        "name": "comment:delete_own",
        "display_name": "Delete Own Comments",
        "description": "Can delete their own comments",
        "resource": "comment",
        "action": "delete_own",
    },
    # User management permissions
    {
        "name": "user:read",
        "display_name": "Read Users",
        "description": "Can view user information",
        "resource": "user",
        "action": "read",
    },
    {
        "name": "user:create",
        "display_name": "Create Users",
        "description": "Can create new user accounts",
        "resource": "user",
        "action": "create",
    },
    {
        "name": "user:update",
        "display_name": "Update Users",
        "description": "Can update user accounts",
        "resource": "user",
        "action": "update",
    },
    {
        "name": "user:delete",
        "display_name": "Delete Users",
        "description": "Can delete user accounts",
        "resource": "user",
        "action": "delete",
    },
    {
        "name": "user:manage",
        "display_name": "Manage Users",
        "description": "Full user management capabilities",
        "resource": "user",
        "action": "manage",
    },
    # Role management permissions
    {
        "name": "role:read",
        "display_name": "Read Roles",
        "description": "Can view role information",
        "resource": "role",
        "action": "read",
    },
    {
        "name": "role:create",
        "display_name": "Create Roles",
        "description": "Can create new roles",
        "resource": "role",
        "action": "create",
    },
    {
        "name": "role:update",
        "display_name": "Update Roles",
        "description": "Can update existing roles",
        "resource": "role",
        "action": "update",
    },
    {
        "name": "role:delete",
        "display_name": "Delete Roles",
        "description": "Can delete roles",
        "resource": "role",
        "action": "delete",
    },
    # Permission management
    {
        "name": "permission:read",
        "display_name": "Read Permissions",
        "description": "Can view permission information",
        "resource": "permission",
        "action": "read",
    },
    {
        "name": "permission:create",
        "display_name": "Create Permissions",
        "description": "Can create new permissions",
        "resource": "permission",
        "action": "create",
    },
    {
        "name": "permission:update",
        "display_name": "Update Permissions",
        "description": "Can update existing permissions",
        "resource": "permission",
        "action": "update",
    },
    {
        "name": "permission:delete",
        "display_name": "Delete Permissions",
        "description": "Can delete permissions",
        "resource": "permission",
        "action": "delete",
    },
]


async def seed_permissions():
    """Create PermissionModel documents for all blog permissions"""
    print("=" * 80)
    print("🌱 SEEDING PERMISSION MODELS")
    print("=" * 80)

    # Connect to MongoDB
    print(f"\n📦 Connecting to MongoDB: {MONGODB_URL}")
    client = AsyncIOMotorClient(MONGODB_URL)
    db = client[DATABASE_NAME]

    # Initialize Beanie
    await init_beanie(
        database=db,
        document_models=[
            UserModel,
            RoleModel,
            PermissionModel,
            UserRoleMembership,
            RefreshTokenModel,
        ],
    )
    print("✅ Database initialized\n")

    # Create permissions
    print(f"📝 Creating {len(PERMISSIONS)} permission definitions...")
    created_count = 0
    skipped_count = 0

    for perm_data in PERMISSIONS:
        # Check if permission already exists
        existing = await PermissionModel.find_one(PermissionModel.name == perm_data["name"])
        
        if existing:
            print(f"  ⏭️  Skipped: {perm_data['name']} (already exists)")
            skipped_count += 1
        else:
            # Create new permission
            permission = PermissionModel(
                name=perm_data["name"],
                display_name=perm_data["display_name"],
                description=perm_data["description"],
                resource=perm_data["resource"],
                action=perm_data["action"],
                is_system=False,  # These are application-specific permissions
                is_active=True,
                tags=["blog", perm_data["resource"]],
            )
            await permission.insert()
            print(f"  ✓ Created: {perm_data['name']} - {perm_data['display_name']}")
            created_count += 1

    # Summary
    print("\n" + "=" * 80)
    print("✅ PERMISSION SEEDING COMPLETE!")
    print("=" * 80)
    print(f"\n📊 Summary:")
    print(f"  • {created_count} permissions created")
    print(f"  • {skipped_count} permissions skipped (already exist)")
    print(f"  • {created_count + skipped_count} total permissions")

    total_in_db = await PermissionModel.find().count()
    print(f"\n📚 Total PermissionModel documents in database: {total_in_db}")

    print("\n🚀 You can now view permissions at:")
    print("   http://localhost:3000/permissions")

    print("\n" + "=" * 80)

    # Close connection
    client.close()


if __name__ == "__main__":
    try:
        asyncio.run(seed_permissions())
    except KeyboardInterrupt:
        print("\n\n❌ Seeding cancelled by user")
    except Exception as e:
        print(f"\n\n❌ Error during seeding: {e}")
        import traceback
        traceback.print_exc()
