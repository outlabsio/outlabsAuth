"""
Test Tree Permissions in EnterpriseRBAC

This script tests hierarchical permission inheritance using _tree suffix permissions.

Entity Hierarchy:
- diverse_platform (organization)
  ├── west_coast (region)
  │   ├── los_angeles (office)
  │   │   ├── luxury_properties (team)
  │   │   └── commercial_la (team)
  │   └── seattle (office)
  └── east_coast (region)
      ├── new_york (office)
      └── boston (office)

Test Users:
1. west.manager@diverse.com - Regional Manager (west_coast) - has lead:read_tree
2. la.manager@diverse.com - Office Manager (los_angeles) - has lead:read_tree
3. luxury.lead@diverse.com - Team Lead (luxury_properties) - has lead:read (flat)
4. agent.luxury@diverse.com - Agent (luxury_properties) - has lead:read (flat)
"""

import asyncio
import os

from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from outlabs_auth import EnterpriseRBAC
from outlabs_auth.models import (
    EntityClosureModel,
    EntityMembershipModel,
    EntityModel,
    PermissionModel,
    RefreshTokenModel,
    RoleModel,
    UserModel,
)

# Configuration
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27018")
DATABASE_NAME = os.getenv("DATABASE_NAME", "realestate_enterprise_rbac")
SECRET_KEY = os.getenv("SECRET_KEY", "test-secret-key")


async def test_tree_permissions():
    """Test tree permissions with different user roles."""

    # Initialize database connection
    client = AsyncIOMotorClient(MONGODB_URL)
    db = client[DATABASE_NAME]

    # Initialize EnterpriseRBAC (this will initialize Beanie)
    auth = EnterpriseRBAC(database=db, secret_key=SECRET_KEY)
    await auth.initialize()

    print("\n" + "=" * 80)
    print("TREE PERMISSIONS TEST SUITE")
    print("=" * 80)

    # Get entities
    diverse_platform = await EntityModel.find_one(
        EntityModel.name == "diverse_platform"
    )
    west_coast = await EntityModel.find_one(EntityModel.name == "west_coast")
    east_coast = await EntityModel.find_one(EntityModel.name == "east_coast")
    los_angeles = await EntityModel.find_one(EntityModel.name == "los_angeles")
    seattle = await EntityModel.find_one(EntityModel.name == "seattle")
    luxury_properties = await EntityModel.find_one(
        EntityModel.name == "luxury_properties"
    )
    commercial_la = await EntityModel.find_one(EntityModel.name == "commercial_la")

    # Get users
    admin = await UserModel.find_one(UserModel.email == "admin@diverse.com")
    regional_mgr = await UserModel.find_one(
        UserModel.email == "west.manager@diverse.com"
    )
    office_mgr = await UserModel.find_one(UserModel.email == "la.manager@diverse.com")
    team_lead = await UserModel.find_one(UserModel.email == "luxury.lead@diverse.com")
    agent = await UserModel.find_one(UserModel.email == "agent.luxury@diverse.com")

    # Test cases
    test_cases = [
        {
            "user": regional_mgr,
            "user_label": "Regional Manager (west_coast)",
            "permission": "lead:read",
            "entities": [
                (
                    "west_coast (region)",
                    west_coast,
                    False,
                    "own entity - has lead:read_tree but NOT lead:read",
                ),
                (
                    "los_angeles (office)",
                    los_angeles,
                    True,
                    "tree - child of west_coast",
                ),
                (
                    "luxury_properties (team)",
                    luxury_properties,
                    True,
                    "tree - descendant of west_coast",
                ),
                (
                    "commercial_la (team)",
                    commercial_la,
                    True,
                    "tree - descendant of west_coast",
                ),
                ("seattle (office)", seattle, True, "tree - child of west_coast"),
                (
                    "east_coast (region)",
                    east_coast,
                    False,
                    "different region - no access",
                ),
            ],
        },
        {
            "user": office_mgr,
            "user_label": "Office Manager (los_angeles)",
            "permission": "lead:read",
            "entities": [
                (
                    "los_angeles (office)",
                    los_angeles,
                    False,
                    "own entity - has lead:read_tree but NOT lead:read",
                ),
                (
                    "luxury_properties (team)",
                    luxury_properties,
                    True,
                    "tree - child of los_angeles",
                ),
                (
                    "commercial_la (team)",
                    commercial_la,
                    True,
                    "tree - child of los_angeles",
                ),
                (
                    "west_coast (region)",
                    west_coast,
                    False,
                    "parent - no tree permission upward",
                ),
                ("seattle (office)", seattle, False, "sibling office - no access"),
            ],
        },
        {
            "user": team_lead,
            "user_label": "Team Lead (luxury_properties) - FLAT permission",
            "permission": "lead:read",
            "entities": [
                (
                    "luxury_properties (team)",
                    luxury_properties,
                    True,
                    "direct - flat permission",
                ),
                (
                    "commercial_la (team)",
                    commercial_la,
                    False,
                    "sibling team - no tree permission",
                ),
                (
                    "los_angeles (office)",
                    los_angeles,
                    False,
                    "parent - flat permission only",
                ),
            ],
        },
        {
            "user": agent,
            "user_label": "Agent (luxury_properties) - FLAT permission",
            "permission": "lead:read",
            "entities": [
                (
                    "luxury_properties (team)",
                    luxury_properties,
                    True,
                    "direct - flat permission",
                ),
                (
                    "commercial_la (team)",
                    commercial_la,
                    False,
                    "sibling team - no access",
                ),
                ("los_angeles (office)", los_angeles, False, "parent - no access"),
            ],
        },
    ]

    # Run test cases
    for test_case in test_cases:
        user = test_case["user"]
        user_label = test_case["user_label"]
        permission = test_case["permission"]
        entities = test_case["entities"]

        print(f"\n{'─' * 80}")
        print(f"Testing: {user_label}")
        print(f"User: {user.email}")
        print(f"Permission: {permission}")
        print(f"{'─' * 80}\n")

        for entity_label, entity, expected, reason in entities:
            entity_id = str(entity.id)

            # Check permission
            has_perm, source = await auth.permission_service.check_permission(
                user_id=str(user.id),
                permission=permission,
                entity_id=entity_id,
            )

            # Determine result icon
            if has_perm == expected:
                icon = "✅"
                status = "PASS"
            else:
                icon = "❌"
                status = "FAIL"

            # Format output
            expected_str = "GRANTED" if expected else "DENIED"
            actual_str = f"GRANTED ({source})" if has_perm else "DENIED"

            print(f"{icon} {status} | {entity_label}")
            print(f"   Expected: {expected_str}")
            print(f"   Actual:   {actual_str}")
            print(f"   Reason:   {reason}")
            print()

    print("=" * 80)
    print("TREE PERMISSIONS TEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_tree_permissions())
