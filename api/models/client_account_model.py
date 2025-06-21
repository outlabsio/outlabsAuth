from datetime import datetime
from typing import Optional, List
from enum import Enum
from pydantic import Field
from beanie import Link, BackLink
from pymongo import IndexModel

from .base_model import BaseDocument

class ClientAccountStatus(str, Enum):
    """
    Enum for client account status values.
    """
    ACTIVE = "active"
    SUSPENDED = "suspended"

class ClientAccountModel(BaseDocument):
    """
    Beanie Document for the 'client_accounts' collection.
    """
    name: str
    description: Optional[str] = None
    status: ClientAccountStatus = ClientAccountStatus.ACTIVE
    main_contact_user: Optional[Link["UserModel"]] = None
    data_retention_policy_days: Optional[int] = None
    
    # BackLink to get all users for this client account
    users: Optional[List[BackLink["UserModel"]]] = Field(original_field="client_account", default_factory=list)
    
    class Settings:
        name = "client_accounts"  # MongoDB collection name
        indexes = [
            IndexModel([("name", 1)], unique=True, name="client_name_unique"),  # Unique name index
        ] 