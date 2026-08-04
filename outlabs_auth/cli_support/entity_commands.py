"""Entity hierarchy administration commands."""

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
from outlabs_auth.cli_support.runtime import CliError, EXIT_USAGE, require_confirmation


def resolve_entity(client: RemoteClient, reference: str) -> tuple[dict[str, Any], dict[str, Any]]:
    return client.resolve_resource(
        reference,
        resource_name="entity",
        detail_path="/entities/{id}",
        list_path="/entities/",
        exact_fields=("slug", "name", "display_name"),
        max_limit=1000,
    )


def _entity_text(entity: dict[str, Any]) -> str:
    return detail_text(
        entity,
        (
            ("Name", "name"),
            ("Display name", "display_name"),
            ("Slug", "slug"),
            ("ID", "id"),
            ("Class", "entity_class"),
            ("Type", "entity_type"),
            ("Status", "status"),
            ("Parent", "parent_entity_id"),
            ("Max members", "max_members"),
            ("Description", "description"),
        ),
    )


@click.group("entities")
def entities_group():
    """Inspect and administer the EnterpriseRBAC entity hierarchy."""


@entities_group.command("list")
@click.option("--page", type=click.IntRange(min=1), default=1, show_default=True)
@click.option("--limit", type=click.IntRange(min=1, max=1000), default=100, show_default=True)
@click.option("--search", default=None)
@click.option("--class", "entity_class", type=click.Choice(["structural", "access_group"]), default=None)
@click.option("--type", "entity_type", default=None)
@click.option("--parent", "parent_reference", default=None, help="Parent UUID, slug, or name.")
@click.option("--root-only", is_flag=True)
@click.option("--all", "all_pages", is_flag=True)
def entities_list(
    page: int,
    limit: int,
    search: Optional[str],
    entity_class: Optional[str],
    entity_type: Optional[str],
    parent_reference: Optional[str],
    root_only: bool,
    all_pages: bool,
):
    """List entities with hierarchy-aware filters."""

    target, client = remote_client()
    parent_id = None
    parent_resolution = None
    if parent_reference:
        parent, parent_resolution = resolve_entity(client, parent_reference)
        parent_id = parent["id"]
    result, meta = client.paginate(
        "/entities/",
        page=page,
        limit=limit,
        max_limit=1000,
        all_pages=all_pages,
        params={
            "search": search,
            "entity_class": entity_class,
            "entity_type": entity_type,
            "parent_id": parent_id,
            "root_only": root_only,
        },
    )
    items = [item for item in result["items"] if isinstance(item, dict)]
    emit_remote_result(
        "entities.list",
        result,
        target=target,
        meta=meta | ({"parent_resolution": parent_resolution.get("resolution")} if parent_resolution else {}),
        text=records_text(
            items,
            (("NAME", "name"), ("TYPE", "entity_type"), ("CLASS", "entity_class"), ("STATUS", "status"), ("ID", "id")),
        ),
    )


@entities_group.command("get")
@click.argument("reference")
def entities_get(reference: str):
    """Get an entity by UUID, slug, exact name, or unambiguous search."""

    target, client = remote_client()
    entity, meta = resolve_entity(client, reference)
    emit_remote_result("entities.get", entity, target=target, meta=meta, text=_entity_text(entity))


@entities_group.command("create")
@click.option("--from", "json_source", type=click.Path(dir_okay=False))
@click.option("--name", default=None)
@click.option("--display-name", default=None)
@click.option("--slug", default=None)
@click.option("--description", default=None)
@click.option("--class", "entity_class", type=click.Choice(["structural", "access_group"]), default=None)
@click.option("--type", "entity_type", default=None)
@click.option("--parent", "parent_reference", default=None, help="Parent UUID, slug, or name.")
@click.option("--status", type=click.Choice(["active", "inactive", "archived"]), default=None)
@click.option("--allowed-child-class", "allowed_child_classes", multiple=True)
@click.option("--allowed-child-type", "allowed_child_types", multiple=True)
@click.option("--max-members", type=click.IntRange(min=1), default=None)
def entities_create(
    json_source: Optional[str],
    name: Optional[str],
    display_name: Optional[str],
    slug: Optional[str],
    description: Optional[str],
    entity_class: Optional[str],
    entity_type: Optional[str],
    parent_reference: Optional[str],
    status: Optional[str],
    allowed_child_classes: tuple[str, ...],
    allowed_child_types: tuple[str, ...],
    max_members: Optional[int],
):
    """Create an entity; advanced policy fields can be supplied with --from."""

    target, client = remote_client()
    parent_id = None
    parent_resolution = None
    if parent_reference:
        parent, parent_resolution = resolve_entity(client, parent_reference)
        parent_id = parent["id"]
    payload = request_payload(
        json_source,
        name=name,
        display_name=display_name,
        slug=slug,
        description=description,
        entity_class=entity_class,
        entity_type=entity_type,
        parent_entity_id=parent_id,
        status=status,
        allowed_child_classes=list(allowed_child_classes) if allowed_child_classes else None,
        allowed_child_types=list(allowed_child_types) if allowed_child_types else None,
        max_members=max_members,
    )
    require_payload_fields(payload, "name", "display_name", "slug", "entity_class", "entity_type")
    result, meta = client.request("POST", "/entities/", json_body=payload)
    emit_remote_result(
        "entities.create",
        result,
        target=target,
        meta=meta | ({"parent_resolution": parent_resolution.get("resolution")} if parent_resolution else {}),
        text=_entity_text(result),
        changed=True,
    )


@entities_group.command("update")
@click.argument("reference")
@click.option("--from", "json_source", type=click.Path(dir_okay=False))
@click.option("--display-name", default=None)
@click.option("--description", default=None)
@click.option("--status", type=click.Choice(["active", "inactive", "archived"]), default=None)
@click.option("--allowed-child-class", "allowed_child_classes", multiple=True)
@click.option("--clear-allowed-child-classes", is_flag=True)
@click.option("--allowed-child-type", "allowed_child_types", multiple=True)
@click.option("--clear-allowed-child-types", is_flag=True)
@click.option("--max-members", type=click.IntRange(min=1), default=None)
def entities_update(
    reference: str,
    json_source: Optional[str],
    display_name: Optional[str],
    description: Optional[str],
    status: Optional[str],
    allowed_child_classes: tuple[str, ...],
    clear_allowed_child_classes: bool,
    allowed_child_types: tuple[str, ...],
    clear_allowed_child_types: bool,
    max_members: Optional[int],
):
    """Update entity metadata and child-policy constraints."""

    if allowed_child_classes and clear_allowed_child_classes:
        raise click.UsageError("Use --allowed-child-class or --clear-allowed-child-classes, not both.")
    if allowed_child_types and clear_allowed_child_types:
        raise click.UsageError("Use --allowed-child-type or --clear-allowed-child-types, not both.")
    class_value: Optional[list[str]] = (
        list(allowed_child_classes) if allowed_child_classes else ([] if clear_allowed_child_classes else None)
    )
    type_value: Optional[list[str]] = (
        list(allowed_child_types) if allowed_child_types else ([] if clear_allowed_child_types else None)
    )
    payload = request_payload(
        json_source,
        display_name=display_name,
        description=description,
        status=status,
        allowed_child_classes=class_value,
        allowed_child_types=type_value,
        max_members=max_members,
    )
    require_nonempty_payload(payload)
    target, client = remote_client()
    entity, resolution = resolve_entity(client, reference)
    result, meta = client.request("PATCH", f"/entities/{entity['id']}", json_body=payload)
    emit_remote_result(
        "entities.update",
        result,
        target=target,
        meta=meta | {"resolution": resolution.get("resolution")},
        text=_entity_text(result),
        changed=True,
    )


@entities_group.command("move")
@click.argument("reference")
@click.option("--parent", "parent_reference", default=None, help="New parent UUID, slug, or name.")
@click.option("--root", "move_to_root", is_flag=True, help="Move the entity to the hierarchy root.")
@click.option("--yes", is_flag=True)
def entities_move(reference: str, parent_reference: Optional[str], move_to_root: bool, yes: bool):
    """Re-parent an entity after resolving both sides and confirming the move."""

    if bool(parent_reference) == move_to_root:
        raise CliError(
            code="PARENT_SELECTION_REQUIRED",
            message="Choose exactly one of --parent or --root.",
            exit_code=EXIT_USAGE,
        )
    target, client = remote_client()
    entity, resolution = resolve_entity(client, reference)
    parent = None
    parent_resolution = None
    if parent_reference:
        parent, parent_resolution = resolve_entity(client, parent_reference)
    parent_id = parent.get("id") if parent else None
    destination = f"'{parent.get('name')}' ({parent_id})" if parent else "the hierarchy root"
    require_confirmation(prompt=f"Move entity '{entity.get('name')}' to {destination}?", yes=yes)
    result, meta = client.request(
        "POST",
        f"/entities/{entity['id']}/move",
        json_body={"new_parent_id": parent_id},
    )
    emit_remote_result(
        "entities.move",
        result,
        target=target,
        meta=meta
        | {"resolution": resolution.get("resolution")}
        | ({"parent_resolution": parent_resolution.get("resolution")} if parent_resolution else {}),
        text=_entity_text(result),
        changed=True,
    )


@entities_group.command("delete")
@click.argument("reference")
@click.option("--cascade", is_flag=True, help="Also archive descendants when supported by the API.")
@click.option("--yes", is_flag=True)
def entities_delete(reference: str, cascade: bool, yes: bool):
    """Archive an entity, with explicit confirmation for the resolved target."""

    target, client = remote_client()
    entity, resolution = resolve_entity(client, reference)
    require_confirmation(
        prompt=f"Archive entity '{entity.get('name')}' ({entity.get('id')}){' and descendants' if cascade else ''}?",
        yes=yes,
    )
    _, meta = client.request("DELETE", f"/entities/{entity['id']}", params={"cascade": cascade})
    emit_remote_result(
        "entities.delete",
        {"id": entity["id"], "name": entity.get("name"), "archived": True, "cascade": cascade},
        target=target,
        meta=meta | {"resolution": resolution.get("resolution")},
        text=f"Archived entity {entity.get('name')} ({entity['id']}).",
        changed=True,
    )


def _entity_relation(reference: str, relation: str, entity_type: Optional[str] = None) -> None:
    target, client = remote_client()
    entity, resolution = resolve_entity(client, reference)
    result, meta = client.request(
        "GET",
        f"/entities/{entity['id']}/{relation}",
        params={"entity_type": entity_type},
    )
    items = [item for item in result if isinstance(item, dict)] if isinstance(result, list) else []
    emit_remote_result(
        f"entities.{relation}",
        result,
        target=target,
        meta=meta | {"resolution": resolution.get("resolution")},
        text=records_text(items, (("NAME", "name"), ("TYPE", "entity_type"), ("STATUS", "status"), ("ID", "id"))),
    )


@entities_group.command("children")
@click.argument("reference")
def entities_children(reference: str):
    """List direct children of an entity."""

    _entity_relation(reference, "children")


@entities_group.command("descendants")
@click.argument("reference")
@click.option("--type", "entity_type", default=None)
def entities_descendants(reference: str, entity_type: Optional[str]):
    """List all descendants of an entity."""

    _entity_relation(reference, "descendants", entity_type)


@entities_group.command("path")
@click.argument("reference")
def entities_path(reference: str):
    """Show the root-to-entity hierarchy path."""

    _entity_relation(reference, "path")
