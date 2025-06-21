from datetime import datetime
from typing import Optional
from enum import Enum
from pydantic import Field

from .base_model import BaseDBModel, PyObjectId

class ClientAccountStatus(str, Enum):
    """
    Enum for client account status values.
    """
    ACTIVE = "active"
    SUSPENDED = "suspended"

class ClientAccountModel(BaseDBModel):
    """
    Pydantic model for the 'client_accounts' collection.
    """
    name: str = Field(..., index=True)
    description: Optional[str] = None
    status: ClientAccountStatus = ClientAccountStatus.ACTIVE
    main_contact_user_id: Optional[PyObjectId] = None
    data_retention_policy_days: Optional[int] = None

    # Collection metadata - handled by services layer 