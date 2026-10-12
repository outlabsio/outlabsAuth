"""Real migrated native/source intent and compatible writer acceptance."""

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import select, text

from outlabs_auth.core.exceptions import InvalidInputError
from outlabs_auth.models.sql.entity_membership import EntityMembershipRole, MembershipSourceClaim
from outlabs_auth.models.sql.role import Role
from tests.integration.test_staff_credential_target_lists import world
from tests.integration.test_administrative_grant_foundation import world as foundation_world

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def role(w):
    r = Role(name=uuid4().hex, display_name="Synthetic", root_entity_id=w.a.id, scope_entity_id=w.a.id)
    w.session.add(r)
    await w.session.flush()
    return r


async def claim(w, identity, roles=(), *, withdraw=False):
    return await w.auth.membership_service.set_source_membership(
        w.session,
        source_id=identity,
        entity_id=w.a.id,
        user_id=w.outsider.id,
        role_ids=None if withdraw else tuple(r.id for r in roles),
    )


async def test_native_reassignment_of_existing_source_role_retains_intent(world):
    w = world
    r = await role(w)
    identity = uuid4()
    m = await claim(w, identity, [r])
    assert not m.native_owned
    link = await w.session.get(EntityMembershipRole, (m.id, r.id))
    assert not link.native_owned
    await w.auth.membership_service.add_member(w.session, w.a.id, w.outsider.id, [r.id], skip_auto_assign=True)
    await claim(w, identity, withdraw=True)
    await w.session.refresh(m, ["roles", "native_owned", "status"])
    assert m.native_owned and m.status == "active" and [x.id for x in m.roles] == [r.id]


async def test_native_role_replacement_keeps_other_source_roles(world):
    w = world
    r, other = await role(w), await role(w)
    identity = uuid4()
    m = await claim(w, identity, [r])
    await w.auth.membership_service.update_membership(
        w.session, w.a.id, w.outsider.id, role_ids=[other.id], update_roles=True
    )
    await w.session.refresh(m, ["roles"])
    assert {x.id for x in m.roles} == {r.id, other.id}
    await claim(w, identity, withdraw=True)
    await w.session.refresh(m, ["roles"])
    assert {x.id for x in m.roles} == {other.id}


async def test_two_source_claims_preserve_each_other_and_last_withdrawal_revokes(world):
    w = world
    r, other = await role(w), await role(w)
    first, second = uuid4(), uuid4()
    m = await claim(w, first, [r])
    await claim(w, second, [r, other])
    await claim(w, first, withdraw=True)
    await w.session.refresh(m, ["roles", "status"])
    assert m.status == "active" and {x.id for x in m.roles} == {r.id, other.id}
    await claim(w, second, withdraw=True)
    await w.session.refresh(m, ["roles", "status"])
    assert m.status == "revoked" and not m.roles
    assert w.outsider.status == "active"


async def test_source_replay_preserves_credentials_and_native_suspension(world):
    w = world
    r = await role(w)
    identity = uuid4()
    old = (w.outsider.hashed_password, w.outsider.session_security_epoch, w.outsider.status)
    await claim(w, identity, [r])
    await w.auth.membership_service.suspend_membership(w.session, w.a.id, w.outsider.id)
    with pytest.raises(InvalidInputError, match="native lifecycle"):
        await claim(w, identity, [r])
    assert (w.outsider.hashed_password, w.outsider.session_security_epoch, w.outsider.status) == old


async def test_source_claim_cannot_transfer_or_grant_global_role(world):
    w = world
    r = await role(w)
    identity = uuid4()
    await claim(w, identity, [r])
    with pytest.raises(InvalidInputError, match="cannot transfer"):
        await w.auth.membership_service.set_source_membership(
            w.session, source_id=identity, entity_id=w.child.id, user_id=w.outsider.id, role_ids=()
        )
    r.is_global = True
    await w.session.flush()
    with pytest.raises(InvalidInputError, match="protected"):
        await claim(w, uuid4(), [r])


async def test_source_effects_and_intent_rollback_together(world):
    w = world
    r = await role(w)
    await w.session.commit()
    identity = uuid4()
    await claim(w, identity, [r])
    await w.session.rollback()
    assert await w.session.get(MembershipSourceClaim, identity) is None


@pytest.mark.parametrize("child", ["membership", "membership_role", "role_permission", "role_condition", "closure"])
async def test_raw_child_insert_or_delete_shares_parent_fence(world, child):
    w = world
    r = await role(w)
    m = await w.auth.membership_service.add_member(w.session, w.a.id, w.outsider.id, [], skip_auto_assign=True)
    r_id, m_id, user_id, entity_id = r.id, m.id, w.outsider.id, w.a.id
    await w.session.commit()
    parent, identity = (
        ("roles", r_id)
        if child.startswith("role_")
        else ("entities", entity_id) if child == "closure" else ("users", user_id)
    )
    sql = {
        "membership": "UPDATE entity_memberships SET native_owned=false WHERE id=:m",
        "membership_role": "INSERT INTO entity_membership_roles (membership_id,role_id) VALUES (:m,:r)",
        "role_permission": "DELETE FROM role_permissions WHERE role_id=:r",  # inserted below to exercise a nonempty delete
        "role_condition": "INSERT INTO role_conditions (id,role_id,attribute,operator,value,created_at,updated_at) VALUES (:id,:r,'region','eq','\"synthetic\"',now(),now())",
        "closure": "DELETE FROM entity_closure WHERE descendant_id=:e",
    }[child]
    if child == "role_permission":
        await w.session.execute(text("INSERT INTO role_permissions SELECT :r,id FROM permissions LIMIT 1"), {"r": r_id})
        await w.session.commit()
    async with w.factory() as held, w.factory() as other:
        await held.execute(text(f"SELECT id FROM {parent} WHERE id=:id FOR UPDATE"), {"id": identity})
        await other.execute(text("SET LOCAL lock_timeout='100ms'"))
        with pytest.raises(Exception, match="lock timeout"):
            await other.execute(text(sql), {"m": m_id, "r": r_id, "e": entity_id, "id": uuid4()})
        await other.rollback()
        await held.rollback()


async def test_native_writer_waits_then_keeps_same_source_role(world):
    w = world
    r = await role(w)
    identity = uuid4()
    await claim(w, identity, [r])
    role_id, user_id, entity_id = r.id, w.outsider.id, w.a.id
    await w.session.commit()
    await w.session.execute(text("SELECT id FROM users WHERE id=:id FOR UPDATE"), {"id": user_id})
    entered = asyncio.Event()

    async def native():
        async with w.factory() as session:
            entered.set()
            await w.auth.membership_service.add_member(session, entity_id, user_id, [role_id], skip_auto_assign=True)
            await session.commit()

    task = asyncio.create_task(native())
    await entered.wait()
    await asyncio.sleep(0.05)
    assert not task.done()
    await w.session.commit()
    await asyncio.wait_for(task, 5)
    await claim(w, identity, withdraw=True)
    m = await w.auth.membership_service.get_one(w.session, w.auth.membership_service.model.user_id == user_id)
    await w.session.refresh(m, ["roles", "native_owned"])
    assert m.native_owned and {x.id for x in m.roles} == {role_id}
