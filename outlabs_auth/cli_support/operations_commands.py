"""Remote audit, configuration, and session lifecycle commands."""

from __future__ import annotations

from typing import Any, Optional

import click

from outlabs_auth.cli_support.entity_commands import resolve_entity
from outlabs_auth.cli_support.payloads import load_json_object, require_nonempty_payload
from outlabs_auth.cli_support.resource_common import emit_remote_result, records_text, remote_client
from outlabs_auth.cli_support.runtime import require_confirmation


@click.group("audit")
def audit_group():
    """Search the cross-user, scope-filtered audit trail."""


@audit_group.command("list")
@click.option("--page", type=click.IntRange(min=1), default=1, show_default=True)
@click.option("--limit", type=click.IntRange(min=1, max=100), default=50, show_default=True)
@click.option("--category", default=None)
@click.option("--event-type", default=None)
@click.option("--subject", "subject_reference", default=None, help="Subject user UUID/email.")
@click.option("--actor", "actor_reference", default=None, help="Actor user UUID/email.")
@click.option("--entity", "entity_reference", default=None)
@click.option("--from", "occurred_from", default=None, help="Inclusive ISO-8601 timestamp.")
@click.option("--to", "occurred_to", default=None, help="Inclusive ISO-8601 timestamp.")
@click.option("--all", "all_pages", is_flag=True)
def audit_list(
    page: int,
    limit: int,
    category: Optional[str],
    event_type: Optional[str],
    subject_reference: Optional[str],
    actor_reference: Optional[str],
    entity_reference: Optional[str],
    occurred_from: Optional[str],
    occurred_to: Optional[str],
    all_pages: bool,
):
    """Search audit events using human user/entity references."""

    target, client = remote_client()
    subject_id = None
    actor_id = None
    entity_id = None
    resolutions: dict[str, Any] = {}
    if subject_reference:
        subject, resolution = client.resolve_user(subject_reference)
        subject_id = subject["id"]
        resolutions["subject_resolution"] = resolution.get("resolution")
    if actor_reference:
        actor, resolution = client.resolve_user(actor_reference)
        actor_id = actor["id"]
        resolutions["actor_resolution"] = resolution.get("resolution")
    if entity_reference:
        entity, resolution = resolve_entity(client, entity_reference)
        entity_id = entity["id"]
        resolutions["entity_resolution"] = resolution.get("resolution")
    result, meta = client.paginate(
        "/audit-events",
        page=page,
        limit=limit,
        max_limit=100,
        all_pages=all_pages,
        params={
            "category": category,
            "event_type": event_type,
            "subject_user_id": subject_id,
            "actor_user_id": actor_id,
            "entity_id": entity_id,
            "occurred_from": occurred_from,
            "occurred_to": occurred_to,
        },
    )
    items = [item for item in result["items"] if isinstance(item, dict)]
    emit_remote_result(
        "audit.list",
        result,
        target=target,
        meta=meta | resolutions,
        text=records_text(
            items,
            (
                ("TIME", "occurred_at"),
                ("EVENT", "event_type"),
                ("ACTOR", "actor_user_id"),
                ("SUBJECT", "subject_email_snapshot"),
                ("REQUEST", "request_id"),
            ),
        ),
    )


@click.group("config")
def config_group():
    """Inspect and administer mounted OutlabsAuth system configuration."""


@config_group.command("entity-types")
def config_entity_types():
    """Get public root and child entity-type policy."""

    target, client = remote_client()
    result, meta = client.request("GET", "/config/entity-types", require_auth=False)
    emit_remote_result("config.entity-types", result, target=target, meta=meta)


@config_group.command("set-entity-types")
@click.option("--from", "json_source", type=click.Path(exists=True, dir_okay=False), required=True)
@click.option("--yes", is_flag=True)
def config_set_entity_types(json_source: str, yes: bool):
    """Replace entity-type policy from a reviewed JSON request object."""

    payload = load_json_object(json_source, required=True)
    assert payload is not None
    require_nonempty_payload(payload)
    require_confirmation(prompt="Update global entity-type configuration?", yes=yes)
    target, client = remote_client()
    result, meta = client.request("PUT", "/config/entity-types", json_body=payload)
    emit_remote_result(
        "config.set-entity-types",
        result,
        target=target,
        meta=meta,
        changed=True,
    )


@click.group("sessions")
def sessions_group():
    """List and revoke refresh-token sessions without exposing tokens."""


@sessions_group.command("list")
@click.option("--user", "user_reference", default=None, help="Admin lookup; omit for current user.")
def sessions_list(user_reference: Optional[str]):
    """List current or resolved-user active sessions."""

    target, client = remote_client()
    resolution = None
    if user_reference:
        user, resolution = client.resolve_user(user_reference)
        path = f"/users/{user['id']}/sessions"
        user_id = user["id"]
    else:
        path = "/users/me/sessions"
        user_id = None
    result, meta = client.request("GET", path)
    items = [item for item in result if isinstance(item, dict)] if isinstance(result, list) else []
    emit_remote_result(
        "sessions.list",
        {"user_id": user_id, "sessions": result},
        target=target,
        meta=meta | ({"resolution": resolution.get("resolution")} if resolution else {}),
        text=records_text(
            items,
            (
                ("DEVICE", "device_name"),
                ("IP", "ip_address"),
                ("LAST USED", "last_used_at"),
                ("EXPIRES", "expires_at"),
                ("ID", "id"),
            ),
        ),
    )


@sessions_group.command("revoke")
@click.argument("session_id")
@click.option("--user", "user_reference", default=None, help="Admin lookup; omit for current user.")
@click.option("--yes", is_flag=True)
def sessions_revoke(session_id: str, user_reference: Optional[str], yes: bool):
    """Revoke one exact session ID."""

    target, client = remote_client()
    resolution = None
    if user_reference:
        user, resolution = client.resolve_user(user_reference)
        path = f"/users/{user['id']}/sessions/{session_id}"
        subject = user.get("email") or user["id"]
    else:
        path = f"/users/me/sessions/{session_id}"
        subject = "the current user"
    require_confirmation(prompt=f"Revoke session {session_id} for {subject}?", yes=yes)
    _, meta = client.request("DELETE", path)
    emit_remote_result(
        "sessions.revoke",
        {"session_id": session_id, "revoked": True},
        target=target,
        meta=meta | ({"resolution": resolution.get("resolution")} if resolution else {}),
        text=f"Revoked session {session_id}.",
        changed=True,
    )


@sessions_group.command("revoke-all")
@click.option("--user", "user_reference", default=None, help="Admin lookup; omit for current user.")
@click.option("--yes", is_flag=True)
def sessions_revoke_all(user_reference: Optional[str], yes: bool):
    """Revoke every active session for one resolved user."""

    target, client = remote_client()
    resolution = None
    if user_reference:
        user, resolution = client.resolve_user(user_reference)
        path = f"/users/{user['id']}/sessions"
        subject = user.get("email") or user["id"]
    else:
        path = "/users/me/sessions"
        subject = "the current user"
    require_confirmation(prompt=f"Revoke every active session for {subject}?", yes=yes)
    _, meta = client.request("DELETE", path)
    local_removed = client.credential_store().delete(target.name) if not user_reference else False
    emit_remote_result(
        "sessions.revoke-all",
        {"user": subject, "revoked_all": True, "local_session_removed": local_removed},
        target=target,
        meta=meta | ({"resolution": resolution.get("resolution")} if resolution else {}),
        text=f"Revoked every active session for {subject}.",
        changed=True,
    )


def register_operations_commands(root: click.Group) -> None:
    root.add_command(audit_group)
    root.add_command(config_group)
    root.add_command(sessions_group)
