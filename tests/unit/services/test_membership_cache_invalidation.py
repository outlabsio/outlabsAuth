from __future__ import annotations

from uuid import uuid4

import pytest

from outlabs_auth.models.sql.entity import Entity
from outlabs_auth.models.sql.entity_membership import EntityMembership
from outlabs_auth.models.sql.enums import EntityClass, MembershipStatus
from outlabs_auth.models.sql.user import User
from outlabs_auth.services.membership import MembershipService


class _FakeCacheService:
    def __init__(self) -> None:
        self.user_ids: list[str] = []

    async def publish_user_permissions_invalidation(self, user_id: str) -> bool:
        self.user_ids.append(user_id)
        return True


async def _create_entity(test_session, slug: str) -> Entity:
    entity = Entity(
        name=slug,
        display_name=slug,
        slug=slug,
        entity_class=EntityClass.STRUCTURAL,
        entity_type="organization",
        status="active",
        depth=0,
    )
    entity.update_path(None)
    test_session.add(entity)
    await test_session.flush()
    return entity


@pytest.mark.unit
@pytest.mark.asyncio
async def test_membership_changes_publish_user_permission_invalidation(
    test_session,
    auth_config,
):
    service = MembershipService(
        auth_config.model_copy(update={"enable_entity_hierarchy": True})
    )
    fake_cache = _FakeCacheService()
    service.cache_service = fake_cache

    user = User(email=f"member-{uuid4().hex[:8]}@example.com")
    test_session.add(user)
    await test_session.flush()

    entity = await _create_entity(test_session, f"entity-{uuid4().hex[:8]}")

    test_session.add(
        EntityMembership(
            user_id=user.id,
            entity_id=entity.id,
            status=MembershipStatus.ACTIVE,
        )
    )
    await test_session.flush()

    await service.suspend_membership(
        test_session,
        entity_id=entity.id,
        user_id=user.id,
        reason="suspended for test",
    )
    await service.reactivate_membership(
        test_session,
        entity_id=entity.id,
        user_id=user.id,
    )
    removed = await service.remove_member(
        test_session,
        entity_id=entity.id,
        user_id=user.id,
        reason="removed for test",
    )

    assert removed is True
    assert fake_cache.user_ids == [str(user.id), str(user.id), str(user.id)]
