import pytest
import pytest_asyncio

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.models.sql.closure import EntityClosure
from outlabs_auth.models.sql.entity import Entity
from outlabs_auth.models.sql.entity_membership import EntityMembership
from outlabs_auth.models.sql.enums import EntityClass, MembershipStatus
from outlabs_auth.models.sql.permission import Permission
from outlabs_auth.models.sql.role import Role
from outlabs_auth.models.sql.user import User
from outlabs_auth.services.permission import PermissionService


@pytest_asyncio.fixture
async def permission_service(auth_config: AuthConfig) -> PermissionService:
    return PermissionService(config=auth_config, observability=None)


async def _create_permission(session, name: str) -> Permission:
    perm = Permission(
        name=name,
        display_name=name,
        description=name,
        is_system=True,
        is_active=True,
    )
    session.add(perm)
    await session.flush()
    return perm


async def _create_role(session, name: str, perms: list[Permission]) -> Role:
    role = Role(
        name=name,
        display_name=name,
        description=name,
        is_system_role=False,
        is_global=False,
    )
    role.permissions = perms
    session.add(role)
    await session.flush()
    return role


async def _create_entity(session, slug: str, parent: Entity | None = None) -> Entity:
    entity = Entity(
        name=slug,
        display_name=slug,
        slug=slug,
        description=slug,
        entity_class=EntityClass.STRUCTURAL,
        entity_type="test",
        parent_id=parent.id if parent else None,
        depth=(parent.depth + 1) if parent else 0,
        status="active",
    )
    entity.update_path(parent.path if parent else None)
    session.add(entity)
    await session.flush()
    return entity


async def _add_closure_rows(session, parent: Entity, child: Entity) -> None:
    session.add(EntityClosure(ancestor_id=parent.id, descendant_id=parent.id, depth=0))
    session.add(EntityClosure(ancestor_id=child.id, descendant_id=child.id, depth=0))
    session.add(EntityClosure(ancestor_id=parent.id, descendant_id=child.id, depth=1))
    await session.flush()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tree_permission_inherited_from_parent(
    test_session, permission_service: PermissionService
):
    user = User(email="u@example.com")
    test_session.add(user)
    await test_session.flush()

    p_update = await _create_permission(test_session, "entity:update")
    p_update_tree = await _create_permission(test_session, "entity:update_tree")
    role = await _create_role(test_session, "org_admin", [p_update_tree])

    parent = await _create_entity(test_session, "parent")
    child = await _create_entity(test_session, "child", parent=parent)
    await _add_closure_rows(test_session, parent=parent, child=child)

    membership = EntityMembership(
        user_id=user.id,
        entity_id=parent.id,
        status=MembershipStatus.ACTIVE,
    )
    membership.roles = [role]
    test_session.add(membership)
    await test_session.flush()

    assert (
        await permission_service.check_permission(
            test_session,
            user_id=user.id,
            permission="entity:update",
            entity_id=child.id,
        )
        is True
    )
    assert (
        await permission_service.check_permission(
            test_session,
            user_id=user.id,
            permission="entity:update_tree",
            entity_id=child.id,
        )
        is True
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_non_tree_permission_does_not_inherit_from_parent(
    test_session, permission_service: PermissionService
):
    user = User(email="u2@example.com")
    test_session.add(user)
    await test_session.flush()

    p_update = await _create_permission(test_session, "entity:update")
    role = await _create_role(test_session, "parent_editor", [p_update])

    parent = await _create_entity(test_session, "parent2")
    child = await _create_entity(test_session, "child2", parent=parent)
    await _add_closure_rows(test_session, parent=parent, child=child)

    membership = EntityMembership(
        user_id=user.id,
        entity_id=parent.id,
        status=MembershipStatus.ACTIVE,
    )
    membership.roles = [role]
    test_session.add(membership)
    await test_session.flush()

    assert (
        await permission_service.check_permission(
            test_session,
            user_id=user.id,
            permission="entity:update",
            entity_id=child.id,
        )
        is False
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tree_permission_is_superset_on_target_entity(
    test_session, permission_service: PermissionService
):
    user = User(email="u3@example.com")
    test_session.add(user)
    await test_session.flush()

    await _create_permission(test_session, "entity:update")
    p_update_tree = await _create_permission(test_session, "entity:update_tree")
    role = await _create_role(test_session, "team_admin", [p_update_tree])

    entity = await _create_entity(test_session, "self")
    test_session.add(
        EntityClosure(ancestor_id=entity.id, descendant_id=entity.id, depth=0)
    )
    await test_session.flush()

    membership = EntityMembership(
        user_id=user.id,
        entity_id=entity.id,
        status=MembershipStatus.ACTIVE,
    )
    membership.roles = [role]
    test_session.add(membership)
    await test_session.flush()

    assert (
        await permission_service.check_permission(
            test_session,
            user_id=user.id,
            permission="entity:update",
            entity_id=entity.id,
        )
        is True
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_all_permission_grants_everywhere(
    test_session, permission_service: PermissionService
):
    user = User(email="u4@example.com")
    test_session.add(user)
    await test_session.flush()

    p_update = await _create_permission(test_session, "entity:update")
    p_update_all = await _create_permission(test_session, "entity:update_all")
    role = await _create_role(test_session, "platform_admin", [p_update_all])

    parent = await _create_entity(test_session, "parent3")
    child = await _create_entity(test_session, "child3", parent=parent)
    await _add_closure_rows(test_session, parent=parent, child=child)

    membership = EntityMembership(
        user_id=user.id,
        entity_id=parent.id,
        status=MembershipStatus.ACTIVE,
    )
    membership.roles = [role]
    test_session.add(membership)
    await test_session.flush()

    assert (
        await permission_service.check_permission(
            test_session, user_id=user.id, permission=p_update.name, entity_id=child.id
        )
        is True
    )
    assert (
        await permission_service.check_permission(
            test_session,
            user_id=user.id,
            permission="entity:update_tree",
            entity_id=child.id,
        )
        is True
    )
