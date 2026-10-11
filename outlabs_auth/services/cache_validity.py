"""Server-owned time bounds for cached authority, carried without extra SQL."""

import math
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from outlabs_auth.services import request_cache


def now() -> float:
    return datetime.now(timezone.utc).timestamp()


def record(subject: str, deadline: Optional[float]) -> None:
    key = ("authority_deadline", subject)
    previous = request_cache.get(key)
    if previous is not None:
        deadline = previous if deadline is None else min(previous, deadline)
    request_cache.set_value(key, deadline)


def deadline(subject: str) -> Optional[float]:
    return request_cache.get(("authority_deadline", subject))


def observe_windows(subject: str, rows: Iterable[Any], *, observed_at: float) -> None:
    """Include scheduled starts, not just the ends of currently active rows.

    A row already expired before the read cannot become active later. A deadline
    crossed during the read remains in the proof so a paused writer cannot give
    the result a new lease. Permission evaluation still checks the live window.
    """
    bound = None
    for row in rows:
        end = getattr(row, "valid_until", None)
        end = end.timestamp() if isinstance(end, datetime) else None
        if end is not None and end < observed_at:
            continue
        start = getattr(row, "valid_from", None)
        start = start.timestamp() if isinstance(start, datetime) else None
        transitions = [value for value in (start, end) if value is not None and value >= observed_at]
        for value in transitions:
            bound = value if bound is None else min(bound, value)
    record(subject, bound)


def is_fresh(payload: dict[str, Any]) -> bool:
    # Old entries have no transition proof. Rebuild rather than lease old allows.
    if payload.get("validity_schema") != 1 or "valid_until" not in payload:
        return False
    bound = payload["valid_until"]
    return bound is None or (type(bound) in (float, int) and math.isfinite(bound) and now() < bound)


def bounded_ttl(ttl: int, bound: Optional[float]) -> int:
    # Redis integer TTL rounds DOWN; zero means don't cache, never an immortal SET.
    return ttl if bound is None else max(0, min(ttl, int(bound - now())))
