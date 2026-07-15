"""Release rehearsal for upgrading populated pre-0.1.0a24 auth schemas."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from outlabs_auth.cli import run_migrations
from tests.conftest import TEST_DATABASE_URL


PRE_RELEASE_REVISION = "20260611_0018"


def _qualified(schema: str, table: str) -> str:
    return f'"{schema}"."{table}"'


async def _drop_schema(schema: str) -> None:
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    try:
        async with engine.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
    finally:
        await engine.dispose()


async def _row_count(schema: str, table: str) -> int:
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text(f"SELECT COUNT(*) FROM {_qualified(schema, table)}"))
            return int(result.scalar_one())
    finally:
        await engine.dispose()


@pytest.mark.integration
async def test_seeded_pre_release_schema_upgrades_losslessly_and_is_idempotent():
    """Exercise 0019/0020 against rows that existed before this release."""
    schema = f"upgrade_rehearsal_{uuid4().hex[:10]}"
    user_id = uuid4()
    token_id = uuid4()
    api_key_id = uuid4()
    expires_at = datetime.now(timezone.utc) + timedelta(days=14)
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    try:
        await run_migrations(TEST_DATABASE_URL, revision=PRE_RELEASE_REVISION, schema=schema)

        async with engine.begin() as conn:
            # The squashed baseline is model-backed, so current source code can
            # expose newly-added columns even when targeting an older revision.
            # Remove only 0020's shape to reconstruct an actual a23 database.
            await conn.execute(
                text(f"ALTER TABLE {_qualified(schema, 'refresh_tokens')} DROP COLUMN IF EXISTS replaced_by_token_id")
            )
            await conn.execute(
                text(f"ALTER TABLE {_qualified(schema, 'refresh_tokens')} DROP COLUMN IF EXISTS family_id")
            )
            await conn.execute(
                text(
                    f"""
                    INSERT INTO {_qualified(schema, 'users')}
                        (id, email, auth_methods, status, is_superuser, email_verified,
                         phone_verified, failed_login_attempts)
                    VALUES
                        (:id, :email, ARRAY['PASSWORD'], 'active', FALSE, TRUE, FALSE, 0)
                    """
                ),
                {"id": user_id, "email": f"upgrade-{user_id.hex[:12]}@example.com"},
            )
            await conn.execute(
                text(
                    f"""
                    INSERT INTO {_qualified(schema, 'refresh_tokens')}
                        (id, user_id, token_hash, expires_at, is_revoked, usage_count)
                    VALUES (:id, :user_id, :token_hash, :expires_at, FALSE, 3)
                    """
                ),
                {
                    "id": token_id,
                    "user_id": user_id,
                    "token_hash": f"seeded-pre-upgrade-{token_id.hex}",
                    "expires_at": expires_at,
                },
            )
            await conn.execute(
                text(
                    f"""
                    INSERT INTO {_qualified(schema, 'api_keys')}
                        (id, name, prefix, key_hash, owner_id, key_kind, status,
                         usage_count, rate_limit_per_minute, inherit_from_tree)
                    VALUES (:id, 'seeded pre-upgrade key', :prefix, :key_hash, :owner_id,
                            'personal', 'active', 17, 60, TRUE)
                    """
                ),
                {
                    "id": api_key_id,
                    "prefix": f"sk_test_{api_key_id.hex[:8]}",
                    "key_hash": f"seeded-pre-upgrade-{api_key_id.hex}",
                    "owner_id": user_id,
                },
            )

        before_counts = {
            table: await _row_count(schema, table)
            for table in ("users", "refresh_tokens", "api_keys")
        }

        await run_migrations(TEST_DATABASE_URL, schema=schema)

        async with engine.connect() as conn:
            token = (
                await conn.execute(
                    text(
                        f"""
                        SELECT family_id, replaced_by_token_id, usage_count
                        FROM {_qualified(schema, 'refresh_tokens')}
                        WHERE id = :id
                        """
                    ),
                    {"id": token_id},
                )
            ).one()
            revision = await conn.execute(
                text(f"SELECT version_num FROM {_qualified(schema, 'outlabs_auth_alembic_version')}")
            )
            index_exists = await conn.execute(
                text(
                    """
                    SELECT 1 FROM pg_indexes
                    WHERE schemaname = :schema AND tablename = 'refresh_tokens'
                      AND indexname = 'ix_refresh_tokens_family_id'
                    """
                ),
                {"schema": schema},
            )

        assert UUID(str(token.family_id)) == token_id
        assert token.replaced_by_token_id is None
        assert token.usage_count == 3
        assert revision.scalar_one() == "20260715_0020"
        assert index_exists.scalar_one() == 1
        assert await _row_count(schema, "api_key_usage_sync_batches") == 0
        assert {
            table: await _row_count(schema, table)
            for table in before_counts
        } == before_counts

        # A second upgrade must neither mutate seeded rows nor create receipts.
        await run_migrations(TEST_DATABASE_URL, schema=schema)
        assert {
            table: await _row_count(schema, table)
            for table in before_counts
        } == before_counts
        assert await _row_count(schema, "api_key_usage_sync_batches") == 0
    finally:
        await engine.dispose()
        await _drop_schema(schema)
