"""Shared helpers for OAuth routers."""

import hmac
import inspect
from typing import Any, Optional, cast

from fastapi import HTTPException, status
import jwt

from outlabs_auth.oauth.exceptions import ProviderError
from outlabs_auth.oauth.models import OAuthUserInfo


def oauth_client_uses_oidc(oauth_client: Any) -> bool:
    """Return whether a client has an OIDC ID-token validation contract."""
    return bool(getattr(oauth_client, "openid_configuration", None)) or bool(getattr(oauth_client, "is_oidc", False))


async def validate_oidc_nonce(
    oauth_client: Any,
    token: dict[str, Any],
    expected_nonce: Optional[str],
) -> None:
    """Cryptographically validate an OIDC ID token and its flow nonce."""
    if expected_nonce is None:
        return

    id_token = token.get("id_token")
    if not isinstance(id_token, str) or not id_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth provider did not return the required ID token",
        )

    claims: Any = None
    configuration = getattr(oauth_client, "openid_configuration", None)
    if isinstance(configuration, dict):
        try:
            issuer = configuration["issuer"]
            header = jwt.get_unverified_header(id_token)
            algorithm = header.get("alg")
            key_id = header.get("kid")
            allowed_algorithms = configuration.get("id_token_signing_alg_values_supported", [])
            if not algorithm or (allowed_algorithms and algorithm not in allowed_algorithms):
                raise ValueError("Unsupported ID-token signing algorithm")

            jwks_uri = configuration["jwks_uri"]
            async with oauth_client.get_httpx_client() as client:
                response = await client.get(jwks_uri)
                response.raise_for_status()
                jwk_set = jwt.PyJWKSet.from_dict(response.json())

            signing_key = next(key.key for key in jwk_set.keys if key.key_id == key_id)
            claims = jwt.decode(
                id_token,
                signing_key,
                algorithms=[algorithm],
                audience=oauth_client.client_id,
                issuer=issuer,
                options={"require": ["exp", "iat", "iss", "aud", "sub", "nonce"]},
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid OAuth provider ID token",
            ) from exc
    else:
        validator = getattr(oauth_client, "validate_id_token", None)
        if callable(validator):
            try:
                claims = validator(id_token)
                if inspect.isawaitable(claims):
                    claims = await claims
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid OAuth provider ID token",
                ) from exc
        else:
            parser = getattr(oauth_client, "parse_id_token", None)
            if callable(parser):
                try:
                    parsed = parser(id_token, verify=True)
                    if inspect.isawaitable(parsed):
                        parsed = await parsed
                    claims = getattr(parsed, "provider_data", None)
                except Exception as exc:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid OAuth provider ID token",
                    ) from exc

    if not isinstance(claims, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth client cannot validate OIDC ID tokens",
        )

    actual_nonce = claims.get("nonce")
    if not isinstance(actual_nonce, str) or not hmac.compare_digest(actual_nonce, expected_nonce):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth provider ID-token nonce",
        )


async def get_oauth_user_info(oauth_client: Any, token: dict[str, Any]) -> OAuthUserInfo:
    """Load normalized OAuth user info, with Apple ID-token fallback."""
    get_user_info = getattr(oauth_client, "get_user_info", None)
    if callable(get_user_info):
        try:
            return cast(OAuthUserInfo, await get_user_info(token["access_token"]))
        except NotImplementedError:
            pass

    id_token = token.get("id_token")
    parse_id_token = getattr(oauth_client, "parse_id_token", None)
    if id_token and callable(parse_id_token):
        try:
            return cast(OAuthUserInfo, parse_id_token(id_token, verify=True))
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
    return cast(Optional[str], cipher.encrypt(token))
