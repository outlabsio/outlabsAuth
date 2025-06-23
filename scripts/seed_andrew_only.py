#!/usr/bin/env python3
"""
Minimal Super Admin Seeding Script for Andrew (system@outlabs.io)

This script creates only the essential super admin user without complex dependencies.
It's designed to be run in production environments safely.

Usage:
    python seed_andrew_only.py

Environment Variables:
    DATABASE_URL: MongoDB connection string (default: mongodb://localhost:27017)
    MONGO_DATABASE: Database name (default: outlabsAuth)
    SUPER_ADMIN_PASSWORD: Optional password (if not set, generates secure password)
"""

import asyncio
import os
import sys
import secrets
import string
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
import bcrypt

# Add the project root to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.models.user_model import UserModel, UserStatus
from api.models.role_model import RoleModel
from api.models.permission_model import PermissionModel
from api.models.client_account_model import ClientAccountModel
from api.models.refresh_token_model import RefreshTokenModel
from api.models.password_reset_token_model import PasswordResetTokenModel
from api.models.group_model import GroupModel

# Configuration
MONGO_URL = os.getenv("DATABASE_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGO_DATABASE", "outlabsAuth")
SUPER_ADMIN_EMAIL = "system@outlabs.io"
SUPER_ADMIN_PASSWORD = os.getenv("SUPER_ADMIN_PASSWORD")

def generate_secure_password(length=20):
    """Generate a cryptographically secure password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()_+-="
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

async def initialize_database(client):
    """Initialize Beanie with the database."""
    db = client[DB_NAME]

    await init_beanie(
        database=db,
        document_models=[
            UserModel,
            RoleModel,
            PermissionModel,
            ClientAccountModel,
            RefreshTokenModel,
            PasswordResetTokenModel,
            GroupModel,
        ]
    )

    # Rebuild models for circular references
    namespace = {
        'UserModel': UserModel,
        'ClientAccountModel': ClientAccountModel,
        'RefreshTokenModel': RefreshTokenModel,
        'PasswordResetTokenModel': PasswordResetTokenModel,
        'GroupModel': GroupModel,
    }
    for model in [UserModel, ClientAccountModel, RefreshTokenModel, PasswordResetTokenModel, GroupModel]:
        model.model_rebuild(_types_namespace=namespace)

    return db

async def create_essential_permissions():
    """Create essential permissions if they don't exist."""
    permissions_data = [
        ("user:create", "Create users"),
        ("user:read", "Read user information"),
        ("user:update", "Update users"),
        ("user:delete", "Delete users"),
        ("user:create_sub", "Create sub-users"),
        ("user:bulk_create", "Bulk create users"),
        ("role:create", "Create roles"),
        ("role:read", "Read roles"),
        ("role:update", "Update roles"),
        ("role:delete", "Delete roles"),
        ("permission:create", "Create permissions"),
        ("permission:read", "Read permissions"),
        ("client_account:create", "Create client accounts"),
        ("client_account:read", "Read client accounts"),
        ("client_account:update", "Update client accounts"),
        ("client_account:delete", "Delete client accounts"),
        ("group:create", "Create groups"),
        ("group:read", "Read groups"),
        ("group:update", "Update groups"),
        ("group:delete", "Delete groups"),
        ("group:manage_members", "Manage group members"),
    ]

    created_permissions = []
    for perm_id, description in permissions_data:
        existing = await PermissionModel.find_one(PermissionModel.id == perm_id)
        if not existing:
            permission = PermissionModel(
                id=perm_id,
                description=description,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            await permission.save()
            created_permissions.append(perm_id)

    return created_permissions

async def create_platform_admin_role():
    """Create platform admin role with all permissions."""
    role_id = "platform_admin"

    # Get all permission IDs
    all_permissions = await PermissionModel.find_all().to_list()
    permission_ids = [perm.id for perm in all_permissions]

    existing_role = await RoleModel.find_one(RoleModel.id == role_id)
    if not existing_role:
        role = RoleModel(
            id=role_id,
            name="Platform Administrator",
            description="Super admin role with all system permissions",
            permissions=permission_ids,
            is_assignable_by_main_client=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        await role.save()
        return True, role
    else:
        # Update existing role to ensure it has all permissions
        existing_role.permissions = permission_ids
        existing_role.updated_at = datetime.utcnow()
        await existing_role.save()
        return False, existing_role

async def create_system_client_account():
    """Create system client account for Andrew."""
    account_name = "Outlabs System"

    existing_account = await ClientAccountModel.find_one(ClientAccountModel.name == account_name)
    if not existing_account:
        account = ClientAccountModel(
            name=account_name,
            description="System-level client account for Outlabs platform administration",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        await account.save()
        return True, account
    else:
        return False, existing_account

async def create_super_admin_user(client_account_id, password):
    """Create or update Andrew's super admin account."""
    existing_user = await UserModel.find_one(UserModel.email == SUPER_ADMIN_EMAIL)

    if existing_user:
        # Update existing user
        existing_user.first_name = "Andrew"
        existing_user.last_name = "System"
        existing_user.is_main_client = True
        existing_user.status = UserStatus.ACTIVE
        existing_user.updated_at = datetime.utcnow()

        # Ensure platform_admin role is assigned
        if "platform_admin" not in existing_user.roles:
            existing_user.roles.append("platform_admin")

        # Update client account reference
        existing_user.client_account = client_account_id

        await existing_user.save()
        return False, existing_user

    else:
        # Create new user
        user = UserModel(
            email=SUPER_ADMIN_EMAIL,
            password_hash=hash_password(password),
            first_name="Andrew",
            last_name="System",
            is_main_client=True,
            roles=["platform_admin"],
            groups=[],
            status=UserStatus.ACTIVE,
            client_account=client_account_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            last_login_at=None,
            locale="en"
        )
        await user.save()
        return True, user

async def main():
    """Main seeding function."""
    print("🚀 Starting Outlabs Super Admin Seeding")
    print("=" * 50)
    print(f"Database: {DB_NAME}")
    print(f"Email: {SUPER_ADMIN_EMAIL}")
    print(f"Name: Andrew System")
    print("=" * 50)

    # Generate or use provided password
    if SUPER_ADMIN_PASSWORD:
        password = SUPER_ADMIN_PASSWORD
        password_source = "environment variable"
    else:
        password = generate_secure_password()
        password_source = "auto-generated"

    client = AsyncIOMotorClient(MONGO_URL)

    try:
        # Test connection
        await client.admin.command('ismaster')
        print("✅ Connected to MongoDB")

        # Initialize database
        db = await initialize_database(client)
        print("✅ Database initialized")

        # Create permissions
        print("📋 Creating essential permissions...")
        created_perms = await create_essential_permissions()
        if created_perms:
            print(f"   Created {len(created_perms)} permissions")
        else:
            print("   All permissions already exist")

        # Create platform admin role
        print("👑 Creating platform admin role...")
        role_created, role = await create_platform_admin_role()
        if role_created:
            print("   Platform admin role created")
        else:
            print("   Platform admin role updated")

        # Create system client account
        print("🏢 Creating system client account...")
        account_created, client_account = await create_system_client_account()
        if account_created:
            print(f"   Created client account: {client_account.name}")
        else:
            print(f"   Using existing client account: {client_account.name}")

        # Create super admin user
        print("👨‍💼 Creating super admin user...")
        user_created, user = await create_super_admin_user(client_account.id, password)
        if user_created:
            print("   Super admin user created")
        else:
            print("   Super admin user updated")

        # Success summary
        print("\n" + "🎉 SEEDING COMPLETED SUCCESSFULLY! 🎉".center(50))
        print("=" * 50)
        print(f"📧 Email: {user.email}")
        print(f"👤 Name: {user.first_name} {user.last_name}")
        print(f"🆔 User ID: {user.id}")
        print(f"🏢 Client Account: {client_account.name}")
        print(f"🔑 Password ({password_source}):")
        print(f"   {password}")
        print("=" * 50)

        if not SUPER_ADMIN_PASSWORD:
            print("⚠️  IMPORTANT: Save this password securely!")
            print("⚠️  It will not be displayed again.")

        print("✅ Andrew can now login to the system")

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        raise
    finally:
        client.close()

if __name__ == "__main__":
    try:
        print("Press Ctrl+C within 3 seconds to cancel...")
        import time
        for i in range(3, 0, -1):
            print(f"Starting in {i}...")
            time.sleep(1)

        asyncio.run(main())

    except KeyboardInterrupt:
        print("\n❌ Cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Fatal error: {str(e)}")
        sys.exit(1)
