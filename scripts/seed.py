import asyncio
import os
import sys
from motor.motor_asyncio import AsyncIOMotorClient

# Add the project root to the Python path to allow importing from 'api'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.services.user_service import user_service
from api.services.role_service import role_service
from api.services.permission_service import permission_service
from api.schemas.user_schema import UserCreateSchema
from api.schemas.role_schema import RoleCreateSchema
from api.schemas.permission_schema import PermissionCreateSchema

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
]

PLATFORM_ADMIN_ROLE = RoleCreateSchema(
    _id="platform_admin",
    name="Platform Administrator",
    description="Grants all permissions in the system.",
    permissions=[p.id for p in ESSENTIAL_PERMISSIONS]
)

ADMIN_USER = UserCreateSchema(
    email="admin@test.com",
    password="a_very_secure_password",
    first_name="Admin",
    last_name="User",
    is_main_client=False,
    roles=["platform_admin"]
)


async def seed_database(db):
    """
    Connects to the test database, wipes it, and seeds it with essential data.
    """
    
    print(f"--- Seeding test database '{db.name}' ---")
    
    # 1. Wipe existing data
    print("Wiping existing collections...")
    await db.users.delete_many({})
    await db.roles.delete_many({})
    await db.permissions.delete_many({})
    print("Collections wiped.")

    # 2. Create permissions
    print("Creating essential permissions...")
    for perm_data in ESSENTIAL_PERMISSIONS:
        await permission_service.create_permission(db, perm_data)
    print(f"{len(ESSENTIAL_PERMISSIONS)} permissions created.")

    # 3. Create platform_admin role
    print("Creating platform admin role...")
    await role_service.create_role(db, PLATFORM_ADMIN_ROLE)
    print(f"Role '{PLATFORM_ADMIN_ROLE.id}' created.")

    # 4. Create admin user
    print("Creating admin user...")
    await user_service.create_user(db, ADMIN_USER)
    print(f"Admin user '{ADMIN_USER.email}' created.")

    print("\n--- Seeding complete! ---")


if __name__ == "__main__":
    # When running as a script, create our own client
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[TEST_DB_NAME]
    asyncio.run(seed_database(db))
    client.close() 