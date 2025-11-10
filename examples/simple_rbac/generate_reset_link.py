import asyncio
import httpx
from motor.motor_asyncio import AsyncIOMotorClient
import hashlib
import os

async def generate_test_token():
    """
    Request password reset and extract the plain token from the database.
    Since we control the backend, we can reverse-engineer the token.
    
    Actually, we can't - the token is hashed. Instead, let's use the auth service
    to generate a token programmatically.
    """
    # Import the auth service
    import sys
    sys.path.insert(0, '/Users/outlabs/Documents/GitHub/outlabsAuth')
    
    from outlabs_auth.services.auth import AuthService
    from outlabs_auth.models.user import UserModel
    from outlabs_auth.config import AuthConfig
    from beanie import init_beanie
    
    mongodb_url = os.getenv("MONGODB_URL", "mongodb://localhost:27018")
    database_name = os.getenv("DATABASE_NAME", "blog_simple_rbac")
    
    client = AsyncIOMotorClient(mongodb_url)
    db = client[database_name]
    
    # Initialize Beanie
    await init_beanie(database=db, document_models=[UserModel])
    
    # Get writer user
    user = await UserModel.find_one(UserModel.email == "writer@test.com")
    
    if not user:
        print("User not found")
        return
    
    # Create auth service
    config = AuthConfig(
        secret_key="simple-rbac-secret-key-change-in-production",
        database_name=database_name
    )
    auth_service = AuthService(database=db, config=config)
    
    # Generate reset token
    plain_token = await auth_service.generate_reset_token(user)
    
    print(f"Reset link: http://localhost:3000/reset-password?token={plain_token}")
    print(f"\nToken: {plain_token}")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(generate_test_token())
