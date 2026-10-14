"""Explicit library admission for bounded customer roles, never general control-plane authority."""

from uuid import uuid4

import pytest

from outlabs_auth.core.exceptions import InvalidInputError
from outlabs_auth.models.sql.administrative_grant import AdministrativeTemplateRevision
from outlabs_auth.models.sql.permission import Permission
from outlabs_auth.services.administrative_grants import _hash
from tests.integration.test_administrative_grant_foundation import grant, world as foundation_world
from tests.integration.test_staff_credential_target_lists import context, world

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
_fixture_exports = (world, foundation_world)


async def template(w, actions, **kwargs):
    for name in actions:
        w.session.add(Permission(name=name, display_name=name))
    await w.session.flush()
    return await w.svc.create_template(
        w.session, actor_id=w.platform.id, template_key=uuid4().hex, revision=1, actions=actions, **kwargs
    )


async def test_catalog_requires_explicit_template_and_callsite_opt_in(world):
    w = world
    w.session.add(Permission(name="role:read", display_name="role:read"))
    await w.session.flush()
    with pytest.raises(InvalidInputError, match="control-plane"):
        await w.svc.create_template(
            w.session, actor_id=w.platform.id, template_key=uuid4().hex, revision=1, actions=["role:read"]
        )
    t = await w.svc.create_template(
        w.session,
        actor_id=w.platform.id,
        template_key=uuid4().hex,
        revision=1,
        actions=["role:read"],
        customer_catalog=True,
    )
    await grant(w, t, w.a)
    await w.session.commit()
    ctx = await context(w)
    assert not (await w.facade.authorize(w.session, ctx, action="role:read", entity_id=w.a.id)).allowed
    assert (
        await w.facade.authorize(w.session, ctx, action="role:read", entity_id=w.a.id, customer_catalog=True)
    ).allowed
    assert not (
        await w.facade.authorize(w.session, ctx, action="role:read", entity_id=w.b.id, customer_catalog=True)
    ).allowed
    assert not (
        await w.facade.authorize(w.session, ctx, action="role:read", entity_id=w.internal.id, customer_catalog=True)
    ).allowed


@pytest.mark.parametrize(
    "action", ["role:*", "role:manage_permissions", "permission:update", "config:update", "administrative_grant:create"]
)
async def test_catalog_opt_in_does_not_enable_control_plane_or_wildcards(world, action):
    with pytest.raises(InvalidInputError, match="control-plane"):
        await template(world, [action], customer_catalog=True)


async def test_catalog_requires_marker_even_for_a_rehashed_legacy_template(world):
    w = world
    t = await template(w, ["role:update"], customer_catalog=True)
    issued = await grant(w, t, w.a)
    await w.session.commit()
    policy = {k: v for k, v in t.policy.items() if k != "customer_catalog"}
    # Simulate an imported older-shaped row without modifying an immutable revision.
    legacy = AdministrativeTemplateRevision(
        template_key=uuid4().hex, revision=1, policy=policy, policy_hash=_hash(policy)
    )
    w.session.add(legacy)
    await w.session.flush()
    await w.svc.revoke_grant(w.session, actor_id=w.platform.id, grant_id=issued.id)
    await grant(w, legacy, w.a)
    await w.session.commit()
    ctx = await context(w)
    assert not (
        await w.facade.authorize(
            w.session, ctx, action="role:update", entity_id=w.a.id, customer_catalog=True, protected_write=True
        )
    ).allowed


async def test_catalog_write_retains_existing_grant_revocation_fence(world):
    w = world
    t = await template(w, ["role:update"], customer_catalog=True)
    g = await grant(w, t, w.a)
    await w.session.commit()
    ctx = await context(w)
    assert (
        await w.facade.authorize(
            w.session, ctx, action="role:update", entity_id=w.a.id, customer_catalog=True, protected_write=True
        )
    ).allowed
    await w.session.commit()
    await w.svc.revoke_grant(w.session, actor_id=w.platform.id, grant_id=g.id)
    await w.session.commit()
    ctx = await context(w)
    assert not (
        await w.facade.authorize(
            w.session, ctx, action="role:update", entity_id=w.a.id, customer_catalog=True, protected_write=True
        )
    ).allowed
