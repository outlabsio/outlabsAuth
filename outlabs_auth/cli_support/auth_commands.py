"""Interactive authentication commands for the remote CLI control plane."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import click

from outlabs_auth.cli_support.client import RemoteClient, resolve_remote_target
from outlabs_auth.cli_support.credentials import CredentialStore
from outlabs_auth.cli_support.entity_commands import resolve_entity
from outlabs_auth.cli_support.secrets import read_secret
from outlabs_auth.cli_support.runtime import (
    CliError,
    EXIT_USAGE,
    emit_result,
    get_runtime,
    require_confirmation,
)


def _iso_timestamp(value: float) -> str:
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _require_bearer_target() -> None:
    runtime = get_runtime()
    target = resolve_remote_target(runtime)
    if target.credential_type != "bearer":
        raise CliError(
            code="BEARER_SESSION_REQUIRED",
            message="This command manages a human bearer session, but the active context uses an API key.",
            exit_code=EXIT_USAGE,
            hint="Use a bearer context for login/logout, or manage the API key through its environment variable.",
        )


@click.group("auth")
def auth_group():
    """Sign in, inspect, refresh, and revoke a local CLI session."""


@auth_group.command("login")
@click.option("--email", required=True, envvar="OUTLABS_AUTH_EMAIL", help="Account email address.")
@click.option("--password-stdin", is_flag=True, help="Read the password from one line on stdin.")
@click.option(
    "--password-env",
    default="OUTLABS_AUTH_PASSWORD",
    show_default=True,
    help="Environment variable containing the password; the value is never printed or persisted.",
)
def auth_login(email: str, password_stdin: bool, password_env: str):
    """Create a refreshable local session without exposing its tokens."""

    _require_bearer_target()
    target = resolve_remote_target(get_runtime())
    password = read_secret(
        from_stdin=password_stdin,
        env_name=password_env,
        prompt="Login password",
        missing_code="LOGIN_PASSWORD_MISSING",
    )
    client = RemoteClient(target)
    session, meta = client.login(email=email, password=password)
    result = session.public_dict() | {
        "expires_at": _iso_timestamp(session.expires_at),
        "created_at": _iso_timestamp(session.created_at),
        "credential_store": str(CredentialStore().path),
    }
    emit_result(
        "auth.login",
        result,
        changed=True,
        context=target.context_dict(),
        meta=meta,
        text=(
            f"Signed in as {email} for context '{target.name}'.\n"
            f"Access token expires: {_iso_timestamp(session.expires_at)}\n"
            "The refreshable session is stored with owner-only permissions."
        ),
    )


def _emit_session_exchange(command: str, client: RemoteClient, payload, meta, *, email: Optional[str]) -> None:
    target = client.target
    session = client.store_session_payload(payload, email=email, endpoint=command)
    result = session.public_dict() | {
        "expires_at": _iso_timestamp(session.expires_at),
        "created_at": _iso_timestamp(session.created_at),
        "credential_store": str(CredentialStore().path),
    }
    emit_result(
        command,
        result,
        changed=True,
        context=target.context_dict(),
        meta=meta,
        text=(
            f"Authenticated for context '{target.name}'.\n"
            f"Access token expires: {_iso_timestamp(session.expires_at)}\n"
            "The refreshable session is stored with owner-only permissions."
        ),
    )


def _require_one_identifier(email: Optional[str], phone: Optional[str]) -> None:
    if bool(email) == bool(phone):
        raise CliError(
            code="IDENTIFIER_REQUIRED",
            message="Choose exactly one of --email or --phone.",
            exit_code=EXIT_USAGE,
        )


@auth_group.command("register")
@click.option("--email", required=True)
@click.option("--password-stdin", is_flag=True)
@click.option("--password-env", default="OUTLABS_AUTH_REGISTER_PASSWORD", show_default=True)
@click.option("--first-name", default=None)
@click.option("--last-name", default=None)
def auth_register(
    email: str,
    password_stdin: bool,
    password_env: str,
    first_name: Optional[str],
    last_name: Optional[str],
):
    """Register an account through the public endpoint."""

    password = read_secret(
        from_stdin=password_stdin,
        env_name=password_env,
        prompt="Registration password",
        missing_code="REGISTRATION_PASSWORD_MISSING",
        confirmation_prompt=True,
    )
    target = resolve_remote_target(get_runtime())
    result, meta = RemoteClient(target).request(
        "POST",
        "/auth/register",
        json_body={
            "email": email,
            "password": password,
            "first_name": first_name,
            "last_name": last_name,
        },
        require_auth=False,
    )
    emit_result(
        "auth.register",
        result,
        changed=True,
        context=target.context_dict(),
        meta=meta,
        text=f"Registered {email}. Sign in after completing any required verification.",
    )


@auth_group.command("forgot-password")
@click.option("--email", required=True)
def auth_forgot_password(email: str):
    """Request an opaque password-reset delivery."""

    target = resolve_remote_target(get_runtime())
    _, meta = RemoteClient(target).request(
        "POST",
        "/auth/forgot-password",
        json_body={"email": email, "app": target.app},
        require_auth=False,
    )
    emit_result(
        "auth.forgot-password",
        {"requested": True, "email": email},
        changed=True,
        context=target.context_dict(),
        meta=meta,
        text="If the account exists, password-reset instructions were requested.",
    )


@auth_group.command("reset-password")
@click.option("--token-stdin", is_flag=True)
@click.option("--token-env", default="OUTLABS_AUTH_RESET_TOKEN", show_default=True)
@click.option("--password-stdin", is_flag=True)
@click.option("--password-env", default="OUTLABS_AUTH_RESET_PASSWORD", show_default=True)
def auth_reset_password(
    token_stdin: bool,
    token_env: str,
    password_stdin: bool,
    password_env: str,
):
    """Exchange a reset token and replacement password from safe input sources."""

    token = read_secret(
        from_stdin=token_stdin,
        env_name=token_env,
        prompt="Password reset token",
        missing_code="RESET_TOKEN_MISSING",
    )
    password = read_secret(
        from_stdin=password_stdin,
        env_name=password_env,
        prompt="Replacement password",
        missing_code="RESET_PASSWORD_MISSING",
        confirmation_prompt=True,
    )
    target = resolve_remote_target(get_runtime())
    _, meta = RemoteClient(target).request(
        "POST",
        "/auth/reset-password",
        json_body={"token": token, "new_password": password},
        require_auth=False,
    )
    emit_result(
        "auth.reset-password",
        {"password_reset": True},
        changed=True,
        context=target.context_dict(),
        meta=meta,
        text="Password reset successfully.",
    )


@auth_group.command("request-magic-link")
@click.option("--email", required=True)
@click.option("--redirect", "redirect_url", default=None)
def auth_request_magic_link(email: str, redirect_url: Optional[str]):
    """Request a one-time magic-link delivery."""

    target = resolve_remote_target(get_runtime())
    _, meta = RemoteClient(target).request(
        "POST",
        "/auth/magic-link/request",
        json_body={"email": email, "app": target.app, "redirect_url": redirect_url},
        require_auth=False,
    )
    emit_result(
        "auth.request-magic-link",
        {"requested": True, "email": email},
        changed=True,
        context=target.context_dict(),
        meta=meta,
        text="If the account is eligible, a magic-link delivery was requested.",
    )


@auth_group.command("verify-magic-link")
@click.option("--token-stdin", is_flag=True)
@click.option("--token-env", default="OUTLABS_AUTH_MAGIC_TOKEN", show_default=True)
def auth_verify_magic_link(token_stdin: bool, token_env: str):
    """Exchange a magic token for a target-bound stored session."""

    _require_bearer_target()
    token = read_secret(
        from_stdin=token_stdin,
        env_name=token_env,
        prompt="Magic-link token",
        missing_code="MAGIC_TOKEN_MISSING",
    )
    target = resolve_remote_target(get_runtime())
    client = RemoteClient(target)
    result, meta = client.request(
        "POST",
        "/auth/magic-link/verify",
        json_body={"token": token},
        require_auth=False,
    )
    _emit_session_exchange("auth.verify-magic-link", client, result, meta, email=None)


@auth_group.command("request-code")
@click.option("--email", default=None)
@click.option("--phone", default=None, help="Verified E.164 phone number.")
@click.option("--channel", type=click.Choice(["email", "whatsapp", "sms"]), default=None)
@click.option("--redirect", "redirect_url", default=None)
def auth_request_code(
    email: Optional[str],
    phone: Optional[str],
    channel: Optional[str],
    redirect_url: Optional[str],
):
    """Request a short-lived email, WhatsApp, or SMS access code."""

    _require_one_identifier(email, phone)
    target = resolve_remote_target(get_runtime())
    _, meta = RemoteClient(target).request(
        "POST",
        "/auth/access-code/request",
        json_body={
            "email": email,
            "phone": phone,
            "channel": channel,
            "app": target.app,
            "redirect_url": redirect_url,
        },
        require_auth=False,
    )
    emit_result(
        "auth.request-code",
        {"requested": True, "email": email, "phone": phone, "channel": channel},
        changed=True,
        context=target.context_dict(),
        meta=meta,
        text="If the account is eligible, an access-code delivery was requested.",
    )


@auth_group.command("verify-code")
@click.option("--email", default=None)
@click.option("--phone", default=None)
@click.option("--channel", type=click.Choice(["email", "whatsapp", "sms"]), default=None)
@click.option("--code-stdin", is_flag=True)
@click.option("--code-env", default="OUTLABS_AUTH_ACCESS_CODE", show_default=True)
def auth_verify_code(
    email: Optional[str],
    phone: Optional[str],
    channel: Optional[str],
    code_stdin: bool,
    code_env: str,
):
    """Exchange an access code for a target-bound stored session."""

    _require_bearer_target()
    _require_one_identifier(email, phone)
    code = read_secret(
        from_stdin=code_stdin,
        env_name=code_env,
        prompt="Access code",
        missing_code="ACCESS_CODE_MISSING",
    )
    target = resolve_remote_target(get_runtime())
    client = RemoteClient(target)
    result, meta = client.request(
        "POST",
        "/auth/access-code/verify",
        json_body={"email": email, "phone": phone, "channel": channel, "code": code},
        require_auth=False,
    )
    _emit_session_exchange("auth.verify-code", client, result, meta, email=email)


@auth_group.command("invite")
@click.option("--email", required=True)
@click.option("--first-name", default=None)
@click.option("--last-name", default=None)
@click.option("--superuser/--not-superuser", "is_superuser", default=False)
@click.option("--role", "role_references", multiple=True)
@click.option("--entity", "entity_reference", default=None)
@click.option("--yes", is_flag=True)
def auth_invite(
    email: str,
    first_name: Optional[str],
    last_name: Optional[str],
    is_superuser: bool,
    role_references: tuple[str, ...],
    entity_reference: Optional[str],
    yes: bool,
):
    """Invite a user with resolved roles and optional entity membership."""

    target = resolve_remote_target(get_runtime())
    client = RemoteClient(target)
    role_ids = []
    for reference in role_references:
        role, _ = client.resolve_resource(
            reference,
            resource_name="role",
            detail_path="/roles/{id}",
            list_path="/roles/",
            exact_fields=("name", "display_name"),
            max_limit=100,
        )
        role_ids.append(role["id"])
    entity_id = None
    if entity_reference:
        entity, _ = resolve_entity(client, entity_reference)
        entity_id = entity["id"]
    if is_superuser or role_ids or entity_id:
        require_confirmation(
            prompt=(
                f"Invite {email} with "
                f"{'superuser authority, ' if is_superuser else ''}"
                f"{len(role_ids)} roles"
                f"{' and an entity membership' if entity_id else ''}?"
            ),
            yes=yes,
        )
    result, meta = client.request(
        "POST",
        "/auth/invite",
        json_body={
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "is_superuser": is_superuser,
            "role_ids": role_ids or None,
            "entity_id": entity_id,
        },
    )
    emit_result(
        "auth.invite",
        result,
        changed=True,
        context=target.context_dict(),
        meta=meta,
        text=f"Invited {email}.",
    )


@auth_group.command("accept-invite")
@click.option("--token-stdin", is_flag=True)
@click.option("--token-env", default="OUTLABS_AUTH_INVITE_TOKEN", show_default=True)
@click.option("--password-stdin", is_flag=True)
@click.option("--password-env", default="OUTLABS_AUTH_INVITE_PASSWORD", show_default=True)
def auth_accept_invite(
    token_stdin: bool,
    token_env: str,
    password_stdin: bool,
    password_env: str,
):
    """Accept an invitation and store the resulting bearer session."""

    _require_bearer_target()
    token = read_secret(
        from_stdin=token_stdin,
        env_name=token_env,
        prompt="Invitation token",
        missing_code="INVITE_TOKEN_MISSING",
    )
    password = read_secret(
        from_stdin=password_stdin,
        env_name=password_env,
        prompt="New account password",
        missing_code="INVITE_PASSWORD_MISSING",
        confirmation_prompt=True,
    )
    target = resolve_remote_target(get_runtime())
    client = RemoteClient(target)
    result, meta = client.request(
        "POST",
        "/auth/accept-invite",
        json_body={"token": token, "new_password": password, "app": target.app},
        require_auth=False,
    )
    _emit_session_exchange("auth.accept-invite", client, result, meta, email=None)


@auth_group.command("status")
@click.option("--verify/--offline", default=True, show_default=True, help="Verify the credential against /users/me.")
def auth_status(verify: bool):
    """Show credential source, expiry, target binding, and optional server identity."""

    target = resolve_remote_target(get_runtime())
    client = RemoteClient(target)
    result = client.authentication_status()
    meta = None
    if verify and result["authenticated"]:
        identity, meta = client.whoami()
        result["verified"] = True
        result["identity"] = identity
    else:
        result["verified"] = False
        result["identity"] = None

    stored = result.get("stored_session")
    if isinstance(stored, dict):
        stored["expires_at"] = _iso_timestamp(float(stored["expires_at"]))
        stored["created_at"] = _iso_timestamp(float(stored["created_at"]))
    if result["authenticated"]:
        identity = result.get("identity")
        user = identity.get("email") if isinstance(identity, dict) else None
        text_output = (
            f"Authenticated: yes ({result['source']})\n"
            f"Context:       {target.name}\n"
            f"Target:        {target.base_url}{target.api_prefix}\n"
            f"Verified user: {user or ('not checked' if not verify else 'unknown')}"
        )
    else:
        text_output = (
            "Authenticated: no\n"
            f"Context:       {target.name}\n"
            f"Set {target.credential_env} or run outlabs-auth auth login."
        )
    emit_result(
        "auth.status",
        result,
        context=target.context_dict(),
        meta=meta,
        text=text_output,
    )


@auth_group.command("refresh")
def auth_refresh():
    """Rotate a stored bearer session immediately."""

    _require_bearer_target()
    target = resolve_remote_target(get_runtime())
    session, meta = RemoteClient(target).refresh_stored_session(force=True)
    emit_result(
        "auth.refresh",
        {
            "profile": target.name,
            "expires_at": _iso_timestamp(session.expires_at),
            "refreshed": True,
        },
        changed=True,
        context=target.context_dict(),
        meta=meta,
        text=f"Session refreshed; access token expires {_iso_timestamp(session.expires_at)}.",
    )


@auth_group.command("logout")
@click.option("--all", "all_devices", is_flag=True, help="Revoke every refresh token for the current user.")
@click.option(
    "--immediate", is_flag=True, help="Also revoke the current access token immediately when Redis supports it."
)
@click.option("--local-only", is_flag=True, help="Forget the local session without calling the remote API.")
@click.option("--yes", is_flag=True, help="Confirm --all without prompting.")
def auth_logout(all_devices: bool, immediate: bool, local_only: bool, yes: bool):
    """Revoke the current session and remove its local credential material."""

    _require_bearer_target()
    if local_only and (all_devices or immediate):
        raise CliError(
            code="CONFLICTING_OPTIONS",
            message="--local-only cannot be combined with --all or --immediate.",
            exit_code=EXIT_USAGE,
        )
    target = resolve_remote_target(get_runtime())
    client = RemoteClient(target)
    store = client.credential_store()
    session = client.stored_session(required=not all_devices and not local_only)
    meta: Optional[dict[str, object]] = None

    if all_devices:
        require_confirmation(
            prompt=f"Revoke every session for the user authenticated to '{target.name}'?",
            yes=yes,
        )
    if not local_only:
        if session is not None and session.expires_within(30):
            session, _ = client.refresh_stored_session(session=session, force=True)
        _, request_meta = client.logout(
            refresh_token=None if all_devices else (session.refresh_token if session else None),
            immediate=immediate,
        )
        meta = request_meta
    removed = store.delete(target.name)
    emit_result(
        "auth.logout",
        {
            "profile": target.name,
            "remote_revoked": not local_only,
            "all_devices": all_devices,
            "immediate": immediate,
            "local_session_removed": removed,
        },
        changed=removed or not local_only,
        context=target.context_dict(),
        meta=meta,
        text=(
            f"Forgot the local session for '{target.name}'."
            if local_only
            else f"Logged out of '{target.name}'{' on all devices' if all_devices else ''}."
        ),
    )
