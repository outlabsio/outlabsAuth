"""
Per-request ContextVar-backed memoization.

Each HTTP request runs in its own asyncio task, so a ContextVar with dict
values gives us task-local, request-scoped storage with no cross-user bleed.
The cache is reset automatically at the start of every request via
``RequestCacheMiddleware``; if no middleware is installed, callers still get
task-local isolation because ContextVars are not shared across tasks.

Keys are tuples to avoid collisions across caller domains. The canonical
shapes used elsewhere in the package are:

- ``("user", user_id)`` → ``User`` instance
- ``("entity", entity_id)`` → ``Entity`` instance
- ``("ancestors", entity_id)`` → ``set[UUID]``
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Awaitable, Callable, Hashable, Optional


_request_cache: ContextVar[Optional[dict[Hashable, Any]]] = ContextVar(
    "outlabs_auth_request_cache",
    default=None,
)


def _store() -> dict[Hashable, Any]:
    cache = _request_cache.get()
    if cache is None:
        cache = {}
        _request_cache.set(cache)
    return cache


def get(key: Hashable) -> Any:
    """Return the cached value for ``key`` or ``None`` if absent."""
    cache = _request_cache.get()
    if cache is None:
        return None
    return cache.get(key)


def set_value(key: Hashable, value: Any) -> None:
    """Cache ``value`` under ``key`` for the current request."""
    _store()[key] = value


def contains(key: Hashable) -> bool:
    cache = _request_cache.get()
    if cache is None:
        return False
    return key in cache


async def get_or_load(key: Hashable, loader: Callable[[], Awaitable[Any]]) -> Any:
    """
    Return the cached value for ``key``, else call ``loader()`` and cache it.

    The sentinel handling stores ``None`` results so a loader that legitimately
    returns ``None`` (e.g. a missing row) is not re-run.
    """
    cache = _store()
    if key in cache:
        return cache[key]
    value = await loader()
    cache[key] = value
    return value


def reset() -> None:
    """Drop the current request's cache. Called by the middleware on exit."""
    _request_cache.set(None)
