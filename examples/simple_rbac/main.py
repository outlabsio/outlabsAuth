"""
SimpleRBAC Example - Blog API

This example demonstrates a simple blog API with flat RBAC using OutlabsAuth.

Features:
- User registration and login
- JWT authentication
- Role-based permissions (reader, writer, editor, admin)
- CRUD operations on blog posts
- Comment management
"""
import os
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field
from beanie import Document, init_beanie

from outlabs_auth import SimpleRBAC
from outlabs_auth.core.config import AuthConfig
from outlabs_auth.models.user import UserModel
from outlabs_auth.models.role import RoleModel
from outlabs_auth.core.exceptions import AuthenticationError
from outlabs_auth.observability import ObservabilityPresets
from outlabs_auth.observability.router import create_metrics_router
from outlabs_auth.observability.middleware import CorrelationIDMiddleware


# ============================================================================
# Configuration
# ============================================================================

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "blog_simple_rbac")
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
PORT = int(os.getenv("PORT", "8003"))  # Default to port 8003


# ============================================================================
# Blog Post Model
# ============================================================================

class BlogPost(Document):
    """Blog post document"""
    title: str
    content: str
    author_id: str
    author_name: str
    published: bool = False
    tags: List[str] = []

    class Settings:
        name = "blog_posts"


# ============================================================================
# Pydantic Schemas
# ============================================================================

class RegisterRequest(BaseModel):
    """User registration"""
    email: EmailStr
    password: str = Field(min_length=8)
    first_name: str = Field(min_length=1, max_length=50)
    last_name: str = Field(min_length=1, max_length=50)


class LoginRequest(BaseModel):
    """Login credentials"""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """JWT token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class BlogPostCreate(BaseModel):
    """Create blog post"""
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    tags: List[str] = []
    published: bool = False


class BlogPostUpdate(BaseModel):
    """Update blog post"""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = None
    tags: Optional[List[str]] = None
    published: Optional[bool] = None


class BlogPostResponse(BaseModel):
    """Blog post response"""
    id: str
    title: str
    content: str
    author_id: str
    author_name: str
    published: bool
    tags: List[str]

    class Config:
        from_attributes = True


# ============================================================================
# Application Lifespan
# ============================================================================

auth: Optional[SimpleRBAC] = None
security = HTTPBearer()


# ============================================================================
# Dependency Functions
# ============================================================================

async def get_current_user_from_token(token: str = Depends(security)):
    """Extract and validate user from Bearer token"""
    try:
        user = await auth.get_current_user(token.credentials)
        return user
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


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
            BlogPost,
        ]
    )

    # Initialize SimpleRBAC with observability (v1.5)
    auth_config = AuthConfig(
        secret_key=SECRET_KEY,
        algorithm="HS256",
        access_token_expire_minutes=60,
        refresh_token_expire_days=30,
    )

    # Configure observability (use development preset for local testing)
    observability_config = ObservabilityPresets.development()

    auth = SimpleRBAC(config=auth_config, observability_config=observability_config)
    await auth.initialize()

    # Create default roles if they don't exist
    await setup_default_roles(auth)

    print("✅ Blog API (SimpleRBAC) started successfully")
    print(f"📦 Database: {DATABASE_NAME}")
    print(f"🔑 Default roles created: reader, writer, editor, admin")

    yield

    # Cleanup
    client.close()
    print("✅ Blog API shutdown complete")


# ============================================================================
# Setup Functions
# ============================================================================

async def setup_default_roles(auth_instance: SimpleRBAC):
    """Create default roles for the blog"""

    # Reader role - can only read published posts
    reader_role = await auth_instance.role_service.find_by_name("reader")
    if not reader_role:
        await auth_instance.role_service.create_role(
            name="reader",
            display_name="Reader",
            description="Can read published blog posts",
            permissions=["post:read"],
            is_global=True,
        )

    # Writer role - can create and manage own posts
    writer_role = await auth_instance.role_service.find_by_name("writer")
    if not writer_role:
        await auth_instance.role_service.create_role(
            name="writer",
            display_name="Writer",
            description="Can create and manage own blog posts",
            permissions=["post:read", "post:create", "post:update_own", "post:delete_own"],
            is_global=True,
        )

    # Editor role - can manage all posts
    editor_role = await auth_instance.role_service.find_by_name("editor")
    if not editor_role:
        await auth_instance.role_service.create_role(
            name="editor",
            display_name="Editor",
            description="Can manage all blog posts",
            permissions=["post:*", "user:read"],
            is_global=True,
        )

    # Admin role - full system access
    admin_role = await auth_instance.role_service.find_by_name("admin")
    if not admin_role:
        await auth_instance.role_service.create_role(
            name="admin",
            display_name="Administrator",
            description="Full system access",
            permissions=["*:*"],
            is_global=True,
        )


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="Blog API - SimpleRBAC Example",
    description="A simple blog API demonstrating OutlabsAuth SimpleRBAC with Observability",
    version="1.5.0",
    lifespan=lifespan,
)

# Add observability middleware and metrics endpoint (v1.5)
# Note: Middleware will be added after auth.initialize() in lifespan
# so we can access auth.observability

@app.on_event("startup")
async def add_observability():
    """Add observability middleware and routes after auth is initialized"""
    # Add correlation ID middleware
    app.add_middleware(CorrelationIDMiddleware, obs_service=auth.observability)

    # Add metrics endpoint
    app.include_router(create_metrics_router())


# ============================================================================
# Authentication Routes
# ============================================================================

@app.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest):
    """Register a new user (default role: reader)"""
    try:
        # Create user
        user = await auth.user_service.create_user(
            email=request.email,
            password=request.password,
            first_name=request.first_name,
            last_name=request.last_name,
        )

        # Assign reader role by default
        reader_role = await auth.role_service.find_by_name("reader")
        if reader_role:
            user.metadata["role_ids"] = [str(reader_role.id)]
            await user.save()

        # Login and return tokens
        logged_in_user, token_pair = await auth.auth_service.login(request.email, request.password)

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
        logged_in_user, token_pair = await auth.auth_service.login(request.email, request.password)

        return TokenResponse(
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
        )

    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )


@app.post("/logout")
async def logout(ctx = Depends(get_auth_context)):
    """Logout (revoke refresh token)"""
    # Note: In a real app, you'd need to track and revoke the refresh token
    return {"message": "Logged out successfully"}


@app.get("/me")
async def get_current_user(ctx = Depends(get_auth_context)):
    """Get current user info"""
    user = ctx.metadata.get("user")
    return {
        "id": str(user.id),
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "full_name": user.full_name,  # Property that combines first + last
        "permissions": ctx.metadata.get("permissions", []),
    }


# ============================================================================
# Blog Post Routes
# ============================================================================

@app.get("/posts", response_model=List[BlogPostResponse])
async def list_posts(
    published_only: bool = True,
    ctx = Depends(get_optional_auth),
):
    """List blog posts (public can see published, authenticated can see all)"""

    # Determine what posts to show
    query = {}
    if published_only and not ctx:
        # Unauthenticated users see only published posts
        query["published"] = True
    elif ctx:
        # Authenticated users with editor permissions see all posts
        has_editor_perms = await auth.permission_service.has_permission(
            user_id=ctx.user_id,
            permission="post:manage",
        )
        if not has_editor_perms:
            query["published"] = True

    posts = await BlogPost.find(query).to_list()

    return [
        BlogPostResponse(
            id=str(post.id),
            title=post.title,
            content=post.content,
            author_id=post.author_id,
            author_name=post.author_name,
            published=post.published,
            tags=post.tags,
        )
        for post in posts
    ]


@app.post("/posts", response_model=BlogPostResponse, status_code=status.HTTP_201_CREATED)
async def create_post(
    post_data: BlogPostCreate,
    ctx = Depends(require_permission("post:create")),
):
    """Create a new blog post (requires post:create permission)"""
    user = ctx.metadata.get("user")

    post = BlogPost(
        title=post_data.title,
        content=post_data.content,
        author_id=str(user.id),
        author_name=user.full_name,  # Uses property that combines first + last
        published=post_data.published,
        tags=post_data.tags,
    )

    await post.insert()

    return BlogPostResponse(
        id=str(post.id),
        title=post.title,
        content=post.content,
        author_id=post.author_id,
        author_name=post.author_name,
        published=post.published,
        tags=post.tags,
    )


@app.get("/posts/{post_id}", response_model=BlogPostResponse)
async def get_post(
    post_id: str,
    ctx = Depends(get_optional_auth),
):
    """Get a single blog post"""
    post = await BlogPost.get(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Check if user can view unpublished posts
    if not post.published:
        if not ctx:
            raise HTTPException(status_code=404, detail="Post not found")

        # Check if user is author or has editor permissions
        user = ctx.metadata.get("user")
        is_author = str(user.id) == post.author_id
        has_editor_perms = await auth.permission_service.has_permission(
            user_id=ctx.user_id,
            permission="post:manage",
        )

        if not is_author and not has_editor_perms:
            raise HTTPException(status_code=404, detail="Post not found")

    return BlogPostResponse(
        id=str(post.id),
        title=post.title,
        content=post.content,
        author_id=post.author_id,
        author_name=post.author_name,
        published=post.published,
        tags=post.tags,
    )


@app.put("/posts/{post_id}", response_model=BlogPostResponse)
async def update_post(
    post_id: str,
    post_data: BlogPostUpdate,
    ctx = Depends(get_auth_context),
):
    """Update a blog post (own posts or with post:manage permission)"""
    post = await BlogPost.get(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    user = ctx.metadata.get("user")
    is_author = str(user.id) == post.author_id

    # Check permissions
    if is_author:
        # Author can update own posts if they have post:update_own
        has_perm = await auth.permission_service.has_permission(
            user_id=ctx.user_id,
            permission="post:update_own",
        )
        if not has_perm:
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to update posts",
            )
    else:
        # Non-authors need post:manage permission
        has_perm = await auth.permission_service.has_permission(
            user_id=ctx.user_id,
            permission="post:manage",
        )
        if not has_perm:
            raise HTTPException(
                status_code=403,
                detail="You can only update your own posts",
            )

    # Update post
    if post_data.title is not None:
        post.title = post_data.title
    if post_data.content is not None:
        post.content = post_data.content
    if post_data.tags is not None:
        post.tags = post_data.tags
    if post_data.published is not None:
        post.published = post_data.published

    await post.save()

    return BlogPostResponse(
        id=str(post.id),
        title=post.title,
        content=post.content,
        author_id=post.author_id,
        author_name=post.author_name,
        published=post.published,
        tags=post.tags,
    )


@app.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(
    post_id: str,
    ctx = Depends(get_auth_context),
):
    """Delete a blog post (own posts or with post:manage permission)"""
    post = await BlogPost.get(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    user = ctx.metadata.get("user")
    is_author = str(user.id) == post.author_id

    # Check permissions
    if is_author:
        has_perm = await auth.permission_service.has_permission(
            user_id=ctx.user_id,
            permission="post:delete_own",
        )
        if not has_perm:
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to delete posts",
            )
    else:
        has_perm = await auth.permission_service.has_permission(
            user_id=ctx.user_id,
            permission="post:manage",
        )
        if not has_perm:
            raise HTTPException(
                status_code=403,
                detail="You can only delete your own posts",
            )

    await post.delete()


# ============================================================================
# Admin Routes
# ============================================================================

@app.post("/admin/users/{user_id}/role")
async def assign_role(
    user_id: str,
    role_name: str,
    ctx = Depends(require_permission("user:manage")),
):
    """Assign a role to a user (requires user:manage permission)"""
    user = await auth.user_service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    role = await auth.role_service.find_by_name(role_name)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    # Replace user's roles with the new role
    user.role_ids = [role.id]
    await user.save()

    return {
        "message": f"Role '{role_name}' assigned to user",
        "user_id": str(user.id),
        "role_id": str(role.id),
    }


@app.get("/admin/roles")
async def list_roles(ctx = Depends(require_permission("user:read"))):
    """List all available roles"""
    roles = await auth.role_service.list_roles()

    return [
        {
            "id": str(role.id),
            "name": role.name,
            "display_name": role.display_name,
            "description": role.description,
            "permissions": role.permissions,
        }
        for role in roles
    ]


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "blog-api-simple-rbac",
        "auth_preset": "SimpleRBAC",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
