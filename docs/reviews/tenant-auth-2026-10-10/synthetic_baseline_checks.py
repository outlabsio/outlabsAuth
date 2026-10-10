"""Read-only synthetic callback/profile checks; no DB, server, or provider use."""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from fastapi import Response

import outlabs_auth.routers.oauth_associate as association
from outlabs_auth.core.config import AuthConfig
from outlabs_auth.models.sql.enums import UserStatus
from outlabs_auth.models.sql.social_account import SocialAccount
from outlabs_auth.models.sql.user import User
from outlabs_auth.oauth.state import generate_state_token
from outlabs_auth.authentication.strategy import JWTStrategy
from outlabs_auth.core.exceptions import AccountInactiveError
from outlabs_auth.services.auth import AuthService
from outlabs_auth.services.permission import PermissionService
from outlabs_auth.services.user import UserService
from outlabs_auth.utils.jwt import create_token_pair


class ScalarResult:
    def scalar_one_or_none(self):
        return None


async def association_case(status, changed_password):
    user_id = uuid4()
    issued_at = datetime.now(timezone.utc)
    user = User(
        id=user_id,
        email="member@example.com",
        status=status,
        auth_methods=["PASSWORD"],
        last_password_change=(issued_at + timedelta(seconds=1)) if changed_password else None,
    )
    auth = SimpleNamespace(
        config=SimpleNamespace(store_oauth_provider_tokens=False),
        deps=SimpleNamespace(require_auth=lambda **kwargs: lambda: None),
        uow=None,
        user_service=SimpleNamespace(
            get_user_by_id=AsyncMock(return_value=user),
            on_after_oauth_associate=AsyncMock(),
        ),
    )
    provider = SimpleNamespace(
        name="github",
        get_access_token=AsyncMock(return_value={"access_token": "synthetic-provider-token"}),
    )
    session = SimpleNamespace(
        execute=AsyncMock(side_effect=[ScalarResult(), ScalarResult()]),
        flush=AsyncMock(),
        commit=AsyncMock(),
        add=Mock(),
    )
    router = association.get_oauth_associate_router(
        provider, auth, "synthetic-review-secret-key-32-bytes", prefix="/associate",
        redirect_url="https://app.example.com/oauth/associate/callback",
    )
    callback = next(route.endpoint for route in router.routes if route.path == "/associate/callback")
    state = generate_state_token({"sub": str(user_id)}, "synthetic-review-secret-key-32-bytes", lifetime_seconds=600)
    # The mocked state/provider boundary means this checks account-work admission
    # after an otherwise valid state, not HTTP or cryptographic protections.
    with (
        patch.object(association, "consume_oauth_state", AsyncMock(return_value=SimpleNamespace(code_verifier="synthetic-pkce", nonce=None))),
        patch.object(association, "validate_oidc_nonce", AsyncMock()),
        patch.object(association, "get_oauth_user_info", AsyncMock(return_value=SimpleNamespace(provider_user_id="attacker-subject", email="attacker@example.com", email_verified=True))),
    ):
        await callback(
            request=SimpleNamespace(), response=Response(), session=session,
            code="synthetic-code", state=state, error=None, access_token_state=None,
        )
    inserted = session.add.call_args.args[0]
    assert isinstance(inserted, SocialAccount)
    assert inserted.user_id == user_id
    session.commit.assert_awaited_once()
    print(f"association: status={status.value}; password_changed_after_state={changed_password}; link_inserted=True; committed=True")


async def deleted_email_case():
    config = AuthConfig(secret_key="synthetic-review-secret-key-32-bytes")
    service = UserService(config)
    user = User(id=uuid4(), email="reserved@example.com", status=UserStatus.DELETED)
    service.get_by_id = AsyncMock(return_value=user)
    service.get_one = AsyncMock(return_value=None)
    service.update = AsyncMock()
    await service.update_user_fields(SimpleNamespace(), user.id, email="replacement@example.com")
    assert user.status == UserStatus.DELETED
    assert user.email == "replacement@example.com"
    print("profile: status=deleted; current_email_changed=True; prior_email_no_longer_in_unique_user_column=True")


async def restored_superuser_and_access_case():
    config = AuthConfig(secret_key="synthetic-review-secret-key-32-bytes")
    auth_service = AuthService(config)
    service = UserService(config, auth_service=auth_service)
    user = User(
        id=uuid4(), email="operator@example.com", status=UserStatus.ACTIVE,
        is_superuser=True, last_password_change=None,
    )
    service.get_by_id = AsyncMock(return_value=user)
    service.get_user_by_id = AsyncMock(return_value=user)
    service.update = AsyncMock()
    refresh_row = SimpleNamespace(is_revoked=False)
    result = SimpleNamespace(
        scalar_one_or_none=lambda: user,
        scalars=lambda: SimpleNamespace(all=lambda: [refresh_row]),
    )
    session = SimpleNamespace(execute=AsyncMock(return_value=result), flush=AsyncMock())
    access, _ = create_token_pair(str(user.id), config.secret_key, audience=config.jwt_audience)
    strategy = JWTStrategy(config.secret_key, audience=config.jwt_audience)
    assert await auth_service.get_current_user(session, access) is user
    assert await strategy.authenticate(access, user_service=service, session=session)
    await service.delete_user(session, user.id)
    assert refresh_row.is_revoked
    assert user.status == UserStatus.DELETED
    try:
        await auth_service.get_current_user(session, access)
    except AccountInactiveError:
        pass
    else:
        raise AssertionError("Deleted user unexpectedly authenticated")
    assert await strategy.authenticate(access, user_service=service, session=session) is None
    await service.restore_user(session, user.id)
    assert user.status == UserStatus.ACTIVE
    assert user.is_superuser
    assert refresh_row.is_revoked
    assert await auth_service.get_current_user(session, access) is user
    assert await strategy.authenticate(access, user_service=service, session=session)
    permissions = await PermissionService(config).get_user_permissions(session, user.id, user=user)
    assert permissions == ["*:*"]
    print("restore: retained_superuser=True; effective_permissions=all; revoked_refresh_stays_revoked=True")
    print("access: accepted_before_delete=True; denied_while_deleted=True; same_jwt_accepted_after_restore=True; service_and_strategy=True")


async def main():
    await association_case(UserStatus.ACTIVE, True)
    await association_case(UserStatus.SUSPENDED, False)
    await association_case(UserStatus.DELETED, False)
    await deleted_email_case()
    await restored_superuser_and_access_case()


asyncio.run(main())
