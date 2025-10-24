"""
Real Estate Leads Platform - Seed Data

Creates comprehensive demo data demonstrating 5 real-world client scenarios:
1. RE/MAX National - Full franchise hierarchy
2. RE/MAX Regional - Subset of locations under one account
3. Keller Williams - Independent brokerage with different naming
4. Solo Agent with Team - Minimal hierarchy
5. Solo Agent Only - Flattest structure

Also creates internal teams (support, finance, leadership) with global access.
"""
import asyncio
import os
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

# Import models
from models import Lead, LeadNote
from profiles import ExtendedUserModel, AgentProfile, TeamMemberProfile
from outlabs_auth import EnterpriseRBAC
from outlabs_auth.models.role import RoleModel
from outlabs_auth.models.entity import EntityModel, EntityClass
from outlabs_auth.models.membership import EntityMembershipModel
from outlabs_auth.models.closure import EntityClosureModel
from outlabs_auth.models.permission import PermissionModel
from outlabs_auth.utils.password import hash_password

# Configuration
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "realestate_leads_platform")
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production-please")

# ============================================================================
# Helper Functions
# ============================================================================

async def create_role_if_not_exists(auth, name: str, permissions: list, display_name: str, description: str = None):
    """Create role if it doesn't exist"""
    # Check if role exists
    existing_role = await RoleModel.find_one(RoleModel.name == name)
    if existing_role:
        print(f"  ✓ Role '{name}' already exists")
        return existing_role

    # Create new role
    role = await auth.role_service.create_role(
        name=name,
        display_name=display_name,
        description=description or display_name,
        permissions=permissions,
        is_global=True
    )
    print(f"  ✓ Created role '{name}' with {len(permissions)} permissions")
    return role


async def create_user_if_not_exists(
    auth, email: str, password: str, full_name: str, role_id: str,
    user_type: str = "team_member", profile_data: dict = None
):
    """
    Create user if doesn't exist, with profile.

    Args:
        auth: EnterpriseRBAC instance
        email: User email
        password: User password
        full_name: Full name (will be split into first/last)
        role_id: Role ID (unused in this function, kept for compatibility)
        user_type: User type ('agent', 'team_member', 'admin')
        profile_data: Optional profile data dict
    """
    # Check if user exists
    existing_user = await ExtendedUserModel.find_one(ExtendedUserModel.email == email)
    if existing_user:
        print(f"  ✓ User '{email}' already exists")
        return existing_user

    # Split full_name into first/last
    name_parts = full_name.split(" ", 1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else ""

    # Create user with user_type
    from outlabs_auth.models.user import UserStatus
    user = ExtendedUserModel(
        email=email,
        hashed_password=hash_password(password),
        first_name=first_name,
        last_name=last_name,
        user_type=user_type,
        status=UserStatus.ACTIVE,
        email_verified=True
    )
    await user.insert()

    # Create profile based on user_type
    if user_type == "agent" and profile_data:
        profile = AgentProfile(**profile_data)
        await profile.save()
        user.agent_profile = profile
        await user.save()
        print(f"  ✓ Created agent '{email}' ({full_name}) with profile")
    elif user_type == "team_member" and profile_data:
        profile = TeamMemberProfile(**profile_data)
        await profile.save()
        user.team_member_profile = profile
        await user.save()
        print(f"  ✓ Created team member '{email}' ({full_name}) with profile")
    else:
        print(f"  ✓ Created {user_type} '{email}' ({full_name})")

    return user


async def create_entity(auth, name: str, entity_type: str, entity_class: EntityClass,
                       parent_id: str = None, display_name: str = None):
    """Create entity and return it"""
    entity = await auth.entity_service.create_entity(
        name=name,
        entity_type=entity_type,
        entity_class=entity_class,
        parent_id=parent_id,
        display_name=display_name or name,
        description=f"{entity_type.title()}: {display_name or name}"
    )
    print(f"    ✓ Created {entity_type}: {display_name or name}")
    return entity


async def add_member(auth, user_id: str, entity_id: str, role_ids: list):
    """Add user as member of entity"""
    await auth.membership_service.add_member(
        entity_id=entity_id,
        user_id=user_id,
        role_ids=role_ids
    )


async def create_lead(
    entity_id: str, lead_type: str, first_name: str, last_name: str,
    email: str, phone: str, source: str, status: str, created_by: str,
    assigned_to: str = None, budget: int = None, location: str = None,
    property_type: str = None, bedrooms: int = None, bathrooms: float = None,
    timeline: str = None, property_address: str = None, asking_price: int = None,
    notes: list = None
):
    """Create a lead"""
    lead = Lead(
        entity_id=entity_id,
        lead_type=lead_type,
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone,
        source=source,
        status=status,
        assigned_to=assigned_to,
        budget=budget,
        location=location,
        property_type=property_type,
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        timeline=timeline,
        property_address=property_address,
        asking_price=asking_price,
        notes=notes or [],
        created_by=created_by,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    await lead.insert()
    return lead


# ============================================================================
# Scenario 1: RE/MAX National - Full Franchise Hierarchy
# ============================================================================

async def create_remax_national(auth, roles, users):
    """
    Scenario 1: RE/MAX National Franchise

    5-level hierarchy:
    RE/MAX Corporate
    └── RE/MAX California (state)
        └── RE/MAX Bay Area (region)
            └── RE/MAX Silicon Valley Brokerage
                └── Downtown Team (ACCESS_GROUP)
    """
    print("\n📍 Scenario 1: RE/MAX National Franchise")

    # Level 1: Corporate
    remax_corp = await create_entity(
        auth, "remax_corporate", "corporate", EntityClass.STRUCTURAL,
        display_name="RE/MAX Corporate"
    )

    # Level 2: State
    remax_ca = await create_entity(
        auth, "remax_california", "state", EntityClass.STRUCTURAL,
        parent_id=str(remax_corp.id), display_name="RE/MAX California"
    )

    # Level 3: Region
    remax_bay = await create_entity(
        auth, "remax_bay_area", "region", EntityClass.STRUCTURAL,
        parent_id=str(remax_ca.id), display_name="RE/MAX Bay Area"
    )

    # Level 4: Brokerage
    remax_sv = await create_entity(
        auth, "remax_silicon_valley", "brokerage", EntityClass.STRUCTURAL,
        parent_id=str(remax_bay.id), display_name="RE/MAX Silicon Valley"
    )

    # Level 5: Teams (ACCESS_GROUP)
    downtown_team = await create_entity(
        auth, "remax_sv_downtown_team", "team", EntityClass.ACCESS_GROUP,
        parent_id=str(remax_sv.id), display_name="Downtown Team"
    )

    residential_team = await create_entity(
        auth, "remax_sv_residential_team", "team", EntityClass.ACCESS_GROUP,
        parent_id=str(remax_sv.id), display_name="Residential Team"
    )

    # Create users
    franchise_exec = await create_user_if_not_exists(
        auth, "exec@remax.com", "Password123!", "Sarah Johnson",
        roles["franchise_executive"].id, "sarah_johnson"
    )

    broker_owner = await create_user_if_not_exists(
        auth, "broker@remax-sv.com", "Password123!", "Michael Chen",
        roles["broker_owner"].id, "michael_chen"
    )

    team_lead = await create_user_if_not_exists(
        auth, "downtown@remax-sv.com", "Password123!", "Emily Rodriguez",
        roles["team_lead"].id, "emily_rodriguez"
    )

    agent1 = await create_user_if_not_exists(
        auth, "agent1@remax-sv.com", "Password123!", "David Kim",
        roles["agent"].id, "david_kim",
        user_type="agent",
        profile_data={
            "license_number": "DRE01234567",
            "license_state": "CA",
            "brokerage_name": "RE/MAX Silicon Valley",
            "years_experience": 5,
            "specialties": ["residential", "first-time buyers"],
            "bio": "Dedicated to helping first-time buyers find their dream home",
            "certifications": ["ABR", "PSA"],
            "deals_closed": 47,
            "total_sales_volume": 23500000
        }
    )

    agent2 = await create_user_if_not_exists(
        auth, "agent2@remax-sv.com", "Password123!", "Jessica Martinez",
        roles["agent"].id, "jessica_martinez",
        user_type="agent",
        profile_data={
            "license_number": "DRE01234568",
            "license_state": "CA",
            "brokerage_name": "RE/MAX Silicon Valley",
            "years_experience": 3,
            "specialties": ["residential", "luxury"],
            "bio": "Luxury home specialist with a passion for modern architecture",
            "certifications": ["CRS"],
            "deals_closed": 29,
            "total_sales_volume": 18700000
        }
    )

    # Add memberships
    await add_member(auth, str(franchise_exec.id), str(remax_corp.id), [str(roles["franchise_executive"].id)])
    await add_member(auth, str(broker_owner.id), str(remax_sv.id), [str(roles["broker_owner"].id)])
    await add_member(auth, str(team_lead.id), str(downtown_team.id), [str(roles["team_lead"].id)])
    await add_member(auth, str(agent1.id), str(downtown_team.id), [str(roles["agent"].id)])
    await add_member(auth, str(agent2.id), str(residential_team.id), [str(roles["agent"].id)])

    # Create leads
    print("    Creating sample leads...")

    # Downtown Team leads
    await create_lead(
        entity_id=str(downtown_team.id),
        lead_type="buyer",
        first_name="John", last_name="Smith",
        email="john.smith@email.com", phone="415-555-0101",
        source="Zillow", status="qualified",
        budget=1200000, location="San Francisco", property_type="condo",
        bedrooms=2, bathrooms=2.0, timeline="1-3 months",
        assigned_to=str(agent1.id),
        created_by=str(agent1.id),
        notes=["Initial contact made", "Looking in SOMA area"]
    )

    await create_lead(
        entity_id=str(downtown_team.id),
        lead_type="seller",
        first_name="Maria", last_name="Garcia",
        email="maria.garcia@email.com", phone="415-555-0102",
        source="Referral", status="new",
        property_address="123 Market St, San Francisco, CA",
        asking_price=1500000, property_type="condo",
        bedrooms=3, bathrooms=2.5,
        assigned_to=str(agent1.id),
        created_by=str(team_lead.id)
    )

    # Residential Team leads
    await create_lead(
        entity_id=str(residential_team.id),
        lead_type="both",
        first_name="Robert", last_name="Taylor",
        email="robert.taylor@email.com", phone="408-555-0103",
        source="Website", status="contacted",
        budget=800000, location="San Jose", property_type="house",
        bedrooms=3, bathrooms=2.0, timeline="3-6 months",
        property_address="456 Oak Ave, San Jose, CA",
        asking_price=750000,
        assigned_to=str(agent2.id),
        created_by=str(agent2.id)
    )

    print(f"  ✓ Created RE/MAX National scenario with 5 entities, 5 users, 3 leads")

    return {
        "entities": {
            "corporate": remax_corp,
            "state": remax_ca,
            "region": remax_bay,
            "brokerage": remax_sv,
            "downtown_team": downtown_team,
            "residential_team": residential_team
        },
        "users": {
            "exec": franchise_exec,
            "broker": broker_owner,
            "team_lead": team_lead,
            "agent1": agent1,
            "agent2": agent2
        }
    }


# ============================================================================
# Scenario 2: RE/MAX Regional - 3 Brokerages Under One Account
# ============================================================================

async def create_remax_regional(auth, roles, users):
    """
    Scenario 2: RE/MAX Regional Account

    3-level hierarchy (no state/region):
    RE/MAX Regional Account
    ├── RE/MAX Oakland Brokerage
    │   └── Oakland Team
    ├── RE/MAX Berkeley Brokerage
    │   └── Berkeley Team
    └── RE/MAX Fremont Brokerage
        └── Fremont Team
    """
    print("\n📍 Scenario 2: RE/MAX Regional Account (3 Brokerages)")

    # Level 1: Regional Account
    regional = await create_entity(
        auth, "remax_east_bay", "regional_account", EntityClass.STRUCTURAL,
        display_name="RE/MAX East Bay Regional"
    )

    # Level 2: Brokerages
    oakland_brokerage = await create_entity(
        auth, "remax_oakland", "brokerage", EntityClass.STRUCTURAL,
        parent_id=str(regional.id), display_name="RE/MAX Oakland"
    )

    berkeley_brokerage = await create_entity(
        auth, "remax_berkeley", "brokerage", EntityClass.STRUCTURAL,
        parent_id=str(regional.id), display_name="RE/MAX Berkeley"
    )

    fremont_brokerage = await create_entity(
        auth, "remax_fremont", "brokerage", EntityClass.STRUCTURAL,
        parent_id=str(regional.id), display_name="RE/MAX Fremont"
    )

    # Level 3: Teams
    oakland_team = await create_entity(
        auth, "oakland_team", "team", EntityClass.ACCESS_GROUP,
        parent_id=str(oakland_brokerage.id), display_name="Oakland Team"
    )

    berkeley_team = await create_entity(
        auth, "berkeley_team", "team", EntityClass.ACCESS_GROUP,
        parent_id=str(berkeley_brokerage.id), display_name="Berkeley Team"
    )

    # Create users
    regional_manager = await create_user_if_not_exists(
        auth, "manager@remax-eastbay.com", "Password123!", "Linda Wu",
        roles["regional_manager"].id, "linda_wu"
    )

    oakland_agent = await create_user_if_not_exists(
        auth, "agent@remax-oakland.com", "Password123!", "Marcus Johnson",
        roles["agent"].id, "marcus_johnson"
    )

    berkeley_agent = await create_user_if_not_exists(
        auth, "agent@remax-berkeley.com", "Password123!", "Sophie Anderson",
        roles["agent"].id, "sophie_anderson"
    )

    # Add memberships
    await add_member(auth, str(regional_manager.id), str(regional.id), [str(roles["regional_manager"].id)])
    await add_member(auth, str(oakland_agent.id), str(oakland_team.id), [str(roles["agent"].id)])
    await add_member(auth, str(berkeley_agent.id), str(berkeley_team.id), [str(roles["agent"].id)])

    # Create leads
    print("    Creating sample leads...")

    await create_lead(
        entity_id=str(oakland_team.id),
        lead_type="buyer",
        first_name="Patricia", last_name="Brown",
        email="patricia.brown@email.com", phone="510-555-0201",
        source="Realtor.com", status="showing",
        budget=650000, location="Oakland", property_type="house",
        bedrooms=3, bathrooms=2.0, timeline="immediate",
        assigned_to=str(oakland_agent.id),
        created_by=str(oakland_agent.id)
    )

    await create_lead(
        entity_id=str(berkeley_team.id),
        lead_type="seller",
        first_name="Thomas", last_name="Lee",
        email="thomas.lee@email.com", phone="510-555-0202",
        source="Walk-in", status="qualified",
        property_address="789 University Ave, Berkeley, CA",
        asking_price=950000, property_type="house",
        bedrooms=4, bathrooms=3.0,
        assigned_to=str(berkeley_agent.id),
        created_by=str(berkeley_agent.id)
    )

    print(f"  ✓ Created RE/MAX Regional scenario with 6 entities, 3 users, 2 leads")

    return {
        "entities": {
            "regional": regional,
            "oakland": oakland_brokerage,
            "berkeley": berkeley_brokerage,
            "fremont": fremont_brokerage,
            "oakland_team": oakland_team,
            "berkeley_team": berkeley_team
        },
        "users": {
            "manager": regional_manager,
            "oakland_agent": oakland_agent,
            "berkeley_agent": berkeley_agent
        }
    }


# ============================================================================
# Scenario 3: Keller Williams - Different Naming Convention
# ============================================================================

async def create_keller_williams(auth, roles, users):
    """
    Scenario 3: Keller Williams Independent Brokerage

    Different naming: "market_center" instead of "brokerage"

    Keller Williams Realty
    └── Palo Alto Market Center
        └── Luxury Division (ACCESS_GROUP)
    """
    print("\n📍 Scenario 3: Keller Williams (Different Naming)")

    # Level 1: Company
    kw = await create_entity(
        auth, "keller_williams_realty", "company", EntityClass.STRUCTURAL,
        display_name="Keller Williams Realty"
    )

    # Level 2: Market Center (their term for brokerage)
    palo_alto = await create_entity(
        auth, "kw_palo_alto", "market_center", EntityClass.STRUCTURAL,
        parent_id=str(kw.id), display_name="Palo Alto Market Center"
    )

    # Level 3: Divisions (ACCESS_GROUP)
    luxury_division = await create_entity(
        auth, "kw_pa_luxury", "division", EntityClass.ACCESS_GROUP,
        parent_id=str(palo_alto.id), display_name="Luxury Division"
    )

    first_time_buyers = await create_entity(
        auth, "kw_pa_ftb", "division", EntityClass.ACCESS_GROUP,
        parent_id=str(palo_alto.id), display_name="First-Time Buyers Division"
    )

    # Create users
    market_center_leader = await create_user_if_not_exists(
        auth, "leader@kw-paloalto.com", "Password123!", "Jennifer White",
        roles["broker_owner"].id, "jennifer_white"
    )

    luxury_agent = await create_user_if_not_exists(
        auth, "luxury@kw-paloalto.com", "Password123!", "Alexander Sterling",
        roles["agent"].id, "alexander_sterling",
        user_type="agent",
        profile_data={
            "license_number": "DRE01987654",
            "license_state": "CA",
            "brokerage_name": "Keller Williams Palo Alto",
            "years_experience": 12,
            "specialties": ["luxury", "investment", "commercial"],
            "bio": "Award-winning luxury real estate specialist serving Silicon Valley's elite",
            "certifications": ["CRS", "GRI", "CLHMS"],
            "deals_closed": 156,
            "total_sales_volume": 187000000,
            "languages": ["English", "Mandarin", "Spanish"]
        }
    )

    ftb_agent = await create_user_if_not_exists(
        auth, "ftb@kw-paloalto.com", "Password123!", "Rachel Green",
        roles["agent"].id, "rachel_green"
    )

    # Add memberships
    await add_member(auth, str(market_center_leader.id), str(palo_alto.id), [str(roles["broker_owner"].id)])
    await add_member(auth, str(luxury_agent.id), str(luxury_division.id), [str(roles["agent"].id)])
    await add_member(auth, str(ftb_agent.id), str(first_time_buyers.id), [str(roles["agent"].id)])

    # Create leads
    print("    Creating sample leads...")

    await create_lead(
        entity_id=str(luxury_division.id),
        lead_type="buyer",
        first_name="Victoria", last_name="Montgomery",
        email="victoria.montgomery@email.com", phone="650-555-0301",
        source="Luxury Portfolio", status="showing",
        budget=3500000, location="Atherton", property_type="house",
        bedrooms=5, bathrooms=4.5, timeline="6-12 months",
        assigned_to=str(luxury_agent.id),
        created_by=str(luxury_agent.id),
        notes=["High net worth client", "Looking for estate properties"]
    )

    await create_lead(
        entity_id=str(first_time_buyers.id),
        lead_type="buyer",
        first_name="Kevin", last_name="Patel",
        email="kevin.patel@email.com", phone="650-555-0302",
        source="Google Ads", status="qualified",
        budget=550000, location="Mountain View", property_type="condo",
        bedrooms=1, bathrooms=1.0, timeline="1-3 months",
        assigned_to=str(ftb_agent.id),
        created_by=str(ftb_agent.id)
    )

    print(f"  ✓ Created Keller Williams scenario with 4 entities, 3 users, 2 leads")

    return {
        "entities": {
            "company": kw,
            "market_center": palo_alto,
            "luxury": luxury_division,
            "ftb": first_time_buyers
        },
        "users": {
            "leader": market_center_leader,
            "luxury_agent": luxury_agent,
            "ftb_agent": ftb_agent
        }
    }


# ============================================================================
# Scenario 4: Solo Agent with Team
# ============================================================================

async def create_solo_with_team(auth, roles, users):
    """
    Scenario 4: Solo Agent with Small Team

    Minimal 2-level hierarchy:
    Jane's Real Estate
    └── Jane's Team (ACCESS_GROUP)
    """
    print("\n📍 Scenario 4: Solo Agent with Team")

    # Level 1: Business
    janes_business = await create_entity(
        auth, "janes_real_estate", "business", EntityClass.STRUCTURAL,
        display_name="Jane's Real Estate"
    )

    # Level 2: Team (ACCESS_GROUP)
    janes_team = await create_entity(
        auth, "janes_team", "workspace", EntityClass.ACCESS_GROUP,
        parent_id=str(janes_business.id), display_name="Jane's Team"
    )

    # Create users
    jane = await create_user_if_not_exists(
        auth, "jane@janesrealestate.com", "Password123!", "Jane Williams",
        roles["solo_agent"].id, "jane_williams"
    )

    assistant = await create_user_if_not_exists(
        auth, "assistant@janesrealestate.com", "Password123!", "Mark Thompson",
        roles["assistant"].id, "mark_thompson"
    )

    # Add memberships
    await add_member(auth, str(jane.id), str(janes_team.id), [str(roles["solo_agent"].id)])
    await add_member(auth, str(assistant.id), str(janes_team.id), [str(roles["assistant"].id)])

    # Create leads
    print("    Creating sample leads...")

    await create_lead(
        entity_id=str(janes_team.id),
        lead_type="buyer",
        first_name="Amy", last_name="Chen",
        email="amy.chen@email.com", phone="408-555-0401",
        source="Facebook", status="new",
        budget=700000, location="Santa Clara", property_type="townhouse",
        bedrooms=3, bathrooms=2.5, timeline="3-6 months",
        assigned_to=str(jane.id),
        created_by=str(assistant.id)
    )

    await create_lead(
        entity_id=str(janes_team.id),
        lead_type="seller",
        first_name="George", last_name="Miller",
        email="george.miller@email.com", phone="408-555-0402",
        source="Referral", status="contacted",
        property_address="321 Elm St, Santa Clara, CA",
        asking_price=825000, property_type="house",
        bedrooms=4, bathrooms=2.0,
        assigned_to=str(jane.id),
        created_by=str(jane.id)
    )

    print(f"  ✓ Created Solo with Team scenario with 2 entities, 2 users, 2 leads")

    return {
        "entities": {
            "business": janes_business,
            "team": janes_team
        },
        "users": {
            "jane": jane,
            "assistant": assistant
        }
    }


# ============================================================================
# Scenario 5: Solo Agent Only (Flattest Structure)
# ============================================================================

async def create_solo_only(auth, roles, users):
    """
    Scenario 5: Solo Agent (No Team)

    Flattest structure - just one entity:
    Mike's Properties (ACCESS_GROUP)
    """
    print("\n📍 Scenario 5: Solo Agent Only (Flattest)")

    # Single entity (ACCESS_GROUP)
    mikes_workspace = await create_entity(
        auth, "mikes_properties", "workspace", EntityClass.ACCESS_GROUP,
        display_name="Mike's Properties"
    )

    # Create user
    mike = await create_user_if_not_exists(
        auth, "mike@mikesproperties.com", "Password123!", "Mike Davis",
        roles["solo_agent"].id, "mike_davis"
    )

    # Add membership
    await add_member(auth, str(mike.id), str(mikes_workspace.id), [str(roles["solo_agent"].id)])

    # Create leads
    print("    Creating sample leads...")

    await create_lead(
        entity_id=str(mikes_workspace.id),
        lead_type="buyer",
        first_name="Sarah", last_name="Johnson",
        email="sarah.j@email.com", phone="650-555-0501",
        source="Instagram", status="qualified",
        budget=600000, location="Redwood City", property_type="condo",
        bedrooms=2, bathrooms=2.0, timeline="immediate",
        assigned_to=str(mike.id),
        created_by=str(mike.id)
    )

    await create_lead(
        entity_id=str(mikes_workspace.id),
        lead_type="seller",
        first_name="Daniel", last_name="Brown",
        email="daniel.brown@email.com", phone="650-555-0502",
        source="Website", status="new",
        property_address="555 Cedar Dr, Redwood City, CA",
        asking_price=725000, property_type="house",
        bedrooms=3, bathrooms=2.0,
        assigned_to=str(mike.id),
        created_by=str(mike.id)
    )

    print(f"  ✓ Created Solo Only scenario with 1 entity, 1 user, 2 leads")

    return {
        "entities": {
            "workspace": mikes_workspace
        },
        "users": {
            "mike": mike
        }
    }


# ============================================================================
# Internal Teams (Global Access)
# ============================================================================

async def create_internal_teams(auth, roles, users):
    """
    Create internal company teams with global access permissions.

    These teams exist outside the client hierarchy and have
    special permissions to access all leads across all clients.
    """
    print("\n🏢 Internal Teams (Global Access)")

    # Internal Teams Container
    internal = await create_entity(
        auth, "outlabs_internal", "department", EntityClass.STRUCTURAL,
        display_name="OutLabs Internal"
    )

    # Support Team
    support_team = await create_entity(
        auth, "support_team", "team", EntityClass.ACCESS_GROUP,
        parent_id=str(internal.id), display_name="Support Team"
    )

    # Finance Team
    finance_team = await create_entity(
        auth, "finance_team", "team", EntityClass.ACCESS_GROUP,
        parent_id=str(internal.id), display_name="Finance Team"
    )

    # Leadership
    leadership = await create_entity(
        auth, "leadership", "team", EntityClass.ACCESS_GROUP,
        parent_id=str(internal.id), display_name="Leadership Team"
    )

    # Create internal users (team_member type with profiles)
    support_rep = await create_user_if_not_exists(
        auth, "support@outlabs.com", "Password123!", "Chris Support",
        roles["support_rep"].id, "chris_support",
        user_type="team_member",
        profile_data={
            "job_title": "Support Representative",
            "department": "support",
            "access_level": "standard",
            "can_view_all_leads": True,
            "skills": ["customer service", "crm", "troubleshooting"]
        }
    )

    finance_admin = await create_user_if_not_exists(
        auth, "finance@outlabs.com", "Password123!", "Angela Finance",
        roles["finance_admin"].id, "angela_finance",
        user_type="team_member",
        profile_data={
            "job_title": "Finance Administrator",
            "department": "operations",
            "access_level": "elevated",
            "can_view_all_leads": False,
            "skills": ["accounting", "reporting", "billing"]
        }
    )

    ceo = await create_user_if_not_exists(
        auth, "ceo@outlabs.com", "Password123!", "Alex CEO",
        roles["system_admin"].id, "alex_ceo",
        user_type="admin"  # Admin has no profile
    )

    # Add memberships
    await add_member(auth, str(support_rep.id), str(support_team.id), [str(roles["support_rep"].id)])
    await add_member(auth, str(finance_admin.id), str(finance_team.id), [str(roles["finance_admin"].id)])
    await add_member(auth, str(ceo.id), str(leadership.id), [str(roles["system_admin"].id)])

    print(f"  ✓ Created internal teams with 4 entities, 3 users")

    return {
        "entities": {
            "internal": internal,
            "support": support_team,
            "finance": finance_team,
            "leadership": leadership
        },
        "users": {
            "support": support_rep,
            "finance": finance_admin,
            "ceo": ceo
        }
    }


# ============================================================================
# Main Seed Function
# ============================================================================

async def seed_all():
    """Main seed function - creates everything"""
    print("=" * 80)
    print("🌱 SEEDING REAL ESTATE LEADS PLATFORM")
    print("=" * 80)

    # Connect to MongoDB
    print("\n📦 Connecting to MongoDB...")
    client = AsyncIOMotorClient(MONGODB_URL)
    db = client[DATABASE_NAME]

    # Initialize EnterpriseRBAC with ExtendedUserModel
    print("🔐 Initializing EnterpriseRBAC...")
    auth = EnterpriseRBAC(
        database=db,
        secret_key=SECRET_KEY,
        user_model=ExtendedUserModel,  # Use extended user model with profiles
        enable_caching=False,  # Disable caching for seeding
        enable_context_aware_roles=False,
        enable_abac=False
    )

    # Initialize Beanie with all document models
    await init_beanie(
        database=db,
        document_models=[
            ExtendedUserModel,   # Extended user model with profile links
            AgentProfile,        # Agent profiles
            TeamMemberProfile,   # Team member profiles
            RoleModel, PermissionModel, EntityModel,
            EntityMembershipModel, EntityClosureModel, Lead, LeadNote
        ]
    )

    await auth.initialize()
    print("✅ Database initialized\n")

    # Create Roles
    print("👥 Creating Roles...")
    roles = {}

    # Agent roles
    roles["agent"] = await create_role_if_not_exists(
        auth, "agent",
        ["lead:read", "lead:create", "lead:update", "lead:assign", "lead:delete"],
        "Agent",
        "Real estate agent - can manage leads in their team"
    )

    roles["team_lead"] = await create_role_if_not_exists(
        auth, "team_lead",
        ["lead:read_tree", "lead:update_tree", "lead:assign", "user:read"],
        "Team Lead",
        "Team leader - sees all team leads with tree permissions"
    )

    roles["broker_owner"] = await create_role_if_not_exists(
        auth, "broker_owner",
        ["lead:read_tree", "lead:update_tree", "lead:delete_tree",
         "user:read", "entity:read", "role:read"],
        "Broker/Owner",
        "Broker/Owner - full access to brokerage hierarchy"
    )

    roles["regional_manager"] = await create_role_if_not_exists(
        auth, "regional_manager",
        ["lead:read_tree", "lead:update_tree", "user:read", "entity:read"],
        "Regional Manager",
        "Regional manager - oversees multiple brokerages"
    )

    roles["franchise_executive"] = await create_role_if_not_exists(
        auth, "franchise_executive",
        ["lead:read_tree", "user:read", "entity:read", "role:read"],
        "Franchise Executive",
        "Franchise executive - read-only access to entire franchise"
    )

    # Specialist roles (granular permissions)
    roles["buyer_specialist"] = await create_role_if_not_exists(
        auth, "buyer_specialist",
        ["lead:read", "lead:create", "lead:update_buyers"],
        "Buyer Specialist",
        "Buyer specialist - only handles buyer leads"
    )

    roles["seller_specialist"] = await create_role_if_not_exists(
        auth, "seller_specialist",
        ["lead:read", "lead:create", "lead:update_sellers"],
        "Seller Specialist",
        "Seller specialist - only handles seller leads"
    )

    # Solo agent roles
    roles["solo_agent"] = await create_role_if_not_exists(
        auth, "solo_agent",
        ["lead:read", "lead:create", "lead:update", "lead:assign", "lead:delete"],
        "Solo Agent",
        "Solo agent - full access to their workspace"
    )

    roles["assistant"] = await create_role_if_not_exists(
        auth, "assistant",
        ["lead:read", "lead:create", "lead:update"],
        "Assistant",
        "Assistant - can create and update leads"
    )

    # Internal team roles (global access)
    roles["support_rep"] = await create_role_if_not_exists(
        auth, "support_rep",
        ["support:read_leads", "support:add_notes", "lead:read"],
        "Support Rep",
        "Support representative - read-only access to all leads"
    )

    roles["finance_admin"] = await create_role_if_not_exists(
        auth, "finance_admin",
        ["finance:read_all", "lead:read", "user:read"],
        "Finance Admin",
        "Finance admin - read access for billing purposes"
    )

    roles["system_admin"] = await create_role_if_not_exists(
        auth, "system_admin",
        ["*:*"],
        "System Admin",
        "System administrator - full system access"
    )

    print(f"✅ Created {len(roles)} roles\n")

    # Create all scenarios
    users = {}

    remax_national = await create_remax_national(auth, roles, users)
    remax_regional = await create_remax_regional(auth, roles, users)
    keller_williams = await create_keller_williams(auth, roles, users)
    solo_with_team = await create_solo_with_team(auth, roles, users)
    solo_only = await create_solo_only(auth, roles, users)
    internal_teams = await create_internal_teams(auth, roles, users)

    # Summary
    print("\n" + "=" * 80)
    print("✅ SEEDING COMPLETE!")
    print("=" * 80)

    total_entities = await EntityModel.find().count()
    total_users = await ExtendedUserModel.find().count()
    total_leads = await Lead.find().count()
    total_roles = await RoleModel.find().count()

    print(f"\n📊 Summary:")
    print(f"  • {total_roles} roles")
    print(f"  • {total_users} users")
    print(f"  • {total_entities} entities")
    print(f"  • {total_leads} leads")

    print(f"\n🔐 Demo Credentials:")
    print(f"\n  Scenario 1 (RE/MAX National):")
    print(f"    exec@remax.com          / password123  (Franchise Executive)")
    print(f"    broker@remax-sv.com     / password123  (Broker/Owner)")
    print(f"    downtown@remax-sv.com   / password123  (Team Lead)")
    print(f"    agent1@remax-sv.com     / password123  (Agent)")

    print(f"\n  Scenario 2 (RE/MAX Regional):")
    print(f"    manager@remax-eastbay.com / password123  (Regional Manager)")
    print(f"    agent@remax-oakland.com   / password123  (Agent)")

    print(f"\n  Scenario 3 (Keller Williams):")
    print(f"    leader@kw-paloalto.com  / password123  (Market Center Leader)")
    print(f"    luxury@kw-paloalto.com  / password123  (Luxury Agent)")

    print(f"\n  Scenario 4 (Solo with Team):")
    print(f"    jane@janesrealestate.com / password123  (Solo Agent)")

    print(f"\n  Scenario 5 (Solo Only):")
    print(f"    mike@mikesproperties.com / password123  (Solo Agent)")

    print(f"\n  Internal Teams:")
    print(f"    support@outlabs.com     / password123  (Support)")
    print(f"    finance@outlabs.com     / password123  (Finance)")
    print(f"    ceo@outlabs.com         / password123  (System Admin)")

    print(f"\n🚀 Start the application:")
    print(f"    uvicorn main_realestate:app --reload --port 8001")
    print(f"\n📚 API Docs:")
    print(f"    http://localhost:8001/docs")

    print("\n" + "=" * 80)

    # Close connection
    client.close()


# ============================================================================
# Run Script
# ============================================================================

if __name__ == "__main__":
    asyncio.run(seed_all())
