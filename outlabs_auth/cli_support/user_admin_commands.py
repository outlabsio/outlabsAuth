"""Mutation and access-management commands attached to the users group."""

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
from outlabs_auth.cli_support.secrets import read_secret


def _user_text(user: dict[str, Any]) -> str:
    name = " ".join(part for part in (user.get("first_name"), user.get("last_name")) if part)
    display = dict(user) | {"full_name": name or None}
    return detail_text(
        display,
        (
            ("Email", "email"),
            ("Name", "full_name"),
            ("ID", "id"),
            ("Status", "status"),
            ("Superuser", "is_superuser"),
            ("Verified", "email_verified"),
            ("Phone", "phone"),
            ("Root entity", "root_entity_name"),
            ("Last login", "last_login"),
        ),
    )


def _resolve_role(client: RemoteClient, reference: str) -> tuple[dict[str, Any], dict[str, Any]]:
    return client.resolve_resource(
        reference,
        resource_name="role",
        detail_path="/roles/{id}",
        list_path="/roles/",
        exact_fields=("name", "display_name"),
        max_limit=100,
    )


@click.command("create")
@click.option("--email", required=True)
@click.option("--password-stdin", is_flag=True)
@click.option("--password-env", default="OUTLABS_AUTH_NEW_USER_PASSWORD", show_default=True)
@click.option("--first-name", default=None)
@click.option("--last-name", default=None)
@click.option("--superuser/--not-superuser", "is_superuser", default=False, show_default=True)
@click.option("--root-entity", "root_entity_reference", default=None)
@click.option("--yes", is_flag=True, help="Confirm creation of a superuser without prompting.")
def users_create(
    email: str,
    password_stdin: bool,
    password_env: str,
    first_name: Optional[str],
    last_name: Optional[str],
    is_superuser: bool,
    root_entity_reference: Optional[str],
    yes: bool,
):
    """Create a user using a password from stdin, environment, or hidden prompt."""

    password = read_secret(
        from_stdin=password_stdin,
        env_name=password_env,
        prompt="New user password",
        missing_code="NEW_USER_PASSWORD_MISSING",
        confirmation_prompt=True,
    )
    target, client = remote_client()
    root_entity_id = None
    root_resolution = None
    if root_entity_reference:
        entity, root_resolution = resolve_entity(client, root_entity_reference)
        root_entity_id = entity["id"]
    if is_superuser:
        require_confirmation(
            prompt=f"Create {email} with platform-wide superuser authority?",
            yes=yes,
        )
    result, meta = client.request(
        "POST",
        "/users/",
        json_body={
            "email": email,
            "password": password,
            "first_name": first_name,
            "last_name": last_name,
            "is_superuser": is_superuser,
            "root_entity_id": root_entity_id,
        },
    )
    emit_remote_result(
        "users.create",
        result,
        target=target,
        meta=meta | ({"root_entity_resolution": root_resolution.get("resolution")} if root_resolution else {}),
        text=_user_text(result),
        changed=True,
    )


@click.command("update")
@click.argument("reference")
@click.option("--from", "json_source", type=click.Path(dir_okay=False))
@click.option("--email", default=None)
@click.option("--first-name", default=None)
@click.option("--last-name", default=None)
@click.option("--phone", default=None, help="E.164 phone number.")
@click.option("--clear-phone", is_flag=True)
def users_update(
    reference: str,
    json_source: Optional[str],
    email: Optional[str],
    first_name: Optional[str],
    last_name: Optional[str],
    phone: Optional[str],
    clear_phone: bool,
):
    """Update a user's profile after exact reference resolution."""

    if phone and clear_phone:
        raise click.UsageError("Use --phone or --clear-phone, not both.")
    payload = request_payload(
        json_source,
        email=email,
        first_name=first_name,
        last_name=last_name,
        phone="" if clear_phone else phone,
    )
    require_nonempty_payload(payload)
    target, client = remote_client()
    user, resolution = client.resolve_user(reference)
    result, meta = client.request("PATCH", f"/users/{user['id']}", json_body=payload)
    emit_remote_result(
        "users.update",
        result,
        target=target,
        meta=meta | {"resolution": resolution.get("resolution")},
        text=_user_text(result),
        changed=True,
    )


@click.command("set-status")
@click.argument("reference")
@click.argument("status", type=click.Choice(["active", "suspended", "banned"]))
@click.option("--until", "suspended_until", default=None, help="ISO-8601 timestamp for suspension expiry.")
@click.option("--reason", default=None)
@click.option("--yes", is_flag=True)
def users_set_status(
    reference: str,
    status: str,
    suspended_until: Optional[str],
    reason: Optional[str],
    yes: bool,
):
    """Activate, suspend, or ban a resolved user with an audit reason."""

    if suspended_until and status != "suspended":
        raise CliError(
            code="INVALID_SUSPENSION_EXPIRY",
            message="--until is valid only when status is suspended.",
            exit_code=EXIT_USAGE,
        )
    target, client = remote_client()
    user, resolution = client.resolve_user(reference)
    require_confirmation(
        prompt=f"Set user {user.get('email')} ({user.get('id')}) status to {status}?",
        yes=yes,
    )
    result, meta = client.request(
        "PATCH",
        f"/users/{user['id']}/status",
        json_body={"status": status, "suspended_until": suspended_until, "reason": reason},
    )
    emit_remote_result(
        "users.set-status",
        result,
        target=target,
        meta=meta | {"resolution": resolution.get("resolution")},
        text=_user_text(result),
        changed=True,
    )


@click.command("set-superuser")
@click.argument("reference")
@click.option("--grant/--revoke", "is_superuser", required=True)
@click.option("--reason", default=None)
@click.option("--yes", is_flag=True)
def users_set_superuser(reference: str, is_superuser: bool, reason: Optional[str], yes: bool):
    """Grant or revoke platform-wide superuser authority."""

    target, client = remote_client()
    user, resolution = client.resolve_user(reference)
    action = "grant" if is_superuser else "revoke"
    require_confirmation(
        prompt=f"{action.title()} superuser authority for {user.get('email')} ({user.get('id')})?",
        yes=yes,
    )
    result, meta = client.request(
        "PATCH",
        f"/users/{user['id']}/superuser",
        json_body={"is_superuser": is_superuser, "reason": reason},
    )
    emit_remote_result(
        "users.set-superuser",
        result,
        target=target,
        meta=meta | {"resolution": resolution.get("resolution")},
        text=_user_text(result),
        changed=True,
    )


@click.command("reset-password")
@click.argument("reference")
@click.option("--password-stdin", is_flag=True)
@click.option("--password-env", default="OUTLABS_AUTH_RESET_PASSWORD", show_default=True)
@click.option("--yes", is_flag=True)
def users_reset_password(reference: str, password_stdin: bool, password_env: str, yes: bool):
    """Reset a resolved user's password without placing it in argv."""

    target, client = remote_client()
    user, resolution = client.resolve_user(reference)
    require_confirmation(prompt=f"Reset the password for {user.get('email')} ({user.get('id')})?", yes=yes)
    password = read_secret(
        from_stdin=password_stdin,
        env_name=password_env,
        prompt="Replacement password",
        missing_code="RESET_PASSWORD_MISSING",
        confirmation_prompt=True,
    )
    _, meta = client.request(
        "PATCH",
        f"/users/{user['id']}/password",
        json_body={"new_password": password},
    )
    emit_remote_result(
        "users.reset-password",
        {"id": user["id"], "email": user.get("email"), "password_reset": True},
        target=target,
        meta=meta | {"resolution": resolution.get("resolution")},
        text=f"Reset the password for {user.get('email')} ({user['id']}).",
        changed=True,
    )


@click.command("delete")
@click.argument("reference")
@click.option("--yes", is_flag=True)
def users_delete(reference: str, yes: bool):
    """Retained-delete a resolved user and revoke access."""

    target, client = remote_client()
    user, resolution = client.resolve_user(reference)
    require_confirmation(prompt=f"Delete user {user.get('email')} ({user.get('id')})?", yes=yes)
    _, meta = client.request("DELETE", f"/users/{user['id']}")
    emit_remote_result(
        "users.delete",
        {"id": user["id"], "email": user.get("email"), "deleted": True},
        target=target,
        meta=meta | {"resolution": resolution.get("resolution")},
        text=f"Deleted user {user.get('email')} ({user['id']}).",
        changed=True,
    )


@click.command("restore")
@click.argument("reference")
@click.option("--yes", is_flag=True)
def users_restore(reference: str, yes: bool):
    """Restore a deleted identity without restoring its former grants."""

    target, client = remote_client()
    user, resolution = client.resolve_user(reference)
    require_confirmation(
        prompt=f"Restore identity {user.get('email')} ({user.get('id')}) without access grants?",
        yes=yes,
    )
    result, meta = client.request("POST", f"/users/{user['id']}/restore")
    emit_remote_result(
        "users.restore",
        result,
        target=target,
        meta=meta | {"resolution": resolution.get("resolution")},
        text=_user_text(result),
        changed=True,
    )


@click.command("roles")
@click.argument("reference")
@click.option("--include-inactive", is_flag=True)
def users_roles(reference: str, include_inactive: bool):
    """List roles currently assigned to a user."""

    target, client = remote_client()
    user, resolution = client.resolve_user(reference)
    result, meta = client.request(
        "GET",
        f"/users/{user['id']}/roles",
        params={"include_inactive": include_inactive},
    )
    items = [item for item in result if isinstance(item, dict)] if isinstance(result, list) else []
    emit_remote_result(
        "users.roles",
        {"user_id": user["id"], "roles": result},
        target=target,
        meta=meta | {"resolution": resolution.get("resolution")},
        text=records_text(items, (("NAME", "name"), ("STATUS", "status"), ("SCOPE", "scope"), ("ID", "id"))),
    )


@click.command("assign-role")
@click.argument("user_reference")
@click.argument("role_reference")
@click.option("--valid-from", default=None)
@click.option("--valid-until", default=None)
@click.option("--yes", is_flag=True)
def users_assign_role(
    user_reference: str,
    role_reference: str,
    valid_from: Optional[str],
    valid_until: Optional[str],
    yes: bool,
):
    """Assign a resolved role directly to a resolved user."""

    target, client = remote_client()
    user, user_resolution = client.resolve_user(user_reference)
    role, role_resolution = _resolve_role(client, role_reference)
    require_confirmation(prompt=f"Assign role {role.get('name')} to {user.get('email')}?", yes=yes)
    result, meta = client.request(
        "POST",
        f"/users/{user['id']}/roles",
        json_body={"role_id": role["id"], "valid_from": valid_from, "valid_until": valid_until},
    )
    emit_remote_result(
        "users.assign-role",
        result,
        target=target,
        meta=meta
        | {
            "user_resolution": user_resolution.get("resolution"),
            "role_resolution": role_resolution.get("resolution"),
        },
        text=f"Assigned role {role.get('name')} to {user.get('email')}.",
        changed=True,
    )


@click.command("revoke-role")
@click.argument("user_reference")
@click.argument("role_reference")
@click.option("--yes", is_flag=True)
def users_revoke_role(user_reference: str, role_reference: str, yes: bool):
    """Revoke a direct role assignment after resolving both resources."""

    target, client = remote_client()
    user, user_resolution = client.resolve_user(user_reference)
    role, role_resolution = _resolve_role(client, role_reference)
    require_confirmation(prompt=f"Revoke role {role.get('name')} from {user.get('email')}?", yes=yes)
    _, meta = client.request("DELETE", f"/users/{user['id']}/roles/{role['id']}")
    emit_remote_result(
        "users.revoke-role",
        {"user_id": user["id"], "role_id": role["id"], "revoked": True},
        target=target,
        meta=meta
        | {
            "user_resolution": user_resolution.get("resolution"),
            "role_resolution": role_resolution.get("resolution"),
        },
        text=f"Revoked role {role.get('name')} from {user.get('email')}.",
        changed=True,
    )


def register_user_admin_commands(group: click.Group) -> None:
    for command in (
        users_create,
        users_update,
        users_set_status,
        users_set_superuser,
        users_reset_password,
        users_delete,
        users_restore,
        users_roles,
        users_assign_role,
        users_revoke_role,
    ):
        group.add_command(command)
