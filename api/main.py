from fastapi import FastAPI
from contextlib import asynccontextmanager
from .database import db
from .routes import user_routes

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages the application's lifespan.
    Connects to the database on startup and disconnects on shutdown.
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

app.include_router(user_routes.router)

@app.get("/health", tags=["Health"])
async def health_check():
    """
    Basic health check to confirm the service is running.
    """
    return {"status": "ok"} 