"""
Essential Users Seeding Script for Production/Staging

Purpose:
This script creates the essential three-tier system architecture with the core admin users
needed for production or staging environments. It sets up:

Three-Tier Architecture:
1. System Level - Outlabs (super_admin): System-wide control and administration
2. Platform Level - Qdarte (platform_admin): Platform operations and client management  
3. Client Level - PropertyHub (client_admin): Optional client example

Essential Users Created:
- system@outlabs.io (super_admin) - Complete system access
- admin@qdarte.com (platform_admin) - Platform operations only
- admin@propertyhub.com (client_admin) - Optional with --propertyhub flag

Features:
- Creates essential system and platform permissions
- Sets up proper role hierarchy with distinct roles per tier
- Configurable database targeting (test vs production)
- Optional PropertyHub client creation
- Safe for production use - only creates necessary admin accounts

Usage:
1. Seed test database with essential users:
   python scripts/seed_essential_users.py --test

2. Seed production database with essential users:
   python scripts/seed_essential_users.py --prod

3. Include optional PropertyHub client:
   python scripts/seed_essential_users.py --test --propertyhub

4. Seed custom database:
   python scripts/seed_essential_users.py --db my_database_name

Note:
This script is safe for production use and only creates essential admin accounts.
For comprehensive test data, use scripts/seed_test_environment.py instead.
"""

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

# Qdarte Platform Details (serves as both platform and primary client)
QDARTE_ORG_NAME = "Qdarte"
QDARTE_ORG_DESCRIPTION = "Qdarte platform for real estate management"

# Platform Admin Details (same as Qdarte since Qdarte is the platform)
PLATFORM_ADMIN_EMAIL = "admin@qdarte.com"
PLATFORM_ADMIN_FIRST_NAME = "Qdarte" 
PLATFORM_ADMIN_LAST_NAME = "Admin"

# Optional PropertyHub Client Details (only created with --propertyhub flag)
PROPERTYHUB_CLIENT_EMAIL = "admin@propertyhub.com"
PROPERTYHUB_CLIENT_FIRST_NAME = "PropertyHub"
PROPERTYHUB_CLIENT_LAST_NAME = "Admin"

# Qdarte Platform Account (this is the platform level)
QDARTE_PLATFORM_ACCOUNT = ClientAccountCreateSchema(
    name="Qdarte Platform",
    description="Qdarte platform for real estate management and client onboarding"
)

# Optional PropertyHub Client Account (client of Qdarte platform)
PROPERTYHUB_CLIENT_ACCOUNT = ClientAccountCreateSchema(
    name="PropertyHub Real Estate",
    description="PropertyHub real estate company - client of Qdarte platform"
)

# --- Essential Data Definitions ---
ESSENTIAL_SYSTEM_PERMISSIONS = [
    # === AUTH PLATFORM PROTECTION PERMISSIONS ===
    
    # Self-access permissions (default for all users)
    PermissionCreateSchema(name="user:read_self", display_name="Read Own Profile", description="Read own user profile in auth platform", scope="system"),
    PermissionCreateSchema(name="user:update_self", display_name="Update Own Profile", description="Update own user profile in auth platform", scope="system"),
    PermissionCreateSchema(name="user:change_password", display_name="Change Own Password", description="Change own password", scope="system"),
    PermissionCreateSchema(name="group:read_own", display_name="Read Own Groups", description="View own group memberships in auth platform", scope="system"),
    PermissionCreateSchema(name="client:read_own", display_name="Read Own Client", description="View own client account info in auth platform", scope="system"),
    
    # Own scope creation permissions (default for all users)
    PermissionCreateSchema(name="permission:create_own_scope", display_name="Create Own Scope Permissions", description="Create permissions in own scope", scope="system"),
    PermissionCreateSchema(name="role:create_own_scope", display_name="Create Own Scope Roles", description="Create roles in own scope", scope="system"),
    PermissionCreateSchema(name="group:create_own_scope", display_name="Create Own Scope Groups", description="Create groups in own scope", scope="system"),
    
    # Client-scoped permissions 
    PermissionCreateSchema(name="user:read_client", display_name="Read Client Users", description="Read users in same client (auth platform)", scope="system"),
    PermissionCreateSchema(name="user:manage_client", display_name="Manage Client Users", description="CRUD users in same client (auth platform)", scope="system"),
    PermissionCreateSchema(name="role:read_client", display_name="Read Client Roles", description="Read roles in same client (auth platform)", scope="system"),
    PermissionCreateSchema(name="role:manage_client", display_name="Manage Client Roles", description="CRUD roles in same client (auth platform)", scope="system"),
    PermissionCreateSchema(name="group:read_client", display_name="Read Client Groups", description="Read groups in same client (auth platform)", scope="system"),
    PermissionCreateSchema(name="group:manage_client", display_name="Manage Client Groups", description="CRUD groups in same client (auth platform)", scope="system"),
    PermissionCreateSchema(name="permission:read_client", display_name="Read Client Permissions", description="Read permissions in same client (auth platform)", scope="system"),
    PermissionCreateSchema(name="permission:manage_client", display_name="Manage Client Permissions", description="CRUD permissions in same client (auth platform)", scope="system"),
    
    # Admin-only permissions (replace broad permissions)
    PermissionCreateSchema(name="user:read_all", display_name="Read All Users", description="Read all users in auth platform (admin only)", scope="system"),
    PermissionCreateSchema(name="user:manage_all", display_name="Manage All Users", description="Global user management in auth platform (admin only)", scope="system"),
    PermissionCreateSchema(name="role:read_all", display_name="Read All Roles", description="Read all roles in auth platform (admin only)", scope="system"),
    PermissionCreateSchema(name="role:manage_all", display_name="Manage All Roles", description="Global role management in auth platform (admin only)", scope="system"),
    PermissionCreateSchema(name="group:read_all", display_name="Read All Groups", description="Read all groups in auth platform (admin only)", scope="system"),
    PermissionCreateSchema(name="group:manage_all", display_name="Manage All Groups", description="Global group management in auth platform (admin only)", scope="system"),
    PermissionCreateSchema(name="permission:read_all", display_name="Read All Permissions", description="Read all permissions in auth platform (admin only)", scope="system"),
    PermissionCreateSchema(name="permission:manage_all", display_name="Manage All Permissions", description="Global permission management in auth platform (admin only)", scope="system"),
    
    # Platform-level permissions
    PermissionCreateSchema(name="client:create", display_name="Create Client Accounts", description="Create new client accounts in auth platform", scope="system"),
    PermissionCreateSchema(name="client:read_platform", display_name="Read Platform Clients", description="Read all platform client accounts", scope="system"),
    PermissionCreateSchema(name="client:manage_platform", display_name="Manage Platform Clients", description="Manage clients across platform", scope="system"),
    PermissionCreateSchema(name="support:cross_client", display_name="Cross-Client Support", description="Support across all platform clients in auth platform", scope="system"),
    
    # System-level infrastructure permissions
    PermissionCreateSchema(name="platform:create", display_name="Create Platforms", description="Create new platforms", scope="system"),
    PermissionCreateSchema(name="platform:manage_all", display_name="Manage All Platforms", description="Full platform management in auth platform", scope="system"),
    PermissionCreateSchema(name="system:infrastructure", display_name="System Infrastructure", description="Auth platform infrastructure management", scope="system"),
    PermissionCreateSchema(name="admin:*", display_name="Admin All Access", description="Wildcard auth platform admin access", scope="system"),
    
    # === TRANSITION PERMISSIONS (for roles and tests migration) ===
    # These maintain some existing functionality while transitioning to granular permissions
    PermissionCreateSchema(name="user:add_member", display_name="Add Team Members", description="Add users to client account", scope="system"),
    PermissionCreateSchema(name="user:bulk_create", display_name="Bulk Create Users", description="Bulk creation of users", scope="system"),
    PermissionCreateSchema(name="group:manage_members", display_name="Manage Group Members", description="Add/remove group members", scope="system"),
]

# Platform-scoped permissions (will be created with platform ID)
ESSENTIAL_PLATFORM_PERMISSIONS = [
    PermissionCreateSchema(name="client_account:create_sub", display_name="Create Sub-Clients", description="Allows creating sub-clients within platform scope.", scope="platform"),
    PermissionCreateSchema(name="client_account:read_platform", display_name="Read Platform Clients", description="Allows reading all clients within platform scope.", scope="platform"),
    PermissionCreateSchema(name="client_account:read_created", display_name="Read Created Clients", description="Allows reading only clients you created.", scope="platform"),
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
    description="Administrative access for managing users, groups, and roles within a client organization - scoped to client level",
    permissions=[],  # Will be populated with granular client-scoped permissions
    scope="client",
    is_assignable_by_main_client=True
)

# Platform Admin Role - for platform-level administration
PLATFORM_ADMIN_ROLE = RoleCreateSchema(
    name="platform_admin",
    display_name="Platform Administrator", 
    description="Administrative access for managing platform-level operations and multiple client accounts - scoped to platform level",
    permissions=[],  # Will be populated with granular platform-level permissions
    scope="platform",
    is_assignable_by_main_client=False
)

# Basic User Role - for standard users with self-access permissions
BASIC_USER_ROLE = RoleCreateSchema(
    name="basic_user",
    display_name="Basic User",
    description="Standard user with self-access permissions - can manage own profile and create business permissions in own scope",
    permissions=[],  # Will be populated with self-access permissions
    scope="system",  # System scope so it's available everywhere
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
        'RoleModel': RoleModel,
        'PermissionModel': PermissionModel,
        'ClientAccountModel': ClientAccountModel,
        'RefreshTokenModel': RefreshTokenModel,
        'PasswordResetTokenModel': PasswordResetTokenModel,
        'GroupModel': GroupModel,
    }
    UserModel.model_rebuild(_types_namespace=namespace)
    RoleModel.model_rebuild(_types_namespace=namespace)
    PermissionModel.model_rebuild(_types_namespace=namespace)
    ClientAccountModel.model_rebuild(_types_namespace=namespace)
    RefreshTokenModel.model_rebuild(_types_namespace=namespace)
    PasswordResetTokenModel.model_rebuild(_types_namespace=namespace)
    GroupModel.model_rebuild(_types_namespace=namespace)


async def ensure_permissions_exist():
    """
    Ensure all essential SYSTEM permissions exist in the database.
    Platform permissions will be created separately with platform IDs.
    """
    print("Ensuring essential system permissions exist...")
    created_count = 0

    for perm_data in ESSENTIAL_SYSTEM_PERMISSIONS:
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

    print(f"System permissions check complete. Created {created_count} new permissions.")
    return created_count


async def ensure_platform_permissions_exist(platform_id: str):
    """
    Ensure all essential PLATFORM permissions exist for a specific platform.
    """
    print(f"Ensuring essential platform permissions exist for platform {platform_id}...")
    created_count = 0

    for perm_data in ESSENTIAL_PLATFORM_PERMISSIONS:
        # Check if permission exists by querying directly
        existing_perm = await PermissionModel.find_one(
            PermissionModel.name == perm_data.name,
            PermissionModel.scope == perm_data.scope,
            PermissionModel.scope_id == platform_id
        )
        if not existing_perm:
            try:
                # Create platform-scoped permission with platform ID as scope_id
                perm_data_with_id = perm_data.model_copy()
                await permission_service.create_permission(
                    perm_data_with_id,
                    current_user_id="system_seed",
                    current_client_id=None,
                    scope_id=platform_id  # Use scope_id instead of platform_id
                )
                created_count += 1
                print(f"  ✓ Created platform permission: {perm_data.name} (platform: {platform_id})")
            except Exception as e:
                print(f"  ❌ Failed to create platform permission {perm_data.name}: {e}")
        else:
            print(f"  - Platform permission already exists: {perm_data.name} (platform: {platform_id})")

    print(f"Platform permissions check complete. Created {created_count} new permissions.")
    return created_count


async def ensure_essential_roles_exist():
    """
    Ensure all essential roles exist in the database.
    """
    print("Ensuring essential roles exist...")
    created_count = 0
    updated_count = 0

    # Get actual permission objects from database (SYSTEM permissions)
    actual_permission_objects = []
    for perm_data in ESSENTIAL_SYSTEM_PERMISSIONS:
        perm = await PermissionModel.find_one(
            PermissionModel.name == perm_data.name,
            PermissionModel.scope == perm_data.scope,
            PermissionModel.scope_id == None
        )
        if perm:
            actual_permission_objects.append(perm)

    # Get platform permission objects (these are scoped to the platform)
    platform_permission_objects = []
    for perm_data in ESSENTIAL_PLATFORM_PERMISSIONS:
        # Find platform permissions for any platform (we'll use the first one we find)
        perm = await PermissionModel.find_one(
            PermissionModel.name == perm_data.name,
            PermissionModel.scope == perm_data.scope
        )
        if perm:
            platform_permission_objects.append(perm)

    # Create super admin role with actual permission objects
    super_admin_role = get_super_admin_role()
    super_admin_role.permissions = actual_permission_objects

    # Basic user permissions - self-access and own scope creation
    basic_user_permission_names = [
        "user:read_self", "user:update_self", "user:change_password",
        "group:read_own",
        "permission:create_own_scope", "role:create_own_scope", "group:create_own_scope"
    ]
    basic_permission_objects = []
    for perm_name in basic_user_permission_names:
        perm = await PermissionModel.find_one(
            PermissionModel.name == perm_name,
            PermissionModel.scope == "system",
            PermissionModel.scope_id == None
        )
        if perm:
            basic_permission_objects.append(perm)

    # Get CLIENT_ADMIN_ROLE permission objects
    client_admin_permission_names = [
        "user:manage_client", "user:add_member",
        "group:manage_client", "group:manage_members",
        "role:read_client", "permission:read_client", "client:read_own"
    ]
    client_admin_permission_objects = []
    for perm_name in client_admin_permission_names:
        perm = await PermissionModel.find_one(
            PermissionModel.name == perm_name,
            PermissionModel.scope == "system",
            PermissionModel.scope_id == None
        )
        if perm:
            client_admin_permission_objects.append(perm)
    
    CLIENT_ADMIN_ROLE.permissions = client_admin_permission_objects

    # Get PLATFORM_ADMIN_ROLE permission objects (includes both system and platform permissions)
    platform_admin_permission_names = [
        "user:manage_all", "user:add_member", "user:bulk_create",
        "role:manage_all",
        "permission:manage_all",
        "client:create", "client:manage_platform",
        "group:manage_all", "group:manage_members"
    ]
    platform_admin_permission_objects = []
    for perm_name in platform_admin_permission_names:
        perm = await PermissionModel.find_one(
            PermissionModel.name == perm_name,
            PermissionModel.scope == "system",
            PermissionModel.scope_id == None
        )
        if perm:
            platform_admin_permission_objects.append(perm)
    
    # Add platform-specific permissions to platform admin
    platform_admin_permission_objects.extend(platform_permission_objects)
    PLATFORM_ADMIN_ROLE.permissions = platform_admin_permission_objects

    essential_roles = [super_admin_role, CLIENT_ADMIN_ROLE, PLATFORM_ADMIN_ROLE]
    
    # Update BASIC_USER_ROLE permissions
    BASIC_USER_ROLE.permissions = basic_permission_objects

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
        super_admin_role = await RoleModel.find_one(RoleModel.name == "super_admin")
        if super_admin_role and super_admin_role not in existing_user.roles:
            existing_user.roles.append(super_admin_role)

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
            roles=["super_admin"],  # UserService will convert this to role objects
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


async def ensure_qdarte_platform_account_exists():
    """
    Ensure the Qdarte platform account exists.
    """
    print(f"Ensuring Qdarte platform account exists: {QDARTE_PLATFORM_ACCOUNT.name}")

    # Check if an account with this name already exists
    existing_accounts = await client_account_service.get_client_accounts()
    platform_account = None

    for account in existing_accounts:
        if account.name == QDARTE_PLATFORM_ACCOUNT.name:
            platform_account = account
            break

    if not platform_account:
        platform_account = await client_account_service.create_client_account(QDARTE_PLATFORM_ACCOUNT)
        print(f"  ✓ Created Qdarte platform account with ID: {platform_account.id}")
        return platform_account, True
    else:
        print(f"  - Qdarte platform account already exists with ID: {platform_account.id}")
        return platform_account, False


async def create_or_update_qdarte_admin(client_account_id):
    """
    Create or update the Qdarte platform admin user (platform level only).
    """
    print(f"Creating/updating Qdarte platform admin user: {PLATFORM_ADMIN_EMAIL}")

    # Check if the user already exists
    existing_user = await user_service.get_user_by_email(PLATFORM_ADMIN_EMAIL)

    if existing_user:
        print(f"  - Qdarte platform admin user already exists with ID: {existing_user.id}")

        # Update user to ensure they have the correct role and client account
        if "platform_admin" not in existing_user.roles:
            existing_user.roles.append("platform_admin")

        # Remove client_admin role if it exists (fixing previous confusion)
        if "client_admin" in existing_user.roles:
            existing_user.roles.remove("client_admin")
            print(f"  ✓ Removed client_admin role (platform admin should only have platform_admin)")

        # Update client account if it's different
        current_client_id = str(existing_user.client_account.ref.id) if hasattr(existing_user.client_account, 'ref') else str(existing_user.client_account.id)
        if current_client_id != str(client_account_id):
            print(f"  ✓ Updating client account association")

        # Ensure is_main_client is True
        existing_user.is_main_client = True
        await existing_user.save()

        print(f"  ✓ Updated Qdarte platform admin user")
        return existing_user, ADMIN_PASSWORD

    else:
        # Create new Qdarte platform admin user with only platform_admin role
        qdarte_admin_data = UserCreateSchema(
            email=PLATFORM_ADMIN_EMAIL,
            password=ADMIN_PASSWORD,
            first_name=PLATFORM_ADMIN_FIRST_NAME,
            last_name=PLATFORM_ADMIN_LAST_NAME,
            is_main_client=True,  # This makes them the main admin for their platform
            roles=["platform_admin"],  # Only platform admin role
            client_account_id=str(client_account_id)
        )

        qdarte_admin_user = await user_service.create_user(qdarte_admin_data)
        print(f"  ✓ Created Qdarte platform admin user with ID: {qdarte_admin_user.id}")

        return qdarte_admin_user, ADMIN_PASSWORD


async def create_or_update_propertyhub_client(platform_account_id):
    """
    Create or update the PropertyHub client account and admin user.
    This is optional and only created when --propertyhub flag is passed.
    """
    print(f"Creating PropertyHub client account as client of Qdarte platform...")

    # Check if PropertyHub client account already exists
    existing_accounts = await client_account_service.get_client_accounts()
    propertyhub_account = None

    for account in existing_accounts:
        if account.name == PROPERTYHUB_CLIENT_ACCOUNT.name:
            propertyhub_account = account
            break

    if not propertyhub_account:
        propertyhub_account = await client_account_service.create_client_account(PROPERTYHUB_CLIENT_ACCOUNT)
        print(f"  ✓ Created PropertyHub client account with ID: {propertyhub_account.id}")
    else:
        print(f"  - PropertyHub client account already exists with ID: {propertyhub_account.id}")

    # Create PropertyHub admin user
    print(f"Creating/updating PropertyHub admin user: {PROPERTYHUB_CLIENT_EMAIL}")

    existing_user = await user_service.get_user_by_email(PROPERTYHUB_CLIENT_EMAIL)

    if existing_user:
        print(f"  - PropertyHub admin user already exists with ID: {existing_user.id}")

        # Update user to ensure they have the correct role and client account
        if "client_admin" not in existing_user.roles:
            existing_user.roles.append("client_admin")

        # Update client account if it's different
        current_client_id = str(existing_user.client_account.ref.id) if hasattr(existing_user.client_account, 'ref') else str(existing_user.client_account.id)
        if current_client_id != str(propertyhub_account.id):
            print(f"  ✓ Updating client account association")

        # Ensure is_main_client is True
        existing_user.is_main_client = True
        await existing_user.save()

        print(f"  ✓ Updated PropertyHub admin user")
        return existing_user, propertyhub_account, ADMIN_PASSWORD

    else:
        # Create new PropertyHub admin user
        propertyhub_admin_data = UserCreateSchema(
            email=PROPERTYHUB_CLIENT_EMAIL,
            password=ADMIN_PASSWORD,
            first_name=PROPERTYHUB_CLIENT_FIRST_NAME,
            last_name=PROPERTYHUB_CLIENT_LAST_NAME,
            is_main_client=True,  # This makes them the main admin for their client org
            roles=["client_admin"],  # Client admin role
            client_account_id=str(propertyhub_account.id)
        )

        propertyhub_admin_user = await user_service.create_user(propertyhub_admin_data)
        print(f"  ✓ Created PropertyHub admin user with ID: {propertyhub_admin_user.id}")

        return propertyhub_admin_user, propertyhub_account, ADMIN_PASSWORD


# Note: Default client admin is now handled by create_or_update_qdarte_admin 
# since Qdarte serves as both platform admin and client admin


async def seed_complete_system(db_name: str = DEFAULT_DB_NAME, include_propertyhub: bool = False):
    """
    Main function to seed the super admin user, default client organization, and all required data.
    
    Args:
        db_name: Name of the database to seed (defaults to main database)
    """
    print("=== Outlabs Three-Tier System Seeding ===")
    print(f"Database: {db_name}")
    print(f"Include PropertyHub: {include_propertyhub}")
    print(f"Super Admin Email: {SUPER_ADMIN_EMAIL}")
    print(f"Super Admin Name: {SUPER_ADMIN_FIRST_NAME} {SUPER_ADMIN_LAST_NAME}")
    print(f"Qdarte Platform Admin Email: {PLATFORM_ADMIN_EMAIL}")
    print(f"Qdarte Platform Admin Name: {PLATFORM_ADMIN_FIRST_NAME} {PLATFORM_ADMIN_LAST_NAME}")
    if include_propertyhub:
        print(f"PropertyHub Client Email: {PROPERTYHUB_CLIENT_EMAIL}")
        print(f"PropertyHub Client Name: {PROPERTYHUB_CLIENT_FIRST_NAME} {PROPERTYHUB_CLIENT_LAST_NAME}")
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

        # Step 2: Ensure Outlabs client account exists
        outlabs_account, outlabs_created = await ensure_outlabs_client_account_exists()

        # Step 3: Create or update super admin user
        super_admin_user, super_admin_password = await create_or_update_super_admin(outlabs_account.id)

        # Step 4: Ensure Qdarte platform account exists (serves as both platform and default client)
        qdarte_account, qdarte_created = await ensure_qdarte_platform_account_exists()

        # Step 5: Ensure platform permissions exist (now we have platform ID)
        await ensure_platform_permissions_exist(str(qdarte_account.id))

        # Step 6: Ensure essential roles exist
        await ensure_essential_roles_exist()

        # Step 7: Create or update Qdarte admin user (platform level only)
        qdarte_admin_user, qdarte_admin_password = await create_or_update_qdarte_admin(qdarte_account.id)

        # Step 8: Optionally create PropertyHub client (only if flag is set)
        propertyhub_admin_user = None
        propertyhub_account = None
        propertyhub_admin_password = None
        
        if include_propertyhub:
            print(f"\n🏗️ Creating PropertyHub client (--propertyhub flag detected)")
            propertyhub_admin_user, propertyhub_account, propertyhub_admin_password = await create_or_update_propertyhub_client(qdarte_account.id)

        print("\n" + "=" * 50)
        print("🎉 COMPLETE THREE-TIER SYSTEM SEEDING COMPLETE 🎉")
        print("=" * 50)
        
        print("\n📋 SUPER ADMIN DETAILS (Tier 1 - System Level):")
        print(f"   Email: {super_admin_user.email}")
        print(f"   Password: {super_admin_password}")
        print(f"   Role: super_admin")
        print(f"   ID: {super_admin_user.id}")
        print(f"   Client Account: {outlabs_account.name}")
        print(f"   Client Account ID: {outlabs_account.id}")
        
        print("\n📋 QDARTE PLATFORM ADMIN DETAILS (Tier 2 - Platform Level):")
        print(f"   Email: {qdarte_admin_user.email}")
        print(f"   Password: {qdarte_admin_password}")
        print(f"   Role: platform_admin")
        print(f"   ID: {qdarte_admin_user.id}")
        print(f"   Platform Account: {qdarte_account.name}")
        print(f"   Account ID: {qdarte_account.id}")
        
        if include_propertyhub and propertyhub_admin_user:
            print("\n📋 PROPERTYHUB CLIENT DETAILS (Tier 3 - Client Level):")
            print(f"   Organization: {propertyhub_account.name}")
            print(f"   Admin Email: {propertyhub_admin_user.email}")
            print(f"   Admin Password: {propertyhub_admin_password}")
            print(f"   Role: client_admin")
            print(f"   Admin ID: {propertyhub_admin_user.id}")
            print(f"   Client Account ID: {propertyhub_account.id}")
            print(f"   Platform Provider: Qdarte Platform")

        accounts_info = "all accounts" if include_propertyhub else "both accounts"
        print(f"\n✅ Ready to use! {accounts_info.title()} can login with password: Asd123$$$")
        print("\nThree-Tier Architecture:")
        print("   1. Outlabs (super_admin) - System-wide control")
        print("   2. Qdarte (platform_admin) - Platform operations")
        if include_propertyhub:
            print("   3. PropertyHub (client_admin) - Client of Qdarte platform")
        else:
            print("   3. PropertyHub - Not created (use --propertyhub to include)")
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
    parser.add_argument(
        "--propertyhub",
        action="store_true", 
        help="Include PropertyHub as a client of Qdarte platform (optional for production)"
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

        asyncio.run(seed_complete_system(target_db, args.propertyhub))

    except KeyboardInterrupt:
        print("\n❌ Seeding cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
