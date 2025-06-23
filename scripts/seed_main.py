"""
Seed Script for Development and Comprehensive Testing

Purpose:
This script is designed for developers to populate the database with a rich set of
test data. It wipes the target database and creates a realistic multi-tenant environment,
including:
- Multiple client accounts (e.g., "ACME Corporation", "Tech Startup Inc").
- A super admin user with full system access.
- Various roles with different permission levels (e.g., "Client Admin", "Manager").
- Users within each client account.
- Groups with members.

This is the primary script to use during development to ensure all features
can be tested thoroughly.

Usage:
The script can target different databases using command-line arguments.

1. Seed the default test database (`outlabsAuth_test`):
   python scripts/seed_main.py

2. Seed a specific database by name:
   python scripts/seed_main.py --db my_custom_db_name

3. Seed the main production/staging database (`outlabsAuth`):
   python scripts/seed_main.py --prod

Note:
This script DELETES all existing data in the target database before seeding.
It is intended for development and testing environments. For initializing a
production environment, consider using `scripts/seed_super_admin.py`.
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
from api.schemas.role_schema import RoleCreateSchema
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
ESSENTIAL_PERMISSIONS = [
    PermissionCreateSchema(_id="user:create", description="Allows creating a single user."),
    PermissionCreateSchema(_id="user:read", description="Allows reading user information."),
    PermissionCreateSchema(_id="user:update", description="Allows updating a user."),
    PermissionCreateSchema(_id="user:delete", description="Allows deleting a user."),
    PermissionCreateSchema(_id="user:add_member", description="Allows adding a new user to one's own client account."),
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

SUPER_ADMIN_ROLE = RoleCreateSchema(
    _id="super_admin",
    name="Super Administrator",
    description="Grants complete system-wide access.",
    permissions=[p.id for p in ESSENTIAL_PERMISSIONS]
)

# New roles for hierarchical multi-platform tenancy
PLATFORM_CREATOR_ROLE = RoleCreateSchema(
    _id="platform_creator",
    name="Platform Creator",
    description="Can create sub-clients within their platform scope and access all platform clients.",
    permissions=[
        "user:read", "user:create", "user:update", "user:add_member",
        "client_account:read", "client_account:create_sub", "client_account:read_platform", "client_account:update",
        "group:read", "group:create", "group:update", "group:manage_members",
        "role:read", "permission:read"
    ]
)

PLATFORM_VIEWER_ROLE = RoleCreateSchema(
    _id="platform_viewer", 
    name="Platform Viewer",
    description="Can only view clients they created within their platform scope.",
    permissions=[
        "user:read", "user:create", "user:update", "user:add_member",
        "client_account:read", "client_account:read_created", "client_account:update",
        "group:read", "group:create", "group:update", "group:manage_members",
        "role:read", "permission:read"
    ]
)

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
    Seeds essential permissions and the super admin role.
    """
    # 2. Create permissions
    print("Creating essential permissions...")
    for perm_data in ESSENTIAL_PERMISSIONS:
        # Using a simple check to avoid errors if already exists
        if not await permission_service.get_permission_by_id(perm_data.id):
            await permission_service.create_permission(perm_data)
    print(f"{len(ESSENTIAL_PERMISSIONS)} permissions seeded.")

    # 3. Create super_admin role
    print("Creating super admin role...")
    if not await role_service.get_role_by_id(SUPER_ADMIN_ROLE.id):
        await role_service.create_role(SUPER_ADMIN_ROLE)
    print(f"Role '{SUPER_ADMIN_ROLE.id}' seeded.")


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
    admin_user_data = UserCreateSchema(
        email="admin@test.com",
        password="admin123",
        first_name="Admin",
        last_name="User",
        is_main_client=True,
        roles=["super_admin"],
        client_account_id=str(test_client.id)
    )
    await user_service.create_user(admin_user_data)
    print("Super admin user 'admin@test.com' created.")

    # Create additional roles for testing
    print("Creating additional test roles...")
    test_roles = [
        RoleCreateSchema(
            _id="client_admin", name="Client Administrator",
            description="Administrative role for client account",
            permissions=["user:create", "user:read", "user:update", "user:delete", "user:add_member", "group:create", "group:read", "group:update", "group:delete", "group:manage_members"],
            is_assignable_by_main_client=True
        ),
        RoleCreateSchema(
            _id="manager", name="Manager",
            description="Manager role with limited permissions",
            permissions=["user:read", "group:read", "group:update", "group:manage_members"],
            is_assignable_by_main_client=True
        ),
        RoleCreateSchema(
            _id="employee", name="Employee",
            description="Basic employee role",
            permissions=["user:read", "group:read"],
            is_assignable_by_main_client=True
        )
    ]
    for role_data in test_roles:
        if not await role_service.get_role_by_id(role_data.id):
            await role_service.create_role(role_data)
    print(f"{len(test_roles)} additional roles created.")

    # Create additional client accounts
    print("Creating additional client accounts...")
    acme_corp = await client_account_service.create_client_account(
        ClientAccountCreateSchema(name="ACME Corporation", description="Large enterprise client")
    )
    tech_startup = await client_account_service.create_client_account(
        ClientAccountCreateSchema(name="Tech Startup Inc", description="Small tech startup client")
    )

    # Create users for different client accounts
    print("Creating additional users...")
    await user_service.create_user(UserCreateSchema(
        email="admin@acme.com", password="admin123", first_name="Alice", last_name="Admin",
        is_main_client=True, roles=["client_admin"], client_account_id=str(acme_corp.id)
    ))
    await user_service.create_user(UserCreateSchema(
        email="manager@acme.com", password="manager123", first_name="Bob", last_name="Manager",
        is_main_client=False, roles=["manager"], client_account_id=str(acme_corp.id)
    ))
    await user_service.create_user(UserCreateSchema(
        email="admin@techstartup.com", password="admin123", first_name="Charlie", last_name="Founder",
        is_main_client=True, roles=["client_admin"], client_account_id=str(tech_startup.id)
    ))
    
    # Create employee users for ACME
    await user_service.create_user(UserCreateSchema(
        email="employee1@acme.com", password="secure_password_123", first_name="Employee1", last_name="Acme",
        is_main_client=False, roles=["employee"], client_account_id=str(acme_corp.id)
    ))
    await user_service.create_user(UserCreateSchema(
        email="employee2@acme.com", password="secure_password_123", first_name="Employee2", last_name="Acme",
        is_main_client=False, roles=["employee"], client_account_id=str(acme_corp.id)
    ))
    await user_service.create_user(UserCreateSchema(
        email="employee3@acme.com", password="secure_password_123", first_name="Employee3", last_name="Acme",
        is_main_client=False, roles=["employee"], client_account_id=str(acme_corp.id)
    ))
    
    # Create employee users for Tech Startup
    await user_service.create_user(UserCreateSchema(
        email="dev1@techstartup.com", password="secure_password_123", first_name="Developer1", last_name="Tech",
        is_main_client=False, roles=["employee"], client_account_id=str(tech_startup.id)
    ))
    await user_service.create_user(UserCreateSchema(
        email="dev2@techstartup.com", password="secure_password_123", first_name="Developer2", last_name="Tech",
        is_main_client=False, roles=["employee"], client_account_id=str(tech_startup.id)
    ))

    # Create test groups
    print("Creating test groups...")
    acme_users = await UserModel.find(UserModel.client_account.id == acme_corp.id).to_list()
    acme_user_ids = [str(u.id) for u in acme_users]
    await group_service.create_group(GroupCreateSchema(
        name="ACME Team", description="ACME Corporation Team",
        client_account_id=str(acme_corp.id), members=acme_user_ids
    ))
    
    print("\n--- COMPREHENSIVE Scenario Seeding Complete! ---")


async def seed_hierarchical_scenario():
    """
    Seeds data for testing hierarchical multi-platform tenancy.
    """
    print("\n--- Seeding: HIERARCHICAL Scenario ---")
    
    # Create platform-specific roles
    print("Creating platform-specific roles...")
    if not await role_service.get_role_by_id(PLATFORM_CREATOR_ROLE.id):
        await role_service.create_role(PLATFORM_CREATOR_ROLE)
    if not await role_service.get_role_by_id(PLATFORM_VIEWER_ROLE.id):
        await role_service.create_role(PLATFORM_VIEWER_ROLE)
    print("Platform roles 'platform_creator' and 'platform_viewer' seeded.")

    # Create platform root client accounts
    print("Creating platform root client accounts...")
    platform1_client = await client_account_service.create_client_account(
        ClientAccountCreateSchema(name="Real Estate Platform", is_platform_root=True)
    )
    platform2_client = await client_account_service.create_client_account(
        ClientAccountCreateSchema(name="CRM Platform", is_platform_root=True)
    )

    # Create platform admin users
    print("Creating platform admin users...")
    await user_service.create_user(UserCreateSchema(
        email="platform1.creator@test.com", password="platform123", first_name="Platform1", last_name="Creator",
        is_main_client=True, roles=["platform_creator"], client_account_id=str(platform1_client.id)
    ))
    await user_service.create_user(UserCreateSchema(
        email="platform2.viewer@test.com", password="platform123", first_name="Platform2", last_name="Viewer",
        is_main_client=True, roles=["platform_viewer"], client_account_id=str(platform2_client.id)
    ))

    # Create sub-clients for platforms
    print("Creating sub-clients for platform testing...")
    acme_client = await client_account_service.create_client_account(
        ClientAccountCreateSchema(name="ACME Properties", description="Sub-client of Real Estate Platform"),
        created_by_client_id=str(platform1_client.id)
    )
    
    # Create client_admin role if it doesn't exist
    if not await role_service.get_role_by_id("client_admin"):
        await role_service.create_role(RoleCreateSchema(
            _id="client_admin", name="Client Administrator", is_assignable_by_main_client=True,
            permissions=["user:read", "user:update"] # Basic permissions for this test
        ))

    # Create users for sub-clients
    await user_service.create_user(UserCreateSchema(
        email="admin@acme-properties.com", password="acme123", first_name="John", last_name="ACME",
        is_main_client=True, roles=["client_admin"], client_account_id=str(acme_client.id)
    ))

    print("\n--- HIERARCHICAL Scenario Seeding Complete! ---")
    print("Test Users:")
    print("  - platform1.creator@test.com (Platform Creator)")
    print("  - platform2.viewer@test.com (Platform Viewer)")
    print("  - admin@acme-properties.com (Client Admin)")


async def seed_propertyhub_scenario():
    """
    Seeds data for testing the PropertyHub three-tier SaaS platform model:
    1. PropertyHub Platform Staff (internal team)
    2. Real Estate Companies (clients)  
    3. Real Estate Agents (end users)
    """
    print("\n--- Seeding: PROPERTYHUB Scenario ---")
    
    # Create PropertyHub platform roles
    print("Creating PropertyHub platform roles...")
    platform_roles = [
        RoleCreateSchema(
            _id="platform_admin", name="Platform Administrator",
            description="PropertyHub internal administrator",
            permissions=["client_account:create", "client_account:read", "client_account:update", 
                        "user:create", "user:read", "user:update", "user:delete",
                        "group:create", "group:read", "group:update", "group:delete"],
            is_assignable_by_main_client=True
        ),
        RoleCreateSchema(
            _id="platform_support", name="Platform Support",
            description="PropertyHub customer success team",
            permissions=["client_account:read", "user:read", "group:read"],
            is_assignable_by_main_client=True
        ),
        RoleCreateSchema(
            _id="platform_sales", name="Platform Sales",
            description="PropertyHub sales team",
            permissions=["client_account:create", "client_account:read", "user:read"],
            is_assignable_by_main_client=True
        ),
        RoleCreateSchema(
            _id="real_estate_admin", name="Real Estate Company Admin",
            description="Real estate company administrator",
            permissions=["user:create", "user:read", "user:update", "user:add_member",
                        "group:create", "group:read", "group:update", "group:manage_members"],
            is_assignable_by_main_client=True
        ),
        RoleCreateSchema(
            _id="real_estate_agent", name="Real Estate Agent",
            description="Real estate agent or sales person",
            permissions=["user:read", "group:read"],
            is_assignable_by_main_client=True
        )
    ]
    
    for role_data in platform_roles:
        if not await role_service.get_role_by_id(role_data.id):
            await role_service.create_role(role_data)
    print(f"{len(platform_roles)} PropertyHub roles created.")

    # Create PropertyHub platform account
    print("Creating PropertyHub platform account...")
    propertyhub_platform = await client_account_service.create_client_account(
        ClientAccountCreateSchema(
            name="PropertyHub Platform", 
            description="PropertyHub SaaS platform for real estate management",
            is_platform_root=True
        )
    )
    
    # Create PropertyHub internal staff
    print("Creating PropertyHub internal staff...")
    await user_service.create_user(UserCreateSchema(
        email="admin@propertyhub.com", password="platform123", 
        first_name="Admin", last_name="PropertyHub",
        is_main_client=True, roles=["platform_admin"], 
        client_account_id=str(propertyhub_platform.id)
    ))
    
    await user_service.create_user(UserCreateSchema(
        email="support@propertyhub.com", password="platform123",
        first_name="Support", last_name="Team", 
        is_main_client=False, roles=["platform_support"],
        client_account_id=str(propertyhub_platform.id)
    ))
    
    await user_service.create_user(UserCreateSchema(
        email="sales@propertyhub.com", password="platform123",
        first_name="Sales", last_name="Team",
        is_main_client=False, roles=["platform_sales"],
        client_account_id=str(propertyhub_platform.id)
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

    # Create real estate company admins
    print("Creating real estate company admins...")
    await user_service.create_user(UserCreateSchema(
        email="admin@acmerealestate.com", password="realestate123",
        first_name="Alice", last_name="Johnson",
        is_main_client=True, roles=["real_estate_admin"],
        client_account_id=str(acme_realestate.id)
    ))
    
    await user_service.create_user(UserCreateSchema(
        email="admin@eliteproperties.com", password="realestate123",
        first_name="Bob", last_name="Smith", 
        is_main_client=True, roles=["real_estate_admin"],
        client_account_id=str(elite_properties.id)
    ))
    
    await user_service.create_user(UserCreateSchema(
        email="admin@downtownrealty.com", password="realestate123",
        first_name="Carol", last_name="Brown",
        is_main_client=True, roles=["real_estate_admin"],
        client_account_id=str(downtown_realty.id)
    ))

    # Create real estate agents for ACME Real Estate
    print("Creating real estate agents...")
    await user_service.create_user(UserCreateSchema(
        email="john.agent@acmerealestate.com", password="agent123",
        first_name="John", last_name="Agent",
        is_main_client=False, roles=["real_estate_agent"],
        client_account_id=str(acme_realestate.id)
    ))
    
    await user_service.create_user(UserCreateSchema(
        email="sarah.manager@acmerealestate.com", password="agent123",
        first_name="Sarah", last_name="Manager",
        is_main_client=False, roles=["real_estate_agent"], 
        client_account_id=str(acme_realestate.id)
    ))
    
    await user_service.create_user(UserCreateSchema(
        email="mike.assistant@acmerealestate.com", password="agent123",
        first_name="Mike", last_name="Assistant",
        is_main_client=False, roles=["real_estate_agent"],
        client_account_id=str(acme_realestate.id)
    ))

    # Create agents for Elite Properties  
    await user_service.create_user(UserCreateSchema(
        email="luxury.agent@eliteproperties.com", password="agent123",
        first_name="Luxury", last_name="Agent",
        is_main_client=False, roles=["real_estate_agent"],
        client_account_id=str(elite_properties.id)
    ))

    # Create PropertyHub team groups
    print("Creating PropertyHub platform groups...")
    platform_users = await UserModel.find(UserModel.client_account.id == propertyhub_platform.id).to_list()
    platform_user_ids = [str(u.id) for u in platform_users]
    await group_service.create_group(GroupCreateSchema(
        name="PropertyHub Internal Team", 
        description="PropertyHub platform staff",
        client_account_id=str(propertyhub_platform.id), 
        members=platform_user_ids,
        roles=["platform_admin"]
    ))

    # Create real estate company groups
    acme_users = await UserModel.find(UserModel.client_account.id == acme_realestate.id).to_list()
    acme_user_ids = [str(u.id) for u in acme_users]
    await group_service.create_group(GroupCreateSchema(
        name="ACME Sales Team",
        description="ACME Real Estate sales team",
        client_account_id=str(acme_realestate.id),
        members=acme_user_ids,
        roles=["real_estate_agent"]
    ))
    
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