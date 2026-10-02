"""Grant-lifecycle predicates shared by routers and services.

Kept free of router and service imports so both layers can use the same
definition of "this edit grants access again" (DD-061).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional


def _status_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(getattr(value, "value", value))


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def lifecycle_update_grants_access(
    *,
    current_status: Any,
    current_valid_from: Optional[datetime],
    current_valid_until: Optional[datetime],
    next_status: Any,
    next_valid_from: Optional[datetime],
    next_valid_until: Optional[datetime],
) -> bool:
    """Whether a membership lifecycle edit (re)grants the access it carries.

    Reactivating a suspended/revoked/expired assignment, or widening the
    validity window of an active one, grants the carried permissions again and
    therefore needs the same delegation containment (SEC-2) as a new
    assignment. Narrowing a window or suspending never does: an incident
    responder must be able to cut access they do not hold themselves.
    """
    if _status_value(next_status) != "active":
        return False
    if _status_value(current_status) != "active":
        return True
    current_until = _as_utc(current_valid_until)
    next_until = _as_utc(next_valid_until)
    if current_until is not None and (next_until is None or next_until > current_until):
        return True
    current_from = _as_utc(current_valid_from)
    next_from = _as_utc(next_valid_from)
    if current_from is not None and (next_from is None or next_from < current_from):
        return True
    return False
