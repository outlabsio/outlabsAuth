"""Shared runtime infrastructure for the OutlabsAuth command-line interface."""

from outlabs_auth.cli_support.client import RemoteClient, RemoteTarget, resolve_remote_target
from outlabs_auth.cli_support.contexts import ContextProfile, ContextStore
from outlabs_auth.cli_support.credentials import CredentialStore, StoredSession
from outlabs_auth.cli_support.runtime import (
    CLI_SCHEMA_VERSION,
    AgentFriendlyGroup,
    CliError,
    CliRuntime,
    emit_progress,
    emit_result,
    effective_output,
    get_runtime,
    require_confirmation,
)

__all__ = [
    "CLI_SCHEMA_VERSION",
    "AgentFriendlyGroup",
    "CliError",
    "CliRuntime",
    "ContextProfile",
    "ContextStore",
    "CredentialStore",
    "RemoteClient",
    "RemoteTarget",
    "StoredSession",
    "emit_progress",
    "emit_result",
    "effective_output",
    "get_runtime",
    "require_confirmation",
    "resolve_remote_target",
]
