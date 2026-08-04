"""Permission catalog, checking, and explanation commands."""

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
from outlabs_auth.cli_support.runtime import CliError, EXIT_OPERATION_FAILED, require_confirmation


def resolve_permission(client: RemoteClient, reference: str) -> tuple[dict[str, Any], dict[str, Any]]:
    return client.resolve_resource(
        reference,
        resource_name="permission",
        detail_path="/permissions/{id}",
        list_path="/permissions/",
        exact_fields=("name", "display_name"),
        search_param=None,
        max_limit=1000,
    )


def _resolve_entity(client: RemoteClient, reference: str) -> tuple[dict[str, Any], dict[str, Any]]:
    return client.resolve_resource(
        reference,
        resource_name="entity",
        detail_path="/entities/{id}",
        list_path="/entities/",
        exact_fields=("slug", "name", "display_name"),
        max_limit=1000,
    )


def _permission_text(permission: dict[str, Any]) -> str:
    return detail_text(
        permission,
        (
            ("Name", "name"),
            ("Display name", "display_name"),
            ("ID", "id"),
            ("Status", "status"),
            ("Active", "is_active"),
            ("System", "is_system"),
            ("Resource", "resource"),
            ("Action", "action"),
            ("Tags", "tags"),
            ("Description", "description"),
        ),
    )


def _matches_permission(grant: str, requested: str) -> bool:
    grant_parts = grant.casefold().split(":")
    requested_parts = requested.casefold().split(":")
    if len(grant_parts) != 2 or len(requested_parts) != 2:
        return grant.casefold() == requested.casefold()
    return all(granted == "*" or granted == needed for granted, needed in zip(grant_parts, requested_parts))


@click.group("permissions")
def permissions_group():
    """Inspect, explain, check, and manage permission definitions."""


@permissions_group.command("list")
@click.option("--page", type=click.IntRange(min=1), default=1, show_default=True)
@click.option("--limit", type=click.IntRange(min=1, max=1000), default=100, show_default=True)
@click.option("--resource", default=None)
@click.option("--all", "all_pages", is_flag=True)
def permissions_list(page: int, limit: int, resource: Optional[str], all_pages: bool):
    """List permission definitions, optionally filtered by resource."""

    target, client = remote_client()
    result, meta = client.paginate(
        "/permissions/",
        page=page,
        limit=limit,
        max_limit=1000,
        all_pages=all_pages,
        params={"resource": resource},
    )
    items = [item for item in result["items"] if isinstance(item, dict)]
    emit_remote_result(
        "permissions.list",
        result,
        target=target,
        meta=meta,
        text=records_text(
            items,
            (("NAME", "name"), ("STATUS", "status"), ("ACTIVE", "is_active"), ("SYSTEM", "is_system"), ("ID", "id")),
        ),
    )


@permissions_group.command("get")
@click.argument("reference")
def permissions_get(reference: str):
    """Get a permission by UUID or exact canonical name."""

    target, client = remote_client()
    permission, meta = resolve_permission(client, reference)
    emit_remote_result(
        "permissions.get",
        permission,
        target=target,
        meta=meta,
        text=_permission_text(permission),
    )


@permissions_group.command("create")
@click.option("--from", "json_source", type=click.Path(dir_okay=False))
@click.option("--name", default=None, help="Canonical resource:action name.")
@click.option("--display-name", default=None)
@click.option("--description", default=None)
@click.option("--system/--not-system", "is_system", default=None)
@click.option("--status", type=click.Choice(["active", "inactive"]), default=None)
@click.option("--active/--inactive", "is_active", default=None)
@click.option("--tag", "tags", multiple=True)
def permissions_create(
    json_source: Optional[str],
    name: Optional[str],
    display_name: Optional[str],
    description: Optional[str],
    is_system: Optional[bool],
    status: Optional[str],
    is_active: Optional[bool],
    tags: tuple[str, ...],
):
    """Create a permission definition from flags and/or JSON."""

    payload = request_payload(
        json_source,
        name=name,
        display_name=display_name,
        description=description,
        is_system=is_system,
        status=status,
        is_active=is_active,
        tags=list(tags) if tags else None,
    )
    require_payload_fields(payload, "name", "display_name")
    target, client = remote_client()
    result, meta = client.request("POST", "/permissions/", json_body=payload)
    emit_remote_result(
        "permissions.create",
        result,
        target=target,
        meta=meta,
        text=_permission_text(result),
        changed=True,
    )


@permissions_group.command("update")
@click.argument("reference")
@click.option("--from", "json_source", type=click.Path(dir_okay=False))
@click.option("--display-name", default=None)
@click.option("--description", default=None)
@click.option("--status", type=click.Choice(["active", "inactive"]), default=None)
@click.option("--active/--inactive", "is_active", default=None)
@click.option("--tag", "tags", multiple=True, help="Replace the complete tag set.")
@click.option("--clear-tags", is_flag=True)
def permissions_update(
    reference: str,
    json_source: Optional[str],
    display_name: Optional[str],
    description: Optional[str],
    status: Optional[str],
    is_active: Optional[bool],
    tags: tuple[str, ...],
    clear_tags: bool,
):
    """Update mutable permission metadata."""

    if tags and clear_tags:
        raise click.UsageError("Use --tag or --clear-tags, not both.")
    tag_value: Optional[list[str]] = list(tags) if tags else ([] if clear_tags else None)
    payload = request_payload(
        json_source,
        display_name=display_name,
        description=description,
        status=status,
        is_active=is_active,
        tags=tag_value,
    )
    require_nonempty_payload(payload)
    target, client = remote_client()
    permission, resolution = resolve_permission(client, reference)
    result, meta = client.request("PATCH", f"/permissions/{permission['id']}", json_body=payload)
    emit_remote_result(
        "permissions.update",
        result,
        target=target,
        meta=meta | {"resolution": resolution.get("resolution")},
        text=_permission_text(result),
        changed=True,
    )


@permissions_group.command("delete")
@click.argument("reference")
@click.option("--yes", is_flag=True)
def permissions_delete(reference: str, yes: bool):
    """Archive a non-system permission after exact resolution."""

    target, client = remote_client()
    permission, resolution = resolve_permission(client, reference)
    require_confirmation(
        prompt=f"Archive permission '{permission.get('name')}' ({permission.get('id')})?",
        yes=yes,
    )
    _, meta = client.request("DELETE", f"/permissions/{permission['id']}")
    emit_remote_result(
        "permissions.delete",
        {"id": permission["id"], "name": permission.get("name"), "archived": True},
        target=target,
        meta=meta | {"resolution": resolution.get("resolution")},
        text=f"Archived permission {permission.get('name')} ({permission['id']}).",
        changed=True,
    )


@permissions_group.command("me")
@click.option("--entity", "entity_reference", default=None, help="Optional entity UUID, slug, or name.")
def permissions_me(entity_reference: Optional[str]):
    """List the authenticated user's effective permission names."""

    target, client = remote_client()
    entity_id = None
    resolution = None
    if entity_reference:
        entity, resolution = _resolve_entity(client, entity_reference)
        entity_id = entity["id"]
    result, meta = client.request("GET", "/permissions/me", params={"entity_id": entity_id})
    names = result if isinstance(result, list) else []
    emit_remote_result(
        "permissions.me",
        {"permissions": names, "entity_id": entity_id},
        target=target,
        meta=meta | ({"entity_resolution": resolution.get("resolution")} if resolution else {}),
        text="\n".join(str(name) for name in names) if names else "No effective permissions.",
    )


@permissions_group.command("check")
@click.argument("user_reference")
@click.argument("permission_names", nargs=-1, required=True)
@click.option("--entity", "entity_reference", default=None)
def permissions_check(user_reference: str, permission_names: tuple[str, ...], entity_reference: Optional[str]):
    """Authoritatively check one or more permissions for a user and context."""

    target, client = remote_client()
    user, user_resolution = client.resolve_user(user_reference)
    entity_id = None
    entity_resolution = None
    if entity_reference:
        entity, entity_resolution = _resolve_entity(client, entity_reference)
        entity_id = entity["id"]
    result, meta = client.request(
        "POST",
        "/permissions/check",
        json_body={"user_id": user["id"], "permissions": list(permission_names), "entity_id": entity_id},
    )
    checks = result.get("results", {}) if isinstance(result, dict) else {}
    text_output = "\n".join(f"{'ALLOW' if allowed else 'DENY '} {name}" for name, allowed in checks.items())
    emit_remote_result(
        "permissions.check",
        result,
        target=target,
        meta=meta
        | {"user_resolution": user_resolution.get("resolution")}
        | ({"entity_resolution": entity_resolution.get("resolution")} if entity_resolution else {}),
        text=text_output or "No permission checks returned.",
    )


@permissions_group.command("explain")
@click.argument("permission_name")
@click.option("--user", "user_reference", default=None, help="User UUID/email; defaults to the authenticated user.")
@click.option("--entity", "entity_reference", default=None, help="Evaluate in an entity context.")
def permissions_explain(
    permission_name: str,
    user_reference: Optional[str],
    entity_reference: Optional[str],
):
    """Explain whether and why a user receives a permission."""

    target, client = remote_client()
    if user_reference:
        user, user_resolution = client.resolve_user(user_reference)
    else:
        identity, identity_meta = client.whoami()
        if not isinstance(identity, dict) or not identity.get("id"):
            raise CliError(
                code="REMOTE_PROTOCOL_ERROR",
                message="The current-user endpoint did not return a user ID.",
                exit_code=EXIT_OPERATION_FAILED,
            )
        user = identity
        user_resolution = {"resolution": {"kind": "current", "id": identity["id"]}, **identity_meta}

    sources, source_meta = client.request("GET", f"/users/{user['id']}/permissions")
    source_items = [item for item in sources if isinstance(item, dict)] if isinstance(sources, list) else []
    matching_sources = []
    for source in source_items:
        permission = source.get("permission")
        granted_name = permission.get("name") if isinstance(permission, dict) else None
        if isinstance(granted_name, str) and _matches_permission(granted_name, permission_name):
            matching_sources.append(source)

    entity_id = None
    entity_resolution = None
    authoritative_check = None
    if entity_reference:
        entity, entity_resolution = _resolve_entity(client, entity_reference)
        entity_id = entity["id"]
        checked, check_meta = client.request(
            "POST",
            "/permissions/check",
            json_body={"user_id": user["id"], "permissions": [permission_name], "entity_id": entity_id},
        )
        authoritative_check = (
            bool(checked.get("results", {}).get(permission_name)) if isinstance(checked, dict) else False
        )
        source_meta = source_meta | {"check": check_meta}

    is_superuser = bool(user.get("is_superuser"))
    granted = authoritative_check if authoritative_check is not None else (is_superuser or bool(matching_sources))
    if not granted:
        reason = "no_matching_grant"
    elif is_superuser and not matching_sources:
        reason = "superuser_bypass"
    elif matching_sources:
        reason = "matching_role_or_direct_grant"
    else:
        reason = "context_policy_grant"
    result = {
        "permission": permission_name,
        "granted": granted,
        "reason": reason,
        "user": {"id": user.get("id"), "email": user.get("email"), "is_superuser": is_superuser},
        "entity_id": entity_id,
        "matching_sources": matching_sources,
        "source_count": len(matching_sources),
        "authoritative_context_check": authoritative_check,
    }
    source_names = [str(source.get("source_name") or source.get("source") or "unknown") for source in matching_sources]
    text_output = (
        f"{'ALLOW' if granted else 'DENY'} {permission_name}\n"
        f"User:   {user.get('email') or user.get('id')}\n"
        f"Entity: {entity_id or '(global aggregate)'}\n"
        f"Reason: {reason}\n"
        f"Sources: {', '.join(source_names) if source_names else '(none)'}"
    )
    emit_remote_result(
        "permissions.explain",
        result,
        target=target,
        meta=source_meta
        | {"user_resolution": user_resolution.get("resolution")}
        | ({"entity_resolution": entity_resolution.get("resolution")} if entity_resolution else {}),
        text=text_output,
    )
