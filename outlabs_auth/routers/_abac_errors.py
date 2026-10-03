"""Refusal mapping shared by the ABAC condition and condition-group write routes."""

from __future__ import annotations

from fastapi import status

from outlabs_auth.core.exceptions import InvalidInputError


class ConditionWriteRefusedError(InvalidInputError):
    """A refused ABAC condition or condition-group write, answered with 400.

    The roles and permissions routers document **400** for these refusals while
    :class:`InvalidInputError` defaults to 422, so the routes re-raise the
    service error as this subclass. It keeps the service error's code, message
    and ``details`` — ``reason = "invalid_abac_condition"`` and the offending
    ``field`` for a condition the policy engine cannot honor — and the library
    exception handler renders the standard ``error`` / ``message`` /
    ``details`` envelope.
    """

    status_code = status.HTTP_400_BAD_REQUEST


def condition_write_refused(exc: InvalidInputError) -> ConditionWriteRefusedError:
    """Re-issue a service refusal as the documented 400 library error."""
    return ConditionWriteRefusedError(
        exc.message,
        error_code=exc.error_code,
        details=dict(exc.details),
    )
