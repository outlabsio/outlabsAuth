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
from api.models.user_model import UserStatus
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
# System-level permissions (granular, scoped permissions)
ESSENTIAL_PERMISSIONS = [
    # === SELF-ACCESS PERMISSIONS (default for all users) ===
    PermissionCreateSchema(name="user:read_self", display_name="Read Own Profile", description="Read own user profile in auth platform", scope="system"),
    PermissionCreateSchema(name="user:update_self", display_name="Update Own Profile", description="Update own user profile in auth platform", scope="system"),
    PermissionCreateSchema(name="user:change_password", display_name="Change Own Password", description="Change own password", scope="system"),
    PermissionCreateSchema(name="group:read_own", display_name="Read Own Groups", description="View own group memberships in auth platform", scope="system"),
    PermissionCreateSchema(name="client:read_own", display_name="Read Own Client", description="View own client account info in auth platform", scope="system"),
    
    # Own scope creation permissions (default for all users)
    PermissionCreateSchema(name="permission:create_own_scope", display_name="Create Own Scope Permissions", description="Create permissions in own scope", scope="system"),
    PermissionCreateSchema(name="role:create_own_scope", display_name="Create Own Scope Roles", description="Create roles in own scope", scope="system"),
    PermissionCreateSchema(name="group:create_own_scope", display_name="Create Own Scope Groups", description="Create groups in own scope", scope="system"),
    
    # === CLIENT-SCOPED PERMISSIONS ===
    PermissionCreateSchema(name="user:read_client", display_name="Read Client Users", description="Read users in same client (auth platform)", scope="system"),
    PermissionCreateSchema(name="user:manage_client", display_name="Manage Client Users", description="CRUD users in same client (auth platform)", scope="system"),
    PermissionCreateSchema(name="role:read_client", display_name="Read Client Roles", description="Read roles in same client (auth platform)", scope="system"),
    PermissionCreateSchema(name="role:manage_client", display_name="Manage Client Roles", description="CRUD roles in same client (auth platform)", scope="system"),
    PermissionCreateSchema(name="group:read_client", display_name="Read Client Groups", description="Read groups in same client (auth platform)", scope="system"),
    PermissionCreateSchema(name="group:manage_client", display_name="Manage Client Groups", description="CRUD groups in same client (auth platform)", scope="system"),
    PermissionCreateSchema(name="permission:read_client", display_name="Read Client Permissions", description="Read permissions in same client (auth platform)", scope="system"),
    PermissionCreateSchema(name="permission:manage_client", display_name="Manage Client Permissions", description="CRUD permissions in same client (auth platform)", scope="system"),
    
    # === ADMIN-ONLY PERMISSIONS (system-wide) ===
    PermissionCreateSchema(name="user:read_all", display_name="Read All Users", description="Read all users in auth platform (admin only)", scope="system"),
    PermissionCreateSchema(name="user:manage_all", display_name="Manage All Users", description="Global user management in auth platform (admin only)", scope="system"),
    PermissionCreateSchema(name="role:read_all", display_name="Read All Roles", description="Read all roles in auth platform (admin only)", scope="system"),
    PermissionCreateSchema(name="role:manage_all", display_name="Manage All Roles", description="Global role management in auth platform (admin only)", scope="system"),
    PermissionCreateSchema(name="group:read_all", display_name="Read All Groups", description="Read all groups in auth platform (admin only)", scope="system"),
    PermissionCreateSchema(name="group:manage_all", display_name="Manage All Groups", description="Global group management in auth platform (admin only)", scope="system"),
    PermissionCreateSchema(name="permission:read_all", display_name="Read All Permissions", description="Read all permissions in auth platform (admin only)", scope="system"),
    PermissionCreateSchema(name="permission:manage_all", display_name="Manage All Permissions", description="Global permission management in auth platform (admin only)", scope="system"),
    
    # === PLATFORM-LEVEL PERMISSIONS ===
    PermissionCreateSchema(name="client:create", display_name="Create Client Accounts", description="Create new client accounts in auth platform", scope="system"),
    PermissionCreateSchema(name="client:read_platform", display_name="Read Platform Clients", description="Read all platform client accounts", scope="system"),
    PermissionCreateSchema(name="client:manage_platform", display_name="Manage Platform Clients", description="Manage clients across platform", scope="system"),
    PermissionCreateSchema(name="support:cross_client", display_name="Cross-Client Support", description="Support across all platform clients in auth platform", scope="system"),
    
    # === SYSTEM-LEVEL INFRASTRUCTURE PERMISSIONS ===
    PermissionCreateSchema(name="platform:create", display_name="Create Platforms", description="Create new platforms", scope="system"),
    PermissionCreateSchema(name="platform:manage_all", display_name="Manage All Platforms", description="Full platform management in auth platform", scope="system"),
    PermissionCreateSchema(name="system:infrastructure", display_name="System Infrastructure", description="Auth platform infrastructure management", scope="system"),
    PermissionCreateSchema(name="admin:*", display_name="Admin All Access", description="Wildcard auth platform admin access", scope="system"),
    
    # === TRANSITION PERMISSIONS (for roles and tests migration) ===
    PermissionCreateSchema(name="user:add_member", display_name="Add Team Members", description="Add users to client account", scope="system"),
    PermissionCreateSchema(name="user:bulk_create", display_name="Bulk Create Users", description="Bulk creation of users", scope="system"),
    PermissionCreateSchema(name="group:manage_members", display_name="Manage Group Members", description="Add/remove group members", scope="system"),
]

# Platform permissions (platform-scoped permissions for specific platforms)
PLATFORM_PERMISSIONS = [
    PermissionCreateSchema(name="client:create_sub", display_name="Create Sub-Clients", description="Create sub-clients within platform scope", scope="platform"),
    PermissionCreateSchema(name="client:read_platform", display_name="Read Platform Clients", description="Read all clients within platform scope", scope="platform"),
    PermissionCreateSchema(name="client:read_created", display_name="Read Created Clients", description="Read only clients you created", scope="platform"),
    PermissionCreateSchema(name="client:manage_platform", display_name="Manage Platform Clients", description="Manage client accounts across the platform", scope="platform"),
    PermissionCreateSchema(name="analytics:view_platform", display_name="View Platform Analytics", description="View platform-wide analytics and metrics", scope="platform"),
    PermissionCreateSchema(name="support:cross_client", display_name="Support Platform Users", description="Provide support to users across all clients", scope="platform"),
    PermissionCreateSchema(name="client:onboard", display_name="Onboard Platform Clients", description="Onboard new clients to the platform", scope="platform"),
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
    # Create essential system permissions
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
    
    # Create platform permissions as system permissions
    print("Creating platform permissions...")
    for perm_data in PLATFORM_PERMISSIONS:
        # Check if permission exists by querying directly
        existing_perm = await PermissionModel.find_one(
            PermissionModel.name == perm_data.name,
            PermissionModel.scope == "system",  # Create as system permissions first
            PermissionModel.scope_id == None  # System permissions have null scope_id
        )
        if not existing_perm:
            try:
                # Create as system permission first
                system_perm_data = PermissionCreateSchema(
                    name=perm_data.name,
                    display_name=perm_data.display_name,
                    description=perm_data.description,
                    scope="system"
                )
                await permission_service.create_permission(
                    system_perm_data,
                    current_user_id="system",
                    current_client_id=None
                )
                created_count += 1
                print(f"  ✓ Created platform permission: {perm_data.name} (scope: system)")
            except Exception as e:
                print(f"  ❌ Failed to create platform permission {perm_data.name}: {e}")
        else:
            print(f"  - Platform permission already exists: {perm_data.name} (scope: system)")
    
    print(f"{created_count} new permissions created out of {len(ESSENTIAL_PERMISSIONS) + len(PLATFORM_PERMISSIONS)} total.")

    # Create system roles
    print("Creating system roles...")
    
    # Check if super_admin role exists
    system_roles = await role_service.get_roles_by_scope(scope=RoleScope.SYSTEM)
    super_admin_exists = any(role.name == "super_admin" for role in system_roles)
    
    if not super_admin_exists:
        # Use permission names directly - service will convert to ObjectIds
        super_admin_permission_names = [perm.name for perm in ESSENTIAL_PERMISSIONS]
        
        super_admin_role_data = RoleCreateSchema(
            name="super_admin",
            display_name="Super Administrator",
            description="Grants complete system-wide access to auth platform.",
            permissions=super_admin_permission_names,  # Use permission names directly
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
        # Use self-access permission names directly - service will convert to ObjectIds
        basic_permission_names = [
            "user:read_self", "user:update_self", "user:change_password",
            "group:read_own",
            "permission:create_own_scope", "role:create_own_scope", "group:create_own_scope"
        ]
        
        basic_user_role_data = RoleCreateSchema(
            name="basic_user",
            display_name="Basic User",
            description="Standard user with self-access permissions - can manage own profile and create business permissions in own scope",
            permissions=basic_permission_names,  # Use permission names directly
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
        status=UserStatus.ACTIVE,
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
            description="Administrative role for client account - manages users, groups, and roles within client scope",
            permissions=["user:manage_client", "user:add_member", 
                        "group:manage_client", "group:manage_members",
                        "role:read_client", "permission:read_client", "client:read_own"],
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
            description="Manager role with limited client-scoped permissions",
            permissions=["user:read_client", "group:read_client", "group:manage_members", "client:read_own"],
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
            description="Basic employee role with self-access permissions",
            permissions=["user:read_self", "group:read_own", "client:read_own"],
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
            description="Administrative role for ACME Corporation - manages users, groups, and roles within client scope",
            permissions=["user:manage_client", "user:add_member", 
                        "group:manage_client", "group:manage_members",
                        "role:read_client", "permission:read_client", "client:read_own"],
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
            description="Basic employee role for ACME Corporation with self-access permissions",
            permissions=["user:read_self", "group:read_own", "client:read_own"],
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
            description="Administrative role for Tech Startup Inc - manages users, groups, and roles within client scope",
            permissions=["user:manage_client", "user:add_member",
                        "group:manage_client", "group:manage_members",
                        "role:read_client", "permission:read_client", "client:read_own"],
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
            description="Basic employee role for Tech Startup Inc with self-access permissions",
            permissions=["user:read_self", "group:read_own", "client:read_own"],
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
        status=UserStatus.ACTIVE, is_main_client=True, roles=[str(acme_admin_role.id)], client_account_id=str(acme_corp.id)
    ))
    await user_service.create_user(UserCreateSchema(
        email="manager@acme.com", password="manager123", first_name="Bob", last_name="Manager",
        status=UserStatus.ACTIVE, is_main_client=False, roles=[str(manager_role.id)], client_account_id=str(test_client.id)
    ))
    await user_service.create_user(UserCreateSchema(
        email="admin@techstartup.com", password="admin123", first_name="Charlie", last_name="Founder",
        status=UserStatus.ACTIVE, is_main_client=True, roles=[str(tech_admin_role.id)], client_account_id=str(tech_startup.id)
    ))
    
    # Create employee users for ACME
    await user_service.create_user(UserCreateSchema(
        email="employee1@acme.com", password="secure_password_123", first_name="Employee1", last_name="Acme",
        status=UserStatus.ACTIVE, is_main_client=False, roles=[str(acme_employee_role.id)], client_account_id=str(acme_corp.id)
    ))
    await user_service.create_user(UserCreateSchema(
        email="employee2@acme.com", password="secure_password_123", first_name="Employee2", last_name="Acme",
        status=UserStatus.ACTIVE, is_main_client=False, roles=[str(acme_employee_role.id)], client_account_id=str(acme_corp.id)
    ))
    await user_service.create_user(UserCreateSchema(
        email="employee3@acme.com", password="secure_password_123", first_name="Employee3", last_name="Acme",
        status=UserStatus.ACTIVE, is_main_client=False, roles=[str(acme_employee_role.id)], client_account_id=str(acme_corp.id)
    ))
    
    # Create employee users for Tech Startup
    await user_service.create_user(UserCreateSchema(
        email="dev1@techstartup.com", password="secure_password_123", first_name="Developer1", last_name="Tech",
        status=UserStatus.ACTIVE, is_main_client=False, roles=[str(tech_employee_role.id)], client_account_id=str(tech_startup.id)
    ))
    await user_service.create_user(UserCreateSchema(
        email="dev2@techstartup.com", password="secure_password_123", first_name="Developer2", last_name="Tech",
        status=UserStatus.ACTIVE, is_main_client=False, roles=[str(tech_employee_role.id)], client_account_id=str(tech_startup.id)
    ))

    # Create test groups with direct permissions
    print("Creating test groups...")
    
    await group_service.create_group(
        group_data=GroupCreateSchema(
            name="acme_team",
            display_name="ACME Team", 
            description="ACME Corporation Team",
            permissions=["user:read_self", "group:read_own", "client:read_own"],  # Use self-access permission names
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
        ClientAccountCreateSchema(name="Hierarchical Real Estate Platform", is_platform_root=True)
    )
    platform2_client = await client_account_service.create_client_account(
        ClientAccountCreateSchema(name="Hierarchical CRM Platform", is_platform_root=True)
    )
    
    # Create platform-specific roles for Platform 1 (Real Estate)
    print("Creating platform-specific roles...")
    platform1_creator_role = await role_service.create_role(
        role_data=RoleCreateSchema(
            name="creator",
            display_name="Platform Creator",
            description="Can create sub-clients within their platform scope and access all platform clients.",
            permissions=[
                "user:manage_all", "user:add_member",
                "client:read_platform", "client:create_sub", "client:manage_platform",
                "group:manage_all", "group:manage_members",
                "role:read_all", "permission:read_all"
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
                "user:manage_client", "user:add_member",
                "client:read_platform", "client:read_created", "client:manage_platform",
                "group:manage_client", "group:manage_members",
                "role:read_client", "permission:read_client"
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
        status=UserStatus.ACTIVE, is_main_client=True, roles=[str(platform1_creator_role.id)], client_account_id=str(platform1_client.id)
    ))
    await user_service.create_user(UserCreateSchema(
        email="platform2.viewer@test.com", password="platform123", first_name="Platform2", last_name="Viewer",
        status=UserStatus.ACTIVE, is_main_client=True, roles=[str(platform2_viewer_role.id)], client_account_id=str(platform2_client.id)
    ))

    # Create sub-clients for platforms
    print("Creating sub-clients for platform testing...")
    acme_client = await client_account_service.create_client_account(
        ClientAccountCreateSchema(name="Hierarchical ACME Properties", description="Sub-client of Hierarchical Real Estate Platform"),
        created_by_client_id=str(platform1_client.id)
    )
    
    # Create client admin role for Hierarchical ACME Properties
    acme_admin_role = await role_service.create_role(
        role_data=RoleCreateSchema(
            name="admin",
            display_name="Client Administrator",
            description="Administrative role for Hierarchical ACME Properties - manages users and groups within client scope",
            permissions=["user:manage_client", "user:add_member",
                        "group:manage_client", "group:manage_members", "client:read_own"],
            scope=RoleScope.CLIENT,
            is_assignable_by_main_client=True
        ),
        current_user_id="system",
        scope_id=str(acme_client.id)
    )

    # Create users for sub-clients
    await user_service.create_user(UserCreateSchema(
        email="admin@hierarchical-acme.com", password="acme12345", first_name="John", last_name="ACME",
        status=UserStatus.ACTIVE, is_main_client=True, roles=[str(acme_admin_role.id)], client_account_id=str(acme_client.id)
    ))

    print("\n--- HIERARCHICAL Scenario Seeding Complete! ---")
    print("Test Users:")
    print("  - platform1.creator@test.com (Platform Creator)")
    print("  - platform2.viewer@test.com (Platform Viewer)")
    print("  - admin@hierarchical-acme.com (Client Admin)")


async def ensure_platform_permissions_exist(platform_id: str):
    """
    Ensure all essential PLATFORM permissions exist for a specific platform.
    """
    print(f"Ensuring essential platform permissions exist for platform {platform_id}...")
    created_count = 0

    # Define platform permissions inline since they're not imported
    platform_permissions = [
        PermissionCreateSchema(name="client:create_sub", display_name="Create Sub-Clients", description="Create sub-client accounts within platform scope", scope="platform"),
        PermissionCreateSchema(name="client:read_platform", display_name="Read Platform Clients", description="Read all clients within platform scope", scope="platform"),
        PermissionCreateSchema(name="client:read_created", display_name="Read Created Clients", description="Read only clients created by the user/platform", scope="platform")
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
    
    # Platform admin role with permission names
    platform_admin_permission_names = [
        "client:create", "client:read_platform", "client:manage_platform", 
        "client:create_sub", "client:read_created", "client:onboard",
        "analytics:view_platform", "support:cross_client",
        "user:manage_all", "user:add_member",
        "group:manage_all", "group:manage_members",
        "role:read_all", "permission:read_all"
    ]
    
    platform_admin_role = await role_service.create_role(
        role_data=RoleCreateSchema(
            name="admin",
            display_name="Platform Administrator",
            description="PropertyHub internal administrator",
            permissions=platform_admin_permission_names,  # Use permission names directly
            scope=RoleScope.PLATFORM,
            is_assignable_by_main_client=True
        ),
        current_user_id="system",
        scope_id=str(propertyhub_platform.id)
    )

    # Platform support role with permission names
    platform_support_permission_names = [
        "client:read_own", "client:read_platform", 
        "user:read_client", "group:read_client",
        "support:cross_client"
    ]
    
    platform_support_role = await role_service.create_role(
        role_data=RoleCreateSchema(
            name="support",
            display_name="Platform Support",
            description="PropertyHub customer success team",
            permissions=platform_support_permission_names,  # Use permission names directly
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
            permissions=["client:create", "client:read_platform", "client:read_created",
                        "user:read_client"],  # Use permission names directly
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
        status=UserStatus.ACTIVE, is_main_client=True, roles=[str(platform_admin_role.id)], 
        client_account_id=str(propertyhub_platform.id),
        is_platform_staff=True, platform_scope="all"
    ))
    
    await user_service.create_user(UserCreateSchema(
        email="support@propertyhub.com", password="platform123",
        first_name="Support", last_name="Team", 
        status=UserStatus.ACTIVE, is_main_client=False, roles=[str(platform_support_role.id)],
        client_account_id=str(propertyhub_platform.id),
        is_platform_staff=True, platform_scope="all"
    ))
    
    await user_service.create_user(UserCreateSchema(
        email="sales@propertyhub.com", password="platform123",
        first_name="Sales", last_name="Team",
        status=UserStatus.ACTIVE, is_main_client=False, roles=[str(platform_sales_role.id)],
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
            permissions=["user:manage_client", "user:add_member",
                        "group:manage_client", "group:manage_members",
                        "client:read_own"],
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
            permissions=["user:read_self", "group:read_own", "client:read_own"],
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
            permissions=["user:manage_client", "user:add_member",
                        "group:manage_client", "group:manage_members",
                        "client:read_own"],
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
            permissions=["user:read_self", "group:read_own", "client:read_own"],
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
            permissions=["user:manage_client", "user:add_member",
                        "group:manage_client", "group:manage_members",
                        "client:read_own"],
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
        status=UserStatus.ACTIVE, is_main_client=True, roles=[str(acme_admin_role.id)],
        client_account_id=str(acme_realestate.id)
    ))
    
    await user_service.create_user(UserCreateSchema(
        email="admin@eliteproperties.com", password="realestate123",
        first_name="Bob", last_name="Smith", 
        status=UserStatus.ACTIVE, is_main_client=True, roles=[str(elite_admin_role.id)],
        client_account_id=str(elite_properties.id)
    ))
    
    await user_service.create_user(UserCreateSchema(
        email="admin@downtownrealty.com", password="realestate123",
        first_name="Carol", last_name="Brown",
        status=UserStatus.ACTIVE, is_main_client=True, roles=[str(downtown_admin_role.id)],
        client_account_id=str(downtown_realty.id)
    ))

    # Create real estate agents for ACME Real Estate
    print("Creating real estate agents...")
    await user_service.create_user(UserCreateSchema(
        email="john.agent@acmerealestate.com", password="agent123",
        first_name="John", last_name="Agent",
        status=UserStatus.ACTIVE, is_main_client=False, roles=[str(acme_agent_role.id)],
        client_account_id=str(acme_realestate.id)
    ))
    
    await user_service.create_user(UserCreateSchema(
        email="sarah.manager@acmerealestate.com", password="agent123",
        first_name="Sarah", last_name="Manager",
        status=UserStatus.ACTIVE, is_main_client=False, roles=[str(acme_agent_role.id)], 
        client_account_id=str(acme_realestate.id)
    ))
    
    await user_service.create_user(UserCreateSchema(
        email="mike.assistant@acmerealestate.com", password="agent123",
        first_name="Mike", last_name="Assistant",
        status=UserStatus.ACTIVE, is_main_client=False, roles=[str(acme_agent_role.id)],
        client_account_id=str(acme_realestate.id)
    ))

    # Create agents for Elite Properties  
    await user_service.create_user(UserCreateSchema(
        email="luxury.agent@eliteproperties.com", password="agent123",
        first_name="Luxury", last_name="Agent",
        status=UserStatus.ACTIVE, is_main_client=False, roles=[str(elite_agent_role.id)],
        client_account_id=str(elite_properties.id)
    ))

    # Create PropertyHub team groups
    print("Creating PropertyHub platform groups...")
    await group_service.create_group(
        group_data=GroupCreateSchema(
            name="PropertyHub Internal Team",
            display_name="PropertyHub Internal Team", 
            description="PropertyHub platform staff",
            permissions=["client:read_platform", "user:read_client", "group:read_client"],  # Use permission names directly
            scope="platform"
        ),
        current_user_id="system",
        current_client_id=str(propertyhub_platform.id),
        scope_id=str(propertyhub_platform.id)  # Platform ID required for platform-scoped groups
    )

    # Create real estate company groups
    await group_service.create_group(
        group_data=GroupCreateSchema(
            name="ACME Sales Team",
            display_name="ACME Sales Team",
            description="ACME Real Estate sales team",
            permissions=["user:read_self", "group:read_own", "client:read_own"],  # Use permission names directly
            scope="client"
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