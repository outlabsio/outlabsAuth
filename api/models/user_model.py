from datetime import datetime
from typing import List, Optional
from pydantic import Field, EmailStr
from enum import Enum
from beanie import Link
from pymongo import IndexModel

from ..models.base_model import BaseDocument
from .client_account_model import ClientAccountModel

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
    roles: List[Link["RoleModel"]] = Field(default_factory=list)  # Direct role assignments
    groups: List[Link["GroupModel"]] = Field(default_factory=list)  # Group memberships
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
    
    # Platform hierarchy fields
    is_platform_staff: bool = False
    platform_scope: Optional[str] = None
    
    class Settings:
        name = "users"  # MongoDB collection name
        indexes = [
            IndexModel([("email", 1)], unique=True, name="email_unique"),  # Unique email index
            IndexModel([("client_account.id", 1)], name="client_account_index"),
            IndexModel([("is_platform_staff", 1)], name="platform_staff_index"),
            IndexModel([("roles", 1)], name="roles_index"),
        ] 

    # Pydantic v2 model configuration
    class Config:
        # Allow population by field name or alias
        populate_by_name = True
        # Validate default values
        validate_default = True 