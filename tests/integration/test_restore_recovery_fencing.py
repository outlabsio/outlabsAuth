"""A restored epoch is insufficient; external signing-key rotation is required."""

from uuid import uuid4

import pytest
from sqlalchemy import text

from outlabs_auth.authentication.strategy import JWTStrategy
from outlabs_auth.core.exceptions import TokenInvalidError, RefreshTokenInvalidError
from outlabs_auth.models.sql.user import User
from outlabs_auth.services.auth import AuthService
from outlabs_auth.services.user import UserService
from outlabs_auth.utils.jwt import create_token_pair


@pytest.mark.asyncio
async def test_rewound_backup_epoch_requires_external_signing_key_rotation(test_session, auth_config):
    config = auth_config.model_copy(update={"store_refresh_tokens": False})
    user = User(email=f"restore-{uuid4().hex}@example.test")
    test_session.add(user)
    await test_session.commit()
    access, refresh = create_token_pair(
        user_id=str(user.id),
        secret_key=config.secret_key,
        audience=config.jwt_audience,
        additional_claims={"security_epoch": 0},
    )
    auth = AuthService(config)
    assert await auth.get_current_user(test_session, access) is user
    await auth.revoke_all_user_tokens(test_session, user.id)
    await test_session.commit()
    with pytest.raises(TokenInvalidError):
        await auth.get_current_user(test_session, access)
    # Rehearse the relevant backup rewind, keeping admission closed. Restoring
    # a backup also rewinds this row; the baseline cannot detect that alone.
    await test_session.execute(text("UPDATE users SET session_security_epoch=NULL WHERE id=:id"), {"id": user.id})
    await test_session.commit()
    await test_session.refresh(user)
    assert await auth.get_current_user(test_session, access) is user
    recovered = config.model_copy(update={"secret_key": "fresh-external-recovery-signing-key-01234567890123456789"})
    fenced = AuthService(recovered)
    with pytest.raises(TokenInvalidError):
        await fenced.get_current_user(test_session, access)
    with pytest.raises(RefreshTokenInvalidError):
        await fenced.refresh_access_token(test_session, refresh)
    strategy = JWTStrategy(secret=recovered.secret_key, audience=recovered.jwt_audience)
    assert await strategy.authenticate(access, user_service=UserService(recovered), session=test_session) is None
    new_access, _ = create_token_pair(
        user_id=str(user.id),
        secret_key=recovered.secret_key,
        audience=recovered.jwt_audience,
        additional_claims={"security_epoch": 0},
    )
    assert await fenced.get_current_user(test_session, new_access) is user
