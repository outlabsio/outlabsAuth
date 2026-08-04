"""Target-bound local session storage for interactive CLI authentication."""

from __future__ import annotations

import json
import os
import stat
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

from outlabs_auth.cli_support.runtime import CliError, EXIT_AUTH, EXIT_USAGE


def default_credentials_path() -> Path:
    """Return the secret store path without mixing it into context config."""

    explicit = os.environ.get("OUTLABS_AUTH_CREDENTIALS")
    if explicit:
        return Path(explicit).expanduser()
    xdg = os.environ.get("XDG_STATE_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".local" / "state"
    return base / "outlabs-auth" / "credentials.json"


@dataclass(frozen=True)
class StoredSession:
    """A refreshable browser-equivalent session bound to one exact API target."""

    profile: str
    base_url: str
    api_prefix: str
    access_token: str
    refresh_token: str
    expires_at: float
    created_at: float
    email: Optional[str] = None
    app: Optional[str] = None

    @classmethod
    def from_dict(cls, profile: str, raw: dict[str, Any]) -> "StoredSession":
        required_strings = ("base_url", "api_prefix", "access_token", "refresh_token")
        values: dict[str, str] = {}
        for name in required_strings:
            value = raw.get(name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"Session '{profile}' has an invalid {name}")
            values[name] = value
        expires_at = float(raw["expires_at"])
        created_at = float(raw["created_at"])
        return cls(
            profile=profile,
            base_url=values["base_url"],
            api_prefix=values["api_prefix"],
            access_token=values["access_token"],
            refresh_token=values["refresh_token"],
            expires_at=expires_at,
            created_at=created_at,
            email=str(raw["email"]) if raw.get("email") is not None else None,
            app=str(raw["app"]) if raw.get("app") is not None else None,
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("profile")
        return payload

    def expires_within(self, seconds: float) -> bool:
        return self.expires_at <= time.time() + seconds

    def public_dict(self) -> dict[str, Any]:
        """Return status metadata that is safe for logs and JSON output."""

        return {
            "profile": self.profile,
            "base_url": self.base_url,
            "api_prefix": self.api_prefix,
            "email": self.email,
            "app": self.app,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "expired": self.expires_within(0),
            "refreshable": bool(self.refresh_token),
        }


class CredentialStore:
    """Atomic, permission-checked storage for refreshable CLI sessions."""

    def __init__(self, path: Optional[Path] = None):
        self.path = path or default_credentials_path()
        self.sessions: dict[str, StoredSession] = {}

    def _reject_symlink(self) -> None:
        if self.path.is_symlink():
            raise CliError(
                code="INSECURE_CREDENTIAL_STORE",
                message="The CLI credential store must not be a symbolic link.",
                exit_code=EXIT_USAGE,
                details={"path": str(self.path)},
            )

    def _check_permissions(self) -> None:
        if os.name == "nt" or not self.path.exists():
            return
        mode = stat.S_IMODE(self.path.stat().st_mode)
        if mode & 0o077:
            raise CliError(
                code="INSECURE_CREDENTIAL_STORE",
                message="The CLI credential store is readable or writable by other users.",
                exit_code=EXIT_USAGE,
                details={"path": str(self.path), "mode": oct(mode)},
                hint=f"Run: chmod 600 {self.path}",
            )

    def load(self) -> "CredentialStore":
        self._reject_symlink()
        if not self.path.exists():
            return self
        self._check_permissions()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            sessions = raw.get("sessions", {})
            if not isinstance(sessions, dict):
                raise ValueError("'sessions' must be an object")
            parsed: dict[str, StoredSession] = {}
            for profile, value in sessions.items():
                if not isinstance(value, dict):
                    raise ValueError(f"Session '{profile}' must be an object")
                parsed[str(profile)] = StoredSession.from_dict(str(profile), value)
            self.sessions = parsed
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise CliError(
                code="INVALID_CREDENTIAL_STORE",
                message=f"Cannot load CLI credentials: {type(exc).__name__}",
                exit_code=EXIT_USAGE,
                details={"path": str(self.path)},
                hint="Repair or remove the credential file, then sign in again.",
            ) from exc
        return self

    def save(self) -> None:
        self._reject_symlink()
        try:
            parent_existed = self.path.parent.exists()
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if not parent_existed and os.name != "nt":
                os.chmod(self.path.parent, 0o700)
            payload = {
                "version": 1,
                "sessions": {name: session.to_dict() for name, session in sorted(self.sessions.items())},
            }
            fd, temp_name = tempfile.mkstemp(prefix=".credentials-", suffix=".json", dir=self.path.parent)
            try:
                os.fchmod(fd, 0o600)
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(payload, handle, indent=2)
                    handle.write("\n")
                os.replace(temp_name, self.path)
            except BaseException:
                try:
                    os.unlink(temp_name)
                except FileNotFoundError:
                    pass
                raise
        except CliError:
            raise
        except OSError as exc:
            raise CliError(
                code="CREDENTIAL_STORE_WRITE_FAILED",
                message="Cannot write CLI credentials.",
                exit_code=EXIT_USAGE,
                details={"path": str(self.path), "exception_type": type(exc).__name__},
                hint="Check that the state directory exists and is writable.",
            ) from exc

    def put(self, session: StoredSession) -> None:
        self.sessions[session.profile] = session
        self.save()

    def get(
        self,
        profile: str,
        *,
        base_url: Optional[str] = None,
        api_prefix: Optional[str] = None,
        required: bool = False,
    ) -> Optional[StoredSession]:
        session = self.sessions.get(profile)
        if session is None:
            if required:
                raise CliError(
                    code="STORED_SESSION_MISSING",
                    message=f"No stored CLI session exists for context '{profile}'.",
                    exit_code=EXIT_AUTH,
                    hint="Run: outlabs-auth auth login --email USER@example.com",
                )
            return None
        if (base_url is not None and session.base_url != base_url) or (
            api_prefix is not None and session.api_prefix != api_prefix
        ):
            raise CliError(
                code="CREDENTIAL_TARGET_MISMATCH",
                message="Stored credentials are bound to a different API target.",
                exit_code=EXIT_AUTH,
                details={
                    "profile": profile,
                    "stored_target": f"{session.base_url}{session.api_prefix}",
                    "requested_target": f"{base_url or ''}{api_prefix or ''}",
                },
                hint="Sign in again for this context; the existing token was not sent.",
            )
        return session

    def delete(self, profile: str) -> bool:
        removed = self.sessions.pop(profile, None) is not None
        if removed:
            self.save()
        return removed
