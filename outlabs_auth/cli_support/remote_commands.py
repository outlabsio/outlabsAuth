"""Human- and agent-friendly commands for mounted OutlabsAuth APIs."""

from __future__ import annotations

from typing import Any, Optional

import click

from outlabs_auth.cli_support.client import RemoteClient, resolve_remote_target
from outlabs_auth.cli_support.contexts import (
    ContextProfile,
    ContextStore,
    normalize_api_prefix,
    normalize_base_url,
)
from outlabs_auth.cli_support.runtime import emit_result, get_runtime


@click.group("context")
def context_group():
    """Manage non-secret remote API contexts."""


@context_group.command("add")
@click.argument("name")
@click.option("--base-url", required=True, help="Remote host base URL, without the API prefix.")
@click.option("--api-prefix", default="/v1", show_default=True, help="Prefix shared by auth resource routers.")
@click.option("--app", default=None, help="Optional frontend application profile key.")
@click.option(
    "--credential-type",
    type=click.Choice(["bearer", "api-key"]),
    default="bearer",
    show_default=True,
    help="Credential transport used by this context.",
)
@click.option(
    "--credential-env",
    default=None,
    help="Name of the environment variable containing the credential.",
)
@click.option("--activate/--no-activate", default=True, show_default=True, help="Make this context active.")
@click.option("--force", is_flag=True, help="Replace an existing context with the same name.")
@click.option(
    "--allow-insecure",
    is_flag=True,
    help="Allow plain HTTP for a non-local target.",
)
def context_add(
    name: str,
    base_url: str,
    api_prefix: str,
    app: Optional[str],
    credential_type: str,
    credential_env: Optional[str],
    activate: bool,
    force: bool,
    allow_insecure: bool,
):
    """Add or replace a remote target context without storing its secret."""

    normalized_url = normalize_base_url(base_url, allow_insecure=allow_insecure)
    normalized_credential_type = credential_type.replace("-", "_")
    resolved_credential_env = credential_env or (
        "OUTLABS_AUTH_API_KEY" if normalized_credential_type == "api_key" else "OUTLABS_AUTH_TOKEN"
    )
    profile = ContextProfile.from_dict(
        name,
        {
            "base_url": normalized_url,
            "api_prefix": normalize_api_prefix(api_prefix),
            "app": app,
            "credential_type": normalized_credential_type,
            "credential_env": resolved_credential_env,
        },
    )
    store = ContextStore().load()
    existed = name in store.contexts
    store.add(profile, activate=activate, force=force)
    emit_result(
        "context.add",
        {
            "name": profile.name,
            "base_url": profile.base_url,
            "api_prefix": profile.api_prefix,
            "app": profile.app,
            "credential_type": profile.credential_type,
            "credential_env": profile.credential_env,
            "active": store.active == profile.name,
        },
        changed=not existed or force,
        text=f"Context '{profile.name}' {'updated' if existed else 'added'}{'; now active' if store.active == name else ''}.",
    )


@context_group.command("list")
def context_list():
    """List configured remote contexts."""

    store = ContextStore().load()
    items = [
        {
            "name": name,
            "active": name == store.active,
            "base_url": profile.base_url,
            "api_prefix": profile.api_prefix,
            "app": profile.app,
            "credential_type": profile.credential_type,
            "credential_env": profile.credential_env,
        }
        for name, profile in sorted(store.contexts.items())
    ]
    if items:
        lines = ["Remote contexts:"]
        for item in items:
            marker = "*" if item["active"] else " "
            lines.append(f"  {marker} {item['name']:<20} {item['base_url']}{item['api_prefix']}")
        text_output = "\n".join(lines)
    else:
        text_output = "No remote contexts configured."
    emit_result("context.list", {"active": store.active, "contexts": items}, text=text_output)


@context_group.command("current")
def context_current():
    """Show the selected remote context."""

    target = resolve_remote_target(get_runtime())
    emit_result(
        "context.current",
        target.context_dict()
        | {
            "credential_type": target.credential_type,
            "credential_env": target.credential_env,
            "timeout": target.timeout,
        },
        text=(
            f"Context:    {target.name}\n"
            f"API:        {target.base_url}{target.api_prefix}\n"
            f"Credential: {target.credential_type} via {target.credential_env}\n"
            f"Timeout:    {target.timeout:g}s"
        ),
    )


@context_group.command("use")
@click.argument("name")
def context_use(name: str):
    """Select the active remote context."""

    store = ContextStore().load()
    changed = store.active != name
    profile = store.use(name)
    emit_result(
        "context.use",
        {"name": profile.name, "base_url": profile.base_url, "api_prefix": profile.api_prefix},
        changed=changed,
        text=f"Active context: {profile.name}",
    )


@click.command("capabilities")
def capabilities_command():
    """Discover the preset and features exposed by the remote API."""

    target = resolve_remote_target(get_runtime())
    result, meta = RemoteClient(target).capabilities()
    if isinstance(result, dict):
        features = sorted(name for name, enabled in result.get("features", {}).items() if enabled)
        text_output = (
            f"Target:   {target.name} ({target.base_url}{target.api_prefix})\n"
            f"Version:  {result.get('library_version', 'unknown')} "
            f"({result.get('api_contract_version', 'unversioned API')})\n"
            f"Preset:   {result.get('preset', 'unknown')}\n"
            f"Features: {', '.join(features) if features else '(none reported)'}"
        )
    else:
        text_output = str(result)
    emit_result(
        "capabilities",
        result,
        text=text_output,
        context=target.context_dict(),
        meta=meta,
    )


@click.command("whoami")
def whoami_command():
    """Show the authenticated remote user and active target."""

    target = resolve_remote_target(get_runtime())
    result, meta = RemoteClient(target).whoami()
    if isinstance(result, dict):
        text_output = (
            f"User:     {result.get('email', result.get('id', 'unknown'))}\n"
            f"ID:       {result.get('id', 'unknown')}\n"
            f"Status:   {result.get('status', 'unknown')}\n"
            f"Context:  {target.name}"
        )
    else:
        text_output = str(result)
    emit_result(
        "whoami",
        result,
        text=text_output,
        context=target.context_dict(),
        meta=meta,
    )


def _format_user_list(payload: dict[str, Any]) -> str:
    raw_items = payload.get("items", [])
    items = raw_items if isinstance(raw_items, list) else []
    if not items:
        return "No users matched."

    lines = ["EMAIL | STATUS | ADMIN | ROOT | ID"]
    for item in items:
        if not isinstance(item, dict):
            continue
        lines.append(
            " | ".join(
                [
                    str(item.get("email") or "-"),
                    str(item.get("status") or "-"),
                    "yes" if item.get("is_superuser") else "no",
                    str(item.get("root_entity_name") or item.get("root_entity_id") or "-"),
                    str(item.get("id") or "-"),
                ]
            )
        )
    total = payload.get("total", len(items))
    if payload.get("all"):
        lines.append(f"\n{len(items)} of {total} users (all pages).")
    else:
        lines.append(
            f"\nPage {payload.get('page', 1)} of {payload.get('pages', 1)} " f"- {len(items)} shown, {total} total."
        )
    return "\n".join(lines)


def _format_user_detail(user: dict[str, Any]) -> str:
    name = " ".join(part for part in [str(user.get("first_name") or ""), str(user.get("last_name") or "")] if part)
    return "\n".join(
        [
            f"Email:       {user.get('email', '-')}",
            f"Name:        {name or '-'}",
            f"ID:          {user.get('id', '-')}",
            f"Status:      {user.get('status', '-')}",
            f"Superuser:   {'yes' if user.get('is_superuser') else 'no'}",
            f"Verified:    {'yes' if user.get('email_verified') else 'no'}",
            f"Root entity: {user.get('root_entity_name') or user.get('root_entity_id') or '-'}",
            f"Last login:  {user.get('last_login') or '-'}",
        ]
    )


@click.group("users")
def users_group():
    """Inspect and manage users through the authenticated remote API."""


@users_group.command("list")
@click.option("--page", type=click.IntRange(min=1), default=1, show_default=True)
@click.option("--limit", type=click.IntRange(min=1, max=100), default=20, show_default=True)
@click.option("--search", default=None, help="Search email, first name, or last name.")
@click.option(
    "--status",
    "user_status",
    type=click.Choice(["active", "suspended", "banned", "deleted"]),
    default=None,
)
@click.option("--root-entity-id", default=None, help="Restrict results to a root entity UUID.")
@click.option("--all", "all_pages", is_flag=True, help="Fetch every page using the maximum page size.")
def users_list(
    page: int,
    limit: int,
    search: Optional[str],
    user_status: Optional[str],
    root_entity_id: Optional[str],
    all_pages: bool,
):
    """List users with server-side filtering and optional auto-pagination."""

    target = resolve_remote_target(get_runtime())
    result, meta = RemoteClient(target).list_users(
        page=page,
        limit=limit,
        search=search,
        status=user_status,
        root_entity_id=root_entity_id,
        all_pages=all_pages,
    )
    emit_result(
        "users.list",
        result,
        text=_format_user_list(result),
        context=target.context_dict(),
        meta=meta,
    )


@users_group.command("get")
@click.argument("reference")
def users_get(reference: str):
    """Get a user by UUID, exact email, or unambiguous search reference."""

    target = resolve_remote_target(get_runtime())
    result, meta = RemoteClient(target).resolve_user(reference)
    emit_result(
        "users.get",
        result,
        text=_format_user_detail(result),
        context=target.context_dict(),
        meta=meta,
    )


def register_remote_commands(root: click.Group) -> None:
    root.add_command(context_group)
    root.add_command(capabilities_command)
    root.add_command(whoami_command)
    root.add_command(users_group)
