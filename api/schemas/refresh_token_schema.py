from pydantic import BaseModel

class RefreshTokenCreateSchema(BaseModel):
    """
    Schema used when creating a refresh token record in the database.
    This is for internal use and not exposed via an API endpoint.
    """
    jti: str
    user_id: str  # Will be used to create Link to UserModel
    expires_at: int # Store as timestamp

class RefreshTokenUpdateSchema(BaseModel):
    """
    Schema used for updating a refresh token, e.g., to revoke it.
    """
    is_revoked: bool 