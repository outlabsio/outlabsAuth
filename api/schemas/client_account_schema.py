from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime

from ..models.client_account_model import ClientAccountStatus
from ..models.base_model import PyObjectId

class ClientAccountCreateSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)  # Require non-empty name
    description: Optional[str] = None
    main_contact_user_id: Optional[PyObjectId] = None

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        str_strip_whitespace=True,
        validate_assignment=True
    )

class ClientAccountUpdateSchema(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)  # If provided, require non-empty name
    description: Optional[str] = None
    status: Optional[ClientAccountStatus] = None
    main_contact_user_id: Optional[PyObjectId] = None
    data_retention_policy_days: Optional[int] = None

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        str_strip_whitespace=True,
        validate_assignment=True
    )

class ClientAccountResponseSchema(BaseModel):
    id: PyObjectId = Field(..., alias="_id")
    name: str
    description: Optional[str] = None
    status: ClientAccountStatus
    main_contact_user_id: Optional[PyObjectId] = None
    data_retention_policy_days: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        arbitrary_types_allowed=True,
        str_strip_whitespace=True,
        json_encoders={
            datetime: lambda v: v.isoformat()
        }
    ) 