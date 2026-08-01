"""ABAC schemas (conditions and condition groups)."""

import json
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ConditionGroupCreateRequest(BaseModel):
    operator: str = Field(default="AND", pattern="^(AND|OR)$")
    description: Optional[str] = None


class ConditionGroupUpdateRequest(BaseModel):
    operator: Optional[str] = Field(default=None, pattern="^(AND|OR)$")
    description: Optional[str] = None


class ConditionGroupResponse(BaseModel):
    id: str
    operator: str
    description: Optional[str] = None
    role_id: Optional[str] = None
    permission_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AbacConditionCreateRequest(BaseModel):
    attribute: str = Field(..., min_length=3)
    operator: str = Field(..., min_length=2, max_length=30)
    value: Optional[Any] = None
    value_type: str = Field(
        default="string", pattern="^(string|integer|float|boolean|list)$"
    )
    description: Optional[str] = None
    condition_group_id: Optional[str] = None


class AbacConditionUpdateRequest(BaseModel):
    attribute: Optional[str] = Field(default=None, min_length=3)
    operator: Optional[str] = Field(default=None, min_length=2, max_length=30)
    value: Optional[Any] = None
    value_type: Optional[str] = Field(
        default=None, pattern="^(string|integer|float|boolean|list)$"
    )
    description: Optional[str] = None
    condition_group_id: Optional[str] = None


class AbacConditionResponse(BaseModel):
    id: str
    attribute: str
    operator: str
    value: Optional[str] = None
    value_type: str
    description: Optional[str] = None
    condition_group_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


def serialize_condition_value(value: Any, value_type: str) -> Optional[str]:
    if value is None:
        return None
    vt = (value_type or "string").lower()
    if vt == "list":
        return json.dumps(value)
    return str(value)


def parse_uuid(raw: Optional[str]) -> Optional[UUID]:
    if raw is None:
        return None
    return UUID(raw)
