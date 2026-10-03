"""ABAC condition and condition-group write refusals keep the library error envelope.

0.1.0a35 documents a refused condition write as **400** with
``details.reason = invalid_abac_condition`` and the offending
``details.field``. The roles and permissions routers re-raised the service
error as ``HTTPException(400, detail=message)``, which dropped ``details``
(and the error code) on every condition and condition-group write route.

These tests mount the real routers on a stub auth object (no database): the
stub services validate exactly like the real ones and then refuse, and the
response is rendered by the library's own exception handlers in both modes.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Optional
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from outlabs_auth.core.exceptions import InvalidInputError
from outlabs_auth.fastapi import register_exception_handlers
from outlabs_auth.models.sql.enums import ConditionOperator
from outlabs_auth.routers import get_permissions_router, get_roles_router
from outlabs_auth.routers._abac_errors import ConditionWriteRefusedError, condition_write_refused
from outlabs_auth.services.abac_validation import (
    validate_condition_definition,
    validate_condition_update,
)

ALLOWED_OPERATORS = [item.value for item in ConditionOperator]
OWNER_ID = uuid4()
GROUP_ID = uuid4()
CONDITION_ID = uuid4()
STORED_CONDITION = SimpleNamespace(
    attribute="user.department",
    operator="equals",
    value="sales",
    value_type="string",
)


class _ConditionServiceStub:
    """Role/permission service stand-in: validates like the real one, then refuses.

    Condition writes run the real write-time validation; the remaining writes
    refuse the way the services do for a system role or permission.
    """

    def __init__(self, kind: str) -> None:
        self.kind = kind
        setattr(self, f"create_{kind}_condition", self._create_condition)
        setattr(self, f"update_{kind}_condition", self._update_condition)
        for name in (
            f"create_{kind}_condition_group",
            f"update_{kind}_condition_group",
            f"delete_{kind}_condition_group",
            f"delete_{kind}_condition",
        ):
            setattr(self, name, self._refuse_system_owner)

    async def _create_condition(
        self,
        session: Any,
        owner_id: UUID,
        *,
        attribute: Any,
        operator: Any,
        value: Any,
        value_type: Any,
        **_: Any,
    ) -> None:
        validate_condition_definition(attribute=attribute, operator=operator, value=value, value_type=value_type)
        raise AssertionError("every payload in these tests is invalid")

    async def _update_condition(
        self,
        session: Any,
        owner_id: UUID,
        condition_id: UUID,
        *,
        fields_set: set[str],
        attribute: Any = None,
        operator: Any = None,
        value: Any = None,
        value_type: Any = None,
        **_: Any,
    ) -> None:
        validate_condition_update(
            STORED_CONDITION,
            fields_set=fields_set,
            attribute=attribute,
            operator=operator,
            value=value,
            value_type=value_type,
        )
        raise AssertionError("every payload in these tests is invalid")

    async def _refuse_system_owner(self, session: Any, owner_id: UUID, *args: Any, **kwargs: Any) -> None:
        raise InvalidInputError(
            message=f"Cannot modify system {self.kind}",
            details={f"{self.kind}_id": str(owner_id), f"{self.kind}_name": f"system:{self.kind}"},
        )


class _RoleServiceStub(_ConditionServiceStub):
    def __init__(self) -> None:
        super().__init__("role")

    async def get_role_by_id(self, session: Any, role_id: UUID, **_: Any) -> SimpleNamespace:
        return SimpleNamespace(
            id=role_id,
            name="abac_tester",
            is_global=True,
            root_entity_id=None,
            scope_entity_id=None,
            is_system_role=False,
        )

    async def get_role_permission_names(self, session: Any, role_id: UUID) -> list[str]:
        return []


def _actor_dependency(*args: Any, **kwargs: Any):
    async def _actor() -> dict[str, Any]:
        return {"user_id": str(OWNER_ID), "source": "jwt"}

    return _actor


class _DepsStub:
    def __getattr__(self, name: str):
        return _actor_dependency


class _AuthStub:
    def __init__(self) -> None:
        # SimpleRBAC-shaped: no tenant scoping, so the routes reach the service.
        self.config = SimpleNamespace(enable_entity_hierarchy=False, enforce_user_scope=False)
        self.deps = _DepsStub()
        self.require_tree_permission = _actor_dependency
        self.observability = None
        self.permission_service = _ConditionServiceStub("permission")
        self.role_service = _RoleServiceStub()

    async def uow(self):
        yield SimpleNamespace()


def _client(mode: str) -> TestClient:
    auth = _AuthStub()
    app = FastAPI()
    register_exception_handlers(app, mode=mode)
    app.include_router(get_permissions_router(auth, prefix="/v1/permissions"))
    app.include_router(get_roles_router(auth, prefix="/v1/roles"))
    return TestClient(app, raise_server_exceptions=False)


def _invalid_condition(message: str, field: str, **extra: Any) -> dict[str, Any]:
    return {
        "error": "INVALID_INPUT",
        "message": message,
        "details": {"reason": "invalid_abac_condition", "field": field, **extra},
    }


def _system_owner(kind: str) -> dict[str, Any]:
    return {
        "error": "INVALID_INPUT",
        "message": f"Cannot modify system {kind}",
        "details": {f"{kind}_id": str(OWNER_ID), f"{kind}_name": f"system:{kind}"},
    }


def _refusal_cases() -> list[Any]:
    cases = []
    for kind, prefix in (("permission", "/v1/permissions"), ("role", "/v1/roles")):
        base = f"{prefix}/{OWNER_ID}"
        cases += [
            pytest.param(
                "POST",
                f"{base}/conditions",
                # The payload from the report against 0.1.0a35.
                {"attribute": "user.department", "operator": "eq", "value": "sales", "value_type": "string"},
                _invalid_condition("Unknown ABAC operator 'eq'", "operator", allowed=ALLOWED_OPERATORS),
                id=f"{kind}-create-condition-unknown-operator",
            ),
            pytest.param(
                "POST",
                f"{base}/conditions",
                {"attribute": "subject.team", "operator": "equals", "value": "a", "value_type": "string"},
                _invalid_condition(
                    "ABAC attribute context must be one of user, resource, env, time",
                    "attribute",
                    attribute="subject.team",
                    allowed_contexts=["user", "resource", "env", "time"],
                ),
                id=f"{kind}-create-condition-unsupported-context",
            ),
            pytest.param(
                "PATCH",
                f"{base}/conditions/{CONDITION_ID}",
                # Validated against the stored string value it would keep.
                {"operator": "in"},
                _invalid_condition(
                    "Operator 'in' requires value_type 'list' and a list value",
                    "value",
                    operator="in",
                ),
                id=f"{kind}-update-condition-operator-needs-list",
            ),
            pytest.param(
                "PATCH",
                f"{base}/conditions/{CONDITION_ID}",
                {"operator": "greater_than", "value": "lots"},
                _invalid_condition(
                    "Operator 'greater_than' requires a numeric value",
                    "value",
                    operator="greater_than",
                ),
                id=f"{kind}-update-condition-non-numeric-value",
            ),
            pytest.param(
                "DELETE",
                f"{base}/conditions/{CONDITION_ID}",
                None,
                _system_owner(kind),
                id=f"{kind}-delete-condition-system-owner",
            ),
            pytest.param(
                "POST",
                f"{base}/condition-groups",
                {"operator": "AND"},
                _system_owner(kind),
                id=f"{kind}-create-group-system-owner",
            ),
            pytest.param(
                "PATCH",
                f"{base}/condition-groups/{GROUP_ID}",
                {"operator": "OR"},
                _system_owner(kind),
                id=f"{kind}-update-group-system-owner",
            ),
            pytest.param(
                "DELETE",
                f"{base}/condition-groups/{GROUP_ID}",
                None,
                _system_owner(kind),
                id=f"{kind}-delete-group-system-owner",
            ),
        ]
    return cases


@pytest.mark.unit
@pytest.mark.parametrize("mode", ["auth_only", "global"])
@pytest.mark.parametrize("method, path, payload, expected", _refusal_cases())
def test_condition_write_refusals_keep_the_library_error_envelope(
    mode: str,
    method: str,
    path: str,
    payload: Optional[dict[str, Any]],
    expected: dict[str, Any],
):
    with _client(mode) as client:
        response = client.request(method, path, json=payload)

    assert response.status_code == 400, response.text
    assert response.json() == expected


@pytest.mark.unit
def test_condition_write_refused_keeps_code_message_and_details():
    original = InvalidInputError(
        message="Unknown ABAC operator 'eq'",
        details={"reason": "invalid_abac_condition", "field": "operator"},
    )

    refused = condition_write_refused(original)

    assert isinstance(refused, ConditionWriteRefusedError)
    assert isinstance(refused, InvalidInputError)
    assert refused.status_code == 400
    assert original.status_code == 422
    assert refused.to_dict() == original.to_dict()
    assert refused.details is not original.details
