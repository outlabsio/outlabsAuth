from fastapi import FastAPI
from contextlib import asynccontextmanager
from .database import db, get_database
from .routes import user_routes, permission_routes, role_routes, auth_routes, client_account_routes
from .services.permission_service import permission_service
from .schemas.permission_schema import PermissionCreateSchema

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages the application's lifespan.
    Connects to the database on startup, ensures essential permissions exist,
    and disconnects on shutdown.
    """
    await db.connect()
    
    # Ensure essential permissions exist
    db_session = db.db # Get the database session directly
    
    essential_permissions = [
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
    
    for perm_data in essential_permissions:
        existing_perm = await permission_service.get_permission_by_id(db_session, perm_data.id)
        if not existing_perm:
            await permission_service.create_permission(db_session, perm_data)

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

@app.get("/health", tags=["Health"])
async def health_check():
    """
    Basic health check to confirm the service is running.
    """
    return {"status": "ok"} 