import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def create_user():
    client = AsyncIOMotorClient("mongodb://localhost:27018")
    db = client["blog_simple_rbac"]
    
    # Hash the password
    hashed_password = pwd_context.hash("Asd123$$")
    
    # Check if user exists
    existing = await db.users.find_one({"email": "test@example.com"})
    if existing:
        print("User already exists, deleting...")
        await db.users.delete_one({"email": "test@example.com"})
        await db.user_role_memberships.delete_many({"user_id": existing["_id"]})
    
    # Create user
    from bson import ObjectId
    from datetime import datetime, UTC
    
    user_id = ObjectId()
    user = {
        "_id": user_id,
        "email": "test@example.com",
        "hashed_password": hashed_password,
        "first_name": "Test",
        "last_name": "User",
        "is_superuser": True,
        "is_active": True,
        "status": "active",
        "can_login": True,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC)
    }
    
    await db.users.insert_one(user)
    print(f"✅ Created user: test@example.com with password: Asd123$$")
    print(f"   User ID: {user_id}")

asyncio.run(create_user())
