#!/usr/bin/env python3
"""
Reset Test Environment Script
Quickly resets the SimpleRBAC example database to a known good state for testing.

Usage:
    uv run python reset_test_env.py

Environment Variables:
    DATABASE_URL: PostgreSQL connection string
                  (default: postgresql+asyncpg://postgres:postgres@localhost:5432/blog_simple_rbac)
"""

import asyncio
import os
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from outlabs_auth import (
    User,
    Role,
    Permission,
    UserRoleMembership,
    MembershipStatus,
    UserStatus,
)
from outlabs_auth.cli import run_migrations
from outlabs_auth.models.sql.role import RolePermission
from outlabs_auth.utils.password import generate_password_hash
from outlabs_auth.core.config import AuthConfig

# Import blog models
from models import BlogPost, Comment

# Configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/blog_simple_rbac"
)


async def _ensure_database_exists(database_url: str) -> None:
    url = make_url(database_url)
    if url.get_backend_name() != "postgresql":
        return

    db_name = url.database
    if not db_name:
        return

    if not all(c.isalnum() or c == "_" for c in db_name):
        raise RuntimeError(f"Unsafe database name in DATABASE_URL: {db_name!r}")

    admin_url = url.set(database="postgres")
    admin_engine = create_async_engine(
        admin_url, echo=False, isolation_level="AUTOCOMMIT"
    )
    try:
        async with admin_engine.connect() as conn:
            exists = await conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": db_name},
            )
            if exists.scalar_one_or_none() is None:
                await conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    finally:
        await admin_engine.dispose()


async def reset_database():
    """Reset database to clean test state using SQLAlchemy."""
    print("🔄 Connecting to PostgreSQL...")

    await _ensure_database_exists(DATABASE_URL)
    await run_migrations(DATABASE_URL)

    # Create engine
    engine = create_async_engine(DATABASE_URL, echo=False)

    # Create session factory
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    # Create all tables
    print("📝 Creating tables...")
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: SQLModel.metadata.create_all(
                sync_conn,
                tables=[BlogPost.__table__, Comment.__table__],
            )
        )
    print("✅ Tables created")

    async with async_session() as session:
        # Drop existing test data (in correct order for foreign keys)
        print("🗑️  Dropping existing test data...")

        # Delete in order respecting foreign keys
        await session.execute(text("DELETE FROM user_role_memberships"))
        await session.execute(text("DELETE FROM role_permissions"))
        await session.execute(text("DELETE FROM comments"))
        await session.execute(text("DELETE FROM blog_posts"))
        await session.execute(text("DELETE FROM roles"))
        await session.execute(text("DELETE FROM permissions"))
        await session.execute(text("DELETE FROM users"))
        await session.commit()
        print("✅ Test data cleared\n")

        # Create permissions
        print("📝 Creating permissions...")
        permissions_data = [
            # User permissions
            {"name": "user:read", "display_name": "User Read", "resource": "user", "action": "read"},
            {"name": "user:create", "display_name": "User Create", "resource": "user", "action": "create"},
            {"name": "user:update", "display_name": "User Update", "resource": "user", "action": "update"},
            {"name": "user:delete", "display_name": "User Delete", "resource": "user", "action": "delete"},
            {"name": "user:manage", "display_name": "User Manage", "resource": "user", "action": "manage"},
            # Role permissions
            {"name": "role:read", "display_name": "Role Read", "resource": "role", "action": "read"},
            {"name": "role:create", "display_name": "Role Create", "resource": "role", "action": "create"},
            {"name": "role:update", "display_name": "Role Update", "resource": "role", "action": "update"},
            {"name": "role:delete", "display_name": "Role Delete", "resource": "role", "action": "delete"},
            # Permission permissions
            {"name": "permission:read", "display_name": "Permission Read", "resource": "permission", "action": "read"},
            {"name": "permission:create", "display_name": "Permission Create", "resource": "permission", "action": "create"},
            {"name": "permission:update", "display_name": "Permission Update", "resource": "permission", "action": "update"},
            # API Key permissions
            {"name": "api_key:read", "display_name": "API Key Read", "resource": "api_key", "action": "read"},
            {"name": "api_key:create", "display_name": "API Key Create", "resource": "api_key", "action": "create"},
            {"name": "api_key:revoke", "display_name": "API Key Revoke", "resource": "api_key", "action": "revoke"},
            # Blog-specific permissions
            {"name": "post:read", "display_name": "Post Read", "resource": "post", "action": "read"},
            {"name": "post:create", "display_name": "Post Create", "resource": "post", "action": "create"},
            {"name": "post:update", "display_name": "Post Update", "resource": "post", "action": "update"},
            {"name": "post:update_own", "display_name": "Post Update Own", "resource": "post", "action": "update_own"},
            {"name": "post:delete", "display_name": "Post Delete", "resource": "post", "action": "delete"},
            {"name": "post:delete_own", "display_name": "Post Delete Own", "resource": "post", "action": "delete_own"},
            {"name": "comment:create", "display_name": "Comment Create", "resource": "comment", "action": "create"},
            {"name": "comment:delete", "display_name": "Comment Delete", "resource": "comment", "action": "delete"},
            {"name": "comment:delete_own", "display_name": "Comment Delete Own", "resource": "comment", "action": "delete_own"},
        ]

        permissions_map = {}
        for perm_data in permissions_data:
            perm = Permission(
                name=perm_data["name"],
                display_name=perm_data["display_name"],
                resource=perm_data["resource"],
                action=perm_data["action"],
                description=f"Permission to {perm_data['action']} {perm_data['resource']}",
                is_system=True,
                is_active=True,
            )
            session.add(perm)
            permissions_map[perm_data["name"]] = perm

        await session.flush()  # Get IDs
        print(f"   Created {len(permissions_map)} permissions\n")

        # Create roles
        print("🎭 Creating roles...")
        roles_data = [
            {
                "name": "reader",
                "display_name": "Reader",
                "description": "Read-only access to blog posts",
                "permissions": ["post:read"],
            },
            {
                "name": "writer",
                "display_name": "Writer",
                "description": "Can create and manage own blog posts",
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
                "description": "Can manage all blog content",
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
                "name": "admin",
                "display_name": "Administrator",
                "description": "Full system access",
                "permissions": [
                    "post:read",
                    "post:create",
                    "post:update",
                    "post:delete",
                    "comment:create",
                    "comment:delete",
                    "user:read",
                    "user:create",
                    "user:update",
                    "user:delete",
                    "user:manage",
                    "role:read",
                    "role:create",
                    "role:update",
                    "role:delete",
                    "permission:read",
                    "permission:create",
                    "permission:update",
                    "api_key:read",
                    "api_key:create",
                    "api_key:revoke",
                ],
            },
        ]

        roles_map = {}
        for role_data in roles_data:
            role = Role(
                name=role_data["name"],
                display_name=role_data["display_name"],
                description=role_data["description"],
                is_system_role=True,
                is_global=True,
            )
            session.add(role)
            await session.flush()  # Get role ID

            # Add permissions via junction table
            for perm_name in role_data["permissions"]:
                if perm_name in permissions_map:
                    role_perm = RolePermission(
                        role_id=role.id,
                        permission_id=permissions_map[perm_name].id,
                    )
                    session.add(role_perm)

            roles_map[role_data["name"]] = role

        await session.flush()
        print(f"   Created {len(roles_map)} roles\n")

        # Create config for password hashing
        config = AuthConfig(secret_key="test-secret-key")

        # Create test users with role assignments
        print("👥 Creating test users...")
        users_data = [
            {
                "email": "admin@test.com",
                "password": "Test123!!",
                "first_name": "Admin",
                "last_name": "User",
                "role": "admin",
                "is_superuser": True,
            },
            {
                "email": "editor@test.com",
                "password": "Test123!!",
                "first_name": "Editor",
                "last_name": "User",
                "role": "editor",
                "is_superuser": False,
            },
            {
                "email": "writer@test.com",
                "password": "Test123!!",
                "first_name": "Writer",
                "last_name": "User",
                "role": "writer",
                "is_superuser": False,
            },
        ]

        for user_data in users_data:
            # Create user
            user = User(
                email=user_data["email"],
                hashed_password=generate_password_hash(user_data["password"], config),
                first_name=user_data["first_name"],
                last_name=user_data["last_name"],
                is_superuser=user_data["is_superuser"],
                status=UserStatus.ACTIVE,
                email_verified=True,
            )
            session.add(user)
            await session.flush()  # Get user ID

            # Assign role using UserRoleMembership
            role = roles_map[user_data["role"]]
            membership = UserRoleMembership(
                user_id=user.id,
                role_id=role.id,
                status=MembershipStatus.ACTIVE,
                assigned_at=datetime.now(timezone.utc),
            )
            session.add(membership)

        await session.commit()
        print(f"   Created {len(users_data)} test users with role assignments\n")

    # Close engine
    await engine.dispose()

    # Print credentials
    print("=" * 60)
    print("✅ Test Environment Reset Complete!")
    print("=" * 60)
    print("\n📋 Test User Credentials:\n")

    for user_data in users_data:
        role_display = roles_map[user_data["role"]].display_name
        print(f"   {user_data['first_name']} {user_data['last_name']} ({role_display})")
        print(f"   Email:    {user_data['email']}")
        print(f"   Password: {user_data['password']}")
        print()

    print("🌐 Application URLs:")
    print(f"   Backend:  http://localhost:8003")
    print(f"   API Docs: http://localhost:8003/docs")
    print(f"   Admin UI: http://localhost:3000")
    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(reset_database())
