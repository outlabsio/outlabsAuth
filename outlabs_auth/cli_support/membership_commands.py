"""Enterprise entity-membership lifecycle commands."""

from __future__ import annotations

from typing import Any, Optional

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
from outlabs_auth.cli_support.runtime import CliError, EXIT_USAGE, require_confirmation


def _resolve_role_id(client: RemoteClient, reference: str) -> tuple[str, dict[str, Any]]:
    role, meta = client.resolve_resource(
        reference,
        resource_name="role",
        detail_path="/roles/{id}",
        list_path="/roles/",
        exact_fields=("name", "display_name"),
        max_limit=100,
    )
    return str(role["id"]), meta


def _membership_text(membership: dict[str, Any]) -> str:
    return detail_text(
        membership,
        (
            ("ID", "id"),
            ("User", "user_id"),
            ("Entity", "entity_id"),
            ("Status", "status"),
            ("Effective", "effective_status"),
            ("Roles", "role_ids"),
            ("Valid from", "valid_from"),
            ("Valid until", "valid_until"),
            ("Joined", "joined_at"),
        ),
    )


@click.group("memberships")
def memberships_group():
    """Inspect and administer entity memberships and their role sets."""


@memberships_group.command("list")
@click.option("--entity", "entity_reference", default=None)
@click.option("--user", "user_reference", default=None)
@click.option("--me", "current_user", is_flag=True, help="List the authenticated user's memberships.")
@click.option("--page", type=click.IntRange(min=1), default=1, show_default=True)
@click.option("--limit", type=click.IntRange(min=1, max=100), default=50, show_default=True)
@click.option("--include-inactive", is_flag=True)
@click.option("--details", is_flag=True, help="Include user and role details for an entity listing.")
def memberships_list(
    entity_reference: Optional[str],
    user_reference: Optional[str],
    current_user: bool,
    page: int,
    limit: int,
    include_inactive: bool,
    details: bool,
):
    """List memberships for exactly one entity, user, or the current user."""

    selected = sum(bool(value) for value in (entity_reference, user_reference, current_user))
    if selected == 0:
        current_user = True
    elif selected > 1:
        raise CliError(
            code="MEMBERSHIP_SCOPE_AMBIGUOUS",
            message="Choose only one of --entity, --user, or --me.",
            exit_code=EXIT_USAGE,
        )
    if details and not entity_reference:
        raise CliError(
            code="DETAILS_REQUIRE_ENTITY",
            message="--details is available only with --entity.",
            exit_code=EXIT_USAGE,
        )

    target, client = remote_client()
    resolution = None
    if entity_reference:
        entity, resolution = resolve_entity(client, entity_reference)
        suffix = "/details" if details else ""
        path = f"/memberships/entity/{entity['id']}{suffix}"
        params = {"page": page, "limit": limit, "include_inactive": include_inactive}
    elif user_reference:
        user, resolution = client.resolve_user(user_reference)
        path = f"/memberships/user/{user['id']}"
        params = {"page": page, "limit": limit, "include_inactive": include_inactive}
    else:
        path = "/memberships/me"
        params = {"include_inactive": include_inactive}

    result, meta = client.request("GET", path, params=params)
    items = [item for item in result if isinstance(item, dict)] if isinstance(result, list) else []
    columns = (
        (("EMAIL", "user_email"), ("STATUS", "status"), ("ROLES", "roles"), ("USER ID", "user_id"))
        if details
        else (("USER", "user_id"), ("ENTITY", "entity_id"), ("STATUS", "status"), ("ROLES", "role_ids"))
    )
    emit_remote_result(
        "memberships.list",
        {"items": result, "scope": "entity" if entity_reference else "user" if user_reference else "me"},
        target=target,
        meta=meta | ({"resolution": resolution.get("resolution")} if resolution else {}),
        text=records_text(items, columns),
    )


@memberships_group.command("add")
@click.option("--user", "user_reference", required=True)
@click.option("--entity", "entity_reference", required=True)
@click.option("--role", "role_references", multiple=True)
@click.option("--status", type=click.Choice(["active", "suspended"]), default=None)
@click.option("--valid-from", default=None, help="ISO-8601 timestamp.")
@click.option("--valid-until", default=None, help="ISO-8601 timestamp.")
@click.option("--reason", default=None)
@click.option("--from", "json_source", type=click.Path(dir_okay=False))
@click.option("--yes", is_flag=True, help="Confirm the access grant without prompting.")
def memberships_add(
    user_reference: str,
    entity_reference: str,
    role_references: tuple[str, ...],
    status: Optional[str],
    valid_from: Optional[str],
    valid_until: Optional[str],
    reason: Optional[str],
    json_source: Optional[str],
    yes: bool,
):
    """Add a resolved user to a resolved entity with optional resolved roles."""

    target, client = remote_client()
    user, user_resolution = client.resolve_user(user_reference)
    entity, entity_resolution = resolve_entity(client, entity_reference)
    role_ids: list[str] = []
    role_resolutions = []
    for reference in role_references:
        role_id, resolution = _resolve_role_id(client, reference)
        role_ids.append(role_id)
        role_resolutions.append(resolution.get("resolution"))
    payload = request_payload(
        json_source,
        user_id=user["id"],
        entity_id=entity["id"],
        role_ids=role_ids if role_references else None,
        status=status,
        valid_from=valid_from,
        valid_until=valid_until,
        reason=reason,
    )
    require_confirmation(
        prompt=f"Add {user.get('email')} to entity '{entity.get('name')}' with {len(role_ids)} explicit roles?",
        yes=yes,
    )
    result, meta = client.request("POST", "/memberships/", json_body=payload)
    emit_remote_result(
        "memberships.add",
        result,
        target=target,
        meta=meta
        | {
            "user_resolution": user_resolution.get("resolution"),
            "entity_resolution": entity_resolution.get("resolution"),
            "role_resolutions": role_resolutions,
        },
        text=_membership_text(result),
        changed=True,
    )


@memberships_group.command("update")
@click.option("--user", "user_reference", required=True)
@click.option("--entity", "entity_reference", required=True)
@click.option("--role", "role_references", multiple=True, help="Replace the complete role set.")
@click.option("--clear-roles", is_flag=True)
@click.option("--status", type=click.Choice(["active", "suspended"]), default=None)
@click.option("--valid-from", default=None)
@click.option("--valid-until", default=None)
@click.option("--reason", default=None)
@click.option("--from", "json_source", type=click.Path(dir_okay=False))
@click.option("--yes", is_flag=True, help="Confirm the access change without prompting.")
def memberships_update(
    user_reference: str,
    entity_reference: str,
    role_references: tuple[str, ...],
    clear_roles: bool,
    status: Optional[str],
    valid_from: Optional[str],
    valid_until: Optional[str],
    reason: Optional[str],
    json_source: Optional[str],
    yes: bool,
):
    """Replace roles or update membership lifecycle fields."""

    if role_references and clear_roles:
        raise click.UsageError("Use --role or --clear-roles, not both.")
    target, client = remote_client()
    user, user_resolution = client.resolve_user(user_reference)
    entity, entity_resolution = resolve_entity(client, entity_reference)
    role_ids: Optional[list[str]] = None
    role_resolutions = []
    if role_references:
        role_ids = []
        for reference in role_references:
            role_id, resolution = _resolve_role_id(client, reference)
            role_ids.append(role_id)
            role_resolutions.append(resolution.get("resolution"))
    elif clear_roles:
        role_ids = []
    payload = request_payload(
        json_source,
        role_ids=role_ids,
        status=status,
        valid_from=valid_from,
        valid_until=valid_until,
        reason=reason,
    )
    require_nonempty_payload(payload)
    require_confirmation(
        prompt=f"Update membership for {user.get('email')} in entity '{entity.get('name')}'?",
        yes=yes,
    )
    result, meta = client.request(
        "PATCH",
        f"/memberships/{entity['id']}/{user['id']}",
        json_body=payload,
    )
    emit_remote_result(
        "memberships.update",
        result,
        target=target,
        meta=meta
        | {
            "user_resolution": user_resolution.get("resolution"),
            "entity_resolution": entity_resolution.get("resolution"),
            "role_resolutions": role_resolutions,
        },
        text=_membership_text(result),
        changed=True,
    )


@memberships_group.command("remove")
@click.option("--user", "user_reference", required=True)
@click.option("--entity", "entity_reference", required=True)
@click.option("--yes", is_flag=True)
def memberships_remove(user_reference: str, entity_reference: str, yes: bool):
    """Revoke a user's entity membership after exact resolution."""

    target, client = remote_client()
    user, user_resolution = client.resolve_user(user_reference)
    entity, entity_resolution = resolve_entity(client, entity_reference)
    require_confirmation(
        prompt=(f"Remove {user.get('email') or user['id']} from " f"entity '{entity.get('name')}' ({entity['id']})?"),
        yes=yes,
    )
    _, meta = client.request("DELETE", f"/memberships/{entity['id']}/{user['id']}")
    emit_remote_result(
        "memberships.remove",
        {"user_id": user["id"], "entity_id": entity["id"], "revoked": True},
        target=target,
        meta=meta
        | {
            "user_resolution": user_resolution.get("resolution"),
            "entity_resolution": entity_resolution.get("resolution"),
        },
        text=f"Removed {user.get('email') or user['id']} from {entity.get('name') or entity['id']}.",
        changed=True,
    )
