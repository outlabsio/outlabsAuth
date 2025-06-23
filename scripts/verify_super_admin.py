#!/usr/bin/env python3
"""
Super Admin Verification Script

This script verifies that the super admin user (Andrew) was created correctly
and has all the necessary permissions and roles.

Usage:
    python verify_super_admin.py
"""

import asyncio
import os
import sys
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

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

async def verify_super_admin():
    """Verify the super admin user exists and is configured correctly."""
    print("🔍 Verifying Super Admin Configuration")
    print("=" * 50)

    issues = []
    warnings = []

    # Check if user exists
    user = await UserModel.find_one(UserModel.email == SUPER_ADMIN_EMAIL)
    if not user:
        issues.append("❌ Super admin user not found")
        return issues, warnings

    print(f"✅ Super admin user found")
    print(f"   Email: {user.email}")
    print(f"   Name: {user.first_name} {user.last_name}")
    print(f"   ID: {user.id}")
    print(f"   Status: {user.status}")

    # Check user details
    if user.first_name != "Andrew":
        warnings.append(f"⚠️  First name is '{user.first_name}', expected 'Andrew'")

    if user.last_name not in ["System", ""]:
        warnings.append(f"⚠️  Last name is '{user.last_name}', expected 'System'")

    if user.status != UserStatus.ACTIVE:
        issues.append(f"❌ User status is '{user.status}', should be 'active'")

    if not user.is_main_client:
        issues.append("❌ User is not marked as main client")

    # Check roles
    print(f"\n📋 User Roles: {user.roles}")
    if "platform_admin" not in user.roles:
        issues.append("❌ User does not have 'platform_admin' role")
    else:
        print("✅ Platform admin role assigned")

    # Check platform_admin role exists and has permissions
    platform_admin_role = await RoleModel.find_one(RoleModel.id == "platform_admin")
    if not platform_admin_role:
        issues.append("❌ Platform admin role not found in database")
    else:
        print(f"✅ Platform admin role found with {len(platform_admin_role.permissions)} permissions")

        # Check if role has essential permissions
        essential_perms = [
            "user:create", "user:read", "user:update", "user:delete",
            "role:create", "role:read", "role:update", "role:delete",
            "permission:create", "permission:read",
            "client_account:create", "client_account:read", "client_account:update", "client_account:delete"
        ]

        missing_perms = []
        for perm in essential_perms:
            if perm not in platform_admin_role.permissions:
                missing_perms.append(perm)

        if missing_perms:
            issues.append(f"❌ Platform admin role missing permissions: {missing_perms}")
        else:
            print("✅ Platform admin role has all essential permissions")

    # Check client account
    if user.client_account:
        try:
            # Handle both Link and direct reference cases
            if hasattr(user.client_account, 'ref'):
                client_account_id = user.client_account.ref.id
            else:
                client_account_id = user.client_account.id if hasattr(user.client_account, 'id') else user.client_account

            client_account = await ClientAccountModel.find_one(ClientAccountModel.id == client_account_id)
            if client_account:
                print(f"✅ Client account found: {client_account.name}")
                print(f"   Account ID: {client_account.id}")
                if client_account.name != "Outlabs System":
                    warnings.append(f"⚠️  Client account name is '{client_account.name}', expected 'Outlabs System'")
            else:
                issues.append("❌ Client account referenced but not found in database")
        except Exception as e:
            issues.append(f"❌ Error checking client account: {str(e)}")
    else:
        issues.append("❌ User has no client account assigned")

    # Check permissions in database
    all_permissions = await PermissionModel.find_all().to_list()
    print(f"\n🔐 Total permissions in database: {len(all_permissions)}")

    if len(all_permissions) < 15:  # Should have at least 15 essential permissions
        warnings.append(f"⚠️  Only {len(all_permissions)} permissions found, may be incomplete")

    # Check password hash exists
    if not user.password_hash:
        issues.append("❌ User has no password hash")
    else:
        print("✅ Password hash exists")

    return issues, warnings

async def test_database_connection():
    """Test database connection."""
    try:
        client = AsyncIOMotorClient(MONGO_URL)
        await client.admin.command('ismaster')
        print("✅ Database connection successful")
        return client
    except Exception as e:
        print(f"❌ Database connection failed: {str(e)}")
        return None

async def main():
    """Main verification function."""
    print("🔍 SUPER ADMIN VERIFICATION")
    print("=" * 50)
    print(f"Database: {DB_NAME}")
    print(f"Email: {SUPER_ADMIN_EMAIL}")
    print("=" * 50)

    # Test database connection
    client = await test_database_connection()
    if not client:
        print("\n❌ Cannot connect to database. Verification failed.")
        return

    try:
        # Initialize database
        await initialize_database(client)
        print("✅ Database initialized")

        # Run verification
        issues, warnings = await verify_super_admin()

        # Print results
        print("\n" + "=" * 50)
        print("📊 VERIFICATION RESULTS")
        print("=" * 50)

        if issues:
            print("❌ CRITICAL ISSUES FOUND:")
            for issue in issues:
                print(f"   {issue}")

        if warnings:
            print("\n⚠️  WARNINGS:")
            for warning in warnings:
                print(f"   {warning}")

        if not issues and not warnings:
            print("🎉 ALL CHECKS PASSED!")
            print("✅ Super admin is correctly configured")
        elif not issues:
            print("✅ VERIFICATION SUCCESSFUL (with warnings)")
            print("   Super admin is functional but has minor issues")
        else:
            print("❌ VERIFICATION FAILED")
            print("   Critical issues must be resolved")

        # Provide recommendations
        if issues or warnings:
            print("\n💡 RECOMMENDATIONS:")
            if issues:
                print("   1. Re-run the seeding script to fix critical issues")
                print("   2. Check database permissions and connectivity")
            if warnings:
                print("   3. Review and update user details if needed")
                print("   4. Consider running: python scripts/seed_super_admin.py")

        print("\n📋 NEXT STEPS:")
        print("   1. Test login with the super admin credentials")
        print("   2. Verify API access with generated tokens")
        print("   3. Check that all endpoints are accessible")

    except Exception as e:
        print(f"\n💥 Verification error: {str(e)}")
        print("   This might indicate incomplete setup or database issues")
    finally:
        client.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n❌ Verification cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Fatal error: {str(e)}")
        sys.exit(1)
