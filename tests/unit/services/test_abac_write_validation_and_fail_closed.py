"""ABAC write validation and fail-closed evaluation (0.1.0a35).

Writes must reject conditions the engine cannot honor (unknown operators,
unpopulated attribute contexts, values that do not match their operator or
value_type); evaluation must never let malformed or missing data satisfy a
condition.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from outlabs_auth.core.exceptions import InvalidInputError
from outlabs_auth.models.sql.condition import Condition
from outlabs_auth.models.sql.enums import ConditionOperator
from outlabs_auth.services.abac_validation import (
    validate_condition_definition,
    validate_condition_update,
)
from outlabs_auth.services.policy_engine import PolicyEvaluationEngine


def _valid(**overrides):
    payload = {
        "attribute": "resource.department",
        "operator": "equals",
        "value": "finance",
        "value_type": "string",
    }
    payload.update(overrides)
    return validate_condition_definition(**payload)


@pytest.mark.unit
@pytest.mark.parametrize(
    "overrides, field",
    [
        ({"operator": "eq"}, "operator"),
        ({"operator": "drop table"}, "operator"),
        ({"attribute": "context.department"}, "attribute"),
        ({"attribute": "request.ip"}, "attribute"),
        ({"attribute": "department"}, "attribute"),
        ({"attribute": "resource..department"}, "attribute"),
        ({"value_type": "datetime"}, "value_type"),
        ({"value": None}, "value"),
        ({"operator": "in", "value": "finance"}, "value"),
        ({"operator": "not_in", "value": ["finance"], "value_type": "string"}, "value"),
        ({"operator": "greater_than", "value": "lots", "value_type": "string"}, "value"),
        ({"operator": "before", "value": "not-a-date"}, "value"),
        ({"operator": "matches", "value": "(unclosed"}, "value"),
        ({"value": "abc", "value_type": "integer"}, "value"),
        ({"value": True, "value_type": "integer"}, "value"),
        ({"value": "maybe", "value_type": "boolean"}, "value"),
        ({"value": ["a"], "value_type": "string"}, "value"),
    ],
)
def test_invalid_condition_definitions_are_rejected(overrides, field):
    with pytest.raises(InvalidInputError) as exc_info:
        _valid(**overrides)
    assert exc_info.value.details["reason"] == "invalid_abac_condition"
    assert exc_info.value.details["field"] == field


@pytest.mark.unit
@pytest.mark.parametrize(
    "overrides, expected",
    [
        ({}, ConditionOperator.EQUALS),
        ({"operator": "EQUALS"}, ConditionOperator.EQUALS),
        ({"operator": "exists", "value": None}, ConditionOperator.EXISTS),
        ({"operator": "is_false", "value": None, "value_type": "boolean"}, ConditionOperator.IS_FALSE),
        ({"operator": "in", "value": ["finance", "ops"], "value_type": "list"}, ConditionOperator.IN),
        ({"operator": "not_in", "value": '["finance"]', "value_type": "list"}, ConditionOperator.NOT_IN),
        ({"operator": "greater_than", "value": 10, "value_type": "integer"}, ConditionOperator.GREATER_THAN),
        ({"operator": "less_than", "value": "2.5", "value_type": "float"}, ConditionOperator.LESS_THAN),
        ({"operator": "before", "value": "2026-01-01T00:00:00Z"}, ConditionOperator.BEFORE),
        ({"operator": "matches", "value": "^fin"}, ConditionOperator.MATCHES),
        (
            {"attribute": "time.hour", "operator": "greater_than_or_equal", "value": 9},
            ConditionOperator.GREATER_THAN_OR_EQUAL,
        ),
        ({"attribute": "env.on_call", "operator": "is_true", "value": None}, ConditionOperator.IS_TRUE),
        ({"attribute": "user.status", "value": "true", "value_type": "boolean"}, ConditionOperator.EQUALS),
    ],
)
def test_valid_condition_definitions_are_accepted(overrides, expected):
    assert _valid(**overrides) == expected


@pytest.mark.unit
def test_update_validation_checks_the_resulting_condition():
    stored = SimpleNamespace(
        attribute="resource.tags",
        operator="in",
        value='["a", "b"]',
        value_type="list",
    )
    # Changing only the description keeps the stored (valid) list condition.
    assert validate_condition_update(stored, fields_set={"description"}) == ConditionOperator.IN
    # Switching the operator re-validates against the stored value.
    assert validate_condition_update(stored, fields_set={"operator"}, operator="contains") == ConditionOperator.CONTAINS
    # Changing value_type without a value would clear it: refused for IN.
    with pytest.raises(InvalidInputError):
        validate_condition_update(stored, fields_set={"value_type"}, value_type="string")
    with pytest.raises(InvalidInputError):
        validate_condition_update(stored, fields_set={"attribute"}, attribute="subject.tags")


@pytest.fixture
def engine() -> PolicyEvaluationEngine:
    return PolicyEvaluationEngine()


@pytest.mark.unit
def test_missing_boolean_attribute_satisfies_neither_is_true_nor_is_false(engine):
    context = {"resource": {}}
    is_false = Condition(attribute="resource.locked", operator=ConditionOperator.IS_FALSE)
    is_true = Condition(attribute="resource.locked", operator=ConditionOperator.IS_TRUE)
    assert engine.evaluate_condition(is_false, context) is False
    assert engine.evaluate_condition(is_true, context) is False
    assert engine.evaluate_condition(is_false, {"resource": {"locked": False}}) is True


@pytest.mark.unit
def test_negative_collection_operators_fail_closed_on_type_mismatch(engine):
    assert engine._evaluate_operator("finance", ConditionOperator.NOT_IN, "finance") is False
    assert engine._evaluate_operator("finance", ConditionOperator.NOT_IN, ["ops"]) is True
    assert engine._evaluate_operator("finance", ConditionOperator.NOT_CONTAINS, "secret") is False
    assert engine._evaluate_operator(["finance"], ConditionOperator.NOT_CONTAINS, "secret") is True


@pytest.mark.unit
def test_malformed_stored_conditions_never_grant(engine):
    def row(**overrides):
        payload = {
            "condition_group_id": None,
            "attribute": "user.department",
            "operator": "equals",
            "value": "finance",
            "value_type": "string",
        }
        payload.update(overrides)
        return SimpleNamespace(**payload)

    context = {"user": {"department": "finance", "level": 5}}
    assert engine.evaluate_sql_conditions(conditions=[row()], group_ops={}, context=context) is True

    for bad in (
        row(operator="eq"),
        row(attribute="subject.department"),
        row(attribute="user.level", operator="greater_than", value="many", value_type="integer"),
        row(operator="not_exists", attribute="context.department"),
    ):
        assert engine.evaluate_sql_conditions(conditions=[bad], group_ops={}, context=context) is False

    # In an OR group a malformed row is simply not a match.
    grouped = [
        row(condition_group_id="g", operator="eq"),
        row(condition_group_id="g", value="ops"),
    ]
    assert engine.evaluate_sql_conditions(conditions=grouped, group_ops={"g": "OR"}, context=context) is False
    grouped.append(row(condition_group_id="g"))
    assert engine.evaluate_sql_conditions(conditions=grouped, group_ops={"g": "OR"}, context=context) is True
