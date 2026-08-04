# OutlabsAuth CLI Design

**Status:** Implementing  
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
host policy allows it. Future interactive login support may use an OS
credential store; it must not put passwords or tokens on the process command
line.

## Compatibility

Published commands such as `outlabs-auth migrate`, `doctor`, and `bootstrap`
remain supported. Namespaced `db` and `ops` aliases can be added without
removing the established spellings.

The legacy per-command `--format json` shape remains available during the
transition. The global `--output json` flag is the versioned envelope used by
new automation.
