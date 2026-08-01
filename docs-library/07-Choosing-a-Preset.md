# Choosing a Preset

OutlabsAuth ships two presets. They share the same core library; the difference
is whether you need an **organization tree**.

## Quick chooser

```
Do you need departments, teams, offices, client orgs, or similar hierarchy?
│
├─ No  → SimpleRBAC
│        Users have roles for the whole app.
│
└─ Yes → EnterpriseRBAC
         Users get roles *inside* entities (and optionally down a tree).
```

| | SimpleRBAC | EnterpriseRBAC |
|---|------------|----------------|
| Best for | Blogs, tools, SaaS without org nesting | Companies, franchises, multi-office products |
| Roles | Flat — assigned to the user | Scoped — assigned via entity membership |
| Entities / tree permissions | No | Yes |
| Typical example | [`examples/simple_rbac`](../examples/simple_rbac/) | [`examples/enterprise_rbac`](../examples/enterprise_rbac/) |

## SimpleRBAC in one sentence

“Who can do what?” — roles and permissions for the whole application.

```python
from outlabs_auth import SimpleRBAC

auth = SimpleRBAC(
    database_url=os.environ["DATABASE_URL"],
    secret_key=os.environ["SECRET_KEY"],
)
```

## EnterpriseRBAC in one sentence

“Who can do what, **where**?” — roles apply in an entity context (and optionally
to descendants with `_tree` permissions).

```python
from outlabs_auth import EnterpriseRBAC

auth = EnterpriseRBAC(
    database_url=os.environ["DATABASE_URL"],
    secret_key=os.environ["SECRET_KEY"],
    # Optional extras:
    # enable_context_aware_roles=True,
    # enable_abac=True,
    redis_url=os.environ.get("REDIS_URL"),  # recommended in production
)
```

## Can I switch later?

You can move from Simple to Enterprise when you need hierarchy, but treat it as
a product migration (new entities, memberships, invite rules), not a one-line
flip. Start with the preset that matches the product you are shipping in the
next quarter.

## Go deeper

- Concepts and diagrams: [13 — Core Authorization Concepts](./13-Core-Authorization-Concepts.md)
- Exhaustive feature table (maintainer-oriented): [`docs/COMPARISON_MATRIX.md`](../docs/COMPARISON_MATRIX.md)
- Next: [Getting Started](./01-Getting-Started.md) if you have not wired an app yet
