from __future__ import annotations

import json
import os
import stat
import time
from pathlib import Path

import httpx
import pytest
from click.testing import CliRunner

import outlabs_auth.cli_support.abac_commands as abac_commands
import outlabs_auth.cli_support.account_commands as account_commands
import outlabs_auth.cli_support.api_commands as api_commands
import outlabs_auth.cli_support.api_key_commands as api_key_commands
import outlabs_auth.cli_support.auth_commands as auth_commands
import outlabs_auth.cli_support.declarative_commands as declarative_commands
import outlabs_auth.cli_support.entity_commands as entity_commands
import outlabs_auth.cli_support.integration_commands as integration_commands
import outlabs_auth.cli_support.membership_commands as membership_commands
import outlabs_auth.cli_support.permission_commands as permission_commands
import outlabs_auth.cli_support.remote_commands as remote_commands
import outlabs_auth.cli_support.role_commands as role_commands
import outlabs_auth.cli_support.user_admin_commands as user_admin_commands
import outlabs_auth.cli_support.user_inspection_commands as user_inspection_commands
from outlabs_auth.cli import _redact_database_url, main as cli_main
from outlabs_auth.cli_support.client import RemoteClient, RemoteTarget, resolve_remote_target
from outlabs_auth.cli_support.contexts import (
    ContextProfile,
    ContextStore,
    normalize_api_prefix,
    normalize_base_url,
)
from outlabs_auth.cli_support.credentials import CredentialStore, StoredSession
from outlabs_auth.cli_support.declarative import (
    apply_plan,
    build_plan,
    validate_manifest,
    validate_plan,
)
from outlabs_auth.cli_support.runtime import CliError, CliRuntime


def _json_output(result) -> dict:
    return json.loads(result.output)


def _target(**overrides) -> RemoteTarget:
    values = {
        "name": "test",
        "base_url": "https://auth.example.test",
        "api_prefix": "/v1",
        "app": None,
        "credential_type": "bearer",
        "credential_env": "TEST_OUTLABS_TOKEN",
        "timeout": 2.0,
    }
    values.update(overrides)
    return RemoteTarget(**values)


def _patch_resource_client(monkeypatch: pytest.MonkeyPatch, module, handler) -> RemoteClient:
    target = _target()
    client = RemoteClient(target, transport=httpx.MockTransport(handler))
    monkeypatch.setattr(module, "remote_client", lambda: (target, client))
    return client


def test_missing_database_url_honors_global_json_contract(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    result = CliRunner().invoke(cli_main, ["--output", "json", "doctor"])

    assert result.exit_code == 2
    payload = _json_output(result)
    assert payload["schema_version"] == "outlabs-auth.cli/v1"
    assert payload["ok"] is False
    assert payload["command"] == "doctor"
    assert payload["error"]["code"] == "DATABASE_URL_MISSING"


def test_legacy_json_request_still_gets_structured_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    result = CliRunner().invoke(cli_main, ["doctor", "--format", "json"])

    assert result.exit_code == 2
    payload = _json_output(result)
    assert payload["ok"] is False
    assert payload["command"] == "doctor"


def test_namespaced_alias_reports_full_safe_command_path(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    result = CliRunner().invoke(cli_main, ["--output", "json", "ops", "doctor"])

    assert result.exit_code == 2
    assert _json_output(result)["command"] == "ops.doctor"


def test_invalid_schema_is_structured_without_traceback(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:secret@localhost/db")
    result = CliRunner().invoke(
        cli_main,
        ["--output", "json", "--schema", "bad-schema", "doctor"],
    )

    assert result.exit_code == 2
    payload = _json_output(result)
    assert payload["error"]["code"] == "INVALID_SCHEMA"
    assert "Traceback" not in result.output
    assert "secret" not in result.output


def test_click_parser_errors_follow_json_contract_and_do_not_echo_secrets():
    result = CliRunner().invoke(
        cli_main,
        [
            "--output",
            "json",
            "bootstrap-admin",
            "--email",
            "admin@example.test",
            "--password",
            "do-not-echo-this",
            "--unknown-option",
        ],
    )

    assert result.exit_code == 2
    payload = _json_output(result)
    assert payload["error"]["code"] == "CLI_USAGE"
    assert payload["command"] == "bootstrap-admin"
    assert "do-not-echo-this" not in result.output


def test_database_url_redaction_covers_sensitive_query_values():
    redacted = _redact_database_url("postgresql+asyncpg://user:password@db/app?ssl=require&token=abc123&api_key=xyz")

    assert "password" not in redacted
    assert "abc123" not in redacted
    assert "xyz" not in redacted
    assert "ssl=require" in redacted


def test_downgrade_dry_run_needs_no_database_connection():
    result = CliRunner().invoke(
        cli_main,
        ["--output", "json", "downgrade", "--revision", "-1", "--dry-run"],
    )

    assert result.exit_code == 0
    payload = _json_output(result)
    assert payload["command"] == "db.downgrade"
    assert payload["changed"] is False
    assert payload["result"]["dry_run"] is True


def test_non_interactive_downgrade_requires_explicit_yes(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:secret@localhost/db")
    result = CliRunner().invoke(
        cli_main,
        ["--output", "json", "--non-interactive", "downgrade"],
    )

    assert result.exit_code == 2
    payload = _json_output(result)
    assert payload["error"]["code"] == "INTERACTION_REQUIRED"
    assert "secret" not in result.output


def test_bootstrap_admin_accepts_only_one_secret_source():
    result = CliRunner().invoke(
        cli_main,
        [
            "--output",
            "json",
            "bootstrap-admin",
            "--email",
            "admin@example.test",
            "--password",
            "one-secret",
            "--password-stdin",
        ],
        input="another-secret\n",
    )

    assert result.exit_code == 2
    assert _json_output(result)["error"]["code"] == "CONFLICTING_SECRET_INPUT"
    assert "one-secret" not in result.output
    assert "another-secret" not in result.output


def test_context_store_round_trip_is_atomic_and_secret_free(tmp_path: Path):
    path = tmp_path / "nested" / "config.json"
    store = ContextStore(path).load()
    store.add(
        ContextProfile(
            name="production",
            base_url="https://api.example.test",
            api_prefix="/iam",
            credential_type="bearer",
            credential_env="PROD_AUTH_TOKEN",
        ),
        activate=True,
        force=False,
    )

    loaded = ContextStore(path).load()
    assert loaded.active == "production"
    assert loaded.get().api_prefix == "/iam"
    contents = path.read_text()
    assert "PROD_AUTH_TOKEN" in contents
    assert "access_token" not in contents
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_credential_store_is_owner_only_and_target_bound(tmp_path: Path):
    path = tmp_path / "state" / "credentials.json"
    store = CredentialStore(path).load()
    session = StoredSession(
        profile="production",
        base_url="https://api.example.test",
        api_prefix="/v1",
        access_token="access-secret",
        refresh_token="refresh-secret",
        expires_at=time.time() + 900,
        created_at=time.time(),
        email="admin@example.test",
    )
    store.put(session)

    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert (
        CredentialStore(path)
        .load()
        .get(
            "production",
            base_url="https://api.example.test",
            api_prefix="/v1",
        )
        == session
    )

    with pytest.raises(CliError) as raised:
        CredentialStore(path).load().get(
            "production",
            base_url="https://attacker.example.test",
            api_prefix="/v1",
        )

    assert raised.value.code == "CREDENTIAL_TARGET_MISMATCH"
    assert "access-secret" not in str(raised.value.details)
    assert "refresh-secret" not in str(raised.value.details)


def test_credential_store_rejects_permissive_file_mode(tmp_path: Path):
    path = tmp_path / "credentials.json"
    path.write_text('{"version": 1, "sessions": {}}')
    path.chmod(0o644)

    with pytest.raises(CliError) as raised:
        CredentialStore(path).load()

    assert raised.value.code == "INSECURE_CREDENTIAL_STORE"


def test_context_cli_add_and_current_use_json_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("OUTLABS_AUTH_CONFIG", str(tmp_path / "config.json"))
    runner = CliRunner()

    added = runner.invoke(
        cli_main,
        [
            "--output",
            "json",
            "context",
            "add",
            "local",
            "--base-url",
            "http://127.0.0.1:8004",
            "--api-prefix",
            "v1",
        ],
    )
    current = runner.invoke(cli_main, ["--output", "json", "context", "current"])

    assert added.exit_code == 0
    assert _json_output(added)["changed"] is True
    assert current.exit_code == 0
    assert _json_output(current)["result"]["profile"] == "local"
    assert _json_output(current)["result"]["api_prefix"] == "/v1"


def test_auth_login_stores_session_without_disclosing_tokens(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    config_path = tmp_path / "config.json"
    credentials_path = tmp_path / "credentials.json"
    monkeypatch.setenv("OUTLABS_AUTH_CONFIG", str(config_path))
    monkeypatch.setenv("OUTLABS_AUTH_CREDENTIALS", str(credentials_path))
    ContextStore(config_path).add(
        ContextProfile(name="local", base_url="http://127.0.0.1:8004", api_prefix="/v1"),
        activate=True,
        force=False,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/auth/login"
        assert json.loads(request.content)["password"] == "human-password"
        return httpx.Response(
            200,
            json={
                "access_token": "access-secret",
                "refresh_token": "refresh-secret",
                "token_type": "bearer",
                "expires_in": 900,
            },
        )

    monkeypatch.setattr(
        auth_commands,
        "RemoteClient",
        lambda target: RemoteClient(
            target,
            transport=httpx.MockTransport(handler),
            credential_store=CredentialStore(credentials_path).load(),
        ),
    )
    result = CliRunner().invoke(
        cli_main,
        ["--output", "json", "auth", "login", "--email", "admin@example.test", "--password-stdin"],
        input="human-password\n",
    )

    assert result.exit_code == 0
    payload = _json_output(result)
    assert payload["command"] == "auth.login"
    assert "access-secret" not in result.output
    assert "refresh-secret" not in result.output
    assert "human-password" not in result.output
    stored = CredentialStore(credentials_path).load().get("local")
    assert stored is not None
    assert stored.access_token == "access-secret"
    assert stored.refresh_token == "refresh-secret"


def test_auth_login_non_interactive_requires_safe_password_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    config_path = tmp_path / "config.json"
    monkeypatch.setenv("OUTLABS_AUTH_CONFIG", str(config_path))
    monkeypatch.delenv("OUTLABS_AUTH_PASSWORD", raising=False)
    ContextStore(config_path).add(
        ContextProfile(name="local", base_url="http://127.0.0.1:8004"),
        activate=True,
        force=False,
    )

    result = CliRunner().invoke(
        cli_main,
        ["--output", "json", "--non-interactive", "auth", "login", "--email", "admin@example.test"],
    )

    assert result.exit_code == 2
    assert _json_output(result)["error"]["code"] == "LOGIN_PASSWORD_MISSING"


def test_context_rejects_insecure_non_local_http():
    with pytest.raises(CliError) as raised:
        normalize_base_url("http://api.example.test")

    assert raised.value.code == "INSECURE_BASE_URL"


@pytest.mark.parametrize(
    "url",
    [
        "https://api.example.test?token=must-not-be-stored",
        "https://api.example.test#fragment",
    ],
)
def test_context_rejects_query_parameters_and_fragments(url: str):
    with pytest.raises(CliError) as raised:
        normalize_base_url(url)

    assert raised.value.code == "INVALID_BASE_URL"


def test_context_store_rejects_malformed_context_entry(tmp_path: Path):
    path = tmp_path / "config.json"
    path.write_text('{"version": 1, "active": null, "contexts": {"bad": "not-an-object"}}')

    with pytest.raises(CliError) as raised:
        ContextStore(path).load()

    assert raised.value.code == "INVALID_CONTEXT_CONFIG"
    assert raised.value.details["path"] == str(path)


def test_api_prefix_normalization():
    assert normalize_api_prefix("v1/") == "/v1"
    assert normalize_api_prefix("/") == ""


def test_resolve_remote_target_from_explicit_runtime():
    target = resolve_remote_target(CliRuntime(base_url="https://api.example.test/", api_prefix="iam/", timeout=4.5))

    assert target.base_url == "https://api.example.test"
    assert target.api_prefix == "/iam"
    assert target.timeout == 4.5


def test_credential_type_override_selects_matching_default_environment(tmp_path: Path):
    store = ContextStore(tmp_path / "config.json")
    store.add(
        ContextProfile(
            name="production",
            base_url="https://api.example.test",
            credential_type="bearer",
            credential_env="CUSTOM_BEARER_TOKEN",
        ),
        activate=True,
        force=False,
    )

    target = resolve_remote_target(CliRuntime(credential_type="api_key"), store=ContextStore(store.path))

    assert target.credential_type == "api_key"
    assert target.credential_env == "OUTLABS_AUTH_API_KEY"


def test_remote_capabilities_does_not_require_token(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("TEST_OUTLABS_TOKEN", raising=False)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://auth.example.test/v1/auth/config"
        assert "authorization" not in request.headers
        return httpx.Response(200, json={"preset": "SimpleRBAC", "features": {"api_keys": True}})

    result, meta = RemoteClient(_target(), transport=httpx.MockTransport(handler)).capabilities()

    assert result["preset"] == "SimpleRBAC"
    assert meta["http_status"] == 200


def test_remote_whoami_requires_named_token_environment(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("TEST_OUTLABS_TOKEN", raising=False)

    with pytest.raises(CliError) as raised:
        RemoteClient(_target(), transport=httpx.MockTransport(lambda request: None)).whoami()

    assert raised.value.code == "AUTH_CREDENTIAL_MISSING"
    assert raised.value.exit_code == 3


def test_remote_whoami_sends_bearer_and_preserves_request_id(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TEST_OUTLABS_TOKEN", "safe-token")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer safe-token"
        return httpx.Response(
            200,
            headers={"x-request-id": "req-123"},
            json={"id": "user-1", "email": "admin@example.test", "status": "active"},
        )

    result, meta = RemoteClient(_target(), transport=httpx.MockTransport(handler)).whoami()

    assert result["id"] == "user-1"
    assert meta["request_id"] == "req-123"


def test_remote_client_supports_scoped_api_key_credentials(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TEST_OUTLABS_API_KEY", "scoped-api-key")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "scoped-api-key"
        assert "authorization" not in request.headers
        return httpx.Response(200, json={"items": [], "total": 0, "page": 1, "limit": 20, "pages": 0})

    target = _target(credential_type="api_key", credential_env="TEST_OUTLABS_API_KEY")
    result, _ = RemoteClient(target, transport=httpx.MockTransport(handler)).request("GET", "/users/")

    assert result["total"] == 0


def test_remote_api_error_maps_to_stable_auth_exit(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TEST_OUTLABS_TOKEN", "safe-token")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={
                "error": "PERMISSION_DENIED",
                "message": "Permission denied",
                "details": {"permission": "user:read"},
            },
        )

    with pytest.raises(CliError) as raised:
        RemoteClient(_target(), transport=httpx.MockTransport(handler)).whoami()

    assert raised.value.code == "PERMISSION_DENIED"
    assert raised.value.exit_code == 3
    assert raised.value.details["http_status"] == 403


def test_remote_validation_error_never_echoes_submitted_secret(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TEST_OUTLABS_TOKEN", "safe-token")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422,
            json={
                "detail": [
                    {
                        "type": "string_too_short",
                        "loc": ["body", "password"],
                        "msg": "String should have at least 8 characters",
                        "input": "echoed-password",
                    }
                ]
            },
        )

    with pytest.raises(CliError) as raised:
        RemoteClient(_target(), transport=httpx.MockTransport(handler)).request(
            "POST",
            "/auth/login",
            json_body={"password": "echoed-password"},
        )

    assert raised.value.code == "HTTP_422"
    assert "echoed-password" not in str(raised.value.details)
    assert raised.value.details["errors"][0]["loc"] == ["body", "password"]


def test_stored_session_refreshes_and_retries_after_unauthorized(tmp_path: Path):
    store = CredentialStore(tmp_path / "credentials.json").load()
    store.put(
        StoredSession(
            profile="test",
            base_url="https://auth.example.test",
            api_prefix="/v1",
            access_token="old-access",
            refresh_token="old-refresh",
            expires_at=time.time() + 600,
            created_at=time.time(),
        )
    )
    seen_authorization: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/auth/refresh":
            assert json.loads(request.content)["refresh_token"] == "old-refresh"
            return httpx.Response(
                200,
                json={
                    "access_token": "new-access",
                    "refresh_token": "new-refresh",
                    "token_type": "bearer",
                    "expires_in": 900,
                },
            )
        seen_authorization.append(request.headers["authorization"])
        if request.headers["authorization"] == "Bearer old-access":
            return httpx.Response(401, json={"error": "TOKEN_EXPIRED", "message": "Expired"})
        return httpx.Response(200, json={"id": "user-1", "email": "admin@example.test"})

    payload, meta = RemoteClient(
        _target(),
        transport=httpx.MockTransport(handler),
        credential_store=store,
    ).whoami()

    assert payload["id"] == "user-1"
    assert seen_authorization == ["Bearer old-access", "Bearer new-access"]
    assert meta["auth_source"] == "stored_session"
    refreshed = CredentialStore(store.path).load().get("test")
    assert refreshed is not None
    assert refreshed.access_token == "new-access"
    assert refreshed.refresh_token == "new-refresh"


def test_remote_transport_failure_is_retryable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    with pytest.raises(CliError) as raised:
        RemoteClient(_target(), transport=httpx.MockTransport(handler)).capabilities()

    assert raised.value.code == "REMOTE_UNAVAILABLE"
    assert raised.value.exit_code == 4
    assert raised.value.retryable is True


def test_remote_user_list_auto_paginates_and_keeps_filters(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TEST_OUTLABS_TOKEN", "safe-token")
    seen_pages: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        seen_pages.append(page)
        assert request.url.params["limit"] == "100"
        assert request.url.params["status"] == "active"
        return httpx.Response(
            200,
            json={
                "items": [{"id": f"user-{page}", "email": f"user{page}@example.test"}],
                "total": 2,
                "page": page,
                "limit": 100,
                "pages": 2,
            },
        )

    result, _ = RemoteClient(_target(), transport=httpx.MockTransport(handler)).list_users(
        page=7,
        status="active",
        all_pages=True,
    )

    assert seen_pages == [1, 2]
    assert [item["id"] for item in result["items"]] == ["user-1", "user-2"]
    assert result["pages_fetched"] == 2


def test_remote_user_reference_prefers_exact_email(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TEST_OUTLABS_TOKEN", "safe-token")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/users/"
        assert request.url.params["search"] == "admin@example.test"
        return httpx.Response(
            200,
            json={
                "items": [
                    {"id": "user-1", "email": "other-admin@example.test"},
                    {"id": "user-2", "email": "admin@example.test"},
                ],
                "total": 2,
                "page": 1,
                "limit": 100,
                "pages": 1,
            },
        )

    result, meta = RemoteClient(_target(), transport=httpx.MockTransport(handler)).resolve_user("admin@example.test")

    assert result["id"] == "user-2"
    assert meta["resolution"]["kind"] == "email"


def test_remote_user_reference_rejects_ambiguous_search(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TEST_OUTLABS_TOKEN", "safe-token")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "items": [
                    {"id": "user-1", "email": "alex.one@example.test"},
                    {"id": "user-2", "email": "alex.two@example.test"},
                ],
                "total": 2,
                "page": 1,
                "limit": 100,
                "pages": 1,
            },
        )

    with pytest.raises(CliError) as raised:
        RemoteClient(_target(), transport=httpx.MockTransport(handler)).resolve_user("alex")

    assert raised.value.code == "USER_REFERENCE_AMBIGUOUS"
    assert raised.value.exit_code == 5


def test_raw_api_write_requires_confirmation_and_uses_bounded_json_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("OUTLABS_AUTH_TOKEN", "safe-token")
    request_file = tmp_path / "request.json"
    request_file.write_text('{"name": "operator"}')
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(201, json={"id": "role-1", "name": "operator"})

    monkeypatch.setattr(
        api_commands,
        "RemoteClient",
        lambda target: RemoteClient(target, transport=httpx.MockTransport(handler)),
    )
    runner = CliRunner()
    denied = runner.invoke(
        cli_main,
        [
            "--output",
            "json",
            "--non-interactive",
            "--base-url",
            "https://auth.example.test",
            "api",
            "request",
            "POST",
            "/roles/",
            "--from",
            str(request_file),
        ],
    )
    allowed = runner.invoke(
        cli_main,
        [
            "--output",
            "json",
            "--non-interactive",
            "--base-url",
            "https://auth.example.test",
            "api",
            "request",
            "POST",
            "/roles/",
            "--from",
            str(request_file),
            "--yes",
        ],
    )

    assert denied.exit_code == 2
    assert _json_output(denied)["error"]["code"] == "INTERACTION_REQUIRED"
    assert allowed.exit_code == 0
    assert _json_output(allowed)["command"] == "api.request"
    assert seen == [{"name": "operator"}]


def test_raw_api_rejects_absolute_url_before_transport(monkeypatch: pytest.MonkeyPatch):
    result = CliRunner().invoke(
        cli_main,
        [
            "--output",
            "json",
            "--base-url",
            "https://auth.example.test",
            "api",
            "request",
            "GET",
            "https://attacker.example.test/users",
        ],
    )

    assert result.exit_code == 2
    assert _json_output(result)["error"]["code"] == "INVALID_API_PATH"


def test_roles_create_builds_typed_request_and_json_contract(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TEST_OUTLABS_TOKEN", "safe-token")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/roles/"
        body = json.loads(request.content)
        assert body == {
            "name": "operator",
            "display_name": "Operator",
            "permissions": ["user:read", "entity:read"],
            "is_global": False,
        }
        return httpx.Response(201, json={"id": "role-1", **body, "status": "active"})

    _patch_resource_client(monkeypatch, role_commands, handler)
    result = CliRunner().invoke(
        cli_main,
        [
            "--output",
            "json",
            "roles",
            "create",
            "--name",
            "operator",
            "--display-name",
            "Operator",
            "--permission",
            "user:read",
            "--permission",
            "entity:read",
            "--not-global",
        ],
    )

    assert result.exit_code == 0
    payload = _json_output(result)
    assert payload["command"] == "roles.create"
    assert payload["changed"] is True
    assert payload["result"]["name"] == "operator"


def test_permission_explain_identifies_wildcard_role_source(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TEST_OUTLABS_TOKEN", "safe-token")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/users/me":
            return httpx.Response(
                200,
                json={"id": "user-1", "email": "admin@example.test", "is_superuser": False},
            )
        assert request.url.path == "/v1/users/user-1/permissions"
        return httpx.Response(
            200,
            json=[
                {
                    "permission": {"id": "permission-1", "name": "user:*", "display_name": "Manage users"},
                    "source": "role",
                    "source_id": "role-1",
                    "source_name": "operator",
                }
            ],
        )

    _patch_resource_client(monkeypatch, permission_commands, handler)
    result = CliRunner().invoke(
        cli_main,
        ["--output", "json", "permissions", "explain", "user:read"],
    )

    assert result.exit_code == 0
    payload = _json_output(result)
    assert payload["command"] == "permissions.explain"
    assert payload["result"]["granted"] is True
    assert payload["result"]["reason"] == "matching_role_or_direct_grant"
    assert payload["result"]["matching_sources"][0]["source_name"] == "operator"


def test_entities_move_resolves_both_names_before_mutation(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TEST_OUTLABS_TOKEN", "safe-token")
    moved: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            search = request.url.params["search"]
            item = (
                {"id": "00000000-0000-0000-0000-000000000001", "name": "sales", "slug": "sales"}
                if search == "sales"
                else {"id": "00000000-0000-0000-0000-000000000002", "name": "north", "slug": "north"}
            )
            return httpx.Response(
                200,
                json={"items": [item], "total": 1, "page": 1, "limit": 1000, "pages": 1},
            )
        assert request.url.path == "/v1/entities/00000000-0000-0000-0000-000000000001/move"
        moved.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "00000000-0000-0000-0000-000000000001",
                "name": "sales",
                "parent_entity_id": "00000000-0000-0000-0000-000000000002",
            },
        )

    _patch_resource_client(monkeypatch, entity_commands, handler)
    result = CliRunner().invoke(
        cli_main,
        ["--output", "json", "entities", "move", "sales", "--parent", "north", "--yes"],
    )

    assert result.exit_code == 0
    assert moved == [{"new_parent_id": "00000000-0000-0000-0000-000000000002"}]
    assert _json_output(result)["command"] == "entities.move"


def test_membership_add_resolves_human_references(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TEST_OUTLABS_TOKEN", "safe-token")
    created: list[dict] = []

    def page(item: dict) -> httpx.Response:
        return httpx.Response(200, json={"items": [item], "total": 1, "page": 1, "limit": 100, "pages": 1})

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/users/":
            return page({"id": "user-1", "email": "alex@example.test"})
        if request.url.path == "/v1/entities/":
            return page({"id": "entity-1", "name": "sales", "slug": "sales"})
        if request.url.path == "/v1/roles/":
            return page({"id": "role-1", "name": "operator", "display_name": "Operator"})
        assert request.url.path == "/v1/memberships/"
        created.append(json.loads(request.content))
        return httpx.Response(
            201,
            json={"id": "membership-1", **created[-1], "status": "active", "effective_status": "active"},
        )

    _patch_resource_client(monkeypatch, membership_commands, handler)
    result = CliRunner().invoke(
        cli_main,
        [
            "--output",
            "json",
            "memberships",
            "add",
            "--user",
            "alex@example.test",
            "--entity",
            "sales",
            "--role",
            "operator",
            "--yes",
        ],
    )

    assert result.exit_code == 0
    assert created == [{"user_id": "user-1", "entity_id": "entity-1", "role_ids": ["role-1"]}]
    assert _json_output(result)["command"] == "memberships.add"


def test_api_key_create_writes_one_time_secret_to_owner_only_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("TEST_OUTLABS_TOKEN", "safe-token")
    secret_path = tmp_path / "secrets" / "agent.key"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/api-keys/"
        body = json.loads(request.content)
        assert body["scopes"] == ["user:read"]
        return httpx.Response(
            201,
            json={
                "id": "key-1",
                "name": "coding-agent",
                "prefix": "sk_live_abc",
                "key_kind": "personal",
                "status": "active",
                "scopes": ["user:read"],
                "rate_limit_per_minute": 60,
                "api_key": "one-time-secret",
            },
        )

    _patch_resource_client(monkeypatch, api_key_commands, handler)
    result = CliRunner().invoke(
        cli_main,
        [
            "--output",
            "json",
            "api-keys",
            "create",
            "--name",
            "coding-agent",
            "--scope",
            "user:read",
            "--secret-file",
            str(secret_path),
            "--yes",
        ],
    )

    assert result.exit_code == 0
    assert secret_path.read_text() == "one-time-secret\n"
    assert stat.S_IMODE(secret_path.stat().st_mode) == 0o600
    assert "one-time-secret" not in result.output
    payload = _json_output(result)
    assert payload["command"] == "api-keys.create"
    assert payload["result"]["secret_written_to"] == str(secret_path)


def test_api_key_secret_sink_preflight_preserves_existing_directory_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("TEST_OUTLABS_TOKEN", "safe-token")
    secret_directory = tmp_path / "shared"
    secret_directory.mkdir(mode=0o755)
    secret_path = secret_directory / "agent.key"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/api-keys/"
        return httpx.Response(
            201,
            json={
                "id": "key-1",
                "name": "coding-agent",
                "prefix": "sk_live_abc",
                "key_kind": "personal",
                "status": "active",
                "scopes": ["user:read"],
                "api_key": "one-time-secret",
            },
        )

    _patch_resource_client(monkeypatch, api_key_commands, handler)
    result = CliRunner().invoke(
        cli_main,
        [
            "--output",
            "json",
            "api-keys",
            "create",
            "--name",
            "coding-agent",
            "--scope",
            "user:read",
            "--secret-file",
            str(secret_path),
            "--yes",
        ],
    )

    assert result.exit_code == 0
    assert stat.S_IMODE(secret_directory.stat().st_mode) == 0o755
    assert stat.S_IMODE(secret_path.stat().st_mode) == 0o600


def test_api_key_secret_sink_is_validated_before_remote_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    called = False
    secret_path = tmp_path / "existing.key"
    secret_path.write_text("do-not-overwrite")

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(500)

    _patch_resource_client(monkeypatch, api_key_commands, handler)
    result = CliRunner().invoke(
        cli_main,
        [
            "--output",
            "json",
            "api-keys",
            "create",
            "--name",
            "coding-agent",
            "--scope",
            "user:read",
            "--secret-file",
            str(secret_path),
            "--yes",
        ],
    )

    assert result.exit_code == 2
    assert _json_output(result)["error"]["code"] == "SECRET_FILE_EXISTS"
    assert called is False


def test_api_key_create_refuses_to_call_api_without_secret_sink(monkeypatch: pytest.MonkeyPatch):
    result = CliRunner().invoke(
        cli_main,
        ["--output", "json", "api-keys", "create", "--name", "agent", "--scope", "user:read", "--yes"],
    )

    assert result.exit_code == 2
    assert _json_output(result)["error"]["code"] == "SECRET_SINK_REQUIRED"


def test_api_key_entity_inventory_resolves_entity_and_owner(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TEST_OUTLABS_TOKEN", "safe-token")

    def page(item: dict) -> httpx.Response:
        return httpx.Response(200, json={"items": [item], "total": 1, "page": 1, "limit": 100, "pages": 1})

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/entities/":
            return page({"id": "entity-1", "name": "engineering", "slug": "engineering"})
        if request.url.path == "/v1/users/":
            return page({"id": "user-1", "email": "owner@example.test"})
        assert request.url.path == "/v1/admin/entities/entity-1/api-keys"
        assert request.url.params["owner_id"] == "user-1"
        assert request.url.params["key_kind"] == "personal"
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "key-1",
                        "name": "automation",
                        "key_kind": "personal",
                        "owner_id": "user-1",
                        "status": "active",
                        "prefix": "sk_live_abc",
                    }
                ],
                "total": 1,
                "page": 1,
                "limit": 20,
                "pages": 1,
            },
        )

    _patch_resource_client(monkeypatch, api_key_commands, handler)
    result = CliRunner().invoke(
        cli_main,
        [
            "--output",
            "json",
            "api-keys",
            "inventory",
            "--entity",
            "engineering",
            "--owner",
            "owner@example.test",
            "--kind",
            "personal",
        ],
    )

    assert result.exit_code == 0
    payload = _json_output(result)
    assert payload["command"] == "api-keys.inventory"
    assert payload["result"]["items"][0]["id"] == "key-1"


def test_integration_principal_requires_explicit_entity_or_platform_scope(
    monkeypatch: pytest.MonkeyPatch,
):
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"Unexpected remote request: {request.method} {request.url}")

    _patch_resource_client(monkeypatch, integration_commands, handler)
    result = CliRunner().invoke(
        cli_main,
        ["--output", "json", "integration-principals", "list"],
    )

    assert result.exit_code == 2
    assert _json_output(result)["error"]["code"] == "INTEGRATION_SCOPE_REQUIRED"


def test_integration_principal_create_resolves_roles_and_platform_scope(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("TEST_OUTLABS_TOKEN", "safe-token")
    submitted: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/roles/":
            return httpx.Response(
                200,
                json={
                    "items": [{"id": "role-1", "name": "deploy-bot", "display_name": "Deploy bot"}],
                    "total": 1,
                    "page": 1,
                    "limit": 100,
                    "pages": 1,
                },
            )
        assert request.url.path == "/v1/system/integration-principals"
        submitted.append(json.loads(request.content))
        return httpx.Response(
            201,
            json={
                "id": "principal-1",
                "name": "release-agent",
                "status": "active",
                "scope_kind": "platform_global",
                "anchor_entity_id": None,
                "inherit_from_tree": False,
                "allowed_scopes": ["deployments:write"],
                "effective_allowed_scopes": ["deployments:write"],
                "role_ids": ["role-1"],
            },
        )

    _patch_resource_client(monkeypatch, integration_commands, handler)
    result = CliRunner().invoke(
        cli_main,
        [
            "--output",
            "json",
            "integration-principals",
            "create",
            "--platform",
            "--name",
            "release-agent",
            "--allowed-scope",
            "deployments:write",
            "--role",
            "deploy-bot",
            "--yes",
        ],
    )

    assert result.exit_code == 0
    assert submitted == [
        {
            "name": "release-agent",
            "allowed_scopes": ["deployments:write"],
            "role_ids": ["role-1"],
        }
    ]
    payload = _json_output(result)
    assert payload["command"] == "integration-principals.create"
    assert payload["meta"]["scope"]["kind"] == "platform_global"


def test_integration_principal_entity_scope_resolves_slug(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TEST_OUTLABS_TOKEN", "safe-token")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/entities/":
            return httpx.Response(
                200,
                json={
                    "items": [{"id": "entity-1", "name": "engineering", "slug": "engineering"}],
                    "total": 1,
                    "page": 1,
                    "limit": 100,
                    "pages": 1,
                },
            )
        assert request.url.path == "/v1/entities/entity-1/integration-principals"
        return httpx.Response(
            200,
            json={"items": [], "total": 0, "page": 1, "limit": 20, "pages": 0},
        )

    _patch_resource_client(monkeypatch, integration_commands, handler)
    result = CliRunner().invoke(
        cli_main,
        [
            "--output",
            "json",
            "integration-principals",
            "list",
            "--entity",
            "engineering",
        ],
    )

    assert result.exit_code == 0
    payload = _json_output(result)
    assert payload["meta"]["scope"] == {"kind": "entity", "entity_id": "entity-1"}


def test_integration_key_create_writes_secret_without_disclosure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("TEST_OUTLABS_TOKEN", "safe-token")
    secret_path = tmp_path / "release-agent.key"
    submitted: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            assert request.url.path == "/v1/system/integration-principals"
            return httpx.Response(
                200,
                json={
                    "items": [{"id": "principal-1", "name": "release-agent"}],
                    "total": 1,
                    "page": 1,
                    "limit": 100,
                    "pages": 1,
                },
            )
        assert request.url.path == "/v1/system/integration-principals/principal-1/api-keys"
        submitted.append(json.loads(request.content))
        return httpx.Response(
            201,
            json={
                "id": "key-1",
                "name": "production-deploy",
                "prefix": "sk_live_release",
                "key_kind": "system_integration",
                "status": "active",
                "scopes": ["deployments:write"],
                "api_key": "system-key-secret",
            },
        )

    _patch_resource_client(monkeypatch, integration_commands, handler)
    result = CliRunner().invoke(
        cli_main,
        [
            "--output",
            "json",
            "integration-keys",
            "create",
            "release-agent",
            "--platform",
            "--name",
            "production-deploy",
            "--scope",
            "deployments:write",
            "--secret-file",
            str(secret_path),
            "--yes",
        ],
    )

    assert result.exit_code == 0
    assert submitted == [{"name": "production-deploy", "scopes": ["deployments:write"]}]
    assert secret_path.read_text() == "system-key-secret\n"
    assert stat.S_IMODE(secret_path.stat().st_mode) == 0o600
    assert "system-key-secret" not in result.output
    payload = _json_output(result)
    assert payload["command"] == "integration-keys.create"
    assert "api_key" not in payload["result"]


def test_role_abac_condition_create_preserves_typed_json_value(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TEST_OUTLABS_TOKEN", "safe-token")
    submitted: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/roles/":
            return httpx.Response(
                200,
                json={
                    "items": [{"id": "role-1", "name": "operator", "display_name": "Operator"}],
                    "total": 1,
                    "page": 1,
                    "limit": 100,
                    "pages": 1,
                },
            )
        assert request.url.path == "/v1/roles/role-1/conditions"
        submitted.append(json.loads(request.content))
        return httpx.Response(
            201,
            json={
                "id": "condition-1",
                "attribute": "subject.department",
                "operator": "in",
                "value": '["engineering", "operations"]',
                "value_type": "list",
                "condition_group_id": None,
            },
        )

    _patch_resource_client(monkeypatch, abac_commands, handler)
    result = CliRunner().invoke(
        cli_main,
        [
            "--output",
            "json",
            "roles",
            "conditions",
            "create",
            "operator",
            "--attribute",
            "subject.department",
            "--operator",
            "in",
            "--value-json",
            '["engineering", "operations"]',
            "--value-type",
            "list",
            "--yes",
        ],
    )

    assert result.exit_code == 0
    assert submitted == [
        {
            "attribute": "subject.department",
            "operator": "in",
            "value": ["engineering", "operations"],
            "value_type": "list",
        }
    ]
    assert _json_output(result)["command"] == "roles.conditions.create"


def test_permission_abac_condition_group_create_resolves_permission(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("TEST_OUTLABS_TOKEN", "safe-token")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/permissions/":
            return httpx.Response(
                200,
                json={
                    "items": [{"id": "permission-1", "name": "reports:read"}],
                    "total": 1,
                    "page": 1,
                    "limit": 1000,
                    "pages": 1,
                },
            )
        assert request.url.path == "/v1/permissions/permission-1/condition-groups"
        assert json.loads(request.content) == {"operator": "OR", "description": "Office or VPN"}
        return httpx.Response(
            201,
            json={
                "id": "group-1",
                "operator": "OR",
                "description": "Office or VPN",
                "permission_id": "permission-1",
                "role_id": None,
            },
        )

    _patch_resource_client(monkeypatch, abac_commands, handler)
    result = CliRunner().invoke(
        cli_main,
        [
            "--output",
            "json",
            "permissions",
            "condition-groups",
            "create",
            "reports:read",
            "--operator",
            "OR",
            "--description",
            "Office or VPN",
            "--yes",
        ],
    )

    assert result.exit_code == 0
    assert _json_output(result)["command"] == "permissions.condition-groups.create"


def test_abac_value_json_validation_fails_before_remote_request():
    result = CliRunner().invoke(
        cli_main,
        [
            "--output",
            "json",
            "roles",
            "conditions",
            "create",
            "operator",
            "--attribute",
            "subject.department",
            "--operator",
            "in",
            "--value-json",
            "[broken",
            "--yes",
        ],
    )

    assert result.exit_code == 2
    assert _json_output(result)["error"]["code"] == "INVALID_ABAC_VALUE_JSON"


def test_user_password_reset_uses_stdin_without_secret_disclosure(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TEST_OUTLABS_TOKEN", "safe-token")
    seen_passwords: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/users/":
            return httpx.Response(
                200,
                json={
                    "items": [{"id": "user-1", "email": "alex@example.test"}],
                    "total": 1,
                    "page": 1,
                    "limit": 100,
                    "pages": 1,
                },
            )
        seen_passwords.append(json.loads(request.content)["new_password"])
        return httpx.Response(204)

    _patch_resource_client(monkeypatch, user_admin_commands, handler)
    result = CliRunner().invoke(
        cli_main,
        [
            "--output",
            "json",
            "users",
            "reset-password",
            "alex@example.test",
            "--password-stdin",
            "--yes",
        ],
        input="replacement-secret\n",
    )

    assert result.exit_code == 0
    assert seen_passwords == ["replacement-secret"]
    assert "replacement-secret" not in result.output
    assert _json_output(result)["command"] == "users.reset-password"


def test_account_change_password_reads_two_stdin_lines_without_disclosure(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("TEST_OUTLABS_TOKEN", "safe-token")
    submitted: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/users/me/change-password"
        submitted.append(json.loads(request.content))
        return httpx.Response(204)

    _patch_resource_client(monkeypatch, account_commands, handler)
    result = CliRunner().invoke(
        cli_main,
        [
            "--output",
            "json",
            "account",
            "change-password",
            "--current-password-stdin",
            "--new-password-stdin",
        ],
        input="current-secret\nreplacement-secret\n",
    )

    assert result.exit_code == 0
    assert submitted == [{"current_password": "current-secret", "new_password": "replacement-secret"}]
    assert "current-secret" not in result.output
    assert "replacement-secret" not in result.output
    assert _json_output(result)["command"] == "account.change-password"


def test_account_update_can_explicitly_clear_phone(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TEST_OUTLABS_TOKEN", "safe-token")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/users/me"
        assert json.loads(request.content) == {"phone": None}
        return httpx.Response(
            200,
            json={
                "id": "user-1",
                "email": "alex@example.test",
                "status": "active",
                "phone": None,
                "email_verified": True,
                "phone_verified": False,
                "is_superuser": False,
            },
        )

    _patch_resource_client(monkeypatch, account_commands, handler)
    result = CliRunner().invoke(
        cli_main,
        ["--output", "json", "account", "update", "--clear-phone"],
    )

    assert result.exit_code == 0
    assert _json_output(result)["result"]["phone"] is None


def test_user_access_report_collects_redacted_authority_surfaces(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TEST_OUTLABS_TOKEN", "safe-token")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/users/":
            return httpx.Response(
                200,
                json={
                    "items": [{"id": "user-1", "email": "alex@example.test"}],
                    "total": 1,
                    "page": 1,
                    "limit": 100,
                    "pages": 1,
                },
            )
        responses = {
            "/v1/memberships/user/user-1": [{"id": "membership-1", "entity_id": "entity-1"}],
            "/v1/users/user-1/role-memberships": [{"id": "role-membership-1", "role_id": "role-1"}],
            "/v1/users/user-1/permissions": [
                {"permission": {"id": "permission-1", "name": "reports:read"}, "source": "role"}
            ],
            "/v1/users/user-1/api-keys": [
                {"id": "key-1", "name": "agent", "prefix": "sk_live_abc", "status": "active"}
            ],
            "/v1/users/user-1/sessions": [{"id": "session-1", "device_name": "CLI"}],
        }
        assert request.url.path in responses
        return httpx.Response(200, json=responses[request.url.path])

    _patch_resource_client(monkeypatch, user_inspection_commands, handler)
    result = CliRunner().invoke(
        cli_main,
        ["--output", "json", "users", "access-report", "alex@example.test"],
    )

    assert result.exit_code == 0
    payload = _json_output(result)
    assert payload["command"] == "users.access-report"
    assert payload["result"]["effective_permissions"][0]["permission"]["name"] == "reports:read"
    assert payload["result"]["personal_api_keys"][0]["prefix"] == "sk_live_abc"
    assert "api_key" not in payload["result"]["personal_api_keys"][0]


def test_command_schema_uses_public_root_path_and_omits_internal_sentinels():
    result = CliRunner().invoke(
        cli_main,
        ["--output", "json", "commands", "roles", "create", "--shallow"],
    )

    assert result.exit_code == 0
    payload = _json_output(result)
    assert payload["result"]["path"] == "outlabs-auth roles create"
    assert "Sentinel" not in result.output

    root_result = CliRunner().invoke(
        cli_main,
        ["--output", "json", "commands", "--shallow"],
    )
    root_payload = _json_output(root_result)
    assert root_payload["result"]["path"] == "outlabs-auth"
    assert root_payload["result"]["name"] == "outlabs-auth"


def test_declarative_plan_and_apply_orders_permission_before_role(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("TEST_OUTLABS_TOKEN", "safe-token")
    permissions: list[dict] = []
    roles: list[dict] = []
    writes: list[str] = []

    def paginated(items: list[dict], request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "items": items,
                "total": len(items),
                "page": int(request.url.params["page"]),
                "limit": int(request.url.params["limit"]),
                "pages": 1 if items else 0,
            },
        )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/v1/permissions/":
            return paginated(permissions, request)
        if request.method == "GET" and request.url.path == "/v1/roles/":
            return paginated(roles, request)
        body = json.loads(request.content)
        if request.url.path == "/v1/permissions/":
            writes.append("permission")
            created = {"id": "permission-1", "status": "active", "is_active": True, **body}
            permissions.append(created)
            return httpx.Response(201, json=created)
        writes.append("role")
        created = {
            "id": "role-1",
            "status": "active",
            "scope": "hierarchy",
            "is_global": True,
            **body,
        }
        roles.append(created)
        return httpx.Response(201, json=created)

    target = _target()
    client = RemoteClient(target, transport=httpx.MockTransport(handler))
    monkeypatch.setattr(declarative_commands, "remote_client", lambda: (target, client))
    manifest_path = tmp_path / "state.json"
    plan_path = tmp_path / "plan.json"
    manifest_path.write_text(
        json.dumps(
            {
                "api_version": "outlabs-auth.state/v1alpha1",
                "kind": "OutlabsAuthState",
                "spec": {
                    "permissions": [{"name": "agent:read", "display_name": "Agent read"}],
                    "roles": [
                        {
                            "name": "coding-agent",
                            "display_name": "Coding agent",
                            "permissions": ["agent:read"],
                        }
                    ],
                },
            }
        )
    )
    runner = CliRunner()
    planned = runner.invoke(
        cli_main,
        ["--output", "json", "plan", str(manifest_path), "--out", str(plan_path)],
    )
    applied = runner.invoke(
        cli_main,
        ["--output", "json", "apply", str(plan_path), "--yes"],
    )

    assert planned.exit_code == 0
    planned_payload = _json_output(planned)
    assert [item["resource"] for item in planned_payload["result"]["operations"]] == ["permissions", "roles"]
    assert stat.S_IMODE(plan_path.stat().st_mode) == 0o600
    assert applied.exit_code == 0
    assert _json_output(applied)["result"]["applied"] == 2
    assert writes == ["permission", "role"]


def test_declarative_apply_detects_drift_before_any_write(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TEST_OUTLABS_TOKEN", "safe-token")
    role = {
        "id": "role-1",
        "name": "operator",
        "display_name": "Operator",
        "permissions": [],
        "status": "active",
        "scope": "hierarchy",
        "is_global": True,
    }
    writes: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method != "GET":
            writes.append(request.method)
            return httpx.Response(200, json={})
        return httpx.Response(
            200,
            json={"items": [role], "total": 1, "page": 1, "limit": 100, "pages": 1},
        )

    target = _target()
    client = RemoteClient(target, transport=httpx.MockTransport(handler))
    manifest = {
        "api_version": "outlabs-auth.state/v1alpha1",
        "kind": "OutlabsAuthState",
        "spec": {"roles": [{"name": "operator", "display_name": "Senior operator"}]},
    }
    plan = build_plan(client, target, manifest)
    role["display_name"] = "Changed elsewhere"

    with pytest.raises(CliError) as raised:
        apply_plan(client, plan["operations"])

    assert raised.value.code == "PLAN_DRIFT_DETECTED"
    assert raised.value.exit_code == 5
    assert writes == []


def test_declarative_apply_resolves_new_entity_and_role_dependencies(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TEST_OUTLABS_TOKEN", "safe-token")
    entities: list[dict] = []
    roles: list[dict] = []
    users = [{"id": "user-1", "email": "alex@example.test"}]
    request_bodies: list[tuple[str, dict]] = []

    def page(items: list[dict], request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "items": items,
                "total": len(items),
                "page": int(request.url.params["page"]),
                "limit": int(request.url.params["limit"]),
                "pages": 1 if items else 0,
            },
        )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            if request.url.path == "/v1/entities/":
                return page(entities, request)
            if request.url.path == "/v1/roles/":
                return page(roles, request)
            if request.url.path == "/v1/users/":
                return page(users, request)
            if request.url.path == "/v1/memberships/user/user-1":
                return httpx.Response(200, json=[])
        body = json.loads(request.content)
        request_bodies.append((request.url.path, body))
        if request.url.path == "/v1/entities/":
            entity_id = f"entity-{len(entities) + 1}"
            created = {"id": entity_id, "status": "active", **body}
            entities.append(created)
            return httpx.Response(201, json=created)
        if request.url.path == "/v1/roles/":
            created = {"id": "role-1", "status": "active", **body}
            roles.append(created)
            return httpx.Response(201, json=created)
        return httpx.Response(201, json={"id": "membership-1", "status": "active", **body})

    target = _target()
    client = RemoteClient(target, transport=httpx.MockTransport(handler))
    manifest = {
        "api_version": "outlabs-auth.state/v1alpha1",
        "kind": "OutlabsAuthState",
        "spec": {
            "entities": [
                {
                    "slug": "acme",
                    "name": "acme",
                    "display_name": "Acme",
                    "entity_class": "structural",
                    "entity_type": "organization",
                },
                {
                    "slug": "engineering",
                    "name": "engineering",
                    "display_name": "Engineering",
                    "entity_class": "structural",
                    "entity_type": "department",
                    "parent": "acme",
                },
            ],
            "roles": [
                {
                    "name": "engineer",
                    "display_name": "Engineer",
                    "scope_entity": "engineering",
                    "permissions": [],
                }
            ],
            "memberships": [
                {
                    "user": "alex@example.test",
                    "entity": "engineering",
                    "roles": ["engineer"],
                }
            ],
        },
    }
    plan = build_plan(client, target, manifest)
    result = apply_plan(client, plan["operations"])

    assert result["applied"] == 4
    assert [path for path, _ in request_bodies] == [
        "/v1/entities/",
        "/v1/entities/",
        "/v1/roles/",
        "/v1/memberships/",
    ]
    assert request_bodies[1][1]["parent_entity_id"] == "entity-1"
    assert request_bodies[2][1]["scope_entity_id"] == "entity-2"
    assert request_bodies[3][1]["entity_id"] == "entity-2"
    assert request_bodies[3][1]["role_ids"] == ["role-1"]


def test_declarative_manifest_rejects_unknown_fields():
    with pytest.raises(CliError) as raised:
        validate_manifest(
            {
                "api_version": "outlabs-auth.state/v1alpha1",
                "kind": "OutlabsAuthState",
                "spec": {"roles": [{"name": "operator", "display_nmae": "typo"}]},
            }
        )

    assert raised.value.code == "UNKNOWN_DECLARATIVE_FIELD"


def test_saved_plan_is_bound_to_exact_target():
    with pytest.raises(CliError) as raised:
        validate_plan(
            {
                "plan_version": "outlabs-auth.plan/v1alpha1",
                "target": {
                    "profile": "test",
                    "base_url": "https://different.example.test",
                    "api_prefix": "/v1",
                },
                "operations": [],
            },
            _target(),
        )

    assert raised.value.code == "PLAN_TARGET_MISMATCH"


def test_users_list_command_wires_filters_into_versioned_result(monkeypatch: pytest.MonkeyPatch):
    class FakeClient:
        def __init__(self, target):
            self.target = target

        def list_users(self, **kwargs):
            assert kwargs == {
                "page": 1,
                "limit": 20,
                "search": "alex",
                "status": "active",
                "root_entity_id": None,
                "all_pages": True,
            }
            return (
                {
                    "items": [
                        {
                            "id": "user-1",
                            "email": "alex@example.test",
                            "status": "active",
                            "is_superuser": False,
                        }
                    ],
                    "total": 1,
                    "all": True,
                    "pages_fetched": 1,
                },
                {"http_status": 200, "request_id": "req-1"},
            )

    monkeypatch.setattr(remote_commands, "RemoteClient", FakeClient)
    result = CliRunner().invoke(
        cli_main,
        [
            "--output",
            "json",
            "--base-url",
            "https://api.example.test",
            "users",
            "list",
            "--search",
            "alex",
            "--status",
            "active",
            "--all",
        ],
    )

    assert result.exit_code == 0
    payload = _json_output(result)
    assert payload["command"] == "users.list"
    assert payload["result"]["items"][0]["email"] == "alex@example.test"
    assert payload["meta"]["request_id"] == "req-1"


def test_users_get_command_reports_reference_resolution(monkeypatch: pytest.MonkeyPatch):
    class FakeClient:
        def __init__(self, target):
            self.target = target

        def resolve_user(self, reference):
            assert reference == "admin@example.test"
            return (
                {"id": "user-1", "email": reference, "status": "active"},
                {
                    "http_status": 200,
                    "resolution": {"input": reference, "kind": "email", "id": "user-1"},
                },
            )

    monkeypatch.setattr(remote_commands, "RemoteClient", FakeClient)
    result = CliRunner().invoke(
        cli_main,
        [
            "--output",
            "json",
            "--base-url",
            "https://api.example.test",
            "users",
            "get",
            "admin@example.test",
        ],
    )

    assert result.exit_code == 0
    payload = _json_output(result)
    assert payload["command"] == "users.get"
    assert payload["meta"]["resolution"]["kind"] == "email"


def test_context_config_never_inherits_process_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OUTLABS_AUTH_TOKEN", "must-not-be-written")
    path = tmp_path / "config.json"
    store = ContextStore(path)
    store.add(
        ContextProfile("local", "http://127.0.0.1:8000"),
        activate=True,
        force=False,
    )

    assert "must-not-be-written" not in path.read_text()
    assert os.environ["OUTLABS_AUTH_TOKEN"] == "must-not-be-written"
