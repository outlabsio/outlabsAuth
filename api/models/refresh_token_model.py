from datetime import datetime, timezone
from typing import Optional
from pydantic import Field

from .base_model import BaseDBModel, PyObjectId

class RefreshTokenModel(BaseDBModel):
    """
    Pydantic model for refresh tokens stored in the database.
    """
    user_id: PyObjectId
    jti: str
    expires_at: datetime
    is_revoked: bool = False
    
    # Optional device info
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    # Collection metadata - handled by services layer 