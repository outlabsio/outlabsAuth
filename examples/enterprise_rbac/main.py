"""
EnterpriseRBAC Example - Project Management System

This example demonstrates hierarchical RBAC with entity hierarchy using OutlabsAuth.

Features:
- Entity hierarchy (Company → Department → Team → Project)
- Multiple roles per user in different entities
- Tree permissions (manage descendants)
- Entity-scoped permission checking
- Complex organizational structures
"""
import os
from contextlib import asynccontextmanager
from typing import List, Optional
from datetime import datetime

from fastapi import FastAPI, Depends, HTTPException, status, Header
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field
from beanie import Document, init_beanie

from outlabs_auth import EnterpriseRBAC
from outlabs_auth.dependencies import AuthDeps
from outlabs_auth.core.config import AuthConfig
from outlabs_auth.models.user import UserModel
from outlabs_auth.models.role import RoleModel
from outlabs_auth.models.entity import EntityModel, EntityClass
from outlabs_auth.models.membership import EntityMembershipModel
from outlabs_auth.models.closure import EntityClosureModel
from outlabs_auth.core.exceptions import AuthenticationError


# ============================================================================
# Configuration
# ============================================================================

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "project_mgmt_enterprise")
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")


# ============================================================================
# Project Model
# ============================================================================

class Project(Document):
    """Project document"""
    name: str
    description: str
    entity_id: str  # The team/entity this project belongs to
    status: str = "active"  # active, completed, archived
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    budget: Optional[float] = None
    deadline: Optional[datetime] = None

    class Settings:
        name = "projects"


# ============================================================================
# Pydantic Schemas
# ============================================================================

class RegisterRequest(BaseModel):
    """User registration"""
    email: EmailStr
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8)
    full_name: str


class LoginRequest(BaseModel):
    """Login credentials"""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """JWT token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class EntityCreate(BaseModel):
    """Create entity"""
    name: str = Field(min_length=1, max_length=100)
    display_name: str
    entity_class: str  # "structural" or "access_group"
    entity_type: str  # "company", "department", "team", "project_group"
    parent_id: Optional[str] = None
    description: Optional[str] = None


class EntityResponse(BaseModel):
    """Entity response"""
    id: str
    name: str
    display_name: str
    entity_class: str
    entity_type: str
    parent_id: Optional[str]
    description: Optional[str]


class MembershipCreate(BaseModel):
    """Add member to entity"""
    user_id: str
    role_ids: List[str]


class ProjectCreate(BaseModel):
    """Create project"""
    name: str = Field(min_length=1, max_length=200)
    description: str
    budget: Optional[float] = None
    deadline: Optional[datetime] = None


class ProjectResponse(BaseModel):
    """Project response"""
    id: str
    name: str
    description: str
    entity_id: str
    status: str
    created_by: str
    created_at: datetime
    budget: Optional[float]
    deadline: Optional[datetime]


# ============================================================================
# Application Lifespan
# ============================================================================

auth: Optional[EnterpriseRBAC] = None
deps: Optional[AuthDeps] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup"""
    global auth, deps

    # Connect to MongoDB
    client = AsyncIOMotorClient(MONGODB_URL)
    database = client[DATABASE_NAME]

    # Initialize Beanie with all models
    await init_beanie(
        database=database,
        document_models=[
            UserModel,
            RoleModel,
            EntityModel,
            EntityMembershipModel,
            EntityClosureModel,
            Project,
        ]
    )

    # Initialize EnterpriseRBAC
    auth_config = AuthConfig(
        secret_key=SECRET_KEY,
        algorithm="HS256",
        access_token_expire_minutes=60,
        refresh_token_expire_days=30,
    )

    auth = EnterpriseRBAC(config=auth_config)
    await auth.initialize()

    # Initialize dependencies
    deps = AuthDeps(auth)

    # Create default company and roles if they don't exist
    await setup_demo_organization(auth)

    print("✅ Project Management API (EnterpriseRBAC) started")
    print(f"📦 Database: {DATABASE_NAME}")
    print(f"🏢 Demo organization created with hierarchy")

    yield

    # Cleanup
    client.close()
    print("✅ Project Management API shutdown complete")


# ============================================================================
# Setup Functions
# ============================================================================

async def setup_demo_organization(auth_instance: EnterpriseRBAC):
    """Create demo organization with hierarchy and roles"""

    # Check if demo company exists
    existing = await EntityModel.find_one(EntityModel.name == "acme_corp")
    if existing:
        print("📋 Demo organization already exists")
        return

    # Create company entity
    company = await auth_instance.entity_service.create_entity(
        name="acme_corp",
        display_name="Acme Corporation",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="company",
        description="Demo company for project management",
    )

    # Create departments
    eng_dept = await auth_instance.entity_service.create_entity(
        name="engineering",
        display_name="Engineering Department",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="department",
        parent_id=str(company.id),
        description="Engineering and development",
    )

    sales_dept = await auth_instance.entity_service.create_entity(
        name="sales",
        display_name="Sales Department",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="department",
        parent_id=str(company.id),
        description="Sales and business development",
    )

    # Create teams under engineering
    backend_team = await auth_instance.entity_service.create_entity(
        name="backend_team",
        display_name="Backend Team",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="team",
        parent_id=str(eng_dept.id),
        description="Backend development team",
    )

    frontend_team = await auth_instance.entity_service.create_entity(
        name="frontend_team",
        display_name="Frontend Team",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="team",
        parent_id=str(eng_dept.id),
        description="Frontend development team",
    )

    # Create roles
    # Company-level roles
    ceo_role = await auth_instance.role_service.create_role(
        name="ceo",
        display_name="CEO",
        description="Chief Executive Officer - full company access",
        permissions=["*:*"],  # Full wildcard
        is_global=False,
    )

    # Department-level roles
    dept_manager_role = await auth_instance.role_service.create_role(
        name="dept_manager",
        display_name="Department Manager",
        description="Manage department and all teams below",
        permissions=[
            "entity:read",
            "entity:update",
            "entity:create_tree",  # Can create entities in subtree
            "entity:update_tree",  # Can update entities in subtree
            "user:read",
            "user:manage_tree",    # Can manage users in subtree
            "project:*",           # Full project management
        ],
        is_global=False,
    )

    # Team-level roles
    team_lead_role = await auth_instance.role_service.create_role(
        name="team_lead",
        display_name="Team Lead",
        description="Lead a team and manage team projects",
        permissions=[
            "entity:read",
            "entity:update",
            "user:read",
            "project:*",
        ],
        is_global=False,
    )

    developer_role = await auth_instance.role_service.create_role(
        name="developer",
        display_name="Developer",
        description="Team member - can work on projects",
        permissions=[
            "entity:read",
            "user:read",
            "project:read",
            "project:update",
        ],
        is_global=False,
    )

    print("✅ Demo organization hierarchy created:")
    print(f"   └─ {company.display_name}")
    print(f"      ├─ {eng_dept.display_name}")
    print(f"      │  ├─ {backend_team.display_name}")
    print(f"      │  └─ {frontend_team.display_name}")
    print(f"      └─ {sales_dept.display_name}")
    print(f"")
    print("✅ Roles created: CEO, Department Manager, Team Lead, Developer")


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="Project Management API - EnterpriseRBAC Example",
    description="Hierarchical project management with OutlabsAuth EnterpriseRBAC",
    version="1.0.0",
    lifespan=lifespan,
)


# ============================================================================
# Helper Functions
# ============================================================================

async def get_entity_context(x_entity_context_id: Optional[str] = Header(None)) -> Optional[str]:
    """Get entity context from header"""
    return x_entity_context_id


# ============================================================================
# Authentication Routes
# ============================================================================

@app.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest):
    """Register a new user"""
    try:
        user = await auth.user_service.create_user(
            email=request.email,
            username=request.username,
            password=request.password,
            full_name=request.full_name,
        )

        # Login and return tokens
        token_pair = await auth.auth_service.login(request.email, request.password)

        return TokenResponse(
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@app.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """Login with email and password"""
    try:
        token_pair = await auth.auth_service.login(request.email, request.password)

        return TokenResponse(
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
        )

    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )


@app.get("/me")
async def get_current_user(ctx = Depends(deps.require_auth())):
    """Get current user info"""
    user = ctx.metadata.get("user")

    # Get user's entities and roles
    memberships = await auth.membership_service.get_user_entities(str(user.id))
    entity_roles = []

    for membership in memberships:
        entity = await auth.entity_service.get_entity(str(membership.entity_id))
        roles = []
        for role_id in membership.role_ids:
            role = await auth.role_service.get_role(str(role_id))
            if role:
                roles.append(role.display_name)

        entity_roles.append({
            "entity": entity.display_name if entity else "Unknown",
            "entity_type": entity.entity_type if entity else None,
            "roles": roles,
        })

    return {
        "id": str(user.id),
        "email": user.email,
        "username": user.username,
        "full_name": user.full_name,
        "entity_memberships": entity_roles,
    }


# ============================================================================
# Entity Routes
# ============================================================================

@app.get("/entities", response_model=List[EntityResponse])
async def list_entities(
    entity_type: Optional[str] = None,
    parent_id: Optional[str] = None,
    ctx = Depends(deps.require_auth()),
):
    """List entities (filtered by access)"""
    # In a real app, filter based on user's access
    # For now, return all entities

    query = {}
    if entity_type:
        query["entity_type"] = entity_type
    if parent_id:
        query["parent_id"] = parent_id

    entities = await EntityModel.find(query).to_list()

    return [
        EntityResponse(
            id=str(e.id),
            name=e.name,
            display_name=e.display_name,
            entity_class=e.entity_class.value,
            entity_type=e.entity_type,
            parent_id=str(e.parent_id) if e.parent_id else None,
            description=e.description,
        )
        for e in entities
    ]


@app.post("/entities", response_model=EntityResponse, status_code=status.HTTP_201_CREATED)
async def create_entity(
    entity_data: EntityCreate,
    ctx = Depends(deps.require_auth()),
):
    """Create a new entity"""
    # Check permission in parent entity or root
    parent_id = entity_data.parent_id
    if parent_id:
        # Check if user has entity:create_tree in parent
        has_perm = await auth.permission_service.check_permission(
            user_id=ctx.user_id,
            permission="entity:create_tree",
            entity_id=parent_id,
        )
        if not has_perm[0]:
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to create entities here",
            )

    entity = await auth.entity_service.create_entity(
        name=entity_data.name,
        display_name=entity_data.display_name,
        entity_class=EntityClass(entity_data.entity_class),
        entity_type=entity_data.entity_type,
        parent_id=parent_id,
        description=entity_data.description,
    )

    return EntityResponse(
        id=str(entity.id),
        name=entity.name,
        display_name=entity.display_name,
        entity_class=entity.entity_class.value,
        entity_type=entity.entity_type,
        parent_id=str(entity.parent_id) if entity.parent_id else None,
        description=entity.description,
    )


@app.get("/entities/{entity_id}", response_model=EntityResponse)
async def get_entity(
    entity_id: str,
    ctx = Depends(deps.require_auth()),
):
    """Get entity details"""
    entity = await auth.entity_service.get_entity(entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    # Check read permission
    has_perm = await auth.permission_service.check_permission(
        user_id=ctx.user_id,
        permission="entity:read",
        entity_id=entity_id,
    )
    if not has_perm[0]:
        raise HTTPException(status_code=403, detail="Access denied")

    return EntityResponse(
        id=str(entity.id),
        name=entity.name,
        display_name=entity.display_name,
        entity_class=entity.entity_class.value,
        entity_type=entity.entity_type,
        parent_id=str(entity.parent_id) if entity.parent_id else None,
        description=entity.description,
    )


@app.get("/entities/{entity_id}/hierarchy")
async def get_entity_hierarchy(
    entity_id: str,
    ctx = Depends(deps.require_auth()),
):
    """Get entity hierarchy path"""
    # Get path from root to entity
    path = await auth.entity_service.get_entity_path(entity_id)

    # Get descendants
    descendants = await auth.entity_service.get_descendants(entity_id)

    return {
        "path": [
            {
                "id": str(e.id),
                "name": e.display_name,
                "type": e.entity_type,
            }
            for e in path
        ],
        "descendants": [
            {
                "id": str(e.id),
                "name": e.display_name,
                "type": e.entity_type,
            }
            for e in descendants
        ],
    }


# ============================================================================
# Membership Routes
# ============================================================================

@app.post("/entities/{entity_id}/members")
async def add_member(
    entity_id: str,
    membership_data: MembershipCreate,
    ctx = Depends(deps.require_auth()),
):
    """Add a member to an entity"""
    # Check if user has permission to manage users in this entity
    has_perm = await auth.permission_service.check_permission(
        user_id=ctx.user_id,
        permission="user:manage",
        entity_id=entity_id,
    )

    # Also check tree permission in parent entities
    if not has_perm[0]:
        has_tree_perm = await auth.permission_service.check_permission(
            user_id=ctx.user_id,
            permission="user:manage_tree",
            entity_id=entity_id,
        )
        if not has_tree_perm[0]:
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to manage members here",
            )

    # Add member
    membership = await auth.membership_service.add_member(
        entity_id=entity_id,
        user_id=membership_data.user_id,
        role_ids=membership_data.role_ids,
    )

    return {
        "message": "Member added successfully",
        "membership_id": str(membership.id),
    }


@app.get("/entities/{entity_id}/members")
async def list_members(
    entity_id: str,
    ctx = Depends(deps.require_auth()),
):
    """List entity members"""
    # Check read permission
    has_perm = await auth.permission_service.check_permission(
        user_id=ctx.user_id,
        permission="user:read",
        entity_id=entity_id,
    )
    if not has_perm[0]:
        raise HTTPException(status_code=403, detail="Access denied")

    members = await auth.membership_service.get_entity_members(entity_id)

    member_list = []
    for membership in members:
        user = await auth.user_service.get_user(str(membership.user_id))
        roles = []
        for role_id in membership.role_ids:
            role = await auth.role_service.get_role(str(role_id))
            if role:
                roles.append({
                    "id": str(role.id),
                    "name": role.display_name,
                })

        if user:
            member_list.append({
                "user_id": str(user.id),
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "roles": roles,
            })

    return {"members": member_list}


# ============================================================================
# Project Routes
# ============================================================================

@app.post("/entities/{entity_id}/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    entity_id: str,
    project_data: ProjectCreate,
    ctx = Depends(deps.require_auth()),
):
    """Create a project in an entity (team)"""
    # Check permission
    has_perm = await auth.permission_service.check_permission(
        user_id=ctx.user_id,
        permission="project:create",
        entity_id=entity_id,
    )
    if not has_perm[0]:
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to create projects here",
        )

    project = Project(
        name=project_data.name,
        description=project_data.description,
        entity_id=entity_id,
        created_by=ctx.user_id,
        budget=project_data.budget,
        deadline=project_data.deadline,
    )

    await project.insert()

    return ProjectResponse(
        id=str(project.id),
        name=project.name,
        description=project.description,
        entity_id=project.entity_id,
        status=project.status,
        created_by=project.created_by,
        created_at=project.created_at,
        budget=project.budget,
        deadline=project.deadline,
    )


@app.get("/entities/{entity_id}/projects", response_model=List[ProjectResponse])
async def list_projects(
    entity_id: str,
    ctx = Depends(deps.require_auth()),
):
    """List projects in an entity"""
    # Check permission
    has_perm = await auth.permission_service.check_permission(
        user_id=ctx.user_id,
        permission="project:read",
        entity_id=entity_id,
    )
    if not has_perm[0]:
        raise HTTPException(status_code=403, detail="Access denied")

    projects = await Project.find(Project.entity_id == entity_id).to_list()

    return [
        ProjectResponse(
            id=str(p.id),
            name=p.name,
            description=p.description,
            entity_id=p.entity_id,
            status=p.status,
            created_by=p.created_by,
            created_at=p.created_at,
            budget=p.budget,
            deadline=p.deadline,
        )
        for p in projects
    ]


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "project-mgmt-enterprise-rbac",
        "auth_preset": "EnterpriseRBAC",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
