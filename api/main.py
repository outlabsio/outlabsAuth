from fastapi import FastAPI
from contextlib import asynccontextmanager
from .database import db, get_database
from .routes import user_routes, permission_routes, role_routes, auth_routes, client_account_routes, group_routes, platform_routes, settings_routes

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages the application's lifespan.
    Connects to the database on startup and disconnects on shutdown.
    Note: Permissions and roles are now created via seeding scripts rather than here.
    """
    await db.connect()
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
app.include_router(settings_routes.router, prefix="/v1/settings", tags=["Settings"])

@app.get("/health", tags=["Health"])
async def health_check():
    """
    Basic health check to confirm the service is running.
    """
    return {"status": "ok"}
