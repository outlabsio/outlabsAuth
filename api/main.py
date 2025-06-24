from fastapi import FastAPI
from contextlib import asynccontextmanager
from .database import db, get_database
from .routes import user_routes, permission_routes, role_routes, auth_routes, client_account_routes, group_routes, platform_routes
from .services.permission_service import permission_service
from .schemas.permission_schema import PermissionCreateSchema
from .services.role_service import role_service
from .schemas.role_schema import RoleCreateSchema

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages the application's lifespan.
    Connects to the database on startup, ensures essential permissions exist,
    and disconnects on shutdown.
    """
    await db.connect()

    # Ensure essential permissions exist (Beanie ODM doesn't require db_session parameter)
    all_permission_ids = []
    essential_permissions = [
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
        PermissionCreateSchema(_id="client_account:create_sub", description="Allows creating sub-clients within platform scope."),
        PermissionCreateSchema(_id="client_account:read_platform", description="Allows reading all clients within platform scope."),
        PermissionCreateSchema(_id="client_account:read_created", description="Allows reading only clients you created."),
        PermissionCreateSchema(_id="group:create", description="Allows creating a group."),
        PermissionCreateSchema(_id="group:read", description="Allows reading group information."),
        PermissionCreateSchema(_id="group:update", description="Allows updating a group."),
        PermissionCreateSchema(_id="group:delete", description="Allows deleting a group."),
        PermissionCreateSchema(_id="group:manage_members", description="Allows adding/removing members from groups."),
        # Platform-specific permissions for PropertyHub three-tier model
        PermissionCreateSchema(_id="platform:manage_clients", description="Allows managing client accounts across the platform."),
        PermissionCreateSchema(_id="platform:view_analytics", description="Allows viewing platform-wide analytics and metrics."),
        PermissionCreateSchema(_id="platform:support_users", description="Allows providing support to users across all clients."),
        PermissionCreateSchema(_id="platform:onboard_clients", description="Allows onboarding new clients to the platform."),
    ]

    for perm_data in essential_permissions:
        all_permission_ids.append(perm_data.id)
        existing_perm = await permission_service.get_permission_by_id(perm_data.id)
        if not existing_perm:
            await permission_service.create_permission(perm_data)

    # Ensure essential roles exist
    essential_roles = [
        # Super Admin Role
        RoleCreateSchema(
            _id="super_admin",
            name="Super Administrator",
            description="Grants complete system-wide access.",
            permissions=all_permission_ids
        ),
        # Client Admin Role - for managing users within a client organization  
        RoleCreateSchema(
            _id="client_admin",
            name="Client Administrator",
            description="Administrative access for managing users, groups, and roles within a client organization",
            permissions=[
                "user:create", "user:read", "user:update", "user:delete", "user:add_member",
                "group:create", "group:read", "group:update", "group:delete", "group:manage_members",
                "role:create", "role:read", "role:update", "role:delete",
                "permission:read", "client_account:read"
            ],
            is_assignable_by_main_client=True
        ),
        # Platform Admin Role - for platform-level administration
        RoleCreateSchema(
            _id="platform_admin",
            name="Platform Administrator", 
            description="Administrative access for managing platform-level operations and multiple client accounts",
            permissions=[
                "user:create", "user:read", "user:update", "user:delete", "user:add_member", "user:bulk_create",
                "role:create", "role:read", "role:update", "role:delete",
                "permission:create", "permission:read",
                "client_account:create", "client_account:read", "client_account:update", "client_account:delete",
                "client_account:create_sub", "client_account:read_platform", "client_account:read_created",
                "group:create", "group:read", "group:update", "group:delete", "group:manage_members"
            ],
            is_assignable_by_main_client=False
        ),
        # Basic User Role - for standard users with minimal permissions
        RoleCreateSchema(
            _id="basic_user",
            name="Basic User",
            description="Standard user with basic read permissions",
            permissions=["user:read", "group:read", "client_account:read"],
            is_assignable_by_main_client=True
        )
    ]

    for role_data in essential_roles:
        existing_role = await role_service.get_role_by_id(role_data.id)
        if not existing_role:
            await role_service.create_role(role_data)
        else:
            # Update existing role to ensure it has current permissions and settings
            from .schemas.role_schema import RoleUpdateSchema
            update_data = RoleUpdateSchema(
                name=role_data.name,
                description=role_data.description,
                permissions=role_data.permissions,
                is_assignable_by_main_client=role_data.is_assignable_by_main_client
            )
            await role_service.update_role(role_data.id, update_data)

    yield
    await db.close()

app = FastAPI(
    title="Outlabs RBAC Microservice",
    description="A standalone, generic Role-Based Access Control (RBAC) microservice.",
    version="0.1.0",
    lifespan=lifespan
)

app.include_router(auth_routes.router)
app.include_router(user_routes.router)
app.include_router(permission_routes.router)
app.include_router(role_routes.router)
app.include_router(client_account_routes.router)
app.include_router(group_routes.router)
app.include_router(platform_routes.router)

@app.get("/health", tags=["Health"])
async def health_check():
    """
    Basic health check to confirm the service is running.
    """
    return {"status": "ok"}
