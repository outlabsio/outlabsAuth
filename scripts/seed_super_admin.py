import asyncio
import os
import sys
import argparse
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
DEFAULT_DB_NAME = os.getenv("MONGO_DATABASE", "outlabsAuth")

# Fixed password for all admin users
ADMIN_PASSWORD = "Asd123$$$"

# Super Admin Details
SUPER_ADMIN_EMAIL = "system@outlabs.io"
SUPER_ADMIN_FIRST_NAME = "Outlabs"
SUPER_ADMIN_LAST_NAME = "System"

# Default Client Organization Details
DEFAULT_ORG_NAME = "Qdarte"
DEFAULT_ORG_DESCRIPTION = "Default client organization"
DEFAULT_CLIENT_ADMIN_EMAIL = "system@qdarte.com"
DEFAULT_CLIENT_ADMIN_FIRST_NAME = "System"
DEFAULT_CLIENT_ADMIN_LAST_NAME = "Admin"

# --- Essential Data Definitions ---
ESSENTIAL_PERMISSIONS = [
    # System-level permissions (global)
    PermissionCreateSchema(name="user:create", display_name="Create Users", description="Allows creating a single user.", scope="system"),
    PermissionCreateSchema(name="user:read", display_name="Read Users", description="Allows reading user information.", scope="system"),
    PermissionCreateSchema(name="user:update", display_name="Update Users", description="Allows updating a user.", scope="system"),
    PermissionCreateSchema(name="user:delete", display_name="Delete Users", description="Allows deleting a user.", scope="system"),
    PermissionCreateSchema(name="user:add_member", display_name="Add Team Members", description="Allows adding a new user to one's own client account.", scope="system"),
    PermissionCreateSchema(name="user:bulk_create", display_name="Bulk Create Users", description="Allows bulk creation of users.", scope="system"),
    PermissionCreateSchema(name="role:create", display_name="Create Roles", description="Allows creating a role.", scope="system"),
    PermissionCreateSchema(name="role:read", display_name="Read Roles", description="Allows reading role information.", scope="system"),
    PermissionCreateSchema(name="role:update", display_name="Update Roles", description="Allows updating a role.", scope="system"),
    PermissionCreateSchema(name="role:delete", display_name="Delete Roles", description="Allows deleting a role.", scope="system"),
    PermissionCreateSchema(name="permission:create", display_name="Create Permissions", description="Allows creating a permission.", scope="system"),
    PermissionCreateSchema(name="permission:read", display_name="Read Permissions", description="Allows reading permission information.", scope="system"),
    PermissionCreateSchema(name="client_account:create", display_name="Create Client Accounts", description="Allows creating a client account.", scope="system"),
    PermissionCreateSchema(name="client_account:read", display_name="Read Client Accounts", description="Allows reading client account information.", scope="system"),
    PermissionCreateSchema(name="client_account:update", display_name="Update Client Accounts", description="Allows updating a client account.", scope="system"),
    PermissionCreateSchema(name="client_account:delete", display_name="Delete Client Accounts", description="Allows deleting a client account.", scope="system"),
    # Platform-scoped permissions for hierarchical multi-platform tenancy
    PermissionCreateSchema(name="client_account:create_sub", display_name="Create Sub-Clients", description="Allows creating sub-clients within platform scope.", scope="platform"),
    PermissionCreateSchema(name="client_account:read_platform", display_name="Read Platform Clients", description="Allows reading all clients within platform scope.", scope="platform"),
    PermissionCreateSchema(name="client_account:read_created", display_name="Read Created Clients", description="Allows reading only clients you created.", scope="platform"),
    PermissionCreateSchema(name="group:create", display_name="Create Groups", description="Allows creating a group.", scope="system"),
    PermissionCreateSchema(name="group:read", display_name="Read Groups", description="Allows reading group information.", scope="system"),
    PermissionCreateSchema(name="group:update", display_name="Update Groups", description="Allows updating a group.", scope="system"),
    PermissionCreateSchema(name="group:delete", display_name="Delete Groups", description="Allows deleting a group.", scope="system"),
    PermissionCreateSchema(name="group:manage_members", display_name="Manage Group Members", description="Allows adding/removing members from groups.", scope="system"),
]

def get_super_admin_role():
    """Function to get super admin role with actual permission IDs"""
    return RoleCreateSchema(
        name="super_admin",
        display_name="Super Administrator",
        description="Grants complete system-wide access.",
        permissions=[],  # Will be populated with actual IDs
        scope="system"
    )

# Client Admin Role - for managing users within a client organization
CLIENT_ADMIN_ROLE = RoleCreateSchema(
    name="client_admin",
    display_name="Client Administrator",
    description="Administrative access for managing users, groups, and roles within a client organization",
    permissions=[
        "user:create", "user:read", "user:update", "user:delete", "user:add_member",
        "group:create", "group:read", "group:update", "group:delete", "group:manage_members",
        "role:read", "permission:read", "client_account:read"
    ],
    scope="client",
    is_assignable_by_main_client=True
)

# Platform Admin Role - for platform-level administration
PLATFORM_ADMIN_ROLE = RoleCreateSchema(
    name="platform_admin",
    display_name="Platform Administrator", 
    description="Administrative access for managing platform-level operations and multiple client accounts",
    permissions=[
        "user:create", "user:read", "user:update", "user:delete", "user:add_member", "user:bulk_create",
        "role:create", "role:read", "role:update", "role:delete",
        "permission:create", "permission:read",
        "client_account:create", "client_account:read", "client_account:update", "client_account:delete",
        "client_account:create_sub", "client_account:read_platform", "client_account:read_created",
        "group:create", "group:read", "group:update", "group:delete", "group:manage_members"
    ],
    scope="platform",
    is_assignable_by_main_client=False
)

# Basic User Role - for standard users with minimal permissions
BASIC_USER_ROLE = RoleCreateSchema(
    name="basic_user",
    display_name="Basic User",
    description="Standard user with basic read permissions",
    permissions=["user:read", "group:read", "client_account:read"],
    scope="system",  # Changed to system so it's available everywhere
    is_assignable_by_main_client=True
)

# Essential roles are now created dynamically in the seeding function

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
        # Check if permission exists by querying directly
        existing_perm = await PermissionModel.find_one(
            PermissionModel.name == perm_data.name,
            PermissionModel.scope == perm_data.scope,
            PermissionModel.scope_id == None  # System permissions have null scope_id
        )
        if not existing_perm:
            try:
                await permission_service.create_permission(
                    perm_data,
                    current_user_id="system_seed",
                    current_client_id=None
                )
                created_count += 1
                print(f"  ✓ Created permission: {perm_data.name} (scope: {perm_data.scope})")
            except Exception as e:
                print(f"  ❌ Failed to create permission {perm_data.name}: {e}")
        else:
            print(f"  - Permission already exists: {perm_data.name} (scope: {perm_data.scope})")

    print(f"Permissions check complete. Created {created_count} new permissions.")
    return created_count


async def ensure_essential_roles_exist():
    """
    Ensure all essential roles exist in the database.
    """
    print("Ensuring essential roles exist...")
    created_count = 0
    updated_count = 0

    # Get actual permission IDs from database
    actual_permission_ids = []
    for perm_data in ESSENTIAL_PERMISSIONS:
        perm = await PermissionModel.find_one(
            PermissionModel.name == perm_data.name,
            PermissionModel.scope == perm_data.scope,
            PermissionModel.scope_id == None
        )
        if perm:
            actual_permission_ids.append(str(perm.id))

    # Create super admin role with actual permission IDs
    super_admin_role = get_super_admin_role()
    super_admin_role.permissions = actual_permission_ids

    # Basic permissions for other roles
    basic_permission_names = ["user:read", "group:read", "client_account:read"]
    basic_permission_ids = []
    for perm_name in basic_permission_names:
        perm = await PermissionModel.find_one(
            PermissionModel.name == perm_name,
            PermissionModel.scope == "system",
            PermissionModel.scope_id == None
        )
        if perm:
            basic_permission_ids.append(str(perm.id))

    # Get CLIENT_ADMIN_ROLE permission IDs
    client_admin_permission_names = [
        "user:create", "user:read", "user:update", "user:delete", "user:add_member",
        "group:create", "group:read", "group:update", "group:delete", "group:manage_members",
        "role:read", "permission:read", "client_account:read"
    ]
    client_admin_permission_ids = []
    for perm_name in client_admin_permission_names:
        perm = await PermissionModel.find_one(
            PermissionModel.name == perm_name,
            PermissionModel.scope == "system",
            PermissionModel.scope_id == None
        )
        if perm:
            client_admin_permission_ids.append(str(perm.id))
    
    CLIENT_ADMIN_ROLE.permissions = client_admin_permission_ids

    essential_roles = [super_admin_role, CLIENT_ADMIN_ROLE, PLATFORM_ADMIN_ROLE]
    
    # Update BASIC_USER_ROLE permissions
    BASIC_USER_ROLE.permissions = basic_permission_ids

    essential_roles.append(BASIC_USER_ROLE)

    for role_data in essential_roles:
        # Look up role by name and scope using the model directly
        existing_role = await RoleModel.find_one(
            RoleModel.name == role_data.name,
            RoleModel.scope == role_data.scope
        )
        
        if not existing_role:
            # Create new role using the service with system admin context
            try:
                await role_service.create_role(
                    role_data,
                    current_user_id="system_seed",  # Dummy user ID for seeding
                    current_client_id=None
                )
                created_count += 1
                print(f"  ✓ Created role: {role_data.name}")
            except Exception as e:
                # If service fails, create directly
                role = RoleModel(
                    name=role_data.name,
                    display_name=role_data.display_name,
                    description=role_data.description,
                    permissions=role_data.permissions,
                    scope=role_data.scope,
                    scope_id=None if role_data.scope == "system" else None,
                    is_assignable_by_main_client=role_data.is_assignable_by_main_client,
                    created_by_user_id="system_seed",
                    created_by_client_id=None
                )
                await role.insert()
                created_count += 1
                print(f"  ✓ Created role: {role_data.name}")
        else:
            # Update existing role
            existing_role.display_name = role_data.display_name
            existing_role.description = role_data.description
            existing_role.permissions = role_data.permissions
            existing_role.is_assignable_by_main_client = role_data.is_assignable_by_main_client
            await existing_role.save()
            updated_count += 1
            print(f"  ✓ Updated role: {role_data.name}")

    print(f"Roles check complete. Created {created_count} new roles, updated {updated_count} existing roles.")
    return created_count, updated_count


async def ensure_outlabs_client_account_exists():
    """
    Ensure the Outlabs system client account exists.
    """
    print("Ensuring Outlabs system client account exists...")

    # Check if an account with this name already exists
    existing_accounts = await client_account_service.get_client_accounts()
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
        if "super_admin" not in existing_user.roles:
            existing_user.roles.append("super_admin")

        # Update client account if it's different
        current_client_id = str(existing_user.client_account.ref.id) if hasattr(existing_user.client_account, 'ref') else str(existing_user.client_account.id)
        if current_client_id != str(client_account_id):
            print(f"  ✓ Updating client account association")

        # Ensure is_main_client is True
        existing_user.is_main_client = True
        await existing_user.save()

        print(f"  ✓ Updated super admin user")
        return existing_user, ADMIN_PASSWORD

    else:
        # Use fixed password
        password = ADMIN_PASSWORD

        # Create new super admin user
        super_admin_data = UserCreateSchema(
            email=SUPER_ADMIN_EMAIL,
            password=password,
            first_name=SUPER_ADMIN_FIRST_NAME,
            last_name=SUPER_ADMIN_LAST_NAME,
            is_main_client=True,
            roles=["super_admin"],
            client_account_id=str(client_account_id)
        )

        super_admin_user = await user_service.create_user(super_admin_data)
        print(f"  ✓ Created super admin user with ID: {super_admin_user.id}")

        return super_admin_user, password


async def ensure_default_client_account_exists():
    """
    Ensure the default client account exists.
    """
    print(f"Ensuring default client account exists: {DEFAULT_ORG_NAME}")

    # Check if an account with this name already exists
    existing_accounts = await client_account_service.get_client_accounts()
    default_account = None

    for account in existing_accounts:
        if account.name == DEFAULT_ORG_NAME:
            default_account = account
            break

    if not default_account:
        client_data = ClientAccountCreateSchema(
            name=DEFAULT_ORG_NAME,
            description=DEFAULT_ORG_DESCRIPTION
        )
        default_account = await client_account_service.create_client_account(client_data)
        print(f"  ✓ Created default client account with ID: {default_account.id}")
        return default_account, True
    else:
        print(f"  - Default client account already exists with ID: {default_account.id}")
        return default_account, False


async def create_or_update_default_client_admin(client_account_id):
    """
    Create or update the default client admin user.
    """
    print(f"Creating/updating default client admin user: {DEFAULT_CLIENT_ADMIN_EMAIL}")

    # Check if the user already exists
    existing_user = await user_service.get_user_by_email(DEFAULT_CLIENT_ADMIN_EMAIL)

    if existing_user:
        print(f"  - Client admin user already exists with ID: {existing_user.id}")

        # Update user to ensure they have the correct role and client account
        if "client_admin" not in existing_user.roles:
            existing_user.roles.append("client_admin")

        # Update client account if it's different
        current_client_id = str(existing_user.client_account.ref.id) if hasattr(existing_user.client_account, 'ref') else str(existing_user.client_account.id)
        if current_client_id != str(client_account_id):
            print(f"  ✓ Updating client account association")

        # Ensure is_main_client is True
        existing_user.is_main_client = True
        await existing_user.save()

        print(f"  ✓ Updated client admin user")
        return existing_user, ADMIN_PASSWORD

    else:
        # Create new client admin user
        client_admin_data = UserCreateSchema(
            email=DEFAULT_CLIENT_ADMIN_EMAIL,
            password=ADMIN_PASSWORD,
            first_name=DEFAULT_CLIENT_ADMIN_FIRST_NAME,
            last_name=DEFAULT_CLIENT_ADMIN_LAST_NAME,
            is_main_client=True,  # This makes them the main admin for their org
            roles=["client_admin"],  # Standard client admin role
            client_account_id=str(client_account_id)
        )

        client_admin_user = await user_service.create_user(client_admin_data)
        print(f"  ✓ Created client admin user with ID: {client_admin_user.id}")

        return client_admin_user, ADMIN_PASSWORD


async def seed_complete_system(db_name: str = DEFAULT_DB_NAME):
    """
    Main function to seed the super admin user, default client organization, and all required data.
    
    Args:
        db_name: Name of the database to seed (defaults to main database)
    """
    print("=== Outlabs Complete System Seeding ===")
    print(f"Database: {db_name}")
    print(f"Super Admin Email: {SUPER_ADMIN_EMAIL}")
    print(f"Super Admin Name: {SUPER_ADMIN_FIRST_NAME} {SUPER_ADMIN_LAST_NAME}")
    print(f"Default Org: {DEFAULT_ORG_NAME}")
    print(f"Default Org Admin Email: {DEFAULT_CLIENT_ADMIN_EMAIL}")
    print(f"Fixed Password: {ADMIN_PASSWORD}")
    print("=" * 50)

    # Connect to database
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[db_name]

    try:
        # Initialize Beanie
        print("Initializing database connection...")
        await initialize_beanie(db)
        print("✓ Database connection established")

        # Step 1: Ensure permissions exist
        await ensure_permissions_exist()

        # Step 2: Ensure essential roles exist
        await ensure_essential_roles_exist()

        # Step 3: Ensure Outlabs client account exists
        outlabs_account, outlabs_created = await ensure_outlabs_client_account_exists()

        # Step 4: Create or update super admin user
        super_admin_user, super_admin_password = await create_or_update_super_admin(outlabs_account.id)

        # Step 5: Ensure default client account exists
        default_account, default_created = await ensure_default_client_account_exists()

        # Step 6: Create or update default client admin user
        client_admin_user, client_admin_password = await create_or_update_default_client_admin(default_account.id)

        print("\n" + "=" * 50)
        print("🎉 COMPLETE SYSTEM SEEDING COMPLETE 🎉")
        print("=" * 50)
        
        print("\n📋 SUPER ADMIN DETAILS:")
        print(f"   Email: {super_admin_user.email}")
        print(f"   Password: {super_admin_password}")
        print(f"   ID: {super_admin_user.id}")
        print(f"   Client Account: {outlabs_account.name}")
        print(f"   Client Account ID: {outlabs_account.id}")
        
        print("\n📋 DEFAULT CLIENT ORGANIZATION:")
        print(f"   Organization: {default_account.name}")
        print(f"   Admin Email: {client_admin_user.email}")
        print(f"   Admin Password: {client_admin_password}")
        print(f"   Admin ID: {client_admin_user.id}")
        print(f"   Client Account ID: {default_account.id}")

        print("\n✅ Ready to use! Both accounts can login with password: Asd123$$$")
        print("\nNext steps:")
        print("   1. Super admin can manage the entire platform")
        print("   2. Client admin can manage users within their organization")
        print("   3. Both can create additional users and groups")
        print("=" * 50)

    except Exception as e:
        print(f"\n❌ Error during seeding: {str(e)}")
        raise
    finally:
        client.close()


def main():
    """
    Main entry point with command line argument parsing.
    """
    parser = argparse.ArgumentParser(description="Seed super admin and essential system data.")
    parser.add_argument(
        "--db",
        type=str,
        default=DEFAULT_DB_NAME,
        help=f"The name of the database to seed. Defaults to '{DEFAULT_DB_NAME}'."
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Seed the test database (outlabsAuth_test). Shortcut for --db outlabsAuth_test"
    )
    args = parser.parse_args()

    # Determine target database
    target_db = "outlabsAuth_test" if args.test else args.db
    
    print("Starting Complete System Seeding Process...")
    print("This will create super admin + default client organization")
    print(f"Target database: {target_db}")
    print("Press Ctrl+C to cancel within 3 seconds...")

    try:
        # Give user a chance to cancel
        import time
        for i in range(3, 0, -1):
            print(f"Starting in {i}...")
            time.sleep(1)

        asyncio.run(seed_complete_system(target_db))

    except KeyboardInterrupt:
        print("\n❌ Seeding cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
