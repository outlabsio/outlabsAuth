import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os

async def get_reset_token():
    mongodb_url = os.getenv("MONGODB_URL", "mongodb://localhost:27018")
    database_name = os.getenv("DATABASE_NAME", "blog_simple_rbac")
    
    client = AsyncIOMotorClient(mongodb_url)
    db = client[database_name]
    
    # Find writer user
    user = await db.users.find_one({"email": "writer@test.com"})
    
    if user and user.get('password_reset_token'):
        # Note: The token in the database is hashed
        # We need to generate a new one via the API to get the plain token
        print("Token is hashed in database. Need to use console output from backend.")
        print("Check the uvicorn terminal for the reset link.")
    else:
        print("No reset token found for writer@test.com")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(get_reset_token())
