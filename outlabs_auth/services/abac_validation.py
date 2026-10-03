"""Write-time validation for stored ABAC conditions (roles and permissions).

The policy engine only understands the operators in ``ConditionOperator`` and
attribute paths rooted in a context it populates. Before 0.1.0a35 the write
paths stored any string, so a typo (``"eq"``) or an unpopulated context
(``"subject.team"``) was accepted and then either crashed evaluation or,
worse, satisfied a negative operator against a missing value. Every
condition write now goes through :func:`validate_condition_definition`.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from dateutil import parser as date_parser  # type: ignore[import-untyped]

from outlabs_auth.core.exceptions import InvalidInputError
from outlabs_auth.models.sql.enums import ConditionOperator

# Contexts the permission service actually populates when it evaluates ABAC.
ABAC_ATTRIBUTE_CONTEXTS = ("user", "resource", "env", "time")
ABAC_VALUE_TYPES = ("string", "integer", "float", "boolean", "list")

_NO_VALUE_OPERATORS = {
    ConditionOperator.EXISTS,
    ConditionOperator.NOT_EXISTS,
    ConditionOperator.IS_TRUE,
    ConditionOperator.IS_FALSE,
}
_LIST_OPERATORS = {ConditionOperator.IN, ConditionOperator.NOT_IN}
_NUMERIC_OPERATORS = {
    ConditionOperator.LESS_THAN,
    ConditionOperator.LESS_THAN_OR_EQUAL,
    ConditionOperator.GREATER_THAN,
    ConditionOperator.GREATER_THAN_OR_EQUAL,
}
_DATETIME_OPERATORS = {ConditionOperator.BEFORE, ConditionOperator.AFTER}
_ATTRIBUTE_SEGMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_\-]*$")
_TRUE_STRINGS = {"1", "true", "yes", "y", "on"}
_FALSE_STRINGS = {"0", "false", "no", "n", "off"}


def _invalid(message: str, **details: Any) -> InvalidInputError:
    return InvalidInputError(message=message, details={"reason": "invalid_abac_condition", **details})


def normalize_condition_operator(operator: Any) -> ConditionOperator:
    raw = str(getattr(operator, "value", operator) or "").strip().lower()
    try:
        return ConditionOperator(raw)
    except ValueError:
        raise _invalid(
            f"Unknown ABAC operator {operator!r}",
            field="operator",
            allowed=[item.value for item in ConditionOperator],
        ) from None


def validate_condition_attribute(attribute: Any) -> str:
    text = str(attribute or "").strip()
    parts = text.split(".")
    if len(parts) < 2 or not all(_ATTRIBUTE_SEGMENT.match(part) for part in parts):
        raise _invalid(
            "ABAC attribute must be a dotted path such as 'resource.department'",
            field="attribute",
            attribute=text,
        )
    if parts[0] not in ABAC_ATTRIBUTE_CONTEXTS:
        raise _invalid(
            f"ABAC attribute context must be one of {', '.join(ABAC_ATTRIBUTE_CONTEXTS)}",
            field="attribute",
            attribute=text,
            allowed_contexts=list(ABAC_ATTRIBUTE_CONTEXTS),
        )
    return text


def _coerce_list(value: Any) -> Optional[list[Any]]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return None
        return parsed if isinstance(parsed, list) else None
    return None


def _is_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    try:
        float(str(value))
    except (TypeError, ValueError):
        return False
    return True


def normalize_value_type(value_type: Any) -> str:
    """Canonical (lower-case, trimmed) spelling of an ABAC ``value_type`` for storage."""
    return str(value_type or "string").strip().lower()


def validate_condition_definition(
    *,
    attribute: Any,
    operator: Any,
    value: Any,
    value_type: Any,
) -> ConditionOperator:
    """Validate one condition as it will be stored; return the normalized operator.

    Raises :class:`InvalidInputError` (HTTP 400) naming the offending field.
    """
    validate_condition_attribute(attribute)
    normalized_operator = normalize_condition_operator(operator)
    normalized_value_type = str(value_type or "string").strip().lower()
    if normalized_value_type not in ABAC_VALUE_TYPES:
        raise _invalid(
            f"Unknown ABAC value_type {value_type!r}",
            field="value_type",
            allowed=list(ABAC_VALUE_TYPES),
        )

    if normalized_operator in _NO_VALUE_OPERATORS:
        return normalized_operator

    if value is None or (isinstance(value, str) and value == ""):
        raise _invalid(
            f"Operator '{normalized_operator.value}' requires a value",
            field="value",
            operator=normalized_operator.value,
        )

    if normalized_operator in _LIST_OPERATORS:
        if normalized_value_type != "list" or _coerce_list(value) is None:
            raise _invalid(
                f"Operator '{normalized_operator.value}' requires value_type 'list' and a list value",
                field="value",
                operator=normalized_operator.value,
            )
        return normalized_operator

    if normalized_value_type != "list" and isinstance(value, (list, tuple, dict)):
        raise _invalid(
            f"value_type '{normalized_value_type}' requires a scalar value",
            field="value",
        )
    if normalized_value_type == "list":
        if _coerce_list(value) is None:
            raise _invalid("value_type 'list' requires a list value", field="value")
    elif normalized_value_type == "integer":
        if isinstance(value, bool):
            raise _invalid("value_type 'integer' requires an integer value", field="value")
        if not isinstance(value, int):
            try:
                int(str(value).strip())
            except (TypeError, ValueError):
                raise _invalid("value_type 'integer' requires an integer value", field="value") from None
    elif normalized_value_type == "float":
        if not _is_number(value):
            raise _invalid("value_type 'float' requires a numeric value", field="value")
    elif normalized_value_type == "boolean":
        if not isinstance(value, bool) and str(value).strip().lower() not in _TRUE_STRINGS | _FALSE_STRINGS:
            raise _invalid("value_type 'boolean' requires true or false", field="value")

    if normalized_operator in _NUMERIC_OPERATORS and not _is_number(value):
        raise _invalid(
            f"Operator '{normalized_operator.value}' requires a numeric value",
            field="value",
            operator=normalized_operator.value,
        )

    if normalized_operator in _DATETIME_OPERATORS:
        try:
            date_parser.parse(str(value))
        except (TypeError, ValueError, OverflowError):
            raise _invalid(
                f"Operator '{normalized_operator.value}' requires an ISO 8601 datetime value",
                field="value",
                operator=normalized_operator.value,
            ) from None

    if normalized_operator == ConditionOperator.MATCHES:
        try:
            re.compile(str(value))
        except re.error as exc:
            raise _invalid(f"Invalid regular expression: {exc}", field="value") from None

    return normalized_operator


def stored_condition_value(raw_value: Any, value_type: Any) -> Any:
    """Decode a stored (serialized) condition value for re-validation on update."""
    if raw_value is None:
        return None
    if str(value_type or "string").strip().lower() == "list":
        decoded = _coerce_list(raw_value)
        return decoded if decoded is not None else raw_value
    return raw_value


def validate_condition_update(
    condition: Any,
    *,
    fields_set: set[str],
    attribute: Any = None,
    operator: Any = None,
    value: Any = None,
    value_type: Any = None,
) -> ConditionOperator:
    """Validate the state a partial condition update would produce.

    Mirrors the write semantics of the update services: a field applies only
    when present in ``fields_set`` (and, for attribute/operator/value_type,
    non-null); changing ``value_type`` re-serializes ``value``.
    """
    next_attribute = attribute if "attribute" in fields_set and attribute is not None else condition.attribute
    next_operator = operator if "operator" in fields_set and operator is not None else condition.operator
    next_value_type = value_type if "value_type" in fields_set and value_type is not None else condition.value_type
    if "value" in fields_set or "value_type" in fields_set:
        next_value = value
    else:
        next_value = stored_condition_value(condition.value, next_value_type)
    return validate_condition_definition(
        attribute=next_attribute,
        operator=next_operator,
        value=next_value,
        value_type=next_value_type,
    )
