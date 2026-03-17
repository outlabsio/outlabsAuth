"""
Real Estate Platform API - EnterpriseRBAC Example

Demonstrates OutlabsAuth's EnterpriseRBAC preset for hierarchical entity-based access control.
Uses PostgreSQL for database storage.

This example shows:
- Entity hierarchy (Organization -> Region -> Office -> Team)
- Tree permissions (hierarchical access control)
- Entity memberships (users can have multiple roles in different entities)
- Real estate domain with leads and notes
- Context-aware permissions

See REQUIREMENTS.md for complete use case documentation.
"""

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from models import Lead, LeadNote
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel

from outlabs_auth import EnterpriseRBAC
from outlabs_auth.middleware.resource_context import ResourceContextMiddleware
from outlabs_auth.models.sql.user import User
from outlabs_auth.observability import ObservabilityPresets
from outlabs_auth.routers import (
    get_api_keys_router,
    get_auth_router,
    get_config_router,
    get_entities_router,
    get_memberships_router,
    get_permissions_router,
    get_roles_router,
    get_users_router,
)
from outlabs_auth.services.user import UserService

# ============================================================================
# Configuration
# ============================================================================

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/realestate_enterprise_rbac",
)
SECRET_KEY = os.getenv(
    "SECRET_KEY", "enterprise-rbac-secret-change-in-production-please"
)
REDIS_URL = os.getenv("REDIS_URL", None)


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
        self, user: User, token: str, request: Optional[any] = None
    ) -> None:
        """Send password reset email to user."""
        reset_link = f"http://localhost:3000/reset-password?token={token}"

        print("\n" + "=" * 80)
        print("PASSWORD RESET EMAIL (Development Mode)")
        print("=" * 80)
        print(f"To: {user.email}")
        print(f"Subject: Reset your password")
        print(f"\nClick the link below to reset your password:")
        print(f"\n{reset_link}")
        print(f"\nThis link will expire in 1 hour.")
        print("=" * 80 + "\n")

    async def on_after_reset_password(
        self, user: User, request: Optional[any] = None
    ) -> None:
        """Send password reset confirmation email."""
        print("\n" + "=" * 80)
        print("PASSWORD RESET CONFIRMATION (Development Mode)")
        print("=" * 80)
        print(f"To: {user.email}")
        print(f"Subject: Password reset successful")
        print(f"\nYour password has been successfully reset.")
        print(f"If you didn't make this change, please contact support immediately.")
        print("=" * 80 + "\n")


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
    print("Starting Real Estate API (EnterpriseRBAC) v1.0.0...")

    # Connect to Redis (if available)
    redis_client = None
    if REDIS_URL:
        try:
            print("Connecting to Redis...")
            import redis.asyncio as redis

            redis_client = redis.from_url(REDIS_URL, decode_responses=True)
            # Test connection
            await redis_client.ping()
            print(f"Redis connected: {REDIS_URL}")
        except Exception as e:
            print(f"Redis connection failed: {e}")
            print("Continuing without caching...")
            redis_client = None

    # Initialize EnterpriseRBAC
    print("Initializing OutlabsAuth EnterpriseRBAC...")
    env = os.getenv("ENV", "development")
    if env == "production":
        obs_config = ObservabilityPresets.production()
    else:
        obs_config = ObservabilityPresets.development()
        obs_config.enable_metrics = True

    auth = EnterpriseRBAC(
        database_url=DATABASE_URL,
        secret_key=SECRET_KEY,
        access_token_expire_minutes=480,  # 8 hours for dev (default: 15 min)
        refresh_token_expire_days=7,  # 7 days for dev (default: 30 days)
        redis_client=redis_client,
        redis_url=REDIS_URL if redis_client else None,
        enable_caching=redis_client is not None,
        enable_abac=True,
        observability_config=obs_config,
    )

    await auth.initialize()

    # Create tables (including domain models)
    print("Creating database tables...")
    async with auth.engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    print("Database tables created")

    # Replace user service with custom one
    auth.user_service = RealEstateUserService(config=auth.config)
    print("Custom user service with password reset hooks enabled")

    # Install observability middleware, exception handlers, and /metrics (if enabled)
    auth.instrument_fastapi(
        app,
        debug=(env != "production"),
        exception_handler_mode="global",
        include_metrics=True,
        include_correlation_id=True,
        include_resource_context=True,
    )

    # Include standard OutlabsAuth routers with /v1 prefix
    print("Including API routers...")
    app.include_router(get_auth_router(auth, prefix="/v1/auth"))
    app.include_router(get_users_router(auth, prefix="/v1/users"))
    app.include_router(get_api_keys_router(auth, prefix="/v1/api-keys"))
    app.include_router(get_roles_router(auth, prefix="/v1/roles"))
    app.include_router(get_permissions_router(auth, prefix="/v1/permissions"))
    app.include_router(get_entities_router(auth, prefix="/v1/entities"))
    app.include_router(get_memberships_router(auth, prefix="/v1/memberships"))
    app.include_router(get_config_router(auth, prefix="/v1/config"))

    print("Routers included (including /metrics for Prometheus)")
    print("Real Estate API (EnterpriseRBAC) started successfully")
    print(
        f"Database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else DATABASE_URL}"
    )
    print(f"API: http://localhost:8004")
    print(f"Docs: http://localhost:8004/docs")

    yield

    # Shutdown
    print("Shutting down...")
    await auth.shutdown()
    print("Real Estate API shutdown complete")


app = FastAPI(
    title="Real Estate API - EnterpriseRBAC Example",
    description="Demonstrates OutlabsAuth EnterpriseRBAC with hierarchical entities and tree permissions",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Resource context middleware for ABAC (must be added at module level, before app starts)
app.add_middleware(ResourceContextMiddleware)


# ============================================================================
# Helper Functions
# ============================================================================


def get_auth() -> EnterpriseRBAC:
    """Get the global auth instance"""
    if auth is None:
        raise HTTPException(status_code=500, detail="Auth not initialized")
    return auth


async def get_session(request: Request):
    """Get database session from auth.uow"""
    async for session in get_auth().uow(request):
        yield session


def _lead_to_response(lead: Lead) -> LeadResponse:
    """Convert Lead model to response"""
    return LeadResponse(
        id=str(lead.id),
        entity_id=str(lead.entity_id),
        first_name=lead.first_name,
        last_name=lead.last_name,
        email=lead.email,
        phone=lead.phone,
        lead_type=lead.lead_type,
        status=lead.status,
        source=lead.source,
        budget=lead.budget,
        location=lead.location,
        property_type=lead.property_type,
        assigned_to=str(lead.assigned_to) if lead.assigned_to else None,
        created_by=str(lead.created_by),
        created_at=lead.created_at,
        updated_at=lead.updated_at,
    )


# ============================================================================
# Domain-Specific Routes: Leads
# ============================================================================


async def require_lead_create(
    request: Request, session: AsyncSession = Depends(get_session)
):
    """Dependency for lead:create permission in entity context."""
    # Use require_entity_permission which reads X-Entity-Context header
    dep_fn = get_auth().deps.require_entity_permission("lead:create")
    return await dep_fn(request=request, session=session)


async def require_lead_read(
    request: Request, session: AsyncSession = Depends(get_session)
):
    """Dependency for lead:read permission"""
    dep_fn = get_auth().deps.require_permission("lead:read")
    return await dep_fn(request=request, session=session)


async def require_lead_update(
    request: Request, session: AsyncSession = Depends(get_session)
):
    """Dependency for lead:update permission"""
    dep_fn = get_auth().deps.require_permission("lead:update")
    return await dep_fn(request=request, session=session)


async def require_lead_delete(
    request: Request, session: AsyncSession = Depends(get_session)
):
    """Dependency for lead:delete permission"""
    dep_fn = get_auth().deps.require_permission("lead:delete")
    return await dep_fn(request=request, session=session)


@app.post(
    "/v1/leads",
    response_model=LeadResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Leads"],
    summary="Create new lead",
)
async def create_lead(
    data: LeadCreateRequest,
    request: Request,
    auth_result: dict = Depends(require_lead_create),
    session: AsyncSession = Depends(get_session),
):
    """
    Create a new lead.

    Requires `lead:create` permission in the target entity.
    """
    user = auth_result.get("user")

    # Create lead
    lead = Lead(
        entity_id=UUID(data.entity_id),
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
        assigned_to=UUID(data.assigned_to) if data.assigned_to else None,
        created_by=user.id,
    )

    session.add(lead)
    await session.commit()
    await session.refresh(lead)

    return _lead_to_response(lead)


@app.get("/v1/leads", response_model=dict, tags=["Leads"], summary="List leads")
async def list_leads(
    request: Request,
    entity_id: Optional[str] = Query(None, description="Filter by entity"),
    lead_status: Optional[str] = Query(None, description="Filter by status"),
    lead_type: Optional[str] = Query(None, description="Filter by type"),
    assigned_to: Optional[str] = Query(None, description="Filter by agent"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    auth_result: dict = Depends(require_lead_read),
    session: AsyncSession = Depends(get_session),
):
    """
    List leads.

    Returns leads based on user's entity memberships and permissions.
    Users with `lead:read_tree` can see leads from descendant entities.
    """
    # Build query filters
    filters = []

    if entity_id:
        filters.append(Lead.entity_id == UUID(entity_id))
    if lead_status:
        filters.append(Lead.status == lead_status)
    if lead_type:
        filters.append(Lead.lead_type == lead_type)
    if assigned_to:
        filters.append(Lead.assigned_to == UUID(assigned_to))

    # Get total count
    count_stmt = select(func.count()).select_from(Lead)
    if filters:
        count_stmt = count_stmt.where(*filters)
    count_result = await session.execute(count_stmt)
    total = count_result.scalar() or 0

    # Get paginated results
    skip = (page - 1) * limit
    stmt = select(Lead).offset(skip).limit(limit)
    if filters:
        stmt = stmt.where(*filters)
    result = await session.execute(stmt)
    leads = result.scalars().all()

    return {
        "leads": [_lead_to_response(lead) for lead in leads],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit if total > 0 else 0,
    }


@app.get(
    "/v1/leads/{lead_id}",
    response_model=LeadResponse,
    tags=["Leads"],
    summary="Get lead details",
)
async def get_lead(
    lead_id: str,
    request: Request,
    auth_result: dict = Depends(require_lead_read),
    session: AsyncSession = Depends(get_session),
):
    """
    Get lead details.

    Requires `lead:read` permission in the lead's entity.
    """
    lead = await session.get(Lead, UUID(lead_id))
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found"
        )

    return _lead_to_response(lead)


@app.put(
    "/v1/leads/{lead_id}",
    response_model=LeadResponse,
    tags=["Leads"],
    summary="Update lead",
)
async def update_lead(
    lead_id: str,
    data: LeadUpdateRequest,
    request: Request,
    auth_result: dict = Depends(require_lead_update),
    session: AsyncSession = Depends(get_session),
):
    """
    Update lead.

    Requires `lead:update` permission in the lead's entity.
    """
    lead = await session.get(Lead, UUID(lead_id))
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found"
        )

    # Update fields
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "assigned_to" and value:
            setattr(lead, field, UUID(value))
        else:
            setattr(lead, field, value)

    lead.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(lead)

    return _lead_to_response(lead)


@app.delete(
    "/v1/leads/{lead_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Leads"],
    summary="Delete lead",
)
async def delete_lead(
    lead_id: str,
    request: Request,
    auth_result: dict = Depends(require_lead_delete),
    session: AsyncSession = Depends(get_session),
):
    """
    Delete lead.

    Requires `lead:delete` permission in the lead's entity.
    """
    lead = await session.get(Lead, UUID(lead_id))
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found"
        )

    await session.delete(lead)
    await session.commit()


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
            "invitations": True,
        },
        "available_permissions": [
            # User permissions
            {"value": "user:read", "label": "User Read", "category": "Users"},
            {
                "value": "user:read_tree",
                "label": "User Read (Tree)",
                "category": "Users",
            },
            {"value": "user:create", "label": "User Create", "category": "Users"},
            {"value": "user:update", "label": "User Update", "category": "Users"},
            {"value": "user:delete", "label": "User Delete", "category": "Users"},
            # Entity permissions
            {"value": "entity:read", "label": "Entity Read", "category": "Entities"},
            {
                "value": "entity:read_tree",
                "label": "Entity Read (Tree)",
                "category": "Entities",
            },
            {
                "value": "entity:create",
                "label": "Entity Create",
                "category": "Entities",
            },
            {
                "value": "entity:update",
                "label": "Entity Update",
                "category": "Entities",
            },
            {
                "value": "entity:delete",
                "label": "Entity Delete",
                "category": "Entities",
            },
            # Lead permissions
            {"value": "lead:read", "label": "Lead Read", "category": "Leads"},
            {
                "value": "lead:read_tree",
                "label": "Lead Read (Tree)",
                "category": "Leads",
            },
            {"value": "lead:create", "label": "Lead Create", "category": "Leads"},
            {"value": "lead:update", "label": "Lead Update", "category": "Leads"},
            {"value": "lead:delete", "label": "Lead Delete", "category": "Leads"},
            # Role permissions
            {"value": "role:read", "label": "Role Read", "category": "Roles"},
            {"value": "role:create", "label": "Role Create", "category": "Roles"},
            {"value": "role:update", "label": "Role Update", "category": "Roles"},
            {"value": "role:delete", "label": "Role Delete", "category": "Roles"},
            # Permission permissions
            {
                "value": "permission:read",
                "label": "Permission Read",
                "category": "Permissions",
            },
            {
                "value": "permission:create",
                "label": "Permission Create",
                "category": "Permissions",
            },
            {
                "value": "permission:update",
                "label": "Permission Update",
                "category": "Permissions",
            },
            {
                "value": "permission:delete",
                "label": "Permission Delete",
                "category": "Permissions",
            },
            # API Key permissions
            {"value": "api_key:read", "label": "API Key Read", "category": "API Keys"},
            {
                "value": "api_key:create",
                "label": "API Key Create",
                "category": "API Keys",
            },
            {
                "value": "api_key:revoke",
                "label": "API Key Revoke",
                "category": "API Keys",
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
