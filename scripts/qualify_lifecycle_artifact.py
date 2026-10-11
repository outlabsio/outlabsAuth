"""Qualify the opt-in lifecycle constructor from an installed candidate artifact.

Run with an artifact-installed Python outside the source checkout. Supply a
synthetic disposable loopback TEST_DATABASE_URL ending in _test. The script
creates and drops only its random owned schema and prints no identity/credential.
"""

import asyncio
import json
import os
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import outlabs_auth
from outlabs_auth.cli import run_migrations
from outlabs_auth.models.sql.enums import EntityClass, MembershipStatus
from outlabs_auth.presets import EnterpriseRBAC
from outlabs_auth.services.lifecycle_events import LifecycleEvent
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine


async def main() -> None:
    assert "site-packages" in str(Path(outlabs_auth.__file__).resolve())
    url = os.environ["TEST_DATABASE_URL"]
    target = urlparse(url)
    assert target.hostname in {"127.0.0.1", "localhost", "::1"} and target.path.endswith("_test")
    schema = "constructor_" + uuid4().hex
    admin = create_async_engine(url)
    reject = False
    calls = 0

    async def observe(session: AsyncSession, event: LifecycleEvent) -> None:
        nonlocal calls
        calls += 1
        await session.execute(
            text(f'INSERT INTO "{schema}".host_witness VALUES (:id,CAST(:payload AS jsonb))'),
            {"id": event.event_id, "payload": json.dumps(asdict(event), default=str)},
        )
        if reject and event.kind == "membership.revoked":
            raise RuntimeError("Synthetic observer outage")

    auth = EnterpriseRBAC(
        database_url=url,
        database_schema=schema,
        secret_key="Synthetic-constructor-test-secret-20261011",
        enable_caching=False,
        lifecycle_observers=[observe],
    )
    try:
        await run_migrations(url, schema=schema, lock_timeout="5s", statement_timeout="60s")
        async with admin.begin() as conn:
            await conn.execute(
                text(f'CREATE TABLE "{schema}".host_witness (id uuid PRIMARY KEY, payload jsonb NOT NULL)')
            )
        await auth.initialize()
        assert auth.user_service.lifecycle_dispatcher is auth.membership_service.lifecycle_dispatcher
        assert auth.entity_service.lifecycle_dispatcher is auth.membership_service.lifecycle_dispatcher
        async with auth.get_session() as session:
            root = await auth.entity_service.create_entity(
                session,
                name="customer-" + uuid4().hex,
                display_name="Synthetic Customer",
                entity_class=EntityClass.STRUCTURAL,
                entity_type="organization",
            )
            user = await auth.user_service.create_user(
                session,
                email=uuid4().hex + "@example.com",
                password="SyntheticConstructor123!",
                first_name="Frozen",
                last_name="Original",
                root_entity_id=root.id,
            )
            membership = await auth.membership_service.add_member(session, root.id, user.id)
            await session.commit()
            user_id, root_id, member_id = user.id, root.id, membership.id
            reject = True
            try:
                await auth.membership_service.remove_member(session, root_id, user_id)
                raise AssertionError("Expected observer failure")
            except RuntimeError as exc:
                assert str(exc) == "Synthetic observer outage"
            try:
                await session.commit()
                raise AssertionError("Expected poisoned commit refusal")
            except RuntimeError as exc:
                assert "rollback is required" in str(exc)
            await session.rollback()
            member = await auth.membership_service.get_by_id(session, member_id)
            assert member.status == MembershipStatus.ACTIVE
            reject = False
            await auth.membership_service.remove_member(session, root_id, user_id)
            await session.commit()
            await auth.user_service.update_user_fields(session, user_id, first_name="Changed")
            user = await auth.user_service.get_by_id(session, user_id)
            await auth.user_service.delete(session, user)
            await session.commit()
            rows = (await session.execute(text(f'SELECT payload FROM "{schema}".host_witness'))).scalars().all()
            removals = [r for r in rows if r["kind"] == "membership.revoked"]
            assert len(removals) == 1 and removals[0]["first_name"] == "Frozen"
            assert any(r["kind"] == "user.hard_deleted" for r in rows)
        print(
            json.dumps(
                {
                    "constructor_dispatcher_shared": True,
                    "caught_observer_failure_commit_refused": True,
                    "original_names_survive_hard_delete": True,
                    "observer_calls": calls,
                }
            )
        )
    finally:
        await auth.shutdown()
        async with admin.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await admin.dispose()


if __name__ == "__main__":
    asyncio.run(main())
