# ABAC (Attribute-Based Access Control)

> **Handbook** · Opt-in attribute conditions on top of RBAC.  
> Part of the [OutlabsAuth Handbook](./README.md). Related:
> [Configuration](./03-Configuration.md) ·
> [Core Authorization Concepts](./13-Core-Authorization-Concepts.md) ·
> [Roles & Permissions](./25-Roles-and-Permissions.md).

ABAC adds **conditions** (attribute + operator + value) to roles and/or
permissions. At check time, RBAC must still grant the permission **and**
conditions must pass against a context (`user`, `resource`, `env`, `time`).

---

## Enable

| Surface | Behavior |
|---------|----------|
| `EnterpriseRBAC(..., enable_abac=True)` | Opt-in; **default `False`** |
| `OutlabsAuth` / `AuthConfig.enable_abac` | Same flag |
| `SimpleRBAC` | **Forced off** |

```python
auth = EnterpriseRBAC(
    database_url=...,
    secret_key=...,
    enable_abac=True,
    # Prefer server-derived context; keep this False unless you know why:
    # trust_resource_context_header=False,
)
auth.instrument_fastapi(app, include_resource_context=True)  # when using request-state merge
```

Do **not** trust client `X-Resource-Context` unless you set
`trust_resource_context_header=True`. Prefer a
`resource_context_provider` that loads attributes from your DB.

---

## Where conditions attach

Same shape on both catalogs ([25](./25-Roles-and-Permissions.md)):

| Attach point | Paths | Auth |
|--------------|-------|------|
| Permission | `/v1/permissions/{id}/condition-groups` + `/conditions` | `permission:read` / `permission:update` |
| Role | `/v1/roles/{id}/condition-groups` + `/conditions` | `role:read` / `role:update` |

**Group:** `operator` `AND` | `OR`, optional description.  
**Condition:** `attribute` (dot path, e.g. `resource.status`), `operator`
(`equals`, `in`, `matches`, …), `value`, `value_type`
(`string` | `integer` | `float` | `boolean` | `list`).

Evaluation shape: ungrouped conditions AND together; within a group use the
group operator; **groups AND together**. Empty conditions → RBAC-only for that
attach point.

**Write validation.** Every condition write (HTTP or service) is validated and
rejected with **400** (`details.reason = invalid_abac_condition`, plus the
offending `field`) when:

- `operator` is not one of `equals`, `not_equals`, `less_than`,
  `less_than_or_equal`, `greater_than`, `greater_than_or_equal`, `in`,
  `not_in`, `contains`, `not_contains`, `starts_with`, `ends_with`,
  `matches`, `exists`, `not_exists`, `is_true`, `is_false`, `before`, `after`
  (case-insensitive; stored lowercase);
- `attribute` is not a dotted path rooted in a context the engine populates:
  `user.`, `resource.`, `env.` or `time.`;
- the value does not fit the operator or `value_type`: `in` / `not_in` need
  `value_type=list` and a list; numeric comparisons need a number; `before` /
  `after` need an ISO 8601 datetime; `matches` needs a compilable regex;
  `integer` / `float` / `boolean` values must parse; value-taking operators
  need a value.

Updates are validated against the condition they would produce.

**Fail closed.** At check time a condition never grants on missing or bad data:
a missing attribute satisfies neither `is_true` nor `is_false`; `not_in` with a
non-list value and `not_contains` on a non-collection attribute are false; a
stored row that cannot be interpreted (legacy operator, unsupported context,
unparseable value) evaluates to false instead of raising.

---

## Evaluation at check time

`auth.deps.require_permission(..., resource_context_provider=...)` builds a
context, then `PermissionService.check_permission(..., resource_context=...)`.

When ABAC is on and condition rows exist: for each candidate grant, **role
conditions must pass**, then **at least one matching permission’s conditions
must pass**. Superusers short-circuit before ABAC. If the flag is on but no
conditions exist, the cheaper non-ABAC path runs.

---

## Example: `abac_cookbook`

Editors may `document:update` only when `resource.status` is `draft` **or**
`review`, using a **server-derived** context (client cannot forge status).

```bash
cd examples/abac_cookbook
uv run python reset_test_env.py
uv run uvicorn main:app --host 127.0.0.1 --port 8005
uv run python ../../scripts/smoke_abac_cookbook.py
```

Smoke: configure permission conditions as admin → editor updates draft (200) /
published (403).

---

## Caveats

- **Not a row-level ACL product** — your host loads resource attributes and
  passes them via `resource_context` / provider.
- **Principal / system API keys** are RBAC-only: if ABAC is on and the required
  permission has conditions, those keys are denied — see
  [API Key Host Integration](./50-API-Key-Host-Integration.md).
- ABAC can disable some permission-cache fast paths; keep conditions focused.
- Client resource-context headers stay off by default on purpose.

---

## Related

- [Configuration](./03-Configuration.md)
- [Roles & Permissions](./25-Roles-and-Permissions.md)
- [Core Authorization Concepts](./13-Core-Authorization-Concepts.md)
- Live demo: [`examples/abac_cookbook/`](../examples/abac_cookbook/)
