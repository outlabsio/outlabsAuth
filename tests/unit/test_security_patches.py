"""
Unit regression tests for the security controls in docs/SECURITY_AUDIT_2026-08-02.md.

Fast, DB-free coverage of:
- SEC-1: refresh tokens must not authenticate as access tokens (JWTStrategy)
- SEC-3: delegation-containment matching logic (grantor_missing_permissions)
- SEC-6: JWT verification must require an `exp` claim
- SEC-8: rejected input (e.g. passwords) must not be echoed in 422 responses
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import jwt as pyjwt
import pytest
from fastapi import FastAPI
from pydantic import BaseModel, Field, ValidationError

from outlabs_auth.authentication.strategy import JWTStrategy
from outlabs_auth.core.auth import OutlabsAuth
from outlabs_auth.core.config import AuthConfig, MIN_HS_SECRET_KEY_LENGTH
from outlabs_auth.core.exceptions import (
    AuthenticationInfrastructureError,
    PermissionDeniedError,
    TokenInvalidError,
)
from outlabs_auth.dependencies import AuthDeps
from outlabs_auth.fastapi import register_exception_handlers
from outlabs_auth.routers._authz_utils import (
    grantor_missing_permissions,
    require_can_delegate_permissions,
    require_can_delegate_roles,
)
from outlabs_auth.services.api_key import APIKeyService
from outlabs_auth.utils.ip import ip_matches_rules, normalize_ip_rules
from outlabs_auth.utils.jwt import (
    create_access_token,
    create_refresh_token,
    create_token_pair,
    verify_token,
)
from outlabs_auth.utils.rate_limit import check_login_ip_rate_limit

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


@pytest.mark.unit
@pytest.mark.asyncio
async def test_delegation_containment_uses_target_entity_context():
    actor_id = uuid4()
    entity_id = uuid4()
    permission_service = SimpleNamespace(get_effective_permission_names=AsyncMock(return_value={"user:read"}))
    auth = SimpleNamespace(permission_service=permission_service)
    session = AsyncMock()

    await require_can_delegate_permissions(
        session,
        auth=auth,
        actor_user_id=actor_id,
        permission_names=["user:read"],
        entity_id=entity_id,
    )
    permission_service.get_effective_permission_names.assert_awaited_once_with(
        session,
        actor_id,
        entity_id=entity_id,
        candidate_permission_names=["user:read"],
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_delegation_containment_rejects_cross_scope_grant():
    auth = SimpleNamespace(
        permission_service=SimpleNamespace(get_effective_permission_names=AsyncMock(return_value=set()))
    )
    with pytest.raises(PermissionDeniedError, match="cannot grant"):
        await require_can_delegate_permissions(
            AsyncMock(),
            auth=auth,
            actor_user_id=uuid4(),
            permission_names=["user:delete"],
            entity_id=uuid4(),
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_role_containment_includes_target_entity_type_overrides():
    entity_id = uuid4()
    session = AsyncMock()
    session.get.return_value = SimpleNamespace(entity_type="team")
    auth = SimpleNamespace(
        role_service=SimpleNamespace(
            get_role_permission_names=AsyncMock(return_value=["user:read"]),
            get_role_entity_type_permission_names=AsyncMock(return_value={"team": ["user:delete"]}),
        ),
        permission_service=SimpleNamespace(get_effective_permission_names=AsyncMock(return_value={"user:read"})),
    )

    with pytest.raises(PermissionDeniedError) as exc_info:
        await require_can_delegate_roles(
            session,
            auth=auth,
            actor_user_id=uuid4(),
            role_ids=[uuid4()],
            entity_id=entity_id,
        )

    assert exc_info.value.details["missing_permissions"] == ["user:delete"]


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
    secret = "unit-verify-secret-1234567890-abcdef"
    forged = pyjwt.encode({"sub": "user-1", "type": "access"}, secret, algorithm="HS256")
    with pytest.raises(TokenInvalidError):
        verify_token(forged, secret, algorithm="HS256")


@pytest.mark.unit
def test_verify_token_accepts_valid_access_token():
    secret = "unit-verify-secret-1234567890-abcdef"
    token = create_access_token({"sub": "user-1"}, secret_key=secret, algorithm="HS256")
    payload = verify_token(
        token,
        secret,
        algorithm="HS256",
        expected_type="access",
        audience="outlabs-auth",
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


@pytest.mark.unit
def test_authconfig_rejects_known_secret_placeholder():
    with pytest.raises(ValidationError, match="known placeholder"):
        AuthConfig(
            secret_key="CHANGE-ME-generate-with-secrets.token_urlsafe(48)",
            algorithm="HS256",
        )


@pytest.mark.unit
def test_refresh_token_carries_absolute_session_expiry():
    secret = "absolute-session-test-secret-key-123456789"
    session_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    _, refresh = create_token_pair(
        "user-1",
        secret,
        refresh_token_expire_days=30,
        session_expires_at=session_expires_at,
    )
    payload = verify_token(
        refresh,
        secret,
        expected_type="refresh",
        audience="outlabs-auth",
    )
    assert payload["session_exp"] == int(session_expires_at.timestamp())
    assert payload["exp"] <= payload["session_exp"]


@pytest.mark.unit
def test_ip_allow_list_accepts_addresses_and_cidr_fail_closed():
    rules = normalize_ip_rules(["192.0.2.7", "10.20.0.0/16", "2001:db8::/32"])
    assert rules == ["192.0.2.7", "10.20.0.0/16", "2001:db8::/32"]
    assert ip_matches_rules("192.0.2.7", rules)
    assert ip_matches_rules("10.20.5.9", rules)
    assert ip_matches_rules("2001:db8::42", rules)
    assert not ip_matches_rules("10.21.5.9", rules)
    assert not ip_matches_rules("not-an-ip", rules)


@pytest.mark.unit
def test_api_key_snapshot_paths_share_cidr_and_missing_ip_fail_closed():
    snapshot = {"ip_whitelist": ["10.20.0.0/16"]}
    allowed_request = SimpleNamespace(client=SimpleNamespace(host="10.20.5.9"))
    denied_request = SimpleNamespace(client=SimpleNamespace(host="10.21.5.9"))
    missing_client_request = SimpleNamespace(client=None)

    assert AuthDeps._snapshot_ip_allowed(snapshot, allowed_request) is True
    assert AuthDeps._snapshot_ip_allowed(snapshot, denied_request) is False
    assert AuthDeps._snapshot_ip_allowed(snapshot, missing_client_request) is False
    assert OutlabsAuth._api_key_snapshot_ip_allowed(snapshot, "10.20.5.9") is True
    assert OutlabsAuth._api_key_snapshot_ip_allowed(snapshot, "10.21.5.9") is False
    assert OutlabsAuth._api_key_snapshot_ip_allowed(snapshot, None) is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_login_ip_rate_limit_uses_redis_counter():
    redis = SimpleNamespace(
        is_available=True,
        increment_with_ttl=AsyncMock(side_effect=[1, 2, 3]),
    )
    ip = f"192.0.2.{uuid4().int % 200 + 1}"
    assert await check_login_ip_rate_limit(ip, redis, max_requests=2) == (False, 0)
    assert await check_login_ip_rate_limit(ip, redis, max_requests=2) == (False, 0)
    limited, retry_after = await check_login_ip_rate_limit(ip, redis, max_requests=2, window_seconds=60)
    assert limited is True
    assert retry_after == 60


@pytest.mark.unit
@pytest.mark.asyncio
async def test_login_ip_rate_limit_fails_closed_when_configured_redis_is_down():
    redis = SimpleNamespace(is_available=False)
    with pytest.raises(AuthenticationInfrastructureError):
        await check_login_ip_rate_limit(
            "192.0.2.250",
            redis,
            redis_required=True,
            failure_mode="fail_closed",
        )


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
