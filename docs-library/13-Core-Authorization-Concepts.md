# Core Authorization Concepts

> **Handbook** · Conceptual guide for implementers.  
> Part of the [OutlabsAuth Handbook](./README.md). Choosing a preset:
> [07 — Choosing a Preset](./07-Choosing-a-Preset.md).  
> HTTP surfaces: [Roles & Permissions](./25-Roles-and-Permissions.md) ·
> [Entities](./51-Entities.md) · [Memberships](./54-Entity-Memberships.md).

How users, permissions, roles, and (in Enterprise) entities fit together.

---

## Building blocks

| Piece | Meaning |
|-------|---------|
| **Permission** | One action, usually `resource:action` (`user:create`, `invoice:approve`) |
| **Role** | Named bundle of permissions |
| **User** | Actor who receives roles (directly or via membership) |
| **Entity** (Enterprise) | Context — org, office, team, project group |

Permissions → roles → (assignment) → users. Enterprise inserts **where** into
assignment via entities and memberships.

---

## SimpleRBAC — who can do what?

Flat model: users get roles for the whole app.

```
Permission "user:read"
      ↓
   Role "Viewer"
      ↓
   User (via UserRoleMembership)
```

A user’s effective permissions are the union of all assigned roles.

API: define roles/permissions on `/v1/roles` and `/v1/permissions`, assign with
`/v1/users/{id}/roles` — [25](./25-Roles-and-Permissions.md),
[23](./23-User-Management-API.md).

---

## EnterpriseRBAC — who can do what, where?

Roles apply **inside an entity** (membership), not only globally.

```
Permission "user:manage"     Entity "Eng. Dept"
         ↘                     ↙
           Role "Manager"
                 ↓
        User (EntityMembership + role_ids)
```

Jane is a Manager *in Eng. Dept* — those permissions apply in that context, and
optionally down the tree when using `*_tree` permissions.

API: [Entities](./51-Entities.md) + [Memberships](./54-Entity-Memberships.md).
Direct user↔role still exists for system-wide grants ([23](./23-User-Management-API.md)).

---

## Structural vs access-group entities

### Structural

Formal org chart — “where you work”:

`Company → Division → Department → Team`

### Access group

Cross-cutting group — “what you’re working on” (project team, working group).

Example: ACME has Finance / Engineering / Marketing. Project Phoenix needs
Alice, Bob, and Carol with `phoenix:edit_document`. Create an **access_group**
entity “Project Phoenix Team”, give them a project role there. Their structural
memberships stay unchanged; revoke the access-group membership when the project
ends.

Permission checks aggregate **all** active memberships (structural + groups).

---

## Tree permissions and closure

Enterprise stores ancestor→descendant links in a **closure table** so subtree
queries stay fast. Permissions named like `invoice:approve_tree` grant the
action on an entity **and its descendants**.

Hosts usually:

- Navigate with `/entities/{id}/children|descendants|path`
- Authorize with tree-aware deps / `POST /permissions/check` + `entity_id`

Details: [51 — Entities](./51-Entities.md).

---

## Custom types and depth

`entity_type` is a free-form string (`organization`, `office`, `team`, …). Root
allowed types come from `/v1/config/entity-types`; parents can further restrict
children via `allowed_child_*`. Depth is capped by config (default max depth
around 10).

---

## Related

- [Choosing a Preset](./07-Choosing-a-Preset.md)
- [Roles & Permissions](./25-Roles-and-Permissions.md)
- [Entities](./51-Entities.md)
- [Entity Memberships](./54-Entity-Memberships.md)
- Maintainer depth: [`docs/COMPARISON_MATRIX.md`](../docs/COMPARISON_MATRIX.md)
