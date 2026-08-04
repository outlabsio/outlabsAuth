# OutlabsAuth CLI Design

**Status:** Implemented foundation; expanding resource-specific coverage
**Contract version:** `outlabs-auth.cli/v1`

The CLI is a first-class OutlabsAuth control surface. A complete deployment
must be operable without the optional admin UI, by both people and unattended
automation.

## Two operating planes

1. **Local operations** own schema lifecycle and deterministic maintenance:
   migrations, bootstrap, inspection, and scheduled maintenance.
2. **Remote administration** calls the host's mounted OutlabsAuth HTTP API:
   users, roles, permissions, entities, memberships, credentials, sessions,
   audit, and configuration.

Remote administration must not write directly to Postgres. The HTTP boundary
preserves authentication, authorization, audit events, host policy, and remote
deployment support.

## Stable automation contract

Global `--output json` returns one JSON document on stdout for every success or
failure. Progress and human diagnostics never contaminate structured stdout.

Success envelope:

```json
{
  "schema_version": "outlabs-auth.cli/v1",
  "ok": true,
  "command": "users.list",
  "result": {},
  "warnings": []
}
```

Failure envelope:

```json
{
  "schema_version": "outlabs-auth.cli/v1",
  "ok": false,
  "command": "users.list",
  "error": {
    "code": "AUTH_CREDENTIAL_MISSING",
    "message": "Authentication token is not configured.",
    "details": {},
    "retryable": false,
    "hint": "Export the token environment variable configured by the active context."
  }
}
```

Exit codes are stable:

| Code | Meaning |
|---:|---|
| 0 | success, including an idempotent no-op |
| 1 | operation or domain failure |
| 2 | invalid invocation or configuration |
| 3 | authentication or authorization failure |
| 4 | timeout, rate limit, or remote unavailability |
| 5 | conflict or detected state drift |
| 6 | partial batch failure |

## Contexts and secrets

Contexts store only non-secret target metadata: base URL, API prefix, optional
application profile, credential type (`bearer` or `api_key`), and the **name**
of the environment variable holding the credential. Tokens, API keys, and
passwords are never written to the context file.

Bearer credentials default to `OUTLABS_AUTH_TOKEN`; API keys default to
`OUTLABS_AUTH_API_KEY`. Coding agents should prefer a scoped API key when the
host policy allows it.

Interactive bearer sessions are stored separately under the platform state
directory (or `OUTLABS_AUTH_CREDENTIALS`). The file uses owner-only
permissions, its default directory is created owner-only, writes are atomic,
and each session is bound to the exact profile, base URL, and API prefix. A
context changed to another host cannot receive the old host's token. Expiring
sessions refresh automatically; one unauthorized response triggers at most one
refresh-and-retry.

Passwords, reset tokens, invitation tokens, magic-link tokens, and access
codes are accepted from environment variables, stdin, or hidden prompts—not
as secret-valued command-line options.

API-key creation and rotation require an explicit one-time secret sink:
`--secret-file` writes mode `0600`, while `--show-secret` deliberately exposes
the value to structured stdout. Without one of these choices, no key is
created.

## Agent discovery and forward compatibility

`outlabs-auth --output json commands` describes the live Click command tree,
including option flags, types, choices, defaults, required fields, and
environment inputs. Agents should inspect a narrow path when possible, for
example `commands roles create --shallow`.

Purpose-built groups cover authentication, self-service accounts, users and
access reports, roles, permissions, ABAC policy, entities, memberships,
personal and entity-wide API-key operations, integration principals/system
keys, sessions, audit, and entity-type config. The guarded `api request`
command is a forward-compatible escape hatch for mounted endpoints not yet
represented by a typed command. It accepts only relative paths, bounded JSON
input, and requires explicit confirmation for every raw write.

Agent workflow and recovery guidance: [`CLI_AGENT_GUIDE.md`](./CLI_AGENT_GUIDE.md).

## Declarative workflow

`plan` and `apply` implement a two-phase state workflow for permissions,
entities, roles, and memberships. Plans are target-bound, saved mode `0600`,
dependency ordered, and include drift hashes. All preconditions are validated
before the first write. Details: [`CLI_MANIFEST.md`](./CLI_MANIFEST.md).

## Compatibility

Published commands such as `outlabs-auth migrate`, `doctor`, and `bootstrap`
remain supported. Namespaced `db` and `ops` aliases can be added without
removing the established spellings.

The legacy per-command `--format json` shape remains available during the
transition. The global `--output json` flag is the versioned envelope used by
new automation.
