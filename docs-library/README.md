# OutlabsAuth Handbook

This is the **user documentation** for people who install OutlabsAuth in a
FastAPI application.

It is written for implementers: clear steps, working examples, and product
language. It is **not** the design-spec tree.

| Folder | Audience | What you’ll find |
|--------|----------|------------------|
| **`docs-library/`** (this handbook) | App developers integrating the library | How to install, configure, mount routers, and ship features |
| [`docs/`](../docs/) | Library maintainers & contributors | Design decisions, audits, release process, deep architecture |
| [`examples/`](../examples/) | Everyone learning by doing | Runnable SimpleRBAC and EnterpriseRBAC apps |

When a guide and the running code disagree, **trust the code** (and please treat
that as a docs bug).

> **Coming later:** this handbook is the content source for a public docs site
> (Nuxt + a docs UI template). Get the structure and wording right here first;
> the site can mirror these sections almost 1:1.

---

## How to read this handbook

### New to OutlabsAuth?

1. [What is OutlabsAuth?](./00-Introduction.md) — mental model in a few minutes
2. [Getting Started](./01-Getting-Started.md) — install, migrate, first login
3. [Choosing Simple vs Enterprise](./07-Choosing-a-Preset.md) — pick a preset
4. Run an [example](../examples/) that matches your preset
5. Optionally plug in [OutlabsAuth UI](../docs/AUTH_UI.md)

### Adding features to an existing integration?

| I want to… | Read |
|------------|------|
| Mount the right HTTP APIs | [Routers & prefixes](./02-Routers-and-Prefixes.md) |
| Tune DB / Redis / cache / flags | [Configuration](./03-Configuration.md) |
| Add Google (or other) social login | [OAuth & social login](./04-OAuth-and-Social-Login.md) |
| Let users see / revoke devices | [Sessions & audit](./05-Sessions-and-Audit.md) |
| Magic links, OTPs, WhatsApp/SMS | [Passwordless & messaging](./06-Passwordless-and-Messaging.md) |
| Invite users by email | [User invitations](./24-User-Invitations.md) |
| Manage the org tree (Enterprise) | [Entities](./51-Entities.md) |
| Assign users to entities | [Entity memberships](./54-Entity-Memberships.md) |
| Add attribute conditions (ABAC) | [ABAC](./26-ABAC.md) |
| Issue API keys from the host app | [API key host integration](./50-API-Key-Host-Integration.md) |
| Understand roles / entities | [Core authorization concepts](./13-Core-Authorization-Concepts.md) |
| Define roles & permission catalog | [Roles & permissions](./25-Roles-and-Permissions.md) |

### Looking up details?

JWT behavior, data models, metrics, and log event catalogs live under
[Reference](#reference) below.

---

## Guide index

### Start here

| Guide | Summary |
|-------|---------|
| [00 — Introduction](./00-Introduction.md) | What the library is, what it is not, and how the pieces fit |
| [01 — Getting Started](./01-Getting-Started.md) | Install → migrate → mount → login → optional admin UI |
| [07 — Choosing a Preset](./07-Choosing-a-Preset.md) | SimpleRBAC vs EnterpriseRBAC in plain language |
| [13 — Core Authorization Concepts](./13-Core-Authorization-Concepts.md) | Users, roles, permissions, entities, tree access |

### Build & configure

| Guide | Summary |
|-------|---------|
| [02 — Routers & Prefixes](./02-Routers-and-Prefixes.md) | Which `get_*_router` factories to mount and how prefixes work |
| [03 — Configuration](./03-Configuration.md) | Secrets, schema, Redis, in-process cache, CLI, production defaults |

### Auth features

| Guide | Summary |
|-------|---------|
| [04 — OAuth & Social Login](./04-OAuth-and-Social-Login.md) | Provider routers, invite-only login, link / unlink accounts |
| [05 — Sessions & Audit](./05-Sessions-and-Audit.md) | Active sessions and searching user audit events |
| [06 — Passwordless & Messaging](./06-Passwordless-and-Messaging.md) | Magic links, access codes, phone channels, host delivery |
| [24 — User Invitations](./24-User-Invitations.md) | Invite-by-email onboarding |
| [23 — User Management API](./23-User-Management-API.md) | Admin + self-service user HTTP surface |
| [25 — Roles & Permissions](./25-Roles-and-Permissions.md) | Permission catalog and role definitions |
| [26 — ABAC](./26-ABAC.md) | Attribute conditions on roles/permissions |
| [48 — User Status](./48-User-Status-System.md) | Active, invited, suspended, deleted, and related states |
| [50 — API Keys (Host Integration)](./50-API-Key-Host-Integration.md) | Personal and system keys for host apps |
| [51 — Entities](./51-Entities.md) | Enterprise org tree CRUD, move, children, path |
| [54 — Entity Memberships](./54-Entity-Memberships.md) | Enterprise membership lifecycle |

### Admin console

| Guide | Summary |
|-------|---------|
| [OutlabsAuth UI](../docs/AUTH_UI.md) | Sister Vite/React console you point at any mounted OutlabsAuth API |

### Reference

Large catalogs (`12` data models, `98` metrics, `99` log events) stay long on
purpose — treat them as lookup appendices, not tutorials.

| Guide | Summary |
|-------|---------|
| [12 — Data Models](./12-Data-Models.md) | Postgres / SQLModel schema reference |
| [22 — JWT Tokens](./22-JWT-Tokens.md) | Access and refresh token behavior |
| [49 — Activity Tracking](./49-Activity-Tracking.md) | DAU / MAU style activity metrics |
| [95 — Testing](./95-Testing-Guide.md) | How to test hosts and the library |
| [97 — Observability](./97-Observability.md) | Metrics and logging for host apps |
| [98 — Metrics Reference](./98-Metrics-Reference.md) | Prometheus metric catalog |
| [99 — Log Events Reference](./99-Log-Events-Reference.md) | Structured log event catalog |

---

## Examples (always prefer these when stuck)

| Example | Port | Best for |
|---------|------|----------|
| [SimpleRBAC blog API](../examples/simple_rbac/) | 8003 | Flat roles, quick local loop |
| [EnterpriseRBAC leads API](../examples/enterprise_rbac/) | 8004 | Hierarchy, memberships, richer admin mounts |
| [ABAC cookbook](../examples/abac_cookbook/) | 8005 | Attribute conditions |

---

## Future docs site (Nuxt) — information architecture

When we stand up a public docs site (Nuxt + docs UI template), mirror this
folder 1:1. Suggested nav:

| Nav section | Handbook sources |
|-------------|------------------|
| **Get started** | `00`, `01`, `07` |
| **Build** | `02`, `03` |
| **Auth** | `04`, `05`, `06`, `22`, `23`, `24`, `25`, `26`, `48` |
| **Enterprise** | `13`, `51`, `54` |
| **Integrations** | `50`, `AUTH_UI.md` (or a short UI page copied from `docs/`) |
| **Reference** | `12`, `49`, `95`, `97`–`99` |
| **Examples** | Link out to `examples/` (or embed READMEs) |

Keep maintainer `docs/` off the public nav (or behind a “Contributing” section).
One Markdown file ≈ one docs route; frontmatter can be added later without
renumbering.

---

## Maintainer docs (usually skip)

Only dive into [`docs/`](../docs/) if you are changing the library itself, reading
audits, or chasing a design decision (DD-xxx). Useful pointers when you need
them:

- [API design / DX patterns](../docs/API_DESIGN.md)
- [Full feature comparison matrix](../docs/COMPARISON_MATRIX.md)
- [Deployment guide](../docs/DEPLOYMENT_GUIDE.md)
- [Auth extensions (deep)](../docs/AUTH_EXTENSIONS.md)
