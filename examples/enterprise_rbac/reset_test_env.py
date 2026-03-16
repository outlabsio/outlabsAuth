#!/usr/bin/env python3
"""
Reset Test Environment Script - EnterpriseRBAC Example
Resets the database to a known good state for testing entity hierarchy.

Usage:
    python reset_test_env.py

Environment Variables:
    DATABASE_URL: PostgreSQL connection string
                  (default: postgresql+asyncpg://postgres:postgres@localhost:5432/realestate_enterprise_rbac)
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path so we can import outlabs_auth
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from datetime import datetime, timezone

# Import domain models
from models import Lead, LeadNote
from sqlalchemy import select, text
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from outlabs_auth import (
    Entity,
    EntityClosure,
    EntityMembership,
    MembershipStatus,
    Permission,
    Role,
    User,
    UserRoleMembership,
    UserStatus,
)
from outlabs_auth.core.config import AuthConfig
from outlabs_auth.models.sql.entity_membership import EntityMembershipRole
from outlabs_auth.models.sql.enums import EntityClass
from outlabs_auth.models.sql.role import RolePermission
from outlabs_auth.utils.password import generate_password_hash

# Configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/realestate_enterprise_rbac",
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
    print("Connecting to PostgreSQL...")

    await _ensure_database_exists(DATABASE_URL)

    # Create engine
    engine = create_async_engine(DATABASE_URL, echo=False)

    # Create session factory
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Create all tables
    print("Creating tables...")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    print("Tables created")

    async with async_session() as session:
        # Drop existing test data (in correct order for foreign keys)
        print("Dropping existing test data...")

        # Delete in order respecting foreign keys
        # Use TRUNCATE ... CASCADE for efficiency, with IF EXISTS to handle first run
        tables_to_clear = [
            "entity_membership_roles",
            "entity_memberships",
            "entity_closure",
            "user_role_memberships",
            "role_permissions",
            "lead_notes",
            "leads",
            "entities",
            "roles",
            "permissions",
            "users",
        ]
        for table in tables_to_clear:
            try:
                await session.execute(text(f"DELETE FROM {table}"))
            except Exception:
                # Table might not exist on first run
                pass
        await session.commit()
        print("Test data cleared\n")

        # Create permissions
        print("Creating permissions...")
        permissions_data = [
            # User permissions
            {
                "name": "user:read",
                "display_name": "User Read",
                "resource": "user",
                "action": "read",
            },
            {
                "name": "user:read_tree",
                "display_name": "User Read Tree",
                "resource": "user",
                "action": "read_tree",
            },
            {
                "name": "user:create",
                "display_name": "User Create",
                "resource": "user",
                "action": "create",
            },
            {
                "name": "user:update",
                "display_name": "User Update",
                "resource": "user",
                "action": "update",
            },
            {
                "name": "user:delete",
                "display_name": "User Delete",
                "resource": "user",
                "action": "delete",
            },
            {
                "name": "user:manage",
                "display_name": "User Manage",
                "resource": "user",
                "action": "manage",
            },
            # Role permissions
            {
                "name": "role:read",
                "display_name": "Role Read",
                "resource": "role",
                "action": "read",
            },
            {
                "name": "role:create",
                "display_name": "Role Create",
                "resource": "role",
                "action": "create",
            },
            {
                "name": "role:update",
                "display_name": "Role Update",
                "resource": "role",
                "action": "update",
            },
            {
                "name": "role:delete",
                "display_name": "Role Delete",
                "resource": "role",
                "action": "delete",
            },
            # Permission permissions
            {
                "name": "permission:read",
                "display_name": "Permission Read",
                "resource": "permission",
                "action": "read",
            },
            {
                "name": "permission:create",
                "display_name": "Permission Create",
                "resource": "permission",
                "action": "create",
            },
            {
                "name": "permission:update",
                "display_name": "Permission Update",
                "resource": "permission",
                "action": "update",
            },
            # Entity permissions
            {
                "name": "entity:read",
                "display_name": "Entity Read",
                "resource": "entity",
                "action": "read",
            },
            {
                "name": "entity:read_tree",
                "display_name": "Entity Read Tree",
                "resource": "entity",
                "action": "read_tree",
            },
            {
                "name": "entity:create",
                "display_name": "Entity Create",
                "resource": "entity",
                "action": "create",
            },
            {
                "name": "entity:update",
                "display_name": "Entity Update",
                "resource": "entity",
                "action": "update",
            },
            {
                "name": "entity:delete",
                "display_name": "Entity Delete",
                "resource": "entity",
                "action": "delete",
            },
            # Lead permissions
            {
                "name": "lead:read",
                "display_name": "Lead Read",
                "resource": "lead",
                "action": "read",
            },
            {
                "name": "lead:read_tree",
                "display_name": "Lead Read Tree",
                "resource": "lead",
                "action": "read_tree",
            },
            {
                "name": "lead:create",
                "display_name": "Lead Create",
                "resource": "lead",
                "action": "create",
            },
            {
                "name": "lead:update",
                "display_name": "Lead Update",
                "resource": "lead",
                "action": "update",
            },
            {
                "name": "lead:delete",
                "display_name": "Lead Delete",
                "resource": "lead",
                "action": "delete",
            },
            # API Key permissions
            {
                "name": "apikey:read",
                "display_name": "API Key Read",
                "resource": "apikey",
                "action": "read",
            },
            {
                "name": "apikey:create",
                "display_name": "API Key Create",
                "resource": "apikey",
                "action": "create",
            },
            {
                "name": "apikey:revoke",
                "display_name": "API Key Revoke",
                "resource": "apikey",
                "action": "revoke",
            },
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

        await session.flush()
        print(f"   Created {len(permissions_map)} permissions\n")

        # Create roles
        print("Creating roles...")
        roles_data = [
            {
                "name": "agent",
                "display_name": "Agent",
                "description": "Real estate agent - can manage leads in their team",
                "permissions": [
                    "lead:read",
                    "lead:create",
                    "lead:update",
                ],
            },
            {
                "name": "team_lead",
                "display_name": "Team Lead",
                "description": "Team leader - can manage leads and view team members",
                "permissions": [
                    "lead:read",
                    "lead:read_tree",
                    "lead:create",
                    "lead:update",
                    "lead:delete",
                    "user:read",
                ],
            },
            {
                "name": "office_manager",
                "display_name": "Office Manager",
                "description": "Office manager - full access to office and all descendants",
                "permissions": [
                    "lead:read",
                    "lead:read_tree",
                    "lead:create",
                    "lead:update",
                    "lead:delete",
                    "user:read",
                    "user:read_tree",
                    "user:create",
                    "entity:read",
                    "entity:read_tree",
                ],
            },
            {
                "name": "admin",
                "display_name": "Administrator",
                "description": "Full system access",
                "permissions": list(permissions_map.keys()),
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
            await session.flush()

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

        # Create entities (Organization -> Region -> Office -> Team)
        print("Creating entity hierarchy...")

        # Helper to create closure table entries
        async def create_closure_for_entity(entity, parent_entity=None):
            """Create closure table entries for an entity."""
            # Self-reference
            self_closure = EntityClosure(
                ancestor_id=entity.id,
                descendant_id=entity.id,
                depth=0,
            )
            session.add(self_closure)

            # If has parent, copy parent's ancestors
            if parent_entity:
                stmt = select(EntityClosure).where(
                    EntityClosure.descendant_id == parent_entity.id
                )
                result = await session.execute(stmt)
                parent_closures = result.scalars().all()

                for pc in parent_closures:
                    ancestor_closure = EntityClosure(
                        ancestor_id=pc.ancestor_id,
                        descendant_id=entity.id,
                        depth=pc.depth + 1,
                    )
                    session.add(ancestor_closure)

        # Organization (root)
        org = Entity(
            name="acme_realty",
            display_name="ACME Realty",
            slug="acme-realty",
            description="ACME Real Estate Corporation",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
            parent_id=None,
            depth=0,
            path="/acme-realty",
            status="active",
        )
        session.add(org)
        await session.flush()
        await create_closure_for_entity(org)

        # Regions
        west_coast = Entity(
            name="west_coast",
            display_name="West Coast Region",
            slug="west-coast",
            description="West Coast operations",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="region",
            parent_id=org.id,
            depth=1,
            path="/acme-realty/west-coast",
            status="active",
        )
        session.add(west_coast)
        await session.flush()
        await create_closure_for_entity(west_coast, org)

        east_coast = Entity(
            name="east_coast",
            display_name="East Coast Region",
            slug="east-coast",
            description="East Coast operations",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="region",
            parent_id=org.id,
            depth=1,
            path="/acme-realty/east-coast",
            status="active",
        )
        session.add(east_coast)
        await session.flush()
        await create_closure_for_entity(east_coast, org)

        # Offices
        sf_office = Entity(
            name="sf_office",
            display_name="San Francisco Office",
            slug="sf-office",
            description="San Francisco branch office",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="office",
            parent_id=west_coast.id,
            depth=2,
            path="/acme-realty/west-coast/sf-office",
            status="active",
        )
        session.add(sf_office)
        await session.flush()
        await create_closure_for_entity(sf_office, west_coast)

        la_office = Entity(
            name="la_office",
            display_name="Los Angeles Office",
            slug="la-office",
            description="Los Angeles branch office",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="office",
            parent_id=west_coast.id,
            depth=2,
            path="/acme-realty/west-coast/la-office",
            status="active",
        )
        session.add(la_office)
        await session.flush()
        await create_closure_for_entity(la_office, west_coast)

        nyc_office = Entity(
            name="nyc_office",
            display_name="New York City Office",
            slug="nyc-office",
            description="NYC branch office",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="office",
            parent_id=east_coast.id,
            depth=2,
            path="/acme-realty/east-coast/nyc-office",
            status="active",
        )
        session.add(nyc_office)
        await session.flush()
        await create_closure_for_entity(nyc_office, east_coast)

        # Teams (ACCESS_GROUP entities)
        sf_residential = Entity(
            name="sf_residential",
            display_name="SF Residential Team",
            slug="sf-residential",
            description="San Francisco residential real estate team",
            entity_class=EntityClass.ACCESS_GROUP,
            entity_type="team",
            parent_id=sf_office.id,
            depth=3,
            path="/acme-realty/west-coast/sf-office/sf-residential",
            status="active",
        )
        session.add(sf_residential)
        await session.flush()
        await create_closure_for_entity(sf_residential, sf_office)

        sf_commercial = Entity(
            name="sf_commercial",
            display_name="SF Commercial Team",
            slug="sf-commercial",
            description="San Francisco commercial real estate team",
            entity_class=EntityClass.ACCESS_GROUP,
            entity_type="team",
            parent_id=sf_office.id,
            depth=3,
            path="/acme-realty/west-coast/sf-office/sf-commercial",
            status="active",
        )
        session.add(sf_commercial)
        await session.flush()
        await create_closure_for_entity(sf_commercial, sf_office)

        await session.flush()
        print("   Created entity hierarchy:")
        print("   - ACME Realty (organization)")
        print("     - West Coast Region")
        print("       - San Francisco Office")
        print("         - SF Residential Team")
        print("         - SF Commercial Team")
        print("       - Los Angeles Office")
        print("     - East Coast Region")
        print("       - New York City Office\n")

        entities_map = {
            "org": org,
            "west_coast": west_coast,
            "east_coast": east_coast,
            "sf_office": sf_office,
            "la_office": la_office,
            "nyc_office": nyc_office,
            "sf_residential": sf_residential,
            "sf_commercial": sf_commercial,
        }

        # Create config for password hashing
        config = AuthConfig(secret_key="test-secret-key")

        # Create test users with role assignments
        print("Creating test users...")
        users_data = [
            {
                "email": "admin@acme.com",
                "password": "Testpass1!",
                "first_name": "System",
                "last_name": "Admin",
                "role": "admin",
                "is_superuser": True,
                "entity_memberships": [("org", "admin")],
            },
            {
                "email": "manager@sf.acme.com",
                "password": "Testpass1!",
                "first_name": "Sarah",
                "last_name": "Manager",
                "role": "office_manager",
                "is_superuser": False,
                "entity_memberships": [("sf_office", "office_manager")],
            },
            {
                "email": "lead@sf.acme.com",
                "password": "Testpass1!",
                "first_name": "Tom",
                "last_name": "TeamLead",
                "role": "team_lead",
                "is_superuser": False,
                "entity_memberships": [("sf_residential", "team_lead")],
            },
            {
                "email": "agent@sf.acme.com",
                "password": "Testpass1!",
                "first_name": "Jane",
                "last_name": "Agent",
                "role": "agent",
                "is_superuser": False,
                "entity_memberships": [("sf_residential", "agent")],
            },
        ]

        users_map = {}
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
            await session.flush()
            users_map[user_data["email"]] = user

            # Create global role assignment
            role = roles_map[user_data["role"]]
            membership = UserRoleMembership(
                user_id=user.id,
                role_id=role.id,
                status=MembershipStatus.ACTIVE,
                assigned_at=datetime.now(timezone.utc),
            )
            session.add(membership)

            # Create entity memberships
            for entity_key, role_name in user_data["entity_memberships"]:
                entity = entities_map[entity_key]
                role = roles_map[role_name]

                entity_membership = EntityMembership(
                    user_id=user.id,
                    entity_id=entity.id,
                    status=MembershipStatus.ACTIVE,
                    joined_at=datetime.now(timezone.utc),
                )
                session.add(entity_membership)
                await session.flush()

                # Add role to membership
                membership_role = EntityMembershipRole(
                    membership_id=entity_membership.id,
                    role_id=role.id,
                )
                session.add(membership_role)

        await session.commit()
        print(f"   Created {len(users_data)} test users with entity memberships\n")

        # --------------------------------------------------------------------
        # ABAC demo conditions
        # --------------------------------------------------------------------
        # We intentionally do NOT write ABAC conditions directly in this reset script.
        # The example smoke runner seeds ABAC via the public API endpoints:
        #   POST /v1/roles/{role_id}/conditions
        # This keeps examples aligned with how a real integration would configure ABAC.
        print(
            "ABAC demo conditions: seeded via API (see scripts/smoke_enterprise_api.py)\n"
        )

    # Close engine
    await engine.dispose()

    # Print credentials
    print("=" * 60)
    print("Test Environment Reset Complete!")
    print("=" * 60)
    print("\nTest User Credentials:\n")

    for user_data in users_data:
        print(
            f"   {user_data['first_name']} {user_data['last_name']} ({user_data['role']})"
        )
        print(f"   Email:    {user_data['email']}")
        print(f"   Password: {user_data['password']}")
        print(f"   Entities: {[e[0] for e in user_data['entity_memberships']]}")
        print()

    print("URLs:")
    print(f"   Backend:  http://localhost:8004")
    print(f"   API Docs: http://localhost:8004/docs")
    print(f"   Admin UI: http://localhost:3000")
    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(reset_database())
