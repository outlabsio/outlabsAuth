"""
Policy Evaluation Engine for ABAC (Attribute-Based Access Control)

This engine evaluates conditions against a context to determine if access should be granted.
"""
import re
from datetime import datetime
from typing import Any, Dict, Optional, List
from dateutil import parser as date_parser

from outlabs_auth.models.sql.condition import Condition, ConditionGroup
from outlabs_auth.models.sql.enums import ConditionOperator


class PolicyEvaluationEngine:
    """
    Evaluates ABAC conditions against a context.

    The context is a dictionary containing:
    - user: User attributes (e.g., {"id": "...", "department": "engineering", "role": "manager"})
    - resource: Resource attributes (e.g., {"id": "...", "department": "engineering", "budget": 50000})
    - env: Environment attributes (e.g., {"ip": "...", "time": "...", "day_of_week": "monday"})
    - time: Current time attributes (e.g., {"hour": 14, "day_of_week": "monday", "is_business_hours": True})

    Example:
        engine = PolicyEvaluationEngine()
        context = {
            "user": {"id": "123", "department": "engineering"},
            "resource": {"id": "456", "department": "engineering", "budget": 50000}
        }

        condition = Condition(
            attribute="resource.department",
            operator=ConditionOperator.EQUALS,
            value="engineering"
        )

        result = engine.evaluate_condition(condition, context)
        # result = True
    """

    def evaluate_condition(self, condition: Condition, context: Dict[str, Any]) -> bool:
        """
        Evaluate a single condition against a context.

        Args:
            condition: The condition to evaluate
            context: Context dictionary with user, resource, env, time attributes

        Returns:
            True if condition is met, False otherwise
        """
        # Get the attribute value from context
        attribute_value = self._get_attribute_value(condition.attribute, context)

        # Handle existence checks first (don't need value comparison)
        if condition.operator == ConditionOperator.EXISTS:
            return attribute_value is not None

        if condition.operator == ConditionOperator.NOT_EXISTS:
            return attribute_value is None

        # Handle boolean checks
        if condition.operator == ConditionOperator.IS_TRUE:
            return bool(attribute_value) is True

        if condition.operator == ConditionOperator.IS_FALSE:
            return bool(attribute_value) is False

        # For all other operators, if attribute doesn't exist, condition fails
        if attribute_value is None:
            return False

        # Evaluate based on operator
        return self._evaluate_operator(
            attribute_value,
            condition.operator,
            condition.value
        )

    def evaluate_condition_group(
        self,
        condition_group: ConditionGroup,
        context: Dict[str, Any]
    ) -> bool:
        """
        Evaluate a group of conditions with AND/OR logic.

        Args:
            condition_group: Group of conditions with logical operator
            context: Context dictionary

        Returns:
            True if condition group is met, False otherwise
        """
        if not condition_group.conditions:
            return True  # Empty condition group passes

        results = [
            self.evaluate_condition(condition, context)
            for condition in condition_group.conditions
        ]

        if condition_group.operator == "AND":
            return all(results)
        elif condition_group.operator == "OR":
            return any(results)
        else:
            raise ValueError(f"Unknown logical operator: {condition_group.operator}")

    def evaluate_conditions(
        self,
        conditions: List[Condition],
        context: Dict[str, Any]
    ) -> bool:
        """
        Evaluate a list of conditions (AND logic).

        Args:
            conditions: List of conditions to evaluate
            context: Context dictionary

        Returns:
            True if all conditions are met, False otherwise
        """
        if not conditions:
            return True  # No conditions means always pass

        return all(
            self.evaluate_condition(condition, context)
            for condition in conditions
        )

    def _get_attribute_value(self, attribute_path: str, context: Dict[str, Any]) -> Any:
        """
        Get attribute value from context using dot notation.

        Args:
            attribute_path: Dot-notation path (e.g., "user.department", "resource.budget")
            context: Context dictionary

        Returns:
            Attribute value or None if not found
        """
        parts = attribute_path.split(".")
        current = context

        for part in parts:
            if not isinstance(current, dict):
                return None

            current = current.get(part)
            if current is None:
                return None

        return current

    def _evaluate_operator(
        self,
        attribute_value: Any,
        operator: ConditionOperator,
        expected_value: Any
    ) -> bool:
        """
        Evaluate a comparison operator.

        Args:
            attribute_value: The actual attribute value
            operator: The comparison operator
            expected_value: The expected value to compare against

        Returns:
            True if comparison passes, False otherwise
        """
        # Equality
        if operator == ConditionOperator.EQUALS:
            return attribute_value == expected_value

        if operator == ConditionOperator.NOT_EQUALS:
            return attribute_value != expected_value

        # Numeric comparisons
        if operator == ConditionOperator.LESS_THAN:
            return self._compare_numeric(attribute_value, expected_value, lambda a, b: a < b)

        if operator == ConditionOperator.LESS_THAN_OR_EQUAL:
            return self._compare_numeric(attribute_value, expected_value, lambda a, b: a <= b)

        if operator == ConditionOperator.GREATER_THAN:
            return self._compare_numeric(attribute_value, expected_value, lambda a, b: a > b)

        if operator == ConditionOperator.GREATER_THAN_OR_EQUAL:
            return self._compare_numeric(attribute_value, expected_value, lambda a, b: a >= b)

        # Collection operations
        if operator == ConditionOperator.IN:
            # Check if attribute_value is in the expected_value list
            return attribute_value in expected_value if isinstance(expected_value, list) else False

        if operator == ConditionOperator.NOT_IN:
            # Check if attribute_value is NOT in the expected_value list
            return attribute_value not in expected_value if isinstance(expected_value, list) else True

        if operator == ConditionOperator.CONTAINS:
            # Check if attribute_value (list) contains expected_value
            return expected_value in attribute_value if isinstance(attribute_value, (list, tuple, set)) else False

        if operator == ConditionOperator.NOT_CONTAINS:
            # Check if attribute_value (list) does NOT contain expected_value
            return expected_value not in attribute_value if isinstance(attribute_value, (list, tuple, set)) else True

        # String operations
        if operator == ConditionOperator.STARTS_WITH:
            return str(attribute_value).startswith(str(expected_value))

        if operator == ConditionOperator.ENDS_WITH:
            return str(attribute_value).endswith(str(expected_value))

        if operator == ConditionOperator.MATCHES:
            # Regex match
            try:
                pattern = re.compile(str(expected_value))
                return bool(pattern.match(str(attribute_value)))
            except re.error:
                return False

        # Time-based operations
        if operator == ConditionOperator.BEFORE:
            return self._compare_datetime(attribute_value, expected_value, lambda a, b: a < b)

        if operator == ConditionOperator.AFTER:
            return self._compare_datetime(attribute_value, expected_value, lambda a, b: a > b)

        # Unknown operator
        raise ValueError(f"Unknown operator: {operator}")

    def _compare_numeric(self, a: Any, b: Any, comparator) -> bool:
        """
        Compare two values numerically.

        Args:
            a: First value
            b: Second value
            comparator: Comparison function

        Returns:
            Result of comparison, or False if values can't be compared
        """
        try:
            # Try to convert to float for comparison
            a_numeric = float(a) if not isinstance(a, (int, float)) else a
            b_numeric = float(b) if not isinstance(b, (int, float)) else b
            return comparator(a_numeric, b_numeric)
        except (ValueError, TypeError):
            return False

    def _compare_datetime(self, a: Any, b: Any, comparator) -> bool:
        """
        Compare two values as datetimes.

        Args:
            a: First value (datetime or string)
            b: Second value (datetime or string)
            comparator: Comparison function

        Returns:
            Result of comparison, or False if values can't be compared
        """
        try:
            # Convert to datetime if needed
            a_dt = a if isinstance(a, datetime) else date_parser.parse(str(a))
            b_dt = b if isinstance(b, datetime) else date_parser.parse(str(b))
            return comparator(a_dt, b_dt)
        except (ValueError, TypeError):
            return False

    def create_context(
        self,
        user: Optional[Dict[str, Any]] = None,
        resource: Optional[Dict[str, Any]] = None,
        env: Optional[Dict[str, Any]] = None,
        time_attrs: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a context dictionary for evaluation.

        Args:
            user: User attributes
            resource: Resource attributes
            env: Environment attributes
            time_attrs: Time-based attributes

        Returns:
            Context dictionary
        """
        context = {}

        if user is not None:
            context["user"] = user

        if resource is not None:
            context["resource"] = resource

        if env is not None:
            context["env"] = env

        # Add time attributes (auto-generate if not provided)
        if time_attrs is None:
            now = datetime.now()
            time_attrs = {
                "hour": now.hour,
                "minute": now.minute,
                "day_of_week": now.strftime("%A").lower(),
                "day_of_month": now.day,
                "month": now.month,
                "year": now.year,
                "is_business_hours": 9 <= now.hour < 17,
                "is_weekend": now.weekday() >= 5,
                "timestamp": now.isoformat()
            }
        context["time"] = time_attrs

        return context

    def add_user_context(
        self,
        context: Dict[str, Any],
        user_id: str,
        user_attributes: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Add user attributes to context.

        Args:
            context: Existing context
            user_id: User ID
            user_attributes: Additional user attributes

        Returns:
            Updated context
        """
        context["user"] = {
            "id": user_id,
            **user_attributes
        }
        return context

    def add_resource_context(
        self,
        context: Dict[str, Any],
        resource_id: str,
        resource_type: str,
        resource_attributes: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Add resource attributes to context.

        Args:
            context: Existing context
            resource_id: Resource ID
            resource_type: Resource type (e.g., "entity", "document")
            resource_attributes: Additional resource attributes

        Returns:
            Updated context
        """
        context["resource"] = {
            "id": resource_id,
            "type": resource_type,
            **resource_attributes
        }
        return context
