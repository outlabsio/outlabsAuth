"""CLI entry points for declarative planning and guarded application."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import click

from outlabs_auth.cli_support.declarative import (
    apply_plan,
    build_plan,
    validate_plan,
    write_plan_file,
)
from outlabs_auth.cli_support.payloads import load_json_object
from outlabs_auth.cli_support.resource_common import emit_remote_result, remote_client
from outlabs_auth.cli_support.runtime import CliError, EXIT_USAGE, require_confirmation


def _plan_text(plan: dict) -> str:
    operations = plan.get("operations", [])
    if not operations:
        return "No changes. Remote state already satisfies the manifest."
    lines = [
        f"Plan: {len(operations)} operations "
        f"({plan['summary']['create']} create, {plan['summary']['update']} update, "
        f"{plan['summary']['delete']} delete)",
        "",
    ]
    lines.extend(f"  {index:>2}. {operation['summary']}" for index, operation in enumerate(operations, 1))
    return "\n".join(lines)


@click.command("plan")
@click.argument("manifest", type=click.Path(exists=True, dir_okay=False))
@click.option("--out", "output_path", type=click.Path(dir_okay=False), default=None)
@click.option("--force", is_flag=True, help="Replace an existing plan output file.")
def declarative_plan(manifest: str, output_path: Optional[str], force: bool):
    """Compare a state manifest to the remote API without changing anything."""

    raw = load_json_object(manifest, required=True)
    assert raw is not None
    target, client = remote_client()
    plan = build_plan(client, target, raw)
    written = write_plan_file(output_path, plan, force=force) if output_path else None
    result = dict(plan)
    if written:
        result["written_to"] = str(written)
    emit_remote_result(
        "plan",
        result,
        target=target,
        meta={"manifest": str(Path(manifest).expanduser()), "plan_file": str(written) if written else None},
        text=f"{_plan_text(plan)}{f'\n\nSaved plan: {written}' if written else ''}",
        changed=False,
    )


@click.command("apply")
@click.argument("plan_file", type=click.Path(exists=True, dir_okay=False))
@click.option("--allow-delete", is_flag=True, help="Allow operations marked destructive in the saved plan.")
@click.option("--yes", is_flag=True, help="Confirm the complete saved plan without prompting.")
def declarative_apply(plan_file: str, allow_delete: bool, yes: bool):
    """Apply a saved, target-bound plan after validating all drift preconditions."""

    raw = load_json_object(plan_file, required=True)
    assert raw is not None
    target, client = remote_client()
    operations = validate_plan(raw, target)
    destructive = [operation for operation in operations if operation.get("destructive")]
    if destructive and not allow_delete:
        raise CliError(
            code="DESTRUCTIVE_PLAN_NOT_ALLOWED",
            message="The plan contains destructive operations.",
            exit_code=EXIT_USAGE,
            details={"operation_ids": [operation.get("id") for operation in destructive]},
            hint="Review the saved plan, then pass --allow-delete and --yes.",
        )
    if operations:
        require_confirmation(
            prompt=f"Apply {len(operations)} planned operations to context '{target.name}'?",
            yes=yes,
        )
    result = apply_plan(client, operations)
    emit_remote_result(
        "apply",
        result,
        target=target,
        meta={"plan_file": str(Path(plan_file).expanduser())},
        text=f"Applied {result['applied']} operations successfully.",
        changed=bool(result["applied"]),
    )


def register_declarative_commands(root: click.Group) -> None:
    root.add_command(declarative_plan)
    root.add_command(declarative_apply)
