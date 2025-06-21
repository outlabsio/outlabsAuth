from datetime import datetime
from typing import List, Optional
from pydantic import Field, EmailStr
from enum import Enum

from ..models.base_model import BaseDBModel, PyObjectId

class UserStatus(str, Enum):
    """
    Enum for user status values.
    """
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    SUSPENDED = "suspended"

class UserModel(BaseDBModel):
    """
    Pydantic model for the 'users' collection in MongoDB.
    """
    email: EmailStr = Field(..., index=True, unique=True)
    password_hash: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    client_account_id: Optional[PyObjectId] = Field(None, index=True)
    roles: List[str] = Field(default_factory=list, index=True)
    is_main_client: bool = False
    status: UserStatus = Field(UserStatus.PENDING, index=True)
    last_login_at: Optional[datetime] = None
    locale: Optional[str] = "en-US"
    metadata: Optional[dict] = None
    mfa_enabled: bool = False
    mfa_secret: Optional[str] = None
    recovery_codes: Optional[List[str]] = None
    failed_login_attempts: int = 0
    lockout_until: Optional[datetime] = None 