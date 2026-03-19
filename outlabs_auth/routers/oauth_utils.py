"""Shared helpers for OAuth routers."""

from typing import Any

from fastapi import HTTPException, status

from outlabs_auth.oauth.exceptions import ProviderError
from outlabs_auth.oauth.models import OAuthUserInfo


async def get_oauth_user_info(
    oauth_client: Any, token: dict[str, Any]
) -> OAuthUserInfo:
    """Load normalized OAuth user info, with Apple ID-token fallback."""
    get_user_info = getattr(oauth_client, "get_user_info", None)
    if callable(get_user_info):
        try:
            return await get_user_info(token["access_token"])
        except NotImplementedError:
            pass

    id_token = token.get("id_token")
    parse_id_token = getattr(oauth_client, "parse_id_token", None)
    if id_token and callable(parse_id_token):
        try:
            return parse_id_token(id_token, verify=True)
        except NotImplementedError:
            pass
        except ProviderError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid OAuth provider ID token",
            ) from exc

    get_id_email = getattr(oauth_client, "get_id_email", None)
    if callable(get_id_email):
        provider_user_id, email = await get_id_email(token["access_token"])
        if email is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email not available from OAuth provider",
            )
        return OAuthUserInfo(
            provider_user_id=provider_user_id,
            email=email,
            email_verified=False,
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="OAuth provider user info is not supported",
    )


def encrypt_provider_token(auth: Any, token: str | None) -> str | None:
    """Encrypt a provider token when token storage is enabled."""
    if token is None:
        return None
    cipher = getattr(auth, "oauth_token_cipher", None)
    if cipher is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OAuth token encryption is not configured",
        )
    return cipher.encrypt(token)
