# OutlabsAuth User Documentation

Guides for people **embedding OutlabsAuth in a FastAPI app**.

Maintainer design specs live in [`docs/`](../docs/). Prefer this folder, the root
[`README.md`](../README.md), and [`examples/`](../examples/) for implementation work.

## Start Here

| Doc | Purpose |
|-----|---------|
| [01-Getting-Started.md](./01-Getting-Started.md) | Install → migrate → mount routers → login → optional admin UI |
| [02-Routers-and-Prefixes.md](./02-Routers-and-Prefixes.md) | Catalog of `get_*_router` factories and prefix conventions |
| [03-Configuration.md](./03-Configuration.md) | Database, Redis, feature flags, CLI, production baseline |
| [04-OAuth-and-Social-Login.md](./04-OAuth-and-Social-Login.md) | Mount Google/GitHub/… login + associate; social account self-service |
| [05-Sessions-and-Audit.md](./05-Sessions-and-Audit.md) | Active sessions (refresh tokens) and audit search |
| [06-Passwordless-and-Messaging.md](./06-Passwordless-and-Messaging.md) | Magic links, access codes, invites, host email/WhatsApp/SMS delivery |
| [13-Core-Authorization-Concepts.md](./13-Core-Authorization-Concepts.md) | SimpleRBAC vs EnterpriseRBAC mental model |
| [../docs/COMPARISON_MATRIX.md](../docs/COMPARISON_MATRIX.md) | Feature comparison and decision tree |
| [../docs/API_DESIGN.md](../docs/API_DESIGN.md) | Library API surface and host DX patterns |
| [../docs/AUTH_UI.md](../docs/AUTH_UI.md) | [OutlabsAuth UI](https://github.com/outlabsio/OutlabsAuthUI) sister admin console |

## Topic Guides

| Doc | Purpose |
|-----|---------|
| [12-Data-Models.md](./12-Data-Models.md) | SQLModel / Postgres schema reference |
| [22-JWT-Tokens.md](./22-JWT-Tokens.md) | Access / refresh token behavior |
| [23-User-Management-API.md](./23-User-Management-API.md) | User/role HTTP surface (**partially stale** — prefer OpenAPI + routers guide) |
| [24-User-Invitations.md](./24-User-Invitations.md) | Invite flow, config, mail intents |
| [48-User-Status-System.md](./48-User-Status-System.md) | User status enum semantics |
| [49-Activity-Tracking.md](./49-Activity-Tracking.md) | DAU / MAU activity tracking |
| [50-API-Key-Host-Integration.md](./50-API-Key-Host-Integration.md) | Host API-key surface and UI workspaces |
| [54-Entity-Memberships.md](./54-Entity-Memberships.md) | Enterprise membership lifecycle |

## Operations & Observability

| Doc | Purpose |
|-----|---------|
| [95-Testing-Guide.md](./95-Testing-Guide.md) | Testing the library and host integrations |
| [97-Observability.md](./97-Observability.md) | Metrics and logging for host apps |
| [98-Metrics-Reference.md](./98-Metrics-Reference.md) | Prometheus metric catalog |
| [99-Log-Events-Reference.md](./99-Log-Events-Reference.md) | Structured log event catalog |

## Known Gaps

This folder was rebuilt from a larger series; some numbered chapters are still
missing. Until they exist, use:

- **OAuth / passwordless / messaging depth** — [04](./04-OAuth-and-Social-Login.md),
  [06](./06-Passwordless-and-Messaging.md), plus maintainer specs in
  [`docs/AUTH_EXTENSIONS.md`](../docs/AUTH_EXTENSIONS.md) and
  [`docs/WHATSAPP_ACCOUNT_MESSAGING.md`](../docs/WHATSAPP_ACCOUNT_MESSAGING.md)
- **Production deploy** — [03-Configuration.md](./03-Configuration.md) + [`docs/DEPLOYMENT_GUIDE.md`](../docs/DEPLOYMENT_GUIDE.md)
- **Runnable wiring** — [`examples/simple_rbac`](../examples/simple_rbac/) and [`examples/enterprise_rbac`](../examples/enterprise_rbac/)

Where a guide and the code disagree, **the code wins**.
