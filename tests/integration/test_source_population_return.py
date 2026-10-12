"""Invited identity setup and provable source-only return on migrated PostgreSQL."""

from uuid import uuid4

import pytest
from sqlalchemy import text

from outlabs_auth.core.exceptions import InvalidInputError, UserAlreadyExistsError
from outlabs_auth.models.sql.entity_membership import MembershipSourceWithdrawal
from tests.integration.test_administrative_grant_foundation import world as foundation_world
from tests.integration.test_membership_source_ownership import role, claim
from tests.integration.test_staff_credential_target_lists import world

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_invited_source_user_has_no_credentials_challenges_or_delivery(world):
    w = world
    user_id = uuid4()
    user = await w.auth.user_service.create_source_user(
        w.session,
        user_id=user_id,
        email="source-" + uuid4().hex + "@example.com",
        root_entity_id=w.a.id,
        first_name="Source",
        last_name="Person",
    )
    assert user.id == user_id and user.status == "invited" and user.hashed_password is None
    assert not user.is_superuser and not user.email_verified and user.session_security_epoch == 0
    assert (
        await w.session.execute(text("SELECT count(*) FROM auth_challenges WHERE user_id=:id"), {"id": user_id})
    ).scalar_one() == 0
    await w.session.rollback()


@pytest.mark.parametrize("collision", ["email", "uuid"])
async def test_source_account_collision_never_adopts_existing_identity(world, collision):
    w = world
    with pytest.raises(UserAlreadyExistsError, match="collides"):
        await w.auth.user_service.create_source_user(
            w.session,
            user_id=w.outsider.id if collision == "uuid" else uuid4(),
            email=w.outsider.email if collision == "email" else "new-" + uuid4().hex + "@example.com",
            root_entity_id=w.b.id,
        )
    assert w.outsider.root_entity_id == w.a.id and w.outsider.status == "active"


async def test_source_only_return_preserves_same_membership_and_credential(world):
    w = world
    r = await role(w)
    identity = uuid4()
    m = await claim(w, identity, [r])
    m_id = m.id
    credential = w.outsider.hashed_password
    await claim(w, identity, withdraw=True)
    proof = await w.session.get(MembershipSourceWithdrawal, (w.outsider.id, w.a.id))
    assert proof and proof.membership_id == m_id
    m = await claim(w, identity, [r])
    await w.session.refresh(m, ["roles", "status"])
    assert m.id == m_id and m.status == "active" and not m.native_owned and {x.id for x in m.roles} == {r.id}
    assert w.outsider.hashed_password == credential
    assert await w.session.get(MembershipSourceWithdrawal, (w.outsider.id, w.a.id)) is None


@pytest.mark.parametrize(
    "native", ["repeat_remove", "same_status_sdk", "same_status_dml", "role_dml", "security_epoch", "hard_delete"]
)
async def test_native_edit_after_withdrawal_refuses_source_return(world, native):
    w = world
    r = await role(w)
    identity = uuid4()
    m = await claim(w, identity, [r])
    m_id = m.id
    user_id = w.outsider.id
    await claim(w, identity, withdraw=True)
    if native == "repeat_remove":
        assert not await w.auth.membership_service.remove_member(w.session, w.a.id, user_id)
    elif native == "same_status_sdk":
        from outlabs_auth.models.sql.enums import MembershipStatus

        await w.auth.membership_service.update_membership(
            w.session, w.a.id, user_id, status=MembershipStatus.REVOKED, update_status=True
        )
    else:
        sql = {
            "same_status_dml": "UPDATE entity_memberships SET status=status WHERE id=:id",
            "role_dml": "INSERT INTO entity_membership_roles(membership_id,role_id) VALUES (:id,:role)",
            "security_epoch": "UPDATE users SET session_security_epoch=coalesce(session_security_epoch,0)+1 WHERE id=:user",
            "hard_delete": "DELETE FROM entity_memberships WHERE id=:id",
        }[native]
        await w.session.execute(text(sql), {"id": m_id, "role": r.id, "user": user_id})
    with pytest.raises(InvalidInputError, match="source-only withdrawal proof|natively deleted"):
        await claim(w, identity, [r])


async def test_native_reactivation_records_attachment_and_survives_future_source_removal(world):
    w = world
    r = await role(w)
    identity = uuid4()
    m = await claim(w, identity, [r])
    await claim(w, identity, withdraw=True)
    await w.auth.membership_service.reactivate_membership(w.session, w.a.id, w.outsider.id)
    await claim(w, identity, [r])
    await claim(w, identity, withdraw=True)
    await w.session.refresh(m, ["status", "native_owned"])
    assert m.status == "active" and m.native_owned


async def test_native_revocation_allows_source_cleanup_without_creating_return_proof(world):
    w = world
    r = await role(w)
    identity = uuid4()
    m = await claim(w, identity, [r])
    await w.auth.membership_service.remove_member(w.session, w.a.id, w.outsider.id)
    await claim(w, identity, withdraw=True)
    await w.session.refresh(m, ["status"])
    assert m.status == "revoked"
    assert await w.session.get(MembershipSourceWithdrawal, (w.outsider.id, w.a.id)) is None


async def test_source_return_rollback_keeps_original_withdrawal(world):
    w = world
    r = await role(w)
    identity = uuid4()
    m = await claim(w, identity, [r])
    m_id = m.id
    user_id = w.outsider.id
    entity_id = w.a.id
    await claim(w, identity, withdraw=True)
    await w.session.commit()
    await claim(w, identity, [r])
    await w.session.rollback()
    assert (
        await w.session.execute(text("SELECT status FROM entity_memberships WHERE id=:id"), {"id": m_id})
    ).scalar_one() == "revoked"
    assert await w.session.get(MembershipSourceWithdrawal, (user_id, entity_id)) is not None
