import asyncio
import os
import sys
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
import secrets
import string

# Add the project root to the Python path to allow importing from 'api'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.services.user_service import user_service
from api.services.role_service import role_service
from api.services.permission_service import permission_service
from api.services.client_account_service import client_account_service
from api.schemas.user_schema import UserCreateSchema
from api.schemas.role_schema import RoleCreateSchema
from api.schemas.permission_schema import PermissionCreateSchema
from api.schemas.client_account_schema import ClientAccountCreateSchema

# Import all document models for Beanie initialization
from api.models.user_model import UserModel
from api.models.role_model import RoleModel
from api.models.permission_model import PermissionModel
from api.models.client_account_model import ClientAccountModel
from api.models.refresh_token_model import RefreshTokenModel
from api.models.password_reset_token_model import PasswordResetTokenModel
from api.models.group_model import GroupModel

# --- Configuration ---
MONGO_URL = os.getenv("DATABASE_URL", "mongodb://localhost:27017")
MAIN_DB_NAME = os.getenv("MONGO_DATABASE", "outlabsAuth")

# Super Admin Details
SUPER_ADMIN_EMAIL = "system@outlabs.io"
SUPER_ADMIN_FIRST_NAME = "Outlabs"
SUPER_ADMIN_LAST_NAME = "System"

# --- Essential Data Definitions ---
ESSENTIAL_PERMISSIONS = [
    PermissionCreateSchema(_id="user:create", description="Allows creating a single user."),
    PermissionCreateSchema(_id="user:read", description="Allows reading user information."),
    PermissionCreateSchema(_id="user:update", description="Allows updating a user."),
    PermissionCreateSchema(_id="user:delete", description="Allows deleting a user."),
    PermissionCreateSchema(_id="user:create_sub", description="Allows a main client to create a sub-user."),
    PermissionCreateSchema(_id="user:bulk_create", description="Allows bulk creation of users."),
    PermissionCreateSchema(_id="role:create", description="Allows creating a role."),
    PermissionCreateSchema(_id="role:read", description="Allows reading role information."),
    PermissionCreateSchema(_id="role:update", description="Allows updating a role."),
    PermissionCreateSchema(_id="role:delete", description="Allows deleting a role."),
    PermissionCreateSchema(_id="permission:create", description="Allows creating a permission."),
    PermissionCreateSchema(_id="permission:read", description="Allows reading permission information."),
    PermissionCreateSchema(_id="client_account:create", description="Allows creating a client account."),
    PermissionCreateSchema(_id="client_account:read", description="Allows reading client account information."),
    PermissionCreateSchema(_id="client_account:update", description="Allows updating a client account."),
    PermissionCreateSchema(_id="client_account:delete", description="Allows deleting a client account."),
    # New platform-scoped permissions for hierarchical multi-platform tenancy
    PermissionCreateSchema(_id="client_account:create_sub", description="Allows creating sub-clients within platform scope."),
    PermissionCreateSchema(_id="client_account:read_platform", description="Allows reading all clients within platform scope."),
    PermissionCreateSchema(_id="client_account:read_created", description="Allows reading only clients you created."),
    PermissionCreateSchema(_id="group:create", description="Allows creating a group."),
    PermissionCreateSchema(_id="group:read", description="Allows reading group information."),
    PermissionCreateSchema(_id="group:update", description="Allows updating a group."),
    PermissionCreateSchema(_id="group:delete", description="Allows deleting a group."),
    PermissionCreateSchema(_id="group:manage_members", description="Allows adding/removing members from groups."),
]

PLATFORM_ADMIN_ROLE = RoleCreateSchema(
    _id="platform_admin",
    name="Platform Administrator",
    description="Grants all permissions in the system.",
    permissions=[p.id for p in ESSENTIAL_PERMISSIONS]
)

# Outlabs System Client Account
OUTLABS_CLIENT_ACCOUNT = ClientAccountCreateSchema(
    name="Outlabs System",
    description="System-level client account for Outlabs platform administration"
)


def generate_secure_password(length=16):
    """
    Generate a secure random password.
    """
    characters = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(characters) for _ in range(length))


async def initialize_beanie(db):
    """
    Initialize Beanie ODM with all document models.
    """
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

    # Rebuild models to resolve circular references
    namespace = {
        'UserModel': UserModel,
        'ClientAccountModel': ClientAccountModel,
        'RefreshTokenModel': RefreshTokenModel,
        'PasswordResetTokenModel': PasswordResetTokenModel,
        'GroupModel': GroupModel,
    }
    UserModel.model_rebuild(_types_namespace=namespace)
    ClientAccountModel.model_rebuild(_types_namespace=namespace)
    RefreshTokenModel.model_rebuild(_types_namespace=namespace)
    PasswordResetTokenModel.model_rebuild(_types_namespace=namespace)
    GroupModel.model_rebuild(_types_namespace=namespace)


async def ensure_permissions_exist():
    """
    Ensure all essential permissions exist in the database.
    """
    print("Ensuring essential permissions exist...")
    created_count = 0

    for perm_data in ESSENTIAL_PERMISSIONS:
        existing_perm = await permission_service.get_permission_by_id(perm_data.id)
        if not existing_perm:
            await permission_service.create_permission(perm_data)
            created_count += 1
            print(f"  ✓ Created permission: {perm_data.id}")
        else:
            print(f"  - Permission already exists: {perm_data.id}")

    print(f"Permissions check complete. Created {created_count} new permissions.")
    return created_count


async def ensure_platform_admin_role_exists():
    """
    Ensure the platform_admin role exists with all permissions.
    """
    print("Ensuring platform_admin role exists...")

    existing_role = await role_service.get_role_by_id("platform_admin")
    if not existing_role:
        await role_service.create_role(PLATFORM_ADMIN_ROLE)
        print("  ✓ Created platform_admin role")
        return True
    else:
        # Update existing role to ensure it has all permissions
        await role_service.update_role("platform_admin", PLATFORM_ADMIN_ROLE)
        print("  ✓ Updated platform_admin role with all permissions")
        return False


async def ensure_outlabs_client_account_exists():
    """
    Ensure the Outlabs system client account exists.
    """
    print("Ensuring Outlabs system client account exists...")

    # Check if an account with this name already exists
    existing_accounts = await client_account_service.get_all_client_accounts()
    outlabs_account = None

    for account in existing_accounts:
        if account.name == OUTLABS_CLIENT_ACCOUNT.name:
            outlabs_account = account
            break

    if not outlabs_account:
        outlabs_account = await client_account_service.create_client_account(OUTLABS_CLIENT_ACCOUNT)
        print(f"  ✓ Created Outlabs client account with ID: {outlabs_account.id}")
        return outlabs_account, True
    else:
        print(f"  - Outlabs client account already exists with ID: {outlabs_account.id}")
        return outlabs_account, False


async def create_or_update_super_admin(client_account_id):
    """
    Create or update the super admin user.
    """
    print(f"Creating/updating super admin user: {SUPER_ADMIN_EMAIL}")

    # Check if the user already exists
    existing_user = await user_service.get_user_by_email(SUPER_ADMIN_EMAIL)

    if existing_user:
        print(f"  - Super admin user already exists with ID: {existing_user.id}")

        # Update user to ensure they have the correct role and client account
        if "platform_admin" not in existing_user.roles:
            existing_user.roles.append("platform_admin")

        # Update client account if it's different
        current_client_id = str(existing_user.client_account.ref.id) if hasattr(existing_user.client_account, 'ref') else str(existing_user.client_account.id)
        if current_client_id != str(client_account_id):
            print(f"  ✓ Updating client account association")

        # Ensure is_main_client is True
        existing_user.is_main_client = True
        await existing_user.save()

        print(f"  ✓ Updated super admin user")
        return existing_user, None  # No password generated for existing user

    else:
        # Generate a secure password
        password = generate_secure_password(20)

        # Create new super admin user
        super_admin_data = UserCreateSchema(
            email=SUPER_ADMIN_EMAIL,
            password=password,
            first_name=SUPER_ADMIN_FIRST_NAME,
            last_name=SUPER_ADMIN_LAST_NAME,
            is_main_client=True,
            roles=["platform_admin"],
            client_account_id=str(client_account_id)
        )

        super_admin_user = await user_service.create_user(super_admin_data)
        print(f"  ✓ Created super admin user with ID: {super_admin_user.id}")

        return super_admin_user, password


async def seed_super_admin():
    """
    Main function to seed the super admin user and required data.
    """
    print("=== Outlabs Super Admin Seeding ===")
    print(f"Database: {MAIN_DB_NAME}")
    print(f"Super Admin Email: {SUPER_ADMIN_EMAIL}")
    print(f"Super Admin Name: {SUPER_ADMIN_FIRST_NAME} {SUPER_ADMIN_LAST_NAME}")
    print("=" * 40)

    # Connect to database
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[MAIN_DB_NAME]

    try:
        # Initialize Beanie
        print("Initializing database connection...")
        await initialize_beanie(db)
        print("✓ Database connection established")

        # Step 1: Ensure permissions exist
        await ensure_permissions_exist()

        # Step 2: Ensure platform admin role exists
        await ensure_platform_admin_role_exists()

        # Step 3: Ensure Outlabs client account exists
        client_account, account_created = await ensure_outlabs_client_account_exists()

        # Step 4: Create or update super admin user
        user, password = await create_or_update_super_admin(client_account.id)

        print("\n" + "=" * 40)
        print("🎉 SUPER ADMIN SEEDING COMPLETE 🎉")
        print("=" * 40)
        print(f"Super Admin Email: {user.email}")
        print(f"Super Admin ID: {user.id}")
        print(f"Client Account: {client_account.name}")
        print(f"Client Account ID: {client_account.id}")

        if password:
            print("\n🔐 IMPORTANT - SAVE THIS PASSWORD:")
            print(f"Password: {password}")
            print("\n⚠️  This password will not be shown again!")
            print("⚠️  Make sure to save it in a secure location.")
        else:
            print("\n📝 User already existed - password unchanged")

        print("\n✅ You can now login with these credentials")
        print("=" * 40)

    except Exception as e:
        print(f"\n❌ Error during seeding: {str(e)}")
        raise
    finally:
        client.close()


if __name__ == "__main__":
    print("Starting Super Admin Seeding Process...")
    print("Press Ctrl+C to cancel within 3 seconds...")

    try:
        # Give user a chance to cancel
        import time
        for i in range(3, 0, -1):
            print(f"Starting in {i}...")
            time.sleep(1)

        asyncio.run(seed_super_admin())

    except KeyboardInterrupt:
        print("\n❌ Seeding cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {str(e)}")
        sys.exit(1)
