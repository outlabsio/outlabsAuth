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
from outlabs_auth.bootstrap import get_system_permission_catalog
from outlabs_auth.cli import run_migrations
from outlabs_auth.models.sql.enums import (
    APIKeyKind,
    APIKeyStatus,
    ConditionOperator,
    DefinitionStatus,
    EntityClass,
    IntegrationPrincipalScopeKind,
    IntegrationPrincipalStatus,
    RoleScope,
)
from outlabs_auth.models.sql.permission import PermissionCondition
from outlabs_auth.models.sql.role import ConditionGroup, RoleCondition, RolePermission
from outlabs_auth.schemas.abac import serialize_condition_value

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
    admin_engine = create_async_engine(admin_url, echo=False, isolation_level="AUTOCOMMIT")
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
        # The reset script never issues tokens; the secret only needs to pass
        # the library's >=32-char HS256 validation (SEC hardening).
        secret_key=os.environ["SECRET_KEY"],
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
            table_names_result = await session.execute(text("""
                    SELECT quote_ident(tablename)
                    FROM pg_tables
                    WHERE schemaname = current_schema()
                      AND tablename != 'outlabs_auth_alembic_version'
                    ORDER BY tablename
                    """))
            table_names = [str(row[0]) for row in table_names_result]
            if table_names:
                await session.execute(text(f"TRUNCATE TABLE {', '.join(table_names)} RESTART IDENTITY CASCADE"))
            await session.commit()
            print("Test data cleared\n")

        # Create permissions: the library-owned catalog first (exactly what
        # seed_system_records() installs in production), then the example's
        # own vocabulary. Keeping the library catalog verbatim means every
        # library route permission (membership:delete, entity:create_tree,
        # permission:check, ...) can be granted without hand-creating it.
        print("Creating permissions...")
        permissions_data = [
            {
                "name": seed.name,
                "display_name": seed.display_name,
                "description": seed.description,
            }
            for seed in get_system_permission_catalog()
        ]
        example_permissions = [
            # Tree variants the example grants through memberships.
            ("user:read_tree", "User Read Tree", "View users across descendant entities."),
            ("membership:create_tree", "Membership Create Tree", "Add members across descendant entities."),
            # Lead (example resource) permissions.
            ("lead:read", "Lead Read", None),
            ("lead:read_tree", "Lead Read Tree", None),
            ("lead:create", "Lead Create", None),
            ("lead:update", "Lead Update", None),
            ("lead:delete", "Lead Delete", None),
            # API keys and integration principals (admin surface).
            ("api_key:read", "API Key Read", None),
            ("api_key:create", "API Key Create", None),
            ("api_key:update", "API Key Update", None),
            ("api_key:delete", "API Key Delete", None),
            ("api_key:read_tree", "API Key Read Tree", None),
            ("api_key:create_tree", "API Key Create Tree", None),
            ("api_key:update_tree", "API Key Update Tree", None),
            ("api_key:delete_tree", "API Key Delete Tree", None),
        ]
        for name, display_name, description in example_permissions:
            permissions_data.append({"name": name, "display_name": display_name, "description": description})
        permissions_data.append(
            {
                "name": "lead:escalate_after_hours",
                "display_name": "Lead Escalate After Hours",
                "description": "Custom permission for emergency lead escalation workflows after standard operating hours.",
                "is_system": False,
            }
        )
        permissions_data.append(
            {
                "name": "lead:export",
                "display_name": "Lead Export",
                "description": "Lifecycle fixture: an INACTIVE permission still attached to a role.",
                "is_system": False,
                "is_active": False,
            }
        )

        permissions_map = {}
        for perm_data in permissions_data:
            resource, action = perm_data["name"].split(":", 1)
            perm = Permission(
                name=perm_data["name"],
                display_name=perm_data["display_name"],
                resource=resource,
                action=action,
                description=perm_data.get("description") or f"Permission to {action} {resource}",
                is_system=perm_data.get("is_system", True),
                is_active=perm_data.get("is_active", True),
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
        # Fixtures that must not lapse between a reseed and an E2E run use a
        # far-future horizon instead of "seed time + a few hours/days".
        far_future = seed_now + timedelta(days=3650)

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
                stmt = select(EntityClosure).where(EntityClosure.descendant_id == parent_entity.id)
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
            valid_until=far_future,
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

        # Lifecycle fixtures in the hierarchy.
        la_downtown = Entity(
            name="la_downtown",
            display_name="LA Downtown Team",
            slug="la-downtown",
            description="Active team under the INACTIVE Los Angeles office (inactive-parent fixture).",
            entity_class=EntityClass.ACCESS_GROUP,
            entity_type="team",
            parent_id=la_office.id,
            depth=3,
            path="/acme-realty/west-coast/la-office/la-downtown",
            status="active",
            max_members=10,
        )
        session.add(la_downtown)
        await session.flush()
        await create_closure_for_entity(la_downtown, la_office)

        sf_capacity = Entity(
            name="sf_capacity_team",
            display_name="SF Capacity Team",
            slug="sf-capacity-team",
            description="Team seeded exactly at max_members=2 (capacity fixture).",
            entity_class=EntityClass.ACCESS_GROUP,
            entity_type="team",
            parent_id=sf_office.id,
            depth=3,
            path="/acme-realty/west-coast/sf-office/sf-capacity-team",
            status="active",
            max_members=2,
        )
        session.add(sf_capacity)
        await session.flush()
        await create_closure_for_entity(sf_capacity, sf_office)

        legacy_office = Entity(
            name="boston_office",
            display_name="Boston Office (archived)",
            slug="boston-office",
            description="Archived office (archived-entity fixture).",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="office",
            parent_id=east_coast.id,
            depth=2,
            path="/acme-realty/east-coast/boston-office",
            status="active",
            allowed_child_types=["team"],
            allowed_child_classes=["access_group"],
        )
        session.add(legacy_office)
        await session.flush()
        await create_closure_for_entity(legacy_office, east_coast)

        await session.flush()
        print("   Created entity hierarchy:")
        print("   - ACME Realty (organization)")
        print("     - West Coast Region")
        print("       - San Francisco Office")
        print("         - SF Residential Team")
        print("         - SF Commercial Team")
        print("         - SF Capacity Team (at max_members)")
        print("       - Los Angeles Office (inactive)")
        print("         - LA Downtown Team")
        print("     - East Coast Region")
        print("       - New York City Office")
        print("       - Boston Office (archived below)")
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
            "la_downtown": la_downtown,
            "sf_capacity": sf_capacity,
            "legacy_office": legacy_office,
        }

        demo_roles_data = [
            {
                "name": "global_roles_admin",
                "display_name": "Global Roles Admin (system-wide)",
                "description": (
                    "System-wide role: holding it DIRECTLY makes the holder a global actor across every "
                    "tenant (DD-056). Seeded unassigned so the console can show what a system-wide role "
                    "looks like; tenant-scoped admins cannot grant it."
                ),
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
                "display_name": "Permission Catalog Admin (deliberately global)",
                "description": (
                    "The one deliberately global delegated persona: a system-wide role, so its holder spans "
                    "every tenant (DD-056). Limited to the global permission catalog and ABAC, plus role "
                    "reads; it carries no user, session or audit access."
                ),
                "permission_names": [
                    "permission:read",
                    "permission:create",
                    "permission:update",
                    "permission:delete",
                    "permission:check",
                    "role:read",
                ],
                "is_global": True,
                "is_system_role": False,
            },
            {
                "name": "acme_org_admin",
                "display_name": "ACME Org Admin",
                "description": (
                    "Top-level ACME admin role. Users rooted at ACME get the whole ACME tree as their "
                    "user/role scope, so this is the tenant administrator."
                ),
                "permission_names": [
                    "api_key:read_tree",
                    "api_key:create_tree",
                    "api_key:update_tree",
                    "api_key:delete_tree",
                    "membership:read",
                    "membership:read_tree",
                    "membership:create",
                    "membership:create_tree",
                    "membership:update_tree",
                    "membership:delete_tree",
                    "permission:read",
                    "permission:check",
                    "role:read",
                    "role:create",
                    "role:update",
                    "role:delete",
                    "user:read",
                    "user:read_tree",
                    "user:create",
                    "user:update",
                    "entity:read",
                    "entity:read_tree",
                    "entity:create_tree",
                    "entity:update",
                    "lead:export",
                ],
                "is_global": False,
                "is_system_role": False,
                "root_entity_key": "org",
            },
            {
                "name": "acme_regional_admin",
                "display_name": "ACME Regional Admin Baseline",
                "description": (
                    "Org-scoped read baseline for region admins. Org-scoped, not system-wide, so holding "
                    "it directly never makes the holder a global actor (DD-056)."
                ),
                "permission_names": [
                    "user:read",
                    "user:read_tree",
                    "role:read",
                    "entity:read",
                    "entity:read_tree",
                    "membership:read",
                    "membership:read_tree",
                    "permission:read",
                    "api_key:read",
                ],
                "is_global": False,
                "is_system_role": False,
                "root_entity_key": "org",
            },
            {
                "name": "acme_office_admin",
                "display_name": "ACME Office Admin Baseline",
                "description": (
                    "Org-scoped baseline for office admins: user onboarding and read access, without the "
                    "global scope a system-wide role would grant."
                ),
                "permission_names": [
                    "user:read",
                    "user:read_tree",
                    "user:create",
                    "role:read",
                    "entity:read",
                    "entity:read_tree",
                    "membership:read",
                    "membership:read_tree",
                    "lead:read",
                    "lead:read_tree",
                ],
                "is_global": False,
                "is_system_role": False,
                "root_entity_key": "org",
            },
            {
                "name": "acme_agent_baseline",
                "display_name": "ACME Agent Baseline",
                "description": (
                    "Direct, org-scoped baseline for ACME operational users. Never a system-wide role: "
                    "a direct system-wide grant would make an agent a global actor (DD-056)."
                ),
                "permission_names": ["lead:read", "lead:create", "lead:update"],
                "is_global": False,
                "is_system_role": False,
                "root_entity_key": "org",
            },
            {
                "name": "acme_team_lead_baseline",
                "display_name": "ACME Team Lead Baseline",
                "description": "Direct, org-scoped baseline for ACME team leads (no cross-tenant reach).",
                "permission_names": [
                    "lead:read",
                    "lead:read_tree",
                    "lead:create",
                    "lead:update",
                    "lead:delete",
                    "user:read",
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
                    "membership:read",
                    "membership:read_tree",
                    "permission:read",
                    "permission:check",
                    "api_key:read",
                    "api_key:read_tree",
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
                    "membership:read",
                    "membership:read_tree",
                    "membership:create",
                    "membership:create_tree",
                    "membership:update_tree",
                    "membership:delete_tree",
                    "permission:read",
                    "permission:check",
                    "role:read",
                    "role:create",
                    "role:update",
                    "role:delete",
                    "user:read",
                    "user:read_tree",
                    "user:create",
                    "user:update",
                    "entity:read",
                    "entity:read_tree",
                    "entity:create_tree",
                    "entity:update",
                ],
                "is_global": False,
                "is_system_role": False,
                "root_entity_key": "summit_org",
            },
            {
                "name": "summit_agent_baseline",
                "display_name": "Summit Agent Baseline",
                "description": "Direct, org-scoped baseline for Summit operational users.",
                "permission_names": ["lead:read", "lead:create", "lead:update"],
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
            {
                "name": "abac_showcase",
                "display_name": "ABAC Showcase",
                "description": (
                    "Lifecycle fixture with every ABAC condition shape: an OR group (list IN or "
                    "equality), a NOT_IN group, and ungrouped numeric and BEFORE conditions."
                ),
                "permission_names": ["lead:read", "lead:update"],
                "is_global": False,
                "is_system_role": False,
                "root_entity_key": "org",
            },
            {
                "name": "legacy_reporting",
                "display_name": "Legacy Reporting (archived)",
                "description": "Lifecycle fixture: an ARCHIVED role that is still attached to a membership.",
                "permission_names": ["lead:read"],
                "is_global": False,
                "is_system_role": False,
                "root_entity_key": "org",
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
                    entities_map[role_data["root_entity_key"]].id if role_data.get("root_entity_key") else None
                ),
                scope_entity_id=(
                    entities_map[role_data["scope_entity_key"]].id if role_data.get("scope_entity_key") else None
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
                "persona": "Global delegated admin (deliberately global)",
                "notes": (
                    "The one deliberately GLOBAL delegated persona: a direct system-wide role makes this "
                    "account span every tenant (DD-056). Limited to the permission catalog and ABAC."
                ),
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
                "notes": (
                    "Tenant-rooted (ACME) admin whose write authority is entity-defined at West Coast. "
                    "User/role/entity listing scope is the ACME tenant (DD-056 scope is per tenant root); "
                    "the West Coast boundary applies on tree-permission surfaces (memberships, entity "
                    "writes, leads). Holds no system-wide role."
                ),
                "is_superuser": False,
                "root_entity_key": "org",
                # Org-scoped (never system-wide) direct role: flat reads without
                # global scope; entity-defined authority through the membership.
                "direct_roles": ["acme_regional_admin"],
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
                "notes": (
                    "Office admin: an org-scoped baseline role plus the SF office membership. Tenant "
                    "scope is ACME; office-local authority applies on tree-permission surfaces. Useful "
                    "for entity_only review."
                ),
                "is_superuser": False,
                "root_entity_key": "org",
                "direct_roles": ["acme_office_admin"],
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
                "notes": (
                    "Sibling-branch admin with East Coast entity-defined authority for branch-isolation "
                    "tests on tree-permission surfaces (tenant scope is ACME)."
                ),
                "is_superuser": False,
                "root_entity_key": "org",
                "direct_roles": ["acme_regional_admin"],
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
                "notes": "Org-scoped team-lead baseline plus the SF Residential membership and its auto-assigned default role.",
                "is_superuser": False,
                "direct_roles": ["acme_team_lead_baseline"],
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
                "direct_roles": ["acme_agent_baseline"],
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
                "direct_roles": ["acme_agent_baseline"],
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
                "direct_roles": ["summit_agent_baseline"],
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
                "notes": "Indefinitely suspended user (no auto-lift date) for lifecycle screens and audit trails.",
                "is_superuser": False,
                "root_entity_key": "org",
                "status": UserStatus.SUSPENDED,
                "direct_roles": ["acme_agent_baseline"],
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
                "notes": "Active but locked account for security-state UI coverage (lock far in the future so it never lapses).",
                "is_superuser": False,
                "root_entity_key": "org",
                "locked_days": 3650,
                "failed_login_attempts": 5,
                "direct_roles": ["acme_agent_baseline"],
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
                "direct_roles": ["summit_agent_baseline"],
                "entity_memberships": [
                    {
                        "entity_key": "austin_growth",
                        "role_names": ["agent"],
                    },
                ],
            },
            {
                "email": "banned@acme.com",
                "password": "Testpass1!",
                "first_name": "Bo",
                "last_name": "Banned",
                "persona": "Banned user",
                "notes": "Permanently banned account (manual lift required).",
                "is_superuser": False,
                "root_entity_key": "org",
                "status": UserStatus.BANNED,
                "direct_roles": [],
                "entity_memberships": [],
            },
            {
                "email": "lifecycle@acme.com",
                "password": "Testpass1!",
                "first_name": "Lia",
                "last_name": "Lifecycle",
                "persona": "Membership lifecycle fixture",
                "notes": (
                    "Holds memberships and direct roles in every non-active state: suspended, revoked, "
                    "pending (future start) and expired, plus an archived role still attached."
                ),
                "is_superuser": False,
                "root_entity_key": "org",
                "direct_roles": [],
                "entity_memberships": [],
            },
            {
                "email": "orphan@acme.com",
                "password": "Testpass1!",
                "first_name": "Otto",
                "last_name": "Orphan",
                "persona": "Orphaned user",
                "notes": "Rooted at ACME whose only membership was revoked: appears in /users/orphaned for ACME admins.",
                "is_superuser": False,
                "root_entity_key": "org",
                "direct_roles": [],
                "entity_memberships": [],
            },
            {
                "email": "abac@acme.com",
                "password": "Testpass1!",
                "first_name": "Ada",
                "last_name": "Attributes",
                "persona": "ABAC fixture",
                "notes": "Holds the ABAC Showcase role at West Coast (OR/IN/NOT_IN/numeric/BEFORE conditions).",
                "is_superuser": False,
                "direct_roles": [],
                "entity_memberships": [
                    {"entity_key": "west_coast", "role_names": ["abac_showcase"]},
                ],
            },
            {
                "email": "capacity-1@acme.com",
                "password": "Testpass1!",
                "first_name": "Cam",
                "last_name": "CapacityOne",
                "persona": "Capacity fixture",
                "notes": "Fills the SF Capacity Team (max_members=2).",
                "is_superuser": False,
                "root_entity_key": "org",
                "direct_roles": [],
                "entity_memberships": [],
            },
            {
                "email": "capacity-2@acme.com",
                "password": "Testpass1!",
                "first_name": "Cy",
                "last_name": "CapacityTwo",
                "persona": "Capacity fixture",
                "notes": "Fills the SF Capacity Team (max_members=2).",
                "is_superuser": False,
                "root_entity_key": "org",
                "direct_roles": [],
                "entity_memberships": [],
            },
        ]

        users_map = {}
        for user_data in users_data:
            root_entity_id = entities_map[user_data["root_entity_key"]].id if user_data.get("root_entity_key") else None
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
            user.last_password_change = seed_now - timedelta(days=user_data.get("last_password_change_days_ago", 45))
            user.failed_login_attempts = user_data.get("failed_login_attempts", 0)
            user.locale = user_data.get("locale", "en-US")
            user.timezone = user_data.get("timezone", "America/Los_Angeles")
            if user_data.get("suspended_days"):
                user.suspended_until = seed_now + timedelta(days=user_data["suspended_days"])
            if user_data.get("locked_days"):
                user.locked_until = seed_now + timedelta(days=user_data["locked_days"])
            if user.status == UserStatus.INVITED:
                user.last_login = None
                user.last_activity = None
                user.last_password_change = None
                # Keep the invite fixture valid however long ago the seed ran.
                user.invite_token_expires = far_future
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

        print(f"   Created {len(users_data)} test users with persona, lifecycle, and multi-root coverage\n")

        # ------------------------------------------------------------------
        # Lifecycle fixtures (F-160): every state a console has to render,
        # created through the library services so history and audit rows are
        # real. Time-based states use far-future / far-past windows so they
        # never drift between a reseed and a test run.
        # ------------------------------------------------------------------
        print("Creating lifecycle fixtures...")
        admin_user = users_map["admin@acme.com"]
        lifecycle_user = users_map["lifecycle@acme.com"]
        far_past = seed_now - timedelta(days=30)
        api_key_service = auth.api_key_service
        principal_service = auth.integration_principal_service

        # Memberships: suspended, pending (future start), expired, revoked.
        await membership_service.add_member(
            session,
            entity_id=entities_map["nyc_office"].id,
            user_id=lifecycle_user.id,
            role_ids=[roles_map["office_dispatch_coordinator"].id],
            joined_by_id=admin_user.id,
            status=MembershipStatus.SUSPENDED,
            reason="On leave (lifecycle fixture)",
        )
        await membership_service.add_member(
            session,
            entity_id=entities_map["east_coast"].id,
            user_id=lifecycle_user.id,
            role_ids=[roles_map["acme_regional_admin"].id],
            joined_by_id=admin_user.id,
            valid_from=far_future,
        )
        expired_membership = await membership_service.add_member(
            session,
            entity_id=entities_map["sf_office"].id,
            user_id=lifecycle_user.id,
            role_ids=[roles_map["office_dispatch_coordinator"].id],
            joined_by_id=admin_user.id,
        )
        expired_membership.valid_from = far_past - timedelta(days=60)
        expired_membership.valid_until = far_past
        await membership_service.add_member(
            session,
            entity_id=entities_map["sf_commercial"].id,
            user_id=lifecycle_user.id,
            role_ids=[roles_map["agent"].id],
            joined_by_id=admin_user.id,
        )
        await membership_service.remove_member(
            session,
            entity_id=entities_map["sf_commercial"].id,
            user_id=lifecycle_user.id,
            revoked_by_id=admin_user.id,
            reason="Moved teams (lifecycle fixture)",
        )
        # An ARCHIVED role still attached to an active membership.
        await membership_service.add_member(
            session,
            entity_id=entities_map["org"].id,
            user_id=lifecycle_user.id,
            role_ids=[roles_map["legacy_reporting"].id],
            joined_by_id=admin_user.id,
        )

        # Direct roles: suspended, revoked, pending, expired.
        direct_states = [
            ("acme_team_lead_baseline", "suspended"),
            ("acme_office_admin", "revoked"),
            ("acme_regional_admin", "pending"),
            ("acme_agent_baseline", "expired"),
        ]
        for role_name, state in direct_states:
            membership = await role_service.assign_role_to_user(
                session,
                user_id=lifecycle_user.id,
                role_id=roles_map[role_name].id,
                assigned_by_id=admin_user.id,
                valid_from=far_future if state == "pending" else None,
            )
            if state == "suspended":
                membership.status = MembershipStatus.SUSPENDED
            elif state == "revoked":
                await role_service.revoke_role_from_user(
                    session,
                    user_id=lifecycle_user.id,
                    role_id=roles_map[role_name].id,
                    revoked_by_id=admin_user.id,
                )
            elif state == "expired":
                membership.valid_from = far_past - timedelta(days=60)
                membership.valid_until = far_past
        await session.flush()

        # A real orphan: rooted at ACME, only membership revoked.
        orphan_user = users_map["orphan@acme.com"]
        await membership_service.add_member(
            session,
            entity_id=entities_map["sf_commercial"].id,
            user_id=orphan_user.id,
            role_ids=[roles_map["agent"].id],
            joined_by_id=admin_user.id,
        )
        await membership_service.remove_member(
            session,
            entity_id=entities_map["sf_commercial"].id,
            user_id=orphan_user.id,
            revoked_by_id=admin_user.id,
            reason="Left the company (orphan fixture)",
        )

        # Entity exactly at capacity.
        for email in ("capacity-1@acme.com", "capacity-2@acme.com"):
            await membership_service.add_member(
                session,
                entity_id=entities_map["sf_capacity"].id,
                user_id=users_map[email].id,
                role_ids=[roles_map["agent"].id],
                joined_by_id=admin_user.id,
            )

        # Archive the legacy office and the legacy role (the role stays attached).
        await auth.entity_service.delete_entity(
            session,
            entities_map["legacy_office"].id,
            deleted_by_id=admin_user.id,
        )
        roles_map["legacy_reporting"].status = DefinitionStatus.ARCHIVED
        await session.flush()

        # Personal API keys in every status, plus a rotated pair.
        sf_agent = users_map["agent@sf.acme.com"]
        key_ids: dict[str, object] = {}
        for label in ("active", "suspended", "revoked", "expired", "rotated"):
            _secret, key = await api_key_service.create_api_key(
                session,
                owner_id=sf_agent.id,
                name=f"SF agent {label} key",
                scopes=["lead:read"],
                description=f"Lifecycle fixture: {label} personal key",
                actor_user_id=sf_agent.id,
            )
            key_ids[label] = key.id
        await api_key_service.update_api_key(
            session,
            key_ids["suspended"],
            actor_user_id=admin_user.id,
            status=APIKeyStatus.SUSPENDED,
        )
        await api_key_service.revoke_api_key(
            session,
            key_ids["revoked"],
            actor_user_id=admin_user.id,
            reason="Lifecycle fixture",
        )
        expired_key = await api_key_service.get_api_key(session, key_ids["expired"])
        expired_key.expires_at = far_past
        expired_key.status = APIKeyStatus.EXPIRED
        await api_key_service.rotate_api_key(session, key_ids["rotated"], actor_user_id=sf_agent.id)
        await session.flush()

        # Service accounts (integration principals) with machine keys.
        platform_principal = await principal_service.create_principal(
            session,
            name="Nightly reporting job",
            description="Platform-global service account (lifecycle fixture).",
            scope_kind=IntegrationPrincipalScopeKind.PLATFORM_GLOBAL,
            anchor_entity_id=None,
            inherit_from_tree=False,
            allowed_scopes=["lead:read", "entity:read"],
            created_by_user_id=admin_user.id,
        )
        await api_key_service.create_api_key(
            session,
            integration_principal_id=platform_principal.id,
            name="Reporting job key",
            scopes=["lead:read"],
            key_kind=APIKeyKind.SYSTEM_INTEGRATION,
            actor_user_id=admin_user.id,
        )
        sf_principal = await principal_service.create_principal(
            session,
            name="SF office CRM sync",
            description="Entity-anchored service account at the SF office (lifecycle fixture).",
            scope_kind=IntegrationPrincipalScopeKind.ENTITY,
            anchor_entity_id=entities_map["sf_office"].id,
            inherit_from_tree=True,
            allowed_scopes=["lead:read", "lead:update"],
            created_by_user_id=admin_user.id,
        )
        await api_key_service.create_api_key(
            session,
            integration_principal_id=sf_principal.id,
            name="SF CRM sync key",
            scopes=["lead:read", "lead:update"],
            entity_id=entities_map["sf_office"].id,
            inherit_from_tree=True,
            key_kind=APIKeyKind.SYSTEM_INTEGRATION,
            actor_user_id=admin_user.id,
        )
        inactive_principal = await principal_service.create_principal(
            session,
            name="Paused webhook relay",
            description="INACTIVE service account (lifecycle fixture).",
            scope_kind=IntegrationPrincipalScopeKind.ENTITY,
            anchor_entity_id=entities_map["nyc_office"].id,
            inherit_from_tree=False,
            allowed_scopes=["lead:read"],
            created_by_user_id=admin_user.id,
        )
        await principal_service.update_principal(
            session,
            inactive_principal.id,
            actor_user_id=admin_user.id,
            status=IntegrationPrincipalStatus.INACTIVE,
        )
        archived_principal = await principal_service.create_principal(
            session,
            name="Retired import tool",
            description="ARCHIVED service account (lifecycle fixture).",
            scope_kind=IntegrationPrincipalScopeKind.PLATFORM_GLOBAL,
            anchor_entity_id=None,
            inherit_from_tree=False,
            allowed_scopes=["lead:read"],
            created_by_user_id=admin_user.id,
        )
        await principal_service.archive_principal(
            session,
            archived_principal.id,
            actor_user_id=admin_user.id,
            reason="Lifecycle fixture",
        )

        # Several sessions per persona so session managers have rows to show.
        for email in ("org-admin@acme.com", "org-admin@acme.com", "agent@sf.acme.com"):
            await auth.auth_service.create_tokens_for_user(
                session,
                users_map[email],
                device_name="seeded-session",
                ip_address="203.0.113.10",
                user_agent="reset_test_env",
                auth_method="seed",
            )
        await session.flush()
        print("   Added membership/role/key/service-account/session lifecycle fixtures\n")

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

        showcase_role_id = roles_map["abac_showcase"].id
        region_or_urgent = ConditionGroup(
            role_id=showcase_role_id,
            operator="OR",
            description="Western/eastern regions OR anything urgent.",
        )
        status_group = ConditionGroup(
            role_id=showcase_role_id,
            operator="AND",
            description="Never on archived or deleted records.",
        )
        session.add_all([region_or_urgent, status_group])
        await session.flush()
        showcase_conditions = [
            (region_or_urgent.id, "resource.region", ConditionOperator.IN, ["west", "east"], "list"),
            (region_or_urgent.id, "resource.priority", ConditionOperator.EQUALS, "urgent", "string"),
            (status_group.id, "resource.status", ConditionOperator.NOT_IN, ["archived", "deleted"], "list"),
            (None, "resource.amount", ConditionOperator.LESS_THAN, 100000, "float"),
            (None, "time.timestamp", ConditionOperator.BEFORE, "2099-01-01T00:00:00+00:00", "string"),
        ]
        for group_id, attribute, operator, value, value_type in showcase_conditions:
            session.add(
                RoleCondition(
                    role_id=showcase_role_id,
                    condition_group_id=group_id,
                    attribute=attribute,
                    operator=operator,
                    value=serialize_condition_value(value, value_type),
                    value_type=value_type,
                    description="ABAC showcase fixture",
                )
            )
        print("   Added OR / IN / NOT_IN / numeric / BEFORE conditions to ABAC Showcase\n")

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
            print(f"   Direct Roles: {', '.join(user_data['direct_roles']) or 'None'}")
            print(
                "   Entity Scope: "
                + ", ".join(
                    f"{membership['entity_key']} ({', '.join(membership['role_names'])})"
                    for membership in user_data["entity_memberships"]
                )
            )
            if user_data.get("root_entity_key"):
                print("   Root Scope: " + entities_map[user_data["root_entity_key"]].display_name)
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
