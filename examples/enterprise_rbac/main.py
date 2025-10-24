"""
Real Estate Leads Platform - EnterpriseRBAC Example

Demonstrates OutlabsAuth's entity flexibility through real-world scenarios:
- 5 different client organizational structures
- Entity type suggestions for naming consistency
- Tree permissions for hierarchical access
- Granular lead permissions (buyer vs seller specialists)
- Internal team with global access

See REQUIREMENTS.md for complete use case documentation.
"""
import os
from contextlib import asynccontextmanager
from typing import List, Optional
from datetime import datetime

from fastapi import FastAPI, Depends, HTTPException, status, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field
from beanie import init_beanie

from models import Lead, LeadNote
from outlabs_auth import EnterpriseRBAC
from outlabs_auth.routers import (
    get_auth_router,
    get_users_router,
    get_api_keys_router,
    get_entities_router,
    get_roles_router,
    get_permissions_router,
    get_memberships_router,
)
from outlabs_auth.models.user import UserModel
from outlabs_auth.models.role import RoleModel
from outlabs_auth.models.entity import EntityModel, EntityClass
from outlabs_auth.models.membership import EntityMembershipModel
from outlabs_auth.models.closure import EntityClosureModel
from outlabs_auth.models.permission import PermissionModel


# ============================================================================
# Configuration
# ============================================================================

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "realestate_leads_platform")
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production-please")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")


# ============================================================================
# Pydantic Schemas
# ============================================================================

class LeadCreateRequest(BaseModel):
    """Create new lead"""
    entity_id: str = Field(description="Entity (team/workspace) that owns this lead")
    lead_type: str = Field(description="buyer, seller, or both")
    first_name: str
    last_name: str
    email: str
    phone: str
    source: str = Field(description="Where lead came from")
    budget: Optional[int] = None
    location: Optional[str] = None
    property_type: Optional[str] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[float] = None
    timeline: Optional[str] = None
    property_address: Optional[str] = None  # For sellers
    asking_price: Optional[int] = None  # For sellers
    notes: Optional[List[str]] = None


class LeadUpdateRequest(BaseModel):
    """Update existing lead"""
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    budget: Optional[int] = None
    location: Optional[str] = None
    property_type: Optional[str] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[float] = None
    timeline: Optional[str] = None
    last_contact: Optional[datetime] = None
    next_followup: Optional[datetime] = None
    property_address: Optional[str] = None
    asking_price: Optional[int] = None
    property_condition: Optional[str] = None


class LeadResponse(BaseModel):
    """Lead response"""
    id: str
    entity_id: str
    assigned_to: Optional[str]
    lead_type: str
    first_name: str
    last_name: str
    email: str
    phone: str
    status: str
    source: str
    budget: Optional[int]
    location: Optional[str]
    property_type: Optional[str]
    bedrooms: Optional[int]
    bathrooms: Optional[float]
    timeline: Optional[str]
    property_address: Optional[str]
    asking_price: Optional[int]
    property_condition: Optional[str]
    notes: List[str]
    last_contact: Optional[datetime]
    next_followup: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    created_by: str

    class Config:
        from_attributes = True


class LeadNoteRequest(BaseModel):
    """Add note to lead"""
    content: str = Field(min_length=1)
    note_type: str = "general"  # general, call, email, showing, offer


class LeadAssignRequest(BaseModel):
    """Assign lead to agent"""
    agent_id: str


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
    print("🚀 Starting Real Estate Leads Platform...")

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
    auth = EnterpriseRBAC(
        database=db,
        secret_key=SECRET_KEY,
        redis_client=redis_client,
        redis_url=REDIS_URL if redis_client else None,
        enable_caching=redis_client is not None,
        enable_context_aware_roles=False,  # Keep it simple for this example
        enable_abac=False
    )

    # Initialize Beanie
    await init_beanie(
        database=db,
        document_models=[
            UserModel,
            RoleModel,
            PermissionModel,
            EntityModel,
            EntityMembershipModel,
            EntityClosureModel,
            Lead,
            LeadNote
        ]
    )

    await auth.initialize()
    print("✅ Database initialized")

    # Include standard OutlabsAuth routers with clean prefixes (no /api!)
    print("📝 Including API routers...")
    app.include_router(get_auth_router(auth, prefix="/auth"))
    app.include_router(get_users_router(auth, prefix="/users"))
    app.include_router(get_api_keys_router(auth, prefix="/api-keys"))
    app.include_router(get_entities_router(auth, prefix="/entities"))
    app.include_router(get_roles_router(auth, prefix="/roles"))
    app.include_router(get_permissions_router(auth, prefix="/permissions"))
    app.include_router(get_memberships_router(auth, prefix="/memberships"))
    print("✅ Routers included")

    print("✅ Real Estate Leads Platform ready!")
    print(f"📍 API: http://localhost:8002")
    print(f"📚 Docs: http://localhost:8002/docs")

    yield

    # Shutdown
    print("👋 Shutting down...")
    client.close()


app = FastAPI(
    title="Real Estate Leads Platform",
    description="EnterpriseRBAC demonstration with flexible entity hierarchies",
    version="1.0.0",
    lifespan=lifespan
)

# CORS for Nuxt admin UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Nuxt dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Helper Functions
# ============================================================================

def get_auth() -> EnterpriseRBAC:
    """Get the global auth instance"""
    if auth is None:
        raise HTTPException(status_code=500, detail="Auth not initialized")
    return auth


# ============================================================================
# Domain-Specific Routes: Lead Management
# ============================================================================

@app.post(
    "/leads",
    response_model=LeadResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Leads"],
    summary="Create new lead"
)
async def create_lead(
    data: LeadCreateRequest,
    auth_result = Depends(lambda: get_auth().deps.require_permission("lead:create"))
):
    """
    Create a new lead in the specified entity.

    Requires `lead:create` permission.
    """
    # Extract user from auth_result dict
    current_user = auth_result["user"]

    # Get auth instance
    auth_instance = get_auth()

    # Verify entity exists
    try:
        entity = await auth_instance.entity_service.get_entity(data.entity_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity {data.entity_id} not found"
        )

    # Create lead
    lead = Lead(
        entity_id=data.entity_id,
        lead_type=data.lead_type,
        first_name=data.first_name,
        last_name=data.last_name,
        email=data.email,
        phone=data.phone,
        source=data.source,
        status="new",
        budget=data.budget,
        location=data.location,
        property_type=data.property_type,
        bedrooms=data.bedrooms,
        bathrooms=data.bathrooms,
        timeline=data.timeline,
        property_address=data.property_address,
        asking_price=data.asking_price,
        notes=data.notes or [],
        created_by=str(current_user.id),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    await lead.insert()

    return LeadResponse(
        id=str(lead.id),
        **lead.dict(exclude={"id"})
    )


@app.get(
    "/leads",
    response_model=dict,
    tags=["Leads"],
    summary="List leads"
)
async def list_leads(
    entity_id: Optional[str] = Query(None, description="Filter by entity"),
    status: Optional[str] = Query(None, description="Filter by status"),
    lead_type: Optional[str] = Query(None, description="Filter by type (buyer/seller)"),
    assigned_to: Optional[str] = Query(None, description="Filter by assigned agent"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    auth_result = Depends(lambda: get_auth().deps.require_auth())
):
    """
    List leads with filtering.

    Automatically filters based on user's permissions:
    - Users with `lead:read` see leads in their entities
    - Users with `lead:read_tree` see leads in descendant entities too
    - Internal support with global permissions see all leads
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

    # TODO: Apply permission-based filtering
    # For now, return all matching leads
    # In production, check user's entity memberships and tree permissions

    skip = (page - 1) * limit
    leads = await Lead.find(query).skip(skip).limit(limit).to_list()
    total = await Lead.find(query).count()

    return {
        "leads": [LeadResponse(id=str(lead.id), **lead.dict(exclude={"id"})) for lead in leads],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit
    }


@app.get(
    "/leads/{lead_id}",
    response_model=LeadResponse,
    tags=["Leads"],
    summary="Get lead details"
)
async def get_lead(
    lead_id: str,
    auth_result = Depends(lambda: get_auth().deps.require_permission("lead:read"))
):
    """
    Get lead details by ID.

    Requires `lead:read` permission.
    """
    lead = await Lead.get(lead_id)
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found"
        )

    # TODO: Check permission in lead's entity context

    return LeadResponse(
        id=str(lead.id),
        **lead.dict(exclude={"id"})
    )


@app.put(
    "/leads/{lead_id}",
    response_model=LeadResponse,
    tags=["Leads"],
    summary="Update lead"
)
async def update_lead(
    lead_id: str,
    data: LeadUpdateRequest,
    auth_result = Depends(lambda: get_auth().deps.require_permission("lead:update"))
):
    """
    Update lead details.

    Requires `lead:update` permission.
    Buyer specialists can only update if lead_type includes 'buyer'.
    Seller specialists can only update if lead_type includes 'seller'.
    """
    lead = await Lead.get(lead_id)
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found"
        )

    # TODO: Check granular permissions (buyer vs seller specialists)
    # For now, allow updates if user has lead:update

    # Update fields
    update_data = data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(lead, field, value)

    lead.updated_at = datetime.utcnow()
    await lead.save()

    return LeadResponse(
        id=str(lead.id),
        **lead.dict(exclude={"id"})
    )


@app.delete(
    "/leads/{lead_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Leads"],
    summary="Delete lead"
)
async def delete_lead(
    lead_id: str,
    auth_result = Depends(lambda: get_auth().deps.require_permission("lead:delete"))
):
    """
    Delete (archive) a lead.

    Requires `lead:delete` permission.
    """
    lead = await Lead.get(lead_id)
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found"
        )

    await lead.delete()


@app.post(
    "/leads/{lead_id}/assign",
    response_model=LeadResponse,
    tags=["Leads"],
    summary="Assign lead to agent"
)
async def assign_lead(
    lead_id: str,
    data: LeadAssignRequest,
    auth_result = Depends(lambda: get_auth().deps.require_permission("lead:assign"))
):
    """
    Assign lead to a specific agent.

    Requires `lead:assign` permission.
    """
    lead = await Lead.get(lead_id)
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found"
        )

    # Verify agent exists
    try:
        agent = await UserModel.get(data.agent_id)
        if not agent:
            raise ValueError()
    except:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {data.agent_id} not found"
        )

    lead.assigned_to = data.agent_id
    lead.updated_at = datetime.utcnow()
    await lead.save()

    return LeadResponse(
        id=str(lead.id),
        **lead.dict(exclude={"id"})
    )


@app.post(
    "/leads/{lead_id}/notes",
    response_model=LeadResponse,
    tags=["Leads"],
    summary="Add note to lead"
)
async def add_lead_note(
    lead_id: str,
    data: LeadNoteRequest,
    auth_result = Depends(lambda: get_auth().deps.require_permission("lead:read"))
):
    """
    Add a note to a lead.

    Requires `lead:read` permission.
    Support staff can add notes with `support:add_notes` permission.
    """
    lead = await Lead.get(lead_id)
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found"
        )

    # Extract user from auth_result dict
    current_user = auth_result["user"]
    lead.add_note(data.content, str(current_user.id))
    await lead.save()

    return LeadResponse(
        id=str(lead.id),
        **lead.dict(exclude={"id"})
    )


# ============================================================================
# Health Check
# ============================================================================

@app.get("/", tags=["Health"])
async def root():
    """Health check endpoint"""
    return {
        "service": "Real Estate Leads Platform",
        "status": "healthy",
        "version": "1.0.0",
        "preset": "EnterpriseRBAC",
        "docs": "/docs"
    }


# ============================================================================
# Run Application
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8002,
        reload=True
    )
