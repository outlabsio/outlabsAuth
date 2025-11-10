"""
Test Entity-Scoped API Keys with Tree Permissions

This script tests API keys that are scoped to specific entities
and can optionally inherit permissions from the entity tree.

Test Scenarios:
1. API key scoped to entity without tree inheritance (direct access only)
2. API key scoped to entity WITH tree inheritance (access descendants)
3. Global API key (no entity_id, access everywhere)
"""

import asyncio
import os

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
SECRET_KEY = os.getenv("SECRET_KEY", "test-secret")


async def test_entity_scoped_api_keys():
    """Test entity-scoped API keys with tree permissions."""

    # Initialize database connection
    client = AsyncIOMotorClient(MONGODB_URL)
    db = client[DATABASE_NAME]

    # Initialize EnterpriseRBAC
    auth = EnterpriseRBAC(database=db, secret_key=SECRET_KEY)
    await auth.initialize()

    print("\n" + "=" * 80)
    print("ENTITY-SCOPED API KEYS TEST SUITE")
    print("=" * 80)

    # Get entities
    west_coast = await EntityModel.find_one(EntityModel.name == "west_coast")
    los_angeles = await EntityModel.find_one(EntityModel.name == "los_angeles")
    luxury_properties = await EntityModel.find_one(
        EntityModel.name == "luxury_properties"
    )
    seattle = await EntityModel.find_one(EntityModel.name == "seattle")
    east_coast = await EntityModel.find_one(EntityModel.name == "east_coast")

    # Get admin user to own the API keys
    admin = await UserModel.find_one(UserModel.email == "admin@diverse.com")

    print(f"\n📋 Test Setup:")
    print(f"   Entity Hierarchy:")
    print(f"   - west_coast (region)")
    print(f"     - los_angeles (office)")
    print(f"       - luxury_properties (team)")
    print(f"     - seattle (office)")
    print(f"   - east_coast (region)")
    print()

    # Test Case 1: API key scoped to region WITHOUT tree inheritance
    print("\n" + "─" * 80)
    print("Test 1: API Key scoped to west_coast WITHOUT tree inheritance")
    print("─" * 80)

    key1_plain, key1_model = await auth.api_key_service.create_api_key(
        owner_id=str(admin.id),
        name="West Coast Key (No Tree)",
        scopes=["lead:read", "lead:create"],
        entity_id=str(west_coast.id),
        inherit_from_tree=False,
    )

    print(f"✅ Created API key: {key1_model.prefix}")
    print(f"   entity_id: {key1_model.entity_id}")
    print(f"   inherit_from_tree: {key1_model.inherit_from_tree}")
    print()

    # Test access to different entities
    test_cases_1 = [
        ("west_coast (own entity)", west_coast, True),
        ("los_angeles (child)", los_angeles, False),
        ("luxury_properties (descendant)", luxury_properties, False),
        ("seattle (child)", seattle, False),
        ("east_coast (different region)", east_coast, False),
    ]

    for entity_label, entity, expected in test_cases_1:
        has_access = await auth.api_key_service.check_entity_access_with_tree(
            key1_model, str(entity.id)
        )

        icon = "✅" if has_access == expected else "❌"
        status = "PASS" if has_access == expected else "FAIL"
        result = "ACCESS" if has_access else "DENIED"

        print(
            f"{icon} {status} | {entity_label}: {result} (expected: {'ACCESS' if expected else 'DENIED'})"
        )

    # Test Case 2: API key scoped to region WITH tree inheritance
    print("\n" + "─" * 80)
    print("Test 2: API Key scoped to west_coast WITH tree inheritance")
    print("─" * 80)

    key2_plain, key2_model = await auth.api_key_service.create_api_key(
        owner_id=str(admin.id),
        name="West Coast Key (With Tree)",
        scopes=["lead:read", "lead:create"],
        entity_id=str(west_coast.id),
        inherit_from_tree=True,
    )

    print(f"✅ Created API key: {key2_model.prefix}")
    print(f"   entity_id: {key2_model.entity_id}")
    print(f"   inherit_from_tree: {key2_model.inherit_from_tree}")
    print()

    test_cases_2 = [
        ("west_coast (own entity)", west_coast, True),
        ("los_angeles (child)", los_angeles, True),
        ("luxury_properties (descendant)", luxury_properties, True),
        ("seattle (child)", seattle, True),
        ("east_coast (different region)", east_coast, False),
    ]

    for entity_label, entity, expected in test_cases_2:
        has_access = await auth.api_key_service.check_entity_access_with_tree(
            key2_model, str(entity.id)
        )

        icon = "✅" if has_access == expected else "❌"
        status = "PASS" if has_access == expected else "FAIL"
        result = "ACCESS" if has_access else "DENIED"

        print(
            f"{icon} {status} | {entity_label}: {result} (expected: {'ACCESS' if expected else 'DENIED'})"
        )

    # Test Case 3: Global API key (no entity_id)
    print("\n" + "─" * 80)
    print("Test 3: Global API Key (no entity_id)")
    print("─" * 80)

    key3_plain, key3_model = await auth.api_key_service.create_api_key(
        owner_id=str(admin.id),
        name="Global Key",
        scopes=["lead:read"],
        entity_id=None,  # Global access
        inherit_from_tree=False,
    )

    print(f"✅ Created API key: {key3_model.prefix}")
    print(f"   entity_id: {key3_model.entity_id}")
    print(f"   inherit_from_tree: {key3_model.inherit_from_tree}")
    print()

    test_cases_3 = [
        ("west_coast", west_coast, True),
        ("los_angeles", los_angeles, True),
        ("luxury_properties", luxury_properties, True),
        ("seattle", seattle, True),
        ("east_coast", east_coast, True),
    ]

    for entity_label, entity, expected in test_cases_3:
        has_access = await auth.api_key_service.check_entity_access_with_tree(
            key3_model, str(entity.id)
        )

        icon = "✅" if has_access == expected else "❌"
        status = "PASS" if has_access == expected else "FAIL"
        result = "ACCESS" if has_access else "DENIED"

        print(
            f"{icon} {status} | {entity_label}: {result} (expected: {'ACCESS' if expected else 'DENIED'})"
        )

    # Test Case 4: Office-level key with tree inheritance
    print("\n" + "─" * 80)
    print("Test 4: API Key scoped to los_angeles WITH tree inheritance")
    print("─" * 80)

    key4_plain, key4_model = await auth.api_key_service.create_api_key(
        owner_id=str(admin.id),
        name="LA Office Key (With Tree)",
        scopes=["lead:read"],
        entity_id=str(los_angeles.id),
        inherit_from_tree=True,
    )

    print(f"✅ Created API key: {key4_model.prefix}")
    print(f"   entity_id: {key4_model.entity_id}")
    print(f"   inherit_from_tree: {key4_model.inherit_from_tree}")
    print()

    test_cases_4 = [
        ("los_angeles (own entity)", los_angeles, True),
        ("luxury_properties (child)", luxury_properties, True),
        ("west_coast (parent)", west_coast, False),
        ("seattle (sibling)", seattle, False),
        ("east_coast (different region)", east_coast, False),
    ]

    for entity_label, entity, expected in test_cases_4:
        has_access = await auth.api_key_service.check_entity_access_with_tree(
            key4_model, str(entity.id)
        )

        icon = "✅" if has_access == expected else "❌"
        status = "PASS" if has_access == expected else "FAIL"
        result = "ACCESS" if has_access else "DENIED"

        print(
            f"{icon} {status} | {entity_label}: {result} (expected: {'ACCESS' if expected else 'DENIED'})"
        )

    # Cleanup: Delete test API keys
    print("\n" + "─" * 80)
    print("Cleanup: Deleting test API keys")
    print("─" * 80)

    for key_model in [key1_model, key2_model, key3_model, key4_model]:
        await auth.api_key_service.delete_api_key(str(key_model.id))
        print(f"🗑️  Deleted API key: {key_model.prefix}")

    print("\n" + "=" * 80)
    print("ENTITY-SCOPED API KEYS TEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_entity_scoped_api_keys())
