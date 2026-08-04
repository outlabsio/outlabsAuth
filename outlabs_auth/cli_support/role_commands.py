"""Role administration commands backed by the mounted roles router."""

from __future__ import annotations

from typing import Any, Optional

import click

from outlabs_auth.cli_support.client import RemoteClient
from outlabs_auth.cli_support.payloads import require_nonempty_payload, require_payload_fields
from outlabs_auth.cli_support.resource_common import (
    detail_text,
    emit_remote_result,
    records_text,
    remote_client,
    request_payload,
)
from outlabs_auth.cli_support.runtime import require_confirmation


def _resolve_role(client: RemoteClient, reference: str) -> tuple[dict[str, Any], dict[str, Any]]:
    return client.resolve_resource(
        reference,
        resource_name="role",
        detail_path="/roles/{id}",
        list_path="/roles/",
        exact_fields=("name", "display_name"),
        max_limit=100,
    )


def _role_text(role: dict[str, Any]) -> str:
    return detail_text(
        role,
        (
            ("Name", "name"),
            ("Display name", "display_name"),
            ("ID", "id"),
            ("Status", "status"),
            ("Scope", "scope"),
            ("Global", "is_global"),
            ("Auto assigned", "is_auto_assigned"),
            ("Permissions", "permissions"),
            ("Root entity", "root_entity_name"),
            ("Scope entity", "scope_entity_name"),
        ),
    )


@click.group("roles")
def roles_group():
    """List, inspect, create, update, archive, and grant roles."""


@roles_group.command("list")
@click.option("--page", type=click.IntRange(min=1), default=1, show_default=True)
@click.option("--limit", type=click.IntRange(min=1, max=100), default=20, show_default=True)
@click.option("--search", default=None)
@click.option("--global/--not-global", "is_global", default=None)
@click.option("--root-entity-id", default=None)
@click.option("--all", "all_pages", is_flag=True, help="Fetch all result pages.")
def roles_list(
    page: int,
    limit: int,
    search: Optional[str],
    is_global: Optional[bool],
    root_entity_id: Optional[str],
    all_pages: bool,
):
    """List roles with server-side filters and optional auto-pagination."""

    target, client = remote_client()
    result, meta = client.paginate(
        "/roles/",
        page=page,
        limit=limit,
        max_limit=100,
        all_pages=all_pages,
        params={"search": search, "is_global": is_global, "root_entity_id": root_entity_id},
    )
    items = [item for item in result["items"] if isinstance(item, dict)]
    emit_remote_result(
        "roles.list",
        result,
        target=target,
        meta=meta,
        text=records_text(
            items,
            (("NAME", "name"), ("STATUS", "status"), ("SCOPE", "scope"), ("GLOBAL", "is_global"), ("ID", "id")),
        ),
    )


@roles_group.command("get")
@click.argument("reference")
def roles_get(reference: str):
    """Get a role by UUID, exact name, or unambiguous search."""

    target, client = remote_client()
    role, meta = _resolve_role(client, reference)
    emit_remote_result("roles.get", role, target=target, meta=meta, text=_role_text(role))


@roles_group.command("create")
@click.option("--from", "json_source", type=click.Path(dir_okay=False), help="Base JSON object from FILE or -.")
@click.option("--name", default=None)
@click.option("--display-name", default=None)
@click.option("--description", default=None)
@click.option("--permission", "permissions", multiple=True)
@click.option("--global/--not-global", "is_global", default=None)
@click.option("--status", type=click.Choice(["active", "inactive"]), default=None)
@click.option("--root-entity-id", default=None)
@click.option("--assignable-at", "assignable_at_types", multiple=True, metavar="ENTITY_TYPE")
@click.option("--scope-entity-id", default=None)
@click.option("--scope", type=click.Choice(["entity_only", "hierarchy"]), default=None)
@click.option("--auto-assigned/--not-auto-assigned", "is_auto_assigned", default=None)
def roles_create(
    json_source: Optional[str],
    name: Optional[str],
    display_name: Optional[str],
    description: Optional[str],
    permissions: tuple[str, ...],
    is_global: Optional[bool],
    status: Optional[str],
    root_entity_id: Optional[str],
    assignable_at_types: tuple[str, ...],
    scope_entity_id: Optional[str],
    scope: Optional[str],
    is_auto_assigned: Optional[bool],
):
    """Create a role from explicit flags and/or a JSON request object."""

    payload = request_payload(
        json_source,
        name=name,
        display_name=display_name,
        description=description,
        permissions=list(permissions) if permissions else None,
        is_global=is_global,
        status=status,
        root_entity_id=root_entity_id,
        assignable_at_types=list(assignable_at_types) if assignable_at_types else None,
        scope_entity_id=scope_entity_id,
        scope=scope,
        is_auto_assigned=is_auto_assigned,
    )
    require_payload_fields(payload, "name", "display_name")
    target, client = remote_client()
    role, meta = client.request("POST", "/roles/", json_body=payload)
    emit_remote_result("roles.create", role, target=target, meta=meta, text=_role_text(role), changed=True)


@roles_group.command("update")
@click.argument("reference")
@click.option("--from", "json_source", type=click.Path(dir_okay=False), help="Base JSON object from FILE or -.")
@click.option("--display-name", default=None)
@click.option("--description", default=None)
@click.option("--permission", "permissions", multiple=True, help="Replace permissions with these names.")
@click.option("--clear-permissions", is_flag=True)
@click.option("--global/--not-global", "is_global", default=None)
@click.option("--status", type=click.Choice(["active", "inactive"]), default=None)
@click.option("--assignable-at", "assignable_at_types", multiple=True, metavar="ENTITY_TYPE")
@click.option("--clear-assignable-at", is_flag=True)
@click.option("--scope", type=click.Choice(["entity_only", "hierarchy"]), default=None)
@click.option("--auto-assigned/--not-auto-assigned", "is_auto_assigned", default=None)
def roles_update(
    reference: str,
    json_source: Optional[str],
    display_name: Optional[str],
    description: Optional[str],
    permissions: tuple[str, ...],
    clear_permissions: bool,
    is_global: Optional[bool],
    status: Optional[str],
    assignable_at_types: tuple[str, ...],
    clear_assignable_at: bool,
    scope: Optional[str],
    is_auto_assigned: Optional[bool],
):
    """Update mutable role fields; list flags replace their complete field."""

    if permissions and clear_permissions:
        raise click.UsageError("Use --permission or --clear-permissions, not both.")
    if assignable_at_types and clear_assignable_at:
        raise click.UsageError("Use --assignable-at or --clear-assignable-at, not both.")
    permission_value: Optional[list[str]] = list(permissions) if permissions else ([] if clear_permissions else None)
    assignable_value: Optional[list[str]] = (
        list(assignable_at_types) if assignable_at_types else ([] if clear_assignable_at else None)
    )
    payload = request_payload(
        json_source,
        display_name=display_name,
        description=description,
        permissions=permission_value,
        is_global=is_global,
        status=status,
        assignable_at_types=assignable_value,
        scope=scope,
        is_auto_assigned=is_auto_assigned,
    )
    require_nonempty_payload(payload)
    target, client = remote_client()
    role, resolution = _resolve_role(client, reference)
    result, meta = client.request("PATCH", f"/roles/{role['id']}", json_body=payload)
    emit_remote_result(
        "roles.update",
        result,
        target=target,
        meta=meta | {"resolution": resolution.get("resolution")},
        text=_role_text(result),
        changed=True,
    )


@roles_group.command("delete")
@click.argument("reference")
@click.option("--yes", is_flag=True, help="Confirm archival without prompting.")
def roles_delete(reference: str, yes: bool):
    """Archive a role after resolving and displaying its exact identity."""

    target, client = remote_client()
    role, resolution = _resolve_role(client, reference)
    require_confirmation(prompt=f"Archive role '{role.get('name')}' ({role.get('id')})?", yes=yes)
    _, meta = client.request("DELETE", f"/roles/{role['id']}")
    emit_remote_result(
        "roles.delete",
        {"id": role["id"], "name": role.get("name"), "archived": True},
        target=target,
        meta=meta | {"resolution": resolution.get("resolution")},
        text=f"Archived role {role.get('name')} ({role['id']}).",
        changed=True,
    )


def _change_role_permissions(
    reference: str,
    permissions: tuple[str, ...],
    *,
    remove: bool,
    yes: bool,
) -> None:
    target, client = remote_client()
    role, resolution = _resolve_role(client, reference)
    if not remove:
        require_confirmation(
            prompt=f"Grant {', '.join(permissions)} to role '{role.get('name')}'?",
            yes=yes,
        )
    method = "DELETE" if remove else "POST"
    result, meta = client.request(method, f"/roles/{role['id']}/permissions", json_body=list(permissions))
    command = "roles.revoke" if remove else "roles.grant"
    emit_remote_result(
        command,
        result,
        target=target,
        meta=meta | {"resolution": resolution.get("resolution")},
        text=_role_text(result),
        changed=True,
    )


@roles_group.command("grant")
@click.argument("reference")
@click.argument("permissions", nargs=-1, required=True)
@click.option("--yes", is_flag=True)
def roles_grant(reference: str, permissions: tuple[str, ...], yes: bool):
    """Add one or more permission names to a role."""

    _change_role_permissions(reference, permissions, remove=False, yes=yes)


@roles_group.command("revoke")
@click.argument("reference")
@click.argument("permissions", nargs=-1, required=True)
def roles_revoke(reference: str, permissions: tuple[str, ...]):
    """Remove one or more permission names from a role."""

    _change_role_permissions(reference, permissions, remove=True, yes=True)
