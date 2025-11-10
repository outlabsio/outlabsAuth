#!/usr/bin/env python3
"""
Reset Test Environment Script for EnterpriseRBAC
Quickly resets the EnterpriseRBAC example database to a known good state for testing.

Creates:
- 4-level entity hierarchy (Organization → Region → Office → Team)
- 30 permissions (including tree permissions)
- 6 roles (Platform Admin, Regional Manager, Office Manager, Team Lead, Agent, Viewer)
- 6 test users with entity memberships
- Sample leads assigned to different entities

Usage:
    python reset_test_env.py

Environment Variables:
    MONGODB_URL: MongoDB connection string (default: mongodb://localhost:27018)
    DATABASE_NAME: Database name (default: realestate_enterprise_rbac)
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path so we can import outlabs_auth
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from datetime import UTC, datetime

from beanie import init_beanie

# Import domain models
from models import Lead, LeadNote
from motor.motor_asyncio import AsyncIOMotorClient

from outlabs_auth.models.closure import EntityClosureModel

# Import models
from outlabs_auth.models.entity import EntityModel
from outlabs_auth.models.membership import EntityMembershipModel
from outlabs_auth.models.permission import PermissionModel
from outlabs_auth.models.role import RoleModel
from outlabs_auth.models.user import UserModel
from outlabs_auth.utils.password import hash_password

# Configuration
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27018")
DATABASE_NAME = os.getenv("DATABASE_NAME", "realestate_enterprise_rbac")


async def reset_database():
    """Reset database to clean test state with entity hierarchy."""
    print("🔄 Connecting to MongoDB...")
    client = AsyncIOMotorClient(MONGODB_URL)
    db = client[DATABASE_NAME]

    # Initialize Beanie with all models
    await init_beanie(
        database=db,
        document_models=[
            UserModel,
            RoleModel,
            PermissionModel,
            EntityModel,
            EntityClosureModel,
            EntityMembershipModel,
            Lead,
            LeadNote,
        ],
    )

    # Drop existing test data
    print("🗑️  Dropping existing test data...")
    await UserModel.delete_all()
    await RoleModel.delete_all()
    await PermissionModel.delete_all()
    await EntityModel.delete_all()
    await EntityClosureModel.delete_all()
    await EntityMembershipModel.delete_all()
    await Lead.delete_all()
    await LeadNote.delete_all()
    print("✅ Test data cleared\n")

    # Create permissions
    print("📝 Creating permissions (30 total)...")
    permissions_data = [
        # User permissions
        {
            "name": "user:read",
            "display_name": "User Read",
            "resource": "user",
            "action": "read",
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
        {
            "name": "user:manage_tree",
            "display_name": "User Manage Tree",
            "resource": "user",
            "action": "manage_tree",
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
        # Entity permissions
        {
            "name": "entity:read",
            "display_name": "Entity Read",
            "resource": "entity",
            "action": "read",
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
        {
            "name": "entity:read_tree",
            "display_name": "Entity Read Tree",
            "resource": "entity",
            "action": "read_tree",
        },
        {
            "name": "entity:manage_tree",
            "display_name": "Entity Manage Tree",
            "resource": "entity",
            "action": "manage_tree",
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
        # Lead permissions (real estate domain)
        {
            "name": "lead:read",
            "display_name": "Lead Read",
            "resource": "lead",
            "action": "read",
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
            "name": "lead:assign",
            "display_name": "Lead Assign",
            "resource": "lead",
            "action": "assign",
        },
        {
            "name": "lead:update_own",
            "display_name": "Lead Update Own",
            "resource": "lead",
            "action": "update_own",
        },
        {
            "name": "lead:read_tree",
            "display_name": "Lead Read Tree",
            "resource": "lead",
            "action": "read_tree",
        },
        {
            "name": "lead:manage_tree",
            "display_name": "Lead Manage Tree",
            "resource": "lead",
            "action": "manage_tree",
        },
    ]

    permissions = []
    for perm_data in permissions_data:
        perm = PermissionModel(
            name=perm_data["name"],
            display_name=perm_data["display_name"],
            resource=perm_data["resource"],
            action=perm_data["action"],
            description=f"Permission to {perm_data['action']} {perm_data['resource']}",
            is_system=True,
            is_active=True,
        )
        await perm.insert()
        permissions.append(perm)

    print(f"   Created {len(permissions)} permissions\n")

    # Create entity hierarchy
    print("🏢 Creating entity hierarchy...")

    # Root: Organization
    diverse_platform = EntityModel(
        name="diverse_platform",
        display_name="Diverse Platform",
        slug="diverse-platform",
        entity_class="structural",
        entity_type="organization",
        description="Main real estate platform organization",
        status="active",
    )
    await diverse_platform.insert()
    print(f"   ✓ Created {diverse_platform.name} (Organization)")

    # Create closure for root (self-reference)
    await EntityClosureModel(
        ancestor_id=str(diverse_platform.id),
        descendant_id=str(diverse_platform.id),
        depth=0,
    ).insert()

    # Level 2: Regions
    west_coast = EntityModel(
        name="west_coast",
        display_name="West Coast",
        slug="west-coast",
        entity_class="structural",
        entity_type="region",
        parent_entity=diverse_platform,
        description="West Coast regional operations",
        status="active",
    )
    await west_coast.insert()
    print(f"   ✓ Created {west_coast.name} (Region)")

    # Update closure table for West Coast
    await EntityClosureModel(
        ancestor_id=str(diverse_platform.id), descendant_id=str(west_coast.id), depth=1
    ).insert()
    await EntityClosureModel(
        ancestor_id=str(west_coast.id), descendant_id=str(west_coast.id), depth=0
    ).insert()

    east_coast = EntityModel(
        name="east_coast",
        display_name="East Coast",
        slug="east-coast",
        entity_class="structural",
        entity_type="region",
        parent_entity=diverse_platform,
        description="East Coast regional operations",
        status="active",
    )
    await east_coast.insert()
    print(f"   ✓ Created {east_coast.name} (Region)")

    # Update closure table for East Coast
    await EntityClosureModel(
        ancestor_id=str(diverse_platform.id), descendant_id=str(east_coast.id), depth=1
    ).insert()
    await EntityClosureModel(
        ancestor_id=str(east_coast.id), descendant_id=str(east_coast.id), depth=0
    ).insert()

    # Level 3: Offices (West Coast)
    la_office = EntityModel(
        name="los_angeles",
        display_name="Los Angeles",
        slug="los-angeles",
        entity_class="structural",
        entity_type="office",
        parent_entity=west_coast,
        description="Los Angeles office",
        status="active",
    )
    await la_office.insert()
    print(f"   ✓ Created {la_office.name} (Office)")

    # Update closure table for LA Office
    await EntityClosureModel(
        ancestor_id=str(diverse_platform.id), descendant_id=str(la_office.id), depth=2
    ).insert()
    await EntityClosureModel(
        ancestor_id=str(west_coast.id), descendant_id=str(la_office.id), depth=1
    ).insert()
    await EntityClosureModel(
        ancestor_id=str(la_office.id), descendant_id=str(la_office.id), depth=0
    ).insert()

    seattle_office = EntityModel(
        name="seattle",
        display_name="Seattle",
        slug="seattle",
        entity_class="structural",
        entity_type="office",
        parent_entity=west_coast,
        description="Seattle office",
        status="active",
    )
    await seattle_office.insert()
    print(f"   ✓ Created {seattle_office.name} (Office)")

    # Update closure table for Seattle Office
    await EntityClosureModel(
        ancestor_id=str(diverse_platform.id),
        descendant_id=str(seattle_office.id),
        depth=2,
    ).insert()
    await EntityClosureModel(
        ancestor_id=str(west_coast.id), descendant_id=str(seattle_office.id), depth=1
    ).insert()
    await EntityClosureModel(
        ancestor_id=str(seattle_office.id),
        descendant_id=str(seattle_office.id),
        depth=0,
    ).insert()

    # Level 3: Offices (East Coast)
    ny_office = EntityModel(
        name="new_york",
        display_name="New York",
        slug="new-york",
        entity_class="structural",
        entity_type="office",
        parent_entity=east_coast,
        description="New York office",
        status="active",
    )
    await ny_office.insert()
    print(f"   ✓ Created {ny_office.name} (Office)")

    # Update closure table for NY Office
    await EntityClosureModel(
        ancestor_id=str(diverse_platform.id), descendant_id=str(ny_office.id), depth=2
    ).insert()
    await EntityClosureModel(
        ancestor_id=str(east_coast.id), descendant_id=str(ny_office.id), depth=1
    ).insert()
    await EntityClosureModel(
        ancestor_id=str(ny_office.id), descendant_id=str(ny_office.id), depth=0
    ).insert()

    boston_office = EntityModel(
        name="boston",
        display_name="Boston",
        slug="boston",
        entity_class="structural",
        entity_type="office",
        parent_entity=east_coast,
        description="Boston office",
        status="active",
    )
    await boston_office.insert()
    print(f"   ✓ Created {boston_office.name} (Office)")

    # Update closure table for Boston Office
    await EntityClosureModel(
        ancestor_id=str(diverse_platform.id),
        descendant_id=str(boston_office.id),
        depth=2,
    ).insert()
    await EntityClosureModel(
        ancestor_id=str(east_coast.id), descendant_id=str(boston_office.id), depth=1
    ).insert()
    await EntityClosureModel(
        ancestor_id=str(boston_office.id), descendant_id=str(boston_office.id), depth=0
    ).insert()

    # Level 4: Teams (LA Office)
    luxury_team = EntityModel(
        name="luxury_properties",
        display_name="Luxury Properties",
        slug="luxury-properties",
        entity_class="structural",
        entity_type="team",
        parent_entity=la_office,
        description="Luxury real estate team in LA",
        status="active",
    )
    await luxury_team.insert()
    print(f"   ✓ Created {luxury_team.name} (Team)")

    # Update closure table for Luxury Team
    await EntityClosureModel(
        ancestor_id=str(diverse_platform.id), descendant_id=str(luxury_team.id), depth=3
    ).insert()
    await EntityClosureModel(
        ancestor_id=str(west_coast.id), descendant_id=str(luxury_team.id), depth=2
    ).insert()
    await EntityClosureModel(
        ancestor_id=str(la_office.id), descendant_id=str(luxury_team.id), depth=1
    ).insert()
    await EntityClosureModel(
        ancestor_id=str(luxury_team.id), descendant_id=str(luxury_team.id), depth=0
    ).insert()

    commercial_team_la = EntityModel(
        name="commercial_la",
        display_name="Commercial LA",
        slug="commercial-la",
        entity_class="structural",
        entity_type="team",
        parent_entity=la_office,
        description="Commercial real estate team in LA",
        status="active",
    )
    await commercial_team_la.insert()
    print(f"   ✓ Created {commercial_team_la.name} (Team)")

    # Update closure table
    await EntityClosureModel(
        ancestor_id=str(diverse_platform.id),
        descendant_id=str(commercial_team_la.id),
        depth=3,
    ).insert()
    await EntityClosureModel(
        ancestor_id=str(west_coast.id),
        descendant_id=str(commercial_team_la.id),
        depth=2,
    ).insert()
    await EntityClosureModel(
        ancestor_id=str(la_office.id), descendant_id=str(commercial_team_la.id), depth=1
    ).insert()
    await EntityClosureModel(
        ancestor_id=str(commercial_team_la.id),
        descendant_id=str(commercial_team_la.id),
        depth=0,
    ).insert()

    print(f"\n   Total: 9 entities across 4 levels\n")

    # Create roles
    print("🎭 Creating roles (6 total)...")
    roles_data = [
        {
            "name": "platform_admin",
            "display_name": "Platform Admin",
            "description": "Full platform access",
            "permissions": [p.name for p in permissions],  # All permissions
        },
        {
            "name": "regional_manager",
            "display_name": "Regional Manager",
            "description": "Manage entire region with tree permissions",
            "permissions": [
                "user:read",
                "user:manage_tree",
                "entity:read_tree",
                "entity:create",
                "entity:update",
                "lead:read_tree",
                "lead:manage_tree",
                "lead:assign",
                "apikey:read",
            ],
        },
        {
            "name": "office_manager",
            "display_name": "Office Manager",
            "description": "Manage office and all teams below",
            "permissions": [
                "user:read",
                "user:manage",
                "entity:read_tree",
                "entity:update",
                "lead:read_tree",
                "lead:manage_tree",
                "lead:assign",
            ],
        },
        {
            "name": "team_lead",
            "display_name": "Team Lead",
            "description": "Manage team members and leads",
            "permissions": [
                "user:read",
                "entity:read",
                "lead:read",
                "lead:create",
                "lead:update",
                "lead:delete",
                "lead:assign",
            ],
        },
        {
            "name": "agent",
            "display_name": "Agent",
            "description": "Create and manage own leads",
            "permissions": [
                "user:read",
                "entity:read",
                "lead:read",
                "lead:create",
                "lead:update_own",
            ],
        },
        {
            "name": "viewer",
            "display_name": "Viewer",
            "description": "Read-only access",
            "permissions": [
                "user:read",
                "entity:read",
                "lead:read",
            ],
        },
    ]

    roles_map = {}
    for role_data in roles_data:
        role = RoleModel(
            name=role_data["name"],
            display_name=role_data["display_name"],
            description=role_data["description"],
            permissions=role_data["permissions"],
            is_system_role=True,
            is_global=False,  # EnterpriseRBAC roles are entity-scoped
        )
        await role.insert()
        roles_map[role_data["name"]] = role

    print(f"   Created {len(roles_map)} roles\n")

    # Create test users with entity memberships
    print("👥 Creating test users (6 total)...")
    users_data = [
        {
            "key": "platform_admin",
            "email": "admin@diverse.com",
            "password": "Admin123!!",
            "first_name": "Platform",
            "last_name": "Admin",
            "role": "platform_admin",
            "entity": diverse_platform,
            "is_superuser": True,
        },
        {
            "key": "regional_manager",
            "email": "west.manager@diverse.com",
            "password": "Test123!!",
            "first_name": "West Coast",
            "last_name": "Manager",
            "role": "regional_manager",
            "entity": west_coast,
            "is_superuser": False,
        },
        {
            "key": "office_manager",
            "email": "la.manager@diverse.com",
            "password": "Test123!!",
            "first_name": "Los Angeles",
            "last_name": "Manager",
            "role": "office_manager",
            "entity": la_office,
            "is_superuser": False,
        },
        {
            "key": "team_lead",
            "email": "luxury.lead@diverse.com",
            "password": "Test123!!",
            "first_name": "Luxury",
            "last_name": "Team Lead",
            "role": "team_lead",
            "entity": luxury_team,
            "is_superuser": False,
        },
        {
            "key": "luxury_agent",
            "email": "agent.luxury@diverse.com",
            "password": "Test123!!",
            "first_name": "Luxury",
            "last_name": "Agent",
            "role": "agent",
            "entity": luxury_team,
            "is_superuser": False,
        },
        {
            "key": "commercial_agent",
            "email": "agent.commercial@diverse.com",
            "password": "Test123!!",
            "first_name": "Commercial",
            "last_name": "Agent",
            "role": "agent",
            "entity": commercial_team_la,
            "is_superuser": False,
        },
    ]

    users_map = {}
    for user_data in users_data:
        # Create user
        user = UserModel(
            email=user_data["email"],
            hashed_password=hash_password(user_data["password"]),
            first_name=user_data["first_name"],
            last_name=user_data["last_name"],
            is_superuser=user_data["is_superuser"],
            status="active",
            can_login=True,
        )
        await user.insert()
        users_map[user_data["key"]] = user

        # Create entity membership with role
        role = roles_map[user_data["role"]]
        membership = EntityMembershipModel(
            user=user,
            entity=user_data["entity"],
            roles=[role],  # EnterpriseRBAC supports multiple roles
            status="active",
            joined_at=datetime.now(UTC),
        )
        await membership.insert()

    print(f"   Created {len(users_data)} test users with entity memberships\n")

    # Create sample leads
    print("📋 Creating sample leads...")
    leads_data = [
        {
            "first_name": "John",
            "last_name": "Smith",
            "email": "john.smith@example.com",
            "phone": "+1 (555) 123-4567",
            "lead_type": "buyer",
            "property_type": "Luxury Villa",
            "budget": 5000000,
            "status": "new",
            "source": "Website",
            "entity": luxury_team,
            "created_by": users_map["luxury_agent"],
        },
        {
            "first_name": "Sarah",
            "last_name": "Johnson",
            "email": "sarah.j@example.com",
            "phone": "+1 (555) 234-5678",
            "lead_type": "buyer",
            "property_type": "Penthouse",
            "budget": 3500000,
            "status": "contacted",
            "source": "Referral",
            "entity": luxury_team,
            "created_by": users_map["luxury_agent"],
        },
        {
            "first_name": "Michael",
            "last_name": "Brown",
            "email": "m.brown@company.com",
            "phone": "+1 (555) 345-6789",
            "lead_type": "buyer",
            "property_type": "Office Space",
            "budget": 2000000,
            "status": "new",
            "source": "Zillow",
            "entity": commercial_team_la,
            "created_by": users_map["commercial_agent"],
        },
    ]

    for lead_data in leads_data:
        lead = Lead(
            first_name=lead_data["first_name"],
            last_name=lead_data["last_name"],
            email=lead_data["email"],
            phone=lead_data["phone"],
            lead_type=lead_data["lead_type"],
            property_type=lead_data["property_type"],
            budget=lead_data["budget"],
            status=lead_data["status"],
            source=lead_data["source"],
            entity_id=str(lead_data["entity"].id),
            created_by=str(lead_data["created_by"].id),
            created_at=datetime.now(UTC),
        )
        await lead.insert()

    print(f"   Created {len(leads_data)} sample leads\n")

    # Print summary
    print("=" * 70)
    print("✅ EnterpriseRBAC Test Environment Reset Complete!")
    print("=" * 70)

    print("\n🏢 Entity Hierarchy:\n")
    print("   Diverse Platform (Organization)")
    print("   ├── West Coast (Region)")
    print("   │   ├── Los Angeles (Office)")
    print("   │   │   ├── Luxury Properties (Team)")
    print("   │   │   └── Commercial LA (Team)")
    print("   │   └── Seattle (Office)")
    print("   └── East Coast (Region)")
    print("       ├── New York (Office)")
    print("       └── Boston (Office)")

    print("\n📋 Test User Credentials:\n")
    for user_data in users_data:
        role_display = roles_map[user_data["role"]].display_name
        entity_name = user_data["entity"].name
        print(f"   {user_data['first_name']} {user_data['last_name']} ({role_display})")
        print(f"   Email:    {user_data['email']}")
        print(f"   Password: {user_data['password']}")
        print(f"   Entity:   {entity_name}")
        print()

    print("🌐 Application URLs:")
    print(f"   Backend:  http://localhost:8004")
    print(f"   API Docs: http://localhost:8004/docs")
    print(f"   Admin UI: http://localhost:3000")

    print("\n💡 Next Steps:")
    print("   1. Start backend: docker-compose up enterprise-rbac")
    print("   2. Start admin UI: cd auth-ui && bun dev")
    print("   3. Login with any test user above")
    print("   4. Explore entity hierarchy and tree permissions")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(reset_database())
