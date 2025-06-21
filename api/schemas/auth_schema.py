from pydantic import BaseModel
from typing import Optional
from bson import ObjectId
from datetime import datetime

class TokenSchema(BaseModel):
    """
    Schema for the JWT access token response.
    """
    access_token: str
    refresh_token: str
    token_type: str

class TokenDataSchema(BaseModel):
    """
    Schema for the data encoded within the JWT.
    """
    user_id: Optional[str] = None
    jti: Optional[str] = None # JTI of the refresh token
    client_account_id: Optional[ObjectId] = None

    class Config:
        arbitrary_types_allowed = True

class SessionResponseSchema(BaseModel):
    """
    Schema for representing a user's active session.
    """
    jti: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime
    expires_at: datetime

    class Config:
        arbitrary_types_allowed = True 