"""
Database connection and initialization
"""
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from api.config import settings

# Import all models here
from api.models.base_model import BaseDocument
from api.models.user_model import UserModel
from api.models.entity_model import EntityModel, EntityMembershipModel
from api.models.role_model import RoleModel
from api.models.refresh_token_model import RefreshTokenModel

# Global database client
client: AsyncIOMotorClient = None


async def init_db():
    """Initialize database connection and Beanie ODM"""
    global client
    
    # Create Motor client
    client = AsyncIOMotorClient(
        settings.DATABASE_URL,
        maxPoolSize=100,
        minPoolSize=10,
        maxIdleTimeMS=30000,
    )
    
    # Initialize Beanie with all document models
    await init_beanie(
        database=client[settings.MONGO_DATABASE],
        document_models=[
            UserModel,
            EntityModel,
            EntityMembershipModel,
            RoleModel,
            RefreshTokenModel,
        ]
    )


async def close_db():
    """Close database connection"""
    global client
    if client:
        client.close()