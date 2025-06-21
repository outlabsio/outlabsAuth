from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from .config import settings

# Import all document models for Beanie initialization
from .models.user_model import UserModel
from .models.role_model import RoleModel
from .models.permission_model import PermissionModel
from .models.client_account_model import ClientAccountModel
from .models.refresh_token_model import RefreshTokenModel
from .models.password_reset_token_model import PasswordResetTokenModel

class Database:
    """
    Manages the MongoDB connection and Beanie ODM initialization.
    """
    client: AsyncIOMotorClient | None = None

    async def connect(self):
        """
        Establishes the connection to MongoDB and initializes Beanie ODM.
        """
        print("Connecting to MongoDB...")
        self.client = AsyncIOMotorClient(settings.DATABASE_URL)
        
        try:
            # Test the connection
            await self.client.admin.command('ismaster')
            print("Successfully connected to MongoDB.")
            
            # Initialize Beanie with all document models
            await init_beanie(
                database=self.client[settings.MONGO_DATABASE],
                document_models=[
                    UserModel,
                    RoleModel,
                    PermissionModel,
                    ClientAccountModel,
                    RefreshTokenModel,
                    PasswordResetTokenModel,
                ]
            )
            print("Beanie ODM initialized successfully.")
            
            # Rebuild models to resolve circular references with proper namespace
            namespace = {
                'UserModel': UserModel,
                'ClientAccountModel': ClientAccountModel,
                'RefreshTokenModel': RefreshTokenModel,
            }
            UserModel.model_rebuild(_types_namespace=namespace)
            ClientAccountModel.model_rebuild(_types_namespace=namespace)
            RefreshTokenModel.model_rebuild(_types_namespace=namespace)
            print("Model circular references resolved.")
            
            # Beanie handles all indexes automatically through model definitions
            print("Database initialization complete.")
            
        except Exception as e:
            print(f"Failed to connect to MongoDB: {e}")
            if self.client:
                self.client.close()
                self.client = None
            raise



    async def close(self):
        """
        Closes the connection to the MongoDB server.
        """
        if self.client:
            self.client.close()
            print("MongoDB connection closed.")
            self.client = None

# Create a single instance of the Database to be used throughout the application
db = Database()

async def get_database():
    """
    A FastAPI dependency that ensures the database is connected.
    Note: With Beanie, you typically don't need to inject the database directly.
    """
    if db.client is None:
        raise RuntimeError("Database connection has not been established.")
    return db.client[settings.MONGO_DATABASE] 