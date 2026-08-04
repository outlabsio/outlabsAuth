"""Secret input helpers that never accept or echo secret command-line values."""

from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Optional

import click

from outlabs_auth.cli_support.runtime import CliError, EXIT_USAGE, get_runtime

_ENV_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def read_secret(
    *,
    from_stdin: bool,
    env_name: str,
    prompt: str,
    missing_code: str,
    confirmation_prompt: bool = False,
) -> str:
    """Read a secret from stdin, an environment variable, or a hidden TTY prompt."""

    if not _ENV_RE.fullmatch(env_name):
        raise CliError(
            code="INVALID_SECRET_ENV",
            message="Secret environment variable names must use shell identifier syntax.",
            exit_code=EXIT_USAGE,
        )
    environment_value = os.environ.get(env_name)
    if from_stdin and environment_value:
        raise CliError(
            code="CONFLICTING_SECRET_INPUT",
            message=f"Use either the stdin flag or {env_name}, not both.",
            exit_code=EXIT_USAGE,
        )
    if from_stdin:
        value = sys.stdin.readline().rstrip("\r\n")
    elif environment_value:
        value = environment_value
    else:
        runtime = get_runtime()
        if runtime.non_interactive or not sys.stdin.isatty():
            raise CliError(
                code=missing_code,
                message=f"{prompt} is required.",
                exit_code=EXIT_USAGE,
                hint=f"Set {env_name} or use the command's stdin secret flag.",
            )
        value = click.prompt(
            prompt,
            hide_input=True,
            confirmation_prompt=confirmation_prompt,
        )
    if not value:
        raise CliError(
            code=missing_code,
            message=f"{prompt} must not be empty.",
            exit_code=EXIT_USAGE,
        )
    return value


def validate_secret_file_target(path_value: str, *, force: bool = False) -> Path:
    """Validate and probe a secret sink before a remote one-time value exists."""

    path = Path(path_value).expanduser()
    if path.is_symlink():
        raise CliError(
            code="INSECURE_SECRET_FILE",
            message="Secret output files must not be symbolic links.",
            exit_code=EXIT_USAGE,
            details={"path": str(path)},
        )
    if path.exists() and not force:
        raise CliError(
            code="SECRET_FILE_EXISTS",
            message="The secret output file already exists.",
            exit_code=EXIT_USAGE,
            details={"path": str(path)},
            hint="Choose another path or pass --force-secret-file after reviewing the target.",
        )
    if path.exists() and not path.is_file():
        raise CliError(
            code="INVALID_SECRET_FILE",
            message="The secret output path must be a regular file.",
            exit_code=EXIT_USAGE,
            details={"path": str(path)},
        )
    parent_existed = path.parent.exists()
    temp_name: Optional[str] = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not parent_existed and os.name != "nt":
            os.chmod(path.parent, 0o700)
        if not path.parent.is_dir():
            raise OSError("secret output parent is not a directory")
        fd, temp_name = tempfile.mkstemp(prefix=".secret-probe-", dir=path.parent)
        os.close(fd)
        os.unlink(temp_name)
        temp_name = None
        return path
    except OSError as exc:
        raise CliError(
            code="SECRET_FILE_WRITE_FAILED",
            message="Cannot write the secret output file.",
            exit_code=EXIT_USAGE,
            details={"path": str(path), "exception_type": type(exc).__name__},
        ) from exc
    finally:
        if temp_name:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass


def write_secret_file(path_value: str, secret: str, *, force: bool = False) -> Path:
    """Atomically write one secret to an owner-only file."""

    path = validate_secret_file_target(path_value, force=force)
    temp_name: Optional[str] = None
    try:
        fd, temp_name = tempfile.mkstemp(prefix=".secret-", dir=path.parent)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(secret)
            handle.write("\n")
        os.replace(temp_name, path)
        temp_name = None
        return path
    except OSError as exc:
        raise CliError(
            code="SECRET_FILE_WRITE_FAILED",
            message="Cannot write the secret output file.",
            exit_code=EXIT_USAGE,
            details={"path": str(path), "exception_type": type(exc).__name__},
        ) from exc
    finally:
        if temp_name:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
