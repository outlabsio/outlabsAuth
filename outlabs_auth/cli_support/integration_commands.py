"""Non-human integration principal and system API-key administration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import click

from outlabs_auth.cli_support.api_key_commands import (
    api_key_text,
    consume_created_key,
    require_secret_sink,
)
from outlabs_auth.cli_support.client import RemoteClient
from outlabs_auth.cli_support.entity_commands import resolve_entity
from outlabs_auth.cli_support.payloads import require_nonempty_payload, require_payload_fields
from outlabs_auth.cli_support.resource_common import (
    detail_text,
    emit_remote_result,
    records_text,
    remote_client,
    request_payload,
)
from outlabs_auth.cli_support.role_commands import resolve_role
from outlabs_auth.cli_support.runtime import CliError, EXIT_USAGE, require_confirmation
from outlabs_auth.cli_support.secrets import validate_secret_file_target


@dataclass(frozen=True)
class PrincipalScope:
    """A resolved platform-global or entity-anchored integration scope."""

    kind: str
    path_prefix: str
    label: str
    meta: dict[str, Any]

    @property
    def principals_path(self) -> str:
        return f"{self.path_prefix}/integration-principals"


def _resolve_scope(
    client: RemoteClient,
    *,
    entity_reference: Optional[str],
    platform: bool,
) -> PrincipalScope:
    if bool(entity_reference) == platform:
        raise CliError(
            code="INTEGRATION_SCOPE_REQUIRED",
            message="Choose exactly one of --entity or --platform.",
            exit_code=EXIT_USAGE,
            hint="Use --entity SLUG for an entity-anchored integration or --platform for a global integration.",
        )
    if platform:
        return PrincipalScope(
            kind="platform_global",
            path_prefix="/system",
            label="platform",
            meta={"scope": {"kind": "platform_global"}},
        )
    assert entity_reference is not None
    entity, resolution = resolve_entity(client, entity_reference)
    entity_id = str(entity["id"])
    return PrincipalScope(
        kind="entity",
        path_prefix=f"/entities/{entity_id}",
        label=f"entity {entity.get('slug') or entity.get('name') or entity_id}",
        meta={
            "scope": {"kind": "entity", "entity_id": entity_id},
            "entity_resolution": resolution.get("resolution"),
        },
    )


def _resolve_principal(
    client: RemoteClient,
    scope: PrincipalScope,
    reference: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    return client.resolve_resource(
        reference,
        resource_name="integration_principal",
        detail_path=f"{scope.principals_path}/{{id}}",
        list_path=scope.principals_path,
        exact_fields=("name",),
        max_limit=100,
    )


def _resolve_integration_key(
    client: RemoteClient,
    scope: PrincipalScope,
    principal_id: str,
    reference: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    base_path = f"{scope.principals_path}/{principal_id}/api-keys"
    return client.resolve_resource(
        reference,
        resource_name="integration_api_key",
        detail_path=f"{base_path}/{{id}}",
        list_path=base_path,
        exact_fields=("name",),
        max_limit=100,
    )


def _principal_text(principal: dict[str, Any]) -> str:
    return detail_text(
        principal,
        (
            ("Name", "name"),
            ("ID", "id"),
            ("Status", "status"),
            ("Scope", "scope_kind"),
            ("Entity", "anchor_entity_id"),
            ("Tree inherit", "inherit_from_tree"),
            ("Allowed scopes", "allowed_scopes"),
            ("Effective scopes", "effective_allowed_scopes"),
            ("Roles", "role_ids"),
            ("Description", "description"),
        ),
    )


def _scope_options(command):
    command = click.option(
        "--platform",
        is_flag=True,
        help="Target the platform-global integration-principal collection.",
    )(command)
    command = click.option(
        "--entity",
        "entity_reference",
        default=None,
        help="Target an entity by UUID, slug, or unambiguous name.",
    )(command)
    return command


@click.group("integration-principals")
def integration_principals_group():
    """Manage non-human identities anchored to an entity or the platform."""


@integration_principals_group.command("list")
@_scope_options
@click.option("--page", type=click.IntRange(min=1), default=1, show_default=True)
@click.option("--limit", type=click.IntRange(min=1, max=100), default=20, show_default=True)
@click.option("--status", type=click.Choice(["active", "inactive", "archived"]), default=None)
@click.option("--search", default=None)
@click.option("--all", "all_pages", is_flag=True)
def integration_principals_list(
    entity_reference: Optional[str],
    platform: bool,
    page: int,
    limit: int,
    status: Optional[str],
    search: Optional[str],
    all_pages: bool,
):
    """List principals in one explicit entity or platform scope."""

    target, client = remote_client()
    scope = _resolve_scope(client, entity_reference=entity_reference, platform=platform)
    result, meta = client.paginate(
        scope.principals_path,
        page=page,
        limit=limit,
        max_limit=100,
        all_pages=all_pages,
        params={"status": status, "search": search},
    )
    items = [item for item in result["items"] if isinstance(item, dict)]
    emit_remote_result(
        "integration-principals.list",
        result,
        target=target,
        meta=meta | scope.meta,
        text=records_text(
            items,
            (("NAME", "name"), ("STATUS", "status"), ("SCOPES", "allowed_scopes"), ("ID", "id")),
        ),
    )


@integration_principals_group.command("get")
@click.argument("reference")
@_scope_options
def integration_principals_get(reference: str, entity_reference: Optional[str], platform: bool):
    """Get a principal by UUID or unique exact name in one scope."""

    target, client = remote_client()
    scope = _resolve_scope(client, entity_reference=entity_reference, platform=platform)
    principal, meta = _resolve_principal(client, scope, reference)
    emit_remote_result(
        "integration-principals.get",
        principal,
        target=target,
        meta=meta | scope.meta,
        text=_principal_text(principal),
    )


@integration_principals_group.command("create")
@_scope_options
@click.option("--from", "json_source", type=click.Path(dir_okay=False))
@click.option("--name", default=None)
@click.option("--description", default=None)
@click.option("--allowed-scope", "allowed_scopes", multiple=True)
@click.option("--role", "role_references", multiple=True, help="Role UUID or exact name.")
@click.option("--inherit-tree/--no-inherit-tree", default=None)
@click.option("--yes", is_flag=True)
def integration_principals_create(
    entity_reference: Optional[str],
    platform: bool,
    json_source: Optional[str],
    name: Optional[str],
    description: Optional[str],
    allowed_scopes: tuple[str, ...],
    role_references: tuple[str, ...],
    inherit_tree: Optional[bool],
    yes: bool,
):
    """Create a bounded non-human identity after resolving its roles."""

    target, client = remote_client()
    scope = _resolve_scope(client, entity_reference=entity_reference, platform=platform)
    if scope.kind == "platform_global" and inherit_tree:
        raise CliError(
            code="PLATFORM_TREE_INHERITANCE_INVALID",
            message="A platform-global principal cannot use entity-tree inheritance.",
            exit_code=EXIT_USAGE,
        )
    payload = request_payload(
        json_source,
        name=name,
        description=description,
        allowed_scopes=list(allowed_scopes) if allowed_scopes else None,
        inherit_from_tree=inherit_tree,
    )
    role_ids: list[str] = []
    role_resolutions: list[dict[str, Any]] = []
    for reference in role_references:
        role, resolution = resolve_role(client, reference)
        role_ids.append(str(role["id"]))
        role_resolutions.append(resolution.get("resolution", {}))
    if role_references:
        payload["role_ids"] = role_ids
    require_payload_fields(payload, "name")
    require_confirmation(
        prompt=f"Create integration principal '{payload['name']}' in {scope.label}?",
        yes=yes,
    )
    result, meta = client.request("POST", scope.principals_path, json_body=payload)
    emit_remote_result(
        "integration-principals.create",
        result,
        target=target,
        meta=meta | scope.meta | {"role_resolutions": role_resolutions},
        text=_principal_text(result),
        changed=True,
    )


@integration_principals_group.command("update")
@click.argument("reference")
@_scope_options
@click.option("--from", "json_source", type=click.Path(dir_okay=False))
@click.option("--name", default=None)
@click.option("--description", default=None)
@click.option("--status", type=click.Choice(["active", "inactive", "archived"]), default=None)
@click.option("--allowed-scope", "allowed_scopes", multiple=True)
@click.option("--clear-allowed-scopes", is_flag=True)
@click.option("--role", "role_references", multiple=True)
@click.option("--clear-roles", is_flag=True)
@click.option("--inherit-tree/--no-inherit-tree", default=None)
@click.option("--yes", is_flag=True)
def integration_principals_update(
    reference: str,
    entity_reference: Optional[str],
    platform: bool,
    json_source: Optional[str],
    name: Optional[str],
    description: Optional[str],
    status: Optional[str],
    allowed_scopes: tuple[str, ...],
    clear_allowed_scopes: bool,
    role_references: tuple[str, ...],
    clear_roles: bool,
    inherit_tree: Optional[bool],
    yes: bool,
):
    """Replace selected principal policy fields after exact resolution."""

    if allowed_scopes and clear_allowed_scopes:
        raise click.UsageError("Use --allowed-scope or --clear-allowed-scopes, not both.")
    if role_references and clear_roles:
        raise click.UsageError("Use --role or --clear-roles, not both.")
    target, client = remote_client()
    scope = _resolve_scope(client, entity_reference=entity_reference, platform=platform)
    if scope.kind == "platform_global" and inherit_tree:
        raise CliError(
            code="PLATFORM_TREE_INHERITANCE_INVALID",
            message="A platform-global principal cannot use entity-tree inheritance.",
            exit_code=EXIT_USAGE,
        )
    principal, resolution = _resolve_principal(client, scope, reference)
    allowed_scope_value: Optional[list[str]] = (
        list(allowed_scopes) if allowed_scopes else ([] if clear_allowed_scopes else None)
    )
    payload = request_payload(
        json_source,
        name=name,
        description=description,
        status=status,
        allowed_scopes=allowed_scope_value,
        inherit_from_tree=inherit_tree,
    )
    role_resolutions: list[dict[str, Any]] = []
    if role_references:
        role_ids = []
        for role_reference in role_references:
            role, role_resolution = resolve_role(client, role_reference)
            role_ids.append(str(role["id"]))
            role_resolutions.append(role_resolution.get("resolution", {}))
        payload["role_ids"] = role_ids
    elif clear_roles:
        payload["role_ids"] = []
    require_nonempty_payload(payload)
    require_confirmation(
        prompt=f"Update integration principal '{principal.get('name')}' ({principal['id']})?",
        yes=yes,
    )
    result, meta = client.request(
        "PATCH",
        f"{scope.principals_path}/{principal['id']}",
        json_body=payload,
    )
    emit_remote_result(
        "integration-principals.update",
        result,
        target=target,
        meta=meta | scope.meta | {"resolution": resolution.get("resolution"), "role_resolutions": role_resolutions},
        text=_principal_text(result),
        changed=True,
    )


@integration_principals_group.command("delete")
@click.argument("reference")
@_scope_options
@click.option("--yes", is_flag=True)
def integration_principals_delete(
    reference: str,
    entity_reference: Optional[str],
    platform: bool,
    yes: bool,
):
    """Archive a principal and disable its authority after confirmation."""

    target, client = remote_client()
    scope = _resolve_scope(client, entity_reference=entity_reference, platform=platform)
    principal, resolution = _resolve_principal(client, scope, reference)
    require_confirmation(
        prompt=f"Archive integration principal '{principal.get('name')}' ({principal['id']})?",
        yes=yes,
    )
    _, meta = client.request("DELETE", f"{scope.principals_path}/{principal['id']}")
    emit_remote_result(
        "integration-principals.delete",
        {"id": principal["id"], "name": principal.get("name"), "archived": True},
        target=target,
        meta=meta | scope.meta | {"resolution": resolution.get("resolution")},
        text=f"Archived integration principal {principal.get('name')} ({principal['id']}).",
        changed=True,
    )


@click.group("integration-keys")
def integration_keys_group():
    """Manage one-time system keys owned by an integration principal."""


@integration_keys_group.command("list")
@click.argument("principal")
@_scope_options
@click.option("--page", type=click.IntRange(min=1), default=1, show_default=True)
@click.option("--limit", type=click.IntRange(min=1, max=100), default=20, show_default=True)
@click.option("--status", type=click.Choice(["active", "suspended", "revoked", "expired"]), default=None)
@click.option("--search", default=None)
@click.option("--all", "all_pages", is_flag=True)
def integration_keys_list(
    principal: str,
    entity_reference: Optional[str],
    platform: bool,
    page: int,
    limit: int,
    status: Optional[str],
    search: Optional[str],
    all_pages: bool,
):
    """List redacted keys for one resolved integration principal."""

    target, client = remote_client()
    scope = _resolve_scope(client, entity_reference=entity_reference, platform=platform)
    owner, resolution = _resolve_principal(client, scope, principal)
    path = f"{scope.principals_path}/{owner['id']}/api-keys"
    result, meta = client.paginate(
        path,
        page=page,
        limit=limit,
        max_limit=100,
        all_pages=all_pages,
        params={"status": status, "search": search},
    )
    items = [item for item in result["items"] if isinstance(item, dict)]
    emit_remote_result(
        "integration-keys.list",
        result,
        target=target,
        meta=meta | scope.meta | {"principal_resolution": resolution.get("resolution")},
        text=records_text(
            items,
            (("NAME", "name"), ("STATUS", "status"), ("PREFIX", "prefix"), ("SCOPES", "scopes"), ("ID", "id")),
        ),
    )


@integration_keys_group.command("get")
@click.argument("principal")
@click.argument("reference")
@_scope_options
def integration_keys_get(
    principal: str,
    reference: str,
    entity_reference: Optional[str],
    platform: bool,
):
    """Get a redacted key by UUID or unique name under one principal."""

    target, client = remote_client()
    scope = _resolve_scope(client, entity_reference=entity_reference, platform=platform)
    owner, principal_resolution = _resolve_principal(client, scope, principal)
    key, key_resolution = _resolve_integration_key(client, scope, str(owner["id"]), reference)
    emit_remote_result(
        "integration-keys.get",
        key,
        target=target,
        meta=key_resolution
        | scope.meta
        | {
            "principal_resolution": principal_resolution.get("resolution"),
            "key_resolution": key_resolution.get("resolution"),
        },
        text=api_key_text(key),
    )


@integration_keys_group.command("create")
@click.argument("principal")
@_scope_options
@click.option("--from", "json_source", type=click.Path(dir_okay=False))
@click.option("--name", default=None)
@click.option("--scope", "scopes", multiple=True)
@click.option("--prefix", "prefix_type", default=None)
@click.option("--ip", "ip_whitelist", multiple=True)
@click.option("--rate-limit", type=click.IntRange(min=1), default=None)
@click.option("--expires-days", type=click.IntRange(min=1), default=None)
@click.option("--description", default=None)
@click.option("--show-secret", is_flag=True)
@click.option("--secret-file", type=click.Path(dir_okay=False), default=None)
@click.option("--force-secret-file", is_flag=True)
@click.option("--yes", is_flag=True)
def integration_keys_create(
    principal: str,
    entity_reference: Optional[str],
    platform: bool,
    json_source: Optional[str],
    name: Optional[str],
    scopes: tuple[str, ...],
    prefix_type: Optional[str],
    ip_whitelist: tuple[str, ...],
    rate_limit: Optional[int],
    expires_days: Optional[int],
    description: Optional[str],
    show_secret: bool,
    secret_file: Optional[str],
    force_secret_file: bool,
    yes: bool,
):
    """Create a system key only when its one-time secret has a safe sink."""

    require_secret_sink(show_secret, secret_file)
    if secret_file:
        validate_secret_file_target(secret_file, force=force_secret_file)
    target, client = remote_client()
    scope = _resolve_scope(client, entity_reference=entity_reference, platform=platform)
    owner, resolution = _resolve_principal(client, scope, principal)
    payload = request_payload(
        json_source,
        name=name,
        scopes=list(scopes) if scopes else None,
        prefix_type=prefix_type,
        ip_whitelist=list(ip_whitelist) if ip_whitelist else None,
        rate_limit_per_minute=rate_limit,
        expires_in_days=expires_days,
        description=description,
    )
    require_payload_fields(payload, "name")
    require_confirmation(
        prompt=(
            f"Create system key '{payload['name']}' for integration principal "
            f"'{owner.get('name')}' ({owner['id']})?"
        ),
        yes=yes,
    )
    result, meta = client.request(
        "POST",
        f"{scope.principals_path}/{owner['id']}/api-keys",
        json_body=payload,
    )
    safe, text, warnings = consume_created_key(
        result,
        show_secret=show_secret,
        secret_file=secret_file,
        force_secret_file=force_secret_file,
    )
    emit_remote_result(
        "integration-keys.create",
        safe,
        target=target,
        meta=meta | scope.meta | {"principal_resolution": resolution.get("resolution")},
        text=text,
        changed=True,
        warnings=warnings,
    )


@integration_keys_group.command("update")
@click.argument("principal")
@click.argument("reference")
@_scope_options
@click.option("--from", "json_source", type=click.Path(dir_okay=False))
@click.option("--name", default=None)
@click.option("--scope", "scopes", multiple=True)
@click.option("--clear-scopes", is_flag=True)
@click.option("--ip", "ip_whitelist", multiple=True)
@click.option("--clear-ips", is_flag=True)
@click.option("--rate-limit", type=click.IntRange(min=1), default=None)
@click.option("--status", type=click.Choice(["active", "suspended", "revoked", "expired"]), default=None)
@click.option("--description", default=None)
@click.option("--yes", is_flag=True)
def integration_keys_update(
    principal: str,
    reference: str,
    entity_reference: Optional[str],
    platform: bool,
    json_source: Optional[str],
    name: Optional[str],
    scopes: tuple[str, ...],
    clear_scopes: bool,
    ip_whitelist: tuple[str, ...],
    clear_ips: bool,
    rate_limit: Optional[int],
    status: Optional[str],
    description: Optional[str],
    yes: bool,
):
    """Update bounded system-key policy after exact owner/key resolution."""

    if scopes and clear_scopes:
        raise click.UsageError("Use --scope or --clear-scopes, not both.")
    if ip_whitelist and clear_ips:
        raise click.UsageError("Use --ip or --clear-ips, not both.")
    target, client = remote_client()
    scope = _resolve_scope(client, entity_reference=entity_reference, platform=platform)
    owner, principal_resolution = _resolve_principal(client, scope, principal)
    key, key_resolution = _resolve_integration_key(client, scope, str(owner["id"]), reference)
    payload = request_payload(
        json_source,
        name=name,
        scopes=list(scopes) if scopes else ([] if clear_scopes else None),
        ip_whitelist=list(ip_whitelist) if ip_whitelist else ([] if clear_ips else None),
        rate_limit_per_minute=rate_limit,
        status=status,
        description=description,
    )
    require_nonempty_payload(payload)
    require_confirmation(
        prompt=f"Update system key '{key.get('name')}' ({key['id']})?",
        yes=yes,
    )
    result, meta = client.request(
        "PATCH",
        f"{scope.principals_path}/{owner['id']}/api-keys/{key['id']}",
        json_body=payload,
    )
    emit_remote_result(
        "integration-keys.update",
        result,
        target=target,
        meta=meta
        | scope.meta
        | {
            "principal_resolution": principal_resolution.get("resolution"),
            "key_resolution": key_resolution.get("resolution"),
        },
        text=api_key_text(result),
        changed=True,
    )


@integration_keys_group.command("rotate")
@click.argument("principal")
@click.argument("reference")
@_scope_options
@click.option("--show-secret", is_flag=True)
@click.option("--secret-file", type=click.Path(dir_okay=False), default=None)
@click.option("--force-secret-file", is_flag=True)
@click.option("--yes", is_flag=True)
def integration_keys_rotate(
    principal: str,
    reference: str,
    entity_reference: Optional[str],
    platform: bool,
    show_secret: bool,
    secret_file: Optional[str],
    force_secret_file: bool,
    yes: bool,
):
    """Rotate a system key and atomically consume its one-time replacement."""

    require_secret_sink(show_secret, secret_file)
    if secret_file:
        validate_secret_file_target(secret_file, force=force_secret_file)
    target, client = remote_client()
    scope = _resolve_scope(client, entity_reference=entity_reference, platform=platform)
    owner, principal_resolution = _resolve_principal(client, scope, principal)
    key, key_resolution = _resolve_integration_key(client, scope, str(owner["id"]), reference)
    require_confirmation(
        prompt=f"Rotate and revoke system key '{key.get('name')}' ({key['id']})?",
        yes=yes,
    )
    result, meta = client.request(
        "POST",
        f"{scope.principals_path}/{owner['id']}/api-keys/{key['id']}/rotate",
    )
    safe, text, warnings = consume_created_key(
        result,
        show_secret=show_secret,
        secret_file=secret_file,
        force_secret_file=force_secret_file,
    )
    emit_remote_result(
        "integration-keys.rotate",
        safe,
        target=target,
        meta=meta
        | scope.meta
        | {
            "principal_resolution": principal_resolution.get("resolution"),
            "key_resolution": key_resolution.get("resolution"),
        },
        text=text,
        changed=True,
        warnings=warnings,
    )


@integration_keys_group.command("revoke")
@click.argument("principal")
@click.argument("reference")
@_scope_options
@click.option("--yes", is_flag=True)
def integration_keys_revoke(
    principal: str,
    reference: str,
    entity_reference: Optional[str],
    platform: bool,
    yes: bool,
):
    """Permanently revoke a resolved system key after confirmation."""

    target, client = remote_client()
    scope = _resolve_scope(client, entity_reference=entity_reference, platform=platform)
    owner, principal_resolution = _resolve_principal(client, scope, principal)
    key, key_resolution = _resolve_integration_key(client, scope, str(owner["id"]), reference)
    require_confirmation(
        prompt=f"Revoke system key '{key.get('name')}' ({key['id']})?",
        yes=yes,
    )
    _, meta = client.request(
        "DELETE",
        f"{scope.principals_path}/{owner['id']}/api-keys/{key['id']}",
    )
    emit_remote_result(
        "integration-keys.revoke",
        {"id": key["id"], "name": key.get("name"), "revoked": True},
        target=target,
        meta=meta
        | scope.meta
        | {
            "principal_resolution": principal_resolution.get("resolution"),
            "key_resolution": key_resolution.get("resolution"),
        },
        text=f"Revoked system key {key.get('name')} ({key['id']}).",
        changed=True,
    )
