"""
Debug script to check PropertyHub platform roles
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

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")

async def debug_roles():
    """Debug PropertyHub platform roles"""
    
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
        print("🎭 All Roles in Database:")
        all_roles = await RoleModel.find().to_list()
        print(f"  Total roles: {len(all_roles)}")
        
        for role in all_roles:
            print(f"\n  📝 Role: {role.name} ({role.display_name})")
            print(f"      ID: {role.id}")
            print(f"      Scope: {role.scope}")
            print(f"      Scope ID: {role.scope_id}")
            print(f"      Permissions: {role.permissions}")
            print(f"      Created by: {role.created_by_user_id}")
            
        print("\n👤 PropertyHub Platform Users:")
        platform_users = await UserModel.find(
            UserModel.email.in_([
                "admin@propertyhub.com", 
                "support@propertyhub.com", 
                "sales@propertyhub.com"
            ]),
            fetch_links=True
        ).to_list()
        
        for user in platform_users:
            print(f"\n  👤 {user.email}")
            print(f"      Roles: {user.roles}")
            print(f"      Client: {user.client_account.name if user.client_account else 'None'}")
            
            # Check if their roles exist
            for role_id in user.roles:
                role = await RoleModel.find_one(RoleModel.id == role_id)
                if role:
                    print(f"      ✅ Role {role_id} exists: {role.name}")
                else:
                    print(f"      ❌ Role {role_id} NOT FOUND!")
                    
        print("\n🔑 All Permissions:")
        all_perms = await PermissionModel.find().to_list()
        system_perms = [p for p in all_perms if p.scope == "system"]
        platform_perms = [p for p in all_perms if p.scope == "platform"]
        
        print(f"  System permissions: {len(system_perms)}")
        print(f"  Platform permissions: {len(platform_perms)}")
        
        for perm in platform_perms:
            print(f"    🔑 {perm.name} (ID: {perm.id}, scope_id: {perm.scope_id})")
            
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(debug_roles()) 