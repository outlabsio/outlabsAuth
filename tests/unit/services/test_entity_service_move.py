import pytest

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import InvalidInputError
from outlabs_auth.models.sql.enums import EntityClass
from outlabs_auth.services.entity import EntityService


@pytest.mark.unit
@pytest.mark.asyncio
async def test_move_entity_reparents_subtree_and_rebuilds_closure(
    test_session, auth_config: AuthConfig
):
    svc = EntityService(config=auth_config, redis_client=None)

    root_a = await svc.create_entity(
        session=test_session,
        name="root_a",
        display_name="Root A",
        slug="root-a",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="root",
    )
    node_b = await svc.create_entity(
        session=test_session,
        name="node_b",
        display_name="Node B",
        slug="node-b",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="node",
        parent_id=root_a.id,
    )
    leaf_c = await svc.create_entity(
        session=test_session,
        name="leaf_c",
        display_name="Leaf C",
        slug="leaf-c",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="leaf",
        parent_id=node_b.id,
    )
    root_x = await svc.create_entity(
        session=test_session,
        name="root_x",
        display_name="Root X",
        slug="root-x",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="root",
    )

    await test_session.flush()

    # Sanity: initial ancestry
    assert await svc.is_ancestor_of(test_session, root_a.id, node_b.id) is True
    assert await svc.is_ancestor_of(test_session, root_a.id, leaf_c.id) is True
    assert await svc.is_ancestor_of(test_session, root_x.id, node_b.id) is False

    # Move B (and its subtree) under X
    moved = await svc.move_entity(
        test_session, entity_id=node_b.id, new_parent_id=root_x.id
    )
    await test_session.flush()

    # Parent pointers updated
    assert moved.parent_id == root_x.id

    # Depth updated for subtree
    node_b_fresh = await svc.get_entity(test_session, node_b.id)
    leaf_c_fresh = await svc.get_entity(test_session, leaf_c.id)
    assert node_b_fresh.depth == root_x.depth + 1
    assert leaf_c_fresh.depth == node_b_fresh.depth + 1

    # Paths updated for subtree
    assert node_b_fresh.path == f"{root_x.path}{node_b_fresh.slug}/"
    assert leaf_c_fresh.path == f"{node_b_fresh.path}{leaf_c_fresh.slug}/"

    # Closure rebuilt: X is now an ancestor; A is no longer.
    assert await svc.is_ancestor_of(test_session, root_x.id, node_b.id) is True
    assert await svc.is_ancestor_of(test_session, root_x.id, leaf_c.id) is True
    assert await svc.is_ancestor_of(test_session, root_a.id, node_b.id) is False
    assert await svc.is_ancestor_of(test_session, root_a.id, leaf_c.id) is False

    # Internal subtree relationships remain.
    assert await svc.is_ancestor_of(test_session, node_b.id, leaf_c.id) is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_move_entity_prevents_cycles(test_session, auth_config: AuthConfig):
    svc = EntityService(config=auth_config, redis_client=None)

    root = await svc.create_entity(
        session=test_session,
        name="root",
        display_name="Root",
        slug="root",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="root",
    )
    child = await svc.create_entity(
        session=test_session,
        name="child",
        display_name="Child",
        slug="child",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="node",
        parent_id=root.id,
    )
    grandchild = await svc.create_entity(
        session=test_session,
        name="grandchild",
        display_name="Grandchild",
        slug="grandchild",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="node",
        parent_id=child.id,
    )
    await test_session.flush()

    with pytest.raises(InvalidInputError):
        await svc.move_entity(
            test_session, entity_id=root.id, new_parent_id=grandchild.id
        )
