"""Durable host evidence, destructive cascades and observer failure injection."""

import json
from dataclasses import asdict
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select, text

from outlabs_auth.models.sql.entity_membership import EntityMembership
from outlabs_auth.models.sql.enums import EntityClass, MembershipStatus, UserStatus
from outlabs_auth.services.entity import EntityService
from outlabs_auth.services.lifecycle_events import LifecycleDispatcher
from outlabs_auth.services.membership import MembershipService
from outlabs_auth.services.user import UserService

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture
async def lifecycle_world(test_session, auth_config):
    await test_session.execute(
        text("CREATE TABLE host_lifecycle_evidence (event_id uuid PRIMARY KEY, payload jsonb NOT NULL)")
    )

    async def retain(session, evidence):
        assert session is test_session
        payload = json.loads(json.dumps(asdict(evidence), default=str))
        await session.execute(
            text("INSERT INTO host_lifecycle_evidence VALUES (:id, CAST(:payload AS jsonb))"),
            {"id": evidence.event_id, "payload": json.dumps(payload)},
        )

    dispatcher = LifecycleDispatcher([retain])
    entities, users, memberships = EntityService(auth_config), UserService(auth_config), MembershipService(auth_config)
    entities.membership_service = memberships
    users.membership_service = memberships
    for service in [entities, users, memberships]:
        service.lifecycle_dispatcher = dispatcher
    suffix = uuid4().hex
    root = await entities.create_entity(
        test_session,
        name=f"root-{suffix}",
        display_name="Customer",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="organization",
    )
    child = await entities.create_entity(
        test_session,
        name=f"office-{suffix}",
        display_name="Office",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="department",
        parent_id=root.id,
    )
    user = await users.create_user(
        test_session,
        email=f"member-{suffix}@example.com",
        password="SyntheticLifecycle123!",
        first_name="Original",
        last_name="Person",
        root_entity_id=root.id,
    )
    member = await memberships.add_member(test_session, child.id, user.id)
    await test_session.commit()
    return SimpleNamespace(
        session=test_session,
        entities=entities,
        users=users,
        memberships=memberships,
        user=user,
        root=root,
        child=child,
        member=member,
        retain=retain,
    )


async def evidence(w):
    return (
        (await w.session.execute(text("SELECT payload FROM host_lifecycle_evidence ORDER BY payload->>'occurred_at'")))
        .scalars()
        .all()
    )


async def test_removal_names_survive_profile_change_and_user_hard_delete(lifecycle_world):
    w = lifecycle_world
    member_id = str(w.member.id)
    await w.memberships.remove_member(w.session, w.child.id, w.user.id)
    await w.session.commit()
    await w.users.update_user_fields(w.session, w.user.id, first_name="Changed")
    await w.users.delete(w.session, w.user)
    await w.session.commit()
    rows = await evidence(w)
    removed = [row for row in rows if row["kind"] == "membership.revoked"]
    assert len(removed) == 1
    assert removed[0]["first_name"] == "Original"
    assert removed[0]["last_name"] == "Person"
    assert removed[0]["membership_id"] == member_id
    assert any(row["kind"] == "user.hard_deleted" for row in rows)
    assert any(row["kind"] == "membership.hard_deleted" for row in rows)
    assert (await w.session.execute(select(EntityMembership))).scalars().all() == []


async def test_repeated_revoke_does_not_manufacture_removal(lifecycle_world):
    w = lifecycle_world
    assert await w.memberships.remove_member(w.session, w.child.id, w.user.id)
    assert not await w.memberships.remove_member(w.session, w.child.id, w.user.id)
    assert len([row for row in await evidence(w) if row["kind"] == "membership.revoked"]) == 1


async def test_observer_failure_refuses_even_a_caught_error_commit(lifecycle_world):
    w = lifecycle_world
    member_id, child_id, user_id = w.member.id, w.child.id, w.user.id

    async def fail(session, event):
        await w.retain(session, event)
        raise RuntimeError("Evidence unavailable")

    w.memberships.lifecycle_dispatcher = LifecycleDispatcher([fail])
    with pytest.raises(RuntimeError, match="Evidence unavailable"):
        await w.memberships.remove_member(w.session, child_id, user_id)
    with pytest.raises(RuntimeError, match="rollback is required"):
        await w.session.commit()
    await w.session.rollback()
    row = await w.session.get(EntityMembership, member_id)
    assert row.status == MembershipStatus.ACTIVE
    assert not any(event["kind"] == "membership.revoked" for event in await evidence(w))
    # The guard is reset by real rollback, not by catching the exception.
    await w.session.commit()


@pytest.mark.parametrize("operation", ["suspend", "retain_delete", "archive"])
async def test_account_and_archive_cascades_share_evidence_transaction(lifecycle_world, operation):
    w = lifecycle_world
    if operation == "suspend":
        await w.users.update_user_status(w.session, w.user.id, UserStatus.SUSPENDED)
        assert any(row["kind"] == "user.status_changed" for row in await evidence(w))
    elif operation == "retain_delete":
        await w.users.delete_user(w.session, w.user.id)
        kinds = {row["kind"] for row in await evidence(w)}
        assert {"user.deleted", "membership.revoked"}.issubset(kinds)
        assert any(
            row["kind"] == "membership.revoked" and row["source"] == "user_service.delete_user"
            for row in await evidence(w)
        )
    else:
        await w.entities.delete_entity(w.session, w.root.id, cascade=True)
        kinds = {row["kind"] for row in await evidence(w)}
        assert {"entity.archived", "membership.entity_archived"}.issubset(kinds)
    await w.session.commit()


async def test_observer_cannot_commit_or_poison_outer_by_rolling_back_later_savepoint(lifecycle_world):
    w = lifecycle_world

    async def commit(session, event):
        await session.commit()

    w.memberships.lifecycle_dispatcher = LifecycleDispatcher([commit])
    with pytest.raises(RuntimeError, match="must not commit"):
        await w.memberships.remove_member(w.session, w.child.id, w.user.id)
    savepoint = await w.session.begin_nested()
    await savepoint.rollback()
    with pytest.raises(RuntimeError, match="rollback is required"):
        await w.session.commit()
    await w.session.rollback()


async def test_failed_savepoint_can_roll_back_without_poisoning_outer(lifecycle_world):
    w = lifecycle_world

    async def fail(session, event):
        raise RuntimeError("Evidence unavailable")

    w.memberships.lifecycle_dispatcher = LifecycleDispatcher([fail])
    nested = await w.session.begin_nested()
    with pytest.raises(RuntimeError):
        await w.memberships.remove_member(w.session, w.child.id, w.user.id)
    await nested.rollback()
    await w.session.commit()


async def test_zero_observers_are_a_noop_without_even_a_transaction(test_session):
    assert not test_session.in_transaction()
    await LifecycleDispatcher().emit(test_session, kind="test", occurred_at=datetime.now(timezone.utc))
    assert not test_session.in_transaction()
