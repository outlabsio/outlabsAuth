#!/usr/bin/env python3
"""
Reset Test Environment Script - ABAC Cookbook Example

Creates a minimal set of:
  - users (admin + editor)
  - permissions + editor role
  - sample documents with different statuses

ABAC conditions are intentionally configured via API (see scripts/smoke_abac_cookbook.py).
"""

import asyncio
import os
import sys
import uuid
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from models import Document
from sqlalchemy import text
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from outlabs_auth import (
    MembershipStatus,
    Permission,
    Role,
    RolePermission,
    User,
    UserRoleMembership,
    UserStatus,
)
from outlabs_auth.core.config import AuthConfig
from outlabs_auth.utils.password import generate_password_hash

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/abac_cookbook",
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


async def reset_database() -> None:
    await _ensure_database_exists(DATABASE_URL)
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)

    async with async_session() as session:
        tables_to_clear = [
            "user_role_memberships",
            "role_permissions",
            "documents",
            "roles",
            "permissions",
            "users",
        ]
        for table in tables_to_clear:
            try:
                await session.execute(text(f"DELETE FROM {table}"))
            except Exception:
                pass
        await session.commit()

        permissions = [
            ("document:read", "Document Read", "document", "read"),
            ("document:create", "Document Create", "document", "create"),
            ("document:update", "Document Update", "document", "update"),
            ("role:read", "Role Read", "role", "read"),
            ("role:update", "Role Update", "role", "update"),
        ]

        perm_map: dict[str, Permission] = {}
        for name, display, resource, action in permissions:
            p = Permission(
                name=name,
                display_name=display,
                resource=resource,
                action=action,
                description=f"{name} (cookbook)",
                is_system=True,
                is_active=True,
            )
            session.add(p)
            perm_map[name] = p
        await session.flush()

        editor_role = Role(
            name="editor",
            display_name="Editor",
            description="Can update documents (ABAC constrained)",
            is_system_role=True,
            is_global=True,
        )
        session.add(editor_role)
        await session.flush()

        for perm_name in (
            "document:read",
            "document:create",
            "document:update",
            "role:read",
        ):
            session.add(
                RolePermission(
                    role_id=editor_role.id,
                    permission_id=perm_map[perm_name].id,
                )
            )

        config = AuthConfig(secret_key="test-secret-key")
        admin = User(
            email="admin@cookbook.example.com",
            hashed_password=generate_password_hash("Test123!!", config),
            first_name="Admin",
            last_name="Cookbook",
            is_superuser=True,
            status=UserStatus.ACTIVE,
            email_verified=True,
        )
        editor = User(
            email="editor@cookbook.example.com",
            hashed_password=generate_password_hash("Test123!!", config),
            first_name="Editor",
            last_name="Cookbook",
            is_superuser=False,
            status=UserStatus.ACTIVE,
            email_verified=True,
        )
        session.add(admin)
        session.add(editor)
        await session.flush()

        session.add(
            UserRoleMembership(
                user_id=editor.id,
                role_id=editor_role.id,
                status=MembershipStatus.ACTIVE,
            )
        )

        docs = [
            Document(title="Draft doc", status="draft", created_by=editor.id),
            Document(title="Review doc", status="review", created_by=editor.id),
            Document(title="Published doc", status="published", created_by=editor.id),
        ]
        for d in docs:
            session.add(d)
        await session.flush()
        await session.commit()

        print("\nABAC Cookbook seed complete")
        print(f"DB: {DATABASE_URL}")
        print("Users:")
        print("  admin@cookbook.example.com / Test123!! (superuser)")
        print("  editor@cookbook.example.com / Test123!! (role: editor)")
        print("Documents:")
        for d in docs:
            print(f"  {d.status:9s} {d.id}  {d.title}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(reset_database())
