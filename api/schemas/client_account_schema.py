from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, field_serializer
from datetime import datetime
from beanie import PydanticObjectId

from ..models.client_account_model import ClientAccountStatus

class ClientAccountCreateSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)  # Require non-empty name
    description: Optional[str] = None
    main_contact_user_id: Optional[str] = None  # String ID for user

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )

class ClientAccountUpdateSchema(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)  # If provided, require non-empty name
    description: Optional[str] = None
    status: Optional[ClientAccountStatus] = None
    main_contact_user_id: Optional[str] = None  # String ID for user
    data_retention_policy_days: Optional[int] = None

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )

class ClientAccountResponseSchema(BaseModel):
    id: PydanticObjectId = Field(..., alias="_id")
    name: str
    description: Optional[str] = None
    status: ClientAccountStatus
    main_contact_user_id: Optional[str] = None  # Will be populated from Link
    data_retention_policy_days: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    @field_serializer('id')
    def serialize_id(self, value: PydanticObjectId) -> str:
        return str(value)

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        str_strip_whitespace=True,
        json_encoders={
            datetime: lambda v: v.isoformat()
        }
    ) 