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
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlencode, urlparse
from uuid import UUID

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from models import Lead, LeadNote
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel

from outlabs_auth import EnterpriseRBAC, register_exception_handlers
from outlabs_auth.middleware.resource_context import ResourceContextMiddleware
from outlabs_auth.models.sql.user import User
from outlabs_auth.observability import ObservabilityPresets, create_metrics_router
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

EXAMPLE_DIR = Path(__file__).parent


def _load_example_env() -> None:
    env_path = EXAMPLE_DIR / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _trim_trailing_slash(value: str) -> str:
    return value.rstrip("/")


def _extract_origin(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return value


_load_example_env()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/realestate_enterprise_rbac",
)
SECRET_KEY = os.getenv("SECRET_KEY", "enterprise-rbac-secret-change-in-production-please")
REDIS_URL = os.getenv("REDIS_URL", None)
ENV = os.getenv("ENV", "development")
DEBUG_MODE = ENV != "production"
FRONTEND_URL = _trim_trailing_slash(os.getenv("FRONTEND_URL", "http://localhost:3000"))
MAILGUN_API_BASE_URL = _trim_trailing_slash(os.getenv("MAILGUN_API_BASE_URL", "https://api.mailgun.net"))
MAILGUN_DOMAIN = os.getenv("MAILGUN_DOMAIN")
MAILGUN_API_KEY = os.getenv("MAILGUN_API_KEY")
MAILGUN_FROM_EMAIL = os.getenv("MAILGUN_FROM_EMAIL")
MAILGUN_FROM_NAME = os.getenv("MAILGUN_FROM_NAME", "Outlabs Auth")
MAILGUN_RECIPIENT_OVERRIDE = os.getenv("MAILGUN_RECIPIENT_OVERRIDE")
FRONTEND_ORIGIN = _extract_origin(FRONTEND_URL)


# ============================================================================
# Custom User Service with Password Reset Hooks
# ============================================================================


class RealEstateUserService(UserService):
    """
    Custom UserService with password reset hooks for email notifications.

    In a production app, these hooks would send actual emails.
    For development, the service uses Mailgun when configured and falls back to
    printing the links to console if delivery is unavailable.
    """

    def __init__(
        self,
        *,
        config,
        frontend_url: str,
        notification_service=None,
        auth_service=None,
        membership_service=None,
        role_service=None,
        api_key_service=None,
        user_audit_service=None,
        mailgun_api_base_url: Optional[str] = None,
        mailgun_domain: Optional[str] = None,
        mailgun_api_key: Optional[str] = None,
        mailgun_from_email: Optional[str] = None,
        mailgun_from_name: str = "Outlabs Auth",
        mailgun_recipient_override: Optional[str] = None,
    ):
        super().__init__(
            config=config,
            notification_service=notification_service,
            auth_service=auth_service,
            membership_service=membership_service,
            role_service=role_service,
            api_key_service=api_key_service,
            user_audit_service=user_audit_service,
        )
        self.frontend_url = _trim_trailing_slash(frontend_url)
        self.mailgun_api_base_url = _trim_trailing_slash(
            mailgun_api_base_url or "https://api.mailgun.net"
        )
        self.mailgun_domain = mailgun_domain
        self.mailgun_api_key = mailgun_api_key
        self.mailgun_from_email = mailgun_from_email
        self.mailgun_from_name = mailgun_from_name
        self.mailgun_recipient_override = mailgun_recipient_override

    def _build_frontend_link(self, path: str, token: str) -> str:
        query = urlencode({"token": token})
        return f"{self.frontend_url}{path}?{query}"

    def _format_from_address(self) -> str:
        if self.mailgun_from_name:
            return f"{self.mailgun_from_name} <{self.mailgun_from_email}>"
        return self.mailgun_from_email or "Outlabs Auth"

    async def _send_notification_email(
        self,
        *,
        intended_recipient: str,
        subject: str,
        text: str,
        fallback_title: str,
    ) -> None:
        actual_recipient = self.mailgun_recipient_override or intended_recipient
        message_text = text

        if actual_recipient != intended_recipient:
            message_text = (
                f"Intended recipient: {intended_recipient}\n"
                f"Sandbox override recipient: {actual_recipient}\n\n{text}"
            )

        if self.mailgun_domain and self.mailgun_api_key and self.mailgun_from_email:
            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    response = await client.post(
                        f"{self.mailgun_api_base_url}/v3/{self.mailgun_domain}/messages",
                        auth=("api", self.mailgun_api_key),
                        data={
                            "from": self._format_from_address(),
                            "to": actual_recipient,
                            "subject": subject,
                            "text": message_text,
                        },
                    )
                    response.raise_for_status()

                print("\n" + "=" * 80)
                print("MAILGUN EMAIL SENT")
                print("=" * 80)
                print(f"Subject: {subject}")
                print(f"Intended recipient: {intended_recipient}")
                print(f"Delivered to: {actual_recipient}")
                print("=" * 80 + "\n")
                return
            except Exception as exc:
                print("\n" + "=" * 80)
                print("MAILGUN DELIVERY FAILED - FALLING BACK TO CONSOLE OUTPUT")
                print("=" * 80)
                print(f"Subject: {subject}")
                print(f"Intended recipient: {intended_recipient}")
                print(f"Attempted recipient: {actual_recipient}")
                print(f"Error: {exc}")
                print("=" * 80 + "\n")

        print("\n" + "=" * 80)
        print(fallback_title)
        print("=" * 80)
        print(f"To: {intended_recipient}")
        print(f"Subject: {subject}")
        print(f"\n{message_text}")
        print("=" * 80 + "\n")

    async def on_after_forgot_password(self, user: User, token: str, request: Optional[any] = None) -> None:
        """Send password reset email to user."""
        reset_link = self._build_frontend_link("/auth/reset-password", token)
        await self._send_notification_email(
            intended_recipient=user.email,
            subject="Reset your password",
            text=(
                "Click the link below to reset your password:\n\n"
                f"{reset_link}\n\n"
                "This link will expire in 1 hour."
            ),
            fallback_title="PASSWORD RESET EMAIL (Development Mode)",
        )

    async def on_after_reset_password(self, user: User, request: Optional[any] = None) -> None:
        """Send password reset confirmation email."""
        await self._send_notification_email(
            intended_recipient=user.email,
            subject="Password reset successful",
            text=(
                "Your password has been successfully reset.\n\n"
                "If you didn't make this change, please contact support immediately."
            ),
            fallback_title="PASSWORD RESET CONFIRMATION (Development Mode)",
        )

    async def on_after_invite(self, user: User, token: str, request: Optional[Request] = None) -> None:
        """Send invite email with accept-invite link."""
        accept_link = self._build_frontend_link("/auth/accept-invite", token)
        recipient_name = " ".join(part for part in [user.first_name, user.last_name] if part) or user.email

        await self._send_notification_email(
            intended_recipient=user.email,
            subject="You're invited to Outlabs Auth",
            text=(
                f"Hello {recipient_name},\n\n"
                "You've been invited to Outlabs Auth.\n\n"
                "Click the link below to accept your invitation and set your password:\n\n"
                f"{accept_link}\n\n"
                "This invite link will expire in 7 days."
            ),
            fallback_title="INVITE EMAIL (Development Mode)",
        )


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


def _ensure_example_tables(sync_conn) -> None:
    """Create example-owned tables without re-touching migrated auth tables."""
    SQLModel.metadata.create_all(
        sync_conn,
        tables=[Lead.__table__, LeadNote.__table__],
    )


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
    if ENV == "production":
        obs_config = ObservabilityPresets.production()
    else:
        obs_config = ObservabilityPresets.development()
        obs_config.enable_metrics = True

    auth = EnterpriseRBAC(
        database_url=DATABASE_URL,
        secret_key=SECRET_KEY,
        auto_migrate=True,
        access_token_expire_minutes=480,  # 8 hours for dev (default: 15 min)
        refresh_token_expire_days=7,  # 7 days for dev (default: 30 days)
        redis_client=redis_client,
        redis_url=REDIS_URL if redis_client else None,
        enable_caching=redis_client is not None,
        enable_context_aware_roles=True,
        enable_abac=True,
        observability_config=obs_config,
    )

    await auth.initialize()

    # Create example-owned domain tables only. Auth tables come from migrations.
    print("Ensuring example domain tables exist...")
    async with auth.engine.begin() as conn:
        await conn.run_sync(_ensure_example_tables)
    print("Example domain tables ready")

    # Replace user service with custom one
    base_user_service = auth.user_service
    auth.user_service = RealEstateUserService(
        config=auth.config,
        frontend_url=FRONTEND_URL,
        notification_service=base_user_service.notifications if base_user_service else None,
        auth_service=base_user_service.auth_service if base_user_service else None,
        membership_service=base_user_service.membership_service if base_user_service else None,
        role_service=base_user_service.role_service if base_user_service else None,
        api_key_service=base_user_service.api_key_service if base_user_service else None,
        user_audit_service=base_user_service.user_audit_service if base_user_service else None,
        mailgun_api_base_url=MAILGUN_API_BASE_URL,
        mailgun_domain=MAILGUN_DOMAIN,
        mailgun_api_key=MAILGUN_API_KEY,
        mailgun_from_email=MAILGUN_FROM_EMAIL,
        mailgun_from_name=MAILGUN_FROM_NAME,
        mailgun_recipient_override=MAILGUN_RECIPIENT_OVERRIDE,
    )
    if auth.deps is not None:
        auth.deps.user_service = auth.user_service
    print("Custom user service with invite/reset email hooks enabled")

    if auth.observability and auth.observability.config.enable_metrics:
        app.include_router(
            create_metrics_router(
                auth.observability,
                path=auth.observability.config.metrics_path,
            )
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
    print(f"Database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else DATABASE_URL}")
    print(f"API: http://localhost:8004")
    print(f"Docs: http://localhost:8004/docs")
    print(f"Frontend URL: {FRONTEND_URL}")
    if MAILGUN_DOMAIN and MAILGUN_API_KEY and MAILGUN_FROM_EMAIL:
        print(f"Mailgun domain: {MAILGUN_DOMAIN}")
        if MAILGUN_RECIPIENT_OVERRIDE:
            print(f"Mailgun sandbox override recipient: {MAILGUN_RECIPIENT_OVERRIDE}")
    else:
        print("Mailgun: not configured, falling back to console email output")

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

# Register consistent JSON error envelopes before the app starts serving requests.
register_exception_handlers(app, debug=DEBUG_MODE, mode="global")

# CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:8000",
        FRONTEND_ORIGIN,
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


async def require_lead_create(request: Request, session: AsyncSession = Depends(get_session)):
    """Dependency for lead:create permission in entity context."""
    # Use require_entity_permission which reads X-Entity-Context header
    dep_fn = get_auth().deps.require_entity_permission("lead:create")
    return await dep_fn(request=request, session=session)


async def require_lead_read(request: Request, session: AsyncSession = Depends(get_session)):
    """Dependency for lead:read permission"""
    dep_fn = get_auth().deps.require_permission("lead:read")
    return await dep_fn(request=request, session=session)


async def require_lead_update(request: Request, session: AsyncSession = Depends(get_session)):
    """Dependency for lead:update permission"""
    dep_fn = get_auth().deps.require_permission("lead:update")
    return await dep_fn(request=request, session=session)


async def require_lead_delete(request: Request, session: AsyncSession = Depends(get_session)):
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

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


# ============================================================================
# Run Application
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    # Watch both the example directory and the library code
    project_root = EXAMPLE_DIR.parent.parent
    reload_dirs = [
        str(EXAMPLE_DIR),  # examples/enterprise_rbac
        str(project_root / "outlabs_auth"),  # library code
    ]

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8004,
        reload=True,
        reload_dirs=reload_dirs,
    )
