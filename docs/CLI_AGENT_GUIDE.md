# Driving OutlabsAuth with Coding Agents

OutlabsAuth exposes a versioned, introspectable CLI contract so an agent can
operate an auth deployment without scraping terminal prose or depending on the
optional admin UI.

## Invocation baseline

Use these global flags before the command name:

```bash
outlabs-auth --output json --non-interactive --profile production COMMAND ...
```

- Parse exactly one JSON document from stdout.
- Check both the process exit code and the envelope's `ok` field.
- Treat `result` as command-specific data and `meta` as request/resolution
  evidence.
- Never infer success from human text.
- Do not pass passwords, tokens, access codes, invitation tokens, or API keys
  as command-line values.

Stable exit categories are `0` success, `1` domain failure, `2` bad input or
configuration, `3` authentication/authorization, `4` transient remote
unavailability, `5` conflict or drift, and `6` partial batch failure. Retry
only when `error.retryable` is true. A partial failure requires inspection of
the returned completed and failed operation IDs before any retry.

## Discover before acting

The live command tree is the source of truth for installed CLI capabilities:

```bash
outlabs-auth --output json commands --recursive
outlabs-auth --output json commands integration-keys create --shallow
```

Each parameter reports its flags, type, choices, cardinality, default when
public, required state, and environment input. Inspect only the command path
you need to keep agent context compact.

Before a workflow, verify the target and server feature set:

```bash
outlabs-auth --output json context current
outlabs-auth --output json capabilities
outlabs-auth --output json whoami
```

Contexts contain no credential values. A stored human session is bound to the
exact profile, base URL, and API prefix. Environment credentials take
precedence over a stored session, which makes an explicit scoped API key the
recommended unattended-agent credential.

## Read, resolve, then mutate

Typed commands accept human references and return exact resolution evidence in
`meta`. Prefer email for users, canonical name for roles/permissions, slug for
entities, and unique name for principals/keys. If a reference is ambiguous,
the command exits `5` and returns candidate IDs; rerun with a UUID.

```bash
outlabs-auth --output json users get operator@example.com
outlabs-auth --output json users access-report operator@example.com
outlabs-auth --output json permissions explain reports:read \
  --user operator@example.com --entity engineering
```

Authority-changing commands require `--yes` in non-interactive mode. Resolve
and inspect the target first when the operation is not declarative.

## Least-privilege agent credentials

Use a non-human integration principal for durable automation. Scope it
explicitly to one entity or the platform, assign only bounded roles/scopes,
then write the one-time system key directly to an owner-only file:

```bash
outlabs-auth --output json --non-interactive integration-principals create \
  --entity engineering --name deploy-agent \
  --allowed-scope deployments:read --allowed-scope deployments:write \
  --role deployment-operator --yes

outlabs-auth --output json --non-interactive integration-keys create \
  deploy-agent --entity engineering --name production-deploy \
  --scope deployments:read --scope deployments:write \
  --secret-file ./production-deploy.key --yes
```

The secret-file destination is validated before remote creation or rotation.
The result contains `secret_written_to`, never the key. `--show-secret` exists
only for callers that deliberately need the one-time value in structured
stdout and can protect that channel.

For incident response, inventory and revoke any key anchored to an entity:

```bash
outlabs-auth --output json api-keys inventory --entity engineering --all
outlabs-auth --output json --non-interactive api-keys admin-revoke KEY_ID \
  --entity engineering --yes
```

## Prefer plan/apply for related changes

Use a declarative manifest when permissions, entities, roles, and memberships
must change together:

```bash
outlabs-auth --output json plan state.json --out state.plan.json
# Review target, summary, every operation, and destructive markers.
outlabs-auth --output json --non-interactive apply state.plan.json --yes
```

Add `--allow-delete` only after reviewing destructive operations. `apply`
validates target binding and all remote state hashes before its first write.
Exit `5` means the plan is stale and must be regenerated; exit `6` means some
writes completed and the returned operation ledger is now the recovery source
of truth.

## Advanced policy and troubleshooting

ABAC policy has typed subcommands under both roles and permissions:

```bash
outlabs-auth --output json roles condition-groups create operator \
  --operator OR --description "Office or VPN" --yes
outlabs-auth --output json roles conditions create operator \
  --attribute subject.department --operator in \
  --value-json '["engineering", "operations"]' --value-type list --yes
```

Use `users timeline` for complete user-centric audit/membership history and
`audit list` for cross-user searches. Session and key outputs are redacted.

`api request` is the last-resort forward-compatibility path for a mounted
endpoint not yet represented by a typed command. It accepts only a relative
path and bounded JSON input; every raw write needs confirmation:

```bash
outlabs-auth --output json api request GET custom-resource \
  --query page=1 --query limit=20
outlabs-auth --output json --non-interactive api request POST custom-resource \
  --from request.json --yes
```

Prefer typed commands whenever available: they add reference resolution,
secret handling, pagination, policy-aware prompts, and stable result shaping.

## Recovery checklist

1. On exit `2`, inspect `error.code`, `details`, and `hint`; do not retry
   unchanged input.
2. On exit `3`, verify `context current`, credential environment selection,
   session status, and server permissions.
3. On retryable exit `4`, use bounded exponential backoff. Do not blindly
   retry an unconfirmed raw write.
4. On exit `5`, resolve ambiguity with UUIDs or regenerate a drifted plan.
5. On exit `6`, reconcile completed operations before creating a new plan.

Manifest details are in [`CLI_MANIFEST.md`](./CLI_MANIFEST.md); the stable
envelope and secret model are in [`CLI_DESIGN.md`](./CLI_DESIGN.md).
