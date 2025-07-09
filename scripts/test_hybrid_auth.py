#!/usr/bin/env python3
"""
Test script for the hybrid authorization model
Demonstrates RBAC + ABAC conditional permissions
"""
import asyncio
import json
from datetime import datetime
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from api.models import UserModel, PermissionModel, RoleModel, EntityModel
from api.models.permission_model import Condition
from api.services.permission_service import permission_service
from api.config import settings


async def create_test_permission():
    """Create a test conditional permission for invoice approval"""
    
    # Create invoice:approve permission with conditions
    permission = PermissionModel(
        name="invoice:approve",
        display_name="Approve Invoices",
        description="Allows approving invoices with value-based restrictions",
        is_system=False,
        is_active=True,
        tags=["finance", "accounting"],
        conditions=[
            Condition(
                attribute="resource.value",
                operator="LESS_THAN_OR_EQUAL",
                value=50000
            ),
            Condition(
                attribute="resource.status",
                operator="EQUALS",
                value="pending_approval"
            ),
            Condition(
                attribute="resource.department",
                operator="IN",
                value=["finance", "accounting", "operations"]
            )
        ]
    )
    
    # Check if already exists
    existing = await PermissionModel.find_one(PermissionModel.name == "invoice:approve")
    if existing:
        print(f"Permission already exists: {existing.name}")
        return existing
    
    await permission.save()
    print(f"Created conditional permission: {permission.name}")
    print(f"Conditions: {len(permission.conditions)}")
    for i, condition in enumerate(permission.conditions, 1):
        print(f"  {i}. {condition.attribute} {condition.operator} {condition.value}")
    
    return permission


async def test_permission_evaluation():
    """Test the permission evaluation with different scenarios"""
    
    # Get a test user (assuming system user exists)
    user = await UserModel.find_one(UserModel.email == "system@outlabs.com")
    if not user:
        print("Test user not found. Please run seed script first.")
        return
    
    print(f"\nTesting permission evaluation for user: {user.email}")
    
    # Test scenarios
    test_cases = [
        {
            "name": "Valid invoice under limit",
            "resource_attributes": {
                "value": 25000,
                "status": "pending_approval",
                "department": "finance",
                "invoice_id": "INV-001"
            },
            "expected": True
        },
        {
            "name": "Invoice over limit",
            "resource_attributes": {
                "value": 75000,
                "status": "pending_approval",
                "department": "finance",
                "invoice_id": "INV-002"
            },
            "expected": False
        },
        {
            "name": "Wrong status",
            "resource_attributes": {
                "value": 25000,
                "status": "approved",
                "department": "finance",
                "invoice_id": "INV-003"
            },
            "expected": False
        },
        {
            "name": "Wrong department",
            "resource_attributes": {
                "value": 25000,
                "status": "pending_approval",
                "department": "marketing",
                "invoice_id": "INV-004"
            },
            "expected": False
        }
    ]
    
    for test_case in test_cases:
        print(f"\n--- Test Case: {test_case['name']} ---")
        print(f"Resource attributes: {json.dumps(test_case['resource_attributes'], indent=2)}")
        
        # Check permission
        result = await permission_service.check_permission_with_context(
            user_id=str(user.id),
            permission="invoice:approve",
            entity_id=None,
            resource_attributes=test_case["resource_attributes"],
            use_cache=False  # Disable cache for testing
        )
        
        print(f"Result: {'✅ ALLOWED' if result.allowed else '❌ DENIED'}")
        print(f"Reason: {result.reason}")
        
        if result.details.get("evaluations"):
            print("Condition evaluations:")
            for eval in result.details["evaluations"]:
                status = "✓" if eval["passed"] else "✗"
                print(f"  {status} {eval['attribute']} {eval['operator']} {eval['expected']} (actual: {eval['actual']})")
        
        # Verify expectation
        if result.allowed == test_case["expected"]:
            print(f"✅ Test passed (expected: {test_case['expected']})")
        else:
            print(f"❌ Test failed (expected: {test_case['expected']}, got: {result.allowed})")


async def main():
    """Main test function"""
    print("Hybrid Authorization Model Test")
    print("=" * 50)
    
    # Initialize database
    print("Connecting to database...")
    client = AsyncIOMotorClient(settings.DATABASE_URL)
    db = client[settings.MONGO_DATABASE]
    
    # Initialize Beanie
    await init_beanie(
        database=db,
        document_models=[
            UserModel,
            PermissionModel,
            RoleModel,
            EntityModel
        ]
    )
    
    print("Database connected.")
    
    # Create test permission
    await create_test_permission()
    
    # Run tests
    await test_permission_evaluation()
    
    print("\n" + "=" * 50)
    print("Test completed!")


if __name__ == "__main__":
    asyncio.run(main())