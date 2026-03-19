from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from outlabs_auth.models.sql.condition import Condition, ConditionGroup
from outlabs_auth.models.sql.enums import ConditionOperator
from outlabs_auth.services.policy_engine import PolicyEvaluationEngine


@pytest.fixture
def policy_engine() -> PolicyEvaluationEngine:
    return PolicyEvaluationEngine()


@pytest.mark.unit
def test_evaluate_condition_handles_existence_boolean_and_missing_attributes(
    policy_engine: PolicyEvaluationEngine,
):
    context = {
        "resource": {
            "owner_id": "user-123",
            "published": True,
            "archived": False,
        }
    }

    assert (
        policy_engine.evaluate_condition(
            Condition(
                attribute="resource.owner_id",
                operator=ConditionOperator.EXISTS,
            ),
            context,
        )
        is True
    )
    assert (
        policy_engine.evaluate_condition(
            Condition(
                attribute="resource.deleted_at",
                operator=ConditionOperator.NOT_EXISTS,
            ),
            context,
        )
        is True
    )
    assert (
        policy_engine.evaluate_condition(
            Condition(
                attribute="resource.published",
                operator=ConditionOperator.IS_TRUE,
            ),
            context,
        )
        is True
    )
    assert (
        policy_engine.evaluate_condition(
            Condition(
                attribute="resource.archived",
                operator=ConditionOperator.IS_FALSE,
            ),
            context,
        )
        is True
    )
    assert (
        policy_engine.evaluate_condition(
            Condition(
                attribute="resource.deleted_at",
                operator=ConditionOperator.EQUALS,
                value="anything",
            ),
            context,
        )
        is False
    )


@pytest.mark.unit
def test_evaluate_condition_handles_numeric_collection_and_string_operators(
    policy_engine: PolicyEvaluationEngine,
):
    context = {
        "resource": {
            "budget": "150.5",
            "status": "active",
            "tags": ["finance", "priority"],
            "slug": "team-finance",
            "code": "FIN-42",
        }
    }

    assert (
        policy_engine.evaluate_condition(
            Condition(
                attribute="resource.budget",
                operator=ConditionOperator.GREATER_THAN,
                value=100,
            ),
            context,
        )
        is True
    )
    assert (
        policy_engine.evaluate_condition(
            Condition(
                attribute="resource.status",
                operator=ConditionOperator.IN,
                value=["active", "pending"],
            ),
            context,
        )
        is True
    )
    assert (
        policy_engine.evaluate_condition(
            Condition(
                attribute="resource.status",
                operator=ConditionOperator.NOT_IN,
                value=["deleted", "archived"],
            ),
            context,
        )
        is True
    )
    assert (
        policy_engine.evaluate_condition(
            Condition(
                attribute="resource.tags",
                operator=ConditionOperator.CONTAINS,
                value="finance",
            ),
            context,
        )
        is True
    )
    assert (
        policy_engine.evaluate_condition(
            Condition(
                attribute="resource.tags",
                operator=ConditionOperator.NOT_CONTAINS,
                value="hr",
            ),
            context,
        )
        is True
    )
    assert (
        policy_engine.evaluate_condition(
            Condition(
                attribute="resource.slug",
                operator=ConditionOperator.STARTS_WITH,
                value="team-",
            ),
            context,
        )
        is True
    )
    assert (
        policy_engine.evaluate_condition(
            Condition(
                attribute="resource.code",
                operator=ConditionOperator.ENDS_WITH,
                value="-42",
            ),
            context,
        )
        is True
    )
    assert (
        policy_engine.evaluate_condition(
            Condition(
                attribute="resource.code",
                operator=ConditionOperator.MATCHES,
                value=r"^FIN-\d+$",
            ),
            context,
        )
        is True
    )
    assert (
        policy_engine.evaluate_condition(
            Condition(
                attribute="resource.code",
                operator=ConditionOperator.MATCHES,
                value="(",
            ),
            context,
        )
        is False
    )
    assert (
        policy_engine.evaluate_condition(
            Condition(
                attribute="resource.budget",
                operator=ConditionOperator.LESS_THAN,
                value="not-a-number",
            ),
            context,
        )
        is False
    )


@pytest.mark.unit
def test_evaluate_condition_handles_datetime_operators(
    policy_engine: PolicyEvaluationEngine,
):
    now = datetime(2026, 3, 19, 12, 0, tzinfo=timezone.utc)
    context = {
        "env": {
            "starts_at": "2026-03-19T10:00:00+00:00",
            "ends_at": now,
        }
    }

    assert (
        policy_engine.evaluate_condition(
            Condition(
                attribute="env.starts_at",
                operator=ConditionOperator.BEFORE,
                value="2026-03-19T11:00:00+00:00",
            ),
            context,
        )
        is True
    )
    assert (
        policy_engine.evaluate_condition(
            Condition(
                attribute="env.ends_at",
                operator=ConditionOperator.AFTER,
                value="2026-03-19T11:59:00+00:00",
            ),
            context,
        )
        is True
    )
    assert (
        policy_engine.evaluate_condition(
            Condition(
                attribute="env.ends_at",
                operator=ConditionOperator.BEFORE,
                value="not-a-timestamp",
            ),
            context,
        )
        is False
    )


@pytest.mark.unit
def test_evaluate_condition_group_and_list_semantics(policy_engine: PolicyEvaluationEngine):
    context = {"user": {"department": "engineering", "level": 4}}

    and_group = ConditionGroup(
        conditions=[
            Condition(
                attribute="user.department",
                operator=ConditionOperator.EQUALS,
                value="engineering",
            ),
            Condition(
                attribute="user.level",
                operator=ConditionOperator.GREATER_THAN_OR_EQUAL,
                value=4,
            ),
        ],
        operator="AND",
    )
    or_group = ConditionGroup(
        conditions=[
            Condition(
                attribute="user.department",
                operator=ConditionOperator.EQUALS,
                value="finance",
            ),
            Condition(
                attribute="user.level",
                operator=ConditionOperator.GREATER_THAN,
                value=3,
            ),
        ],
        operator="OR",
    )

    assert policy_engine.evaluate_condition_group(and_group, context) is True
    assert policy_engine.evaluate_condition_group(or_group, context) is True
    assert policy_engine.evaluate_conditions(and_group.conditions, context) is True
    assert policy_engine.evaluate_conditions([], context) is True


@pytest.mark.unit
def test_evaluate_condition_group_rejects_unknown_group_operator(
    policy_engine: PolicyEvaluationEngine,
):
    invalid_group = SimpleNamespace(
        operator="XOR",
        conditions=[
            Condition(
                attribute="user.department",
                operator=ConditionOperator.EQUALS,
                value="engineering",
            )
        ],
    )

    with pytest.raises(ValueError, match="Unknown logical operator: XOR"):
        policy_engine.evaluate_condition_group(invalid_group, {"user": {"department": "engineering"}})


@pytest.mark.unit
def test_create_context_and_context_enrichment_helpers(policy_engine: PolicyEvaluationEngine):
    context = policy_engine.create_context(
        user={"department": "engineering"},
        resource={"type": "document"},
        env={"ip": "127.0.0.1"},
    )

    assert context["user"] == {"department": "engineering"}
    assert context["resource"] == {"type": "document"}
    assert context["env"] == {"ip": "127.0.0.1"}
    assert context["time"]["timestamp"]
    assert isinstance(context["time"]["is_business_hours"], bool)

    enriched = policy_engine.add_user_context({}, "user-123", {"department": "finance"})
    assert enriched["user"] == {"id": "user-123", "department": "finance"}

    enriched = policy_engine.add_resource_context(
        enriched,
        "resource-456",
        "entity",
        {"status": "active"},
    )
    assert enriched["resource"] == {
        "id": "resource-456",
        "type": "entity",
        "status": "active",
    }


@pytest.mark.unit
def test_evaluate_sql_conditions_handles_ungrouped_and_grouped_conditions(
    policy_engine: PolicyEvaluationEngine,
):
    context = {
        "user": {"department": "finance", "level": 5},
        "env": {"method": "POST"},
    }
    conditions = [
        SimpleNamespace(
            condition_group_id=None,
            attribute="user.level",
            operator=ConditionOperator.GREATER_THAN_OR_EQUAL,
            value="4",
            value_type="integer",
        ),
        SimpleNamespace(
            condition_group_id="group-1",
            attribute="env.method",
            operator=ConditionOperator.EQUALS,
            value="GET",
            value_type="string",
        ),
        SimpleNamespace(
            condition_group_id="group-1",
            attribute="env.method",
            operator=ConditionOperator.EQUALS,
            value="POST",
            value_type="string",
        ),
        SimpleNamespace(
            condition_group_id="group-2",
            attribute="user.department",
            operator=ConditionOperator.IN,
            value='["finance", "ops"]',
            value_type="list",
        ),
    ]

    assert (
        policy_engine.evaluate_sql_conditions(
            conditions=conditions,
            group_ops={"group-1": "OR", "group-2": "AND"},
            context=context,
        )
        is True
    )


@pytest.mark.unit
def test_evaluate_sql_conditions_rejects_unknown_group_operator(
    policy_engine: PolicyEvaluationEngine,
):
    conditions = [
        SimpleNamespace(
            condition_group_id="group-1",
            attribute="user.department",
            operator=ConditionOperator.EQUALS,
            value="finance",
            value_type="string",
        )
    ]

    with pytest.raises(ValueError, match="Unknown logical operator: XOR"):
        policy_engine.evaluate_sql_conditions(
            conditions=conditions,
            group_ops={"group-1": "XOR"},
            context={"user": {"department": "finance"}},
        )
