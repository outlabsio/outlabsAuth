from datetime import datetime
from typing import Optional, Any, Dict
from bson import ObjectId
from pydantic import BaseModel, Field, ConfigDict, BeforeValidator
from typing_extensions import Annotated

def validate_object_id(v: Any) -> ObjectId:
    """Validate and convert input to ObjectId"""
    if isinstance(v, ObjectId):
        return v
    if isinstance(v, str):
        try:
            return ObjectId(v)
        except Exception:
            raise ValueError(f"Invalid ObjectId: {v}")
    raise ValueError(f"Invalid ObjectId type: {type(v)}")

# Simple ObjectId type for internal models
PyObjectId = Annotated[ObjectId, BeforeValidator(validate_object_id)]

class BaseDBModel(BaseModel):
    """
    Base Pydantic v2 model for MongoDB documents.
    Handles ObjectId serialization, timestamps, and common configurations.
    """
    
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = ConfigDict(
        # Core Pydantic v2 configuration
        populate_by_name=True,
        arbitrary_types_allowed=True,
        str_strip_whitespace=True,
        validate_assignment=True,
        use_enum_values=True,
        
        # MongoDB integration
        from_attributes=True,
        
        # JSON serialization
        json_encoders={
            ObjectId: str,
            datetime: lambda v: v.isoformat(),
        }
    )
    
    def model_dump_json_safe(self) -> Dict[str, Any]:
        """
        Safe model dump that handles ObjectId conversion for JSON serialization.
        """
        data = self.model_dump(by_alias=True, exclude_unset=True)
        
        # Convert ObjectId fields to strings
        for key, value in data.items():
            if isinstance(value, ObjectId):
                data[key] = str(value)
        
        return data
    
    # ObjectId validation and serialization is handled by the PyObjectId type annotation

class BaseDBModelWithStringID(BaseModel):
    """
    A base model for database documents that use a string as the primary key (_id).
    """
    id: str = Field(alias="_id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True
    ) 