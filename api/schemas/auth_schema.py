from pydantic import BaseModel

class TokenSchema(BaseModel):
    """
    Schema for the JWT access token response.
    """
    access_token: str
    token_type: str

class TokenDataSchema(BaseModel):
    """
    Schema for the data encoded within the JWT.
    """
    user_id: str | None = None 