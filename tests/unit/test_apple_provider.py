from types import SimpleNamespace

import pytest

from outlabs_auth.oauth.exceptions import ProviderError
from outlabs_auth.oauth.providers.apple import AppleProvider


@pytest.fixture
def apple_provider() -> AppleProvider:
    return AppleProvider(
        client_id="com.example.service",
        team_id="TEAM123456",
        key_id="KEY123456",
        private_key="-----BEGIN PRIVATE KEY-----\nMIIBVwIBADANBgkqhkiG9w0BAQEFAASCAT8wggE7AgEAAkEA\n-----END PRIVATE KEY-----",
    )


@pytest.mark.unit
def test_parse_id_token_verifies_signature_and_normalizes_email_verified(
    apple_provider: AppleProvider,
    monkeypatch: pytest.MonkeyPatch,
):
    decode_calls: list[dict] = []

    class DummyJWKClient:
        def get_signing_key_from_jwt(self, token: str):
            assert token == "apple-id-token"
            return SimpleNamespace(key="signing-key")

    def fake_decode(token, key, algorithms, audience, issuer):
        decode_calls.append(
            {
                "token": token,
                "key": key,
                "algorithms": algorithms,
                "audience": audience,
                "issuer": issuer,
            }
        )
        return {
            "sub": "apple-user-123",
            "email": "apple@example.com",
            "email_verified": "true",
        }

    monkeypatch.setattr(apple_provider, "_get_jwk_client", lambda: DummyJWKClient())
    monkeypatch.setattr("outlabs_auth.oauth.providers.apple.jwt.decode", fake_decode)

    user_info = apple_provider.parse_id_token("apple-id-token", verify=True)

    assert user_info.provider_user_id == "apple-user-123"
    assert user_info.email == "apple@example.com"
    assert user_info.email_verified is True
    assert decode_calls == [
        {
            "token": "apple-id-token",
            "key": "signing-key",
            "algorithms": ["RS256"],
            "audience": "com.example.service",
            "issuer": "https://appleid.apple.com",
        }
    ]


@pytest.mark.unit
def test_parse_id_token_wraps_verification_failures(
    apple_provider: AppleProvider,
    monkeypatch: pytest.MonkeyPatch,
):
    class DummyJWKClient:
        def get_signing_key_from_jwt(self, token: str):
            return SimpleNamespace(key="signing-key")

    def failing_decode(*args, **kwargs):
        raise ValueError("signature verification failed")

    monkeypatch.setattr(apple_provider, "_get_jwk_client", lambda: DummyJWKClient())
    monkeypatch.setattr("outlabs_auth.oauth.providers.apple.jwt.decode", failing_decode)

    with pytest.raises(ProviderError) as exc_info:
        apple_provider.parse_id_token("apple-id-token", verify=True)

    assert exc_info.value.provider == "apple"
    assert exc_info.value.error == "invalid_id_token"
    assert "signature verification failed" in exc_info.value.error_description
