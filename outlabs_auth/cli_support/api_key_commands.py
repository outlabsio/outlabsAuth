"""Personal API-key lifecycle commands with explicit one-time secret sinks."""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

import click

from outlabs_auth.cli_support.client import RemoteClient
from outlabs_auth.cli_support.entity_commands import resolve_entity
from outlabs_auth.cli_support.payloads import require_nonempty_payload
from outlabs_auth.cli_support.resource_common import (
    detail_text,
    emit_remote_result,
    records_text,
    remote_client,
    request_payload,
)
from outlabs_auth.cli_support.runtime import (
    CliError,
    EXIT_CONFLICT,
    EXIT_OPERATION_FAILED,
    EXIT_USAGE,
    require_confirmation,
)
from outlabs_auth.cli_support.secrets import validate_secret_file_target, write_secret_file


def _resolve_api_key(client: RemoteClient, reference: str) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        key_id = str(UUID(reference))
    except ValueError:
        key_id = None
    if key_id:
        result, meta = client.request("GET", f"/api-keys/{key_id}")
        if not isinstance(result, dict):
            raise CliError(
                code="REMOTE_PROTOCOL_ERROR",
                message="The API-key endpoint returned an invalid response.",
                exit_code=EXIT_OPERATION_FAILED,
            )
        meta["resolution"] = {"kind": "id", "input": reference, "id": key_id}
        return result, meta
    result, meta = client.request("GET", "/api-keys/")
    items = [item for item in result if isinstance(item, dict)] if isinstance(result, list) else []
    matches = [item for item in items if str(item.get("name", "")).casefold() == reference.casefold()]
    if not matches:
        raise CliError(
            code="API_KEY_NOT_FOUND",
            message=f"No API key matched '{reference}'.",
            exit_code=EXIT_OPERATION_FAILED,
        )
    if len(matches) > 1:
        raise CliError(
            code="API_KEY_REFERENCE_AMBIGUOUS",
            message=f"API key name '{reference}' is not unique.",
            exit_code=EXIT_CONFLICT,
            details={"matches": [{"id": item.get("id"), "name": item.get("name")} for item in matches]},
            hint="Use the API-key UUID.",
        )
    meta["resolution"] = {"kind": "name", "input": reference, "id": matches[0].get("id")}
    return matches[0], meta


def _key_text(key: dict[str, Any]) -> str:
    return detail_text(
        key,
        (
            ("Name", "name"),
            ("ID", "id"),
            ("Prefix", "prefix"),
            ("Kind", "key_kind"),
            ("Status", "status"),
            ("Scopes", "scopes"),
            ("Entities", "entity_ids"),
            ("Tree inherit", "inherit_from_tree"),
            ("Rate/minute", "rate_limit_per_minute"),
            ("Expires", "expires_at"),
            ("Last used", "last_used_at"),
        ),
    )


def _require_secret_sink(show_secret: bool, secret_file: Optional[str]) -> None:
    if show_secret == bool(secret_file):
        raise CliError(
            code="SECRET_SINK_REQUIRED",
            message="Choose exactly one of --show-secret or --secret-file for the one-time API key value.",
            exit_code=EXIT_USAGE,
            hint="Use --secret-file for unattended creation to keep the key out of terminal logs.",
        )


def _consume_created_key(
    result: Any,
    *,
    show_secret: bool,
    secret_file: Optional[str],
    force_secret_file: bool,
) -> tuple[dict[str, Any], str, list[str]]:
    if not isinstance(result, dict) or not isinstance(result.get("api_key"), str) or not result["api_key"]:
        raise CliError(
            code="REMOTE_PROTOCOL_ERROR",
            message="The API returned no one-time key value.",
            exit_code=EXIT_OPERATION_FAILED,
        )
    secret = result["api_key"]
    safe = dict(result)
    warnings = ["This API key is shown only once; store it in an approved secret manager."]
    if show_secret:
        text = f"{_key_text(safe)}\nAPI key: {secret}\nWARNING: this value cannot be retrieved again."
    else:
        assert secret_file is not None
        written = write_secret_file(secret_file, secret, force=force_secret_file)
        safe.pop("api_key", None)
        safe["secret_written_to"] = str(written)
        text = f"{_key_text(safe)}\nOne-time key written to {written} with owner-only permissions."
    return safe, text, warnings


@click.group("api-keys")
def api_keys_group():
    """Create and manage least-privilege personal API keys."""


@api_keys_group.command("list")
def api_keys_list():
    """List the authenticated user's API keys without secret values."""

    target, client = remote_client()
    result, meta = client.request("GET", "/api-keys/")
    items = [item for item in result if isinstance(item, dict)] if isinstance(result, list) else []
    emit_remote_result(
        "api-keys.list",
        {"items": result},
        target=target,
        meta=meta,
        text=records_text(
            items,
            (("NAME", "name"), ("STATUS", "status"), ("PREFIX", "prefix"), ("EXPIRES", "expires_at"), ("ID", "id")),
        ),
    )


@api_keys_group.command("get")
@click.argument("reference")
def api_keys_get(reference: str):
    """Get an API key by UUID or unique exact name."""

    target, client = remote_client()
    result, meta = _resolve_api_key(client, reference)
    emit_remote_result("api-keys.get", result, target=target, meta=meta, text=_key_text(result))


@api_keys_group.command("grantable-scopes")
@click.option("--entity", "entity_reference", default=None)
@click.option("--inherit-tree", is_flag=True)
def api_keys_grantable_scopes(entity_reference: Optional[str], inherit_tree: bool):
    """Ask server policy which scopes the current actor may delegate."""

    target, client = remote_client()
    entity_id = None
    resolution = None
    if entity_reference:
        entity, resolution = resolve_entity(client, entity_reference)
        entity_id = entity["id"]
    result, meta = client.request(
        "GET",
        "/api-keys/grantable-scopes",
        params={"entity_id": entity_id, "inherit_from_tree": inherit_tree},
    )
    scopes = result.get("grantable_scopes", []) if isinstance(result, dict) else []
    emit_remote_result(
        "api-keys.grantable-scopes",
        result,
        target=target,
        meta=meta | ({"entity_resolution": resolution.get("resolution")} if resolution else {}),
        text="\n".join(str(scope) for scope in scopes) if scopes else "No grantable scopes.",
    )


@api_keys_group.command("create")
@click.option("--name", required=True)
@click.option("--scope", "scopes", multiple=True, required=True)
@click.option("--entity", "entity_reference", default=None)
@click.option("--inherit-tree", is_flag=True)
@click.option("--expires-days", type=click.IntRange(min=1), default=None)
@click.option("--rate-limit", type=click.IntRange(min=1), default=60, show_default=True)
@click.option("--ip", "ip_whitelist", multiple=True)
@click.option("--description", default=None)
@click.option("--prefix", "prefix_type", default="sk_live", show_default=True)
@click.option("--show-secret", is_flag=True, help="Print the one-time key in command output.")
@click.option("--secret-file", type=click.Path(dir_okay=False), default=None)
@click.option("--force-secret-file", is_flag=True)
@click.option("--yes", is_flag=True)
def api_keys_create(
    name: str,
    scopes: tuple[str, ...],
    entity_reference: Optional[str],
    inherit_tree: bool,
    expires_days: Optional[int],
    rate_limit: int,
    ip_whitelist: tuple[str, ...],
    description: Optional[str],
    prefix_type: str,
    show_secret: bool,
    secret_file: Optional[str],
    force_secret_file: bool,
    yes: bool,
):
    """Create a key only when an explicit one-time secret destination exists."""

    _require_secret_sink(show_secret, secret_file)
    if secret_file:
        validate_secret_file_target(secret_file, force=force_secret_file)
    target, client = remote_client()
    entity_ids = None
    entity_resolution = None
    if entity_reference:
        entity, entity_resolution = resolve_entity(client, entity_reference)
        entity_ids = [entity["id"]]
    require_confirmation(
        prompt=f"Create API key '{name}' with scopes: {', '.join(scopes)}?",
        yes=yes,
    )
    result, meta = client.request(
        "POST",
        "/api-keys/",
        json_body={
            "name": name,
            "scopes": list(scopes),
            "prefix_type": prefix_type,
            "ip_whitelist": list(ip_whitelist) if ip_whitelist else None,
            "rate_limit_per_minute": rate_limit,
            "expires_in_days": expires_days,
            "description": description,
            "key_kind": "personal",
            "entity_ids": entity_ids,
            "inherit_from_tree": inherit_tree,
        },
    )
    safe, text, warnings = _consume_created_key(
        result,
        show_secret=show_secret,
        secret_file=secret_file,
        force_secret_file=force_secret_file,
    )
    emit_remote_result(
        "api-keys.create",
        safe,
        target=target,
        meta=meta | ({"entity_resolution": entity_resolution.get("resolution")} if entity_resolution else {}),
        text=text,
        changed=True,
        warnings=warnings,
    )


@api_keys_group.command("update")
@click.argument("reference")
@click.option("--from", "json_source", type=click.Path(dir_okay=False))
@click.option("--name", default=None)
@click.option("--scope", "scopes", multiple=True)
@click.option("--clear-scopes", is_flag=True)
@click.option("--status", type=click.Choice(["active", "revoked", "expired"]), default=None)
@click.option("--rate-limit", type=click.IntRange(min=1), default=None)
@click.option("--description", default=None)
@click.option("--inherit-tree/--no-inherit-tree", default=None)
@click.option("--yes", is_flag=True)
def api_keys_update(
    reference: str,
    json_source: Optional[str],
    name: Optional[str],
    scopes: tuple[str, ...],
    clear_scopes: bool,
    status: Optional[str],
    rate_limit: Optional[int],
    description: Optional[str],
    inherit_tree: Optional[bool],
    yes: bool,
):
    """Update key policy after confirmation; scope flags replace the full set."""

    if scopes and clear_scopes:
        raise click.UsageError("Use --scope or --clear-scopes, not both.")
    scope_value: Optional[list[str]] = list(scopes) if scopes else ([] if clear_scopes else None)
    payload = request_payload(
        json_source,
        name=name,
        scopes=scope_value,
        status=status,
        rate_limit_per_minute=rate_limit,
        description=description,
        inherit_from_tree=inherit_tree,
    )
    require_nonempty_payload(payload)
    target, client = remote_client()
    key, resolution = _resolve_api_key(client, reference)
    require_confirmation(prompt=f"Update API key '{key.get('name')}' ({key.get('id')})?", yes=yes)
    result, meta = client.request("PATCH", f"/api-keys/{key['id']}", json_body=payload)
    emit_remote_result(
        "api-keys.update",
        result,
        target=target,
        meta=meta | {"resolution": resolution.get("resolution")},
        text=_key_text(result),
        changed=True,
    )


@api_keys_group.command("rotate")
@click.argument("reference")
@click.option("--show-secret", is_flag=True)
@click.option("--secret-file", type=click.Path(dir_okay=False), default=None)
@click.option("--force-secret-file", is_flag=True)
@click.option("--yes", is_flag=True)
def api_keys_rotate(
    reference: str,
    show_secret: bool,
    secret_file: Optional[str],
    force_secret_file: bool,
    yes: bool,
):
    """Rotate a key and send the new one-time secret to an explicit sink."""

    _require_secret_sink(show_secret, secret_file)
    if secret_file:
        validate_secret_file_target(secret_file, force=force_secret_file)
    target, client = remote_client()
    key, resolution = _resolve_api_key(client, reference)
    require_confirmation(prompt=f"Rotate and revoke API key '{key.get('name')}' ({key.get('id')})?", yes=yes)
    result, meta = client.request("POST", f"/api-keys/{key['id']}/rotate")
    safe, text, warnings = _consume_created_key(
        result,
        show_secret=show_secret,
        secret_file=secret_file,
        force_secret_file=force_secret_file,
    )
    emit_remote_result(
        "api-keys.rotate",
        safe,
        target=target,
        meta=meta | {"resolution": resolution.get("resolution")},
        text=text,
        changed=True,
        warnings=warnings,
    )


@api_keys_group.command("revoke")
@click.argument("reference")
@click.option("--yes", is_flag=True)
def api_keys_revoke(reference: str, yes: bool):
    """Revoke a key after resolving and confirming its exact identity."""

    target, client = remote_client()
    key, resolution = _resolve_api_key(client, reference)
    require_confirmation(prompt=f"Revoke API key '{key.get('name')}' ({key.get('id')})?", yes=yes)
    _, meta = client.request("DELETE", f"/api-keys/{key['id']}")
    emit_remote_result(
        "api-keys.revoke",
        {"id": key["id"], "name": key.get("name"), "revoked": True},
        target=target,
        meta=meta | {"resolution": resolution.get("resolution")},
        text=f"Revoked API key {key.get('name')} ({key['id']}).",
        changed=True,
    )
