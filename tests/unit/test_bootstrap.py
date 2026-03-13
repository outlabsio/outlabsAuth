from __future__ import annotations

import pytest
from sqlalchemy import select

from outlabs_auth.bootstrap import (
    get_system_permission_catalog,
    bootstrap_superuser,
    seed_system_records,
)
from outlabs_auth.core.config import AuthConfig
from outlabs_auth.models.sql.permission import Permission
from outlabs_auth.models.sql.system_config import SystemConfig
from outlabs_auth.models.sql.user import User
from outlabs_auth.services.config import ConfigService
from outlabs_auth.services.permission import PermissionService
from outlabs_auth.services.user import UserService


@pytest.mark.unit
@pytest.mark.asyncio
async def test_seed_system_records_is_idempotent(test_session, test_secret_key):
    config = AuthConfig(secret_key=test_secret_key, enable_token_cleanup=False)
    permission_service = PermissionService(config)
    config_service = ConfigService()

    first = await seed_system_records(
        test_session,
        permission_service=permission_service,
        config_service=config_service,
    )
    await test_session.commit()

    second = await seed_system_records(
        test_session,
        permission_service=permission_service,
        config_service=config_service,
    )
    await test_session.commit()

    permissions = (await test_session.execute(select(Permission))).scalars().all()
    config_rows = (await test_session.execute(select(SystemConfig))).scalars().all()

    assert first.permissions_created == len(get_system_permission_catalog())
    assert first.permissions_existing == 0
    assert first.config_seeded is True
    assert second.permissions_created == 0
    assert second.permissions_existing == len(get_system_permission_catalog())
    assert second.config_seeded is False
    assert len(permissions) == len(get_system_permission_catalog())
    assert len(config_rows) == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_bootstrap_superuser_creates_first_user_and_is_idempotent(
    test_session, test_secret_key
):
    config = AuthConfig(secret_key=test_secret_key, enable_token_cleanup=False)
    user_service = UserService(config)

    created = await bootstrap_superuser(
        test_session,
        user_service=user_service,
        email="admin@example.com",
        password="BootstrapPass123!",
        first_name="Admin",
        last_name="User",
    )
    await test_session.commit()

    existing = await bootstrap_superuser(
        test_session,
        user_service=user_service,
        email="admin@example.com",
        password="BootstrapPass123!",
    )

    users = (await test_session.execute(select(User))).scalars().all()

    assert created.status == "created"
    assert existing.status == "existing"
    assert len(users) == 1
    assert users[0].is_superuser is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_bootstrap_superuser_refuses_when_other_user_exists(
    test_session, test_secret_key
):
    config = AuthConfig(secret_key=test_secret_key, enable_token_cleanup=False)
    user_service = UserService(config)

    await user_service.create_user(
        test_session,
        email="member@example.com",
        password="BootstrapPass123!",
    )
    await test_session.commit()

    with pytest.raises(RuntimeError, match="users already exist"):
        await bootstrap_superuser(
            test_session,
            user_service=user_service,
            email="admin@example.com",
            password="BootstrapPass123!",
        )
