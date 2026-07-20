"""Cover `OutlabsAuth.prime_fastapi_routing()` — mount-at-import-time support.

This method had no tests and no callers inside this repo, which made it look like
a speculative escape hatch. It isn't: it is the load-bearing path for the library's
largest production consumer (diverse-data-api mounts every `/iam` router at module
import and calls this to make it legal). Breaking it would break that app at import,
and nothing here would have noticed.

The contract it exists to provide: router factories dereference `auth.deps` when
they are *called*, but `deps` is only built by `await initialize()` — which can't
run at module import. `prime_fastapi_routing()` does the synchronous half of setup
(engine, session factory, services, backends, deps) so routers can be bound at
import while migrations/Redis stay deferred to `initialize()`.

No database is touched: `create_async_engine` is lazy, so priming never connects.
"""

import pytest
from fastapi import FastAPI

from outlabs_auth import SimpleRBAC
from outlabs_auth.core.exceptions import ConfigurationError
from outlabs_auth.routers import get_auth_router

DATABASE_URL = "postgresql+asyncpg://example:example@localhost:5432/test"


def _auth(secret_key: str, **kwargs) -> SimpleRBAC:
    return SimpleRBAC(database_url=DATABASE_URL, secret_key=secret_key, **kwargs)


@pytest.mark.unit
def test_deps_unavailable_before_priming(test_secret_key: str) -> None:
    """The problem prime_fastapi_routing exists to solve."""
    auth = _auth(test_secret_key)

    with pytest.raises(ConfigurationError, match="Dependencies not initialized"):
        _ = auth.deps


@pytest.mark.unit
def test_priming_makes_deps_available_without_initialize(test_secret_key: str) -> None:
    auth = _auth(test_secret_key)

    auth.prime_fastapi_routing()

    assert auth.deps is not None
    assert callable(auth.deps.require_auth())


@pytest.mark.unit
def test_priming_lets_routers_mount_at_import_time(test_secret_key: str) -> None:
    """The actual production shape: build routers before any async startup.

    Router factories call `auth.deps.require_auth()` while constructing the route,
    so without priming this raises ConfigurationError at import — which is exactly
    what the README quickstart trips over.
    """
    auth = _auth(test_secret_key)
    auth.prime_fastapi_routing()

    app = FastAPI()
    app.include_router(get_auth_router(auth, prefix="/iam/auth"))

    # Nothing async has run; the app is still routable.
    assert app.routes


@pytest.mark.unit
def test_priming_is_idempotent(test_secret_key: str) -> None:
    """Callers can't easily tell whether priming already happened; it must be safe."""
    auth = _auth(test_secret_key)

    auth.prime_fastapi_routing()
    engine, session_factory, deps = auth._engine, auth._session_factory, auth.deps

    auth.prime_fastapi_routing()

    assert auth._engine is engine
    assert auth._session_factory is session_factory
    assert auth.deps is deps


@pytest.mark.unit
def test_priming_keeps_a_host_supplied_engine(test_secret_key: str) -> None:
    """Bring-your-own-engine must survive priming.

    diverse-data-api hands in the app's engine so auth and domain tables share one
    pool. If priming built its own instead, that app would silently run two pools
    against the same database.
    """
    from sqlalchemy.ext.asyncio import create_async_engine

    host_engine = create_async_engine(DATABASE_URL)
    auth = SimpleRBAC(engine=host_engine, secret_key=test_secret_key)

    auth.prime_fastapi_routing()

    assert auth._engine is host_engine


@pytest.mark.unit
def test_priming_requires_a_database_url_or_engine(test_secret_key: str) -> None:
    """Constructing without either is already rejected, so priming can't reach the
    'database_url is required' branch through the public API — assert the guard at
    construction instead of pretending the later branch is reachable."""
    with pytest.raises(ConfigurationError):
        SimpleRBAC(secret_key=test_secret_key)
