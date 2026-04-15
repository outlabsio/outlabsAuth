#!/usr/bin/env python3
"""
Reset Test Environment Script - EnterpriseRBAC Example
Resets the database to a known good state for testing entity hierarchy.

Usage:
    uv run python reset_test_env.py

Environment Variables:
    DATABASE_URL: PostgreSQL connection string
                  (default: postgresql+asyncpg://postgres:postgres@localhost:5432/realestate_enterprise_rbac)
"""

import asyncio
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from models import Lead, LeadNote
from outlabs_auth import (
    EnterpriseRBAC,
    Entity,
    EntityClosure,
    MembershipStatus,
    Permission,
    Role,
    UserStatus,
)
from outlabs_auth.cli import run_migrations
from outlabs_auth.models.sql.enums import ConditionOperator, EntityClass, RoleScope
from outlabs_auth.models.sql.permission import PermissionCondition
from outlabs_auth.models.sql.role import ConditionGroup, RoleCondition, RolePermission

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
    await run_migrations(DATABASE_URL)

    auth = EnterpriseRBAC(
        database_url=DATABASE_URL,
        secret_key="example-reset-secret-key",
        auto_migrate=False,
        enable_context_aware_roles=True,
        enable_abac=True,
        enable_token_cleanup=False,
    )
    await auth.initialize()
    engine = auth.engine

    # Create session factory
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Create example-owned tables only. Auth tables are managed by migrations.
    print("Ensuring tables...")
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: SQLModel.metadata.create_all(
                sync_conn,
                tables=[Lead.__table__, LeadNote.__table__],
            )
        )
    print("Tables ready")

    try:
        async with async_session() as session:
            print("Dropping existing test data...")
            table_names_result = await session.execute(
                text(
                    """
                    SELECT quote_ident(tablename)
                    FROM pg_tables
                    WHERE schemaname = current_schema()
                      AND tablename != 'outlabs_auth_alembic_version'
                    ORDER BY tablename
                    """
                )
            )
            table_names = [str(row[0]) for row in table_names_result]
            if table_names:
                await session.execute(
                    text(f"TRUNCATE TABLE {', '.join(table_names)} RESTART IDENTITY CASCADE")
                )
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
            {
                "name": "permission:delete",
                "display_name": "Permission Delete",
                "resource": "permission",
                "action": "delete",
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
            # Membership permissions
            {
                "name": "membership:create",
                "display_name": "Membership Create",
                "resource": "membership",
                "action": "create",
            },
            {
                "name": "membership:read",
                "display_name": "Membership Read",
                "resource": "membership",
                "action": "read",
            },
            {
                "name": "membership:read_tree",
                "display_name": "Membership Read Tree",
                "resource": "membership",
                "action": "read_tree",
            },
            {
                "name": "membership:update",
                "display_name": "Membership Update",
                "resource": "membership",
                "action": "update",
            },
            {
                "name": "membership:update_tree",
                "display_name": "Membership Update Tree",
                "resource": "membership",
                "action": "update_tree",
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
            {
                "name": "lead:escalate_after_hours",
                "display_name": "Lead Escalate After Hours",
                "resource": "lead",
                "action": "escalate_after_hours",
                "description": "Custom permission for emergency lead escalation workflows after standard operating hours.",
                "is_system": False,
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
            # API Key permissions used by the current admin surface
            {
                "name": "api_key:read",
                "display_name": "API Key Read",
                "resource": "api_key",
                "action": "read",
            },
            {
                "name": "api_key:create",
                "display_name": "API Key Create",
                "resource": "api_key",
                "action": "create",
            },
            {
                "name": "api_key:read_tree",
                "display_name": "API Key Read Tree",
                "resource": "api_key",
                "action": "read_tree",
            },
            {
                "name": "api_key:create_tree",
                "display_name": "API Key Create Tree",
                "resource": "api_key",
                "action": "create_tree",
            },
            {
                "name": "api_key:update",
                "display_name": "API Key Update",
                "resource": "api_key",
                "action": "update",
            },
            {
                "name": "api_key:delete",
                "display_name": "API Key Delete",
                "resource": "api_key",
                "action": "delete",
            },
            {
                "name": "api_key:update_tree",
                "display_name": "API Key Update Tree",
                "resource": "api_key",
                "action": "update_tree",
            },
            {
                "name": "api_key:delete_tree",
                "display_name": "API Key Delete Tree",
                "resource": "api_key",
                "action": "delete_tree",
            },
        ]

        permissions_map = {}
        for perm_data in permissions_data:
            perm = Permission(
                name=perm_data["name"],
                display_name=perm_data["display_name"],
                resource=perm_data["resource"],
                action=perm_data["action"],
                description=perm_data.get(
                    "description",
                    f"Permission to {perm_data['action']} {perm_data['resource']}",
                ),
                is_system=perm_data.get("is_system", True),
                is_active=True,
            )
            session.add(perm)
            permissions_map[perm_data["name"]] = perm

        await session.flush()
        print(f"   Created {len(permissions_map)} permissions\n")

        # Create base/system roles before entities exist. Additional scoped roles are
        # created after the hierarchy so they can reference real root/scope entities.
        print("Creating roles...")
        roles_map = {}
        seeded_roles_for_manifest = []

        async def create_role_record(
            *,
            name: str,
            display_name: str,
            description: str,
            permission_names: list[str],
            is_system_role: bool,
            is_global: bool,
            root_entity_id=None,
            scope_entity_id=None,
            scope: RoleScope = RoleScope.HIERARCHY,
            is_auto_assigned: bool = False,
            assignable_at_types: list[str] | None = None,
        ) -> Role:
            role = Role(
                name=name,
                display_name=display_name,
                description=description,
                is_system_role=is_system_role,
                is_global=is_global,
                root_entity_id=root_entity_id,
                scope_entity_id=scope_entity_id,
                scope=scope,
                is_auto_assigned=is_auto_assigned,
                assignable_at_types=assignable_at_types or [],
            )
            session.add(role)
            await session.flush()

            for permission_name in permission_names:
                permission = permissions_map.get(permission_name)
                if permission is None:
                    continue
                session.add(
                    RolePermission(
                        role_id=role.id,
                        permission_id=permission.id,
                    )
                )

            roles_map[name] = role
            seeded_roles_for_manifest.append(role)
            return role

        base_roles_data = [
            {
                "name": "agent",
                "display_name": "Agent",
                "description": "Real estate agent who can manage leads within a team.",
                "permission_names": [
                    "lead:read",
                    "lead:create",
                    "lead:update",
                ],
            },
            {
                "name": "team_lead",
                "display_name": "Team Lead",
                "description": "Team lead who can manage leads and inspect nearby user activity.",
                "permission_names": [
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
                "description": "Office manager with broad office-level operational visibility.",
                "permission_names": [
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
                "description": "Full system access.",
                "permission_names": list(permissions_map.keys()),
            },
            {
                "name": "service_reader",
                "display_name": "Service Reader",
                "description": "Machine-safe global role for service accounts and system API keys.",
                "permission_names": [
                    "entity:read",
                    "entity:read_tree",
                    "membership:read",
                    "membership:read_tree",
                    "user:read",
                    "user:read_tree",
                ],
            },
        ]

        for role_data in base_roles_data:
            await create_role_record(
                name=role_data["name"],
                display_name=role_data["display_name"],
                description=role_data["description"],
                permission_names=role_data["permission_names"],
                is_system_role=True,
                is_global=True,
            )

        await session.flush()

        seed_now = datetime.now(timezone.utc)

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
            allowed_child_types=["region"],
            allowed_child_classes=["structural"],
            max_depth=3,
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
            allowed_child_types=["office"],
            allowed_child_classes=["structural"],
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
            allowed_child_types=["office"],
            allowed_child_classes=["structural"],
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
            allowed_child_types=["team"],
            allowed_child_classes=["access_group"],
            max_members=40,
        )
        session.add(sf_office)
        await session.flush()
        await create_closure_for_entity(sf_office, west_coast)

        la_office = Entity(
            name="la_office",
            display_name="Los Angeles Office",
            slug="la-office",
            description="Los Angeles branch office. Seeded as inactive to exercise lifecycle messaging.",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="office",
            parent_id=west_coast.id,
            depth=2,
            path="/acme-realty/west-coast/la-office",
            status="inactive",
            allowed_child_types=["team"],
            allowed_child_classes=["access_group"],
            valid_until=seed_now + timedelta(days=90),
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
            allowed_child_types=["team"],
            allowed_child_classes=["access_group"],
            max_members=25,
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
            max_members=12,
            valid_from=seed_now - timedelta(days=120),
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
            max_members=10,
        )
        session.add(sf_commercial)
        await session.flush()
        await create_closure_for_entity(sf_commercial, sf_office)

        summit_org = Entity(
            name="summit_commercial",
            display_name="Summit Commercial",
            slug="summit-commercial",
            description="Second organization root for multi-root browser testing.",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
            parent_id=None,
            depth=0,
            path="/summit-commercial",
            status="active",
            allowed_child_types=["region"],
            allowed_child_classes=["structural"],
            max_depth=3,
        )
        session.add(summit_org)
        await session.flush()
        await create_closure_for_entity(summit_org)

        texas_region = Entity(
            name="texas_region",
            display_name="Texas Region",
            slug="texas-region",
            description="Summit regional operations across Texas.",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="region",
            parent_id=summit_org.id,
            depth=1,
            path="/summit-commercial/texas-region",
            status="active",
            allowed_child_types=["office"],
            allowed_child_classes=["structural"],
        )
        session.add(texas_region)
        await session.flush()
        await create_closure_for_entity(texas_region, summit_org)

        austin_office = Entity(
            name="austin_office",
            display_name="Austin Office",
            slug="austin-office",
            description="Austin commercial sales office.",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="office",
            parent_id=texas_region.id,
            depth=2,
            path="/summit-commercial/texas-region/austin-office",
            status="active",
            allowed_child_types=["team"],
            allowed_child_classes=["access_group"],
            max_members=30,
        )
        session.add(austin_office)
        await session.flush()
        await create_closure_for_entity(austin_office, texas_region)

        austin_growth = Entity(
            name="austin_growth",
            display_name="Austin Growth Team",
            slug="austin-growth",
            description="Summit pipeline generation team for Austin.",
            entity_class=EntityClass.ACCESS_GROUP,
            entity_type="team",
            parent_id=austin_office.id,
            depth=3,
            path="/summit-commercial/texas-region/austin-office/austin-growth",
            status="active",
            max_members=15,
            valid_from=seed_now - timedelta(days=45),
        )
        session.add(austin_growth)
        await session.flush()
        await create_closure_for_entity(austin_growth, austin_office)

        await session.flush()
        print("   Created entity hierarchy:")
        print("   - ACME Realty (organization)")
        print("     - West Coast Region")
        print("       - San Francisco Office")
        print("         - SF Residential Team")
        print("         - SF Commercial Team")
        print("       - Los Angeles Office")
        print("     - East Coast Region")
        print("       - New York City Office")
        print("   - Summit Commercial (organization)")
        print("     - Texas Region")
        print("       - Austin Office")
        print("         - Austin Growth Team\n")

        entities_map = {
            "org": org,
            "west_coast": west_coast,
            "east_coast": east_coast,
            "sf_office": sf_office,
            "la_office": la_office,
            "nyc_office": nyc_office,
            "sf_residential": sf_residential,
            "sf_commercial": sf_commercial,
            "summit_org": summit_org,
            "texas_region": texas_region,
            "austin_office": austin_office,
            "austin_growth": austin_growth,
        }

        demo_roles_data = [
            {
                "name": "scoped_roles_admin",
                "display_name": "Scoped Roles Admin",
                "description": "Directly grants role-management permissions. Pair it with user root or entity scope to limit what that admin can actually change.",
                "permission_names": [
                    "role:read",
                    "role:create",
                    "role:update",
                    "role:delete",
                    "user:read",
                    "user:read_tree",
                    "entity:read",
                    "entity:read_tree",
                ],
                "is_global": True,
                "is_system_role": False,
            },
            {
                "name": "permission_catalog_admin",
                "display_name": "Permission Catalog Admin",
                "description": "Global permission administrator who can mint custom permissions and manage permission-level ABAC without full superuser access.",
                "permission_names": [
                    "permission:read",
                    "permission:create",
                    "permission:update",
                    "permission:delete",
                    "role:read",
                    "user:read",
                ],
                "is_global": True,
                "is_system_role": False,
            },
            {
                "name": "acme_org_admin",
                "display_name": "ACME Org Admin",
                "description": "Top-level ACME admin role. Intended for organization operators who manage roles across the full root scope.",
                "permission_names": [
                    "api_key:read_tree",
                    "api_key:create_tree",
                    "api_key:update_tree",
                    "api_key:delete_tree",
                    "membership:read_tree",
                    "role:read",
                    "role:create",
                    "role:update",
                    "role:delete",
                    "user:read",
                    "user:read_tree",
                    "user:create",
                    "entity:read",
                    "entity:read_tree",
                ],
                "is_global": False,
                "is_system_role": False,
                "root_entity_key": "org",
            },
            {
                "name": "acme_auditor",
                "display_name": "ACME Auditor",
                "description": "Read-only organization role for audit and review workflows.",
                "permission_names": [
                    "role:read",
                    "user:read",
                    "user:read_tree",
                    "entity:read",
                    "entity:read_tree",
                    "lead:read",
                    "lead:read_tree",
                ],
                "is_global": False,
                "is_system_role": False,
                "root_entity_key": "org",
            },
            {
                "name": "office_dispatch_coordinator",
                "display_name": "Office Dispatch Coordinator",
                "description": "Root-scoped example role that is only intended to be assigned at office memberships.",
                "permission_names": [
                    "lead:read",
                    "lead:update",
                    "user:read",
                    "entity:read",
                ],
                "is_global": False,
                "is_system_role": False,
                "root_entity_key": "org",
                "assignable_at_types": ["office"],
            },
            {
                "name": "west_coast_hierarchy_admin",
                "display_name": "West Coast Hierarchy Admin",
                "description": "Entity-defined admin role from West Coast. It applies at the region and all descendants.",
                "permission_names": [
                    "api_key:read_tree",
                    "api_key:create_tree",
                    "api_key:update_tree",
                    "api_key:delete_tree",
                    "membership:read_tree",
                    "role:read",
                    "role:create",
                    "role:update",
                    "user:read",
                    "user:read_tree",
                    "entity:read",
                    "entity:read_tree",
                    "lead:read",
                    "lead:read_tree",
                ],
                "is_global": False,
                "is_system_role": False,
                "root_entity_key": "org",
                "scope_entity_key": "west_coast",
                "scope": RoleScope.HIERARCHY,
                "assignable_at_types": ["region", "office", "team"],
            },
            {
                "name": "sf_office_local_admin",
                "display_name": "SF Office Local Admin",
                "description": "Entity-only admin role defined at the San Francisco office. It stays local and does not inherit to teams.",
                "permission_names": [
                    "api_key:read",
                    "api_key:create",
                    "api_key:update",
                    "api_key:delete",
                    "membership:read",
                    "role:read",
                    "role:create",
                    "role:update",
                    "user:read",
                    "entity:read",
                    "lead:read",
                    "lead:update",
                ],
                "is_global": False,
                "is_system_role": False,
                "root_entity_key": "org",
                "scope_entity_key": "sf_office",
                "scope": RoleScope.ENTITY_ONLY,
                "assignable_at_types": ["office"],
            },
            {
                "name": "sf_team_member_default",
                "display_name": "SF Team Default Member",
                "description": "Auto-assigned example role for SF Residential memberships. Useful for testing inherited defaults and blast radius messaging.",
                "permission_names": [
                    "lead:read",
                    "lead:create",
                ],
                "is_global": False,
                "is_system_role": False,
                "root_entity_key": "org",
                "scope_entity_key": "sf_residential",
                "scope": RoleScope.HIERARCHY,
                "is_auto_assigned": True,
                "assignable_at_types": ["team"],
            },
            {
                "name": "east_coast_hierarchy_admin",
                "display_name": "East Coast Hierarchy Admin",
                "description": "Sibling branch admin role for East Coast scope filtering and scoped admin review.",
                "permission_names": [
                    "api_key:read_tree",
                    "api_key:create_tree",
                    "api_key:update_tree",
                    "api_key:delete_tree",
                    "membership:read_tree",
                    "role:read",
                    "role:create",
                    "role:update",
                    "user:read",
                    "user:read_tree",
                    "entity:read",
                    "entity:read_tree",
                    "lead:read",
                    "lead:read_tree",
                ],
                "is_global": False,
                "is_system_role": False,
                "root_entity_key": "org",
                "scope_entity_key": "east_coast",
                "scope": RoleScope.HIERARCHY,
                "assignable_at_types": ["region", "office"],
            },
            {
                "name": "west_coast_after_hours",
                "display_name": "West Coast After Hours Override",
                "description": "Entity-defined hierarchy role with ABAC conditions. Intended for emergency after-hours handling from approved backoffice sessions.",
                "permission_names": [
                    "lead:read",
                    "lead:update",
                    "lead:escalate_after_hours",
                ],
                "is_global": False,
                "is_system_role": False,
                "root_entity_key": "org",
                "scope_entity_key": "west_coast",
                "scope": RoleScope.HIERARCHY,
                "assignable_at_types": ["region", "office"],
            },
            {
                "name": "summit_org_admin",
                "display_name": "Summit Org Admin",
                "description": "Top-level Summit administrator for testing multi-root role workspaces.",
                "permission_names": [
                    "api_key:read_tree",
                    "api_key:create_tree",
                    "api_key:update_tree",
                    "api_key:delete_tree",
                    "membership:read_tree",
                    "role:read",
                    "role:create",
                    "role:update",
                    "role:delete",
                    "user:read",
                    "user:read_tree",
                    "user:create",
                    "entity:read",
                    "entity:read_tree",
                ],
                "is_global": False,
                "is_system_role": False,
                "root_entity_key": "summit_org",
            },
            {
                "name": "austin_office_local_admin",
                "display_name": "Austin Office Local Admin",
                "description": "Entity-only Summit role for office-local administration and entity_only testing on a second root.",
                "permission_names": [
                    "api_key:read",
                    "api_key:create",
                    "api_key:update",
                    "api_key:delete",
                    "membership:read",
                    "role:read",
                    "role:create",
                    "role:update",
                    "user:read",
                    "entity:read",
                    "lead:read",
                    "lead:update",
                ],
                "is_global": False,
                "is_system_role": False,
                "root_entity_key": "summit_org",
                "scope_entity_key": "austin_office",
                "scope": RoleScope.ENTITY_ONLY,
                "assignable_at_types": ["office"],
            },
            {
                "name": "summit_growth_default",
                "display_name": "Summit Growth Default",
                "description": "Auto-assigned baseline role for Summit growth team members.",
                "permission_names": [
                    "lead:read",
                    "lead:create",
                ],
                "is_global": False,
                "is_system_role": False,
                "root_entity_key": "summit_org",
                "scope_entity_key": "austin_growth",
                "scope": RoleScope.HIERARCHY,
                "is_auto_assigned": True,
                "assignable_at_types": ["team"],
            },
        ]

        for role_data in demo_roles_data:
            await create_role_record(
                name=role_data["name"],
                display_name=role_data["display_name"],
                description=role_data["description"],
                permission_names=role_data["permission_names"],
                is_system_role=role_data["is_system_role"],
                is_global=role_data["is_global"],
                root_entity_id=(
                    entities_map[role_data["root_entity_key"]].id
                    if role_data.get("root_entity_key")
                    else None
                ),
                scope_entity_id=(
                    entities_map[role_data["scope_entity_key"]].id
                    if role_data.get("scope_entity_key")
                    else None
                ),
                scope=role_data.get("scope", RoleScope.HIERARCHY),
                is_auto_assigned=role_data.get("is_auto_assigned", False),
                assignable_at_types=role_data.get("assignable_at_types", []),
            )

        await session.flush()
        print(
            f"   Created {len(seeded_roles_for_manifest)} roles "
            f"({len(base_roles_data)} system + {len(demo_roles_data)} demo)\n"
        )

        user_service = auth.user_service
        membership_service = auth.membership_service
        role_service = auth.role_service

        # Create test users with review-friendly personas.
        print("Creating test users...")
        users_data = [
            {
                "email": "admin@acme.com",
                "password": "Testpass1!",
                "first_name": "System",
                "last_name": "Admin",
                "persona": "Superuser",
                "notes": "Can manage global, root-scoped, and entity-defined roles everywhere.",
                "is_superuser": True,
                "root_entity_key": "org",
                "direct_roles": ["admin"],
                "entity_memberships": [
                    {"entity_key": "org", "role_names": ["admin"]},
                ],
            },
            {
                "email": "permissions-admin@acme.com",
                "password": "Testpass1!",
                "first_name": "Priya",
                "last_name": "Permissions",
                "persona": "Permission catalog admin",
                "notes": "Can create custom permissions and manage permission-level ABAC globally, without superuser access.",
                "is_superuser": False,
                "root_entity_key": "org",
                "direct_roles": ["permission_catalog_admin"],
                "entity_memberships": [],
            },
            {
                "email": "org-admin@acme.com",
                "password": "Testpass1!",
                "first_name": "Olivia",
                "last_name": "OrgAdmin",
                "persona": "Root-scoped admin",
                "notes": "Can manage ACME root roles and descendants, but not system-wide global roles.",
                "is_superuser": False,
                "root_entity_key": "org",
                "direct_roles": ["acme_org_admin"],
                "entity_memberships": [
                    {"entity_key": "org", "role_names": ["acme_org_admin"]},
                ],
            },
            {
                "email": "regional-admin@acme.com",
                "password": "Testpass1!",
                "first_name": "Riley",
                "last_name": "RegionalAdmin",
                "persona": "West Coast scoped admin",
                "notes": "Can manage West Coast entity-defined roles only. Good for hierarchy-scope testing.",
                "is_superuser": False,
                "root_entity_key": "org",
                "direct_roles": ["scoped_roles_admin"],
                "entity_memberships": [
                    {
                        "entity_key": "west_coast",
                        "role_names": [
                            "west_coast_hierarchy_admin",
                            "west_coast_after_hours",
                        ],
                    },
                ],
            },
            {
                "email": "manager@sf.acme.com",
                "password": "Testpass1!",
                "first_name": "Sarah",
                "last_name": "Manager",
                "persona": "SF office scoped admin",
                "notes": "Can manage San Francisco office-local roles only. Useful for entity_only review.",
                "is_superuser": False,
                "root_entity_key": "org",
                "direct_roles": ["scoped_roles_admin"],
                "entity_memberships": [
                    {
                        "entity_key": "sf_office",
                        "role_names": ["office_manager", "sf_office_local_admin"],
                    },
                ],
            },
            {
                "email": "east-admin@acme.com",
                "password": "Testpass1!",
                "first_name": "Elliot",
                "last_name": "EastAdmin",
                "persona": "East Coast scoped admin",
                "notes": "Sibling branch admin for East Coast scope filtering and branch-isolation browser tests.",
                "is_superuser": False,
                "root_entity_key": "org",
                "direct_roles": ["scoped_roles_admin"],
                "entity_memberships": [
                    {
                        "entity_key": "east_coast",
                        "role_names": ["east_coast_hierarchy_admin"],
                    },
                ],
            },
            {
                "email": "auditor@acme.com",
                "password": "Testpass1!",
                "first_name": "Avery",
                "last_name": "Auditor",
                "persona": "Read-only auditor",
                "notes": "Can inspect the ACME role catalog without mutation permissions.",
                "is_superuser": False,
                "root_entity_key": "org",
                "direct_roles": ["acme_auditor"],
                "entity_memberships": [
                    {"entity_key": "org", "role_names": ["acme_auditor"]},
                ],
            },
            {
                "email": "lead@sf.acme.com",
                "password": "Testpass1!",
                "first_name": "Tom",
                "last_name": "TeamLead",
                "persona": "Operational team lead",
                "notes": "Has normal team permissions plus the auto-assigned SF team default role.",
                "is_superuser": False,
                "direct_roles": ["team_lead"],
                "entity_memberships": [
                    {"entity_key": "sf_residential", "role_names": ["team_lead"]},
                ],
            },
            {
                "email": "agent@sf.acme.com",
                "password": "Testpass1!",
                "first_name": "Jane",
                "last_name": "Agent",
                "persona": "Residential agent",
                "notes": "Receives the auto-assigned SF team default role on the residential team.",
                "is_superuser": False,
                "direct_roles": ["agent"],
                "entity_memberships": [
                    {"entity_key": "sf_residential", "role_names": ["agent"]},
                ],
            },
            {
                "email": "commercial@sf.acme.com",
                "password": "Testpass1!",
                "first_name": "Chris",
                "last_name": "Commercial",
                "persona": "Commercial agent",
                "notes": "Operational user outside the residential auto-assignment scope.",
                "is_superuser": False,
                "direct_roles": ["agent"],
                "entity_memberships": [
                    {"entity_key": "sf_commercial", "role_names": ["agent"]},
                ],
            },
            {
                "email": "summit-admin@summit.com",
                "password": "Testpass1!",
                "first_name": "Morgan",
                "last_name": "SummitAdmin",
                "persona": "Second root admin",
                "notes": "Root-scoped Summit admin for multi-root testing and superuser root switching.",
                "is_superuser": False,
                "root_entity_key": "summit_org",
                "direct_roles": ["summit_org_admin"],
                "entity_memberships": [
                    {"entity_key": "summit_org", "role_names": ["summit_org_admin"]},
                ],
            },
            {
                "email": "agent@austin.summit.com",
                "password": "Testpass1!",
                "first_name": "Parker",
                "last_name": "Growth",
                "persona": "Summit growth agent",
                "notes": "Operational user in the second organization with an auto-assigned team default role.",
                "is_superuser": False,
                "root_entity_key": "summit_org",
                "direct_roles": ["agent"],
                "entity_memberships": [
                    {"entity_key": "austin_growth", "role_names": ["agent"]},
                ],
            },
            {
                "email": "invited@acme.com",
                "password": None,
                "first_name": "Indigo",
                "last_name": "Invitee",
                "persona": "Pending invite",
                "notes": "Fresh invite fixture for resend-invite flows and invited-user filtering.",
                "is_superuser": False,
                "root_entity_key": "org",
                "status": UserStatus.INVITED,
                "email_verified": False,
                "invited_by_email": "org-admin@acme.com",
                "direct_roles": [],
                "entity_memberships": [],
            },
            {
                "email": "suspended@ny.acme.com",
                "password": "Testpass1!",
                "first_name": "Nina",
                "last_name": "Suspended",
                "persona": "Suspended operator",
                "notes": "Suspended user for lifecycle screens and audit trails.",
                "is_superuser": False,
                "root_entity_key": "org",
                "status": UserStatus.SUSPENDED,
                "suspended_days": 14,
                "direct_roles": ["agent"],
                "entity_memberships": [
                    {
                        "entity_key": "nyc_office",
                        "role_names": ["office_dispatch_coordinator"],
                    },
                ],
            },
            {
                "email": "locked@la.acme.com",
                "password": "Testpass1!",
                "first_name": "Lena",
                "last_name": "Locked",
                "persona": "Locked support user",
                "notes": "Active but temporarily locked account for security-state UI coverage.",
                "is_superuser": False,
                "root_entity_key": "org",
                "locked_hours": 8,
                "failed_login_attempts": 5,
                "direct_roles": ["agent"],
                "entity_memberships": [
                    {
                        "entity_key": "la_office",
                        "role_names": ["office_dispatch_coordinator"],
                    },
                ],
            },
            {
                "email": "unverified@austin.summit.com",
                "password": "Testpass1!",
                "first_name": "Uma",
                "last_name": "Unverified",
                "persona": "Unverified Summit hire",
                "notes": "Email-unverified active user for badge and filter coverage in the second root.",
                "is_superuser": False,
                "root_entity_key": "summit_org",
                "email_verified": False,
                "direct_roles": ["agent"],
                "entity_memberships": [
                    {
                        "entity_key": "austin_growth",
                        "role_names": ["agent"],
                    },
                ],
            },
        ]

        users_map = {}
        for user_data in users_data:
            root_entity_id = (
                entities_map[user_data["root_entity_key"]].id
                if user_data.get("root_entity_key")
                else None
            )
            if user_data.get("status") == UserStatus.INVITED:
                invited_by_id = None
                invited_by_email = user_data.get("invited_by_email")
                if invited_by_email and invited_by_email in users_map:
                    invited_by_id = users_map[invited_by_email].id
                user, _plain_invite_token = await user_service.invite_user(
                    session,
                    user_data["email"],
                    first_name=user_data["first_name"],
                    last_name=user_data["last_name"],
                    invited_by_id=invited_by_id,
                    root_entity_id=root_entity_id,
                )
            else:
                user = await user_service.create_user(
                    session,
                    user_data["email"],
                    user_data["password"],
                    first_name=user_data["first_name"],
                    last_name=user_data["last_name"],
                    is_superuser=user_data["is_superuser"],
                    root_entity_id=root_entity_id,
                )

            user.status = user_data.get("status", UserStatus.ACTIVE)
            user.email_verified = user_data.get(
                "email_verified",
                user.status == UserStatus.ACTIVE,
            )
            user.last_login = seed_now - timedelta(hours=user_data.get("last_login_hours_ago", 18))
            user.last_activity = seed_now - timedelta(hours=user_data.get("last_activity_hours_ago", 2))
            user.last_password_change = seed_now - timedelta(
                days=user_data.get("last_password_change_days_ago", 45)
            )
            user.failed_login_attempts = user_data.get("failed_login_attempts", 0)
            user.locale = user_data.get("locale", "en-US")
            user.timezone = user_data.get("timezone", "America/Los_Angeles")
            if user_data.get("suspended_days"):
                user.suspended_until = seed_now + timedelta(days=user_data["suspended_days"])
            if user_data.get("locked_hours"):
                user.locked_until = seed_now + timedelta(hours=user_data["locked_hours"])
            if user.status == UserStatus.INVITED:
                user.last_login = None
                user.last_activity = None
                user.last_password_change = None
            await session.flush()
            users_map[user_data["email"]] = user

            assigned_by_email = user_data.get("assigned_by_email", "admin@acme.com")
            assigned_by = users_map.get(assigned_by_email)
            for role_name in user_data["direct_roles"]:
                await role_service.assign_role_to_user(
                    session,
                    user_id=user.id,
                    role_id=roles_map[role_name].id,
                    assigned_by_id=assigned_by.id if assigned_by else None,
                )

            joined_by_email = user_data.get("joined_by_email", "admin@acme.com")
            joined_by = users_map.get(joined_by_email)
            for membership_data in user_data["entity_memberships"]:
                await membership_service.add_member(
                    session,
                    entity_id=entities_map[membership_data["entity_key"]].id,
                    user_id=user.id,
                    role_ids=[roles_map[role_name].id for role_name in membership_data["role_names"]],
                    joined_by_id=joined_by.id if joined_by else None,
                    status=membership_data.get("status", MembershipStatus.ACTIVE),
                    reason=membership_data.get("reason"),
                )

        print(
            f"   Created {len(users_data)} test users with persona, lifecycle, and multi-root coverage\n"
        )

        print("Creating ABAC demo conditions...")
        after_hours_group = ConditionGroup(
            role_id=roles_map["west_coast_after_hours"].id,
            operator="AND",
            description="Only allow after-hours override from approved backoffice workflows.",
        )
        session.add(after_hours_group)
        await session.flush()
        session.add(
            RoleCondition(
                role_id=roles_map["west_coast_after_hours"].id,
                condition_group_id=after_hours_group.id,
                attribute="env.request_origin",
                operator=ConditionOperator.EQUALS,
                value="backoffice",
                value_type="string",
                description="Restrict to backoffice-originated requests.",
            )
        )
        session.add(
            RoleCondition(
                role_id=roles_map["west_coast_after_hours"].id,
                condition_group_id=after_hours_group.id,
                attribute="env.shift_window",
                operator=ConditionOperator.EQUALS,
                value="after_hours",
                value_type="string",
                description="Require the after-hours shift window flag.",
            )
        )
        print("   Added ABAC condition group to West Coast After Hours Override\n")

        permission_group = ConditionGroup(
            permission_id=permissions_map["lead:escalate_after_hours"].id,
            operator="AND",
            description="Only allow emergency escalation for urgent, on-call workflows.",
        )
        session.add(permission_group)
        await session.flush()
        session.add(
            PermissionCondition(
                permission_id=permissions_map["lead:escalate_after_hours"].id,
                condition_group_id=permission_group.id,
                attribute="env.on_call",
                operator=ConditionOperator.IS_TRUE,
                value=None,
                value_type="boolean",
                description="Require an on-call session context.",
            )
        )
        session.add(
            PermissionCondition(
                permission_id=permissions_map["lead:escalate_after_hours"].id,
                condition_group_id=permission_group.id,
                attribute="resource.priority",
                operator=ConditionOperator.EQUALS,
                value="urgent",
                value_type="string",
                description="Restrict escalation to urgent leads only.",
            )
        )
        print("   Added ABAC condition group to Lead Escalate After Hours\n")

        await session.commit()

        entity_display_by_id = {str(entity.id): entity.display_name for entity in entities_map.values()}

        # Print credentials and starter manifest
        print("=" * 60)
        print("Test Environment Reset Complete!")
        print("=" * 60)
        print("\nReview Personas:\n")

        for user_data in users_data:
            print(f"   {user_data['persona']}: {user_data['first_name']} {user_data['last_name']}")
            print(f"   Email:    {user_data['email']}")
            print(f"   Password: {user_data['password'] or 'Invite flow only'}")
            print(
                f"   Status:   {user_data.get('status', UserStatus.ACTIVE).value if isinstance(user_data.get('status'), UserStatus) else user_data.get('status', 'active')}"
            )
            print(
                f"   Direct Roles: {', '.join(user_data['direct_roles']) or 'None'}"
            )
            print(
                "   Entity Scope: "
                + ", ".join(
                    f"{membership['entity_key']} ({', '.join(membership['role_names'])})"
                    for membership in user_data["entity_memberships"]
                )
            )
            if user_data.get("root_entity_key"):
                print(
                    "   Root Scope: "
                    + entities_map[user_data["root_entity_key"]].display_name
                )
            print(f"   Notes:    {user_data['notes']}")
            print()

        print("Seeded Roles Workspace Examples:\n")
        for role in seeded_roles_for_manifest:
            if role.is_global and role.root_entity_id is None and role.scope_entity_id is None:
                role_type = "Global"
                defined_at = "System"
                scope_label = "system-wide"
            elif role.scope_entity_id is None:
                role_type = "Organization-scoped"
                defined_at = entity_display_by_id.get(str(role.root_entity_id), "Unknown root")
                scope_label = "root"
            else:
                role_type = "Entity-defined"
                defined_at = entity_display_by_id.get(str(role.scope_entity_id), "Unknown entity")
                scope_label = role.scope.value

            flags = []
            if role.is_system_role:
                flags.append("system")
            if role.is_auto_assigned:
                flags.append("auto-assigned")
            if role.name == "west_coast_after_hours":
                flags.append("abac")

            assignable = ", ".join(role.assignable_at_types) if role.assignable_at_types else "any entity type"
            flag_summary = f" [{', '.join(flags)}]" if flags else ""
            print(
                f"   - {role.display_name}{flag_summary}: {role_type}, defined at {defined_at}, "
                f"scope={scope_label}, assignable_at={assignable}"
            )
        print()

        print("Seed Summary:")
        print(f"   Root entities: {sum(1 for entity in entities_map.values() if entity.parent_id is None)}")
        print(f"   Total entities: {len(entities_map)}")
        print(f"   Total roles: {len(seeded_roles_for_manifest)}")
        print(f"   Total personas: {len(users_data)}")
        print()

        print("URLs:")
        print(f"   Backend:  http://localhost:8004")
        print(f"   API Docs: http://localhost:8004/docs")
        print(f"   Admin UI: http://localhost:3000")
        print("\n" + "=" * 60)
    finally:
        await auth.shutdown()


if __name__ == "__main__":
    asyncio.run(reset_database())
