"""Common presentation and resolution helpers for remote resource groups."""

from __future__ import annotations

from typing import Any, Iterable, Optional, Sequence

from outlabs_auth.cli_support.client import RemoteClient, RemoteTarget, resolve_remote_target
from outlabs_auth.cli_support.payloads import compact_payload, load_json_object
from outlabs_auth.cli_support.runtime import emit_result, get_runtime


def remote_client() -> tuple[RemoteTarget, RemoteClient]:
    target = resolve_remote_target(get_runtime())
    return target, RemoteClient(target)


def request_payload(source: Optional[str], **explicit: Any) -> dict[str, Any]:
    payload = dict(load_json_object(source, required=False) or {})
    payload.update(compact_payload(explicit))
    return payload


def records_text(items: Iterable[dict[str, Any]], columns: tuple[tuple[str, str], ...]) -> str:
    records = list(items)
    if not records:
        return "No records matched."
    headings = " | ".join(label for label, _ in columns)
    lines = [headings]
    for item in records:
        lines.append(" | ".join(_display(item.get(field)) for _, field in columns))
    return "\n".join(lines)


def detail_text(item: dict[str, Any], fields: tuple[tuple[str, str], ...]) -> str:
    return "\n".join(f"{label + ':':<16} {_display(item.get(field))}" for label, field in fields)


def _display(value: Any) -> str:
    if value is None or value == "":
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else "-"
    return str(value)


def emit_remote_result(
    command: str,
    result: Any,
    *,
    target: RemoteTarget,
    meta: dict[str, Any],
    text: Optional[str] = None,
    changed: Optional[bool] = None,
    warnings: Optional[Sequence[str]] = None,
) -> None:
    emit_result(
        command,
        result,
        text=text,
        changed=changed,
        warnings=warnings,
        context=target.context_dict(),
        meta=meta,
    )
