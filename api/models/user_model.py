from datetime import datetime
from typing import List, Optional
from pydantic import Field, EmailStr
from enum import Enum
from beanie import Link
from pymongo import IndexModel

from ..models.base_model import BaseDocument

class UserStatus(str, Enum):
    """
    Enum for user status values.
    """
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    SUSPENDED = "suspended"

class UserModel(BaseDocument):
    """
    Beanie Document for the 'users' collection in MongoDB.
    """
    email: EmailStr
    password_hash: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    client_account: Optional[Link["ClientAccountModel"]] = None
    roles: List[str] = Field(default_factory=list)
    is_main_client: bool = False
    status: UserStatus = Field(UserStatus.PENDING)
    last_login_at: Optional[datetime] = None
    locale: Optional[str] = "en-US"
    metadata: Optional[dict] = None
    mfa_enabled: bool = False
    mfa_secret: Optional[str] = None
    recovery_codes: Optional[List[str]] = None
    failed_login_attempts: int = 0
    lockout_until: Optional[datetime] = None
    
    class Settings:
        name = "users"  # MongoDB collection name
        indexes = [
            IndexModel([("email", 1)], unique=True, name="email_unique"),  # Unique email index
        ] 