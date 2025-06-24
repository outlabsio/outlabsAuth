from fastapi import FastAPI
from contextlib import asynccontextmanager
from .database import db, get_database
from .routes import user_routes, permission_routes, role_routes, auth_routes, client_account_routes, group_routes, platform_routes
from .services.permission_service import permission_service
from .schemas.permission_schema import PermissionCreateSchema
from .services.role_service import role_service
from .schemas.role_schema import RoleCreateSchema, RoleScope
from .models.role_model import RoleModel

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
        # Super Admin Role (System Scope)
        {
            "name": "super_admin",
            "display_name": "Super Administrator",
            "description": "Grants complete system-wide access.",
            "permissions": all_permission_ids,
            "scope": RoleScope.SYSTEM,
            "scope_id": None,
            "is_assignable_by_main_client": False
        },
        # Basic User Role (System Scope) 
        {
            "name": "basic_user",
            "display_name": "Basic User",
            "description": "Basic user access with minimal permissions",
            "permissions": ["user:read"],
            "scope": RoleScope.SYSTEM,
            "scope_id": None,
            "is_assignable_by_main_client": True
        }
    ]
    
    for role_data in essential_roles:
        # Check if role exists (by name and scope)
        existing_role = await RoleModel.find_one(
            RoleModel.name == role_data["name"],
            RoleModel.scope == role_data["scope"],
            RoleModel.scope_id == role_data["scope_id"]
        )
        
        if not existing_role:
            # Create new role
            role = RoleModel(**role_data)
            await role.insert()
        else:
            # Update existing role permissions
            existing_role.display_name = role_data["display_name"]
            existing_role.description = role_data["description"]
            existing_role.permissions = role_data["permissions"]
            existing_role.is_assignable_by_main_client = role_data["is_assignable_by_main_client"]
            await existing_role.save()

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
