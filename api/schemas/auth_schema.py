from pydantic import BaseModel
from typing import Optional

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