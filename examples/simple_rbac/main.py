"""
Blog API - SimpleRBAC Example

Demonstrates OutlabsAuth's SimpleRBAC preset for flat role-based access control.

This example shows:
- Flat RBAC (no entity hierarchy)
- Direct user-role assignments
- Simple permission model
- Blog domain with posts and comments
- PostgreSQL with SQLAlchemy

See REQUIREMENTS.md for complete use case documentation.
"""

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from models import BlogPost, Comment
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel

from outlabs_auth import SimpleRBAC, User
from outlabs_auth.routers import (
    get_api_keys_router,
    get_auth_router,
    get_integration_principals_router,
    get_permissions_router,
    get_roles_router,
    get_users_router,
)

# ============================================================================
# Configuration
# ============================================================================

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/blog_simple_rbac",
)
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


def _ensure_example_tables(sync_conn) -> None:
    """Create example-owned tables without re-touching migrated auth tables."""
    SQLModel.metadata.create_all(
        sync_conn,
        tables=[BlogPost.__table__, Comment.__table__],
    )


# ============================================================================
# FastAPI Application
# ============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global auth

    # Startup
    print("🚀 Starting Blog API (SimpleRBAC) v2.0.0...")

    # Initialize SimpleRBAC with PostgreSQL
    print("📦 Connecting to PostgreSQL...")
    auth = SimpleRBAC(
        database_url=DATABASE_URL,
        secret_key=SECRET_KEY,
        access_token_expire_minutes=480,  # 8 hours for dev
        refresh_token_expire_days=7,
        redis_url=REDIS_URL if REDIS_URL else None,
        auto_migrate=False,  # We'll handle migrations manually
        echo_sql=os.getenv("ECHO_SQL", "false").lower() == "true",
    )

    await auth.initialize()
    print("✅ OutlabsAuth initialized")

    # Include library routers for user/role/permission management
    include_auth_routers(app, auth)
    print("✅ Library routers included")

    # Install centralized exception handlers (and observability if configured)
    auth.instrument_fastapi(
        app,
        debug=True,
        exception_handler_mode="global",
        include_metrics=True,
        include_correlation_id=True,
        include_resource_context=True,
    )

    # Create blog-specific tables if they don't exist
    print("📝 Creating blog tables...")
    async with auth.engine.begin() as conn:
        await conn.run_sync(_ensure_example_tables)
    print("✅ Blog tables ready")

    # Create default roles if they don't exist
    await create_default_roles()

    print("✅ Blog API (SimpleRBAC) started successfully")
    print(f"📦 Database: {DATABASE_URL.split('@')[-1]}")  # Hide password
    print(f"📍 API: http://localhost:8003")
    print(f"📚 Docs: http://localhost:8003/docs")
    print("🛠️  Auth schema bootstrap: uv run outlabs-auth migrate")
    print(f"🔑 Default roles created: reader, writer, editor, admin")

    yield

    # Shutdown
    print("👋 Shutting down...")
    await auth.shutdown()
    print("✅ Blog API shutdown complete")


app = FastAPI(
    title="Blog API - SimpleRBAC Example",
    description="Demonstrates OutlabsAuth SimpleRBAC with PostgreSQL",
    version="2.0.0",
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
# Include Library Routers (after auth is initialized via lifespan)
# ============================================================================
# Note: These are added dynamically in lifespan since they need the auth instance


def include_auth_routers(app: FastAPI, auth_instance: SimpleRBAC):
    """Include all OutlabsAuth library routers"""
    # Auth routes (login, register, logout, refresh, config, me)
    app.include_router(get_auth_router(auth_instance, prefix="/v1/auth", tags=["Auth"]))
    # User management routes
    app.include_router(get_users_router(auth_instance, prefix="/v1/users", tags=["Users"]))
    # Role management routes
    app.include_router(get_roles_router(auth_instance, prefix="/v1/roles", tags=["Roles"]))
    # Permission management routes
    app.include_router(get_permissions_router(auth_instance, prefix="/v1/permissions", tags=["Permissions"]))
    # API Key management routes
    app.include_router(get_api_keys_router(auth_instance, prefix="/v1/api-keys", tags=["API Keys"]))
    # Platform-global integration principals and owned system API keys
    app.include_router(
        get_integration_principals_router(
            auth_instance,
            prefix="/v1/admin",
            tags=["Integration Principals"],
        )
    )


# ============================================================================
# Helper Functions
# ============================================================================


def get_auth() -> SimpleRBAC:
    """Get the global auth instance"""
    if auth is None:
        raise HTTPException(status_code=500, detail="Auth not initialized")
    return auth


async def get_session() -> AsyncSession:
    """Get database session dependency"""
    auth_instance = get_auth()
    async with auth_instance.get_session() as session:
        yield session


async def create_default_roles():
    """Create default roles for the blog application"""
    auth_instance = get_auth()

    # Permission definitions
    all_permissions = [
        # User permissions
        ("user:read", "User Read"),
        ("user:create", "User Create"),
        ("user:update", "User Update"),
        ("user:delete", "User Delete"),
        ("user:manage", "User Manage"),
        # Role permissions
        ("role:read", "Role Read"),
        ("role:create", "Role Create"),
        ("role:update", "Role Update"),
        ("role:delete", "Role Delete"),
        # Permission permissions
        ("permission:read", "Permission Read"),
        ("permission:create", "Permission Create"),
        ("permission:update", "Permission Update"),
        ("permission:delete", "Permission Delete"),
        # API Key permissions
        ("api_key:read", "API Key Read"),
        ("api_key:create", "API Key Create"),
        ("api_key:revoke", "API Key Revoke"),
        # Blog permissions
        ("post:read", "Post Read"),
        ("post:create", "Post Create"),
        ("post:update", "Post Update"),
        ("post:update_own", "Post Update Own"),
        ("post:delete", "Post Delete"),
        ("post:delete_own", "Post Delete Own"),
        ("comment:create", "Comment Create"),
        ("comment:delete", "Comment Delete"),
        ("comment:delete_own", "Comment Delete Own"),
    ]

    # Role definitions
    roles = [
        {
            "name": "reader",
            "display_name": "Reader",
            "description": "Can view published posts and comments",
            "permissions": ["post:read"],
        },
        {
            "name": "writer",
            "display_name": "Writer",
            "description": "Can create posts and add comments",
            "permissions": [
                "post:read",
                "post:create",
                "post:update_own",
                "comment:create",
            ],
        },
        {
            "name": "editor",
            "display_name": "Editor",
            "description": "Can update/delete their own posts",
            "permissions": [
                "post:read",
                "post:create",
                "post:update_own",
                "post:delete_own",
                "comment:create",
                "comment:delete_own",
            ],
        },
        {
            "name": "service_reader",
            "display_name": "Service Reader",
            "description": "Minimal machine-access role for service accounts.",
            "permissions": [
                "user:read",
            ],
        },
        {
            "name": "admin",
            "display_name": "Administrator",
            "description": "Full administrative control",
            "permissions": [
                # Blog permissions
                "post:read",
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

    async with auth_instance.get_session() as session:
        # Create permissions if they don't exist
        for perm_name, display_name in all_permissions:
            existing = await auth_instance.permission_service.get_permission_by_name(session, perm_name)
            if not existing:
                await auth_instance.permission_service.create_permission(
                    session,
                    name=perm_name,
                    display_name=display_name,
                    description=f"Permission to {perm_name.replace(':', ' ')}",
                )

        # Create roles if they don't exist
        for role_data in roles:
            existing = await auth_instance.role_service.get_role_by_name(session, role_data["name"])
            if not existing:
                await auth_instance.role_service.create_role(
                    session,
                    name=role_data["name"],
                    display_name=role_data["display_name"],
                    description=role_data["description"],
                    permission_names=role_data["permissions"],
                )

        await session.commit()


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
    session: AsyncSession = Depends(get_session),
):
    """
    Create a new blog post.

    Requires `post:create` permission (writer, editor, or admin role).
    """
    auth_instance = get_auth()

    # TODO: Get current user from auth dependency
    # For now, we'll create without auth check
    # current_user = await auth_instance.deps.requires("post:create")

    # Create post
    post = BlogPost(
        title=data.title,
        content=data.content,
        author_id=UUID("00000000-0000-0000-0000-000000000000"),  # Placeholder
        status=data.status,
        tags=data.tags or [],
    )

    session.add(post)
    await session.commit()
    await session.refresh(post)

    return PostResponse(
        id=str(post.id),
        title=post.title,
        content=post.content,
        author_id=str(post.author_id),
        status=post.status,
        tags=post.tags or [],
        created_at=post.created_at,
        updated_at=post.updated_at,
        view_count=post.view_count,
    )


@app.get("/posts", response_model=dict, tags=["Posts"], summary="List blog posts")
async def list_posts(
    post_status: Optional[str] = Query(None, alias="status", description="Filter by status"),
    author_id: Optional[str] = Query(None, description="Filter by author"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """
    List blog posts (public access).

    Returns published posts by default.
    """
    # Build query
    filters = []

    # Default: only show published posts
    if post_status:
        filters.append(BlogPost.status == post_status)
    else:
        filters.append(BlogPost.status == "published")

    if author_id:
        filters.append(BlogPost.author_id == UUID(author_id))

    # Count total
    from sqlalchemy import func

    count_stmt = select(func.count()).select_from(BlogPost).where(*filters)
    total_result = await session.execute(count_stmt)
    total = total_result.scalar() or 0

    # Paginate
    skip = (page - 1) * limit
    stmt = select(BlogPost).where(*filters).order_by(BlogPost.created_at.desc()).offset(skip).limit(limit)
    result = await session.execute(stmt)
    posts = result.scalars().all()

    return {
        "posts": [
            PostResponse(
                id=str(post.id),
                title=post.title,
                content=post.content,
                author_id=str(post.author_id),
                status=post.status,
                tags=post.tags or [],
                created_at=post.created_at,
                updated_at=post.updated_at,
                view_count=post.view_count,
            )
            for post in posts
        ],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit if total > 0 else 0,
    }


@app.get(
    "/posts/{post_id}",
    response_model=PostResponse,
    tags=["Posts"],
    summary="Get post details",
)
async def get_post(
    post_id: str,
    session: AsyncSession = Depends(get_session),
):
    """
    Get blog post details (public access).

    Increments view count.
    """
    stmt = select(BlogPost).where(BlogPost.id == UUID(post_id))
    result = await session.execute(stmt)
    post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    # Increment view count
    post.increment_views()
    post.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(post)

    return PostResponse(
        id=str(post.id),
        title=post.title,
        content=post.content,
        author_id=str(post.author_id),
        status=post.status,
        tags=post.tags or [],
        created_at=post.created_at,
        updated_at=post.updated_at,
        view_count=post.view_count,
    )


@app.put(
    "/posts/{post_id}",
    response_model=PostResponse,
    tags=["Posts"],
    summary="Update blog post",
)
async def update_post(
    post_id: str,
    data: PostUpdateRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Update blog post.

    - Editors can update their own posts (post:update_own)
    - Admins can update any post (post:update)
    """
    stmt = select(BlogPost).where(BlogPost.id == UUID(post_id))
    result = await session.execute(stmt)
    post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    # TODO: Add permission checks via auth dependency

    # Update fields
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(post, field, value)

    post.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(post)

    return PostResponse(
        id=str(post.id),
        title=post.title,
        content=post.content,
        author_id=str(post.author_id),
        status=post.status,
        tags=post.tags or [],
        created_at=post.created_at,
        updated_at=post.updated_at,
        view_count=post.view_count,
    )


@app.delete(
    "/posts/{post_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Posts"],
    summary="Delete blog post",
)
async def delete_post(
    post_id: str,
    session: AsyncSession = Depends(get_session),
):
    """
    Delete blog post (admin only).

    Requires `post:delete` permission.
    """
    stmt = select(BlogPost).where(BlogPost.id == UUID(post_id))
    result = await session.execute(stmt)
    post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    await session.delete(post)
    await session.commit()


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
    session: AsyncSession = Depends(get_session),
):
    """
    Add a comment to a blog post.

    Requires `comment:create` permission (writer, editor, or admin role).
    """
    # Verify post exists
    stmt = select(BlogPost).where(BlogPost.id == UUID(post_id))
    result = await session.execute(stmt)
    post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    # Create comment
    comment = Comment(
        post_id=UUID(post_id),
        author_id=UUID("00000000-0000-0000-0000-000000000000"),  # Placeholder
        content=data.content,
    )

    session.add(comment)
    await session.commit()
    await session.refresh(comment)

    return CommentResponse(
        id=str(comment.id),
        post_id=str(comment.post_id),
        author_id=str(comment.author_id),
        content=comment.content,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )


@app.get(
    "/posts/{post_id}/comments",
    response_model=List[CommentResponse],
    tags=["Comments"],
    summary="List comments on post",
)
async def list_comments(
    post_id: str,
    session: AsyncSession = Depends(get_session),
):
    """
    List all comments on a post (public access).
    """
    stmt = select(Comment).where(Comment.post_id == UUID(post_id)).order_by(Comment.created_at)
    result = await session.execute(stmt)
    comments = result.scalars().all()

    return [
        CommentResponse(
            id=str(comment.id),
            post_id=str(comment.post_id),
            author_id=str(comment.author_id),
            content=comment.content,
            created_at=comment.created_at,
            updated_at=comment.updated_at,
        )
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
    session: AsyncSession = Depends(get_session),
):
    """
    Delete comment.

    - Users can delete their own comments
    - Admins can delete any comment (comment:delete permission)
    """
    stmt = select(Comment).where(Comment.id == UUID(comment_id))
    result = await session.execute(stmt)
    comment = result.scalar_one_or_none()

    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")

    # TODO: Add permission checks via auth dependency

    await session.delete(comment)
    await session.commit()


# ============================================================================
# Health Check
# ============================================================================


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {
        "service": "Blog API - SimpleRBAC Example",
        "status": "healthy",
        "version": "2.0.0",
        "preset": "SimpleRBAC",
        "database": "PostgreSQL",
        "docs": "/docs",
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
        str(Path(__file__).parent),  # examples/simple_rbac
        str(project_root / "outlabs_auth"),  # library code
    ]

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8003,
        reload=True,
        reload_dirs=reload_dirs,
    )
