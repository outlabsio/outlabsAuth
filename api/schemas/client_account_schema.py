from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict, field_serializer, computed_field
from datetime import datetime
from beanie import PydanticObjectId

from ..models.client_account_model import ClientAccountStatus

class ClientAccountCreateSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)  # Require non-empty name
    description: Optional[str] = None
    main_contact_user_id: Optional[str] = None  # String ID for user
    
    # Hierarchical Multi-Platform Tenancy fields
    platform_id: Optional[str] = None          # Platform this client belongs to
    created_by_client_id: Optional[str] = None # Parent client creating this account
    is_platform_root: bool = False             # Whether this client can create sub-clients
    platform_url: Optional[str] = Field(None, pattern="^https?://.*", description="Platform URL (only for platform root accounts)")

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
    
    # Hierarchical Multi-Platform Tenancy fields
    platform_id: Optional[str] = None
    is_platform_root: Optional[bool] = None
    platform_url: Optional[str] = Field(None, pattern="^https?://.*", description="Platform URL (only for platform root accounts)")
    
    # Note: created_by_client_id is not updatable for security reasons
    # Note: child clients found via reverse queries, not stored as array

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
    
    # Hierarchical Multi-Platform Tenancy fields
    platform_id: Optional[str] = None
    created_by_client_id: Optional[str] = None
    is_platform_root: bool = False
    platform_url: Optional[str] = None
    # Note: child_clients removed for scalability - use /my-sub-clients endpoint instead
    
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def created_by_platform(self) -> bool:
        """Indicates if this client was created by a platform (has a parent client)."""
        return self.created_by_client_id is not None

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