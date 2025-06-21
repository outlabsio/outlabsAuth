from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime

from ..models.base_model import PyObjectId
from ..models.client_account_model import ClientAccountStatus

class ClientAccountCreateSchema(BaseModel):
    name: str
    description: Optional[str] = None
    main_contact_user_id: Optional[PyObjectId] = None

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {PyObjectId: str}

class ClientAccountUpdateSchema(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[ClientAccountStatus] = None
    main_contact_user_id: Optional[PyObjectId] = None
    data_retention_policy_days: Optional[int] = None

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {PyObjectId: str}

class ClientAccountResponseSchema(BaseModel):
    id: PyObjectId = Field(..., alias="_id")
    name: str
    description: Optional[str] = None
    status: ClientAccountStatus
    main_contact_user_id: Optional[PyObjectId] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True
        json_encoders = {PyObjectId: str}
        arbitrary_types_allowed = True 