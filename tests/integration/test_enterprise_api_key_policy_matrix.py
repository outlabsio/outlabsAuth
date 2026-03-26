import uuid
from uuid import UUID

import pytest
import pytest_asyncio

from outlabs_auth import EnterpriseRBAC
from outlabs_auth.models.sql.enums import APIKeyStatus, EntityClass


async def _verify_key_access(
    auth: EnterpriseRBAC,
    *,
    api_key: str,
    required_scope: str,
    entity_id: UUID,
) -> bool:
    async with auth.get_session() as session:
        verified, _ = await auth.api_key_service.verify_api_key(
            session,
            api_key,
            required_scope=required_scope,
            entity_id=entity_id,
        )
        return verified is not None


async def _get_key_status(
    auth: EnterpriseRBAC,
    *,
    key_id: UUID,
) -> APIKeyStatus:
    async with auth.get_session() as session:
        key = await auth.api_key_service.get_api_key(session, key_id)
        assert key is not None
        return key.status


@pytest_asyncio.fixture
async def enterprise_auth(test_engine) -> EnterpriseRBAC:
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
async def test_enterprise_api_keys_follow_permission_role_and_membership_mutations(
    enterprise_auth: EnterpriseRBAC,
):
    unique = uuid.uuid4().hex[:8]
    contacts_read = f"contacts{unique}:read"
    contacts_read_tree = f"{contacts_read}_tree"
    orders_read = f"orders{unique}:read"
    orders_read_tree = f"{orders_read}_tree"
    billing_read = f"billing{unique}:read"
    reports_read = f"reports{unique}:read"

    async with enterprise_auth.get_session() as session:
        root = await enterprise_auth.entity_service.create_entity(
            session=session,
            name=f"api_key_matrix_root_{unique}",
            display_name="API Key Matrix Root",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        department = await enterprise_auth.entity_service.create_entity(
            session=session,
            name=f"api_key_matrix_department_{unique}",
            display_name="API Key Matrix Department",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="department",
            parent_id=root.id,
        )
        team = await enterprise_auth.entity_service.create_entity(
            session=session,
            name=f"api_key_matrix_team_{unique}",
            display_name="API Key Matrix Team",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=department.id,
        )

        admin = await enterprise_auth.user_service.create_user(
            session=session,
            email=f"api-key-matrix-admin-{unique}@example.com",
            password="AdminPass123!",
            first_name="Matrix",
            last_name="Admin",
            is_superuser=True,
            root_entity_id=root.id,
        )
        owner_permission_removed = await enterprise_auth.user_service.create_user(
            session=session,
            email=f"api-key-permission-owner-{unique}@example.com",
            password="OwnerPass123!",
            first_name="Permission",
            last_name="Owner",
            root_entity_id=root.id,
        )
        owner_role_removed_from_entity = await enterprise_auth.user_service.create_user(
            session=session,
            email=f"api-key-membership-owner-{unique}@example.com",
            password="OwnerPass123!",
            first_name="Membership",
            last_name="Owner",
            root_entity_id=root.id,
        )
        owner_role_removed_from_user = await enterprise_auth.user_service.create_user(
            session=session,
            email=f"api-key-user-role-owner-{unique}@example.com",
            password="OwnerPass123!",
            first_name="UserRole",
            last_name="Owner",
            root_entity_id=root.id,
        )
        owner_removed_from_entity = await enterprise_auth.user_service.create_user(
            session=session,
            email=f"api-key-removed-owner-{unique}@example.com",
            password="OwnerPass123!",
            first_name="Removed",
            last_name="Owner",
            root_entity_id=root.id,
        )

        contacts_permission = await enterprise_auth.permission_service.create_permission(
            session,
            name=contacts_read_tree,
            display_name="Contacts Read Tree",
            description="Can read contacts in a subtree",
        )
        orders_permission = await enterprise_auth.permission_service.create_permission(
            session,
            name=orders_read_tree,
            display_name="Orders Read Tree",
            description="Can read orders in a subtree",
        )
        billing_permission = await enterprise_auth.permission_service.create_permission(
            session,
            name=billing_read,
            display_name="Billing Read",
            description="Can read billing data",
        )
        reports_permission = await enterprise_auth.permission_service.create_permission(
            session,
            name=reports_read,
            display_name="Reports Read",
            description="Can read reports",
        )

        permission_removed_role = await enterprise_auth.role_service.create_role(
            session=session,
            name=f"api_key_permission_removed_role_{unique}",
            display_name="Permission Removed Role",
            is_global=False,
            root_entity_id=root.id,
        )
        membership_role = await enterprise_auth.role_service.create_role(
            session=session,
            name=f"api_key_membership_role_{unique}",
            display_name="Membership Role",
            is_global=False,
            root_entity_id=root.id,
        )
        direct_user_role = await enterprise_auth.role_service.create_role(
            session=session,
            name=f"api_key_direct_user_role_{unique}",
            display_name="Direct User Role",
            is_global=True,
        )
        removed_member_role = await enterprise_auth.role_service.create_role(
            session=session,
            name=f"api_key_removed_member_role_{unique}",
            display_name="Removed Member Role",
            is_global=False,
            root_entity_id=root.id,
        )

        await enterprise_auth.role_service.add_permissions(
            session,
            permission_removed_role.id,
            [contacts_permission.id],
        )
        await enterprise_auth.role_service.add_permissions(
            session,
            membership_role.id,
            [orders_permission.id],
        )
        await enterprise_auth.role_service.add_permissions(
            session,
            direct_user_role.id,
            [billing_permission.id],
        )
        await enterprise_auth.role_service.add_permissions(
            session,
            removed_member_role.id,
            [reports_permission.id],
        )

        await enterprise_auth.membership_service.add_member(
            session=session,
            entity_id=department.id,
            user_id=owner_permission_removed.id,
            role_ids=[permission_removed_role.id],
            joined_by_id=admin.id,
        )
        await enterprise_auth.membership_service.add_member(
            session=session,
            entity_id=department.id,
            user_id=owner_role_removed_from_entity.id,
            role_ids=[membership_role.id],
            joined_by_id=admin.id,
        )
        await enterprise_auth.role_service.assign_role_to_user(
            session=session,
            user_id=owner_role_removed_from_user.id,
            role_id=direct_user_role.id,
            assigned_by_id=admin.id,
        )
        await enterprise_auth.membership_service.add_member(
            session=session,
            entity_id=team.id,
            user_id=owner_removed_from_entity.id,
            role_ids=[removed_member_role.id],
            joined_by_id=admin.id,
        )

        permission_removed_key, permission_removed_model = await enterprise_auth.api_key_service.create_api_key(
            session=session,
            owner_id=owner_permission_removed.id,
            name="Permission Removed Key",
            scopes=[contacts_read_tree],
            entity_id=department.id,
            inherit_from_tree=True,
            actor_user_id=owner_permission_removed.id,
        )
        membership_role_key, membership_role_model = await enterprise_auth.api_key_service.create_api_key(
            session=session,
            owner_id=owner_role_removed_from_entity.id,
            name="Membership Role Key",
            scopes=[orders_read_tree],
            entity_id=department.id,
            inherit_from_tree=True,
            actor_user_id=owner_role_removed_from_entity.id,
        )
        direct_user_role_key, direct_user_role_model = await enterprise_auth.api_key_service.create_api_key(
            session=session,
            owner_id=owner_role_removed_from_user.id,
            name="Direct User Role Key",
            scopes=[billing_read],
            entity_id=root.id,
            inherit_from_tree=True,
            actor_user_id=owner_role_removed_from_user.id,
        )
        removed_member_key, removed_member_model = await enterprise_auth.api_key_service.create_api_key(
            session=session,
            owner_id=owner_removed_from_entity.id,
            name="Removed Member Key",
            scopes=[reports_read],
            entity_id=team.id,
            actor_user_id=owner_removed_from_entity.id,
        )
        await session.commit()

        admin_id = admin.id
        department_id = department.id
        team_id = team.id
        permission_removed_role_id = permission_removed_role.id
        direct_user_role_id = direct_user_role.id
        membership_role_owner_id = owner_role_removed_from_entity.id
        direct_user_role_owner_id = owner_role_removed_from_user.id
        removed_member_owner_id = owner_removed_from_entity.id
        permission_removed_key_id = permission_removed_model.id
        membership_role_key_id = membership_role_model.id
        direct_user_role_key_id = direct_user_role_model.id
        removed_member_key_id = removed_member_model.id

    assert await _verify_key_access(
        enterprise_auth,
        api_key=permission_removed_key,
        required_scope=contacts_read,
        entity_id=team_id,
    )
    assert await _verify_key_access(
        enterprise_auth,
        api_key=membership_role_key,
        required_scope=orders_read,
        entity_id=team_id,
    )
    assert await _verify_key_access(
        enterprise_auth,
        api_key=direct_user_role_key,
        required_scope=billing_read,
        entity_id=team_id,
    )
    assert await _verify_key_access(
        enterprise_auth,
        api_key=removed_member_key,
        required_scope=reports_read,
        entity_id=team_id,
    )

    async with enterprise_auth.get_session() as session:
        await enterprise_auth.role_service.remove_permissions_by_name(
            session,
            permission_removed_role_id,
            [contacts_read_tree],
            changed_by_id=admin_id,
        )
        await session.commit()

    assert not await _verify_key_access(
        enterprise_auth,
        api_key=permission_removed_key,
        required_scope=contacts_read,
        entity_id=team_id,
    )
    assert await _get_key_status(enterprise_auth, key_id=permission_removed_key_id) == APIKeyStatus.ACTIVE

    async with enterprise_auth.get_session() as session:
        await enterprise_auth.membership_service.update_membership(
            session=session,
            entity_id=department_id,
            user_id=membership_role_owner_id,
            role_ids=[],
            update_roles=True,
            changed_by_id=admin_id,
        )
        await session.commit()

    assert not await _verify_key_access(
        enterprise_auth,
        api_key=membership_role_key,
        required_scope=orders_read,
        entity_id=team_id,
    )
    assert await _get_key_status(enterprise_auth, key_id=membership_role_key_id) == APIKeyStatus.ACTIVE

    async with enterprise_auth.get_session() as session:
        await enterprise_auth.role_service.revoke_role_from_user(
            session,
            user_id=direct_user_role_owner_id,
            role_id=direct_user_role_id,
            revoked_by_id=admin_id,
            reason="role removed from user",
        )
        await session.commit()

    assert not await _verify_key_access(
        enterprise_auth,
        api_key=direct_user_role_key,
        required_scope=billing_read,
        entity_id=team_id,
    )
    assert await _get_key_status(enterprise_auth, key_id=direct_user_role_key_id) == APIKeyStatus.ACTIVE

    async with enterprise_auth.get_session() as session:
        await enterprise_auth.membership_service.remove_member(
            session,
            entity_id=team_id,
            user_id=removed_member_owner_id,
            revoked_by_id=admin_id,
            reason="removed from team",
        )
        await session.commit()

    assert not await _verify_key_access(
        enterprise_auth,
        api_key=removed_member_key,
        required_scope=reports_read,
        entity_id=team_id,
    )
    assert await _get_key_status(enterprise_auth, key_id=removed_member_key_id) == APIKeyStatus.ACTIVE


@pytest.mark.integration
@pytest.mark.asyncio
async def test_enterprise_archived_anchor_entities_revoke_anchored_api_keys(
    enterprise_auth: EnterpriseRBAC,
):
    unique = uuid.uuid4().hex[:8]
    inventory_read = f"inventory{unique}:read"

    async with enterprise_auth.get_session() as session:
        root = await enterprise_auth.entity_service.create_entity(
            session=session,
            name=f"api_key_archive_root_{unique}",
            display_name="API Key Archive Root",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        team = await enterprise_auth.entity_service.create_entity(
            session=session,
            name=f"api_key_archive_team_{unique}",
            display_name="API Key Archive Team",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=root.id,
        )
        admin = await enterprise_auth.user_service.create_user(
            session=session,
            email=f"api-key-archive-admin-{unique}@example.com",
            password="AdminPass123!",
            first_name="Archive",
            last_name="Admin",
            is_superuser=True,
            root_entity_id=root.id,
        )
        owner = await enterprise_auth.user_service.create_user(
            session=session,
            email=f"api-key-archive-owner-{unique}@example.com",
            password="OwnerPass123!",
            first_name="Archive",
            last_name="Owner",
            root_entity_id=root.id,
        )
        permission = await enterprise_auth.permission_service.create_permission(
            session,
            name=inventory_read,
            display_name="Inventory Read",
            description="Can read inventory",
        )
        role = await enterprise_auth.role_service.create_role(
            session=session,
            name=f"api_key_archive_role_{unique}",
            display_name="API Key Archive Role",
            is_global=False,
            root_entity_id=root.id,
        )
        await enterprise_auth.role_service.add_permissions(session, role.id, [permission.id])
        await enterprise_auth.membership_service.add_member(
            session=session,
            entity_id=team.id,
            user_id=owner.id,
            role_ids=[role.id],
            joined_by_id=admin.id,
        )
        full_key, api_key = await enterprise_auth.api_key_service.create_api_key(
            session=session,
            owner_id=owner.id,
            name="Archived Anchor Key",
            scopes=[inventory_read],
            entity_id=team.id,
            actor_user_id=owner.id,
        )
        await session.commit()

        admin_id = admin.id
        api_key_id = api_key.id
        team_id = team.id

    assert await _verify_key_access(
        enterprise_auth,
        api_key=full_key,
        required_scope=inventory_read,
        entity_id=team_id,
    )

    async with enterprise_auth.get_session() as session:
        await enterprise_auth.entity_service.delete_entity(
            session,
            team_id,
            deleted_by_id=admin_id,
        )
        await session.commit()

    assert not await _verify_key_access(
        enterprise_auth,
        api_key=full_key,
        required_scope=inventory_read,
        entity_id=team_id,
    )
    assert await _get_key_status(enterprise_auth, key_id=api_key_id) == APIKeyStatus.REVOKED
