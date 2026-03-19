from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest

from outlabs_auth.oauth.security import (
    build_authorization_url,
    constant_time_compare,
    generate_nonce,
    generate_pkce_pair,
    generate_state,
    verify_pkce,
)


@pytest.mark.unit
def test_generate_state_and_nonce_return_distinct_urlsafe_tokens():
    state = generate_state()
    nonce = generate_nonce()

    assert isinstance(state, str)
    assert isinstance(nonce, str)
    assert len(state) >= 40
    assert len(nonce) >= 40
    assert state != nonce


@pytest.mark.unit
def test_generate_pkce_pair_supports_s256_and_verification():
    verifier, challenge = generate_pkce_pair("S256")

    assert verifier
    assert challenge
    assert verifier != challenge
    assert verify_pkce(verifier, challenge, "S256") is True
    assert verify_pkce(f"{verifier}x", challenge, "S256") is False


@pytest.mark.unit
def test_generate_pkce_pair_supports_plain_method():
    verifier, challenge = generate_pkce_pair("plain")

    assert challenge == verifier
    assert verify_pkce(verifier, challenge, "plain") is True
    assert verify_pkce("mismatch", challenge, "plain") is False


@pytest.mark.unit
def test_generate_pkce_pair_rejects_unknown_method():
    with pytest.raises(ValueError, match="PKCE method must be 'S256' or 'plain'"):
        generate_pkce_pair("SHA512")


@pytest.mark.unit
def test_build_authorization_url_includes_security_and_extra_params():
    url = build_authorization_url(
        base_url="https://provider.example.com/oauth/authorize",
        client_id="client-id",
        redirect_uri="https://app.example.com/callback",
        scope="openid email profile",
        state="state-123",
        code_challenge="challenge-123",
        nonce="nonce-123",
        access_type="offline",
        prompt="consent",
    )

    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert parsed.netloc == "provider.example.com"
    assert query == {
        "client_id": ["client-id"],
        "redirect_uri": ["https://app.example.com/callback"],
        "response_type": ["code"],
        "scope": ["openid email profile"],
        "state": ["state-123"],
        "code_challenge": ["challenge-123"],
        "code_challenge_method": ["S256"],
        "nonce": ["nonce-123"],
        "access_type": ["offline"],
        "prompt": ["consent"],
    }


@pytest.mark.unit
def test_constant_time_compare_matches_equal_and_unequal_strings():
    assert constant_time_compare("same-value", "same-value") is True
    assert constant_time_compare("same-value", "different-value") is False
