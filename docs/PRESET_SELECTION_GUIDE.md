# OutlabsAuth Preset Selection Guide

**Choose the right authentication preset for your application in 5 minutes.**

---

## Quick Decision Tree

```
START: What type of application are you building?

├─ Do you have organizational hierarchy (departments, teams, divisions)?
│  ├─ NO → SimpleRBAC ✓
│  └─ YES → Continue ↓
│
├─ Do users need different roles in different parts of the organization?
│  ├─ NO → SimpleRBAC ✓
│  └─ YES → Continue ↓
│
├─ Do managers need to control descendant entities/teams?
│  ├─ NO → SimpleRBAC ✓
│  └─ YES → EnterpriseRBAC ✓
```

---

## The Two Presets

### SimpleRBAC
**Flat role hierarchy** - Users have ONE global role

```python
from outlabs_auth import SimpleRBAC

auth = SimpleRBAC(database=mongo_client)
await auth.initialize()
```

**Best for**:
- Personal projects
- SaaS products
- Simple APIs
- Blogs and content sites
- Apps without organizational structure

**Setup time**: 15 minutes

---

### EnterpriseRBAC
**Hierarchical roles** - Users have MULTIPLE roles in different entities

```python
from outlabs_auth import EnterpriseRBAC

auth = EnterpriseRBAC(
    database=mongo_client,
    enable_context_aware_roles=True,  # Optional
    enable_abac=True,                 # Optional
    enable_caching=True,              # Optional
    redis_url="redis://localhost:6379"
)
await auth.initialize()
```

**Best for**:
- Corporate systems
- Multi-tenant applications
- Project management tools
- Enterprise software
- Organizations with departments/teams

**Setup time**: 30 minutes

---

## Feature Comparison

| Feature | SimpleRBAC | EnterpriseRBAC |
|---------|-----------|----------------|
| **Authentication** | ✅ JWT | ✅ JWT |
| **API Keys** | ✅ Yes | ✅ Yes |
| **Service Tokens** | ✅ Yes | ✅ Yes |
| **User Management** | ✅ Full | ✅ Full |
| **Roles per User** | 1 | Multiple |
| **Entity Hierarchy** | ❌ No | ✅ Yes |
| **Tree Permissions** | ❌ No | ✅ Yes |
| **Entity-Scoped Permissions** | ❌ No | ✅ Yes |
| **Context-Aware Roles** | ❌ No | ✅ Optional |
| **ABAC Conditions** | ❌ No | ✅ Optional |
| **Redis Caching** | ❌ No | ✅ Optional |
| **Multi-Tenant** | ❌ No | ✅ Optional |
| **Performance** | Excellent | Excellent (with caching) |
| **Complexity** | ⭐️ Low | ⭐️⭐️⭐️ Medium-High |
| **Learning Curve** | Easy | Moderate |

---

## Use Case Examples

### ✅ Use SimpleRBAC for:

#### 1. Personal Blog
```
Users:
  - Reader (read posts)
  - Writer (create own posts)
  - Editor (manage all posts)
  - Admin (full control)

No hierarchy → SimpleRBAC
```

#### 2. SaaS Product (Flat Structure)
```
Users:
  - Free User (limited features)
  - Pro User (more features)
  - Admin (manage settings)

No departments/teams → SimpleRBAC
```

#### 3. Simple API
```
Clients:
  - Read-Only API Key
  - Read-Write API Key
  - Admin API Key

No organizational context → SimpleRBAC
```

---

### ✅ Use EnterpriseRBAC for:

#### 1. Corporate System
```
Acme Corp
├── Engineering
│   ├── Backend Team (Alice is Team Lead)
│   └── Frontend Team (Bob is Developer)
└── Sales
    └── Regional Team (Charlie is Manager)

Hierarchy + Multiple roles per user → EnterpriseRBAC
```

#### 2. Multi-Tenant SaaS
```
Platform
├── Company A
│   ├── Department 1 (User X is Manager)
│   └── Department 2 (User X is Member)
└── Company B
    └── Department 1 (User Y is Admin)

Each company is isolated → EnterpriseRBAC
```

#### 3. Project Management Tool
```
Organization
├── Project Alpha (Users A, B, C with different roles)
├── Project Beta (Users B, D, E with different roles)
└── Project Gamma (User A is Admin, User F is Viewer)

Projects as entities + role variations → EnterpriseRBAC
```

---

## Real-World Scenarios

### Scenario 1: Blog Platform (SimpleRBAC)

**Requirements**:
- Users can register and create posts
- Roles: Reader, Writer, Editor, Admin
- Writers can edit their own posts
- Editors can edit all posts

**Why SimpleRBAC?**
- ✅ Flat structure (no departments/teams)
- ✅ One role per user
- ✅ Simple permission model
- ✅ No organizational hierarchy

```python
# Implementation
auth = SimpleRBAC(database=mongo_client)

# Create roles
reader = await auth.role_service.create_role(
    name="reader",
    permissions=["post:read"]
)

writer = await auth.role_service.create_role(
    name="writer",
    permissions=["post:read", "post:create", "post:update_own"]
)

editor = await auth.role_service.create_role(
    name="editor",
    permissions=["post:*"]  # Wildcard
)
```

---

### Scenario 2: Corporate HR System (EnterpriseRBAC)

**Requirements**:
- Multi-department company
- Department managers control their department + teams below
- HR admins have company-wide access
- Employees see only their department

**Why EnterpriseRBAC?**
- ✅ Department hierarchy
- ✅ Managers need tree permissions (manage descendants)
- ✅ Different access levels per entity
- ✅ Complex organizational structure

```python
# Implementation
auth = EnterpriseRBAC(database=mongo_client)

# Create hierarchy
company = await auth.entity_service.create_entity(
    name="acme_corp",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="company"
)

hr_dept = await auth.entity_service.create_entity(
    name="hr",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="department",
    parent_id=str(company.id)
)

# Create roles with tree permissions
dept_manager = await auth.role_service.create_role(
    name="dept_manager",
    permissions=[
        "employee:read",
        "employee:manage_tree",  # Manage all employees in subtree
        "entity:update_tree",    # Update all teams below
    ]
)

# Assign user as manager of HR department
await auth.membership_service.add_member(
    entity_id=str(hr_dept.id),
    user_id=manager_id,
    role_ids=[str(dept_manager.id)]
)
```

---

### Scenario 3: GitHub-like Platform (EnterpriseRBAC)

**Requirements**:
- Organizations → Teams → Repositories
- Users can be in multiple organizations
- Users have different roles in different teams
- Repo permissions inherited from team

**Why EnterpriseRBAC?**
- ✅ 3-level hierarchy (Org → Team → Repo)
- ✅ Users belong to multiple contexts
- ✅ Permission inheritance via tree permissions
- ✅ Cross-cutting teams (access groups)

```python
auth = EnterpriseRBAC(database=mongo_client)

# Create organization
org = await auth.entity_service.create_entity(
    name="outlabs",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="organization"
)

# Create team
backend_team = await auth.entity_service.create_entity(
    name="backend",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="team",
    parent_id=str(org.id)
)

# Create repo
api_repo = await auth.entity_service.create_entity(
    name="api",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="repository",
    parent_id=str(backend_team.id)
)

# User roles
- Org Owner: Full control of org and all teams/repos
- Team Admin: Control team and all repos
- Repo Contributor: Write access to specific repo
```

---

## Migration Path

### Starting with SimpleRBAC

If you're unsure, **start with SimpleRBAC**:

1. SimpleRBAC is easier to learn
2. Faster initial development
3. Can migrate to EnterpriseRBAC later if needed

### Migrating to EnterpriseRBAC

When you need hierarchy:

```python
# Before (SimpleRBAC)
auth = SimpleRBAC(database=mongo_client)

# After (EnterpriseRBAC)
auth = EnterpriseRBAC(database=mongo_client)

# Your existing users and roles remain
# Add entity hierarchy on top
```

**Migration steps**:
1. Install EnterpriseRBAC
2. Create top-level entity (company)
3. Migrate existing roles to entity-scoped
4. Add entity memberships for users
5. Test entity-scoped permissions

---

## Cost-Benefit Analysis

### SimpleRBAC

**Benefits**:
- ✅ Fast setup (15 min)
- ✅ Easy to understand
- ✅ Minimal code
- ✅ Great performance
- ✅ Perfect for 80% of apps

**Costs**:
- ❌ No hierarchy
- ❌ One role per user
- ❌ No entity scoping
- ❌ Limited scalability for complex orgs

**Verdict**: Start here for simple apps

---

### EnterpriseRBAC

**Benefits**:
- ✅ Hierarchical structure
- ✅ Multiple roles per user
- ✅ Tree permissions
- ✅ Entity-scoped access
- ✅ Scales to complex organizations
- ✅ O(1) queries with closure table

**Costs**:
- ❌ Longer setup (30-45 min)
- ❌ Steeper learning curve
- ❌ More complex permission model
- ❌ Requires careful planning

**Verdict**: Use for enterprise/corporate apps

---

## Performance Considerations

### SimpleRBAC Performance

```
- User Creation: ~50ms
- Permission Check: ~5ms
- JWT Validation: ~0.5ms (with service tokens)
- Database: MongoDB only
```

**Optimization**: Enable Redis for permission caching (optional)

---

### EnterpriseRBAC Performance

```
- User Creation: ~50ms
- Entity Creation: ~30ms (includes closure table)
- Permission Check: ~10ms (without cache)
- Permission Check: ~1ms (with Redis cache)
- Tree Permission: ~5ms (via closure table, O(1))
- JWT Validation: ~0.5ms (with service tokens)
```

**Optimization**:
- Enable Redis caching (recommended for production)
- Use closure table (enabled by default)
- Enable Pub/Sub cache invalidation

---

## When to Use Optional Features

### EnterpriseRBAC Optional Features

#### Context-Aware Roles
**Use when**: Permissions should vary by entity type

```python
auth = EnterpriseRBAC(
    database=mongo_client,
    enable_context_aware_roles=True  # Enable this
)

# Example: Regional Manager
# - Full control in "region" entities
# - Read-only in "office" entities
# - No access to "team" entities
```

**Don't use when**: Roles are consistent across entity types

---

#### ABAC Conditions
**Use when**: Permissions depend on attributes (budget, department, etc.)

```python
auth = EnterpriseRBAC(
    database=mongo_client,
    enable_abac=True  # Enable this
)

# Example: Approve invoices up to $50,000
# Condition: resource.amount <= 50000
```

**Don't use when**: Simple role-based permissions are sufficient

---

#### Redis Caching
**Use when**: High traffic or many permission checks

```python
auth = EnterpriseRBAC(
    database=mongo_client,
    enable_caching=True,
    redis_url="redis://localhost:6379"
)

# Results:
# - 10x faster permission checks
# - Reduced MongoDB load
# - <100ms cache invalidation across instances
```

**Don't use when**: Low traffic or development environment

---

## Decision Matrix

| Requirement | SimpleRBAC | EnterpriseRBAC | EnterpriseRBAC + ABAC |
|-------------|-----------|----------------|----------------------|
| **Flat roles** | ✅ Perfect | 🟡 Overkill | 🔴 Overkill |
| **Small team** | ✅ Perfect | 🟡 Works | 🔴 Overkill |
| **Departments** | 🔴 Limited | ✅ Perfect | ✅ Perfect |
| **Complex hierarchy** | 🔴 No | ✅ Perfect | ✅ Perfect |
| **Budget limits** | 🔴 No | 🟡 Workaround | ✅ Perfect |
| **Multi-tenant** | 🔴 No | ✅ Perfect | ✅ Perfect |
| **High traffic** | ✅ Fast | 🟡 Needs cache | ✅ With Redis |

Legend:
- ✅ Perfect fit
- 🟡 Works with limitations
- 🔴 Not recommended

---

## Getting Started

### 1. Install OutlabsAuth

```bash
pip install outlabs-auth
```

### 2. Choose Your Preset

Based on this guide, choose:
- **SimpleRBAC**: For simple apps
- **EnterpriseRBAC**: For hierarchical apps

### 3. Follow the Example

- [SimpleRBAC Example](../examples/simple_rbac/)
- [EnterpriseRBAC Example](../examples/enterprise_rbac/)

### 4. Read the Docs

- [API Design](./docs/library-redesign/API_DESIGN.md)
- [Architecture](./docs/library-redesign/LIBRARY_ARCHITECTURE.md)

---

## FAQ

### Q: Can I switch presets later?
**A**: Yes! Start with SimpleRBAC, migrate to EnterpriseRBAC if needed.

### Q: Which is more performant?
**A**: Both are fast. EnterpriseRBAC with Redis caching is optimal for high traffic.

### Q: Do I need Redis?
**A**: No for SimpleRBAC. Optional for EnterpriseRBAC (recommended for production).

### Q: What's the setup time?
**A**: SimpleRBAC: 15 min, EnterpriseRBAC: 30-45 min.

### Q: Can I use both presets?
**A**: No, choose one per application. They're mutually exclusive.

### Q: What if I'm still unsure?
**A**: Start with SimpleRBAC. It's easier and covers most use cases.

---

## Summary

### Choose SimpleRBAC if:
- ✅ Simple app structure
- ✅ One role per user
- ✅ No organizational hierarchy
- ✅ Fast development priority

### Choose EnterpriseRBAC if:
- ✅ Organizational hierarchy
- ✅ Multiple roles per user needed
- ✅ Managers control descendants
- ✅ Entity-scoped permissions required

**Still unsure? Start with SimpleRBAC.**

---

**Need help? Check out the [examples](../examples/) or [open an issue](https://github.com/outlabs/outlabs-auth/issues).**
