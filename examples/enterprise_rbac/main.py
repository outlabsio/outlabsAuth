"""
Real Estate Platform API - EnterpriseRBAC Example

Demonstrates OutlabsAuth's EnterpriseRBAC preset for hierarchical entity-based access control.

This example shows:
- Entity hierarchy (Organization → Region → Office → Team)
- Tree permissions (hierarchical access control)
- Entity memberships (users can have multiple roles in different entities)
- Real estate domain with leads and notes
- Context-aware permissions

See REQUIREMENTS.md for complete use case documentation.
"""

import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import List, Optional

from beanie import init_beanie
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from models import Lead, LeadNote
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field

from outlabs_auth import EnterpriseRBAC
from outlabs_auth.models.api_key import APIKeyModel
from outlabs_auth.models.closure import EntityClosureModel
from outlabs_auth.models.entity import EntityModel
from outlabs_auth.models.membership import EntityMembershipModel
from outlabs_auth.models.permission import PermissionModel
from outlabs_auth.models.role import RoleModel
from outlabs_auth.models.user import UserModel
from outlabs_auth.observability import (
    CorrelationIDMiddleware,
    ObservabilityConfig,
    ObservabilityPresets,
    create_metrics_router,
)
from outlabs_auth.routers import (
    get_api_keys_router,
    get_auth_router,
    get_entities_router,
    get_memberships_router,
    get_permissions_router,
    get_roles_router,
    get_users_router,
)
from outlabs_auth.services.user import UserService

# ============================================================================
# Custom User Service with Password Reset Hooks
# ============================================================================


class RealEstateUserService(UserService):
    """
    Custom UserService with password reset hooks for email notifications.

    In a production app, these hooks would send actual emails.
    For development, we just print the reset links to console.
    """

    async def on_after_forgot_password(
        self, user: UserModel, token: str, request: Optional[any] = None
    ) -> None:
        """Send password reset email to user."""
        reset_link = f"http://localhost:3000/reset-password?token={token}"

        print("\n" + "=" * 80)
        print("📧 PASSWORD RESET EMAIL (Development Mode)")
        print("=" * 80)
        print(f"To: {user.email}")
        print(f"Subject: Reset your password")
        print(f"\nClick the link below to reset your password:")
        print(f"\n{reset_link}")
        print(f"\nThis link will expire in 1 hour.")
        print("=" * 80 + "\n")

    async def on_after_reset_password(
        self, user: UserModel, request: Optional[any] = None
    ) -> None:
        """Send password reset confirmation email."""
        print("\n" + "=" * 80)
        print("✅ PASSWORD RESET CONFIRMATION (Development Mode)")
        print("=" * 80)
        print(f"To: {user.email}")
        print(f"Subject: Password reset successful")
        print(f"\nYour password has been successfully reset.")
        print(f"If you didn't make this change, please contact support immediately.")
        print("=" * 80 + "\n")


# ============================================================================
# Configuration
# ============================================================================

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27018")
DATABASE_NAME = os.getenv("DATABASE_NAME", "realestate_enterprise_rbac")
SECRET_KEY = os.getenv(
    "SECRET_KEY", "enterprise-rbac-secret-change-in-production-please"
)
REDIS_URL = os.getenv("REDIS_URL", None)


# ============================================================================
# Pydantic Schemas
# ============================================================================


class LeadCreateRequest(BaseModel):
    """Create new lead"""

    entity_id: str = Field(description="Entity (team/office) that owns this lead")
    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)
    email: str
    phone: str
    lead_type: str = Field(description="buyer, seller, or both")
    status: str = Field(
        default="new",
        description="new, contacted, qualified, showing, offer, closed, dead",
    )
    source: str = Field(description="Website, referral, Zillow, etc.")
    budget: Optional[int] = None
    location: Optional[str] = None
    property_type: Optional[str] = None
    assigned_to: Optional[str] = Field(None, description="Agent user_id")


class LeadUpdateRequest(BaseModel):
    """Update existing lead"""

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[str] = None
    budget: Optional[int] = None
    location: Optional[str] = None
    property_type: Optional[str] = None
    assigned_to: Optional[str] = None


class LeadResponse(BaseModel):
    """Lead response"""

    id: str
    entity_id: str
    first_name: str
    last_name: str
    email: str
    phone: str
    lead_type: str
    status: str
    source: str
    budget: Optional[int]
    location: Optional[str]
    property_type: Optional[str]
    assigned_to: Optional[str]
    created_by: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# Global Variables
# ============================================================================

# Auth instance (initialized in lifespan)
auth: Optional[EnterpriseRBAC] = None


# ============================================================================
# FastAPI Application
# ============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global auth

    # Startup
    print("🚀 Starting Real Estate API (EnterpriseRBAC) v1.0.0...")

    # Connect to MongoDB
    print("📦 Connecting to MongoDB...")
    client = AsyncIOMotorClient(MONGODB_URL)
    db = client[DATABASE_NAME]

    # Connect to Redis (if available)
    redis_client = None
    if REDIS_URL:
        try:
            print("📮 Connecting to Redis...")
            import redis.asyncio as redis

            redis_client = redis.from_url(REDIS_URL, decode_responses=True)
            # Test connection
            await redis_client.ping()
            print(f"✅ Redis connected: {REDIS_URL}")
        except Exception as e:
            print(f"⚠️  Redis connection failed: {e}")
            print("   Continuing without caching...")
            redis_client = None

    # Initialize EnterpriseRBAC
    print("🔐 Initializing OutlabsAuth EnterpriseRBAC...")
    env = os.getenv("ENV", "development")
    if env == "production":
        obs_config = ObservabilityPresets.production()
    else:
        obs_config = ObservabilityPresets.development()
        obs_config.enable_metrics = True

    auth = EnterpriseRBAC(
        database=db,
        secret_key=SECRET_KEY,
        access_token_expire_minutes=480,  # 8 hours for dev (default: 15 min)
        refresh_token_expire_days=7,  # 7 days for dev (default: 30 days)
        redis_client=redis_client,
        redis_url=REDIS_URL if redis_client else None,
        enable_caching=redis_client is not None,
        observability_config=obs_config,
    )

    # Initialize Beanie with all document models
    await init_beanie(
        database=db,
        document_models=[
            UserModel,
            RoleModel,
            PermissionModel,
            APIKeyModel,
            EntityModel,
            EntityClosureModel,
            EntityMembershipModel,
            Lead,
            LeadNote,
        ],
    )

    await auth.initialize()
    print("✅ Database initialized")

    # Replace user service with custom one
    auth.user_service = RealEstateUserService(
        database=db, config=auth.config, notification_service=auth.notification_service
    )
    print("✅ Custom user service with password reset hooks enabled")

    # Include standard OutlabsAuth routers with /v1 prefix
    print("📝 Including API routers...")
    app.include_router(get_auth_router(auth, prefix="/v1/auth"))
    app.include_router(get_users_router(auth, prefix="/v1/users"))
    app.include_router(get_api_keys_router(auth, prefix="/v1/api-keys"))
    app.include_router(get_roles_router(auth, prefix="/v1/roles"))
    app.include_router(get_permissions_router(auth, prefix="/v1/permissions"))
    app.include_router(get_entities_router(auth, prefix="/v1/entities"))
    app.include_router(get_memberships_router(auth, prefix="/v1/memberships"))

    # Include observability metrics endpoint
    app.include_router(create_metrics_router(auth.observability))

    print("✅ Routers included (including /metrics for Prometheus)")
    print("✅ Real Estate API (EnterpriseRBAC) started successfully")
    print(f"📦 Database: {DATABASE_NAME}")
    print(f"📍 API: http://localhost:8004")
    print(f"📚 Docs: http://localhost:8004/docs")

    yield

    # Shutdown
    print("👋 Shutting down...")
    await auth.shutdown()
    client.close()
    print("✅ Real Estate API shutdown complete")


app = FastAPI(
    title="Real Estate API - EnterpriseRBAC Example",
    description="Demonstrates OutlabsAuth EnterpriseRBAC with hierarchical entities and tree permissions",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Note: CorrelationIDMiddleware is added during lifespan startup
# Cannot add here because auth is not yet initialized


# ============================================================================
# Helper Functions
# ============================================================================


def get_auth() -> EnterpriseRBAC:
    """Get the global auth instance"""
    if auth is None:
        raise HTTPException(status_code=500, detail="Auth not initialized")
    return auth


# ============================================================================
# Domain-Specific Routes: Leads
# ============================================================================


@app.post(
    "/v1/leads",
    response_model=LeadResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Leads"],
    summary="Create new lead",
)
async def create_lead(
    data: LeadCreateRequest,
    current_user: UserModel = Depends(lambda: get_auth().deps.requires("lead:create")),
):
    """
    Create a new lead.

    Requires `lead:create` permission in the target entity.
    """
    # Create lead
    lead = Lead(
        entity_id=data.entity_id,
        first_name=data.first_name,
        last_name=data.last_name,
        email=data.email,
        phone=data.phone,
        lead_type=data.lead_type,
        status=data.status,
        source=data.source,
        budget=data.budget,
        location=data.location,
        property_type=data.property_type,
        assigned_to=data.assigned_to,
        created_by=str(current_user.id),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    await lead.insert()

    return LeadResponse(id=str(lead.id), **lead.dict(exclude={"id"}))


@app.get("/v1/leads", response_model=dict, tags=["Leads"], summary="List leads")
async def list_leads(
    entity_id: Optional[str] = Query(None, description="Filter by entity"),
    status: Optional[str] = Query(None, description="Filter by status"),
    lead_type: Optional[str] = Query(None, description="Filter by type"),
    assigned_to: Optional[str] = Query(None, description="Filter by agent"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: UserModel = Depends(lambda: get_auth().deps.requires("lead:read")),
):
    """
    List leads.

    Returns leads based on user's entity memberships and permissions.
    Users with `lead:read_tree` can see leads from descendant entities.
    """
    # Build query
    query = {}

    if entity_id:
        query["entity_id"] = entity_id
    if status:
        query["status"] = status
    if lead_type:
        query["lead_type"] = lead_type
    if assigned_to:
        query["assigned_to"] = assigned_to

    # Paginate
    skip = (page - 1) * limit
    leads = await Lead.find(query).skip(skip).limit(limit).to_list()
    total = await Lead.find(query).count()

    return {
        "leads": [
            LeadResponse(id=str(lead.id), **lead.dict(exclude={"id"})) for lead in leads
        ],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit,
    }


@app.get(
    "/v1/leads/{lead_id}",
    response_model=LeadResponse,
    tags=["Leads"],
    summary="Get lead details",
)
async def get_lead(
    lead_id: str,
    current_user: UserModel = Depends(lambda: get_auth().deps.requires("lead:read")),
):
    """
    Get lead details.

    Requires `lead:read` permission in the lead's entity.
    """
    lead = await Lead.get(lead_id)
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found"
        )

    return LeadResponse(id=str(lead.id), **lead.dict(exclude={"id"}))


@app.put(
    "/v1/leads/{lead_id}",
    response_model=LeadResponse,
    tags=["Leads"],
    summary="Update lead",
)
async def update_lead(
    lead_id: str,
    data: LeadUpdateRequest,
    current_user: UserModel = Depends(lambda: get_auth().deps.requires("lead:update")),
):
    """
    Update lead.

    Requires `lead:update` permission in the lead's entity.
    """
    lead = await Lead.get(lead_id)
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found"
        )

    # Update fields
    update_data = data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(lead, field, value)

    lead.updated_at = datetime.now(UTC)
    await lead.save()

    return LeadResponse(id=str(lead.id), **lead.dict(exclude={"id"}))


@app.delete(
    "/v1/leads/{lead_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Leads"],
    summary="Delete lead",
)
async def delete_lead(
    lead_id: str,
    current_user: UserModel = Depends(lambda: get_auth().deps.requires("lead:delete")),
):
    """
    Delete lead.

    Requires `lead:delete` permission in the lead's entity.
    """
    lead = await Lead.get(lead_id)
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found"
        )

    await lead.delete()


# ============================================================================
# Health Check
# ============================================================================


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {
        "service": "Real Estate API - EnterpriseRBAC Example",
        "status": "healthy",
        "version": "1.0.0",
        "preset": "EnterpriseRBAC",
        "docs": "/docs",
    }


@app.get("/v1/auth/config", tags=["Auth"], summary="Get auth configuration")
async def get_auth_config():
    """
    Get authentication system configuration.

    Returns preset type, feature flags, and available permissions.
    This allows the admin UI to adapt to the backend's capabilities.
    """
    return {
        "preset": "EnterpriseRBAC",
        "features": {
            "entity_hierarchy": True,
            "context_aware_roles": True,
            "abac": False,
            "tree_permissions": True,
            "api_keys": True,
            "user_status": True,
            "activity_tracking": True,
        },
        "available_permissions": [
            # User permissions
            {
                "value": "user:read",
                "label": "User Read",
                "category": "Users",
                "description": "View user information",
            },
            {
                "value": "user:read_tree",
                "label": "User Read (Tree)",
                "category": "Users",
                "description": "View users in entity and all descendants",
            },
            {
                "value": "user:create",
                "label": "User Create",
                "category": "Users",
                "description": "Create new users",
            },
            {
                "value": "user:update",
                "label": "User Update",
                "category": "Users",
                "description": "Update user information",
            },
            {
                "value": "user:delete",
                "label": "User Delete",
                "category": "Users",
                "description": "Delete users",
            },
            # Entity permissions
            {
                "value": "entity:read",
                "label": "Entity Read",
                "category": "Entities",
                "description": "View entity information",
            },
            {
                "value": "entity:read_tree",
                "label": "Entity Read (Tree)",
                "category": "Entities",
                "description": "View entity and all descendants",
            },
            {
                "value": "entity:create",
                "label": "Entity Create",
                "category": "Entities",
                "description": "Create new entities",
            },
            {
                "value": "entity:update",
                "label": "Entity Update",
                "category": "Entities",
                "description": "Update entity information",
            },
            {
                "value": "entity:delete",
                "label": "Entity Delete",
                "category": "Entities",
                "description": "Delete entities",
            },
            # Lead permissions
            {
                "value": "lead:read",
                "label": "Lead Read",
                "category": "Leads",
                "description": "View leads in entity",
            },
            {
                "value": "lead:read_tree",
                "label": "Lead Read (Tree)",
                "category": "Leads",
                "description": "View leads in entity and all descendants",
            },
            {
                "value": "lead:create",
                "label": "Lead Create",
                "category": "Leads",
                "description": "Create new leads",
            },
            {
                "value": "lead:update",
                "label": "Lead Update",
                "category": "Leads",
                "description": "Update lead information",
            },
            {
                "value": "lead:delete",
                "label": "Lead Delete",
                "category": "Leads",
                "description": "Delete leads",
            },
            # Role permissions
            {
                "value": "role:read",
                "label": "Role Read",
                "category": "Roles",
                "description": "View roles",
            },
            {
                "value": "role:create",
                "label": "Role Create",
                "category": "Roles",
                "description": "Create new roles",
            },
            {
                "value": "role:update",
                "label": "Role Update",
                "category": "Roles",
                "description": "Update roles",
            },
            {
                "value": "role:delete",
                "label": "Role Delete",
                "category": "Roles",
                "description": "Delete roles",
            },
            # Permission permissions
            {
                "value": "permission:read",
                "label": "Permission Read",
                "category": "Permissions",
                "description": "View permissions",
            },
            {
                "value": "permission:create",
                "label": "Permission Create",
                "category": "Permissions",
                "description": "Create new permissions",
            },
            {
                "value": "permission:update",
                "label": "Permission Update",
                "category": "Permissions",
                "description": "Update permissions",
            },
            {
                "value": "permission:delete",
                "label": "Permission Delete",
                "category": "Permissions",
                "description": "Delete permissions",
            },
            # API Key permissions
            {
                "value": "api_key:read",
                "label": "API Key Read",
                "category": "API Keys",
                "description": "View API keys",
            },
            {
                "value": "api_key:create",
                "label": "API Key Create",
                "category": "API Keys",
                "description": "Create API keys",
            },
            {
                "value": "api_key:revoke",
                "label": "API Key Revoke",
                "category": "API Keys",
                "description": "Revoke API keys",
            },
        ],
    }


# ============================================================================
# Run Application
# ============================================================================

if __name__ == "__main__":
    from pathlib import Path

    import uvicorn

    # Watch both the example directory and the library code
    project_root = Path(__file__).parent.parent.parent
    reload_dirs = [
        str(Path(__file__).parent),  # examples/enterprise_rbac
        str(project_root / "outlabs_auth"),  # library code
    ]

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8004,
        reload=True,
        reload_dirs=reload_dirs,
    )
