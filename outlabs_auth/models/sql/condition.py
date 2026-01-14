"""
ABAC Condition Models (Pydantic - stored as JSONB)

These are NOT database tables - they are Pydantic models that get
serialized to JSONB columns in Role and Permission tables.
"""

from typing import Any, List, Optional, Union
from pydantic import BaseModel, Field, field_validator

from .enums import ConditionOperator


class Condition(BaseModel):
    """
    Single ABAC condition for fine-grained access control.

    Stored as JSONB within Role/Permission documents.

    Attributes:
        attribute: Dot-notation path to the value (e.g., "resource.department")
        operator: Comparison operator
        value: Value to compare against
        description: Human-readable description

    Example:
        >>> condition = Condition(
        ...     attribute="resource.department",
        ...     operator=ConditionOperator.EQUALS,
        ...     value="engineering"
        ... )
    """

    attribute: str = Field(
        ...,
        description="Dot-notation path (e.g., 'resource.department', 'user.role')",
        min_length=3,
    )
    operator: ConditionOperator = Field(
        ...,
        description="Comparison operator",
    )
    value: Optional[Union[str, int, float, bool, List[Any]]] = Field(
        default=None,
        description="Value to compare against (not needed for EXISTS/IS_TRUE/etc.)",
    )
    description: Optional[str] = Field(
        default=None,
        description="Human-readable description of this condition",
    )

    @field_validator("attribute")
    @classmethod
    def validate_attribute(cls, v: str) -> str:
        """Validate attribute path format."""
        if not v or not v.strip():
            raise ValueError("Attribute path cannot be empty")

        parts = v.split(".")
        if len(parts) < 2:
            raise ValueError(
                "Attribute path must include context (e.g., 'resource.field', 'user.role')"
            )

        valid_contexts = {"resource", "user", "env", "time", "request"}
        if parts[0] not in valid_contexts:
            raise ValueError(
                f"Attribute context must be one of {valid_contexts}, got '{parts[0]}'"
            )

        return v

    @field_validator("value")
    @classmethod
    def validate_value(cls, v, info):
        """Validate value based on operator."""
        # Get operator from the data being validated
        operator = info.data.get("operator")

        # Operators that don't need a value
        no_value_operators = {
            ConditionOperator.EXISTS,
            ConditionOperator.NOT_EXISTS,
            ConditionOperator.IS_TRUE,
            ConditionOperator.IS_FALSE,
        }

        if operator in no_value_operators:
            return None  # Value not needed

        # Operators that require a list value
        list_operators = {
            ConditionOperator.IN,
            ConditionOperator.NOT_IN,
        }

        if operator in list_operators and v is not None and not isinstance(v, list):
            raise ValueError(f"Operator '{operator}' requires a list value")

        return v

    model_config = {
        "use_enum_values": True,
        "json_schema_extra": {
            "examples": [
                {
                    "attribute": "resource.department",
                    "operator": "equals",
                    "value": "engineering",
                    "description": "Only for engineering department"
                },
                {
                    "attribute": "resource.budget",
                    "operator": "less_than",
                    "value": 100000,
                    "description": "Budget under $100k"
                },
            ]
        }
    }


class ConditionGroup(BaseModel):
    """
    Group of conditions with AND/OR logic.

    Stored as JSONB within Role/Permission documents.
    Allows for complex permission rules like:
    "user is in engineering AND resource budget < 100k"

    Attributes:
        conditions: List of conditions to evaluate
        operator: AND or OR logic
        description: Human-readable description

    Example:
        >>> group = ConditionGroup(
        ...     conditions=[
        ...         Condition(attribute="resource.department", operator="equals", value="eng"),
        ...         Condition(attribute="resource.status", operator="equals", value="active"),
        ...     ],
        ...     operator="AND"
        ... )
    """

    conditions: List[Condition] = Field(
        ...,
        min_length=1,
        description="List of conditions to evaluate",
    )
    operator: str = Field(
        default="AND",
        description="Logical operator: AND or OR",
    )
    description: Optional[str] = Field(
        default=None,
        description="Human-readable description of this condition group",
    )

    @field_validator("operator")
    @classmethod
    def validate_operator(cls, v: str) -> str:
        """Validate logical operator."""
        v_upper = v.upper()
        if v_upper not in {"AND", "OR"}:
            raise ValueError("Operator must be 'AND' or 'OR'")
        return v_upper

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "conditions": [
                        {"attribute": "resource.department", "operator": "equals", "value": "engineering"},
                        {"attribute": "resource.status", "operator": "equals", "value": "active"},
                    ],
                    "operator": "AND",
                    "description": "Active engineering resources only"
                }
            ]
        }
    }
