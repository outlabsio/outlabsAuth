# Declarative CLI State

**Manifest version:** `outlabs-auth.state/v1alpha1`
**Plan version:** `outlabs-auth.plan/v1alpha1`

The CLI can compare a reviewed JSON state manifest with a mounted OutlabsAuth
API, save the exact operations as a plan, and apply that plan only if the
target and every remote precondition still match.

```bash
outlabs-auth --output json plan state.json --out state.plan.json
outlabs-auth --output json --non-interactive apply state.plan.json --yes
```

If the plan contains an absent-state operation, application additionally
requires `--allow-delete`. Any drift fails with exit code `5` before the first
write. If a later request fails after earlier operations succeeded, the CLI
returns exit code `6` and lists both completed and failed operation IDs.

## Manifest shape

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

Each item defaults to `"state": "present"`. Use `"state": "absent"` to
archive a permission, role, or entity, or to revoke a membership. The
manifest is intentionally non-authoritative outside the items it names: it
does not delete remote resources merely because they are omitted.

Identity and references are human-readable:

| Resource | Identity | Supported references |
|---|---|---|
| Permission | `name` | permission names in role `permissions` |
| Entity | `slug` | `parent`, role `root_entity` / `scope_entity` |
| Role | `name` | membership `roles` |
| Membership | `user` + `entity` | exact user email + entity slug |

Entity creation is dependency-ordered, so a child may reference a parent
created by the same plan. Role and membership references are resolved after
their dependencies are created. Cycles, missing references, duplicate
identities, and unknown fields are rejected during planning.

See [`examples/cli/state.example.json`](../examples/cli/state.example.json) for
a complete example.

## Review and safety model

- `plan` is read-only and returns `changed: false`.
- Saved plans are mode `0600` and bound to profile, base URL, and API prefix.
- Each operation records a hash of the state observed during planning.
- `apply` re-reads all involved resources and validates every hash before the
  first mutation.
- Authority dependencies are ordered: permissions → entities → roles →
  memberships. Explicit removals run in reverse order.
- The alpha version is rejected rather than silently upgraded when the
  manifest or plan contract changes.
