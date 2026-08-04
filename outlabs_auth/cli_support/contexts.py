"""Non-secret remote target profiles for the OutlabsAuth CLI."""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from outlabs_auth.cli_support.runtime import CliError, EXIT_CONFLICT, EXIT_USAGE

_PROFILE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_ENV_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def default_config_path() -> Path:
    explicit = os.environ.get("OUTLABS_AUTH_CONFIG")
    if explicit:
        return Path(explicit).expanduser()
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".config"
    return base / "outlabs-auth" / "config.json"


def normalize_api_prefix(value: str) -> str:
    stripped = value.strip()
    if not stripped or stripped == "/":
        return ""
    if not stripped.startswith("/"):
        stripped = f"/{stripped}"
    return stripped.rstrip("/")


def normalize_base_url(value: str, *, allow_insecure: bool = False) -> str:
    stripped = value.strip().rstrip("/")
    parsed = urlparse(stripped)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise CliError(
            code="INVALID_BASE_URL",
            message="Base URL must be an absolute http:// or https:// URL.",
            exit_code=EXIT_USAGE,
        )
    if parsed.username or parsed.password:
        raise CliError(
            code="INVALID_BASE_URL",
            message="Base URL must not contain credentials.",
            exit_code=EXIT_USAGE,
            hint="Provide authentication through the credential environment configured by the active context.",
        )
    if parsed.query or parsed.fragment:
        raise CliError(
            code="INVALID_BASE_URL",
            message="Base URL must not contain query parameters or a fragment.",
            exit_code=EXIT_USAGE,
            hint="Put only the API host and optional path in the context base URL.",
        )
    hostname = (parsed.hostname or "").lower()
    local = hostname in {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme == "http" and not local and not allow_insecure:
        raise CliError(
            code="INSECURE_BASE_URL",
            message="Plain HTTP is only allowed for local targets by default.",
            exit_code=EXIT_USAGE,
            hint="Use HTTPS or pass --allow-insecure when the transport is protected elsewhere.",
        )
    return stripped


@dataclass(frozen=True)
class ContextProfile:
    name: str
    base_url: str
    api_prefix: str = "/v1"
    app: Optional[str] = None
    credential_type: str = "bearer"
    credential_env: str = "OUTLABS_AUTH_TOKEN"

    @classmethod
    def from_dict(cls, name: str, raw: dict[str, Any]) -> "ContextProfile":
        credential_type = str(raw.get("credential_type", "bearer"))
        if credential_type not in {"bearer", "api_key"}:
            raise ValueError(f"Invalid credential_type for context '{name}'")
        default_env = "OUTLABS_AUTH_API_KEY" if credential_type == "api_key" else "OUTLABS_AUTH_TOKEN"
        # token_env is accepted for configs written by the first development
        # iteration of the context store; new files use credential_env.
        credential_env = str(raw.get("credential_env", raw.get("token_env", default_env)))
        if not _ENV_RE.fullmatch(credential_env):
            raise ValueError(f"Invalid credential_env for context '{name}'")
        return cls(
            name=name,
            base_url=normalize_base_url(str(raw["base_url"]), allow_insecure=True),
            api_prefix=normalize_api_prefix(str(raw.get("api_prefix", "/v1"))),
            app=str(raw["app"]) if raw.get("app") is not None else None,
            credential_type=credential_type,
            credential_env=credential_env,
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("name")
        return payload


class ContextStore:
    """Atomic JSON-backed context store. Authentication secrets are never stored."""

    def __init__(self, path: Optional[Path] = None):
        self.path = path or default_config_path()
        self.active: Optional[str] = None
        self.contexts: dict[str, ContextProfile] = {}

    def load(self) -> "ContextStore":
        if not self.path.exists():
            return self
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            contexts = raw.get("contexts", {})
            if not isinstance(contexts, dict):
                raise ValueError("'contexts' must be an object")
            parsed_contexts: dict[str, ContextProfile] = {}
            for name, value in contexts.items():
                if not isinstance(value, dict):
                    raise ValueError(f"Context '{name}' must be an object")
                parsed_contexts[str(name)] = ContextProfile.from_dict(str(name), value)
            self.contexts = parsed_contexts
            active = raw.get("active")
            self.active = str(active) if active is not None else None
            if self.active and self.active not in self.contexts:
                raise ValueError(f"Active context '{self.active}' does not exist")
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise CliError(
                code="INVALID_CONTEXT_CONFIG",
                message=f"Cannot load CLI context configuration: {type(exc).__name__}",
                exit_code=EXIT_USAGE,
                details={"path": str(self.path)},
                hint="Repair the file or point OUTLABS_AUTH_CONFIG at a valid configuration.",
            ) from exc
        return self

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "active": self.active,
            "contexts": {name: profile.to_dict() for name, profile in sorted(self.contexts.items())},
        }
        fd, temp_name = tempfile.mkstemp(prefix=".config-", suffix=".json", dir=self.path.parent)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
                handle.write("\n")
            os.replace(temp_name, self.path)
        except OSError as exc:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
            raise CliError(
                code="CONTEXT_WRITE_FAILED",
                message="Cannot write CLI context configuration.",
                exit_code=EXIT_USAGE,
                details={"path": str(self.path), "exception_type": type(exc).__name__},
                hint="Check that the configuration directory exists and is writable.",
            ) from exc

    def add(self, profile: ContextProfile, *, activate: bool, force: bool) -> None:
        if not _PROFILE_RE.fullmatch(profile.name):
            raise CliError(
                code="INVALID_CONTEXT_NAME",
                message="Context names may contain letters, digits, dots, dashes, and underscores.",
                exit_code=EXIT_USAGE,
            )
        if profile.name in self.contexts and not force:
            raise CliError(
                code="CONTEXT_EXISTS",
                message=f"Context '{profile.name}' already exists.",
                exit_code=EXIT_CONFLICT,
                hint="Pass --force to replace it.",
            )
        self.contexts[profile.name] = profile
        if activate or self.active is None:
            self.active = profile.name
        self.save()

    def use(self, name: str) -> ContextProfile:
        profile = self.get(name)
        self.active = name
        self.save()
        return profile

    def get(self, name: Optional[str] = None) -> ContextProfile:
        selected = name or self.active
        if not selected:
            raise CliError(
                code="NO_ACTIVE_CONTEXT",
                message="No remote context is active.",
                exit_code=EXIT_USAGE,
                hint="Run: outlabs-auth context add NAME --base-url URL",
            )
        profile = self.contexts.get(selected)
        if profile is None:
            raise CliError(
                code="CONTEXT_NOT_FOUND",
                message=f"Context '{selected}' does not exist.",
                exit_code=EXIT_USAGE,
                details={"available": sorted(self.contexts)},
            )
        return profile
