from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime

from ..models.client_account_model import ClientAccountStatus

class ClientAccountCreateSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)  # Require non-empty name
    description: Optional[str] = None
    main_contact_user_id: Optional[str] = None

    model_config = ConfigDict(
        arbitrary_types_allowed=True
    )

class ClientAccountUpdateSchema(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)  # If provided, require non-empty name
    description: Optional[str] = None
    status: Optional[ClientAccountStatus] = None
    main_contact_user_id: Optional[str] = None
    data_retention_policy_days: Optional[int] = None

    model_config = ConfigDict(
        arbitrary_types_allowed=True
    )

class ClientAccountResponseSchema(BaseModel):
    id: str = Field(..., alias="_id")
    name: str
    description: Optional[str] = None
    status: ClientAccountStatus
    main_contact_user_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    ) 