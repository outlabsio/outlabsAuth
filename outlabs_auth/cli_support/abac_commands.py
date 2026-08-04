"""Typed ABAC condition-group and condition administration commands."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Optional

import click

from outlabs_auth.cli_support.client import RemoteClient
from outlabs_auth.cli_support.payloads import require_nonempty_payload, require_payload_fields
from outlabs_auth.cli_support.permission_commands import resolve_permission
from outlabs_auth.cli_support.resource_common import emit_remote_result, records_text, remote_client, request_payload
from outlabs_auth.cli_support.role_commands import resolve_role
from outlabs_auth.cli_support.runtime import CliError, EXIT_OPERATION_FAILED, EXIT_USAGE, require_confirmation

Resolver = Callable[[RemoteClient, str], tuple[dict[str, Any], dict[str, Any]]]


@dataclass(frozen=True)
class AbacOwner:
    """Resource-specific routing and resolution for one ABAC owner type."""

    singular: str
    plural: str
    base_path: str
    resolver: Resolver


ROLE_OWNER = AbacOwner("role", "roles", "/roles", resolve_role)
PERMISSION_OWNER = AbacOwner("permission", "permissions", "/permissions", resolve_permission)


def _owner_path(owner: AbacOwner, owner_id: str, resource: str) -> str:
    return f"{owner.base_path}/{owner_id}/{resource}"


def _ensure_list(result: Any, endpoint: str) -> list[dict[str, Any]]:
    if not isinstance(result, list) or not all(isinstance(item, dict) for item in result):
        raise CliError(
            code="REMOTE_PROTOCOL_ERROR",
            message=f"The {endpoint} endpoint returned an invalid response.",
            exit_code=EXIT_OPERATION_FAILED,
        )
    return result


def _parse_value(value: Optional[str], value_json: Optional[str]) -> Any:
    if value is not None and value_json is not None:
        raise CliError(
            code="CONFLICTING_ABAC_VALUE",
            message="Use --value or --value-json, not both.",
            exit_code=EXIT_USAGE,
        )
    if value_json is None:
        return value
    try:
        return json.loads(value_json)
    except json.JSONDecodeError as exc:
        raise CliError(
            code="INVALID_ABAC_VALUE_JSON",
            message="--value-json must be one valid JSON value.",
            exit_code=EXIT_USAGE,
            details={"exception_type": type(exc).__name__},
        ) from exc


def _resolution_meta(resolution: dict[str, Any], owner: AbacOwner) -> dict[str, Any]:
    return {f"{owner.singular}_resolution": resolution.get("resolution")}


def _build_condition_groups(owner: AbacOwner) -> click.Group:
    @click.group("condition-groups")
    def condition_groups():
        """Manage AND/OR groups that organize ABAC conditions."""

    @condition_groups.command("list")
    @click.argument("owner_reference")
    def list_groups(owner_reference: str):
        """List condition groups for a resolved role or permission."""

        target, client = remote_client()
        resource, resolution = owner.resolver(client, owner_reference)
        result, meta = client.request("GET", _owner_path(owner, str(resource["id"]), "condition-groups"))
        items = _ensure_list(result, f"{owner.singular} condition-groups")
        emit_remote_result(
            f"{owner.plural}.condition-groups.list",
            {owner.singular: resource, "items": items},
            target=target,
            meta=meta | _resolution_meta(resolution, owner),
            text=records_text(
                items,
                (("ID", "id"), ("OPERATOR", "operator"), ("DESCRIPTION", "description")),
            ),
        )

    @condition_groups.command("create")
    @click.argument("owner_reference")
    @click.option("--from", "json_source", type=click.Path(dir_okay=False))
    @click.option("--operator", type=click.Choice(["AND", "OR"]), default=None)
    @click.option("--description", default=None)
    @click.option("--yes", is_flag=True)
    def create_group(
        owner_reference: str,
        json_source: Optional[str],
        operator: Optional[str],
        description: Optional[str],
        yes: bool,
    ):
        """Create an AND/OR group after resolving its authority owner."""

        target, client = remote_client()
        resource, resolution = owner.resolver(client, owner_reference)
        payload = request_payload(json_source, operator=operator, description=description)
        require_confirmation(
            prompt=f"Create an ABAC condition group on {owner.singular} '{resource.get('name')}'?",
            yes=yes,
        )
        result, meta = client.request(
            "POST",
            _owner_path(owner, str(resource["id"]), "condition-groups"),
            json_body=payload,
        )
        emit_remote_result(
            f"{owner.plural}.condition-groups.create",
            result,
            target=target,
            meta=meta | _resolution_meta(resolution, owner),
            changed=True,
        )

    @condition_groups.command("update")
    @click.argument("owner_reference")
    @click.argument("group_id")
    @click.option("--from", "json_source", type=click.Path(dir_okay=False))
    @click.option("--operator", type=click.Choice(["AND", "OR"]), default=None)
    @click.option("--description", default=None)
    @click.option("--clear-description", is_flag=True)
    @click.option("--yes", is_flag=True)
    def update_group(
        owner_reference: str,
        group_id: str,
        json_source: Optional[str],
        operator: Optional[str],
        description: Optional[str],
        clear_description: bool,
        yes: bool,
    ):
        """Update a condition group by UUID after owner resolution."""

        if description is not None and clear_description:
            raise click.UsageError("Use --description or --clear-description, not both.")
        target, client = remote_client()
        resource, resolution = owner.resolver(client, owner_reference)
        payload = request_payload(json_source, operator=operator, description=description)
        if clear_description:
            payload["description"] = None
        require_nonempty_payload(payload)
        require_confirmation(
            prompt=f"Update ABAC condition group {group_id} on {owner.singular} '{resource.get('name')}'?",
            yes=yes,
        )
        result, meta = client.request(
            "PATCH",
            f"{_owner_path(owner, str(resource['id']), 'condition-groups')}/{group_id}",
            json_body=payload,
        )
        emit_remote_result(
            f"{owner.plural}.condition-groups.update",
            result,
            target=target,
            meta=meta | _resolution_meta(resolution, owner),
            changed=True,
        )

    @condition_groups.command("delete")
    @click.argument("owner_reference")
    @click.argument("group_id")
    @click.option("--yes", is_flag=True)
    def delete_group(owner_reference: str, group_id: str, yes: bool):
        """Delete a condition group by UUID after explicit confirmation."""

        target, client = remote_client()
        resource, resolution = owner.resolver(client, owner_reference)
        require_confirmation(
            prompt=f"Delete ABAC condition group {group_id} from {owner.singular} '{resource.get('name')}'?",
            yes=yes,
        )
        _, meta = client.request(
            "DELETE",
            f"{_owner_path(owner, str(resource['id']), 'condition-groups')}/{group_id}",
        )
        emit_remote_result(
            f"{owner.plural}.condition-groups.delete",
            {"id": group_id, "deleted": True, f"{owner.singular}_id": resource["id"]},
            target=target,
            meta=meta | _resolution_meta(resolution, owner),
            changed=True,
        )

    return condition_groups


def _build_conditions(owner: AbacOwner) -> click.Group:
    @click.group("conditions")
    def conditions():
        """Manage typed attribute-based access-control conditions."""

    @conditions.command("list")
    @click.argument("owner_reference")
    def list_conditions(owner_reference: str):
        """List conditions for a resolved role or permission."""

        target, client = remote_client()
        resource, resolution = owner.resolver(client, owner_reference)
        result, meta = client.request("GET", _owner_path(owner, str(resource["id"]), "conditions"))
        items = _ensure_list(result, f"{owner.singular} conditions")
        emit_remote_result(
            f"{owner.plural}.conditions.list",
            {owner.singular: resource, "items": items},
            target=target,
            meta=meta | _resolution_meta(resolution, owner),
            text=records_text(
                items,
                (
                    ("ATTRIBUTE", "attribute"),
                    ("OPERATOR", "operator"),
                    ("VALUE", "value"),
                    ("TYPE", "value_type"),
                    ("GROUP", "condition_group_id"),
                    ("ID", "id"),
                ),
            ),
        )

    @conditions.command("create")
    @click.argument("owner_reference")
    @click.option("--from", "json_source", type=click.Path(dir_okay=False))
    @click.option("--attribute", default=None)
    @click.option("--operator", default=None)
    @click.option("--value", default=None, help="String value.")
    @click.option("--value-json", default=None, help="Typed value as one JSON literal.")
    @click.option(
        "--value-type",
        type=click.Choice(["string", "integer", "float", "boolean", "list"]),
        default=None,
    )
    @click.option("--description", default=None)
    @click.option("--group", "condition_group_id", default=None, help="Condition-group UUID.")
    @click.option("--yes", is_flag=True)
    def create_condition(
        owner_reference: str,
        json_source: Optional[str],
        attribute: Optional[str],
        operator: Optional[str],
        value: Optional[str],
        value_json: Optional[str],
        value_type: Optional[str],
        description: Optional[str],
        condition_group_id: Optional[str],
        yes: bool,
    ):
        """Create a typed ABAC predicate from flags or a JSON object."""

        parsed_value = _parse_value(value, value_json)
        target, client = remote_client()
        resource, resolution = owner.resolver(client, owner_reference)
        payload = request_payload(
            json_source,
            attribute=attribute,
            operator=operator,
            value=parsed_value,
            value_type=value_type,
            description=description,
            condition_group_id=condition_group_id,
        )
        require_payload_fields(payload, "attribute", "operator")
        require_confirmation(
            prompt=f"Create an ABAC condition on {owner.singular} '{resource.get('name')}'?",
            yes=yes,
        )
        result, meta = client.request(
            "POST",
            _owner_path(owner, str(resource["id"]), "conditions"),
            json_body=payload,
        )
        emit_remote_result(
            f"{owner.plural}.conditions.create",
            result,
            target=target,
            meta=meta | _resolution_meta(resolution, owner),
            changed=True,
        )

    @conditions.command("update")
    @click.argument("owner_reference")
    @click.argument("condition_id")
    @click.option("--from", "json_source", type=click.Path(dir_okay=False))
    @click.option("--attribute", default=None)
    @click.option("--operator", default=None)
    @click.option("--value", default=None)
    @click.option("--value-json", default=None)
    @click.option("--clear-value", is_flag=True)
    @click.option(
        "--value-type",
        type=click.Choice(["string", "integer", "float", "boolean", "list"]),
        default=None,
    )
    @click.option("--description", default=None)
    @click.option("--clear-description", is_flag=True)
    @click.option("--group", "condition_group_id", default=None)
    @click.option("--clear-group", is_flag=True)
    @click.option("--yes", is_flag=True)
    def update_condition(
        owner_reference: str,
        condition_id: str,
        json_source: Optional[str],
        attribute: Optional[str],
        operator: Optional[str],
        value: Optional[str],
        value_json: Optional[str],
        clear_value: bool,
        value_type: Optional[str],
        description: Optional[str],
        clear_description: bool,
        condition_group_id: Optional[str],
        clear_group: bool,
        yes: bool,
    ):
        """Update or clear selected ABAC predicate fields by condition UUID."""

        if clear_value and (value is not None or value_json is not None):
            raise click.UsageError("Use a value option or --clear-value, not both.")
        if clear_description and description is not None:
            raise click.UsageError("Use --description or --clear-description, not both.")
        if clear_group and condition_group_id is not None:
            raise click.UsageError("Use --group or --clear-group, not both.")
        parsed_value = _parse_value(value, value_json)
        target, client = remote_client()
        resource, resolution = owner.resolver(client, owner_reference)
        payload = request_payload(
            json_source,
            attribute=attribute,
            operator=operator,
            value=parsed_value,
            value_type=value_type,
            description=description,
            condition_group_id=condition_group_id,
        )
        if clear_value:
            payload["value"] = None
        if clear_description:
            payload["description"] = None
        if clear_group:
            payload["condition_group_id"] = None
        require_nonempty_payload(payload)
        require_confirmation(
            prompt=f"Update ABAC condition {condition_id} on {owner.singular} '{resource.get('name')}'?",
            yes=yes,
        )
        result, meta = client.request(
            "PATCH",
            f"{_owner_path(owner, str(resource['id']), 'conditions')}/{condition_id}",
            json_body=payload,
        )
        emit_remote_result(
            f"{owner.plural}.conditions.update",
            result,
            target=target,
            meta=meta | _resolution_meta(resolution, owner),
            changed=True,
        )

    @conditions.command("delete")
    @click.argument("owner_reference")
    @click.argument("condition_id")
    @click.option("--yes", is_flag=True)
    def delete_condition(owner_reference: str, condition_id: str, yes: bool):
        """Delete an ABAC condition by UUID after explicit confirmation."""

        target, client = remote_client()
        resource, resolution = owner.resolver(client, owner_reference)
        require_confirmation(
            prompt=f"Delete ABAC condition {condition_id} from {owner.singular} '{resource.get('name')}'?",
            yes=yes,
        )
        _, meta = client.request(
            "DELETE",
            f"{_owner_path(owner, str(resource['id']), 'conditions')}/{condition_id}",
        )
        emit_remote_result(
            f"{owner.plural}.conditions.delete",
            {"id": condition_id, "deleted": True, f"{owner.singular}_id": resource["id"]},
            target=target,
            meta=meta | _resolution_meta(resolution, owner),
            changed=True,
        )

    return conditions


def register_abac_commands(roles_group: click.Group, permissions_group: click.Group) -> None:
    """Attach matching ABAC subtrees to both owner command groups."""

    roles_group.add_command(_build_condition_groups(ROLE_OWNER))
    roles_group.add_command(_build_conditions(ROLE_OWNER))
    permissions_group.add_command(_build_condition_groups(PERMISSION_OWNER))
    permissions_group.add_command(_build_conditions(PERMISSION_OWNER))
