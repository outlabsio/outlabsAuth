from datetime import datetime
from pydantic import BaseModel, Field, BeforeValidator
from typing_extensions import Annotated
from bson import ObjectId

def validate_object_id(v):
    """
    Validates if a value is a valid MongoDB ObjectId.
    """
    if isinstance(v, ObjectId):
        return v
    if ObjectId.is_valid(v):
        return ObjectId(v)
    raise ValueError("Invalid ObjectId")

# Annotated type for ObjectId validation in Pydantic V2
PyObjectId = Annotated[ObjectId, BeforeValidator(validate_object_id)]

class BaseDBModel(BaseModel):
    """
    A base model for all database documents.
    It includes common fields like id, created_at, and updated_at,
    and configures Pydantic to work with MongoDB ObjectIds and aliases.
    """
    id: PyObjectId = Field(default_factory=ObjectId, alias="_id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(datetime.timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(datetime.timezone.utc))

    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}
        arbitrary_types_allowed = True

class BaseDBModelWithStringID(BaseModel):
    """
    A base model for database documents that use a string as the primary key (_id).
    """
    id: str = Field(alias="_id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(datetime.timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(datetime.timezone.utc))

    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}
        arbitrary_types_allowed = True 