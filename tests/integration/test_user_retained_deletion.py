import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select

from outlabs_auth import EnterpriseRBAC
from outlabs_auth.core.exceptions import (
    AccountInactiveError,
    RefreshTokenInvalidError,
    UserAlreadyExistsError,
)
from outlabs_auth.models.sql.api_key import APIKey
from outlabs_auth.models.sql.entity_membership import EntityMembership
from outlabs_auth.models.sql.enums import APIKeyStatus, EntityClass, MembershipStatus, UserStatus
from outlabs_auth.models.sql.token import RefreshToken
from outlabs_auth.models.sql.user_role_membership import UserRoleMembership


@pytest_asyncio.fixture
async def auth_instance(test_engine) -> EnterpriseRBAC:
    auth = EnterpriseRBAC(
        engine=test_engine,
        secret_key="test-secret-key-do-not-use-in-production-12345678",
        access_token_expire_minutes=60,
        enable_token_cleanup=False,
    )
    await auth.initialize()
    yield auth
    await auth.shutdown()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_user_retains_row_and_revokes_access_artifacts(auth_instance: EnterpriseRBAC):
    unique = uuid.uuid4().hex[:8]

    async with auth_instance.get_session() as session:
        root = await auth_instance.entity_service.create_entity(
            session=session,
            name=f"user_delete_root_{unique}",
            display_name="User Delete Root",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        team = await auth_instance.entity_service.create_entity(
            session=session,
            name=f"user_delete_team_{unique}",
            display_name="User Delete Team",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=root.id,
        )
        direct_role = await auth_instance.role_service.create_role(
            session=session,
            name=f"user_delete_direct_role_{unique}",
            display_name="User Delete Direct Role",
            is_global=False,
            root_entity_id=root.id,
        )
        permission = await auth_instance.permission_service.create_permission(
            session,
            name=f"users{unique}:read",
            display_name="User Delete Read",
            description="Delete flow permission",
        )
        await auth_instance.role_service.add_permissions(session, direct_role.id, [permission.id])
        admin = await auth_instance.user_service.create_user(
            session=session,
            email=f"delete-admin-{unique}@example.com",
            password="AdminPass123!",
            first_name="Delete",
            last_name="Admin",
            is_superuser=True,
            root_entity_id=root.id,
        )
        target = await auth_instance.user_service.create_user(
            session=session,
            email=f"delete-target-{unique}@example.com",
            password="TargetPass123!",
            first_name="Delete",
            last_name="Target",
            root_entity_id=root.id,
        )
        await auth_instance.membership_service.add_member(
            session=session,
            entity_id=team.id,
            user_id=target.id,
            role_ids=[direct_role.id],
            joined_by_id=admin.id,
        )
        await auth_instance.role_service.assign_role_to_user(
            session=session,
            user_id=target.id,
            role_id=direct_role.id,
            assigned_by_id=admin.id,
        )
        full_api_key, api_key = await auth_instance.api_key_service.create_api_key(
            session=session,
            owner_id=target.id,
            name=f"user-delete-key-{unique}",
            scopes=[permission.name],
            entity_id=team.id,
        )
        await session.commit()

        admin_id = admin.id
        target_id = target.id
        team_id = team.id
        direct_role_id = direct_role.id
        api_key_id = api_key.id
        target_email = target.email

    async with auth_instance.get_session() as session:
        logged_in_user, tokens = await auth_instance.auth_service.login(
            session,
            email=target_email,
            password="TargetPass123!",
        )
        assert logged_in_user.id == target_id
        await session.commit()

        access_token = tokens.access_token
        refresh_token = tokens.refresh_token

    async with auth_instance.get_session() as session:
        deleted = await auth_instance.user_service.delete_user(
            session,
            target_id,
            deleted_by_id=admin_id,
        )
        assert deleted is True
        await session.commit()

    async with auth_instance.get_session() as session:
        retained_user = await auth_instance.user_service.get_user_by_id(session, target_id)
        assert retained_user is not None
        assert retained_user.status == UserStatus.DELETED
        assert retained_user.deleted_at is not None

        membership = (
            await session.execute(
                select(EntityMembership).where(
                    EntityMembership.user_id == target_id,
                    EntityMembership.entity_id == team_id,
                )
            )
        ).scalar_one()
        assert membership.status == MembershipStatus.REVOKED
        assert membership.revoked_at is not None
        assert membership.revoked_by_id == admin_id
        assert membership.revocation_reason == "User deleted"

        direct_membership = (
            await session.execute(
                select(UserRoleMembership).where(
                    UserRoleMembership.user_id == target_id,
                    UserRoleMembership.role_id == direct_role_id,
                )
            )
        ).scalar_one()
        assert direct_membership.status == MembershipStatus.REVOKED
        assert direct_membership.revoked_at is not None
        assert direct_membership.revoked_by_id == admin_id
        assert direct_membership.revocation_reason == "User deleted"

        refresh_tokens = (
            (await session.execute(select(RefreshToken).where(RefreshToken.user_id == target_id))).scalars().all()
        )
        assert refresh_tokens
        assert all(token.is_revoked for token in refresh_tokens)
        assert all(token.revoked_reason == "User deleted" for token in refresh_tokens)

        stored_api_key = (await session.execute(select(APIKey).where(APIKey.id == api_key_id))).scalar_one()
        assert stored_api_key.status == APIKeyStatus.REVOKED

        verified_key, _ = await auth_instance.api_key_service.verify_api_key(session, full_api_key)
        assert verified_key is None

        with pytest.raises(AccountInactiveError):
            await auth_instance.auth_service.login(
                session,
                email=target_email,
                password="TargetPass123!",
            )

        with pytest.raises(AccountInactiveError):
            await auth_instance.auth_service.get_current_user(session, access_token)

        with pytest.raises(RefreshTokenInvalidError) as exc_info:
            await auth_instance.auth_service.refresh_access_token(session, refresh_token)
        assert exc_info.value.details["reason"] == "revoked"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_deleted_email_cannot_be_reused_for_create_or_invite(auth_instance: EnterpriseRBAC):
    unique = uuid.uuid4().hex[:8]
    email = f"retained-delete-{unique}@example.com"

    async with auth_instance.get_session() as session:
        user = await auth_instance.user_service.create_user(
            session=session,
            email=email,
            password="TargetPass123!",
            first_name="Retained",
            last_name="Delete",
        )
        await auth_instance.user_service.delete_user(session, user.id)
        await session.commit()

    async with auth_instance.get_session() as session:
        retained_user = await auth_instance.user_service.get_user_by_email(session, email)
        assert retained_user is not None
        assert retained_user.status == UserStatus.DELETED

        with pytest.raises(UserAlreadyExistsError):
            await auth_instance.user_service.create_user(
                session=session,
                email=email,
                password="AnotherPass123!",
            )

        with pytest.raises(UserAlreadyExistsError):
            await auth_instance.user_service.invite_user(
                session=session,
                email=email,
            )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_restore_user_is_identity_only_and_keeps_access_artifacts_revoked(auth_instance: EnterpriseRBAC):
    unique = uuid.uuid4().hex[:8]

    async with auth_instance.get_session() as session:
        root = await auth_instance.entity_service.create_entity(
            session=session,
            name=f"user_restore_root_{unique}",
            display_name="User Restore Root",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        team = await auth_instance.entity_service.create_entity(
            session=session,
            name=f"user_restore_team_{unique}",
            display_name="User Restore Team",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=root.id,
        )
        direct_role = await auth_instance.role_service.create_role(
            session=session,
            name=f"user_restore_direct_role_{unique}",
            display_name="User Restore Direct Role",
            is_global=False,
            root_entity_id=root.id,
        )
        permission = await auth_instance.permission_service.create_permission(
            session,
            name=f"users_restore_{unique}:read",
            display_name="User Restore Read",
            description="Restore flow permission",
        )
        await auth_instance.role_service.add_permissions(session, direct_role.id, [permission.id])
        admin = await auth_instance.user_service.create_user(
            session=session,
            email=f"restore-admin-{unique}@example.com",
            password="AdminPass123!",
            first_name="Restore",
            last_name="Admin",
            is_superuser=True,
            root_entity_id=root.id,
        )
        target = await auth_instance.user_service.create_user(
            session=session,
            email=f"restore-target-{unique}@example.com",
            password="TargetPass123!",
            first_name="Restore",
            last_name="Target",
            root_entity_id=root.id,
        )
        await auth_instance.membership_service.add_member(
            session=session,
            entity_id=team.id,
            user_id=target.id,
            role_ids=[direct_role.id],
            joined_by_id=admin.id,
        )
        await auth_instance.role_service.assign_role_to_user(
            session=session,
            user_id=target.id,
            role_id=direct_role.id,
            assigned_by_id=admin.id,
        )
        full_api_key, api_key = await auth_instance.api_key_service.create_api_key(
            session=session,
            owner_id=target.id,
            name=f"user-restore-key-{unique}",
            scopes=[permission.name],
            entity_id=team.id,
        )
        _, tokens = await auth_instance.auth_service.login(
            session,
            email=target.email,
            password="TargetPass123!",
        )
        await auth_instance.user_service.delete_user(
            session,
            target.id,
            deleted_by_id=admin.id,
        )
        await session.commit()

        target_id = target.id
        target_email = target.email
        team_id = team.id
        direct_role_id = direct_role.id
        api_key_id = api_key.id
        revoked_refresh_token = tokens.refresh_token

    async with auth_instance.get_session() as session:
        restored = await auth_instance.user_service.restore_user(session, target_id)
        await session.commit()
        assert restored.status == UserStatus.ACTIVE
        assert restored.deleted_at is None

    async with auth_instance.get_session() as session:
        restored_user = await auth_instance.user_service.get_user_by_id(session, target_id)
        assert restored_user is not None
        assert restored_user.status == UserStatus.ACTIVE
        assert restored_user.deleted_at is None

        membership = (
            await session.execute(
                select(EntityMembership).where(
                    EntityMembership.user_id == target_id,
                    EntityMembership.entity_id == team_id,
                )
            )
        ).scalar_one()
        assert membership.status == MembershipStatus.REVOKED

        direct_membership = (
            await session.execute(
                select(UserRoleMembership).where(
                    UserRoleMembership.user_id == target_id,
                    UserRoleMembership.role_id == direct_role_id,
                )
            )
        ).scalar_one()
        assert direct_membership.status == MembershipStatus.REVOKED

        refresh_tokens = (
            (await session.execute(select(RefreshToken).where(RefreshToken.user_id == target_id))).scalars().all()
        )
        assert refresh_tokens
        assert all(token.is_revoked for token in refresh_tokens)

        stored_api_key = (await session.execute(select(APIKey).where(APIKey.id == api_key_id))).scalar_one()
        assert stored_api_key.status == APIKeyStatus.REVOKED

        with pytest.raises(RefreshTokenInvalidError):
            await auth_instance.auth_service.refresh_access_token(session, revoked_refresh_token)

        new_login_user, new_tokens = await auth_instance.auth_service.login(
            session,
            email=target_email,
            password="TargetPass123!",
        )
        assert new_login_user.id == target_id
        assert new_tokens.refresh_token

        verified_key, _ = await auth_instance.api_key_service.verify_api_key(session, full_api_key)
        assert verified_key is None
