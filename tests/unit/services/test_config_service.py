from __future__ import annotations

from uuid import uuid4

import pytest

from outlabs_auth.models.sql.system_config import ConfigKeys, DEFAULT_ENTITY_TYPE_CONFIG
from outlabs_auth.models.sql.user import User
from outlabs_auth.schemas.config import DefaultChildTypes, EntityTypeConfig
from outlabs_auth.services.config import ConfigService


async def _create_actor(test_session, *, email_prefix: str) -> User:
    actor = User(email=f"{email_prefix}-{uuid4().hex[:8]}@example.com")
    test_session.add(actor)
    await test_session.flush()
    return actor


@pytest.mark.unit
@pytest.mark.asyncio
async def test_config_service_crud_roundtrip_update_and_delete(test_session):
    service = ConfigService()
    actor = await _create_actor(test_session, email_prefix="config-actor")

    created = await service.set_config(
        test_session,
        ConfigKeys.FEATURE_FLAGS,
        {"beta_dashboard": True},
        description="Initial flags",
    )
    await test_session.commit()

    loaded = await service.get_config(test_session, ConfigKeys.FEATURE_FLAGS)
    assert created.key == ConfigKeys.FEATURE_FLAGS
    assert loaded == {"beta_dashboard": True}

    updated = await service.set_config(
        test_session,
        ConfigKeys.FEATURE_FLAGS,
        {"beta_dashboard": False},
        description="Updated flags",
        updated_by_id=actor.id,
    )
    await test_session.commit()

    assert updated.description == "Updated flags"
    assert updated.updated_by_id == actor.id
    assert await service.get_config(test_session, ConfigKeys.FEATURE_FLAGS) == {
        "beta_dashboard": False,
    }

    assert await service.delete_config(test_session, "missing") is False
    assert await service.delete_config(test_session, ConfigKeys.FEATURE_FLAGS) is True
    await test_session.commit()
    assert await service.get_config(test_session, ConfigKeys.FEATURE_FLAGS) is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_config_service_entity_type_defaults_setters_and_seed_defaults(test_session):
    service = ConfigService()
    actor = await _create_actor(test_session, email_prefix="entity-config-actor")

    default_config = await service.get_entity_type_config(test_session)
    assert default_config.allowed_root_types == DEFAULT_ENTITY_TYPE_CONFIG["allowed_root_types"]
    assert default_config.default_child_types.model_dump() == DEFAULT_ENTITY_TYPE_CONFIG["default_child_types"]

    updated_config = EntityTypeConfig(
        allowed_root_types=["organization", "workspace"],
        default_child_types=DefaultChildTypes(
            structural=["division"],
            access_group=["reviewers"],
        ),
    )

    persisted = await service.set_entity_type_config(
        test_session,
        updated_config,
        updated_by_id=actor.id,
    )
    await test_session.commit()

    assert persisted == updated_config
    loaded = await service.get_entity_type_config(test_session)
    assert loaded.allowed_root_types == ["organization", "workspace"]
    assert loaded.default_child_types.structural == ["division"]
    assert loaded.default_child_types.access_group == ["reviewers"]

    await service.seed_defaults(test_session, updated_by_id=actor.id)
    await test_session.commit()

    seeded = await service.get_entity_type_config(test_session)
    assert seeded.allowed_root_types == ["organization", "workspace"]
    assert seeded.default_child_types.structural == ["division"]
