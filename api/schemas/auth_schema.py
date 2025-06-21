from pydantic import BaseModel, ConfigDict
from typing import Optional
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
    client_account_id: Optional[str] = None  # String ID for client account

class SessionResponseSchema(BaseModel):
    """
    Schema for representing a user's active session.
    """
    jti: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime
    expires_at: datetime

    model_config = ConfigDict(from_attributes=True) 