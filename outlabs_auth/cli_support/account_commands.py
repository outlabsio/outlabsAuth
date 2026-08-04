"""Authenticated self-service account commands for UI-optional deployments."""

from __future__ import annotations

from typing import Any, Optional

import click

from outlabs_auth.cli_support.payloads import require_nonempty_payload
from outlabs_auth.cli_support.resource_common import (
    detail_text,
    emit_remote_result,
    records_text,
    remote_client,
    request_payload,
)
from outlabs_auth.cli_support.runtime import require_confirmation
from outlabs_auth.cli_support.secrets import read_secret


def _account_text(account: dict[str, Any]) -> str:
    return detail_text(
        account,
        (
            ("Email", "email"),
            ("Name", "first_name"),
            ("Last name", "last_name"),
            ("Phone", "phone"),
            ("Email verified", "email_verified"),
            ("Phone verified", "phone_verified"),
            ("Status", "status"),
            ("Superuser", "is_superuser"),
            ("Root entity", "root_entity_name"),
            ("ID", "id"),
        ),
    )


@click.group("account")
def account_group():
    """Inspect and manage the authenticated human account."""


@account_group.command("show")
def account_show():
    """Show the current profile without requiring administrative permission."""

    target, client = remote_client()
    result, meta = client.request("GET", "/users/me")
    emit_remote_result("account.show", result, target=target, meta=meta, text=_account_text(result))


@account_group.command("update")
@click.option("--from", "json_source", type=click.Path(dir_okay=False))
@click.option("--email", default=None)
@click.option("--first-name", default=None)
@click.option("--last-name", default=None)
@click.option("--phone", default=None, help="E.164 WhatsApp/SMS number.")
@click.option("--clear-phone", is_flag=True)
def account_update(
    json_source: Optional[str],
    email: Optional[str],
    first_name: Optional[str],
    last_name: Optional[str],
    phone: Optional[str],
    clear_phone: bool,
):
    """Update the current profile; email or phone changes may require verification."""

    if phone is not None and clear_phone:
        raise click.UsageError("Use --phone or --clear-phone, not both.")
    payload = request_payload(
        json_source,
        email=email,
        first_name=first_name,
        last_name=last_name,
        phone=phone,
    )
    if clear_phone:
        payload["phone"] = None
    require_nonempty_payload(payload)
    target, client = remote_client()
    result, meta = client.request("PATCH", "/users/me", json_body=payload)
    emit_remote_result(
        "account.update",
        result,
        target=target,
        meta=meta,
        text=_account_text(result),
        changed=True,
    )


@account_group.command("change-password")
@click.option("--current-password-stdin", is_flag=True)
@click.option("--current-password-env", default="OUTLABS_AUTH_CURRENT_PASSWORD", show_default=True)
@click.option("--new-password-stdin", is_flag=True)
@click.option("--new-password-env", default="OUTLABS_AUTH_NEW_PASSWORD", show_default=True)
def account_change_password(
    current_password_stdin: bool,
    current_password_env: str,
    new_password_stdin: bool,
    new_password_env: str,
):
    """Change the current password using only safe secret input channels."""

    current_password = read_secret(
        from_stdin=current_password_stdin,
        env_name=current_password_env,
        prompt="Current password",
        missing_code="CURRENT_PASSWORD_MISSING",
    )
    new_password = read_secret(
        from_stdin=new_password_stdin,
        env_name=new_password_env,
        prompt="New password",
        missing_code="NEW_PASSWORD_MISSING",
        confirmation_prompt=True,
    )
    target, client = remote_client()
    _, meta = client.request(
        "POST",
        "/users/me/change-password",
        json_body={"current_password": current_password, "new_password": new_password},
    )
    emit_remote_result(
        "account.change-password",
        {"password_changed": True},
        target=target,
        meta=meta,
        text="Password changed successfully.",
        changed=True,
    )


@account_group.command("request-phone-code")
def account_request_phone_code():
    """Request a verification code for the profile's current phone number."""

    target, client = remote_client()
    _, meta = client.request("POST", "/users/me/phone/request-code")
    emit_remote_result(
        "account.request-phone-code",
        {"requested": True},
        target=target,
        meta=meta,
        text="Phone verification code requested.",
        changed=True,
    )


@account_group.command("verify-phone")
@click.option("--code-stdin", is_flag=True)
@click.option("--code-env", default="OUTLABS_AUTH_PHONE_VERIFY_CODE", show_default=True)
def account_verify_phone(code_stdin: bool, code_env: str):
    """Verify the profile phone using a code from stdin, env, or hidden prompt."""

    code = read_secret(
        from_stdin=code_stdin,
        env_name=code_env,
        prompt="Phone verification code",
        missing_code="PHONE_VERIFY_CODE_MISSING",
    )
    target, client = remote_client()
    result, meta = client.request("POST", "/users/me/phone/verify-code", json_body={"code": code})
    emit_remote_result(
        "account.verify-phone",
        result,
        target=target,
        meta=meta,
        text=_account_text(result),
        changed=True,
    )


@account_group.command("social-accounts")
def account_social_accounts():
    """List linked OAuth/social identities without provider token secrets."""

    target, client = remote_client()
    result, meta = client.request("GET", "/users/me/social-accounts")
    items = [item for item in result if isinstance(item, dict)] if isinstance(result, list) else []
    emit_remote_result(
        "account.social-accounts",
        {"items": result},
        target=target,
        meta=meta,
        text=records_text(
            items,
            (
                ("PROVIDER", "provider"),
                ("EMAIL", "email"),
                ("VERIFIED", "email_verified"),
                ("LINKED", "linked_at"),
                ("ID", "id"),
            ),
        ),
    )


@account_group.command("unlink-social")
@click.argument("account_id")
@click.option("--yes", is_flag=True)
def account_unlink_social(account_id: str, yes: bool):
    """Unlink one social identity unless it is the last usable login method."""

    require_confirmation(prompt=f"Unlink social account {account_id}?", yes=yes)
    target, client = remote_client()
    _, meta = client.request("DELETE", f"/users/me/social-accounts/{account_id}")
    emit_remote_result(
        "account.unlink-social",
        {"id": account_id, "unlinked": True},
        target=target,
        meta=meta,
        text=f"Unlinked social account {account_id}.",
        changed=True,
    )
