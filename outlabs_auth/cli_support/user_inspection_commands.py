"""High-signal user access reports and lifecycle timelines for operators."""

from __future__ import annotations

from typing import Any, Optional

import click

from outlabs_auth.cli_support.entity_commands import resolve_entity
from outlabs_auth.cli_support.resource_common import emit_remote_result, records_text, remote_client
from outlabs_auth.cli_support.runtime import require_confirmation


def _list_payload(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


@click.command("access-report")
@click.argument("reference")
@click.option("--include-inactive", is_flag=True)
def users_access_report(reference: str, include_inactive: bool):
    """Show one user's memberships, roles, permission sources, keys, and sessions."""

    target, client = remote_client()
    user, resolution = client.resolve_user(reference)
    user_id = str(user["id"])
    entity_memberships, entity_meta = client.request(
        "GET",
        f"/memberships/user/{user_id}",
        params={"include_inactive": include_inactive},
    )
    role_memberships, role_meta = client.request(
        "GET",
        f"/users/{user_id}/role-memberships",
        params={"include_inactive": include_inactive},
    )
    permissions, permission_meta = client.request("GET", f"/users/{user_id}/permissions")
    api_keys, key_meta = client.request("GET", f"/users/{user_id}/api-keys")
    sessions, session_meta = client.request("GET", f"/users/{user_id}/sessions")
    result = {
        "user": user,
        "entity_memberships": entity_memberships,
        "direct_role_memberships": role_memberships,
        "effective_permissions": permissions,
        "personal_api_keys": api_keys,
        "active_sessions": sessions,
    }
    permission_names = []
    for item in _list_payload(permissions):
        permission = item.get("permission") if isinstance(item, dict) else None
        if isinstance(permission, dict) and permission.get("name"):
            permission_names.append(str(permission["name"]))
    text = "\n".join(
        [
            f"Access report: {user.get('email') or user_id}",
            f"Entity memberships:      {len(_list_payload(entity_memberships))}",
            f"Direct role assignments: {len(_list_payload(role_memberships))}",
            f"Effective permissions:   {len(_list_payload(permissions))}",
            f"Personal API keys:       {len(_list_payload(api_keys))}",
            f"Active sessions:         {len(_list_payload(sessions))}",
            f"Permissions: {', '.join(permission_names) if permission_names else '-'}",
        ]
    )
    emit_remote_result(
        "users.access-report",
        result,
        target=target,
        meta={
            "resolution": resolution.get("resolution"),
            "requests": {
                "entity_memberships": entity_meta,
                "direct_role_memberships": role_meta,
                "effective_permissions": permission_meta,
                "personal_api_keys": key_meta,
                "active_sessions": session_meta,
            },
        },
        text=text,
    )


@click.command("timeline")
@click.argument("reference")
@click.option(
    "--kind",
    "kinds",
    type=click.Choice(["audit", "membership"]),
    multiple=True,
    help="Repeat to select sources; omitted means both.",
)
@click.option("--category", default=None, help="Audit category filter.")
@click.option("--event-type", default=None)
@click.option("--entity", "entity_reference", default=None)
def users_timeline(
    reference: str,
    kinds: tuple[str, ...],
    category: Optional[str],
    event_type: Optional[str],
    entity_reference: Optional[str],
):
    """Fetch complete high-signal audit and membership history for one user."""

    selected = set(kinds or ("audit", "membership"))
    target, client = remote_client()
    user, resolution = client.resolve_user(reference)
    user_id = str(user["id"])
    entity_id = None
    entity_resolution = None
    if entity_reference:
        entity, entity_resolution = resolve_entity(client, entity_reference)
        entity_id = entity["id"]
    result: dict[str, Any] = {"user": user}
    requests: dict[str, Any] = {}
    if "audit" in selected:
        audit, meta = client.paginate(
            f"/users/{user_id}/audit-events",
            all_pages=True,
            max_limit=100,
            params={"category": category, "event_type": event_type, "entity_id": entity_id},
        )
        result["audit_events"] = audit["items"]
        requests["audit_events"] = meta
    if "membership" in selected:
        membership, meta = client.paginate(
            f"/users/{user_id}/membership-history",
            all_pages=True,
            max_limit=100,
            params={"event_type": event_type, "entity_id": entity_id},
        )
        result["membership_history"] = membership["items"]
        requests["membership_history"] = meta
    text = "\n".join(
        [
            f"Timeline: {user.get('email') or user_id}",
            f"Audit events:       {len(result.get('audit_events', [])) if 'audit' in selected else 'not requested'}",
            (
                "Membership history: "
                f"{len(result.get('membership_history', [])) if 'membership' in selected else 'not requested'}"
            ),
        ]
    )
    emit_remote_result(
        "users.timeline",
        result,
        target=target,
        meta={
            "resolution": resolution.get("resolution"),
            "entity_resolution": entity_resolution.get("resolution") if entity_resolution else None,
            "requests": requests,
        },
        text=text,
    )


@click.command("orphaned")
@click.option("--search", default=None)
@click.option("--root-entity-id", default=None)
@click.option("--page", type=click.IntRange(min=1), default=1, show_default=True)
@click.option("--limit", type=click.IntRange(min=1, max=100), default=20, show_default=True)
@click.option("--all", "all_pages", is_flag=True)
def users_orphaned(
    search: Optional[str],
    root_entity_id: Optional[str],
    page: int,
    limit: int,
    all_pages: bool,
):
    """List users with membership history but no active entity membership."""

    target, client = remote_client()
    result, meta = client.paginate(
        "/users/orphaned",
        page=page,
        limit=limit,
        max_limit=100,
        all_pages=all_pages,
        params={"search": search, "root_entity_id": root_entity_id},
    )
    items = [item for item in result["items"] if isinstance(item, dict)]
    display_items = [
        item | {"user_email": (item.get("user", {}).get("email") if isinstance(item.get("user"), dict) else None)}
        for item in items
    ]
    emit_remote_result(
        "users.orphaned",
        result,
        target=target,
        meta=meta,
        text=records_text(
            display_items,
            (
                ("USER", "user_email"),
                ("LAST ENTITY", "last_entity_name"),
                ("LAST EVENT", "last_membership_event_type"),
                ("WHEN", "last_membership_event_at"),
            ),
        ),
    )


@click.command("resend-invite")
@click.argument("reference")
@click.option("--yes", is_flag=True)
def users_resend_invite(reference: str, yes: bool):
    """Regenerate and deliver an invitation for a resolved invited user."""

    target, client = remote_client()
    user, resolution = client.resolve_user(reference)
    require_confirmation(
        prompt=f"Resend the invitation to {user.get('email')} ({user['id']})?",
        yes=yes,
    )
    result, meta = client.request("POST", f"/users/{user['id']}/resend-invite")
    emit_remote_result(
        "users.resend-invite",
        result,
        target=target,
        meta=meta | {"resolution": resolution.get("resolution")},
        text=f"Invitation resent to {user.get('email')}.",
        changed=True,
    )


def register_user_inspection_commands(group: click.Group) -> None:
    """Attach operator-focused read models and invitation retry."""

    for command in (users_access_report, users_timeline, users_orphaned, users_resend_invite):
        group.add_command(command)
