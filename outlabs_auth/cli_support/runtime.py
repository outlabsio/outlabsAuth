"""Stable output, error, and invocation contracts for the CLI."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence

import click

CLI_SCHEMA_VERSION = "outlabs-auth.cli/v1"

EXIT_OPERATION_FAILED = 1
EXIT_USAGE = 2
EXIT_AUTH = 3
EXIT_UNAVAILABLE = 4
EXIT_CONFLICT = 5
EXIT_PARTIAL = 6


@dataclass
class CliRuntime:
    """Options shared by local operator and remote administration commands."""

    output: str = "text"
    non_interactive: bool = False
    debug: bool = False
    profile: Optional[str] = None
    base_url: Optional[str] = None
    api_prefix: Optional[str] = None
    timeout: float = 10.0
    schema: Optional[str] = None
    credential_type: Optional[str] = None
    credential_env: Optional[str] = None


@dataclass
class CliError(Exception):
    """A safe, structured error intended for an operator or automation client."""

    code: str
    message: str
    exit_code: int = EXIT_OPERATION_FAILED
    details: Mapping[str, Any] = field(default_factory=dict)
    hint: Optional[str] = None
    retryable: bool = False

    def __str__(self) -> str:
        return self.message


def _detect_requested_output(args: Sequence[str]) -> str:
    """Read output intent before Click parses the full command tree.

    The legacy per-command ``--format`` option is recognized so even parser and
    configuration failures remain JSON when an existing caller requested JSON.
    """

    for index, value in enumerate(args):
        if value in {"--output", "--format"} and index + 1 < len(args):
            candidate = args[index + 1].lower()
            if candidate in {"text", "json"}:
                return candidate
        if value.startswith("--output=") or value.startswith("--format="):
            candidate = value.split("=", 1)[1].lower()
            if candidate in {"text", "json"}:
                return candidate
    return "text"


def _command_from_args(args: Sequence[str]) -> str:
    value_options = {
        "--output",
        "--profile",
        "--base-url",
        "--api-prefix",
        "--timeout",
        "--schema",
        "--format",
        "--credential-type",
        "--credential-env",
    }
    skip_next = False
    for index, value in enumerate(args):
        if skip_next:
            skip_next = False
            continue
        if value in value_options:
            skip_next = True
            continue
        if value.startswith("-"):
            continue
        # Only the first parsed word is safe to report before Click validates
        # the command. Later words may be option values containing secrets.
        if value in {"context", "db", "ops"} and index + 1 < len(args):
            subcommand = args[index + 1]
            if not subcommand.startswith("-"):
                return f"{value}.{subcommand}"
        return value
    return "outlabs-auth"


def _error_payload(problem: CliError, command: str) -> dict[str, Any]:
    error: dict[str, Any] = {
        "code": problem.code,
        "message": problem.message,
        "details": dict(problem.details),
        "retryable": problem.retryable,
    }
    if problem.hint:
        error["hint"] = problem.hint
    return {
        "schema_version": CLI_SCHEMA_VERSION,
        "ok": False,
        "command": command,
        "error": error,
    }


def render_error(problem: CliError, *, output: str, command: str) -> None:
    if output == "json":
        click.echo(json.dumps(_error_payload(problem, command), indent=2, default=str))
        return

    click.echo(f"Error [{problem.code}]: {problem.message}", err=True)
    if problem.hint:
        click.echo(f"Hint: {problem.hint}", err=True)


class AgentFriendlyGroup(click.Group):
    """Click group that guarantees safe errors, including parser failures."""

    def main(
        self,
        args: Optional[Sequence[str]] = None,
        prog_name: Optional[str] = None,
        complete_var: Optional[str] = None,
        standalone_mode: bool = True,
        windows_expand_args: bool = True,
        **extra: Any,
    ) -> Any:
        raw_args = list(args) if args is not None else list(sys.argv[1:])
        output = _detect_requested_output(raw_args)
        command = _command_from_args(raw_args)
        debug = "--debug" in raw_args

        try:
            return super().main(
                args=raw_args,
                prog_name=prog_name,
                complete_var=complete_var,
                standalone_mode=False,
                windows_expand_args=windows_expand_args,
                **extra,
            )
        except CliError as exc:
            problem = exc
        except click.ClickException as exc:
            problem = CliError(
                code="CLI_USAGE",
                message=exc.format_message(),
                exit_code=EXIT_USAGE,
                hint="Run the command with --help to inspect its accepted arguments.",
            )
        except click.Abort:
            problem = CliError(
                code="INTERACTION_ABORTED",
                message="The operation was aborted.",
                exit_code=EXIT_OPERATION_FAILED,
            )
        except Exception as exc:
            if debug:
                raise
            problem = CliError(
                code="INTERNAL_ERROR",
                message="The command failed unexpectedly.",
                exit_code=EXIT_OPERATION_FAILED,
                details={"exception_type": type(exc).__name__},
                hint="Re-run with --debug for a traceback.",
            )

        render_error(problem, output=output, command=command)
        if standalone_mode:
            raise SystemExit(problem.exit_code)
        return problem.exit_code


def get_runtime() -> CliRuntime:
    ctx = click.get_current_context(silent=True)
    if ctx is None:
        return CliRuntime()
    root = ctx.find_root()
    return root.obj if isinstance(root.obj, CliRuntime) else CliRuntime()


def effective_output(legacy_format: Optional[str] = None) -> str:
    return legacy_format or get_runtime().output


def emit_progress(message: str) -> None:
    """Emit human progress without contaminating structured stdout."""

    if get_runtime().output == "text":
        click.echo(message)


def require_confirmation(*, prompt: str, yes: bool, flag_hint: str = "--yes") -> None:
    """Require an explicit acknowledgement for a destructive operation."""

    if yes:
        return
    runtime = get_runtime()
    if runtime.non_interactive or not sys.stdin.isatty():
        raise CliError(
            code="INTERACTION_REQUIRED",
            message="The destructive operation requires explicit confirmation.",
            exit_code=EXIT_USAGE,
            hint=f"Review the target and pass {flag_hint} to confirm non-interactively.",
        )
    if not click.confirm(prompt, default=False):
        raise CliError(
            code="INTERACTION_ABORTED",
            message="The destructive operation was not confirmed.",
            exit_code=EXIT_OPERATION_FAILED,
        )


def emit_result(
    command: str,
    result: Any,
    *,
    text: Optional[str] = None,
    changed: Optional[bool] = None,
    warnings: Optional[Sequence[str]] = None,
    context: Optional[Mapping[str, Any]] = None,
    meta: Optional[Mapping[str, Any]] = None,
) -> None:
    runtime = get_runtime()
    if runtime.output == "text":
        if text is not None:
            click.echo(text)
        elif isinstance(result, str):
            click.echo(result)
        else:
            click.echo(json.dumps(result, indent=2, default=str))
        return

    payload: dict[str, Any] = {
        "schema_version": CLI_SCHEMA_VERSION,
        "ok": True,
        "command": command,
        "result": result,
        "warnings": list(warnings or ()),
    }
    if changed is not None:
        payload["changed"] = changed
    if context:
        payload["context"] = dict(context)
    if meta:
        payload["meta"] = dict(meta)
    click.echo(json.dumps(payload, indent=2, default=str))
