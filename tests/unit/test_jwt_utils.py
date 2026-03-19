from __future__ import annotations

from datetime import timedelta, timezone

import pytest
from jose import jwt

from outlabs_auth.core.exceptions import TokenExpiredError, TokenInvalidError
from outlabs_auth.utils.jwt import (
    create_access_token,
    create_refresh_token,
    create_token_pair,
    decode_token_without_verification,
    get_token_expiration,
    is_token_expired,
    verify_token,
)


@pytest.mark.unit
def test_verify_token_supports_audience_and_no_audience_and_rejects_wrong_type():
    secret = "jwt-secret"
    refresh_token = create_refresh_token(
        {"sub": "user-123"},
        secret,
        audience="my-app",
    )
    audience_less_access_token = jwt.encode(
        {
            "sub": "user-123",
            "exp": 4102444800,
            "type": "access",
        },
        secret,
        algorithm="HS256",
    )

    verified_refresh = verify_token(
        refresh_token,
        secret,
        expected_type="refresh",
        audience="my-app",
    )
    verified_access = verify_token(
        audience_less_access_token,
        secret,
        expected_type="access",
    )

    assert verified_refresh["type"] == "refresh"
    assert verified_access["type"] == "access"

    with pytest.raises(TokenInvalidError) as exc_info:
        verify_token(refresh_token, secret, expected_type="access", audience="my-app")

    assert exc_info.value.details == {
        "expected_type": "access",
        "actual_type": "refresh",
    }


@pytest.mark.unit
def test_verify_token_raises_expired_and_invalid_errors():
    secret = "jwt-secret"
    expired_token = create_access_token(
        {"sub": "user-123"},
        secret,
        expires_delta=timedelta(seconds=-1),
        audience="my-app",
    )
    valid_token = create_access_token(
        {"sub": "user-123"},
        secret,
        audience="my-app",
    )

    with pytest.raises(TokenExpiredError) as expired:
        verify_token(expired_token, secret, expected_type="access", audience="my-app")
    assert expired.value.details == {"token_expired": True}

    with pytest.raises(TokenInvalidError) as invalid:
        verify_token(valid_token, "wrong-secret", expected_type="access", audience="my-app")
    assert "jwt_error" in invalid.value.details


@pytest.mark.unit
def test_decode_and_expiration_helpers_handle_invalid_missing_and_expired_tokens():
    secret = "jwt-secret"
    access_token = create_access_token(
        {"sub": "user-123"},
        secret,
        expires_delta=timedelta(minutes=5),
    )
    no_exp_token = create_access_token({"sub": "user-123"}, secret)
    no_exp_payload = decode_token_without_verification(no_exp_token)
    no_exp_payload.pop("exp", None)

    from jose import jwt

    tampered_token = access_token + "broken"
    no_exp_encoded = jwt.encode(no_exp_payload, secret, algorithm="HS256")
    expired_token = create_access_token(
        {"sub": "user-123"},
        secret,
        expires_delta=timedelta(seconds=-1),
    )

    decoded = decode_token_without_verification(access_token)
    expiration = get_token_expiration(access_token)

    assert decoded["sub"] == "user-123"
    assert expiration is not None
    assert expiration.tzinfo == timezone.utc
    assert get_token_expiration(no_exp_encoded) is None
    assert get_token_expiration(tampered_token) is None
    assert is_token_expired(expired_token) is True
    assert is_token_expired(access_token) is False
    assert is_token_expired(no_exp_encoded) is False

    with pytest.raises(TokenInvalidError):
        decode_token_without_verification("not-a-jwt")


@pytest.mark.unit
def test_create_token_pair_keeps_additional_claims_only_on_access_and_refresh_defaults():
    secret = "jwt-secret"
    refresh_token = create_refresh_token({"sub": "user-123"}, secret)
    access_token, paired_refresh = create_token_pair(
        user_id="user-123",
        secret_key=secret,
        additional_claims={"tenant_id": "tenant-abc", "role": "admin"},
        audience="my-app",
    )

    refresh_payload = decode_token_without_verification(refresh_token)
    access_payload = decode_token_without_verification(access_token)
    paired_refresh_payload = decode_token_without_verification(paired_refresh)

    assert refresh_payload["type"] == "refresh"
    assert refresh_payload["aud"] == "outlabs-auth"
    assert access_payload["tenant_id"] == "tenant-abc"
    assert access_payload["role"] == "admin"
    assert paired_refresh_payload["type"] == "refresh"
    assert paired_refresh_payload["aud"] == "my-app"
    assert "tenant_id" not in paired_refresh_payload
