"""
outlabsAuth API - Main Application
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from api.config import settings
from api.database import init_db, close_db
from api.services.email_service import email_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    try:
        await init_db()
        print("Database connected")
        
        # Start email worker
        await email_service.start_worker()
        print("Email service started")
    except Exception as e:
        print(f"Warning: Database connection failed: {e}")
        print("Running in limited mode without database")
    
    yield
    
    # Shutdown
    try:
        await close_db()
        print("Database disconnected")
    except:
        pass


# Create FastAPI app
app = FastAPI(
    title="outlabsAuth API",
    description="Unified Entity Model Authentication Platform",
    version="2.0.0",
    lifespan=lifespan
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if settings.ENVIRONMENT == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["api.auth.outlabs.com", "*.auth.outlabs.com"]
    )

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "2.0.0"}


# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "outlabsAuth API - Unified Entity Model",
        "version": "2.0.0",
        "docs": "/docs"
    }


# Import and include routers
from api.routes import test_routes, auth_routes, entity_routes, role_routes, user_routes, permission_routes, system_routes

# Test routes (remove in production)
app.include_router(test_routes.router, prefix="/v1/test", tags=["Testing"])

# Authentication routes
app.include_router(auth_routes.router, prefix="/v1/auth", tags=["Authentication"])

# Entity routes
app.include_router(entity_routes.router, prefix="/v1/entities", tags=["Entities"])

# Role routes
app.include_router(role_routes.router, prefix="/v1/roles", tags=["Roles"])

# User routes
app.include_router(user_routes.router, prefix="/v1/users", tags=["Users"])

# Permission routes
app.include_router(permission_routes.router, prefix="/v1/permissions", tags=["Permissions"])

# System routes
app.include_router(system_routes.router, prefix="/v1/system", tags=["System"])