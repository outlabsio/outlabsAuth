from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import httpx
import pytest
from click.testing import CliRunner

import outlabs_auth.cli_support.remote_commands as remote_commands
from outlabs_auth.cli import _redact_database_url, main as cli_main
from outlabs_auth.cli_support.client import RemoteClient, RemoteTarget, resolve_remote_target
from outlabs_auth.cli_support.contexts import (
    ContextProfile,
    ContextStore,
    normalize_api_prefix,
    normalize_base_url,
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
