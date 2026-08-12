from __future__ import annotations

import asyncio
import logging
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from outlabs_auth.cli import run_migrations
from tests.conftest import TEST_DATABASE_URL


async def _drop_schema(schema: str) -> None:
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    try:
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
    finally:
        await engine.dispose()


@pytest.mark.integration
def test_in_process_migration_preserves_host_application_logger() -> None:
    schema = f"logger_{uuid4().hex[:10]}"
    logger = logging.getLogger(f"host_application.{uuid4().hex}")
    logger.disabled = False
    logger.propagate = True

    try:
        asyncio.run(run_migrations(TEST_DATABASE_URL, schema=schema))

        assert logger.disabled is False
        assert logger.propagate is True
    finally:
        asyncio.run(_drop_schema(schema))
