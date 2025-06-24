"""
Comprehensive Test Environment Seeding Script

Purpose:
This script creates a rich, comprehensive test environment with multiple scenarios
for development and testing. It completely wipes the target database and creates:

Available Test Scenarios:
1. 'comprehensive' - General multi-tenant testing with various companies and users
2. 'hierarchical' - Platform-level hierarchy testing with sub-clients  
3. 'propertyhub' - Complete PropertyHub three-tier SaaS platform scenario

PropertyHub Scenario includes:
- PropertyHub Platform Staff (admin@propertyhub.com, support@propertyhub.com, sales@propertyhub.com)
- Real Estate Companies (ACME Real Estate, Elite Properties, Downtown Realty)
- Real Estate Agents and company admins
- Complete three-tier isolation testing
- Cross-platform access control scenarios

Features:
- Multiple realistic test scenarios
- Comprehensive user roles and permissions
- Groups and team structures
- Multi-tenant isolation testing
- Realistic business scenarios

Usage:
1. Seed with PropertyHub scenario (for three-tier tests):
   python scripts/seed_test_environment.py --scenario propertyhub

2. Seed with comprehensive scenario:
   python scripts/seed_test_environment.py --scenario comprehensive

3. Target specific database:
   python scripts/seed_test_environment.py --db outlabsAuth_test --scenario propertyhub

4. Add data without wiping:
   python scripts/seed_test_environment.py --no-wipe --scenario hierarchical

Note:
⚠️  This script DELETES all existing data in the target database before seeding.
It is intended for development and testing environments only.
For production setup, use scripts/seed_essential_users.py instead.
"""
import asyncio
import os
import sys
import argparse
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

# Add the project root to the Python path to allow importing from 'api'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.services.user_service import user_service
from api.services.role_service import role_service
from api.services.permission_service import permission_service
from api.services.client_account_service import client_account_service
from api.services.group_service import group_service
from api.schemas.user_schema import UserCreateSchema
from api.schemas.role_schema import RoleCreateSchema, RoleScope
from api.schemas.permission_schema import PermissionCreateSchema
from api.schemas.client_account_schema import ClientAccountCreateSchema
from api.schemas.group_schema import GroupCreateSchema

# Import all document models for Beanie initialization
from api.models.user_model import UserModel
from api.models.role_model import RoleModel
from api.models.permission_model import PermissionModel
from api.models.client_account_model import ClientAccountModel
from api.models.refresh_token_model import RefreshTokenModel
from api.models.password_reset_token_model import PasswordResetTokenModel
from api.models.group_model import GroupModel

# --- Configuration ---
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
# The database name is now handled via command-line arguments.

# --- Essential Data Definitions ---
# System-level permissions (clean names, scope handled by scope field)
ESSENTIAL_PERMISSIONS = [
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
    PermissionCreateSchema(name="group:create", display_name="Create Groups", description="Allows creating a group.", scope="system"),
    PermissionCreateSchema(name="group:read", display_name="Read Groups", description="Allows reading group information.", scope="system"),
    PermissionCreateSchema(name="group:update", display_name="Update Groups", description="Allows updating a group.", scope="system"),
    PermissionCreateSchema(name="group:delete", display_name="Delete Groups", description="Allows deleting a group.", scope="system"),
    PermissionCreateSchema(name="group:manage_members", display_name="Manage Group Members", description="Allows adding/removing members from groups.", scope="system"),
]

# Platform permissions (clean names, scope handled by scope field)
PLATFORM_PERMISSIONS = [
    PermissionCreateSchema(name="client_account:create_sub", display_name="Create Sub-Clients", description="Allows creating sub-clients within platform scope.", scope="platform"),
    PermissionCreateSchema(name="client_account:read_platform", display_name="Read Platform Clients", description="Allows reading all clients within platform scope.", scope="platform"),
    PermissionCreateSchema(name="client_account:read_created", display_name="Read Created Clients", description="Allows reading only clients you created.", scope="platform"),
    PermissionCreateSchema(name="clients:manage", display_name="Manage Platform Clients", description="Allows managing client accounts across the platform.", scope="platform"),
    PermissionCreateSchema(name="analytics:view", display_name="View Platform Analytics", description="Allows viewing platform-wide analytics and metrics.", scope="platform"),
    PermissionCreateSchema(name="support:cross_client", display_name="Support Platform Users", description="Allows providing support to users across all clients.", scope="platform"),
    PermissionCreateSchema(name="clients:onboard", display_name="Onboard Platform Clients", description="Allows onboarding new clients to the platform.", scope="platform"),
]

# System roles will be created in the seeding function

# Platform roles will be created in the hierarchical scenario

# Test client account for the admin user
TEST_CLIENT_ACCOUNT = ClientAccountCreateSchema(
    name="Test Organization",
    description="Test client account for seeded admin user"
)


async def initialize_and_wipe(db):
    """
    Initializes Beanie, resolves model references, and wipes all relevant collections.
    """
    print(f"--- Initializing and wiping database '{db.name}' ---")
    
    # Initialize Beanie with all document models
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
    
    # Wipe existing data
    print("Wiping existing collections...")
    await UserModel.delete_all()
    await RoleModel.delete_all()
    await PermissionModel.delete_all()
    await ClientAccountModel.delete_all()
    await GroupModel.delete_all()
    print("Collections wiped.")

async def seed_permissions_and_super_admin_role():
    """
    Seeds essential permissions and system roles.
    """
    # Create permissions
    print("Creating essential permissions...")
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
                    current_user_id="system",
                    current_client_id=None
                )
                created_count += 1
                print(f"  ✓ Created permission: {perm_data.name} (scope: {perm_data.scope})")
            except Exception as e:
                print(f"  ❌ Failed to create permission {perm_data.name}: {e}")
        else:
            print(f"  - Permission already exists: {perm_data.name} (scope: {perm_data.scope})")
    print(f"{created_count} new permissions created out of {len(ESSENTIAL_PERMISSIONS)} total.")

    # Create system roles
    print("Creating system roles...")
    
    # Check if super_admin role exists
    system_roles = await role_service.get_roles_by_scope(scope=RoleScope.SYSTEM)
    super_admin_exists = any(role.name == "super_admin" for role in system_roles)
    
    if not super_admin_exists:
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
        
        super_admin_role_data = RoleCreateSchema(
            name="super_admin",
            display_name="Super Administrator",
            description="Grants complete system-wide access.",
            permissions=actual_permission_ids,  # Use actual permission IDs
            scope=RoleScope.SYSTEM,
            is_assignable_by_main_client=False
        )
        await role_service.create_role(
            role_data=super_admin_role_data,
            current_user_id="system"
        )
        print("Super admin role created.")
    else:
        print("Super admin role already exists.")
    
    # Create basic_user role  
    basic_user_exists = any(role.name == "basic_user" for role in system_roles)
    
    if not basic_user_exists:
        # Get actual permission IDs for basic user
        basic_permission_names = ["user:read", "group:read"]
        basic_permission_ids = []
        for perm_name in basic_permission_names:
            perm = await PermissionModel.find_one(
                PermissionModel.name == perm_name,
                PermissionModel.scope == "system",
                PermissionModel.scope_id == None
            )
            if perm:
                basic_permission_ids.append(str(perm.id))
        
        basic_user_role_data = RoleCreateSchema(
            name="basic_user",
            display_name="Basic User",
            description="Basic user access with minimal permissions",
            permissions=basic_permission_ids,  # Use actual permission IDs
            scope=RoleScope.SYSTEM,
            is_assignable_by_main_client=True
        )
        await role_service.create_role(
            role_data=basic_user_role_data,
            current_user_id="system"
        )
        print("Basic user role created.")
    else:
        print("Basic user role already exists.")


async def seed_comprehensive_scenario():
    """
    Seeds a comprehensive set of data for general development and testing.
    Includes multiple clients, users, roles, and groups.
    """
    print("\n--- Seeding: COMPREHENSIVE Scenario ---")

    # Create test client account for the main admin
    print("Creating test client account for super admin...")
    test_client = await client_account_service.create_client_account(TEST_CLIENT_ACCOUNT)

    # Create super admin user
    print("Creating super admin user...")
    # Find the super_admin role
    system_roles = await role_service.get_roles_by_scope(scope=RoleScope.SYSTEM)
    super_admin_role = next((role for role in system_roles if role.name == "super_admin"), None)
    if not super_admin_role:
        raise Exception("Super admin role not found. This should not happen.")
    
    admin_user_data = UserCreateSchema(
        email="admin@test.com",
        password="admin123",
        first_name="Admin",
        last_name="User",
        is_main_client=True,
        roles=[str(super_admin_role.id)],
        client_account_id=str(test_client.id)
    )
    await user_service.create_user(admin_user_data)
    print("Super admin user 'admin@test.com' created.")

    # Create additional client-scoped roles for testing
    print("Creating client-scoped test roles...")
    
    # Create client admin role for test client
    client_admin_role = await role_service.create_role(
        role_data=RoleCreateSchema(
            name="admin",
            display_name="Client Administrator",
            description="Administrative role for client account",
            permissions=["user:create", "user:read", "user:update", "user:delete", "user:add_member", 
                        "group:create", "group:read", "group:update", "group:delete", "group:manage_members",
                        "role:create", "role:read", "role:update", "role:delete"],
            scope=RoleScope.CLIENT,
            is_assignable_by_main_client=True
        ),
        current_user_id="system",
        scope_id=str(test_client.id)
    )
    
    # Create manager role for test client
    manager_role = await role_service.create_role(
        role_data=RoleCreateSchema(
            name="manager",
            display_name="Manager",
            description="Manager role with limited permissions",
            permissions=["user:read", "group:read", "group:update", "group:manage_members"],
            scope=RoleScope.CLIENT,
            is_assignable_by_main_client=True
        ),
        current_user_id="system",
        scope_id=str(test_client.id)
    )
    
    # Create employee role for test client
    employee_role = await role_service.create_role(
        role_data=RoleCreateSchema(
            name="employee",
            display_name="Employee",
            description="Basic employee role",
            permissions=["user:read", "group:read"],
            scope=RoleScope.CLIENT,
            is_assignable_by_main_client=True
        ),
        current_user_id="system",
        scope_id=str(test_client.id)
    )
    
    print("Client-scoped test roles created.")

    # Create additional client accounts
    print("Creating additional client accounts...")
    acme_corp = await client_account_service.create_client_account(
        ClientAccountCreateSchema(name="ACME Corporation", description="Large enterprise client")
    )
    tech_startup = await client_account_service.create_client_account(
        ClientAccountCreateSchema(name="Tech Startup Inc", description="Small tech startup client")
    )

    # Create client-specific roles for each organization
    print("Creating client-specific roles...")
    
    # ACME Corporation roles
    acme_admin_role = await role_service.create_role(
        role_data=RoleCreateSchema(
            name="admin",
            display_name="Client Administrator",
            description="Administrative role for ACME Corporation",
            permissions=["user:create", "user:read", "user:update", "user:delete", "user:add_member", 
                        "group:create", "group:read", "group:update", "group:delete", "group:manage_members",
                        "role:create", "role:read", "role:update", "role:delete"],
            scope=RoleScope.CLIENT,
            is_assignable_by_main_client=True
        ),
        current_user_id="system",
        scope_id=str(acme_corp.id)
    )
    
    acme_employee_role = await role_service.create_role(
        role_data=RoleCreateSchema(
            name="employee",
            display_name="Employee",
            description="Basic employee role for ACME Corporation",
            permissions=["user:read", "group:read"],
            scope=RoleScope.CLIENT,
            is_assignable_by_main_client=True
        ),
        current_user_id="system",
        scope_id=str(acme_corp.id)
    )
    
    # Tech Startup roles
    tech_admin_role = await role_service.create_role(
        role_data=RoleCreateSchema(
            name="admin",
            display_name="Client Administrator",
            description="Administrative role for Tech Startup Inc",
            permissions=["user:create", "user:read", "user:update", "user:delete", "user:add_member",
                        "group:create", "group:read", "group:update", "group:delete", "group:manage_members",
                        "role:create", "role:read", "role:update", "role:delete"],
            scope=RoleScope.CLIENT,
            is_assignable_by_main_client=True
        ),
        current_user_id="system",
        scope_id=str(tech_startup.id)
    )
    
    tech_employee_role = await role_service.create_role(
        role_data=RoleCreateSchema(
            name="employee",
            display_name="Employee",
            description="Basic employee role for Tech Startup Inc",
            permissions=["user:read", "group:read"],
            scope=RoleScope.CLIENT,
            is_assignable_by_main_client=True
        ),
        current_user_id="system",
        scope_id=str(tech_startup.id)
    )

    # Create users for different client accounts
    print("Creating additional users...")
    await user_service.create_user(UserCreateSchema(
        email="admin@acme.com", password="admin123", first_name="Alice", last_name="Admin",
        is_main_client=True, roles=[str(acme_admin_role.id)], client_account_id=str(acme_corp.id)
    ))
    await user_service.create_user(UserCreateSchema(
        email="manager@acme.com", password="manager123", first_name="Bob", last_name="Manager",
        is_main_client=False, roles=[str(manager_role.id)], client_account_id=str(test_client.id)
    ))
    await user_service.create_user(UserCreateSchema(
        email="admin@techstartup.com", password="admin123", first_name="Charlie", last_name="Founder",
        is_main_client=True, roles=[str(tech_admin_role.id)], client_account_id=str(tech_startup.id)
    ))
    
    # Create employee users for ACME
    await user_service.create_user(UserCreateSchema(
        email="employee1@acme.com", password="secure_password_123", first_name="Employee1", last_name="Acme",
        is_main_client=False, roles=[str(acme_employee_role.id)], client_account_id=str(acme_corp.id)
    ))
    await user_service.create_user(UserCreateSchema(
        email="employee2@acme.com", password="secure_password_123", first_name="Employee2", last_name="Acme",
        is_main_client=False, roles=[str(acme_employee_role.id)], client_account_id=str(acme_corp.id)
    ))
    await user_service.create_user(UserCreateSchema(
        email="employee3@acme.com", password="secure_password_123", first_name="Employee3", last_name="Acme",
        is_main_client=False, roles=[str(acme_employee_role.id)], client_account_id=str(acme_corp.id)
    ))
    
    # Create employee users for Tech Startup
    await user_service.create_user(UserCreateSchema(
        email="dev1@techstartup.com", password="secure_password_123", first_name="Developer1", last_name="Tech",
        is_main_client=False, roles=[str(tech_employee_role.id)], client_account_id=str(tech_startup.id)
    ))
    await user_service.create_user(UserCreateSchema(
        email="dev2@techstartup.com", password="secure_password_123", first_name="Developer2", last_name="Tech",
        is_main_client=False, roles=[str(tech_employee_role.id)], client_account_id=str(tech_startup.id)
    ))

    # Create test groups
    print("Creating test groups...")
    acme_users = await UserModel.find(UserModel.client_account.id == acme_corp.id).to_list()
    
    # Get permission IDs for group
    user_read_perm = await PermissionModel.find_one(
        PermissionModel.name == "user:read",
        PermissionModel.scope == "system"
    )
    group_read_perm = await PermissionModel.find_one(
        PermissionModel.name == "group:read", 
        PermissionModel.scope == "system"
    )
    
    permission_ids = []
    if user_read_perm:
        permission_ids.append(str(user_read_perm.id))
    if group_read_perm:
        permission_ids.append(str(group_read_perm.id))
    
    await group_service.create_group(
        group_data=GroupCreateSchema(
            name="acme_team",
            display_name="ACME Team", 
            description="ACME Corporation Team",
            permissions=permission_ids,  # Use actual permission IDs
            scope="client"
        ),
        current_user_id="system",
        current_client_id=str(acme_corp.id)
    )
    
    print("\n--- COMPREHENSIVE Scenario Seeding Complete! ---")


async def seed_hierarchical_scenario():
    """
    Seeds data for testing hierarchical multi-platform tenancy.
    """
    print("\n--- Seeding: HIERARCHICAL Scenario ---")

    # Create platform root client accounts
    print("Creating platform root client accounts...")
    platform1_client = await client_account_service.create_client_account(
        ClientAccountCreateSchema(name="Real Estate Platform", is_platform_root=True)
    )
    platform2_client = await client_account_service.create_client_account(
        ClientAccountCreateSchema(name="CRM Platform", is_platform_root=True)
    )
    
    # Create platform-specific roles for Platform 1 (Real Estate)
    print("Creating platform-specific roles...")
    platform1_creator_role = await role_service.create_role(
        role_data=RoleCreateSchema(
            name="creator",
            display_name="Platform Creator",
            description="Can create sub-clients within their platform scope and access all platform clients.",
            permissions=[
                "user:read", "user:create", "user:update", "user:add_member",
                "client_account:read", "client_account:create_sub", "client_account:read_platform", "client_account:update",
                "group:read", "group:create", "group:update", "group:manage_members",
                "role:read", "permission:read"
            ],
            scope=RoleScope.PLATFORM,
            is_assignable_by_main_client=True
        ),
        current_user_id="system",
        scope_id=str(platform1_client.id)
    )

    # Create platform-specific roles for Platform 2 (CRM)
    platform2_viewer_role = await role_service.create_role(
        role_data=RoleCreateSchema(
            name="viewer",
            display_name="Platform Viewer",
            description="Can only view clients they created within their platform scope.",
            permissions=[
                "user:read", "user:create", "user:update", "user:add_member",
                "client_account:read", "client_account:read_created", "client_account:update",
                "group:read", "group:create", "group:update", "group:manage_members",
                "role:read", "permission:read"
            ],
            scope=RoleScope.PLATFORM,
            is_assignable_by_main_client=True
        ),
        current_user_id="system",
        scope_id=str(platform2_client.id)
    )

    # Create platform admin users
    print("Creating platform admin users...")
    await user_service.create_user(UserCreateSchema(
        email="platform1.creator@test.com", password="platform123", first_name="Platform1", last_name="Creator",
        is_main_client=True, roles=[str(platform1_creator_role.id)], client_account_id=str(platform1_client.id)
    ))
    await user_service.create_user(UserCreateSchema(
        email="platform2.viewer@test.com", password="platform123", first_name="Platform2", last_name="Viewer",
        is_main_client=True, roles=[str(platform2_viewer_role.id)], client_account_id=str(platform2_client.id)
    ))

    # Create sub-clients for platforms
    print("Creating sub-clients for platform testing...")
    acme_client = await client_account_service.create_client_account(
        ClientAccountCreateSchema(name="ACME Properties", description="Sub-client of Real Estate Platform"),
        created_by_client_id=str(platform1_client.id)
    )
    
    # Create client admin role for ACME Properties
    acme_admin_role = await role_service.create_role(
        role_data=RoleCreateSchema(
            name="admin",
            display_name="Client Administrator",
            description="Administrative role for ACME Properties",
            permissions=["user:read", "user:update", "user:create", "user:add_member",
                        "group:read", "group:create", "group:update", "group:manage_members"],
            scope=RoleScope.CLIENT,
            is_assignable_by_main_client=True
        ),
        current_user_id="system",
        scope_id=str(acme_client.id)
    )

    # Create users for sub-clients
    await user_service.create_user(UserCreateSchema(
        email="admin@acme-properties.com", password="acme123", first_name="John", last_name="ACME",
        is_main_client=True, roles=[str(acme_admin_role.id)], client_account_id=str(acme_client.id)
    ))

    print("\n--- HIERARCHICAL Scenario Seeding Complete! ---")
    print("Test Users:")
    print("  - platform1.creator@test.com (Platform Creator)")
    print("  - platform2.viewer@test.com (Platform Viewer)")
    print("  - admin@acme-properties.com (Client Admin)")


async def convert_permission_names_to_ids(permission_names: list[str], scope_id: str = None) -> list[str]:
    """
    Convert a list of permission names to ObjectIds.
    For platform permissions, provide scope_id. For system permissions, leave scope_id as None.
    """
    permission_ids = []
    
    for perm_name in permission_names:
        # First try to find system permission
        perm = await PermissionModel.find_one(
            PermissionModel.name == perm_name,
            PermissionModel.scope == "system",
            PermissionModel.scope_id == None
        )
        
        # If not found and we have a scope_id, try platform permission
        if not perm and scope_id:
            perm = await PermissionModel.find_one(
                PermissionModel.name == perm_name,
                PermissionModel.scope == "platform",
                PermissionModel.scope_id == scope_id
            )
            
        if perm:
            permission_ids.append(str(perm.id))
        else:
            print(f"  ⚠️  Permission not found: {perm_name}")
            
    return permission_ids


async def ensure_platform_permissions_exist(platform_id: str):
    """
    Ensure all essential PLATFORM permissions exist for a specific platform.
    """
    print(f"Ensuring essential platform permissions exist for platform {platform_id}...")
    created_count = 0

    # Define platform permissions inline since they're not imported
    platform_permissions = [
        PermissionCreateSchema(name="client_account:create_sub", display_name="Create Sub-Clients", description="Allows creating sub-client accounts within platform scope.", scope="platform"),
        PermissionCreateSchema(name="client_account:read_platform", display_name="Read Platform Clients", description="Allows reading all clients within platform scope.", scope="platform"),
        PermissionCreateSchema(name="client_account:read_created", display_name="Read Created Clients", description="Allows reading only clients created by the user/platform.", scope="platform")
    ]

    for perm_data in platform_permissions:
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


async def seed_propertyhub_scenario():
    """
    Seeds data for testing the PropertyHub three-tier SaaS platform model:
    1. PropertyHub Platform Staff (internal team)
    2. Real Estate Companies (clients)  
    3. Real Estate Agents (end users)
    """
    print("\n--- Seeding: PROPERTYHUB Scenario ---")

    # Create PropertyHub platform account
    print("Creating PropertyHub platform account...")
    propertyhub_platform = await client_account_service.create_client_account(
        ClientAccountCreateSchema(
            name="PropertyHub Platform", 
            description="PropertyHub SaaS platform for real estate management",
            is_platform_root=True
        )
    )
    
    # Create platform-scoped permissions for PropertyHub platform
    print("Creating platform permissions for PropertyHub...")
    await ensure_platform_permissions_exist(str(propertyhub_platform.id))
    
    # Create PropertyHub platform roles for the platform
    print("Creating PropertyHub platform roles...")
    
    # Convert permission names to ObjectIds for platform admin
    platform_admin_permission_names = [
        "client_account:create", "client_account:read", "client_account:update", 
        "client_account:create_sub", "client_account:read_platform", "client_account:read_created",
        "user:create", "user:read", "user:update", "user:delete", "user:add_member",
        "group:create", "group:read", "group:update", "group:delete", "group:manage_members",
        "role:read", "permission:read"
    ]
    platform_admin_permission_ids = await convert_permission_names_to_ids(
        platform_admin_permission_names, 
        str(propertyhub_platform.id)
    )
    
    platform_admin_role = await role_service.create_role(
        role_data=RoleCreateSchema(
            name="admin",
            display_name="Platform Administrator",
            description="PropertyHub internal administrator",
            permissions=platform_admin_permission_ids,
            scope=RoleScope.PLATFORM,
            is_assignable_by_main_client=True
        ),
        current_user_id="system",
        scope_id=str(propertyhub_platform.id)
    )

    # Convert permission names to ObjectIds for platform support
    platform_support_permission_names = [
        "client_account:read", "client_account:read_platform", 
        "user:read", "group:read"
    ]
    platform_support_permission_ids = await convert_permission_names_to_ids(
        platform_support_permission_names, 
        str(propertyhub_platform.id)
    )
    
    platform_support_role = await role_service.create_role(
        role_data=RoleCreateSchema(
            name="support",
            display_name="Platform Support",
            description="PropertyHub customer success team",
            permissions=platform_support_permission_ids,
            scope=RoleScope.PLATFORM,
            is_assignable_by_main_client=True
        ),
        current_user_id="system",
        scope_id=str(propertyhub_platform.id)
    )

    platform_sales_role = await role_service.create_role(
        role_data=RoleCreateSchema(
            name="sales",
            display_name="Platform Sales",
            description="PropertyHub sales team",
            permissions=["client_account:create", "client_account:read", "client_account:read_created",
                        "user:read"],
            scope=RoleScope.PLATFORM,
            is_assignable_by_main_client=True
        ),
        current_user_id="system",
        scope_id=str(propertyhub_platform.id)
    )

    print("3 PropertyHub platform roles created.")
    
    # Create PropertyHub internal staff
    print("Creating PropertyHub internal staff...")
    await user_service.create_user(UserCreateSchema(
        email="admin@propertyhub.com", password="platform123", 
        first_name="Admin", last_name="PropertyHub",
        is_main_client=True, roles=[str(platform_admin_role.id)], 
        client_account_id=str(propertyhub_platform.id),
        is_platform_staff=True, platform_scope="all"
    ))
    
    await user_service.create_user(UserCreateSchema(
        email="support@propertyhub.com", password="platform123",
        first_name="Support", last_name="Team", 
        is_main_client=False, roles=[str(platform_support_role.id)],
        client_account_id=str(propertyhub_platform.id),
        is_platform_staff=True, platform_scope="all"
    ))
    
    await user_service.create_user(UserCreateSchema(
        email="sales@propertyhub.com", password="platform123",
        first_name="Sales", last_name="Team",
        is_main_client=False, roles=[str(platform_sales_role.id)],
        client_account_id=str(propertyhub_platform.id),
        is_platform_staff=True, platform_scope="created"
    ))

    # Create real estate company clients
    print("Creating real estate company clients...")
    acme_realestate = await client_account_service.create_client_account(
        ClientAccountCreateSchema(
            name="ACME Real Estate", 
            description="Independent real estate brokerage using PropertyHub"
        ),
        created_by_client_id=str(propertyhub_platform.id)
    )
    
    elite_properties = await client_account_service.create_client_account(
        ClientAccountCreateSchema(
            name="Elite Properties", 
            description="Luxury real estate firm using PropertyHub"
        ),
        created_by_client_id=str(propertyhub_platform.id)
    )
    
    downtown_realty = await client_account_service.create_client_account(
        ClientAccountCreateSchema(
            name="Downtown Realty", 
            description="Urban real estate specialists using PropertyHub"
        ),
        created_by_client_id=str(propertyhub_platform.id)
    )

    # Create client-specific roles for each real estate company
    print("Creating client-specific roles...")
    
    # ACME Real Estate roles
    acme_admin_role = await role_service.create_role(
        role_data=RoleCreateSchema(
            name="admin",
            display_name="Real Estate Company Admin",
            description="Real estate company administrator",
            permissions=["user:create", "user:read", "user:update", "user:add_member",
                        "group:create", "group:read", "group:update", "group:manage_members",
                        "client_account:read"],
            scope=RoleScope.CLIENT,
            is_assignable_by_main_client=True
        ),
        current_user_id="system",
        scope_id=str(acme_realestate.id)
    )

    acme_agent_role = await role_service.create_role(
        role_data=RoleCreateSchema(
            name="agent",
            display_name="Real Estate Agent",
            description="Real estate agent or sales person",
            permissions=["user:read", "group:read", "client_account:read"],
            scope=RoleScope.CLIENT,
            is_assignable_by_main_client=True
        ),
        current_user_id="system",
        scope_id=str(acme_realestate.id)
    )

    # Elite Properties roles
    elite_admin_role = await role_service.create_role(
        role_data=RoleCreateSchema(
            name="admin",
            display_name="Real Estate Company Admin",
            description="Real estate company administrator",
            permissions=["user:create", "user:read", "user:update", "user:add_member",
                        "group:create", "group:read", "group:update", "group:manage_members",
                        "client_account:read"],
            scope=RoleScope.CLIENT,
            is_assignable_by_main_client=True
        ),
        current_user_id="system",
        scope_id=str(elite_properties.id)
    )

    elite_agent_role = await role_service.create_role(
        role_data=RoleCreateSchema(
            name="agent",
            display_name="Real Estate Agent",
            description="Real estate agent or sales person",
            permissions=["user:read", "group:read", "client_account:read"],
            scope=RoleScope.CLIENT,
            is_assignable_by_main_client=True
        ),
        current_user_id="system",
        scope_id=str(elite_properties.id)
    )

    # Downtown Realty roles
    downtown_admin_role = await role_service.create_role(
        role_data=RoleCreateSchema(
            name="admin",
            display_name="Real Estate Company Admin",
            description="Real estate company administrator",
            permissions=["user:create", "user:read", "user:update", "user:add_member",
                        "group:create", "group:read", "group:update", "group:manage_members",
                        "client_account:read"],
            scope=RoleScope.CLIENT,
            is_assignable_by_main_client=True
        ),
        current_user_id="system",
        scope_id=str(downtown_realty.id)
    )

    # Create real estate company admins
    print("Creating real estate company admins...")
    await user_service.create_user(UserCreateSchema(
        email="admin@acmerealestate.com", password="realestate123",
        first_name="Alice", last_name="Johnson",
        is_main_client=True, roles=[str(acme_admin_role.id)],
        client_account_id=str(acme_realestate.id)
    ))
    
    await user_service.create_user(UserCreateSchema(
        email="admin@eliteproperties.com", password="realestate123",
        first_name="Bob", last_name="Smith", 
        is_main_client=True, roles=[str(elite_admin_role.id)],
        client_account_id=str(elite_properties.id)
    ))
    
    await user_service.create_user(UserCreateSchema(
        email="admin@downtownrealty.com", password="realestate123",
        first_name="Carol", last_name="Brown",
        is_main_client=True, roles=[str(downtown_admin_role.id)],
        client_account_id=str(downtown_realty.id)
    ))

    # Create real estate agents for ACME Real Estate
    print("Creating real estate agents...")
    await user_service.create_user(UserCreateSchema(
        email="john.agent@acmerealestate.com", password="agent123",
        first_name="John", last_name="Agent",
        is_main_client=False, roles=[str(acme_agent_role.id)],
        client_account_id=str(acme_realestate.id)
    ))
    
    await user_service.create_user(UserCreateSchema(
        email="sarah.manager@acmerealestate.com", password="agent123",
        first_name="Sarah", last_name="Manager",
        is_main_client=False, roles=[str(acme_agent_role.id)], 
        client_account_id=str(acme_realestate.id)
    ))
    
    await user_service.create_user(UserCreateSchema(
        email="mike.assistant@acmerealestate.com", password="agent123",
        first_name="Mike", last_name="Assistant",
        is_main_client=False, roles=[str(acme_agent_role.id)],
        client_account_id=str(acme_realestate.id)
    ))

    # Create agents for Elite Properties  
    await user_service.create_user(UserCreateSchema(
        email="luxury.agent@eliteproperties.com", password="agent123",
        first_name="Luxury", last_name="Agent",
        is_main_client=False, roles=[str(elite_agent_role.id)],
        client_account_id=str(elite_properties.id)
    ))

    # Create PropertyHub team groups
    print("Creating PropertyHub platform groups...")
    platform_users = await UserModel.find(UserModel.client_account.id == propertyhub_platform.id).to_list()
    platform_user_ids = [str(u.id) for u in platform_users]
    await group_service.create_group(
        group_data=GroupCreateSchema(
            name="PropertyHub Internal Team",
            display_name="PropertyHub Internal Team", 
            description="PropertyHub platform staff",
            scope="platform",
            client_account_id=str(propertyhub_platform.id), 
            members=platform_user_ids,
            roles=[str(platform_admin_role.id)]
        ),
        current_user_id="system",
        current_client_id=str(propertyhub_platform.id),
        scope_id=str(propertyhub_platform.id)  # Platform ID required for platform-scoped groups
    )

    # Create real estate company groups
    acme_users = await UserModel.find(UserModel.client_account.id == acme_realestate.id).to_list()
    acme_user_ids = [str(u.id) for u in acme_users]
    await group_service.create_group(
        group_data=GroupCreateSchema(
            name="ACME Sales Team",
            display_name="ACME Sales Team",
            description="ACME Real Estate sales team",
            scope="client",
            client_account_id=str(acme_realestate.id),
            members=acme_user_ids,
            roles=[str(acme_agent_role.id)]
        ),
        current_user_id="system",
        current_client_id=str(acme_realestate.id)
    )
    
    print("\n--- PROPERTYHUB Scenario Seeding Complete! ---")
    print("PropertyHub Platform Staff:")
    print("  - admin@propertyhub.com (Platform Admin)")
    print("  - support@propertyhub.com (Customer Success)")
    print("  - sales@propertyhub.com (Sales Team)")
    print("\nReal Estate Company Admins:")
    print("  - admin@acmerealestate.com (ACME Real Estate)")
    print("  - admin@eliteproperties.com (Elite Properties)")
    print("  - admin@downtownrealty.com (Downtown Realty)")
    print("\nReal Estate Agents:")
    print("  - john.agent@acmerealestate.com (ACME Agent)")
    print("  - sarah.manager@acmerealestate.com (ACME Manager)")
    print("  - luxury.agent@eliteproperties.com (Elite Agent)")


async def main():
    """
    Main function to execute the seeding process based on command-line arguments.
    """
    parser = argparse.ArgumentParser(description="Seed the database with test data.")
    parser.add_argument(
        "--db",
        type=str,
        default="outlabsAuth_test",
        help="The name of the database to seed. Defaults to 'outlabsAuth_test'."
    )
    parser.add_argument(
        "--prod",
        action="store_true",
        help="If specified, seeds the 'outlabsAuth' database. Overrides --db."
    )
    parser.add_argument(
        "--scenario",
        type=str,
        choices=['comprehensive', 'hierarchical', 'propertyhub'],
        default='comprehensive',
        help="The seeding scenario to run. Defaults to 'comprehensive'."
    )
    parser.add_argument(
        "--no-wipe",
        action="store_true",
        help="If specified, does not wipe the database before seeding. Useful for adding data."
    )
    args = parser.parse_args()

    db_name = "outlabsAuth" if args.prod else args.db
    
    print(f"--- Target database: '{db_name}' ---")
    print(f"--- Scenario: '{args.scenario}' ---")
    print("!!! WARNING: This will wipe all data in the target database. !!!")
    
    # Give user a chance to cancel
    try:
        import time
        for i in range(5, 0, -1):
            print(f"Starting in {i}...", end="\r")
            time.sleep(1)
        print("\nStarting seeding process...")
    except KeyboardInterrupt:
        print("\n❌ Seeding cancelled by user.")
        sys.exit(1)

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[db_name]
    
    try:
        # Step 1: Initialize DB and optionally wipe collections
        if not args.no_wipe:
            await initialize_and_wipe(db)
        else:
            print(f"--- Skipping database wipe for '{db_name}' ---")
            # Still need to initialize beanie for services to work
            await init_beanie(
                database=db,
                document_models=[
                    UserModel, RoleModel, PermissionModel, ClientAccountModel,
                    RefreshTokenModel, PasswordResetTokenModel, GroupModel
                ]
            )

        # Step 2: Seed common data (permissions, super_admin role)
        await seed_permissions_and_super_admin_role()

        # Step 3: Run the selected scenario
        if args.scenario == 'comprehensive':
            await seed_comprehensive_scenario()
        elif args.scenario == 'hierarchical':
            await seed_hierarchical_scenario()
        elif args.scenario == 'propertyhub':
            await seed_propertyhub_scenario()

        print(f"\n✅ Successfully seeded database '{db_name}' with '{args.scenario}' scenario.")

    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main()) 