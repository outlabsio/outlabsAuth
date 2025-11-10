"""
Blog API - SimpleRBAC Example

Demonstrates OutlabsAuth's SimpleRBAC preset for flat role-based access control.

This example shows:
- Flat RBAC (no entity hierarchy)
- Direct user-role assignments
- Simple permission model
- Blog domain with posts and comments
- Minimal code (most routes provided by OutlabsAuth)

See REQUIREMENTS.md for complete use case documentation.
"""

import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional

from beanie import init_beanie
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from models import BlogPost, Comment
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field

from outlabs_auth import SimpleRBAC
from outlabs_auth.models.api_key import APIKeyModel
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
    get_memberships_router,
    get_permissions_router,
    get_roles_router,
    get_users_router,
)
from outlabs_auth.services.user import UserService

# ============================================================================
# Custom User Service with Password Reset Hooks
# ============================================================================


class BlogUserService(UserService):
    """
    Custom UserService with password reset hooks for email notifications.

    In a production app, these hooks would send actual emails.
    For development, we just print the reset links to console.
    """

    async def on_after_forgot_password(
        self, user: UserModel, token: str, request: Optional[any] = None
    ) -> None:
        """
        Send password reset email to user.

        In production: Send email with reset link
        For development: Print reset link to console
        """
        # Build reset link (in production, use actual domain)
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

        # TODO: Integrate email service for production
        # In production, you would send an actual email:
        # await send_email(
        #     to=user.email,
        #     subject="Reset your password",
        #     template="password_reset",
        #     context={"reset_link": reset_link, "user": user}
        # )

    async def on_after_reset_password(
        self, user: UserModel, request: Optional[any] = None
    ) -> None:
        """
        Send password reset confirmation email.

        Notifies user that their password was successfully changed.
        """
        print("\n" + "=" * 80)
        print("✅ PASSWORD RESET CONFIRMATION (Development Mode)")
        print("=" * 80)
        print(f"To: {user.email}")
        print(f"Subject: Password reset successful")
        print(f"\nYour password has been successfully reset.")
        print(f"If you didn't make this change, please contact support immediately.")
        print("=" * 80 + "\n")

        # TODO: Integrate email service for production
        # In production, you would send an actual email:
        # await send_email(
        #     to=user.email,
        #     subject="Password reset successful",
        #     template="password_reset_confirmation",
        #     context={"user": user}
        # )


# ============================================================================
# Configuration
# ============================================================================

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "blog_simple_rbac")
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production-please")
REDIS_URL = os.getenv("REDIS_URL", None)


# ============================================================================
# Pydantic Schemas
# ============================================================================


class PostCreateRequest(BaseModel):
    """Create new blog post"""

    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    status: str = Field(default="draft", description="draft, published, or archived")
    tags: Optional[List[str]] = None


class PostUpdateRequest(BaseModel):
    """Update existing blog post"""

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=1)
    status: Optional[str] = None
    tags: Optional[List[str]] = None


class PostResponse(BaseModel):
    """Blog post response"""

    id: str
    title: str
    content: str
    author_id: str
    status: str
    tags: List[str]
    created_at: datetime
    updated_at: datetime
    view_count: int

    class Config:
        from_attributes = True


class CommentCreateRequest(BaseModel):
    """Add comment to post"""

    content: str = Field(min_length=1, max_length=1000)


class CommentResponse(BaseModel):
    """Comment response"""

    id: str
    post_id: str
    author_id: str
    content: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# Global Variables
# ============================================================================

# Auth instance (initialized in lifespan)
auth: Optional[SimpleRBAC] = None


# ============================================================================
# FastAPI Application
# ============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global auth

    # Startup
    print("🚀 Starting Blog API (SimpleRBAC) v1.0.0...")

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

    # Initialize SimpleRBAC
    print("🔐 Initializing OutlabsAuth SimpleRBAC...")
    # Configure observability (use preset for development/production)
    # Development: text logs, verbose, all permission checks
    # Production: JSON logs, INFO level, failures only
    env = os.getenv("ENV", "development")
    if env == "production":
        obs_config = ObservabilityPresets.production()
    else:
        # Use development preset but enable metrics for Prometheus
        obs_config = ObservabilityPresets.development()
        obs_config.enable_metrics = True

    auth = SimpleRBAC(
        database=db,
        secret_key=SECRET_KEY,
        access_token_expire_minutes=480,  # 8 hours for dev (default: 15 min)
        refresh_token_expire_days=7,  # 7 days for dev (default: 30 days)
        redis_client=redis_client,
        redis_url=REDIS_URL if redis_client else None,
        enable_caching=redis_client is not None,
        observability_config=obs_config,  # Enable observability
    )

    # Initialize Beanie with all document models
    await init_beanie(
        database=db,
        document_models=[
            UserModel,
            RoleModel,
            PermissionModel,
            APIKeyModel,
            BlogPost,
            Comment,
        ],
    )

    await auth.initialize()
    print("✅ Database initialized")

    # Replace user service with custom one that has password reset hooks
    auth.user_service = BlogUserService(
        database=db, config=auth.config, notification_service=auth.notification_service
    )
    print("✅ Custom user service with password reset hooks enabled")

    # Create default roles if they don't exist
    await create_default_roles()

    # Include standard OutlabsAuth routers with /v1 prefix
    print("📝 Including API routers...")
    app.include_router(get_auth_router(auth, prefix="/v1/auth"))
    app.include_router(get_users_router(auth, prefix="/v1/users"))
    app.include_router(get_api_keys_router(auth, prefix="/v1/api-keys"))
    app.include_router(get_roles_router(auth, prefix="/v1/roles"))
    app.include_router(get_permissions_router(auth, prefix="/v1/permissions"))
    app.include_router(get_memberships_router(auth, prefix="/v1/memberships"))

    # Include observability metrics endpoint (for Prometheus scraping)
    app.include_router(create_metrics_router(auth.observability))

    print("✅ Routers included (including /metrics for Prometheus)")

    print("✅ Blog API (SimpleRBAC) started successfully")
    print(f"📦 Database: {DATABASE_NAME}")
    print(f"📍 API: http://localhost:8003")
    print(f"📚 Docs: http://localhost:8003/docs")
    print(f"🔑 Default roles created: reader, writer, editor, admin")

    yield

    # Shutdown
    print("👋 Shutting down...")
    await auth.shutdown()
    client.close()
    print("✅ Blog API shutdown complete")


app = FastAPI(
    title="Blog API - SimpleRBAC Example",
    description="Demonstrates OutlabsAuth SimpleRBAC with a blog application",
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


# ============================================================================
# Helper Functions
# ============================================================================


def get_auth() -> SimpleRBAC:
    """Get the global auth instance"""
    if auth is None:
        raise HTTPException(status_code=500, detail="Auth not initialized")
    return auth


async def create_default_roles():
    """Create default roles for the blog application"""
    auth_instance = get_auth()

    # Role definitions
    roles = [
        {
            "name": "reader",
            "display_name": "Reader",
            "description": "Can view published posts and comments",
            "permissions": [],  # Public access, no special permissions
        },
        {
            "name": "writer",
            "display_name": "Writer",
            "description": "Can create posts and add comments",
            "permissions": [
                "post:create",
                "comment:create",
            ],
        },
        {
            "name": "editor",
            "display_name": "Editor",
            "description": "Can update/delete their own posts",
            "permissions": [
                "post:create",
                "post:update_own",
                "post:delete_own",
                "comment:create",
                "comment:delete_own",
            ],
        },
        {
            "name": "admin",
            "display_name": "Administrator",
            "description": "Full administrative control over users, roles, permissions, API keys, posts, and comments",
            "permissions": [
                # Blog permissions
                "post:create",
                "post:update",
                "post:delete",
                "comment:create",
                "comment:delete",
                # User management
                "user:read",
                "user:create",
                "user:update",
                "user:delete",
                "user:manage",
                # Role management
                "role:read",
                "role:create",
                "role:update",
                "role:delete",
                # Permission management
                "permission:read",
                "permission:create",
                "permission:update",
                "permission:delete",
                # API Key management
                "api_key:read",
                "api_key:create",
                "api_key:revoke",
            ],
        },
    ]

    # Create roles if they don't exist
    for role_data in roles:
        existing = await auth_instance.role_service.get_role_by_name(role_data["name"])
        if not existing:
            await auth_instance.role_service.create_role(
                name=role_data["name"],
                display_name=role_data["display_name"],
                description=role_data["description"],
                permissions=role_data["permissions"],
            )


# ============================================================================
# Domain-Specific Routes: Blog Posts
# ============================================================================


@app.post(
    "/posts",
    response_model=PostResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Posts"],
    summary="Create new blog post",
)
async def create_post(
    data: PostCreateRequest,
    current_user: UserModel = Depends(lambda: get_auth().deps.requires("post:create")),
):
    """
    Create a new blog post.

    Requires `post:create` permission (writer, editor, or admin role).
    """

    # Create post
    post = BlogPost(
        title=data.title,
        content=data.content,
        author_id=str(current_user.id),
        status=data.status,
        tags=data.tags or [],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    await post.insert()

    return PostResponse(id=str(post.id), **post.dict(exclude={"id"}))


@app.get("/posts", response_model=dict, tags=["Posts"], summary="List blog posts")
async def list_posts(
    status: Optional[str] = Query(None, description="Filter by status"),
    author_id: Optional[str] = Query(None, description="Filter by author"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """
    List blog posts (public access).

    Returns published posts by default. Authenticated users can see their own drafts.
    """
    # Build query
    query = {}

    # Default: only show published posts
    if status:
        query["status"] = status
    else:
        query["status"] = "published"

    if author_id:
        query["author_id"] = author_id

    # Paginate
    skip = (page - 1) * limit
    posts = await BlogPost.find(query).skip(skip).limit(limit).to_list()
    total = await BlogPost.find(query).count()

    return {
        "posts": [
            PostResponse(id=str(post.id), **post.dict(exclude={"id"})) for post in posts
        ],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit,
    }


@app.get(
    "/posts/{post_id}",
    response_model=PostResponse,
    tags=["Posts"],
    summary="Get post details",
)
async def get_post(post_id: str):
    """
    Get blog post details (public access).

    Increments view count.
    """
    post = await BlogPost.get(post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )

    # Increment view count
    post.increment_views()
    await post.save()

    return PostResponse(id=str(post.id), **post.dict(exclude={"id"}))


@app.put(
    "/posts/{post_id}",
    response_model=PostResponse,
    tags=["Posts"],
    summary="Update blog post",
)
async def update_post(
    post_id: str,
    data: PostUpdateRequest,
    current_user: UserModel = Depends(lambda: get_auth().deps.authenticated()),
):
    """
    Update blog post.

    - Editors can update their own posts (post:update_own)
    - Admins can update any post (post:update)
    """
    post = await BlogPost.get(post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )

    # Get user permissions
    auth_instance = get_auth()
    user_permissions = await auth_instance.permission_service.get_user_permissions(
        str(current_user.id)
    )

    # Check if user can edit this post
    if not post.can_be_edited_by(str(current_user.id), user_permissions):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this post",
        )

    # Update fields
    update_data = data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(post, field, value)

    post.updated_at = datetime.utcnow()
    await post.save()

    return PostResponse(id=str(post.id), **post.dict(exclude={"id"}))


@app.delete(
    "/posts/{post_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Posts"],
    summary="Delete blog post",
)
async def delete_post(
    post_id: str,
    current_user: UserModel = Depends(lambda: get_auth().deps.requires("post:delete")),
):
    """
    Delete blog post (admin only).

    Requires `post:delete` permission.
    """
    post = await BlogPost.get(post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )

    await post.delete()


# ============================================================================
# Domain-Specific Routes: Comments
# ============================================================================


@app.post(
    "/posts/{post_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Comments"],
    summary="Add comment to post",
)
async def add_comment(
    post_id: str,
    data: CommentCreateRequest,
    current_user: UserModel = Depends(
        lambda: get_auth().deps.requires("comment:create")
    ),
):
    """
    Add a comment to a blog post.

    Requires `comment:create` permission (writer, editor, or admin role).
    """
    # Verify post exists
    post = await BlogPost.get(post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )

    # Create comment
    comment = Comment(
        post_id=post_id,
        author_id=str(current_user.id),
        content=data.content,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    await comment.insert()

    return CommentResponse(id=str(comment.id), **comment.dict(exclude={"id"}))


@app.get(
    "/posts/{post_id}/comments",
    response_model=List[CommentResponse],
    tags=["Comments"],
    summary="List comments on post",
)
async def list_comments(post_id: str):
    """
    List all comments on a post (public access).
    """
    comments = await Comment.find({"post_id": post_id}).to_list()

    return [
        CommentResponse(id=str(comment.id), **comment.dict(exclude={"id"}))
        for comment in comments
    ]


@app.delete(
    "/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Comments"],
    summary="Delete comment",
)
async def delete_comment(
    comment_id: str,
    current_user: UserModel = Depends(lambda: get_auth().deps.authenticated()),
):
    """
    Delete comment.

    - Users can delete their own comments
    - Admins can delete any comment (comment:delete permission)
    """
    comment = await Comment.get(comment_id)
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found"
        )

    # Get user permissions
    auth_instance = get_auth()
    user_permissions = await auth_instance.permission_service.get_user_permissions(
        str(current_user.id)
    )

    # Check if user can delete this comment
    if not comment.can_be_deleted_by(str(current_user.id), user_permissions):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to delete this comment",
        )

    await comment.delete()


# ============================================================================
# Health Check
# ============================================================================


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {
        "service": "Blog API - SimpleRBAC Example",
        "status": "healthy",
        "version": "1.0.0",
        "preset": "SimpleRBAC",
        "docs": "/docs",
    }


@app.get("/v1/auth/config", tags=["Auth"], summary="Get auth configuration")
async def get_auth_config():
    """
    Get authentication system configuration

    Returns preset type, feature flags, and available permissions.
    This allows the admin UI to adapt to the backend's capabilities.
    """
    return {
        "preset": "SimpleRBAC",
        "features": {
            "entity_hierarchy": False,
            "context_aware_roles": False,
            "abac": False,
            "tree_permissions": False,
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
                "description": "View user information and profiles",
            },
            {
                "value": "user:create",
                "label": "User Create",
                "category": "Users",
                "description": "Create new user accounts",
            },
            {
                "value": "user:update",
                "label": "User Update",
                "category": "Users",
                "description": "Update user information and profiles",
            },
            {
                "value": "user:delete",
                "label": "User Delete",
                "category": "Users",
                "description": "Delete user accounts",
            },
            # Role permissions
            {
                "value": "role:read",
                "label": "Role Read",
                "category": "Roles",
                "description": "View role definitions and assignments",
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
                "description": "Update role definitions and permissions",
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
                "description": "View permission definitions",
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
                "description": "Update permission definitions",
            },
            {
                "value": "permission:delete",
                "label": "Permission Delete",
                "category": "Permissions",
                "description": "Delete custom permissions",
            },
            # API Key permissions
            {
                "value": "api_key:read",
                "label": "API Key Read",
                "category": "API Keys",
                "description": "View API keys (hashed)",
            },
            {
                "value": "api_key:create",
                "label": "API Key Create",
                "category": "API Keys",
                "description": "Generate new API keys",
            },
            {
                "value": "api_key:revoke",
                "label": "API Key Revoke",
                "category": "API Keys",
                "description": "Revoke existing API keys",
            },
            # Blog-specific permissions (SimpleRBAC example)
            {
                "value": "post:read",
                "label": "Post Read",
                "category": "Blog",
                "description": "View blog posts",
            },
            {
                "value": "post:create",
                "label": "Post Create",
                "category": "Blog",
                "description": "Create new blog posts",
            },
            {
                "value": "post:update",
                "label": "Post Update",
                "category": "Blog",
                "description": "Edit blog posts",
            },
            {
                "value": "post:delete",
                "label": "Post Delete",
                "category": "Blog",
                "description": "Delete blog posts",
            },
            {
                "value": "comment:create",
                "label": "Comment Create",
                "category": "Blog",
                "description": "Add comments to posts",
            },
            {
                "value": "comment:delete",
                "label": "Comment Delete",
                "category": "Blog",
                "description": "Delete comments",
            },
        ],
    }


# ============================================================================
# Run Application
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8003, reload=True)
