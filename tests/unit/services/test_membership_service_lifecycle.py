from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import (
    EntityNotFoundError,
    InvalidInputError,
    MembershipNotFoundError,
    RoleNotFoundError,
    UserNotFoundError,
)
from outlabs_auth.models.sql.enums import EntityClass, MembershipStatus
from outlabs_auth.services.entity import EntityService
from outlabs_auth.services.membership import MembershipService
from outlabs_auth.services.role import RoleService
from outlabs_auth.services.user import UserService


async def _create_membership_tree(
    test_session,
    auth_config: AuthConfig,
    *,
    root_slug: str,
    team_slug: str,
    max_members: int | None = None,
):
    entity_service = EntityService(config=auth_config, redis_client=None)
    root = await entity_service.create_entity(
        session=test_session,
        name=root_slug,
        display_name=root_slug.title(),
        slug=root_slug,
        entity_class=EntityClass.STRUCTURAL,
        entity_type="organization",
    )
    team = await entity_service.create_entity(
        session=test_session,
        name=team_slug,
        display_name=team_slug.title(),
        slug=team_slug,
        entity_class=EntityClass.STRUCTURAL,
        entity_type="team",
        parent_id=root.id,
        max_members=max_members,
    )
    return root, team


@pytest.mark.unit
@pytest.mark.asyncio
async def test_membership_service_add_member_validations_and_existing_update(
    test_session,
    auth_config: AuthConfig,
):
    entity_service = EntityService(config=auth_config, redis_client=None)
    user_service = UserService(config=auth_config)
    role_service = RoleService(config=auth_config)
    membership_service = MembershipService(config=auth_config)

    root, team = await _create_membership_tree(
        test_session,
        auth_config,
        root_slug="membership-root",
        team_slug="membership-team",
    )
    limited_team = await entity_service.create_entity(
        session=test_session,
        name="limited-team",
        display_name="Limited Team",
        slug="limited-team",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="team",
        parent_id=root.id,
        max_members=1,
    )
    other_root, other_team = await _create_membership_tree(
        test_session,
        auth_config,
        root_slug="other-root",
        team_slug="other-team",
    )

    member = await user_service.create_user(
        test_session,
        email="membership-member@example.com",
        password="TestPass123!",
        first_name="Membership",
        last_name="Member",
    )
    second_member = await user_service.create_user(
        test_session,
        email="membership-second@example.com",
        password="TestPass123!",
        first_name="Second",
        last_name="Member",
    )
    org_role = await role_service.create_role(
        test_session,
        name="membership-org-role",
        display_name="Membership Org Role",
        is_global=False,
        root_entity_id=root.id,
    )

    now = datetime.now(timezone.utc)
    with pytest.raises(InvalidInputError, match="valid_until must be after valid_from"):
        await membership_service.add_member(
            test_session,
            entity_id=team.id,
            user_id=member.id,
            valid_from=now,
            valid_until=now - timedelta(minutes=5),
        )

    with pytest.raises(EntityNotFoundError, match="Entity not found"):
        await membership_service.add_member(
            test_session,
            entity_id=uuid4(),
            user_id=member.id,
        )

    with pytest.raises(UserNotFoundError, match="User not found"):
        await membership_service.add_member(
            test_session,
            entity_id=team.id,
            user_id=uuid4(),
        )

    with pytest.raises(RoleNotFoundError, match="Role not found"):
        await membership_service.add_member(
            test_session,
            entity_id=team.id,
            user_id=member.id,
            role_ids=[uuid4()],
        )

    limited_membership = await membership_service.add_member(
        test_session,
        entity_id=limited_team.id,
        user_id=member.id,
        role_ids=[],
    )
    assert limited_membership.entity_id == limited_team.id

    with pytest.raises(InvalidInputError, match="maximum members limit"):
        await membership_service.add_member(
            test_session,
            entity_id=limited_team.id,
            user_id=second_member.id,
            role_ids=[],
        )

    membership = await membership_service.add_member(
        test_session,
        entity_id=team.id,
        user_id=member.id,
        role_ids=[org_role.id],
    )
    assert membership.user_id == member.id
    assert member.root_entity_id == root.id

    updated = await membership_service.add_member(
        test_session,
        entity_id=team.id,
        user_id=member.id,
        role_ids=[],
        status=MembershipStatus.SUSPENDED,
        reason="paused by admin",
        skip_auto_assign=True,
    )
    assert updated.id == membership.id
    assert updated.status == MembershipStatus.SUSPENDED
    assert updated.revocation_reason == "paused by admin"

    reactivated = await membership_service.add_member(
        test_session,
        entity_id=team.id,
        user_id=member.id,
        role_ids=[org_role.id],
        status=MembershipStatus.ACTIVE,
        skip_auto_assign=True,
    )
    assert reactivated.id == membership.id
    assert reactivated.status == MembershipStatus.ACTIVE
    assert reactivated.revocation_reason is None
    assert [role.id for role in reactivated.roles] == [org_role.id]

    with pytest.raises(InvalidInputError, match="different organization"):
        await membership_service.add_member(
            test_session,
            entity_id=other_team.id,
            user_id=member.id,
            role_ids=[],
        )

    assert other_root.id != root.id


@pytest.mark.unit
@pytest.mark.asyncio
async def test_membership_service_update_lifecycle_and_batch_revocation_paths(
    test_session,
    auth_config: AuthConfig,
):
    entity_service = EntityService(config=auth_config, redis_client=None)
    user_service = UserService(config=auth_config)
    role_service = RoleService(config=auth_config)
    membership_service = MembershipService(config=auth_config)

    root, team = await _create_membership_tree(
        test_session,
        auth_config,
        root_slug="lifecycle-root",
        team_slug="lifecycle-team",
    )
    project = await entity_service.create_entity(
        session=test_session,
        name="lifecycle-project",
        display_name="Lifecycle Project",
        slug="lifecycle-project",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="project",
        parent_id=root.id,
    )

    member = await user_service.create_user(
        test_session,
        email="lifecycle-member@example.com",
        password="TestPass123!",
        first_name="Lifecycle",
        last_name="Member",
    )
    second_member = await user_service.create_user(
        test_session,
        email="lifecycle-second@example.com",
        password="TestPass123!",
        first_name="Lifecycle",
        last_name="Second",
    )
    archived_member = await user_service.create_user(
        test_session,
        email="lifecycle-archived@example.com",
        password="TestPass123!",
        first_name="Lifecycle",
        last_name="Archived",
    )

    role_one = await role_service.create_role(
        test_session,
        name="lifecycle-role-one",
        display_name="Lifecycle Role One",
        is_global=False,
        root_entity_id=root.id,
    )
    role_two = await role_service.create_role(
        test_session,
        name="lifecycle-role-two",
        display_name="Lifecycle Role Two",
        is_global=False,
        root_entity_id=root.id,
    )

    membership = await membership_service.add_member(
        test_session,
        entity_id=team.id,
        user_id=member.id,
        role_ids=[role_one.id],
    )
    batch_membership = await membership_service.add_member(
        test_session,
        entity_id=project.id,
        user_id=second_member.id,
        role_ids=[],
    )
    archived_membership = await membership_service.add_member(
        test_session,
        entity_id=team.id,
        user_id=archived_member.id,
        role_ids=[],
    )

    future = datetime.now(timezone.utc) + timedelta(days=1)
    later = future + timedelta(days=7)
    updated = await membership_service.update_membership(
        test_session,
        entity_id=team.id,
        user_id=member.id,
        role_ids=[role_two.id],
        update_roles=True,
        status=MembershipStatus.SUSPENDED,
        update_status=True,
        valid_from=future,
        update_valid_from=True,
        valid_until=later,
        update_valid_until=True,
        reason="temporarily paused",
        update_reason=True,
        changed_by_id=member.id,
    )
    assert updated.status == MembershipStatus.SUSPENDED
    assert updated.valid_from == future
    assert updated.valid_until == later
    assert updated.revocation_reason == "temporarily paused"
    assert [role.id for role in updated.roles] == [role_two.id]

    role_reset = await membership_service.update_member_roles(
        test_session,
        entity_id=team.id,
        user_id=member.id,
        role_ids=[role_one.id],
    )
    assert [role.id for role in role_reset.roles] == [role_one.id]

    with pytest.raises(MembershipNotFoundError, match="Membership not found"):
        await membership_service.remove_member(
            test_session,
            entity_id=team.id,
            user_id=uuid4(),
        )

    suspended = await membership_service.suspend_membership(
        test_session,
        entity_id=team.id,
        user_id=member.id,
        reason="manual suspension",
    )
    assert suspended.status == MembershipStatus.SUSPENDED
    assert suspended.revocation_reason == "manual suspension"

    reactivated = await membership_service.reactivate_membership(
        test_session,
        entity_id=team.id,
        user_id=member.id,
    )
    assert reactivated.status == MembershipStatus.ACTIVE
    assert reactivated.revocation_reason is None
    assert reactivated.revoked_at is None

    removed = await membership_service.remove_member(
        test_session,
        entity_id=team.id,
        user_id=member.id,
        reason="removed from team",
    )
    assert removed is True

    with pytest.raises(MembershipNotFoundError, match="Membership not found"):
        await membership_service.suspend_membership(
            test_session,
            entity_id=project.id,
            user_id=uuid4(),
        )

    with pytest.raises(MembershipNotFoundError, match="Membership not found"):
        await membership_service.reactivate_membership(
            test_session,
            entity_id=project.id,
            user_id=uuid4(),
        )

    revoked_for_user = await membership_service.revoke_memberships_for_user(
        test_session,
        user_id=second_member.id,
        reason="user deleted",
    )
    assert {membership.id for membership in revoked_for_user} == {batch_membership.id}

    archived_entity_memberships = await membership_service.archive_memberships_for_entity(
        test_session,
        entity_id=team.id,
        reason="entity archived",
    )
    assert [membership.id for membership in archived_entity_memberships] == [archived_membership.id]

    history, total = await membership_service.get_user_membership_history(
        test_session,
        user_id=member.id,
        page=1,
        limit=20,
    )
    assert total >= 4
    assert history[0].event_type in {"entity_archived", "revoked", "reactivated", "updated"}
