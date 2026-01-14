"""
Condition Model for ABAC (Attribute-Based Access Control)

Conditions allow fine-grained access control based on resource attributes,
user attributes, and environmental context.

Examples:
    - User can only view documents where document.department == user.department
    - User can edit entities where entity.budget < 100000
    - User can approve requests during business hours only
"""
from enum import Enum
from typing import Any, Optional, Union, List
from pydantic import BaseModel, Field, field_validator


class ConditionOperator(str, Enum):
    """Operators for condition evaluation"""

    # Equality
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"

    # Comparison (numeric)
    LESS_THAN = "less_than"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    GREATER_THAN = "greater_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"

    # Collection
    IN = "in"  # attribute value is in list
    NOT_IN = "not_in"  # attribute value is not in list
    CONTAINS = "contains"  # list attribute contains value
    NOT_CONTAINS = "not_contains"  # list attribute does not contain value

    # String
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    MATCHES = "matches"  # regex match

    # Existence
    EXISTS = "exists"  # attribute exists (not None)
    NOT_EXISTS = "not_exists"  # attribute does not exist or is None

    # Boolean
    IS_TRUE = "is_true"
    IS_FALSE = "is_false"

    # Time-based
    BEFORE = "before"  # datetime comparison
    AFTER = "after"  # datetime comparison


class Condition(BaseModel):
    """
    A single ABAC condition that must be evaluated.

    Attributes:
        attribute: The attribute path to check (e.g., "resource.department", "user.role")
        operator: The comparison operator to use
        value: The value to compare against (can be None for EXISTS/NOT_EXISTS operators)
        description: Optional human-readable description of the condition

    Examples:
        Condition(
            attribute="resource.department",
            operator=ConditionOperator.EQUALS,
            value="engineering"
        )

        Condition(
            attribute="resource.budget",
            operator=ConditionOperator.LESS_THAN,
            value=100000
        )

        Condition(
            attribute="user.clearance_level",
            operator=ConditionOperator.IN,
            value=["secret", "top_secret"]
        )
    """

    attribute: str = Field(
        ...,
        description="Dot-notation path to the attribute (e.g., 'resource.department', 'user.role')"
    )
    operator: ConditionOperator = Field(
        ...,
        description="The comparison operator to use"
    )
    value: Optional[Union[str, int, float, bool, List[Any]]] = Field(
        default=None,
        description="The value to compare against (can be None for existence checks)"
    )
    description: Optional[str] = Field(
        default=None,
        description="Human-readable description of this condition"
    )

    @field_validator("attribute")
    @classmethod
    def validate_attribute(cls, v: str) -> str:
        """Validate attribute path format"""
        if not v or not v.strip():
            raise ValueError("Attribute path cannot be empty")

        # Attribute should be dot-notation path
        parts = v.split(".")
        if len(parts) < 2:
            raise ValueError(
                "Attribute path must include context (e.g., 'resource.field', 'user.field', 'env.field')"
            )

        # First part should be a valid context
        valid_contexts = {"resource", "user", "env", "time"}
        if parts[0] not in valid_contexts:
            raise ValueError(
                f"Attribute context must be one of {valid_contexts}, got '{parts[0]}'"
            )

        return v

    @field_validator("value")
    @classmethod
    def validate_value(cls, v: Optional[Union[str, int, float, bool, List[Any]]], info) -> Optional[Union[str, int, float, bool, List[Any]]]:
        """Validate value based on operator"""
        operator = info.data.get("operator")

        # Operators that don't need a value
        no_value_operators = {
            ConditionOperator.EXISTS,
            ConditionOperator.NOT_EXISTS,
            ConditionOperator.IS_TRUE,
            ConditionOperator.IS_FALSE,
        }

        if operator in no_value_operators and v is not None:
            raise ValueError(f"Operator {operator} should not have a value")

        if operator not in no_value_operators and v is None:
            raise ValueError(f"Operator {operator} requires a value")

        # Operators that require list values
        list_operators = {ConditionOperator.IN, ConditionOperator.NOT_IN}
        if operator in list_operators and not isinstance(v, list):
            raise ValueError(f"Operator {operator} requires a list value")

        return v

    class Config:
        """Pydantic configuration"""
        use_enum_values = True
        json_schema_extra = {
            "example": {
                "attribute": "resource.department",
                "operator": "equals",
                "value": "engineering",
                "description": "User can only access resources in engineering department"
            }
        }


class ConditionGroup(BaseModel):
    """
    A group of conditions with logical operators.

    Attributes:
        conditions: List of conditions to evaluate
        operator: Logical operator (AND/OR)
        description: Optional description of this condition group

    Examples:
        ConditionGroup(
            conditions=[
                Condition(attribute="resource.department", operator="equals", value="engineering"),
                Condition(attribute="resource.status", operator="equals", value="active")
            ],
            operator="AND"
        )
    """

    conditions: List[Condition] = Field(
        ...,
        min_length=1,
        description="List of conditions to evaluate"
    )
    operator: str = Field(
        default="AND",
        description="Logical operator for combining conditions (AND/OR)"
    )
    description: Optional[str] = Field(
        default=None,
        description="Human-readable description of this condition group"
    )

    @field_validator("operator")
    @classmethod
    def validate_operator(cls, v: str) -> str:
        """Validate logical operator"""
        valid_operators = {"AND", "OR"}
        v_upper = v.upper()
        if v_upper not in valid_operators:
            raise ValueError(f"Operator must be one of {valid_operators}, got '{v}'")
        return v_upper

    class Config:
        """Pydantic configuration"""
        json_schema_extra = {
            "example": {
                "conditions": [
                    {
                        "attribute": "resource.department",
                        "operator": "equals",
                        "value": "engineering"
                    },
                    {
                        "attribute": "resource.status",
                        "operator": "equals",
                        "value": "active"
                    }
                ],
                "operator": "AND",
                "description": "User can only access active engineering resources"
            }
        }
