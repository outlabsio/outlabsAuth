"""Authenticated raw API escape hatch for forward-compatible administration."""

from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse

import click

from outlabs_auth.cli_support.client import RemoteClient, resolve_remote_target
from outlabs_auth.cli_support.payloads import load_json_object, parse_key_values
from outlabs_auth.cli_support.runtime import (
    CliError,
    EXIT_USAGE,
    emit_result,
    get_runtime,
    require_confirmation,
)


def _normalize_api_path(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        raise CliError(
            code="INVALID_API_PATH",
            message="API paths must be relative to the active context and contain no query string.",
            exit_code=EXIT_USAGE,
            hint="Use --query KEY=VALUE for query parameters.",
        )
    parts = [part for part in parsed.path.split("/") if part]
    if any(part in {".", ".."} for part in parts):
        raise CliError(
            code="INVALID_API_PATH",
            message="API paths must not contain dot segments.",
            exit_code=EXIT_USAGE,
        )
    if not parts:
        raise CliError(
            code="INVALID_API_PATH",
            message="An API resource path is required.",
            exit_code=EXIT_USAGE,
        )
    return "/" + "/".join(parts)


@click.group("api")
def api_group():
    """Call mounted endpoints not yet covered by a purpose-built command."""


@api_group.command("request")
@click.argument("method", type=click.Choice(["GET", "POST", "PUT", "PATCH", "DELETE"], case_sensitive=False))
@click.argument("path")
@click.option("--query", "query_values", multiple=True, metavar="KEY=VALUE", help="Add a query parameter.")
@click.option(
    "--from", "json_source", type=click.Path(dir_okay=False), help="Read a JSON request object from FILE or -."
)
@click.option("--unauthenticated", is_flag=True, help="Do not send a credential; allowed only for GET.")
@click.option("--yes", is_flag=True, help="Confirm a raw write request without prompting.")
def api_request(
    method: str,
    path: str,
    query_values: tuple[str, ...],
    json_source: Optional[str],
    unauthenticated: bool,
    yes: bool,
):
    """Issue a bounded JSON request relative to the configured API prefix."""

    normalized_method = method.upper()
    normalized_path = _normalize_api_path(path)
    if unauthenticated and normalized_method != "GET":
        raise CliError(
            code="UNAUTHENTICATED_WRITE_FORBIDDEN",
            message="Raw unauthenticated write requests are not allowed.",
            exit_code=EXIT_USAGE,
        )
    if normalized_method in {"POST", "PUT", "PATCH", "DELETE"}:
        require_confirmation(
            prompt=f"Send raw {normalized_method} request to '{normalized_path}'?",
            yes=yes,
        )
    body = load_json_object(json_source, required=False)
    if normalized_method == "GET" and body is not None:
        raise CliError(
            code="GET_BODY_FORBIDDEN",
            message="GET requests cannot include --from JSON input.",
            exit_code=EXIT_USAGE,
        )
    target = resolve_remote_target(get_runtime())
    result, meta = RemoteClient(target).request(
        normalized_method,
        normalized_path,
        json_body=body,
        params=parse_key_values(query_values),
        require_auth=not unauthenticated,
    )
    emit_result(
        "api.request",
        result,
        changed=normalized_method != "GET",
        context=target.context_dict(),
        meta=meta | {"method": normalized_method, "path": normalized_path},
        text=(
            f"{normalized_method} {normalized_path}: no response body"
            if result is None
            else result if isinstance(result, str) else None
        ),
    )
