"""
Debug script to check PropertyHub platform admin permissions and access
"""
import asyncio
import os
import sys
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

# Add the project root to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from api.models.user_model import UserModel
from api.models.role_model import RoleModel
from api.models.permission_model import PermissionModel
from api.models.client_account_model import ClientAccountModel
from api.models.refresh_token_model import RefreshTokenModel
from api.models.password_reset_token_model import PasswordResetTokenModel
from api.models.group_model import GroupModel
from api.services.group_service import group_service

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")

async def debug_platform_admin():
    """Debug PropertyHub platform admin permissions"""
    
    # Connect to test database
    client = AsyncIOMotorClient(MONGO_URL)
    db = client["outlabsAuth_test"]
    
    # Initialize Beanie
    await init_beanie(
        database=db,
        document_models=[
            UserModel, RoleModel, PermissionModel, ClientAccountModel,
            RefreshTokenModel, PasswordResetTokenModel, GroupModel
        ]
    )
    
    try:
        # Get PropertyHub platform admin
        admin_user = await UserModel.find_one(
            UserModel.email == "admin@propertyhub.com", 
            fetch_links=True
        )
        
        if not admin_user:
            print("❌ PropertyHub platform admin not found!")
            return
            
        print("🔍 PropertyHub Platform Admin Analysis:")
        print(f"  📧 Email: {admin_user.email}")
        print(f"  🆔 User ID: {admin_user.id}")
        print(f"  🏢 Client Account: {admin_user.client_account.name if admin_user.client_account else 'None'}")
        print(f"  🏢 Client Account ID: {admin_user.client_account.id if admin_user.client_account else 'None'}")
        print(f"  🏢 Client is_platform_root: {admin_user.client_account.is_platform_root if admin_user.client_account else 'None'}")
        print(f"  👥 Roles: {admin_user.roles}")
        print(f"  🚀 is_platform_staff: {getattr(admin_user, 'is_platform_staff', 'NOT SET')}")
        print(f"  🌐 platform_scope: {getattr(admin_user, 'platform_scope', 'NOT SET')}")
        
        # Check role details
        print("\n🎭 Role Analysis:")
        for role_id in admin_user.roles:
            role = await RoleModel.find_one(RoleModel.id == role_id, fetch_links=True)
            if role:
                print(f"  📝 Role: {role.name} ({role.display_name})")
                print(f"      Scope: {role.scope}")
                print(f"      Scope ID: {role.scope_id}")
                print(f"      Permissions: {role.permissions}")
                
                # Check actual permission details
                print(f"      🔍 Permission Details:")
                for perm_id in role.permissions:
                    perm = await PermissionModel.find_one(PermissionModel.id == perm_id)
                    if perm:
                        print(f"        ✅ {perm.name} (scope: {perm.scope}, scope_id: {perm.scope_id})")
                    else:
                        print(f"        ❌ Permission ID {perm_id} not found!")
        
        # Check effective permissions
        print("\n🔐 Effective Permissions Analysis:")
        try:
            effective_permissions = await group_service.get_user_effective_permissions(admin_user.id)
            print(f"  Total effective permissions: {len(effective_permissions)}")
            for perm in sorted(effective_permissions):
                print(f"    ✅ {perm}")
        except Exception as e:
            print(f"  ❌ Error getting effective permissions: {e}")
        
        # Check all client accounts
        print("\n🏢 All Client Accounts:")
        all_accounts = await ClientAccountModel.find().to_list()
        for account in all_accounts:
            print(f"  🏢 {account.name} (ID: {account.id})")
            print(f"      Platform root: {account.is_platform_root}")
            print(f"      Created by: {account.created_by_client_id}")
            
        # Check platform permissions
        print("\n🌐 Platform Permissions:")
        platform_perms = await PermissionModel.find(PermissionModel.scope == "platform").to_list()
        for perm in platform_perms:
            print(f"  🔑 {perm.name} (scope_id: {perm.scope_id})")
        
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(debug_platform_admin()) 