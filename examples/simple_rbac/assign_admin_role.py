import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime, UTC

async def assign_admin():
    client = AsyncIOMotorClient("mongodb://localhost:27018")
    db = client["blog_simple_rbac"]
    
    # Find test user
    user = await db.users.find_one({"email": "test@example.com"})
    if not user:
        print("❌ Test user not found")
        return
    
    # Find admin role
    admin_role = await db.roles.find_one({"name": "admin"})
    if not admin_role:
        print("❌ Admin role not found")
        return
    
    # Check if membership already exists
    existing = await db.user_role_memberships.find_one({
        "user_id": user["_id"],
        "role_id": admin_role["_id"]
    })
    
    if existing:
        print("✅ User already has admin role")
        return
    
    # Create membership
    membership = {
        "_id": ObjectId(),
        "user_id": user["_id"],
        "role_id": admin_role["_id"],
        "status": "active",
        "can_grant": True,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC)
    }
    
    await db.user_role_memberships.insert_one(membership)
    print(f"✅ Assigned admin role to test@example.com")

asyncio.run(assign_admin())
