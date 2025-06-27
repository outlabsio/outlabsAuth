from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any
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

class EnrichedTokenUserSchema(BaseModel):
    """
    Schema for user data within enriched JWT token.
    """
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    status: str
    is_platform_staff: bool = False
    platform_scope: Optional[str] = None

class EnrichedTokenRoleSchema(BaseModel):
    """
    Schema for role data within enriched JWT token.
    """
    id: str
    name: str
    scope: str
    scope_id: Optional[str] = None

class EnrichedTokenSessionSchema(BaseModel):
    """
    Schema for session metadata within enriched JWT token.
    """
    is_main_client: bool = False
    mfa_enabled: bool = False
    locale: str = "en-US"

class EnrichedTokenDataSchema(BaseModel):
    """
    Schema for enriched JWT token payload with user permissions and role information.
    This is now the standard token format that includes all data needed by frontend.
    """
    # Standard JWT claims
    sub: str  # user_id
    client_account_id: Optional[str] = None
    jti: Optional[str] = None
    exp: int  # expiration timestamp
    iat: int  # issued at timestamp
    
    # User information
    user: EnrichedTokenUserSchema
    
    # Authorization data
    roles: List[EnrichedTokenRoleSchema]
    permissions: List[str]  # Permission names for quick access
    scopes: List[str]       # Available scopes
    
    # Session metadata
    session: EnrichedTokenSessionSchema
    
    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )

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