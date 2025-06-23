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
    Enhanced for Hierarchical Multi-Platform Tenancy.
    """
    name: str
    description: Optional[str] = None
    status: ClientAccountStatus = ClientAccountStatus.ACTIVE
    main_contact_user: Optional[Link["UserModel"]] = None
    data_retention_policy_days: Optional[int] = None
    
    # Hierarchical Multi-Platform Tenancy fields
    platform_id: Optional[str] = None          # Which platform owns this client
    created_by_client_id: Optional[str] = None # Parent client relationship  
    is_platform_root: bool = False             # Can create sub-clients
    
    # Removed child_clients array for scalability - use reverse queries instead
    # To get children: ClientAccountModel.find(ClientAccountModel.created_by_client_id == parent_id)
    
    # BackLink to get all users for this client account
    users: Optional[List[BackLink["UserModel"]]] = Field(original_field="client_account", default_factory=list)
    
    class Settings:
        name = "client_accounts"  # MongoDB collection name
        indexes = [
            IndexModel([("name", 1)], unique=True, name="client_name_unique"),  # Unique name index
            IndexModel([("platform_id", 1)], name="platform_id_index"),  # Platform lookup optimization
            IndexModel([("created_by_client_id", 1)], name="created_by_client_index"),  # Parent-child queries - CRITICAL for performance
            IndexModel([("is_platform_root", 1)], name="platform_root_index"),  # Platform root lookups
        ] 