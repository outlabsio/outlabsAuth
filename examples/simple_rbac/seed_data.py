"""
Seed Data for SimpleRBAC Blog Example

Creates demo data for testing the blog API:
- 4 roles (reader, writer, editor, admin)
- 5 demo users with different roles
- 15 sample blog posts
- Comments on posts
"""
import asyncio
import os
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

from main import BlogPost, Comment
from outlabs_auth import SimpleRBAC
from outlabs_auth.models.user import UserModel
from outlabs_auth.models.role import RoleModel
from outlabs_auth.models.permission import PermissionModel


# Configuration
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "blog_simple_rbac")
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production-please")


async def create_role_if_not_exists(auth, name: str, permissions: list[str], display_name: str) -> RoleModel:
    """Create role if it doesn't exist"""
    existing = await RoleModel.find_one(RoleModel.name == name)
    if existing:
        print(f"  ✓ Role '{name}' already exists")
        return existing

    role = await auth.role_service.create_role(
        name=name,
        display_name=display_name,
        permissions=permissions,
        description=f"{display_name} role for blog"
    )
    print(f"  ✓ Created role: {name}")
    return role


async def create_user_if_not_exists(auth, email: str, password: str, name: str, role: RoleModel) -> UserModel:
    """Create user if it doesn't exist"""
    existing = await UserModel.find_one(UserModel.email == email)
    if existing:
        print(f"  ✓ User '{email}' already exists")
        return existing

    # Split name into first and last
    name_parts = name.split(" ", 1)
    first_name = name_parts[0] if name_parts else ""
    last_name = name_parts[1] if len(name_parts) > 1 else ""

    user = await auth.user_service.create_user(
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
    )

    # Assign role via metadata (SimpleRBAC pattern)
    user.metadata["role_ids"] = [str(role.id)]
    await user.save()

    print(f"  ✓ Created user: {email} ({role.name})")
    return user


async def create_sample_posts(users: dict) -> None:
    """Create sample blog posts"""
    print("\n📝 Creating sample blog posts...")

    # Check if posts already exist
    existing_count = await BlogPost.count()
    if existing_count > 0:
        print(f"  ✓ {existing_count} blog posts already exist, skipping creation")
        return

    posts_data = [
        {
            "title": "Welcome to Our Blog!",
            "content": "This is the first post on our blog. We're excited to share our thoughts and ideas with you. This blog demonstrates the SimpleRBAC preset of OutlabsAuth, showing how role-based permissions work in a real-world application.",
            "author": users["admin"],
            "published": True,
            "tags": ["announcement", "welcome"]
        },
        {
            "title": "Getting Started with FastAPI",
            "content": "FastAPI is an amazing framework for building APIs with Python. In this post, we'll explore the basics of FastAPI and why it's become so popular. FastAPI provides automatic API documentation, data validation using Pydantic, and excellent performance.",
            "author": users["editor"],
            "published": True,
            "tags": ["fastapi", "python", "tutorial"]
        },
        {
            "title": "Understanding RBAC",
            "content": "Role-Based Access Control (RBAC) is a security paradigm where access decisions are based on the roles of individual users. In this post, we'll dive deep into RBAC concepts and how OutlabsAuth implements them.",
            "author": users["writer1"],
            "published": True,
            "tags": ["rbac", "security", "auth"]
        },
        {
            "title": "Building a Blog API",
            "content": "Let's build a complete blog API from scratch using FastAPI and MongoDB. We'll implement authentication, authorization, CRUD operations, and more. This tutorial will guide you through the entire process step by step.",
            "author": users["writer1"],
            "published": True,
            "tags": ["api", "tutorial", "mongodb"]
        },
        {
            "title": "JWT Authentication Explained",
            "content": "JSON Web Tokens (JWT) are a compact way to securely transmit information between parties. In this post, we'll explain how JWT works, why it's useful, and how to implement it in your applications using OutlabsAuth.",
            "author": users["editor"],
            "published": True,
            "tags": ["jwt", "authentication", "security"]
        },
        {
            "title": "Draft: Advanced MongoDB Queries",
            "content": "This is a draft post about advanced MongoDB queries. We'll cover aggregation pipelines, text search, geospatial queries, and more. Coming soon!",
            "author": users["writer2"],
            "published": False,
            "tags": ["mongodb", "database", "draft"]
        },
        {
            "title": "Python Best Practices",
            "content": "Writing clean, maintainable Python code is essential for long-term project success. In this post, we'll cover PEP 8, type hints, documentation, testing, and other best practices that will make your Python code shine.",
            "author": users["writer1"],
            "published": True,
            "tags": ["python", "best-practices", "code-quality"]
        },
        {
            "title": "Introduction to Async/Await",
            "content": "Asynchronous programming in Python can be confusing at first, but it's powerful once you understand it. This post explains async/await, asyncio, and how to write asynchronous code that's both performant and readable.",
            "author": users["editor"],
            "published": True,
            "tags": ["python", "async", "tutorial"]
        },
        {
            "title": "Draft: Microservices Architecture",
            "content": "This draft explores microservices architecture patterns. We'll discuss when to use microservices, how to design them, and common pitfalls to avoid. Still working on this one!",
            "author": users["writer2"],
            "published": False,
            "tags": ["microservices", "architecture", "draft"]
        },
        {
            "title": "API Design Principles",
            "content": "Good API design is crucial for developer experience. This post covers RESTful design principles, versioning strategies, error handling, documentation, and other important aspects of API design.",
            "author": users["writer1"],
            "published": True,
            "tags": ["api", "design", "rest"]
        },
        {
            "title": "Security in Web Applications",
            "content": "Web security is critical. This post covers common vulnerabilities like SQL injection, XSS, CSRF, and how to protect against them. We'll also discuss authentication, authorization, and secure coding practices.",
            "author": users["editor"],
            "published": True,
            "tags": ["security", "web", "vulnerabilities"]
        },
        {
            "title": "Testing FastAPI Applications",
            "content": "Testing is essential for reliable software. In this post, we'll explore how to test FastAPI applications using pytest, including unit tests, integration tests, and testing authentication flows.",
            "author": users["writer1"],
            "published": True,
            "tags": ["testing", "fastapi", "pytest"]
        },
        {
            "title": "Draft: Docker for Python Developers",
            "content": "Docker makes deploying Python applications much easier. This draft will cover Docker basics, creating Dockerfiles, docker-compose, and best practices for containerizing Python apps.",
            "author": users["writer2"],
            "published": False,
            "tags": ["docker", "deployment", "draft"]
        },
        {
            "title": "Database Indexing Strategies",
            "content": "Proper indexing can make your database queries 100x faster. This post explains how indexes work in MongoDB, when to use them, and common indexing strategies that will improve your application's performance.",
            "author": users["editor"],
            "published": True,
            "tags": ["mongodb", "performance", "indexing"]
        },
        {
            "title": "Year in Review 2024",
            "content": "As we wrap up 2024, let's look back at what we've accomplished this year. We've published 50+ articles, grown our community, and learned so much together. Thank you for being part of this journey!",
            "author": users["admin"],
            "published": True,
            "tags": ["announcement", "review", "2024"]
        }
    ]

    created_posts = []
    for i, post_data in enumerate(posts_data, 1):
        post = BlogPost(
            title=post_data["title"],
            content=post_data["content"],
            author_id=str(post_data["author"].id),
            author_name=post_data["author"].full_name,  # Uses property that combines first + last
            published=post_data["published"],
            tags=post_data["tags"]
        )
        await post.insert()
        created_posts.append(post)
        print(f"  ✓ Created post {i}/15: {post.title[:50]}{'...' if len(post.title) > 50 else ''}")

    return created_posts


async def create_sample_comments(posts: list, users: dict) -> None:
    """Create sample comments on blog posts"""
    print("\n💬 Creating sample comments...")

    # Check if comments already exist
    existing_count = await Comment.count()
    if existing_count > 0:
        print(f"  ✓ {existing_count} comments already exist, skipping creation")
        return

    # Add comments to first few published posts
    published_posts = [p for p in posts if p.published][:5]

    comments_data = [
        {
            "post": published_posts[0],  # Welcome post
            "author": users["reader"],
            "content": "Great to see this blog launch! Looking forward to more content."
        },
        {
            "post": published_posts[0],
            "author": users["writer1"],
            "content": "Welcome! Excited to contribute to this blog."
        },
        {
            "post": published_posts[1],  # FastAPI post
            "author": users["reader"],
            "content": "FastAPI is awesome! Thanks for this introduction."
        },
        {
            "post": published_posts[1],
            "author": users["writer2"],
            "content": "I've been using FastAPI for a year now. It's truly game-changing."
        },
        {
            "post": published_posts[2],  # RBAC post
            "author": users["reader"],
            "content": "This explains RBAC so clearly. Finally understand the concept!"
        },
        {
            "post": published_posts[3],  # Blog API post
            "author": users["reader"],
            "content": "Following along with this tutorial. Very helpful!"
        },
        {
            "post": published_posts[4],  # JWT post
            "author": users["writer1"],
            "content": "JWT is really useful for stateless authentication. Great explanation!"
        }
    ]

    for i, comment_data in enumerate(comments_data, 1):
        comment = Comment(
            post_id=str(comment_data["post"].id),
            author_id=str(comment_data["author"].id),
            author_name=comment_data["author"].full_name,  # Uses property that combines first + last
            content=comment_data["content"]
        )
        await comment.insert()
        print(f"  ✓ Created comment {i}/{len(comments_data)}")


async def seed_blog_demo():
    """Main seed function"""
    print("🌱 Seeding Blog Demo Data...\n")

    # Connect to MongoDB
    print("📦 Connecting to MongoDB...")
    client = AsyncIOMotorClient(MONGODB_URL)
    db = client[DATABASE_NAME]

    # Initialize OutlabsAuth
    print("🔐 Initializing OutlabsAuth SimpleRBAC...")
    auth = SimpleRBAC(
        database=db,
        secret_key=SECRET_KEY
    )

    # Initialize Beanie
    await init_beanie(
        database=db,
        document_models=[
            UserModel,
            RoleModel,
            PermissionModel,
            BlogPost,
            Comment
        ]
    )

    await auth.initialize()
    print("  ✓ Database initialized\n")

    # Create roles
    print("👥 Creating roles...")
    roles = {
        "reader": await create_role_if_not_exists(
            auth,
            "reader",
            ["post:read"],
            "Reader"
        ),
        "writer": await create_role_if_not_exists(
            auth,
            "writer",
            ["post:read", "post:create", "post:update_own", "post:delete_own", "comment:create"],
            "Writer"
        ),
        "editor": await create_role_if_not_exists(
            auth,
            "editor",
            ["post:*", "comment:*", "user:read"],
            "Editor"
        ),
        "admin": await create_role_if_not_exists(
            auth,
            "admin",
            ["*:*"],
            "Administrator"
        )
    }

    # Create demo users
    print("\n👤 Creating demo users...")
    users = {
        "admin": await create_user_if_not_exists(
            auth,
            "admin@blog.com",
            "password123",
            "Admin User",
            roles["admin"]
        ),
        "editor": await create_user_if_not_exists(
            auth,
            "editor@blog.com",
            "password123",
            "Editor User",
            roles["editor"]
        ),
        "writer1": await create_user_if_not_exists(
            auth,
            "writer1@blog.com",
            "password123",
            "Alice Writer",
            roles["writer"]
        ),
        "writer2": await create_user_if_not_exists(
            auth,
            "writer2@blog.com",
            "password123",
            "Bob Writer",
            roles["writer"]
        ),
        "reader": await create_user_if_not_exists(
            auth,
            "reader@blog.com",
            "password123",
            "Charlie Reader",
            roles["reader"]
        )
    }

    # Create sample posts
    posts = await create_sample_posts(users)

    # Create sample comments
    if posts:
        await create_sample_comments(posts, users)

    print("\n" + "="*60)
    print("✅ Blog demo data seeded successfully!")
    print("="*60)

    print("\n📋 Demo Credentials:")
    print("-" * 60)
    print("  Admin:     admin@blog.com     / password123")
    print("  Editor:    editor@blog.com    / password123")
    print("  Writer 1:  writer1@blog.com   / password123")
    print("  Writer 2:  writer2@blog.com   / password123")
    print("  Reader:    reader@blog.com    / password123")
    print("-" * 60)

    print("\n🧪 Test Scenarios:")
    print("-" * 60)
    print("  1. Login as reader → Can view posts, cannot create")
    print("  2. Login as writer1 → Create post → Can edit it")
    print("  3. Login as writer1 → Try to edit writer2's post → Denied")
    print("  4. Login as editor → Can edit any post")
    print("  5. Login as admin → Can delete posts, manage users")
    print("-" * 60)

    print("\n🚀 Start the API:")
    print("  uvicorn main:app --reload --port 8000")
    print("\n📚 API Docs:")
    print("  http://localhost:8000/docs")
    print("\n🎨 Connect Admin UI:")
    print("  cd auth-ui")
    print("  NUXT_PUBLIC_API_BASE_URL=http://localhost:8000/api npm run dev")
    print()

    client.close()


if __name__ == "__main__":
    asyncio.run(seed_blog_demo())
