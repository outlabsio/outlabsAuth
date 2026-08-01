"""
Unit regression tests for the security patches in docs/SECURITY_AUDIT_2026-06-10.md.

Fast, DB-free coverage of:
- SEC-1: refresh tokens must not authenticate as access tokens (JWTStrategy)
- SEC-3: delegation-containment matching logic (grantor_missing_permissions)
- SEC-6: JWT verification must require an `exp` claim
- SEC-8: rejected input (e.g. passwords) must not be echoed in 422 responses
"""

import httpx
import jwt as pyjwt
import pytest
from fastapi import FastAPI
from pydantic import BaseModel, Field, ValidationError

from outlabs_auth.authentication.strategy import JWTStrategy
from outlabs_auth.core.config import AuthConfig, MIN_HS_SECRET_KEY_LENGTH
from outlabs_auth.services.api_key import APIKeyService
from outlabs_auth.core.exceptions import TokenInvalidError
from outlabs_auth.fastapi import register_exception_handlers
from outlabs_auth.routers._authz_utils import grantor_missing_permissions
from outlabs_auth.utils.jwt import create_access_token, create_refresh_token, verify_token


# ---------------------------------------------------------------------------
# SEC-3 — delegation containment matching ("you can't grant what you don't hold")
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_grantor_wildcard_grants_everything():
    assert grantor_missing_permissions(["user:delete", "anything:weird"], {"*:*"}) == []


@pytest.mark.unit
def test_grantor_resource_wildcard_scopes_to_resource():
    assert grantor_missing_permissions(["post:read", "post:create"], {"post:*"}) == []
    # A resource wildcard for `post` must NOT cover `user:read`.
    assert grantor_missing_permissions(["user:read"], {"post:*"}) == ["user:read"]


@pytest.mark.unit
def test_grantor_exact_and_missing():
    granted = {"user:read", "user:update"}
    assert grantor_missing_permissions(["user:read"], granted) == []
    assert grantor_missing_permissions(["user:read", "user:delete"], granted) == ["user:delete"]


@pytest.mark.unit
def test_grantor_tree_is_superset_of_base():
    # Holding `entity:read_tree` lets you grant the non-scoped `entity:read`.
    assert grantor_missing_permissions(["entity:read"], {"entity:read_tree"}) == []


@pytest.mark.unit
def test_grantor_empty_grant_set_blocks_everything():
    assert grantor_missing_permissions(["user:read"], set()) == ["user:read"]


# ---------------------------------------------------------------------------
# SEC-1 — refresh tokens must not authenticate as access tokens
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_jwt_strategy_rejects_refresh_token():
    secret = "unit-test-secret-key-1234567890-abcdef"
    strategy = JWTStrategy(secret=secret, algorithm="HS256", audience="outlabs-auth")

    refresh = create_refresh_token({"sub": "user-1"}, secret_key=secret, algorithm="HS256")

    # The type check fires immediately after decode, before any user/session lookup,
    # so passing None services is sufficient to prove the rejection.
    result = await strategy.authenticate(refresh, user_service=None, session=None)
    assert result is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_jwt_strategy_rejects_token_without_exp():
    secret = "unit-test-secret-key-1234567890-abcdef"
    strategy = JWTStrategy(secret=secret, algorithm="HS256", audience="outlabs-auth")

    # Hand-craft an access-typed token that never expires.
    forged = pyjwt.encode(
        {"sub": "user-1", "type": "access", "aud": "outlabs-auth"},
        secret,
        algorithm="HS256",
    )
    result = await strategy.authenticate(forged, user_service=None, session=None)
    assert result is None


# ---------------------------------------------------------------------------
# SEC-6 — verify_token must require an `exp` claim
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_verify_token_rejects_token_without_exp():
    forged = pyjwt.encode({"sub": "user-1", "type": "access"}, "secret", algorithm="HS256")
    with pytest.raises(TokenInvalidError):
        verify_token(forged, "secret", algorithm="HS256")


@pytest.mark.unit
def test_verify_token_accepts_valid_access_token():
    token = create_access_token({"sub": "user-1"}, secret_key="secret", algorithm="HS256")
    payload = verify_token(
        token, "secret", algorithm="HS256", expected_type="access", audience="outlabs-auth"
    )
    assert payload["sub"] == "user-1"


# ---------------------------------------------------------------------------
# SEC-8 — rejected input must not be echoed back in validation errors
# ---------------------------------------------------------------------------

class _PasswordBody(BaseModel):
    password: str = Field(min_length=8)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validation_error_does_not_echo_submitted_password():
    app = FastAPI()
    register_exception_handlers(app)

    @app.post("/x")
    async def _x(body: _PasswordBody):  # pragma: no cover - never reached on invalid input
        return {"ok": True}

    secret = "nope"  # under min_length=8 -> triggers a 422 that would echo the input pre-fix
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.post("/x", json={"password": secret})

    assert resp.status_code == 422
    # The submitted secret must not appear anywhere in the response body.
    assert secret not in resp.text
    body = resp.json()
    for error in body["details"]["errors"]:
        assert "input" not in error
        assert "ctx" not in error


# ---------------------------------------------------------------------------
# SEC-9 — weak symmetric signing secrets are rejected at construction time
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_authconfig_rejects_short_hs_secret():
    with pytest.raises(ValidationError, match="at least 32 characters"):
        AuthConfig(secret_key="too-short", algorithm="HS256")


@pytest.mark.unit
def test_authconfig_accepts_sufficiently_long_hs_secret():
    cfg = AuthConfig(secret_key="x" * MIN_HS_SECRET_KEY_LENGTH, algorithm="HS256")
    assert len(cfg.secret_key) >= MIN_HS_SECRET_KEY_LENGTH


@pytest.mark.unit
def test_authconfig_exempts_asymmetric_algorithm_from_length_rule():
    # RS*/ES* use PEM keys; the HS minimum-length rule must not apply to them.
    cfg = AuthConfig(secret_key="-----BEGIN PRIVATE KEY-----short", algorithm="RS256")
    assert cfg.algorithm == "RS256"


# ---------------------------------------------------------------------------
# SEC-11 — Apple ID-token parsing verifies the signature by default
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_apple_parse_id_token_defaults_to_verify_true():
    import inspect

    from outlabs_auth.oauth.providers.apple import AppleProvider

    # A caller that omits `verify` must get signature verification, not an
    # attacker-controllable unverified decode (account-takeover footgun).
    sig = inspect.signature(AppleProvider.parse_id_token)
    assert sig.parameters["verify"].default is True


# ---------------------------------------------------------------------------
# SEC-13 — integration principals fail CLOSED on empty allowed-scopes
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_principal_scopes_fail_closed_on_empty():
    # Integration principals have no owner to bound them: an empty allow-list grants nothing.
    assert APIKeyService.principal_scopes_allow_permission([], "user:read") is False
    assert APIKeyService.principal_scopes_allow_permission(["user:read"], "user:read") is True
    assert APIKeyService.principal_scopes_allow_permission(["*:*"], "anything:goes") is True
    assert APIKeyService.principal_scopes_allow_permission(["post:read"], "user:read") is False


@pytest.mark.unit
def test_owner_narrowing_scopes_stay_permissive_on_empty():
    # User-key `scopes` are an owner-NARROWING filter: empty = no narrowing (owner-bounded).
    assert APIKeyService.scopes_allow_permission([], "user:read") is True


@pytest.mark.unit
def test_snapshot_integration_principal_with_empty_scopes_denies():
    svc = APIKeyService(config=AuthConfig(secret_key="x" * 32))
    snapshot = {
        "integration_principal_id": "ip-1",
        "scopes": [],
        "principal_allowed_scopes": [],
        "effective_permissions": ["*:*"],
    }
    assert svc.auth_snapshot_allows_permission(snapshot, "user:read") is False


@pytest.mark.unit
def test_snapshot_user_key_empty_scopes_uses_owner_permissions():
    svc = APIKeyService(config=AuthConfig(secret_key="x" * 32))
    # A user-owned key (no integration_principal_id) with empty scopes acts as the owner.
    snapshot = {"scopes": [], "effective_permissions": ["user:read"]}
    assert svc.auth_snapshot_allows_permission(snapshot, "user:read") is True
    assert svc.auth_snapshot_allows_permission(snapshot, "user:delete") is False
