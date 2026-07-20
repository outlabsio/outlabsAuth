# Introduction

OutlabsAuth is a **library**, not a hosted login service.

You install it into your FastAPI app, point it at **your** PostgreSQL database,
mount the routers you need, and keep authentication and authorization inside
your product. That is the whole point: control and ownership without standing
up a separate IdP you do not control.

## What you get

- **Presets** — `SimpleRBAC` for flat roles, `EnterpriseRBAC` when you need an
  org tree (departments, teams, clients, …)
- **Sign-in** — email/password JWTs, optional OAuth, magic links, access codes
  (including verified-phone / WhatsApp / SMS delivery that *you* own)
- **Admin APIs** — users, roles, permissions, API keys, invitations, sessions,
  audit search, and (Enterprise) entities and memberships
- **Optional UI** — [OutlabsAuth UI](https://github.com/outlabsio/OutlabsAuthUI),
  a sister admin console you point at whatever API mounts this library

## What it is not

- Not a multi-tenant SaaS IdP you “sign up for”
- Not a black-box auth microservice you must deploy separately (unless you
  choose to wrap the library that way)
- Not a replacement for your product UI — the sister admin console is optional
  and generic; your app still owns customer-facing screens

## Mental model

```
Your FastAPI app
├── OutlabsAuth (library)
│   ├── Postgres tables (users, roles, …) in your DB / schema
│   ├── Router factories you choose to mount (/auth, /users, …)
│   └── deps you use on host routes (authenticated, require_permission, …)
└── Optional: OutlabsAuth UI → talks to your mounted API
```

You decide the URL prefix (`/auth`, `/v1`, `/iam`, …). The admin UI’s
`authApiPrefix` must match that choice.

## Two presets

| If you need… | Use |
|--------------|-----|
| Users with global roles (blog, SaaS without org tree) | **SimpleRBAC** |
| Hierarchy, “permissions in this team / office”, tree access | **EnterpriseRBAC** |

Short chooser: [07 — Choosing a Preset](./07-Choosing-a-Preset.md).  
Concepts: [13 — Core Authorization Concepts](./13-Core-Authorization-Concepts.md).

## Next step

[Getting Started →](./01-Getting-Started.md)

Or browse the [handbook home](./README.md) for reading paths and the full index.

> This handbook is Markdown in-repo on purpose. A Nuxt docs site can map these
> guides 1:1 later; we want the wording and structure solid first.
