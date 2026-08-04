# Command Line

Operate an OutlabsAuth deployment without the optional admin UI. The CLI
covers local database lifecycle, authenticated remote administration, account
security, access-policy debugging, and repeatable automation for both people
and coding agents.

The executable is installed with the Python package:

```bash
pip install outlabs-auth
outlabs-auth --version
outlabs-auth --help
```

The installed command tree is always the source of truth. Use ordinary
`--help` when working interactively and the machine-readable `commands`
command when generating or validating an invocation.

---

## Choose the operating plane

The CLI deliberately separates two kinds of work:

| Plane | Use it for | Connection |
|---|---|---|
| **Local database** | Migrations, first boot, schema diagnosis, deterministic maintenance | Direct Postgres connection through `DATABASE_URL` |
| **Remote administration** | Users, roles, permissions, entities, memberships, keys, sessions, audit, and account operations | Authenticated requests to the host application's mounted OutlabsAuth API |

Remote administration never edits auth tables directly. It goes through the
HTTP API so the same authorization, validation, audit, and host policy apply
whether the caller is the CLI, the optional UI, or another client.

## Human quickstart

### 1. Save the target

Contexts store a base URL and API prefix, but never a password, bearer token,
or API-key value.

```bash
outlabs-auth context add production \
  --base-url https://api.example.com \
  --api-prefix /iam

outlabs-auth context current
```

Use `outlabs-auth context list` to see all targets and
`outlabs-auth context use NAME` to switch the default. Global `--profile NAME`
selects a context for one invocation without changing the default.

For local development, plain HTTP is accepted on loopback addresses. A remote
plain-HTTP target is rejected unless you deliberately pass `--allow-insecure`.

### 2. Sign in without exposing the password

The default is a hidden password prompt:

```bash
outlabs-auth auth login --email admin@example.com
```

For a pipe or password manager, use stdin instead of a secret-valued command
argument:

```bash
printf '%s\n' "$OUTLABS_AUTH_PASSWORD" | \
  outlabs-auth auth login --email admin@example.com --password-stdin
```

The refreshable session is stored separately from contexts in an owner-only
file and is bound to the exact profile, base URL, and API prefix. Check or
remove it with:

```bash
outlabs-auth auth status
outlabs-auth auth logout
```

### 3. Verify the target before changing it

```bash
outlabs-auth capabilities
outlabs-auth whoami
```

`capabilities` reports the mounted preset and available server features.
`whoami` confirms the authenticated identity and the exact resolved target.

### 4. Inspect and administer

```bash
outlabs-auth users list --status active --all
outlabs-auth users get analyst@example.com
outlabs-auth users access-report analyst@example.com
outlabs-auth permissions explain reports:read \
  --user analyst@example.com --entity engineering
```

Most typed commands accept either a UUID or an unambiguous human reference:
email for users, canonical name for roles and permissions, and slug or unique
name for entities. Ambiguous references fail with candidate IDs instead of
guessing.

## What can be managed

| Command group | Main jobs |
|---|---|
| `db` | Schema initialization, migrations, revision inspection, seed data, bootstrap, and guarded teardown |
| `ops` | Read-only diagnosis and deterministic maintenance |
| `account` | Inspect and update the signed-in account, change password, verify phone, unlink social accounts |
| `auth` | Login, refresh, logout, registration, invitations, password reset, magic links, and access codes |
| `users` | Create, update, suspend, ban, restore, delete, assign roles, inspect access, and view timelines |
| `permissions` | Catalog CRUD, current grants, checks, explanations, and ABAC conditions |
| `roles` | Role CRUD, permission grants, entity scope, and ABAC conditions |
| `entities` | Enterprise hierarchy CRUD, children, descendants, paths, and moves |
| `memberships` | Add, update, list, and remove entity membership and membership roles |
| `api-keys` | Personal keys plus entity-wide inventory and revocation |
| `integration-principals` | Bounded non-human identities with allowed scopes and roles |
| `integration-keys` | One-time system keys owned by integration principals |
| `sessions` | List and revoke refresh-token sessions |
| `audit` | Search cross-user audit events by actor, subject, entity, category, and time |
| `config` | Inspect and update mounted entity-type configuration |
| `plan` / `apply` | Review and apply declarative permissions, entities, roles, and memberships |
| `api request` | Guarded relative-path fallback for a newly mounted endpoint without a typed command |

Ask the installed CLI for exact options:

```bash
outlabs-auth users --help
outlabs-auth memberships add --help
outlabs-auth integration-keys create --help
```

## Common administration workflows

### Create a permission, role, and membership

```bash
outlabs-auth permissions create \
  --name reports:read \
  --display-name "Read reports"

outlabs-auth roles create \
  --name report-reader \
  --display-name "Report reader" \
  --permission reports:read

outlabs-auth memberships add \
  --user analyst@example.com \
  --entity engineering \
  --role report-reader \
  --reason "Reporting responsibility" \
  --yes
```

Access-granting and other authority-sensitive operations ask for confirmation.
In `--non-interactive` mode they fail unless the command also includes `--yes`.

### Suspend a user and revoke sessions

```bash
outlabs-auth users set-status analyst@example.com suspended \
  --reason "Security review" \
  --yes

outlabs-auth sessions revoke-all \
  --user analyst@example.com \
  --yes
```

Use `users timeline USER` for user-centric access and audit history, or
`audit list` for cross-user searches:

```bash
outlabs-auth users timeline analyst@example.com
outlabs-auth audit list --actor admin@example.com --entity engineering --all
```

### Work with an enterprise hierarchy

```bash
outlabs-auth entities create \
  --name Engineering \
  --slug engineering \
  --class structural

outlabs-auth entities create \
  --name Platform \
  --slug platform \
  --class structural \
  --parent engineering

outlabs-auth entities children engineering
outlabs-auth entities path platform
```

### Create a personal API key safely

API-key secrets are returned once. Creation and rotation require an explicit
secret destination so a successful command cannot silently lose the key.

```bash
outlabs-auth api-keys grantable-scopes --entity engineering

outlabs-auth api-keys create \
  --name reporting-export \
  --scope reports:read \
  --entity engineering \
  --secret-file ./reporting-export.key \
  --yes
```

The CLI validates the destination before the remote write and creates the file
with mode `0600`. `--show-secret` is available only when the caller explicitly
wants the one-time value in command output and can protect that channel.

### Create a least-privilege identity for an agent

Durable unattended automation should use a non-human integration principal
and a narrowly scoped system key instead of a human session:

```bash
outlabs-auth --output json --non-interactive \
  integration-principals create \
  --entity engineering \
  --name deploy-agent \
  --allowed-scope deployments:read \
  --allowed-scope deployments:write \
  --role deployment-operator \
  --yes

outlabs-auth --output json --non-interactive \
  integration-keys create deploy-agent \
  --entity engineering \
  --name production-deploy \
  --scope deployments:read \
  --scope deployments:write \
  --secret-file ./production-deploy.key \
  --yes
```

Store the resulting key in the automation platform's secret store. Configure
the target to use API-key transport and expose the value only at invocation
time:

```bash
outlabs-auth context add production-agent \
  --base-url https://api.example.com \
  --api-prefix /iam \
  --credential-type api-key

export OUTLABS_AUTH_API_KEY='secret-from-your-secret-store'
outlabs-auth --profile production-agent --output json whoami
```

## Local database operations

Set a direct asyncpg URL, then use the established top-level commands or their
namespaced `db` and `ops` forms:

```bash
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@db/app
export OUTLABS_AUTH_SCHEMA=outlabs_auth

outlabs-auth doctor
outlabs-auth migrate
outlabs-auth seed-system
outlabs-auth bootstrap-admin --email admin@example.com
outlabs-auth ops maintenance
```

`doctor` is read-only. `bootstrap` is an idempotent first-boot orchestrator that
classifies the schema, migrates it, seeds system data, and optionally creates
the initial admin. It aborts on unsafe drift instead of guessing.

For production, run migrations once in a prestart or release job before
starting multiple workers. See [Deployment](./08-Deployment.md).
Run `ops maintenance` from exactly one external scheduler per database and
environment; the complete ownership and failure contract is in
[Background Maintenance](./09-Background-Maintenance.md).

## Coding-agent and automation contract

Use global flags before the command name:

```bash
outlabs-auth \
  --output json \
  --non-interactive \
  --profile production-agent \
  COMMAND ...
```

This mode writes exactly one JSON document to stdout for both success and
failure. Check the process exit code and the envelope's `ok` field; never infer
success from terminal prose.

```json
{
  "schema_version": "outlabs-auth.cli/v1",
  "ok": true,
  "command": "users.list",
  "result": {},
  "warnings": []
}
```

Failures contain a stable `error.code`, human message, structured `details`, a
`retryable` boolean, and usually a recovery `hint`.

| Exit | Meaning | Automation behavior |
|---:|---|---|
| `0` | Success, including an idempotent no-op | Continue |
| `1` | Domain or operation failure | Inspect the error; do not assume a retry helps |
| `2` | Invalid input or configuration | Correct the invocation or environment |
| `3` | Authentication or authorization failure | Verify context, credential, session, and grants |
| `4` | Timeout, rate limit, or remote unavailability | Retry only when `error.retryable` is true |
| `5` | Conflict, ambiguous reference, or state drift | Resolve with a UUID or regenerate the plan |
| `6` | Partial batch failure | Reconcile completed and failed operation IDs first |

### Discover before acting

Agents should inspect the installed command schema instead of relying on a
memorized command list:

```bash
outlabs-auth --output json commands --recursive
outlabs-auth --output json commands memberships add --shallow
```

Each option reports its flags, type, choices, cardinality, default when public,
required state, and environment input. Prefer a narrow path to keep context and
tool output small.

A safe agent workflow is:

1. Run `context current`, `capabilities`, and `whoami` in JSON mode.
2. Resolve and read the target resource before a mutation.
3. Prefer typed commands and unambiguous references.
4. Add `--yes` only after validating the target and intended authority change.
5. Parse the returned `meta` evidence and stable error fields.
6. Retry only when explicitly marked retryable.

## Declarative plan and apply

Use a manifest when permissions, entities, roles, and memberships must change
together or be reviewed before execution:

```json
{
  "api_version": "outlabs-auth.state/v1alpha1",
  "kind": "OutlabsAuthState",
  "spec": {
    "permissions": [],
    "entities": [],
    "roles": [],
    "memberships": []
  }
}
```

```bash
outlabs-auth --output json plan state.json --out state.plan.json
# Review the target, summary, operation list, and destructive markers.
outlabs-auth --output json --non-interactive \
  apply state.plan.json --yes
```

Plans are saved owner-only, bound to the target, dependency ordered, and
contain hashes of the remote state observed during planning. `apply` validates
every precondition before its first write. Add `--allow-delete` only after
reviewing operations marked destructive.

Manifest items omitted from the file are left alone. An explicit
`"state": "absent"` requests archival or revocation; the manifest is not an
authoritative delete-everything-not-listed sync.

## Forward-compatible API fallback

Use `api request` only when the host exposes an endpoint that the installed CLI
does not yet cover with a typed command:

```bash
outlabs-auth --output json api request GET custom-resource \
  --query page=1 --query limit=20

outlabs-auth --output json --non-interactive \
  api request POST custom-resource --from request.json --yes
```

The path must be relative, JSON input is bounded, and every raw write requires
confirmation. Typed commands remain preferable because they add reference
resolution, secret handling, pagination, policy-aware prompts, and stable
result shaping.

## Configuration reference

The most commonly used variables are:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Direct Postgres URL for local database commands |
| `OUTLABS_AUTH_SCHEMA` | Database schema for local operations |
| `OUTLABS_AUTH_CONFIG` | Alternate non-secret context file |
| `OUTLABS_AUTH_CREDENTIALS` | Alternate owner-only human session file |
| `OUTLABS_AUTH_PROFILE` | Context selected for an invocation |
| `OUTLABS_AUTH_TOKEN` | Default remote bearer credential |
| `OUTLABS_AUTH_API_KEY` | Default remote API-key credential |
| `OUTLABS_AUTH_OUTPUT` | Default output mode: `text` or `json` |
| `OUTLABS_AUTH_NON_INTERACTIVE` | Disable all prompts |
| `OUTLABS_AUTH_TIMEOUT` | Remote timeout in seconds |
| `OUTLABS_AUTH_DEBUG` | Include tracebacks for unexpected CLI failures |

Global flags can override the active profile, target, credential transport,
credential environment-variable name, timeout, schema, and output mode for one
invocation. The complete environment table is in
[Configuration](./03-Configuration.md#cli-environment).

## Troubleshooting

| Symptom | Check |
|---|---|
| Wrong server or prefix | `outlabs-auth context current`, then confirm `base_url` and `api_prefix` |
| Missing credential | `outlabs-auth auth status` for bearer sessions, or confirm the configured credential environment variable |
| `401` after a context change | Login again; stored sessions are intentionally target-bound |
| `403` | `whoami`, `users access-report`, and `permissions explain` |
| Feature or route missing | `capabilities`, then verify the host mounted the required router |
| Ambiguous name | Repeat the command with the candidate UUID returned in the error |
| Stale plan | Generate a new `plan`; do not force an old plan through drift |
| Partial apply | Use the returned operation ledger before retrying or replanning |
| Database first-boot uncertainty | Run read-only `doctor` before `bootstrap` or `migrate` |

## Related

- [Configuration](./03-Configuration.md)
- [Deployment](./08-Deployment.md)
- [Roles & Permissions](./25-Roles-and-Permissions.md)
- [Entities](./51-Entities.md)
- [Entity Memberships](./54-Entity-Memberships.md)
- [API Keys](./50-API-Key-Host-Integration.md)
- [Maintainer CLI contract](../docs/CLI_DESIGN.md)
- [Detailed coding-agent guide](../docs/CLI_AGENT_GUIDE.md)
- [Declarative manifest contract](../docs/CLI_MANIFEST.md)
