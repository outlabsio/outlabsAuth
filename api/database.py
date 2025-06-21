from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from .config import settings

class Database:
    """
    Manages the MongoDB connection and provides access to the database.
    """
    client: AsyncIOMotorClient | None = None
    db: AsyncIOMotorDatabase | None = None

    async def connect(self):
        """
        Establishes the connection to the MongoDB server and selects the database.
        """
        print("Connecting to MongoDB...")
        self.client = AsyncIOMotorClient(settings.DATABASE_URL)
        self.db = self.client[settings.MONGO_DATABASE]
        try:
            # The ismaster command is cheap and does not require auth.
            await self.client.admin.command('ismaster')
            print("Successfully connected to MongoDB.")
        except Exception as e:
            print(f"Failed to connect to MongoDB: {e}")
            self.client.close()
            self.client = None
            self.db = None
            raise

    async def close(self):
        """
        Closes the connection to the MongoDB server.
        """
        if self.client:
            self.client.close()
            print("MongoDB connection closed.")
            self.client = None
            self.db = None

# Create a single instance of the Database to be used throughout the application
db = Database()

async def get_database() -> AsyncIOMotorDatabase:
    """
    A FastAPI dependency that provides a database session.
    It relies on the lifespan event handler to have the connection established.
    """
    if db.db is None:
        raise RuntimeError("Database connection has not been established.")
    return db.db 