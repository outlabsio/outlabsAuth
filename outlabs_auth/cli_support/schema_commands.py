"""Machine-readable command discovery generated from the live Click tree."""

from __future__ import annotations

from typing import Any

import click

from outlabs_auth.cli_support.runtime import CliError, EXIT_USAGE, emit_result


def _type_schema(param_type: click.ParamType) -> dict[str, Any]:
    result: dict[str, Any] = {"name": param_type.name or type(param_type).__name__}
    choices = getattr(param_type, "choices", None)
    if choices is not None:
        result["choices"] = list(choices)
    minimum = getattr(param_type, "min", None)
    maximum = getattr(param_type, "max", None)
    if minimum is not None:
        result["minimum"] = minimum
    if maximum is not None:
        result["maximum"] = maximum
    return result


def _parameter_schema(parameter: click.Parameter) -> dict[str, Any]:
    result: dict[str, Any] = {
        "name": parameter.name,
        "kind": "option" if isinstance(parameter, click.Option) else "argument",
        "required": bool(parameter.required),
        "multiple": bool(getattr(parameter, "multiple", False)),
        "nargs": parameter.nargs,
        "type": _type_schema(parameter.type),
    }
    if isinstance(parameter, click.Option):
        result.update(
            {
                "flags": list(parameter.opts),
                "secondary_flags": list(parameter.secondary_opts),
                "help": parameter.help,
                "envvar": parameter.envvar,
                "is_flag": parameter.is_flag,
            }
        )
    default = parameter.default
    if isinstance(default, (str, int, float, bool)):
        result["default"] = default
    elif isinstance(default, (list, tuple)) and all(
        isinstance(item, (str, int, float, bool)) or item is None for item in default
    ):
        result["default"] = list(default)
    return result


def _command_schema(command: click.Command, path: str, *, recursive: bool) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": path,
        "name": "outlabs-auth" if path == "outlabs-auth" else command.name,
        "help": command.help,
        "short_help": command.short_help,
        "deprecated": bool(command.deprecated),
        "parameters": [_parameter_schema(parameter) for parameter in command.params],
    }
    if isinstance(command, click.Group):
        names = sorted(command.commands)
        result["subcommands"] = names
        if recursive:
            result["commands"] = [
                _command_schema(command.commands[name], f"{path} {name}".strip(), recursive=True)
                for name in names
                if not command.commands[name].hidden
            ]
    return result


def _resolve_command(root: click.Command, path_parts: tuple[str, ...]) -> tuple[click.Command, str]:
    command = root
    resolved = "outlabs-auth"
    for part in path_parts:
        if not isinstance(command, click.Group) or part not in command.commands:
            raise CliError(
                code="COMMAND_NOT_FOUND",
                message=f"Command path '{' '.join(path_parts)}' does not exist.",
                exit_code=EXIT_USAGE,
            )
        command = command.commands[part]
        resolved = f"{resolved} {part}"
    return command, resolved


@click.command("commands")
@click.argument("path_parts", nargs=-1)
@click.option("--recursive/--shallow", default=True, show_default=True)
@click.pass_context
def commands_schema(ctx: click.Context, path_parts: tuple[str, ...], recursive: bool):
    """Describe commands, options, types, defaults, and environment inputs."""

    root = ctx.find_root().command
    command, path = _resolve_command(root, path_parts)
    result = _command_schema(command, path, recursive=recursive)
    if isinstance(command, click.Group):
        paths = []

        def collect(item: dict[str, Any]) -> None:
            for child in item.get("commands", []):
                if child.get("commands"):
                    collect(child)
                else:
                    paths.append(child["path"])

        collect(result)
        text_output = "Available command paths:\n" + "\n".join(f"  {item}" for item in paths)
    else:
        text_output = f"{path}\n{command.help or ''}"
    emit_result("commands", result, text=text_output)


def register_schema_commands(root: click.Group) -> None:
    root.add_command(commands_schema)
