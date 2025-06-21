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

    # 3. Create platform_admin role
    print("Creating platform admin role...")
    await role_service.create_role(PLATFORM_ADMIN_ROLE)
    print(f"Role '{PLATFORM_ADMIN_ROLE.id}' created.")

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

    # 6. Create additional roles for testing
    print("Creating additional test roles...")
    test_roles = [
        RoleCreateSchema(
            _id="client_admin",
            name="Client Administrator",
            description="Administrative role for client account",
            permissions=["user:create", "user:read", "user:update", "user:delete", "user:create_sub", "group:create", "group:read", "group:update", "group:delete", "group:manage_members"],
            is_assignable_by_main_client=True
        ),
        RoleCreateSchema(
            _id="manager",
            name="Manager",
            description="Manager role with limited permissions",
            permissions=["user:read", "group:read", "group:update", "group:manage_members"],
            is_assignable_by_main_client=True
        ),
        RoleCreateSchema(
            _id="employee",
            name="Employee",
            description="Basic employee role",
            permissions=["user:read", "group:read"],
            is_assignable_by_main_client=True
        )
    ]
    
    for role_data in test_roles:
        await role_service.create_role(role_data)
        print(f"Role '{role_data.id}' created.")

    # 7. Create additional client accounts
    print("Creating additional client accounts...")
    acme_corp = await client_account_service.create_client_account(
        ClientAccountCreateSchema(
            name="ACME Corporation",
            description="Large enterprise client"
        )
    )
    print(f"Client account '{acme_corp.name}' created with ID: {acme_corp.id}")

    tech_startup = await client_account_service.create_client_account(
        ClientAccountCreateSchema(
            name="Tech Startup Inc",
            description="Small tech startup client"
        )
    )
    print(f"Client account '{tech_startup.name}' created with ID: {tech_startup.id}")

    # 8. Create users for different client accounts
    print("Creating additional users...")
    
    # ACME Corporation users
    acme_admin = await user_service.create_user(UserCreateSchema(
        email="admin@acme.com",
        password="secure_password_123",
        first_name="John",
        last_name="Admin",
        is_main_client=True,
        roles=["client_admin"],
        client_account_id=str(acme_corp.id)
    ))
    print(f"ACME admin user '{acme_admin.email}' created.")

    acme_manager = await user_service.create_user(UserCreateSchema(
        email="manager@acme.com",
        password="secure_password_123",
        first_name="Jane",
        last_name="Manager",
        is_main_client=False,
        roles=["manager"],
        client_account_id=str(acme_corp.id)
    ))
    print(f"ACME manager user '{acme_manager.email}' created.")

    acme_employees = []
    for i in range(1, 4):
        employee = await user_service.create_user(UserCreateSchema(
            email=f"employee{i}@acme.com",
            password="secure_password_123",
            first_name=f"Employee{i}",
            last_name="Acme",
            is_main_client=False,
            roles=["employee"],
            client_account_id=str(acme_corp.id)
        ))
        acme_employees.append(employee)
        print(f"ACME employee '{employee.email}' created.")

    # Tech Startup users
    startup_admin = await user_service.create_user(UserCreateSchema(
        email="admin@techstartup.com",
        password="secure_password_123",
        first_name="Alice",
        last_name="Tech",
        is_main_client=True,
        roles=["client_admin"],
        client_account_id=str(tech_startup.id)
    ))
    print(f"Startup admin user '{startup_admin.email}' created.")

    startup_employees = []
    for i in range(1, 3):
        employee = await user_service.create_user(UserCreateSchema(
            email=f"dev{i}@techstartup.com",
            password="secure_password_123",
            first_name=f"Developer{i}",
            last_name="Tech",
            is_main_client=False,
            roles=["employee"],
            client_account_id=str(tech_startup.id)
        ))
        startup_employees.append(employee)
        print(f"Startup employee '{employee.email}' created.")

    # 9. Create groups for testing
    print("Creating test groups...")
    
    # ACME groups
    acme_dev_group = await group_service.create_group(GroupCreateSchema(
        name="Development Team",
        description="ACME development team",
        client_account_id=str(acme_corp.id),
        roles=["employee"],
        members=[str(acme_employees[0].id), str(acme_employees[1].id)]
    ))
    print(f"ACME Development Team group created with ID: {acme_dev_group.id}")

    acme_mgmt_group = await group_service.create_group(GroupCreateSchema(
        name="Management Team",
        description="ACME management team",
        client_account_id=str(acme_corp.id),
        roles=["manager"],
        members=[str(acme_manager.id)]
    ))
    print(f"ACME Management Team group created with ID: {acme_mgmt_group.id}")

    # Tech Startup groups
    startup_all_group = await group_service.create_group(GroupCreateSchema(
        name="All Hands",
        description="Everyone at the startup",
        client_account_id=str(tech_startup.id),
        roles=["employee"],
        members=[str(startup_employees[0].id), str(startup_employees[1].id)]
    ))
    print(f"Startup All Hands group created with ID: {startup_all_group.id}")

    print(f"\n--- Enhanced seeding complete! ---")
    print(f"Created:")
    print(f"  - {len(ESSENTIAL_PERMISSIONS)} permissions")
    print(f"  - {len(test_roles) + 1} roles") 
    print(f"  - 3 client accounts")
    print(f"  - 8 users across different organizations")
    print(f"  - 3 groups with members")
    print(f"Now you have real data to test with!")


if __name__ == "__main__":
    # When running as a script, create our own client
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[TEST_DB_NAME]
    asyncio.run(seed_database(db))
    client.close() 