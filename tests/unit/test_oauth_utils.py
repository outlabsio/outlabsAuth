from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from outlabs_auth.routers.oauth_utils import (
    encrypt_provider_token,
    get_oauth_user_info,
    oauth_client_uses_oidc,
    validate_oidc_nonce,
)


class FallbackOAuthClient:
    async def get_user_info(self, access_token: str):
        raise NotImplementedError

    def parse_id_token(self, id_token: str, verify: bool = False):
        raise NotImplementedError

    async def get_id_email(self, access_token: str):
        return ("provider-user-123", "fallback@example.com")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_oauth_user_info_falls_back_to_get_id_email():
    user_info = await get_oauth_user_info(
        FallbackOAuthClient(),
        {
            "access_token": "provider-access-token",
            "id_token": "provider-id-token",
        },
    )

    assert user_info.provider_user_id == "provider-user-123"
    assert user_info.email == "fallback@example.com"
    assert user_info.email_verified is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_oauth_user_info_rejects_missing_email_and_unsupported_provider():
    class MissingEmailOAuthClient(FallbackOAuthClient):
        async def get_id_email(self, access_token: str):
            return ("provider-user-456", None)

    with pytest.raises(HTTPException) as missing_email_exc_info:
        await get_oauth_user_info(
            MissingEmailOAuthClient(),
            {"access_token": "provider-access-token"},
        )

    assert missing_email_exc_info.value.status_code == 400
    assert missing_email_exc_info.value.detail == "Email not available from OAuth provider"

    class UnsupportedOAuthClient:
        pass

    with pytest.raises(HTTPException) as unsupported_exc_info:
        await get_oauth_user_info(
            UnsupportedOAuthClient(),
            {"access_token": "provider-access-token"},
        )

    assert unsupported_exc_info.value.status_code == 400
    assert unsupported_exc_info.value.detail == "OAuth provider user info is not supported"


@pytest.mark.unit
def test_encrypt_provider_token_handles_none_missing_cipher_and_cipher_success():
    auth_without_cipher = SimpleNamespace(oauth_token_cipher=None)

    assert encrypt_provider_token(auth_without_cipher, None) is None

    with pytest.raises(HTTPException) as exc_info:
        encrypt_provider_token(auth_without_cipher, "provider-token")

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "OAuth token encryption is not configured"

    auth_with_cipher = SimpleNamespace(oauth_token_cipher=SimpleNamespace(encrypt=lambda token: f"encrypted:{token}"))
    assert encrypt_provider_token(auth_with_cipher, "provider-token") == "encrypted:provider-token"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_oidc_nonce_requires_verified_matching_claim():
    client = SimpleNamespace(
        is_oidc=True,
        validate_id_token=lambda token: {"sub": "provider-user", "nonce": "expected"},
    )
    assert oauth_client_uses_oidc(client) is True

    await validate_oidc_nonce(
        client,
        {"id_token": "signed-provider-token"},
        "expected",
    )

    with pytest.raises(HTTPException, match="nonce"):
        await validate_oidc_nonce(
            client,
            {"id_token": "signed-provider-token"},
            "different",
        )

    with pytest.raises(HTTPException, match="required ID token"):
        await validate_oidc_nonce(client, {}, "expected")
