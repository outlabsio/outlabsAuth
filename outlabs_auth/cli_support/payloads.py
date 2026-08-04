"""Safe JSON and key/value input helpers shared by remote commands."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional, Sequence

from outlabs_auth.cli_support.runtime import CliError, EXIT_USAGE

MAX_JSON_INPUT_BYTES = 2 * 1024 * 1024


def load_json_object(source: Optional[str], *, required: bool = False) -> Optional[dict[str, Any]]:
    """Load a bounded JSON object from a file or stdin without echoing content."""

    if source is None:
        if required:
            raise CliError(
                code="JSON_INPUT_REQUIRED",
                message="This operation requires a JSON request object.",
                exit_code=EXIT_USAGE,
                hint="Pass --from FILE, or --from - to read JSON from stdin.",
            )
        return None
    try:
        if source == "-":
            raw = sys.stdin.buffer.read(MAX_JSON_INPUT_BYTES + 1)
        else:
            path = Path(source).expanduser()
            if path.stat().st_size > MAX_JSON_INPUT_BYTES:
                raise CliError(
                    code="JSON_INPUT_TOO_LARGE",
                    message="JSON input exceeds the 2 MiB safety limit.",
                    exit_code=EXIT_USAGE,
                    details={"path": str(path), "max_bytes": MAX_JSON_INPUT_BYTES},
                )
            raw = path.read_bytes()
    except CliError:
        raise
    except OSError as exc:
        raise CliError(
            code="JSON_INPUT_UNREADABLE",
            message="Cannot read the JSON input.",
            exit_code=EXIT_USAGE,
            details={"source": source, "exception_type": type(exc).__name__},
        ) from exc
    if len(raw) > MAX_JSON_INPUT_BYTES:
        raise CliError(
            code="JSON_INPUT_TOO_LARGE",
            message="JSON input exceeds the 2 MiB safety limit.",
            exit_code=EXIT_USAGE,
            details={"max_bytes": MAX_JSON_INPUT_BYTES},
        )
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CliError(
            code="INVALID_JSON_INPUT",
            message="The request input is not valid JSON.",
            exit_code=EXIT_USAGE,
            details={"source": source, "exception_type": type(exc).__name__},
        ) from exc
    if not isinstance(value, dict):
        raise CliError(
            code="JSON_OBJECT_REQUIRED",
            message="The request input must be a JSON object.",
            exit_code=EXIT_USAGE,
        )
    return value


def parse_key_values(values: Sequence[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise CliError(
                code="INVALID_KEY_VALUE",
                message=f"Expected KEY=VALUE, received '{value}'.",
                exit_code=EXIT_USAGE,
            )
        key, item = value.split("=", 1)
        if not key:
            raise CliError(
                code="INVALID_KEY_VALUE",
                message="Query parameter names must not be empty.",
                exit_code=EXIT_USAGE,
            )
        if key in result:
            raise CliError(
                code="DUPLICATE_QUERY_PARAMETER",
                message=f"Query parameter '{key}' was supplied more than once.",
                exit_code=EXIT_USAGE,
            )
        result[key] = item
    return result


def compact_payload(values: dict[str, Any]) -> dict[str, Any]:
    """Drop unspecified values while preserving false, zero, and empty lists."""

    return {name: value for name, value in values.items() if value is not None}


def require_payload_fields(payload: dict[str, Any], *fields: str) -> None:
    missing = [name for name in fields if payload.get(name) is None or payload.get(name) == ""]
    if missing:
        raise CliError(
            code="REQUIRED_FIELDS_MISSING",
            message="The request is missing required fields.",
            exit_code=EXIT_USAGE,
            details={"fields": missing},
        )


def require_nonempty_payload(payload: dict[str, Any]) -> None:
    if not payload:
        raise CliError(
            code="EMPTY_UPDATE",
            message="No changes were supplied.",
            exit_code=EXIT_USAGE,
            hint="Pass update flags or provide a JSON object with --from FILE.",
        )
