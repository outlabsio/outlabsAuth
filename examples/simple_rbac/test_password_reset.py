import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
import os

async def test_password_reset():
    # Connect to MongoDB
    mongodb_url = os.getenv("MONGODB_URL", "mongodb://localhost:27018")
    database_name = os.getenv("DATABASE_NAME", "blog_simple_rbac")
    
    client = AsyncIOMotorClient(mongodb_url)
    db = client[database_name]
    
    # Find writer user
    user = await db.users.find_one({"email": "writer@test.com"})
    
    if user:
        print(f"✅ Found user: {user['email']}")
        print(f"   User ID: {user['_id']}")
        
        if user.get('password_reset_token'):
            print(f"✅ Reset token exists: {user['password_reset_token'][:20]}...")
            print(f"   Expires: {user.get('password_reset_expires')}")
            
            # Check if expired
            if user.get('password_reset_expires'):
                now = datetime.now(timezone.utc)
                expires = user['password_reset_expires']
                if expires > now:
                    print(f"✅ Token is valid (expires in {(expires - now).seconds} seconds)")
                else:
                    print(f"❌ Token is expired")
        else:
            print("❌ No reset token found")
    else:
        print("❌ User not found")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(test_password_reset())
