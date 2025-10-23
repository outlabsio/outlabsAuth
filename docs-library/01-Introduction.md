# Introduction to OutlabsAuth

**Tags**: #getting-started #overview #introduction

## What is OutlabsAuth?

OutlabsAuth is a comprehensive **FastAPI authentication and authorization library** that combines:

- 🔐 **Authentication**: Email/password, OAuth (Google, Facebook, GitHub, etc.), API keys, JWT service tokens
- 🛡️ **Authorization**: Simple flat RBAC or hierarchical enterprise RBAC with tree permissions
- 🏢 **Entity Hierarchy**: Optional organizational structure (departments, teams, projects)
- ⚡ **Performance**: Redis caching, closure table optimization, minimal database queries
- 🎯 **Developer Experience**: 2-line OAuth setup, pre-built routers, lifecycle hooks

---

## Why OutlabsAuth?

### The Problem

Building authentication and authorization for FastAPI applications typically involves:

1. **Authentication**: JWT tokens, OAuth, API keys → 500+ lines of boilerplate
2. **Authorization**: RBAC, permissions, hierarchical access → 1000+ lines of complex logic
3. **Integration**: Connecting auth to FastAPI routes → Error-prone dependency injection
4. **Security**: CSRF protection, token validation, rate limiting → Easy to get wrong

**Result**: Weeks of development, security vulnerabilities, maintenance burden.

### The Solution

OutlabsAuth provides **production-ready auth** that you can integrate in **minutes**:

```python
from fastapi import FastAPI, Depends
from outlabs_auth import SimpleRBAC

app = FastAPI()
auth = SimpleRBAC(database=mongo_client)

# Require authentication
@app.get("/protected")
async def protected_route(user = Depends(auth.deps.require_auth())):
    return {"user_id": user["user_id"]}

# Require specific permission
@app.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    ctx = Depends(auth.deps.require_permission("user:delete"))
):
    await auth.user_service.delete_user(user_id)
    return {"status": "deleted"}
```

**That's it!** You now have:
- ✅ JWT authentication
- ✅ Permission checking
- ✅ User management
- ✅ Secure by default

---

## Key Features

### 🔐 Authentication (Core v1.0)

| Feature | Description | Status |
|---------|-------------|--------|
| **Email/Password** | Traditional username/password auth | ✅ Available |
| **JWT Tokens** | Access (15 min) + Refresh (30 days) tokens | ✅ Available |
| **API Keys** | argon2id hashed, prefixed, rate limited | ✅ Available |
| **Service Tokens** | JWT tokens for microservices (~0.5ms auth) | ✅ Available |
| **OAuth/Social** | Google, Facebook, GitHub, Microsoft, Discord | ✅ Available |
| **Multi-Source** | Fallback chain: JWT → API Key → Service Token | ✅ Available |

### 🛡️ Authorization (Core v1.0)

| Feature | SimpleRBAC | EnterpriseRBAC |
|---------|------------|----------------|
| **Flat RBAC** | ✅ Yes | ✅ Yes |
| **Entity Hierarchy** | ❌ No | ✅ Yes |
| **Tree Permissions** | ❌ No | ✅ Yes |
| **Context-Aware Roles** | ❌ No | ✅ Optional |
| **ABAC Policies** | ❌ No | ✅ Optional |

### 🏢 Entity Hierarchy (EnterpriseRBAC)

```
Company (STRUCTURAL)
├── Engineering Dept (STRUCTURAL)
│   ├── Backend Team (ACCESS_GROUP)
│   └── Frontend Team (ACCESS_GROUP)
└── Sales Dept (STRUCTURAL)
    ├── Enterprise Sales (ACCESS_GROUP)
    └── SMB Sales (ACCESS_GROUP)
```

**Tree Permissions**: Grant `project:read_tree` at "Engineering Dept" → User gets access to ALL projects in Backend and Frontend teams!

### ⚡ Performance

- **Closure Table**: O(1) ancestor/descendant queries (20x improvement over recursive)
- **Redis Caching**: Permission checks, role lookups, entity hierarchies
- **Redis Counters**: API key usage tracking (99%+ reduction in DB writes)
- **Redis Pub/Sub**: <100ms cache invalidation across instances

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Application                      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   OutlabsAuth Library                        │
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  SimpleRBAC  │  │EnterpriseRBAC│  │  AuthDeps    │      │
│  │   (Preset)   │  │   (Preset)   │  │(Dependencies)│      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│         │                  │                  │              │
│         └──────────────────┴──────────────────┘              │
│                            │                                 │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                    Services Layer                     │   │
│  │  • UserService    • RoleService   • PermissionService│   │
│  │  • AuthService    • ApiKeyService • EntityService    │   │
│  └──────────────────────────────────────────────────────┘   │
│                            │                                 │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                  Data Models (Beanie)                 │   │
│  │  • User  • Role  • Permission  • Entity  • ApiKey    │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            │
                ┌───────────┴───────────┐
                ▼                       ▼
        ┌─────────────┐         ┌─────────────┐
        │  MongoDB    │         │   Redis     │
        │  (Primary)  │         │  (Cache)    │
        └─────────────┘         └─────────────┘
```

---

## When to Use OutlabsAuth

### ✅ Perfect For

- **SaaS Applications**: Multi-tenant with hierarchical teams/departments
- **Enterprise Apps**: Complex organizational structures and permissions
- **API Services**: API key authentication for external clients
- **Microservices**: Service-to-service JWT authentication
- **OAuth Apps**: Social login with Google, Facebook, GitHub
- **Rapid Prototyping**: Get auth working in 5 minutes

### ⚠️ Consider Alternatives

- **Simple Auth Only**: If you just need email/password, FastAPI-Users might be simpler
- **SQL Database**: OutlabsAuth uses MongoDB (PostgreSQL support planned for v2.0)
- **OAuth 1.0**: We only support OAuth 2.0 (covers 99% of providers)
- **Non-FastAPI**: This library is FastAPI-native (won't work with Flask/Django)

---

## Comparison with Alternatives

### vs FastAPI-Users

| Feature | OutlabsAuth | FastAPI-Users |
|---------|-------------|---------------|
| Flat RBAC | ✅ Yes | ❌ No |
| Hierarchical RBAC | ✅ Yes | ❌ No |
| Tree Permissions | ✅ Yes | ❌ No |
| OAuth Support | ✅ Yes | ✅ Yes |
| Database | MongoDB | SQL + MongoDB |
| Router Factories | ✅ Yes | ✅ Yes |
| Lifecycle Hooks | ✅ Yes | ✅ Yes |

**Verdict**: OutlabsAuth = FastAPI-Users authentication + Advanced authorization

### vs AuthLib

| Feature | OutlabsAuth | AuthLib |
|---------|-------------|---------|
| FastAPI Native | ✅ Async | ❌ Sync |
| OAuth Support | ✅ Via httpx-oauth | ✅ Built-in |
| Authorization | ✅ Full RBAC | ❌ Basic |
| Pre-built Routers | ✅ Yes | ❌ No |
| Developer Experience | ✅ Excellent | ⚠️ Manual setup |

**Verdict**: OutlabsAuth is more FastAPI-native with better authorization

---

## Quick Decision Guide

**Choose SimpleRBAC if**:
- ✅ Flat organizational structure (no departments/teams)
- ✅ Simple role-based permissions (admin, user, moderator)
- ✅ No hierarchical access control needed
- ✅ Want fastest setup and simplest API

**Choose EnterpriseRBAC if**:
- ✅ Hierarchical organization (company → departments → teams)
- ✅ Need tree permissions (grant access to entire subtrees)
- ✅ Context-aware roles (different permissions per entity type)
- ✅ Complex authorization requirements
- ✅ Multi-tenant SaaS application

**Not sure?** Start with **SimpleRBAC** and upgrade to EnterpriseRBAC later if needed. The migration is straightforward!

---

## What's Next?

Ready to get started?

1. **[[02-Quick-Start|Quick Start]]** - Get OutlabsAuth running in 5 minutes
2. **[[03-Installation|Installation]]** - Installation options and dependencies
3. **[[04-Basic-Concepts|Basic Concepts]]** - Understand core terminology
4. **[[41-SimpleRBAC|SimpleRBAC Guide]]** - Start with flat RBAC
5. **[[42-EnterpriseRBAC|EnterpriseRBAC Guide]]** - Explore hierarchical RBAC

---

## Need Help?

- 📖 **Documentation**: You're reading it! Check the [[README|Table of Contents]]
- 🐛 **Issues**: [GitHub Issues](https://github.com/outlabsio/outlabsAuth/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/outlabsio/outlabsAuth/discussions)
- 📧 **Email**: contact@outlabs.io

---

**Next**: [[02-Quick-Start|Quick Start Guide →]]
