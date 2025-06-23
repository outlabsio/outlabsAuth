import asyncio
import os
import sys
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
TEST_DB_NAME = "outlabs_auth_test"

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

# New roles for hierarchical multi-platform tenancy
PLATFORM_CREATOR_ROLE = RoleCreateSchema(
    _id="platform_creator",
    name="Platform Creator",
    description="Can create sub-clients within their platform scope and access all platform clients.",
    permissions=[
        "user:read", "user:create", "user:update", "user:create_sub",
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
        "user:read", "user:create", "user:update", "user:create_sub",
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


async def seed_database(db):
    """
    Connects to the test database, wipes it, and seeds it with essential data.
    """
    
    print(f"--- Seeding test database '{db.name}' ---")
    
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
    print("Beanie ODM initialized for seeding.")
    
    # Rebuild models to resolve circular references with proper namespace
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
    print("Model circular references resolved.")
    
    # 1. Wipe existing data using Beanie
    print("Wiping existing collections...")
    await UserModel.delete_all()
    await RoleModel.delete_all()
    await PermissionModel.delete_all()
    await ClientAccountModel.delete_all()
    await GroupModel.delete_all()
    print("Collections wiped.")

    # 2. Create permissions
    print("Creating essential permissions...")
    for perm_data in ESSENTIAL_PERMISSIONS:
        await permission_service.create_permission(perm_data)
    print(f"{len(ESSENTIAL_PERMISSIONS)} permissions created.")

    # 3. Create platform_admin role and new hierarchical roles
    print("Creating platform admin role...")
    await role_service.create_role(PLATFORM_ADMIN_ROLE)
    print(f"Role '{PLATFORM_ADMIN_ROLE.id}' created.")
    
    print("Creating platform creator role...")
    await role_service.create_role(PLATFORM_CREATOR_ROLE)
    print(f"Role '{PLATFORM_CREATOR_ROLE.id}' created.")
    
    print("Creating platform viewer role...")
    await role_service.create_role(PLATFORM_VIEWER_ROLE)
    print(f"Role '{PLATFORM_VIEWER_ROLE.id}' created.")

    # 4. Create test client account
    print("Creating test client account...")
    client_account = await client_account_service.create_client_account(TEST_CLIENT_ACCOUNT)
    print(f"Client account '{client_account.name}' created with ID: {client_account.id}")

    # 5. Create admin user with proper client account
    print("Creating admin user...")
    admin_user_data = UserCreateSchema(
        email="admin@test.com",
        password="a_very_secure_password",
        first_name="Admin",
        last_name="User",
        is_main_client=True,  # Make them a main client user
        roles=["platform_admin"],
        client_account_id=str(client_account.id)
    )
    admin_user = await user_service.create_user(admin_user_data)
    print(f"Admin user '{admin_user.email}' created.")

    # Additional roles for testing
    ADDITIONAL_ROLES = [
        RoleCreateSchema(_id="client_admin", name="Client Administrator", description="Administrator for a specific client account"),
        RoleCreateSchema(_id="manager", name="Manager", description="Management role with limited permissions"),
        RoleCreateSchema(_id="employee", name="Employee", description="Basic employee access")
    ]

    print("Creating additional test roles...")
    for role_data in ADDITIONAL_ROLES:
        await role_service.create_role(role_data)
        print(f"Role '{role_data.id}' created.")

    # 7. Create additional client accounts with hierarchical relationships
    print("Creating platform root client accounts...")
    
    # Platform 1: Real Estate Platform
    platform1_root = ClientAccountCreateSchema(
        name="Real Estate Platform Root",
        description="Root client for real estate platform",
        platform_id="real_estate_platform",
        is_platform_root=True
    )
    platform1_client = await client_account_service.create_client_account(platform1_root)
    print(f"Platform 1 root client '{platform1_client.name}' created with ID: {platform1_client.id}")

    # Platform 2: CRM Platform  
    platform2_root = ClientAccountCreateSchema(
        name="CRM Platform Root",
        description="Root client for CRM platform",
        platform_id="crm_platform", 
        is_platform_root=True
    )
    platform2_client = await client_account_service.create_client_account(platform2_root)
    print(f"Platform 2 root client '{platform2_client.name}' created with ID: {platform2_client.id}")

    # Create platform admin users
    print("Creating platform admin users...")
    
    # Platform 1 Creator Admin
    platform1_creator_data = UserCreateSchema(
        email="platform1.creator@test.com",
        password="platform123",
        first_name="Platform1",
        last_name="Creator",
        is_main_client=True,
        roles=["platform_creator"],
        client_account_id=str(platform1_client.id)
    )
    platform1_creator = await user_service.create_user(platform1_creator_data)
    print(f"Platform 1 creator '{platform1_creator.email}' created.")

    # Platform 2 Viewer Admin  
    platform2_viewer_data = UserCreateSchema(
        email="platform2.viewer@test.com",
        password="platform123",
        first_name="Platform2", 
        last_name="Viewer",
        is_main_client=True,
        roles=["platform_viewer"],
        client_account_id=str(platform2_client.id)
    )
    platform2_viewer = await user_service.create_user(platform2_viewer_data)
    print(f"Platform 2 viewer '{platform2_viewer.email}' created.")

    # Create sub-clients for platforms
    print("Creating sub-clients for platform testing...")
    
    # Sub-clients for Platform 1 (Real Estate)
    acme_properties = ClientAccountCreateSchema(
        name="ACME Properties",
        description="Real estate company under platform 1"
    )
    acme_client = await client_account_service.create_client_account(
        acme_properties, 
        created_by_client_id=str(platform1_client.id)
    )
    print(f"Sub-client 'ACME Properties' created under Platform 1")

    # Sub-clients for Platform 2 (CRM)
    tech_startup = ClientAccountCreateSchema(
        name="Tech Startup Inc",
        description="Technology startup using CRM platform"
    )
    tech_client = await client_account_service.create_client_account(
        tech_startup,
        created_by_client_id=str(platform2_client.id)
    )
    print(f"Sub-client 'Tech Startup Inc' created under Platform 2")

    # Create users for sub-clients
    print("Creating users for sub-clients...")
    
    # ACME Properties users
    acme_admin_data = UserCreateSchema(
        email="admin@acme-properties.com",
        password="acme123",
        first_name="John",
        last_name="ACME",
        is_main_client=True,
        roles=["client_admin"],
        client_account_id=str(acme_client.id)
    )
    await user_service.create_user(acme_admin_data)
    print("ACME Properties admin user created.")

    # Tech Startup users
    tech_admin_data = UserCreateSchema(
        email="admin@techstartup.com", 
        password="tech123",
        first_name="Jane",
        last_name="Tech",
        is_main_client=True,
        roles=["client_admin"],
        client_account_id=str(tech_client.id)
    )
    await user_service.create_user(tech_admin_data)
    print("Tech Startup admin user created.")

    print("\n--- Hierarchical Multi-Platform Tenancy Setup Complete! ---")
    print("Created:")
    print(f"  - {len(ESSENTIAL_PERMISSIONS)} permissions (including new platform-scoped)")
    print(f"  - 6 roles (including platform_creator and platform_viewer)")
    print(f"  - 5 client accounts (1 original + 2 platform roots + 2 sub-clients)")
    print(f"  - Platform relationships and hierarchical permissions")
    print("  - Platform admin users with scoped access")
    print("  - Real-world multi-platform test scenario")
    print("\nTest Users:")
    print("  - admin@test.com (Super Admin) - Full system access")
    print("  - platform1.creator@test.com (Platform Creator) - Can create sub-clients, see all in platform")
    print("  - platform2.viewer@test.com (Platform Viewer) - Can only see clients they created") 
    print("  - admin@acme-properties.com (Client Admin) - Real estate platform sub-client")
    print("  - admin@techstartup.com (Client Admin) - CRM platform sub-client")
    print("Now you can test the hierarchical multi-platform tenancy system!")


if __name__ == "__main__":
    # When running as a script, create our own client
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[TEST_DB_NAME]
    asyncio.run(seed_database(db))
    client.close() 