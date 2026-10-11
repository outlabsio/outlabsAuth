"""Bound migration locks and reject incomplete PostgreSQL indexes."""

import re
import asyncio
import threading
import time
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.engine import Connection

DEFAULT_LOCK_TIMEOUT = "5s"
_DURATION = re.compile(r"^(\d+(?:\.\d+)?)\s*(ms|s|min)?$")
_ALEMBIC_CONTEXT_LOCK = threading.Lock()


def validate_lock_timeout(value: str) -> str:
    match = _DURATION.fullmatch(value.strip()) if isinstance(value, str) else None
    if not match or float(match[1]) <= 0:
        raise ValueError("Migration lock_timeout must be a positive duration in ms, s or min")
    # PostgreSQL interprets a bare value as milliseconds.
    milliseconds = float(match[1]) * {None: 1, "ms": 1, "s": 1000, "min": 60000}[match[2]]
    if milliseconds < 1 or milliseconds > 30000:
        raise ValueError("Migration lock_timeout must be between 1ms and 30s")
    return value.strip()


@asynccontextmanager
async def serialized_alembic_context(timeout: str):
    """Alembic's module proxy is process-global, even across async loops."""
    match = _DURATION.fullmatch(validate_lock_timeout(timeout))
    assert match is not None
    seconds = float(match[1]) * {None: 0.001, "ms": 0.001, "s": 1, "min": 60}[match[2]]
    deadline = time.monotonic() + seconds
    while not _ALEMBIC_CONTEXT_LOCK.acquire(blocking=False):
        if time.monotonic() >= deadline:
            raise RuntimeError("Another in-process Alembic command exceeded the bounded lock wait")
        await asyncio.sleep(min(0.01, max(0, deadline - time.monotonic())))
    try:
        yield
    finally:
        _ALEMBIC_CONTEXT_LOCK.release()


def acquire_migration_lock(connection: Connection, schema: str | None, timeout: str = DEFAULT_LOCK_TIMEOUT) -> None:
    """Serialize migration runners per database/schema, never request traffic."""
    connection.execute(
        text("SELECT set_config('lock_timeout', :timeout, true)"), {"timeout": validate_lock_timeout(timeout)}
    )
    connection.execute(
        text(
            "SELECT pg_advisory_xact_lock(hashtextextended('outlabs_auth:migrate:' || COALESCE(:schema, current_schema()), 0))"
        ),
        {"schema": schema},
    )


def index_exists(connection: Connection, schema: str | None, table_name: str, index_name: str) -> bool:
    row = connection.execute(
        text(
            "SELECT i.indisvalid, i.indisready, i.indislive FROM pg_index i "
            "JOIN pg_class idx ON idx.oid=i.indexrelid "
            "JOIN pg_class tbl ON tbl.oid=i.indrelid "
            "JOIN pg_namespace n ON n.oid=tbl.relnamespace "
            "WHERE n.nspname=COALESCE(:schema, current_schema()) "
            "AND tbl.relname=:table AND idx.relname=:name"
        ),
        {"schema": schema, "table": table_name, "name": index_name},
    ).first()
    if row is None:
        return False
    if not all(row):
        raise RuntimeError(
            f"Index {index_name} on {table_name} is invalid or incomplete; "
            "repair it under the reviewed migration procedure before retrying"
        )
    return True


def validate_indexes(connection: Connection, schema: str | None) -> None:
    """Head is not an acceptance receipt while an Auth-owned index is invalid."""
    from outlabs_auth.models.sql import ALL_MODELS

    tables = [model.__tablename__ for model in ALL_MODELS]
    invalid = (
        connection.execute(
            text(
                "SELECT idx.relname FROM pg_index i JOIN pg_class idx ON idx.oid=i.indexrelid "
                "JOIN pg_class tbl ON tbl.oid=i.indrelid JOIN pg_namespace n ON n.oid=tbl.relnamespace "
                "WHERE n.nspname=COALESCE(:schema, current_schema()) AND tbl.relname=ANY(:tables) "
                "AND NOT (i.indisvalid AND i.indisready AND i.indislive)"
            ),
            {"schema": schema, "tables": tables},
        )
        .scalars()
        .all()
    )
    if invalid:
        raise RuntimeError("Auth indexes are invalid or incomplete: " + ", ".join(sorted(invalid)))
