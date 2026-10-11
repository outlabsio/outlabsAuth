"""Persistent foundation; these checks do not qualify runtime S2 admission."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from outlabs_auth.core.exceptions import InvalidInputError, PermissionDeniedError
from outlabs_auth.models.sql.administrative_grant import AdministrativeAudit, AdministrativeTemplateRevision
from outlabs_auth.models.sql.enums import EntityClass, UserStatus
from outlabs_auth.models.sql.user import User
from outlabs_auth.services.administrative_grants import AdministrativeGrantService
from outlabs_auth.services.entity import EntityService
from outlabs_auth.services.permission import PermissionService
from outlabs_auth.services.user import UserService

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture
async def world(test_session, auth_config):
    entities = EntityService(auth_config)
    users = UserService(auth_config)
    suffix = uuid4().hex
    roots = []
    for key in ["internal", "a", "b"]:
        roots.append(
            await entities.create_entity(
                test_session,
                name=f"{key}-{suffix}",
                display_name=key,
                entity_class=EntityClass.STRUCTURAL,
                entity_type="organization",
            )
        )
    internal, a, b = roots
    child = await entities.create_entity(
        test_session,
        name=f"child-{suffix}",
        display_name="Child",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="department",
        parent_id=a.id,
    )
    platform = await users.create_user(
        test_session, email=f"platform-{suffix}@example.com", password="SyntheticGrant123!", is_superuser=True
    )
    staff = await users.create_user(
        test_session, email=f"staff-{suffix}@example.com", password="SyntheticGrant123!", root_entity_id=internal.id
    )
    outsider = await users.create_user(
        test_session, email=f"outside-{suffix}@example.com", password="SyntheticGrant123!", root_entity_id=a.id
    )
    permissions = PermissionService(auth_config)
    for action in ["case:read", "case:update", "user:update"]:
        await permissions.create_permission(test_session, name=action, display_name=action)
    svc = AdministrativeGrantService(trusted_internal_root_id=internal.id)
    read = await svc.create_template(
        test_session, actor_id=platform.id, template_key="reader", revision=1, actions=["case:read"]
    )
    update = await svc.create_template(
        test_session, actor_id=platform.id, template_key="writer", revision=1, actions=["case:update", "user:update"]
    )
    await test_session.commit()
    return SimpleNamespace(
        session=test_session,
        entities=entities,
        users=users,
        svc=svc,
        platform=platform,
        staff=staff,
        outsider=outsider,
        internal=internal,
        a=a,
        b=b,
        child=child,
        read=read,
        update=update,
    )


async def grant(w, template, target, kind="entity", **kwargs):
    return await w.svc.issue_grant(
        w.session,
        actor_id=w.platform.id,
        user_id=w.staff.id,
        template_id=template.id,
        selector_kind=kind,
        target_id=target.id,
        request_key=uuid4().hex,
        reason="Synthetic reviewed policy",
        **kwargs,
    )


async def check(w, action, target, **kwargs):
    return await w.svc.check_target(w.session, user_id=w.staff.id, action=action, entity_id=target.id, **kwargs)


async def test_actions_and_targets_cannot_be_stitched(world):
    w = world
    await grant(w, w.read, w.a)
    await grant(w, w.update, w.b)
    assert (await check(w, "case:read", w.a)).allowed
    assert (await check(w, "case:update", w.b)).allowed
    assert not (await check(w, "case:update", w.a)).allowed
    assert not (await check(w, "case:read", w.b)).allowed
    assert not (await check(w, "case:read", w.child)).allowed
    assert not (await check(w, "case:read", w.internal)).allowed


async def test_management_rechecks_a_demoted_platform_actor(world):
    w = world
    # Keep the original ORM instance alive in the management session while a
    # different transaction withdraws platform authority.
    assert w.platform.is_superuser
    factory = async_sessionmaker(w.session.bind, expire_on_commit=False)
    async with factory() as other:
        await other.execute(update(User).where(User.id == w.platform.id).values(is_superuser=False))
        await other.commit()
    with pytest.raises(PermissionDeniedError, match="platform-only"):
        await w.svc.create_group(w.session, actor_id=w.platform.id, group_key="must-not-exist")


async def test_subtree_and_account_root_and_personal_key_ceilings(world):
    w = world
    await grant(w, w.update, w.child, "subtree")
    assert (await check(w, "case:update", w.child)).allowed
    assert not (await check(w, "user:update", w.child, account_root_required=True)).allowed
    await grant(w, w.update, w.a, "subtree")
    assert (await check(w, "user:update", w.child, account_root_required=True)).allowed
    assert not (await check(w, "case:update", w.child, key_actions=set())).allowed
    assert not (await check(w, "user:update", w.child, account_root_required=True, key_entity_ids={w.child.id})).allowed
    assert (
        await check(
            w,
            "user:update",
            w.child,
            account_root_required=True,
            key_entity_ids={w.child.id, w.a.id},
            key_actions={"user:update"},
        )
    ).allowed


async def test_pinned_admissions_never_follow_removal_readd_or_new_customer(world):
    w = world
    group = await w.svc.create_group(w.session, actor_id=w.platform.id, group_key="Customers")
    admission = await w.svc.admit_customer(
        w.session, actor_id=w.platform.id, group_id=group.id, customer_root_id=w.a.id
    )
    await grant(w, w.read, group, "group")
    assert (await check(w, "case:read", w.child)).allowed
    await w.svc.admit_customer(w.session, actor_id=w.platform.id, group_id=group.id, customer_root_id=w.b.id)
    assert not (await check(w, "case:read", w.b)).allowed
    await w.svc.remove_customer(w.session, actor_id=w.platform.id, admission_id=admission.id)
    assert not (await check(w, "case:read", w.a)).allowed
    readded = await w.svc.admit_customer(w.session, actor_id=w.platform.id, group_id=group.id, customer_root_id=w.a.id)
    assert readded.id != admission.id
    assert not (await check(w, "case:read", w.a)).allowed
    await grant(w, w.read, group, "group")
    assert (await check(w, "case:read", w.a)).allowed


async def test_platform_only_management_and_foreign_human_refusal(world):
    w = world
    with pytest.raises(PermissionDeniedError):
        await w.svc.create_group(w.session, actor_id=w.staff.id, group_key="Self-granted")
    with pytest.raises(InvalidInputError):
        await w.svc.issue_grant(
            w.session,
            actor_id=w.platform.id,
            user_id=w.outsider.id,
            template_id=w.read.id,
            selector_kind="entity",
            target_id=w.a.id,
            request_key=uuid4().hex,
            reason="Foreign human",
        )
    group = await w.svc.create_group(w.session, actor_id=w.platform.id, group_key="Customers")
    for target in [w.internal, w.child]:
        with pytest.raises(InvalidInputError):
            await w.svc.admit_customer(w.session, actor_id=w.platform.id, group_id=group.id, customer_root_id=target.id)


async def test_terminal_idempotency_and_conflicts(world):
    w = world
    row = await grant(w, w.read, w.a)
    await w.svc.revoke_grant(w.session, actor_id=w.platform.id, grant_id=row.id)
    retry = await w.svc.issue_grant(
        w.session,
        actor_id=w.platform.id,
        user_id=w.staff.id,
        template_id=w.read.id,
        selector_kind="entity",
        target_id=w.a.id,
        request_key=row.request_key,
        reason=row.reason,
    )
    assert retry.id == row.id and retry.revoked_at is not None
    assert not (await check(w, "case:read", w.a)).allowed
    with pytest.raises(InvalidInputError):
        await w.svc.issue_grant(
            w.session,
            actor_id=w.platform.id,
            user_id=w.staff.id,
            template_id=w.read.id,
            selector_kind="entity",
            target_id=w.b.id,
            request_key=row.request_key,
            reason=row.reason,
        )


@pytest.mark.parametrize("window", ["future", "expired"])
async def test_aware_window_denial(world, window):
    w = world
    now = datetime.now(timezone.utc)
    await grant(
        w,
        w.read,
        w.a,
        **(
            {"valid_from": now + timedelta(days=1)}
            if window == "future"
            else {"valid_until": now - timedelta(seconds=1)}
        ),
    )
    assert not (await check(w, "case:read", w.a)).allowed


async def test_suspension_and_template_kill_switch(world):
    w = world
    await grant(w, w.read, w.a)
    await w.svc.set_template_active(w.session, actor_id=w.platform.id, template_id=w.read.id, active=False)
    assert not (await check(w, "case:read", w.a)).allowed
    await w.svc.set_template_active(w.session, actor_id=w.platform.id, template_id=w.read.id, active=True)
    await w.users.update_user_status(w.session, w.staff.id, UserStatus.SUSPENDED)
    assert not (await check(w, "case:read", w.a)).allowed


async def test_policy_objects_are_separate_and_creation_audit_rolls_back(world):
    w = world
    row = await w.svc.create_template(
        w.session, actor_id=w.platform.id, template_key="temporary", revision=1, actions=["case:read"]
    )
    identity = row.id
    await w.session.rollback()
    assert (
        await w.session.execute(
            select(AdministrativeTemplateRevision).where(AdministrativeTemplateRevision.id == identity)
        )
    ).scalar_one_or_none() is None
    assert (
        await w.session.execute(select(AdministrativeAudit).where(AdministrativeAudit.subject_id == identity))
    ).scalar_one_or_none() is None


@pytest.mark.parametrize("action", ["*:*", "case:*", "role:create", "permission:update"])
async def test_unsupported_policy_never_becomes_authority(world, action):
    w = world
    with pytest.raises(InvalidInputError):
        await w.svc.create_template(
            w.session, actor_id=w.platform.id, template_key="unsupported", revision=1, actions=[action]
        )
