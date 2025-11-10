"""
Simple test to check if APIKeyModel can be created
"""

import asyncio
import os

from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from outlabs_auth.models.api_key import APIKeyModel, APIKeyStatus
from outlabs_auth.models.user import UserModel

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27018")
DATABASE_NAME = os.getenv("DATABASE_NAME", "realestate_enterprise_rbac")


async def test():
    client = AsyncIOMotorClient(MONGODB_URL)
    db = client[DATABASE_NAME]

    # Initialize Beanie with minimal models
    await init_beanie(database=db, document_models=[UserModel, APIKeyModel])

    # Get a user
    user = await UserModel.find_one(UserModel.email == "admin@diverse.com")

    print(f"User found: {user.email}")

    # Try to create API key
    full_key, prefix = APIKeyModel.generate_key("sk_test")
    key_hash = APIKeyModel.hash_key(full_key)

    api_key = APIKeyModel(
        name="Test Key",
        prefix=prefix,
        key_hash=key_hash,
        owner=user,
        status=APIKeyStatus.ACTIVE,
        scopes=["test:read"],
        entity_id="test123",
        inherit_from_tree=True,
    )

    print("Saving API key...")
    await api_key.save()
    print(f"✅ API key created: {api_key.prefix}")

    # Cleanup
    await api_key.delete()
    print("✅ Test passed!")


if __name__ == "__main__":
    asyncio.run(test())
